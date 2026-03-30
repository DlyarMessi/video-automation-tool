from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import yaml

NON_ENTRY_KEYS = {
    "version",
    "meta",
    "status",
    "about",
    "principles",
    "governed_fields",
    "notes",
    "entries",
}

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


def _clone_value(value: Any) -> Any:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def extract_registry_entries(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}

    if isinstance(data.get("entries"), dict):
        entries = data.get("entries") or {}
        out: dict[str, dict[str, Any]] = {}
        for key, value in entries.items():
            if isinstance(key, str) and isinstance(value, dict):
                out[key] = value
        return out

    out: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        if key.startswith("_") or key in NON_ENTRY_KEYS:
            continue
        if isinstance(value, dict):
            out[key] = value
    return out


def load_registry_entries(registry_path: Path) -> dict[str, dict[str, Any]]:
    if not registry_path.exists():
        return {}

    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    return extract_registry_entries(data)


def hydrate_slot_from_registry(slot: dict[str, Any], registry_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    hydrated = dict(slot) if isinstance(slot, dict) else {}
    registry_key = _clean_text(hydrated.get("registry_key", ""))

    if not registry_key:
        return hydrated

    entry = registry_map.get(registry_key, {})
    if not isinstance(entry, dict):
        return hydrated

    for key in SEMANTIC_FIELDS:
        cur = hydrated.get(key)
        if cur is None or (isinstance(cur, str) and not cur.strip()) or (isinstance(cur, list) and not cur):
            if key in entry:
                hydrated[key] = _clone_value(entry.get(key))

    entry_defaults = entry.get("defaults", {}) if isinstance(entry.get("defaults", {}), dict) else {}
    slot_defaults = hydrated.get("defaults", {}) if isinstance(hydrated.get("defaults", {}), dict) else {}
    merged_defaults = dict(slot_defaults)

    for key in DEFAULT_FIELDS:
        if key not in merged_defaults and key in entry_defaults:
            merged_defaults[key] = _clone_value(entry_defaults.get(key))

    if merged_defaults:
        hydrated["defaults"] = merged_defaults

    return hydrated


def attach_pool_row_semantics(slot_rows: list[dict[str, Any]], hydrated_slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from src.workflow import _legacy_subject_action_from_content

    def _canonical_tuple(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
        scene = _clean_text(item.get("scene", ""))
        subject = _clean_text(item.get("subject", ""))
        action = _clean_text(item.get("action", ""))
        if not subject and not action:
            content = _clean_text(item.get("content", ""))
            if content:
                derived_subject, derived_action = _legacy_subject_action_from_content(content, "")
                subject = _clean_text(derived_subject)
                action = _clean_text(derived_action)
        coverage = _clean_text(item.get("coverage", ""))
        move = _clean_text(item.get("move", ""))
        return (scene, subject, action, coverage, move)

    by_registry: dict[str, dict[str, Any]] = {}
    by_tuple: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    for slot in hydrated_slots:
        if not isinstance(slot, dict):
            continue

        registry_key = _clean_text(slot.get("registry_key", ""))
        key_tuple = _canonical_tuple(slot)

        if registry_key:
            by_registry[registry_key] = slot
        by_tuple[key_tuple] = slot

    out: list[dict[str, Any]] = []
    for row in slot_rows:
        if not isinstance(row, dict):
            out.append(row)
            continue

        merged = dict(row)
        row_registry_key = _clean_text(row.get("registry_key", ""))
        key_tuple = _canonical_tuple(row)

        source = None
        if row_registry_key and row_registry_key in by_registry:
            source = by_registry[row_registry_key]
        elif key_tuple in by_tuple:
            source = by_tuple[key_tuple]

        if isinstance(source, dict):
            for key in ["registry_key", *SEMANTIC_FIELDS]:
                cur = merged.get(key)
                if key in source and (
                    cur is None
                    or (isinstance(cur, str) and not cur.strip())
                    or (isinstance(cur, list) and not cur)
                ):
                    merged[key] = _clone_value(source.get(key))

            source_defaults = source.get("defaults", {}) if isinstance(source.get("defaults", {}), dict) else {}
            row_defaults = merged.get("defaults", {}) if isinstance(merged.get("defaults", {}), dict) else {}

            for key, value in source_defaults.items():
                if key not in row_defaults:
                    row_defaults[key] = _clone_value(value)

            if row_defaults:
                merged["defaults"] = row_defaults

        out.append(merged)

    return out


def build_pool_card_view(row: dict[str, Any]) -> dict[str, Any]:
    from src.workflow import _legacy_subject_action_from_content

    out = dict(row) if isinstance(row, dict) else {}

    scene = _clean_text(out.get("scene", ""))
    content = _clean_text(out.get("content", ""))
    subject = _clean_text(out.get("subject", ""))
    action = _clean_text(out.get("action", ""))
    coverage = _clean_text(out.get("coverage", ""))
    move = _clean_text(out.get("move", ""))

    if not subject and not action and content:
        derived_subject, derived_action = _legacy_subject_action_from_content(content, "")
        subject = _clean_text(derived_subject)
        action = _clean_text(derived_action)

    canonical_tuple_text = " / ".join([x for x in [scene, subject, action, coverage, move] if x])
    slot_label = _clean_text(out.get("slot_label", ""))
    human_label = _clean_text(out.get("human_label", ""))

    display_label = human_label or slot_label or canonical_tuple_text or "Unnamed Slot"

    out["display_label"] = display_label
    out["slot_label_text"] = slot_label
    out["canonical_tuple_text"] = canonical_tuple_text
    out["legacy_content_text"] = content
    out["subject_text"] = subject
    out["action_text"] = action
    out["registry_key_text"] = _clean_text(out.get("registry_key", ""))
    out["shoot_brief_text"] = _clean_text(out.get("shoot_brief", ""))
    out["purpose_text"] = _clean_text(out.get("purpose", ""))
    out["success_criteria_list"] = _clean_list(out.get("success_criteria", []))
    out["fallback_list"] = _clean_list(out.get("fallback", []))

    return out


def get_brand_validation_status(root: Path, company: str, slugify: Callable[[str], str]) -> dict[str, Any]:
    company_clean = _clean_text(company)
    slug = str(slugify(company_clean)).lower()
    brand_dir = root / "data" / "brands" / slug
    logo_path = brand_dir / "logo.png"
    pool_plan_dir = brand_dir / "pool_plans"
    default_plan_path = pool_plan_dir / "default.yaml"

    available_plans: list[str] = []
    if pool_plan_dir.exists():
        available_plans = sorted([p.stem for p in pool_plan_dir.glob("*.yaml")])

    return {
        "company": company_clean,
        "slug": slug,
        "brand_dir": brand_dir,
        "logo_path": logo_path,
        "pool_plan_dir": pool_plan_dir,
        "default_plan_path": default_plan_path,
        "logo_exists": logo_path.exists(),
        "default_plan_exists": default_plan_path.exists(),
        "available_plans": available_plans,
        "plan_count": len(available_plans),
    }


def build_brand_status_summary(status: dict[str, Any]) -> str:
    logo_state = "logo ready" if bool(status.get("logo_exists")) else "logo optional / not set"
    plan_state = "default plan ready" if bool(status.get("default_plan_exists")) else "default plan not set"
    plan_count = int(status.get("plan_count", 0) or 0)
    return f"Status · {logo_state} · {plan_state} · {plan_count} plan(s)"
