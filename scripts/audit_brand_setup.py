#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "data" / "brands"
REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"
DOCS_AUDIT_DIR = ROOT / "docs" / "brand_audits"

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
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def load_registry_keys() -> set[str]:
    data = load_yaml(REGISTRY_PATH)
    return set(extract_registry_entries(data).keys())


def get_plan_files(brand_dir: Path) -> list[Path]:
    plan_dir = brand_dir / "pool_plans"
    if not plan_dir.exists():
        return []
    return sorted(list(plan_dir.glob("*.yaml")) + list(plan_dir.glob("*.yml")))


def choose_plan(brand_dir: Path, plan_name: str) -> Path | None:
    plan_dir = brand_dir / "pool_plans"
    if not plan_dir.exists():
        return None

    if not plan_name:
        for p in [plan_dir / "default.yaml", plan_dir / "default.yml"]:
            if p.exists():
                return p
        plans = get_plan_files(brand_dir)
        return plans[0] if plans else None

    slug = safe_slug(plan_name)
    for ext in (".yaml", ".yml"):
        p = plan_dir / f"{slug}{ext}"
        if p.exists():
            return p

    for p in get_plan_files(brand_dir):
        if p.stem.lower() == slug:
            return p

    return None


def iter_slots(plan_data: dict[str, Any]) -> list[dict[str, Any]]:
    topics = plan_data.get("topics", [])
    if not isinstance(topics, list):
        return []

    out: list[dict[str, Any]] = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        topic_name = str(topic.get("name", "") or "").strip()
        slots = topic.get("slots", [])
        if not isinstance(slots, list):
            continue
        for idx, slot in enumerate(slots, start=1):
            if not isinstance(slot, dict):
                continue
            x = dict(slot)
            x["_topic"] = topic_name
            x["_topic_slot_index"] = idx
            out.append(x)
    return out


def derived_registry_key(slot: dict[str, Any]) -> str:
    scene = str(slot.get("scene", "") or "").strip().lower()
    content = str(slot.get("content", "") or "").strip().lower()
    coverage = str(slot.get("coverage", "") or "").strip().lower()
    move = str(slot.get("move", "") or "").strip().lower()
    return ".".join([scene, content, coverage, move]).strip(".")


def count_semantic_coverage(slots: list[dict[str, Any]]) -> dict[str, int]:
    covered = 0
    full = 0
    for s in slots:
        present = 0
        for key in SEMANTIC_FIELDS:
            value = s.get(key)
            if isinstance(value, list):
                if value:
                    present += 1
            elif str(value or "").strip():
                present += 1
        if present > 0:
            covered += 1
        if present == len(SEMANTIC_FIELDS):
            full += 1
    return {"any": covered, "full": full}


def count_defaults_coverage(slots: list[dict[str, Any]]) -> dict[str, int]:
    covered = 0
    full = 0
    for s in slots:
        defaults = s.get("defaults", {})
        if not isinstance(defaults, dict):
            continue
        present = 0
        for key in DEFAULT_FIELDS:
            if key in defaults:
                present += 1
        if present > 0:
            covered += 1
        if present == len(DEFAULT_FIELDS):
            full += 1
    return {"any": covered, "full": full}


def build_markdown_report(
    brand_name: str,
    brand_dir: Path,
    logo_exists: bool,
    plan_files: list[Path],
    selected_plan: Path | None,
    slots: list[dict[str, Any]],
    registry_keys: set[str],
    warnings: list[str],
    mismatches: list[str],
    missing_registry: list[str],
    duplicates: list[str],
) -> str:
    semantic = count_semantic_coverage(slots)
    defaults = count_defaults_coverage(slots)

    topics = Counter(str(s.get("_topic", "") or "").strip() for s in slots)
    topic_count = len([k for k in topics if k])

    lines: list[str] = []
    lines.append(f"# Brand Audit · {brand_name}")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Brand dir: `{brand_dir.relative_to(ROOT)}`")
    lines.append(f"- Logo: `{'found' if logo_exists else 'optional / not set'}`")
    lines.append(f"- Pool plan count: **{len(plan_files)}**")
    lines.append(f"- Selected plan: `{selected_plan.name if selected_plan else '(none)'}`")
    lines.append(f"- Topic count: **{topic_count}**")
    lines.append(f"- Slot count: **{len(slots)}**")
    lines.append(f"- Registry entries available: **{len(registry_keys)}**")
    lines.append("")
    lines.append("## Coverage summary")
    lines.append("")
    lines.append(f"- Semantic fields present on at least one level: **{semantic['any']}/{len(slots) if slots else 0}**")
    lines.append(f"- Semantic fields fully populated: **{semantic['full']}/{len(slots) if slots else 0}**")
    lines.append(f"- Defaults present on at least one level: **{defaults['any']}/{len(slots) if slots else 0}**")
    lines.append(f"- Defaults fully populated: **{defaults['full']}/{len(slots) if slots else 0}**")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    lines.append(f"- Derived-key mismatches: **{len(mismatches)}**")
    lines.append(f"- Registry keys missing from taxonomy: **{len(missing_registry)}**")
    lines.append(f"- Duplicate registry keys inside plan: **{len(duplicates)}**")
    lines.append(f"- Warnings: **{len(warnings)}**")
    lines.append("")

    if warnings:
        lines.append("### Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    if mismatches:
        lines.append("### Derived key mismatches")
        lines.append("")
        for item in mismatches[:30]:
            lines.append(f"- {item}")
        lines.append("")

    if missing_registry:
        lines.append("### Missing in registry")
        lines.append("")
        for item in missing_registry[:30]:
            lines.append(f"- {item}")
        lines.append("")

    if duplicates:
        lines.append("### Duplicate registry keys")
        lines.append("")
        for item in duplicates[:30]:
            lines.append(f"- {item}")
        lines.append("")

    if topics:
        lines.append("## Topics")
        lines.append("")
        for topic_name, count in topics.items():
            lines.append(f"- `{topic_name or '(unnamed topic)'}` · {count} slot(s)")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit a brand's setup, pool plans, and registry linkage."
    )
    parser.add_argument("brand_name", help="Brand display name or slug, e.g. Siglen")
    parser.add_argument("--plan", default="default", help="Plan name to audit (default: default)")
    parser.add_argument("--write-report", action="store_true", help="Write a markdown report to docs/brand_audits/")
    args = parser.parse_args()

    brand_name = str(args.brand_name or "").strip()
    brand_dir = get_brand_dir(brand_name)
    logo_path = brand_dir / "logo.png"
    logo_exists = logo_path.exists()
    plan_files = get_plan_files(brand_dir)
    selected_plan = choose_plan(brand_dir, args.plan)
    registry_keys = load_registry_keys()

    print(f"=== Brand Audit · {brand_name} ===")
    print(f"brand_dir           : {brand_dir}")
    print(f"logo                : {'found' if logo_exists else 'optional / not set'}")
    print(f"pool_plan_count     : {len(plan_files)}")

    if plan_files:
        print("available_plans     : " + ", ".join([p.stem for p in plan_files]))
    else:
        print("available_plans     : (none)")

    warnings: list[str] = []
    mismatches: list[str] = []
    missing_registry: list[str] = []
    duplicates: list[str] = []
    slots: list[dict[str, Any]] = []

    if not brand_dir.exists():
        warnings.append("Brand directory does not exist.")
    if not selected_plan:
        warnings.append("No plan selected or available for audit.")
    else:
        print(f"selected_plan       : {selected_plan.relative_to(ROOT)}")
        plan_data = load_yaml(selected_plan)
        if not isinstance(plan_data, dict):
            warnings.append("Selected plan YAML could not be parsed as a dictionary.")
        else:
            slots = iter_slots(plan_data)
            topic_count = len({str(s.get('_topic', '') or '').strip() for s in slots if str(s.get('_topic', '') or '').strip()})
            print(f"topic_count         : {topic_count}")
            print(f"slot_count          : {len(slots)}")

            semantic = count_semantic_coverage(slots)
            defaults = count_defaults_coverage(slots)
            print(f"semantic_any        : {semantic['any']}/{len(slots) if slots else 0}")
            print(f"semantic_full       : {semantic['full']}/{len(slots) if slots else 0}")
            print(f"defaults_any        : {defaults['any']}/{len(slots) if slots else 0}")
            print(f"defaults_full       : {defaults['full']}/{len(slots) if slots else 0}")

            seen_keys: list[str] = []
            for slot in slots:
                topic_name = str(slot.get("_topic", "") or "").strip()
                slot_idx = slot.get("_topic_slot_index", "?")
                rk = str(slot.get("registry_key", "") or "").strip()
                dk = derived_registry_key(slot)

                if not rk:
                    warnings.append(f"{topic_name} #{slot_idx}: missing registry_key")
                else:
                    seen_keys.append(rk)
                    if rk != dk:
                        mismatches.append(f"{topic_name} #{slot_idx}: registry_key='{rk}' but derived='{dk}'")
                    if registry_keys and rk not in registry_keys:
                        missing_registry.append(f"{topic_name} #{slot_idx}: {rk}")

            dup_counter = Counter(seen_keys)
            duplicates = [f"{k} · {v} occurrences" for k, v in dup_counter.items() if v > 1]

    if warnings:
        print("warnings           :")
        for w in warnings:
            print(f"  - {w}")

    if mismatches:
        print("derived_mismatches :")
        for item in mismatches[:20]:
            print(f"  - {item}")

    if missing_registry:
        print("missing_in_registry:")
        for item in missing_registry[:20]:
            print(f"  - {item}")

    if duplicates:
        print("duplicate_keys     :")
        for item in duplicates[:20]:
            print(f"  - {item}")

    if args.write_report:
        DOCS_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        slug = safe_slug(brand_name) or "starter"
        report_path = DOCS_AUDIT_DIR / f"{slug}_brand_audit.md"
        report = build_markdown_report(
            brand_name=brand_name,
            brand_dir=brand_dir,
            logo_exists=logo_exists,
            plan_files=plan_files,
            selected_plan=selected_plan,
            slots=slots,
            registry_keys=registry_keys,
            warnings=warnings,
            mismatches=mismatches,
            missing_registry=missing_registry,
            duplicates=duplicates,
        )
        report_path.write_text(report, encoding="utf-8")
        print(f"report_written      : {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
