#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "data" / "brands"
REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"

ALLOWED_COVERAGE = {"wide", "medium", "detail", "hero"}
ALLOWED_PRIORITY = {"high", "medium", "low"}

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


def safe_slug(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def is_template_brand_name(name: str) -> bool:
    clean = str(name or "").strip()
    return clean == "_starter" or safe_slug(clean) == "starter"


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
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def choose_plan(brand_dir: Path, plan_name: str) -> Path:
    plan_dir = brand_dir / "pool_plans"
    if not plan_dir.exists():
        raise FileNotFoundError(f"Missing pool_plans directory: {plan_dir}")

    slug = safe_slug(plan_name or "default")
    candidates = [
        plan_dir / f"{slug}.yaml",
        plan_dir / f"{slug}.yml",
    ]
    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(f"Could not find plan '{plan_name}' under {plan_dir}")


def load_registry_keys() -> set[str]:
    if not REGISTRY_PATH.exists():
        return set()

    data = load_yaml(REGISTRY_PATH)
    if not isinstance(data, dict):
        return set()

    keys = set()
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_") or k in {"version", "meta"}:
            continue
        if isinstance(v, dict):
            keys.add(k)
    return keys


def derived_registry_key(slot: dict[str, Any]) -> str:
    scene = str(slot.get("scene", "") or "").strip().lower()
    content = str(slot.get("content", "") or "").strip().lower()
    coverage = str(slot.get("coverage", "") or "").strip().lower()
    move = str(slot.get("move", "") or "").strip().lower()
    return ".".join([scene, content, coverage, move]).strip(".")


def semantic_coverage(slots: list[dict[str, Any]]) -> tuple[int, int]:
    any_count = 0
    full_count = 0
    for s in slots:
        present = 0
        for key in SEMANTIC_FIELDS:
            val = s.get(key)
            if isinstance(val, list):
                if val:
                    present += 1
            elif str(val or "").strip():
                present += 1
        if present > 0:
            any_count += 1
        if present == len(SEMANTIC_FIELDS):
            full_count += 1
    return any_count, full_count


def defaults_coverage(slots: list[dict[str, Any]]) -> tuple[int, int]:
    any_count = 0
    full_count = 0
    for s in slots:
        d = s.get("defaults", {})
        if not isinstance(d, dict):
            continue
        present = sum(1 for k in DEFAULT_FIELDS if k in d)
        if present > 0:
            any_count += 1
        if present == len(DEFAULT_FIELDS):
            full_count += 1
    return any_count, full_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a brand pool plan against structure and registry rules."
    )
    parser.add_argument("brand_name", help="Brand display name or slug, e.g. Siglen or _starter")
    parser.add_argument("--plan", default="default", help="Plan name under data/brands/<slug>/pool_plans/")
    args = parser.parse_args()

    brand_dir = get_brand_dir(args.brand_name)
    plan_path = choose_plan(brand_dir, args.plan)
    registry_keys = load_registry_keys()
    template_mode = is_template_brand_name(args.brand_name) or brand_dir.name == "_starter"

    data = load_yaml(plan_path)
    errors: list[str] = []
    warnings: list[str] = []
    slots: list[dict[str, Any]] = []

    if not isinstance(data, dict):
        errors.append("Top-level YAML must be a dictionary.")
    else:
        topics = data.get("topics", None)
        if not isinstance(topics, list):
            errors.append("Top-level field 'topics' must be a list.")
        else:
            for topic_idx, topic in enumerate(topics, start=1):
                if not isinstance(topic, dict):
                    errors.append(f"Topic #{topic_idx} must be a dictionary.")
                    continue

                topic_name = str(topic.get("name", "") or "").strip()
                if not topic_name:
                    warnings.append(f"Topic #{topic_idx} has no name.")

                topic_slots = topic.get("slots", None)
                if not isinstance(topic_slots, list):
                    errors.append(f"Topic '{topic_name or topic_idx}' must contain a list field: slots")
                    continue

                for slot_idx, slot in enumerate(topic_slots, start=1):
                    if not isinstance(slot, dict):
                        errors.append(f"Topic '{topic_name or topic_idx}' slot #{slot_idx} must be a dictionary.")
                        continue

                    slot["_topic_name"] = topic_name or f"topic-{topic_idx}"
                    slot["_slot_index"] = slot_idx
                    slots.append(slot)

    seen_registry_keys: list[str] = []

    for slot in slots:
        topic_name = str(slot.get("_topic_name", "") or "").strip()
        slot_idx = slot.get("_slot_index", "?")
        prefix = f"{topic_name} :: slot #{slot_idx}"

        for required in ["scene", "content", "coverage", "move", "target", "priority"]:
            if required not in slot:
                errors.append(f"{prefix} missing required field: {required}")

        coverage = str(slot.get("coverage", "") or "").strip().lower()
        if coverage and coverage not in ALLOWED_COVERAGE:
            errors.append(f"{prefix} invalid coverage: {coverage}")

        priority = str(slot.get("priority", "") or "").strip().lower()
        if priority and priority not in ALLOWED_PRIORITY:
            errors.append(f"{prefix} invalid priority: {priority}")

        target = slot.get("target", None)
        if target is not None:
            try:
                if int(target) < 0:
                    errors.append(f"{prefix} target must be >= 0")
            except Exception:
                errors.append(f"{prefix} target must be an integer")

        registry_key = str(slot.get("registry_key", "") or "").strip()
        if not registry_key:
            warnings.append(f"{prefix} missing registry_key")
        else:
            seen_registry_keys.append(registry_key)
            derived = derived_registry_key(slot)
            if derived and registry_key != derived:
                msg = f"{prefix} registry_key mismatch: '{registry_key}' != derived '{derived}'"
                if template_mode:
                    warnings.append(msg)
                else:
                    errors.append(msg)
            if registry_keys and registry_key not in registry_keys:
                msg = f"{prefix} registry_key not found in canonical registry: {registry_key}"
                if template_mode:
                    warnings.append(msg)
                else:
                    errors.append(msg)

        defaults = slot.get("defaults", None)
        if defaults is not None and not isinstance(defaults, dict):
            errors.append(f"{prefix} defaults must be a dictionary if present")

        success_criteria = slot.get("success_criteria", None)
        if success_criteria is not None and not isinstance(success_criteria, list):
            errors.append(f"{prefix} success_criteria must be a list if present")

        fallback = slot.get("fallback", None)
        if fallback is not None and not isinstance(fallback, list):
            errors.append(f"{prefix} fallback must be a list if present")

    dup_counter = Counter(seen_registry_keys)
    duplicate_keys = [k for k, v in dup_counter.items() if v > 1]
    for k in duplicate_keys:
        msg = f"Duplicate registry_key in plan: {k}"
        if template_mode:
            warnings.append(msg)
        else:
            errors.append(msg)

    semantic_any, semantic_full = semantic_coverage(slots)
    defaults_any, defaults_full = defaults_coverage(slots)

    print(f"=== Pool Plan Validation | {args.brand_name} / {args.plan} ===")
    print(f"plan_path         : {plan_path.relative_to(ROOT)}")
    print(f"slot_count        : {len(slots)}")
    print(f"semantic_any      : {semantic_any}/{len(slots) if slots else 0}")
    print(f"semantic_full     : {semantic_full}/{len(slots) if slots else 0}")
    print(f"defaults_any      : {defaults_any}/{len(slots) if slots else 0}")
    print(f"defaults_full     : {defaults_full}/{len(slots) if slots else 0}")
    print(f"errors            : {len(errors)}")
    print(f"warnings          : {len(warnings)}")
    print(f"template_mode     : {'yes' if template_mode else 'no'}")

    if warnings:
        print("warning_items:")
        for item in warnings[:50]:
            print(f"  - {item}")

    if errors:
        print("error_items:")
        for item in errors[:50]:
            print(f"  - {item}")
        sys.exit(1)

    print("validation        : PASS")
