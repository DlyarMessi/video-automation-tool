from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v"}

SCENE_VALUES = {
    "exterior",
    "entrance",
    "showroom",
    "factory-floor",
    "factory-line",
    "workstation",
    "testing-area",
    "warehouse",
    "office",
}

SUBJECT_VALUES = {
    "person",
    "product",
    "machine",
    "part",
    "panel",
    "workspace",
    "environment",
}

ACTION_VALUES = {
    "display",
    "operate",
    "process",
    "assemble",
    "inspect",
    "transport",
    "interact",
    "idle",
    "close",
}

COVERAGE_VALUES = {"wide", "medium", "close", "detail"}

MOVE_VALUES = {
    "static",
    "pan",
    "tilt",
    "slide",
    "pushin",
    "pushout",
    "follow",
    "orbit",
    "reveal",
}

SEGMENT_RE = re.compile(r"^[a-z0-9-]+$")
VARIANT_RE = re.compile(r"^v[1-9][0-9]*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_catalog(root_input_dir: str = "", orientation: str = "") -> Dict[str, Any]:
    return {
        "schema_version": "asset-index-v1",
        "catalog_meta": {
            "generated_at": _now_iso(),
            "root_input_dir": root_input_dir,
            "orientation": orientation,
            "asset_count": 0,
            "valid_asset_count": 0,
            "invalid_asset_count": 0,
        },
        "assets": [],
        "by_asset_id": {},
        "stats": {
            "by_scene": {},
            "by_subject": {},
            "by_action": {},
            "by_coverage": {},
            "by_move": {},
            "by_validity": {},
        },
    }


def load_asset_catalog(index_path: Path) -> Dict[str, Any]:
    if not index_path.exists():
        return _new_catalog()

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return _new_catalog()

    if isinstance(data, dict) and data.get("schema_version") == "asset-index-v1":
        data.setdefault("catalog_meta", {})
        data.setdefault("assets", [])
        data.setdefault("by_asset_id", {})
        data.setdefault("stats", {})
        return data

    if isinstance(data, list):
        catalog = _new_catalog()
        catalog["assets"] = [x for x in data if isinstance(x, dict)]
        catalog["catalog_meta"]["asset_count"] = len(catalog["assets"])
        return catalog

    return _new_catalog()


def save_asset_catalog(index_path: Path, catalog: Dict[str, Any]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def load_asset_index(index_path: Path) -> List[Dict[str, Any]]:
    catalog = load_asset_catalog(index_path)
    assets = catalog.get("assets", [])
    return [x for x in assets if isinstance(x, dict) and not str(x.get("filename", "")).startswith("._")]


def save_asset_index(index_path: Path, items: List[Dict[str, Any]]) -> None:
    catalog = _new_catalog()
    catalog["assets"] = [x for x in items if isinstance(x, dict)]
    catalog = rebuild_catalog_views(catalog)
    save_asset_catalog(index_path, catalog)


def split_filename_stem(filename: str) -> Dict[str, str]:
    p = Path(filename)
    return {"stem": p.stem, "ext": p.suffix.lower()}


def split_naming_segments(stem: str) -> Dict[str, Any]:
    parts = str(stem or "").split("_")
    errors: List[str] = []
    if len(parts) != 6:
        errors.append(f"Expected 6 naming segments, got {len(parts)}")
    return {"parts": parts, "errors": errors}


def normalize_segment_value(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def validate_segment_format(name: str, value: str) -> List[str]:
    errors: List[str] = []
    if not value:
        errors.append(f"{name} is empty")
        return errors
    if "_" in value:
        errors.append(f"{name} contains illegal '_'")
    if not SEGMENT_RE.match(value):
        if name == "variant" and VARIANT_RE.match(value):
            return errors
        errors.append(f"{name} contains illegal characters")
    return errors


def _validate_in_dict(name: str, value: str, allowed: set[str]) -> Dict[str, Any]:
    if value in allowed:
        return {"canonical_value": value, "status": "accepted", "notes": ""}
    return {
        "canonical_value": value,
        "status": "rejected",
        "notes": f"{name} is not in canonical dictionary",
    }


def validate_scene_value(value: str) -> Dict[str, Any]:
    return _validate_in_dict("scene", value, SCENE_VALUES)


def validate_subject_value(value: str) -> Dict[str, Any]:
    return _validate_in_dict("subject", value, SUBJECT_VALUES)


def validate_action_value(value: str) -> Dict[str, Any]:
    return _validate_in_dict("action", value, ACTION_VALUES)


def validate_coverage_value(value: str) -> Dict[str, Any]:
    return _validate_in_dict("coverage", value, COVERAGE_VALUES)


def validate_move_value(value: str) -> Dict[str, Any]:
    return _validate_in_dict("move", value, MOVE_VALUES)


def validate_variant_value(value: str) -> Dict[str, Any]:
    if VARIANT_RE.match(value):
        return {"canonical_value": value, "status": "accepted", "notes": ""}
    return {
        "canonical_value": value,
        "status": "rejected",
        "notes": "variant must match v1 / v2 / v3 ...",
    }


def parse_canonical_stem(filename: str) -> Dict[str, Any]:
    name_info = split_filename_stem(filename)
    stem = name_info["stem"]
    ext = name_info["ext"]

    result: Dict[str, Any] = {
        "stem": stem,
        "ext": ext,
        "scene": "",
        "subject": "",
        "action": "",
        "coverage": "",
        "move": "",
        "variant": "",
        "is_valid": False,
        "errors": [],
        "warnings": [],
    }

    if ext and ext not in VIDEO_EXTS:
        result["errors"].append(f"Unsupported extension: {ext}")

    split_result = split_naming_segments(stem)
    result["errors"].extend(split_result["errors"])
    parts = split_result["parts"]

    if len(parts) != 6:
        return result

    keys = ["scene", "subject", "action", "coverage", "move", "variant"]
    normalized: Dict[str, str] = {}
    for key, raw in zip(keys, parts):
        clean = normalize_segment_value(raw)
        normalized[key] = clean
        result[key] = clean
        result["errors"].extend(validate_segment_format(key, clean))

    validators = {
        "scene": validate_scene_value,
        "subject": validate_subject_value,
        "action": validate_action_value,
        "coverage": validate_coverage_value,
        "move": validate_move_value,
        "variant": validate_variant_value,
    }

    for key in keys:
        check = validators[key](normalized[key])
        if check["status"] != "accepted":
            result["errors"].append(check["notes"])

    result["is_valid"] = len(result["errors"]) == 0
    return result


def probe_duration_seconds(video_path: Path) -> float:
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        return round(float(out), 3)
    except Exception:
        return 0.0


def infer_orientation(video_path: Path) -> str:
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(video_path),
        ]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        w_str, h_str = out.split("x")
        w = int(w_str)
        h = int(h_str)
        return "portrait" if h >= w else "landscape"
    except Exception:
        return ""


def default_usable_window(raw_duration: float) -> Dict[str, float]:
    d = float(raw_duration or 0.0)
    if d <= 0:
        return {"usable_start": 0.0, "usable_end": 0.0, "usable_duration": 0.0}

    if d >= 3.0:
        start = 1.0
        end = max(start, d - 1.0)
    else:
        start = 0.2
        end = max(start, d - 0.2)

    return {
        "usable_start": round(start, 3),
        "usable_end": round(end, 3),
        "usable_duration": round(max(0.0, end - start), 3),
    }


def derive_bucket_signatures(record: Dict[str, Any]) -> Dict[str, str]:
    primary = "|".join(
        [
            str(record.get("scene", "") or ""),
            str(record.get("subject", "") or ""),
            str(record.get("action", "") or ""),
        ]
    )
    style = "|".join(
        [
            str(record.get("coverage", "") or ""),
            str(record.get("move", "") or ""),
        ]
    )
    return {
        "primary_bucket_signature": primary,
        "style_signature": style,
    }


def _build_asset_id(video_path: Path) -> str:
    digest = hashlib.sha1(str(video_path.as_posix()).encode("utf-8")).hexdigest()
    return f"asset-{digest[:12]}"


def attach_validation_state(
    *,
    parse_result: Dict[str, Any],
    raw_duration: float,
    usable_duration: float,
    quality_status: str,
) -> Dict[str, Any]:
    errors = list(parse_result.get("errors", []))
    warnings = list(parse_result.get("warnings", []))

    if raw_duration <= 0:
        errors.append("Media probe failed or duration is zero")

    if usable_duration <= 0:
        errors.append("Usable duration is zero")

    qs = str(quality_status or "approved").strip().lower()
    if qs not in {"approved", "review", "reject"}:
        warnings.append(f"Unknown quality_status '{quality_status}', defaulting to approved")
        qs = "approved"

    if errors:
        ingest_status = "rejected"
        ingest_status_label = "Rejected"
        ingest_reason_summary = errors[0]
        next_action_hint = "Fix naming or media issues, then re-index this asset."
    elif qs == "review":
        ingest_status = "indexed_but_blocked"
        ingest_status_label = "Blocked"
        ingest_reason_summary = "Blocked: quality_status is review"
        next_action_hint = "Review the asset and change quality_status to approved when ready."
    elif qs == "reject":
        ingest_status = "indexed_but_blocked"
        ingest_status_label = "Blocked"
        ingest_reason_summary = "Blocked: quality_status is reject"
        next_action_hint = "Replace or reclassify this asset before allocation."
    else:
        ingest_status = "valid_allocatable"
        ingest_status_label = "Ready"
        ingest_reason_summary = "Naming valid and ready for allocation"
        next_action_hint = "No action needed"

    return {
        "is_valid": ingest_status == "valid_allocatable",
        "validation_errors": errors,
        "validation_warnings": warnings,
        "ingest_status": ingest_status,
        "ingest_status_label": ingest_status_label,
        "ingest_reason_summary": ingest_reason_summary,
        "next_action_hint": next_action_hint,
        "quality_status": qs,
    }


def build_asset_record_v1(video_path: Path, existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    existing = existing or {}
    parse_result = parse_canonical_stem(video_path.name)
    raw_duration = probe_duration_seconds(video_path)
    usable = default_usable_window(raw_duration)

    base_quality = str(existing.get("quality_status", "approved") or "approved").strip().lower()
    validation = attach_validation_state(
        parse_result=parse_result,
        raw_duration=raw_duration,
        usable_duration=usable["usable_duration"],
        quality_status=base_quality,
    )

    record: Dict[str, Any] = {
        "asset_id": _build_asset_id(video_path),
        "filename": video_path.name,
        "path": str(video_path),
        "orientation": infer_orientation(video_path),
        "raw_duration": raw_duration,
        "usable_start": usable["usable_start"],
        "usable_end": usable["usable_end"],
        "usable_duration": usable["usable_duration"],
        "scene": parse_result.get("scene", ""),
        "subject": parse_result.get("subject", ""),
        "action": parse_result.get("action", ""),
        "coverage": parse_result.get("coverage", ""),
        "move": parse_result.get("move", ""),
        "variant": parse_result.get("variant", ""),
        "hero_safe": bool(existing.get("hero_safe", False)),
        "intro_safe": bool(existing.get("intro_safe", False)),
        "outro_safe": bool(existing.get("outro_safe", False)),
        "continuity_group": str(existing.get("continuity_group", "") or ""),
        "energy": str(existing.get("energy", "mid") or "mid"),
        "notes": str(existing.get("notes", "") or ""),
    }

    record.update(validation)
    record.update(derive_bucket_signatures(record))
    return record


def rebuild_catalog_views(catalog: Dict[str, Any]) -> Dict[str, Any]:
    assets = [x for x in catalog.get("assets", []) if isinstance(x, dict)]

    by_asset_id = {
        str(item.get("asset_id", "") or ""): item
        for item in assets
        if str(item.get("asset_id", "") or "")
    }

    def _count(key: str) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for item in assets:
            value = str(item.get(key, "") or "")
            out[value] = out.get(value, 0) + 1
        return dict(sorted(out.items()))

    by_validity: Dict[str, int] = {}
    for item in assets:
        value = str(item.get("ingest_status_label", "") or "")
        by_validity[value] = by_validity.get(value, 0) + 1

    valid_count = sum(1 for item in assets if item.get("ingest_status") == "valid_allocatable")
    invalid_count = len(assets) - valid_count

    catalog["by_asset_id"] = by_asset_id
    catalog["stats"] = {
        "by_scene": _count("scene"),
        "by_subject": _count("subject"),
        "by_action": _count("action"),
        "by_coverage": _count("coverage"),
        "by_move": _count("move"),
        "by_validity": dict(sorted(by_validity.items())),
    }
    catalog["catalog_meta"]["generated_at"] = _now_iso()
    catalog["catalog_meta"]["asset_count"] = len(assets)
    catalog["catalog_meta"]["valid_asset_count"] = valid_count
    catalog["catalog_meta"]["invalid_asset_count"] = invalid_count
    return catalog


def upsert_asset_record(index_path: Path, video_path: Path) -> Dict[str, Any]:
    if video_path.name.startswith("._"):
        return {}

    catalog = load_asset_catalog(index_path)
    assets = [x for x in catalog.get("assets", []) if isinstance(x, dict)]
    existing_by_filename = {str(item.get("filename", "") or ""): item for item in assets}

    existing = existing_by_filename.get(video_path.name, {})
    fresh = build_asset_record_v1(video_path, existing=existing)

    existing_by_filename[video_path.name] = fresh
    catalog["assets"] = sorted(existing_by_filename.values(), key=lambda x: str(x.get("filename", "")))
    catalog = rebuild_catalog_views(catalog)
    save_asset_catalog(index_path, catalog)
    return fresh


def update_asset_record_fields(index_path: Path, filename: str, updates: Dict[str, Any]) -> bool:
    catalog = load_asset_catalog(index_path)
    assets = [x for x in catalog.get("assets", []) if isinstance(x, dict)]
    changed = False

    for item in assets:
        if str(item.get("filename", "") or "") != str(filename):
            continue

        for key in [
            "hero_safe",
            "intro_safe",
            "outro_safe",
            "continuity_group",
            "energy",
            "quality_status",
            "notes",
        ]:
            if key in updates:
                item[key] = updates[key]
                changed = True

        if changed:
            rebuilt = build_asset_record_v1(Path(str(item.get("path", ""))), existing=item)
            item.clear()
            item.update(rebuilt)
        break

    if changed:
        catalog["assets"] = assets
        catalog = rebuild_catalog_views(catalog)
        save_asset_catalog(index_path, catalog)

    return changed


def find_asset_record(index_path: Path, filename: str) -> Dict[str, Any]:
    catalog = load_asset_catalog(index_path)
    for item in catalog.get("assets", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("filename", "") or "") == str(filename):
            return item
    return {}


def rebuild_asset_index_v1(index_path: Path, input_dir: Path) -> Dict[str, Any]:
    catalog = _new_catalog(root_input_dir=str(input_dir))
    assets: List[Dict[str, Any]] = []

    for video_path in sorted(input_dir.rglob("*")):
        if not video_path.is_file():
            continue
        if video_path.name.startswith("._"):
            continue
        if video_path.suffix.lower() not in VIDEO_EXTS:
            continue
        assets.append(build_asset_record_v1(video_path))

    catalog["assets"] = assets
    catalog = rebuild_catalog_views(catalog)
    save_asset_catalog(index_path, catalog)
    return catalog
