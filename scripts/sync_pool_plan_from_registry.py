#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "data" / "brands"
REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"

SEMANTIC_FIELDS = [
    "human_label",
    "shoot_brief",
    "success_criteria",
    "fallback",
    "purpose",
]

DEFAULT_FIELDS = [
    "energy",
    "quality_status",
    "continuity_group",
    "intro_safe",
    "hero_safe",
    "outro_safe",
]

NON_ENTRY_KEYS = {"version", "meta", "status", "about", "principles", "governed_fields", "notes", "entries"}


def safe_slug(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_brand_dir(brand_name: str) -> Path:
    clean = str(brand_name or "").strip()
    if clean == "_starter":
        return BRANDS_DIR / "_starter"

    slug = safe_slug(clean)
    if slug == "starter" and (BRANDS_DIR / "_starter").exists():
        return BRANDS_DIR / "_starter"

    return BRANDS_DIR / slug


def load_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def save_yaml(path: Path, data: Any) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def choose_plan(brand_dir: Path, plan_name: str) -> Path:
    plan_dir = brand_dir / "pool_plans"
    if not plan_dir.exists():
        raise FileNotFoundError(f"Missing pool_plans directory: {plan_dir}")

    slug = safe_slug(plan_name or "default")
    for ext in (".yaml", ".yml"):
        p = plan_dir / f"{slug}{ext}"
        if p.exists():
            return p

    raise FileNotFoundError(f"Could not find plan '{plan_name}' under {plan_dir}")


def extract_registry_entries(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}

    if isinstance(data.get("entries"), dict):
        entries = data.get("entries") or {}
        out: dict[str, dict[str, Any]] = {}
        for k, v in entries.items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k] = v
        return out

    out: dict[str, dict[str, Any]] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_") or k in NON_ENTRY_KEYS:
            continue
        if isinstance(v, dict):
            out[k] = v
    return out


def load_registry_entries() -> dict[str, dict[str, Any]]:
    data = load_yaml(REGISTRY_PATH)
    return extract_registry_entries(data)


def iter_topic_slots(plan_data: dict[str, Any]) -> list[tuple[int, int, dict[str, Any], dict[str, Any]]]:
    topics = plan_data.get("topics", [])
    if not isinstance(topics, list):
        return []

    out: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for topic_idx, topic in enumerate(topics):
        if not isinstance(topic, dict):
            continue
        slots = topic.get("slots", [])
        if not isinstance(slots, list):
            continue
        for slot_idx, slot in enumerate(slots):
            if not isinstance(slot, dict):
                continue
            out.append((topic_idx, slot_idx, topic, slot))
    return out


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def merge_field(slot: dict[str, Any], registry_entry: dict[str, Any], key: str, mode: str) -> bool:
    if key not in registry_entry:
        return False
    reg_val = registry_entry.get(key)

    if mode == "overwrite":
        if slot.get(key) != reg_val:
            slot[key] = copy.deepcopy(reg_val)
            return True
        return False

    if is_missing_value(slot.get(key)):
        slot[key] = copy.deepcopy(reg_val)
        return True
    return False


def merge_defaults(slot: dict[str, Any], registry_entry: dict[str, Any], mode: str) -> int:
    reg_defaults = registry_entry.get("defaults", {})
    if not isinstance(reg_defaults, dict):
        return 0

    slot_defaults = slot.get("defaults", {})
    if not isinstance(slot_defaults, dict):
        slot_defaults = {}

    changed = 0
    for key in DEFAULT_FIELDS:
        if key not in reg_defaults:
            continue

        if mode == "overwrite":
            if slot_defaults.get(key) != reg_defaults.get(key):
                slot_defaults[key] = copy.deepcopy(reg_defaults.get(key))
                changed += 1
        else:
            if key not in slot_defaults:
                slot_defaults[key] = copy.deepcopy(reg_defaults.get(key))
                changed += 1

    if changed > 0:
        slot["defaults"] = slot_defaults
    return changed


def sync_plan_from_registry(
    plan_data: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    mode: str = "fill-missing",
) -> dict[str, Any]:
    if mode not in {"fill-missing", "overwrite"}:
        raise ValueError("mode must be 'fill-missing' or 'overwrite'")

    slots_info = iter_topic_slots(plan_data)

    slot_count = 0
    matched_count = 0
    missing_registry_keys: list[str] = []
    registry_not_found: list[str] = []
    semantic_changes = 0
    defaults_changes = 0

    for _, slot_idx, topic, slot in slots_info:
        slot_count += 1
        topic_name = str(topic.get("name", "") or "").strip()
        registry_key = str(slot.get("registry_key", "") or "").strip()

        if not registry_key:
            missing_registry_keys.append(f"{topic_name} :: slot #{slot_idx + 1}")
            continue

        registry_entry = registry.get(registry_key)
        if not isinstance(registry_entry, dict):
            registry_not_found.append(f"{topic_name} :: slot #{slot_idx + 1} :: {registry_key}")
            continue

        matched_count += 1

        for key in SEMANTIC_FIELDS:
            if merge_field(slot, registry_entry, key, mode):
                semantic_changes += 1

        defaults_changes += merge_defaults(slot, registry_entry, mode)

    return {
        "plan_data": plan_data,
        "slot_count": slot_count,
        "matched_count": matched_count,
        "missing_registry_keys": missing_registry_keys,
        "registry_not_found": registry_not_found,
        "semantic_changes": semantic_changes,
        "defaults_changes": defaults_changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync semantic/default fields from canonical registry into a brand pool plan."
    )
    parser.add_argument("brand_name", help="Brand display name or slug, e.g. Siglen")
    parser.add_argument("--plan", default="default", help="Plan name under data/brands/<slug>/pool_plans/")
    parser.add_argument(
        "--mode",
        default="fill-missing",
        choices=["fill-missing", "overwrite"],
        help="fill-missing = only fill empty fields; overwrite = replace with registry values",
    )
    parser.add_argument("--write", action="store_true", help="Write changes back to the YAML file")
    args = parser.parse_args()

    brand_dir = get_brand_dir(args.brand_name)
    plan_path = choose_plan(brand_dir, args.plan)
    registry = load_registry_entries()
    plan_data = load_yaml(plan_path)

    if not isinstance(plan_data, dict):
        raise ValueError(f"Plan YAML must be a dictionary: {plan_path}")

    result = sync_plan_from_registry(plan_data, registry, mode=args.mode)

    print(f"=== Registry Sync | {args.brand_name} / {plan_path.stem} ===")
    print(f"plan_path            : {plan_path.relative_to(ROOT)}")
    print(f"mode                 : {args.mode}")
    print(f"slot_count           : {result['slot_count']}")
    print(f"registry_matched     : {result['matched_count']}")
    print(f"semantic_changes     : {result['semantic_changes']}")
    print(f"defaults_changes     : {result['defaults_changes']}")
    print(f"missing_registry_key : {len(result['missing_registry_keys'])}")
    print(f"registry_not_found   : {len(result['registry_not_found'])}")

    if result["missing_registry_keys"]:
        print("missing_registry_key_items:")
        for item in result["missing_registry_keys"][:20]:
            print(f"  - {item}")

    if result["registry_not_found"]:
        print("registry_not_found_items:")
        for item in result["registry_not_found"][:20]:
            print(f"  - {item}")

    if args.write:
        save_yaml(plan_path, result["plan_data"])
        print("write_back           : done")
    else:
        print("write_back           : skipped (--write not set)")


if __name__ == "__main__":
    main()
