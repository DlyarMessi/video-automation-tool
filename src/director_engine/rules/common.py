from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Optional
import json


HERO_TAGS: Set[str] = {"hero", "landing", "brand", "outro"}
COVERAGE_ORDER = {"wide": 0, "medium": 1, "detail": 2, "hero": 3}


def get_tags(shot: Dict[str, Any]) -> List[str]:
    tags: List[str] = []

    t = shot.get("tags")
    if isinstance(t, list):
        tags.extend([str(x).strip() for x in t if str(x).strip()])

    t1 = shot.get("tag")
    if isinstance(t1, str) and t1.strip():
        tags.append(t1.strip())

    src = shot.get("source")
    if isinstance(src, str) and "tags:" in src:
        try:
            after = src.split("tags:", 1)[1]
            after = after.split()[0]
            for part in after.split(","):
                part = part.strip()
                if part:
                    tags.append(part)
        except Exception:
            pass

    out: List[str] = []
    seen = set()
    for x in tags:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _source_parts(shot: Dict[str, Any]) -> List[str]:
    src = shot.get("source")
    if not isinstance(src, str) or "tags:" not in src:
        return []
    try:
        after = src.split("tags:", 1)[1]
        after = after.split()[0]
        return [x.strip() for x in after.split(",") if x.strip()]
    except Exception:
        return []


def _asset_index_path_from_context(context: Dict[str, Any]) -> Optional[Path]:
    p = context.get("asset_index_path")
    if not p:
        return None
    try:
        return Path(str(p))
    except Exception:
        return None


def _load_asset_index_map(context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cache = context.get("_asset_index_map")
    if isinstance(cache, dict):
        return cache

    path = _asset_index_path_from_context(context)
    if not path or not path.exists():
        context["_asset_index_map"] = {}
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        items: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            raw_assets = data.get("assets", [])
            if isinstance(raw_assets, list):
                items = [x for x in raw_assets if isinstance(x, dict)]
        elif isinstance(data, list):
            items = [x for x in data if isinstance(x, dict)]

        mapping = {}
        for item in items:
            filename = str(item.get("filename", "") or "").strip()
            if filename:
                mapping[filename] = item

        context["_asset_index_map"] = mapping
        return mapping
    except Exception:
        context["_asset_index_map"] = {}
        return {}


def _source_filename(shot: Dict[str, Any]) -> str:
    source_file = str(shot.get("source_file", "") or "").strip()
    if source_file:
        return Path(source_file).name

    selected = str(shot.get("_selected_file", "") or shot.get("selected_file", "") or "").strip()
    if selected:
        return Path(selected).name

    return ""


def get_asset_record(shot: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    mapping = _load_asset_index_map(context)
    filename = _source_filename(shot)
    if not filename:
        return {}
    return mapping.get(filename, {})


def get_scene(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    val = str(
        shot.get("_preferred_scene")
        or shot.get("preferred_scene")
        or shot.get("scene")
        or ""
    ).strip()
    if val:
        return val

    if isinstance(context, dict):
        rec = get_asset_record(shot, context)
        val = str(rec.get("scene", "") or "").strip()
        if val:
            return val

    parts = _source_parts(shot)
    return parts[0] if len(parts) >= 1 else ""


def get_subject(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    val = str(
        shot.get("_preferred_subject")
        or shot.get("preferred_subject")
        or shot.get("subject")
        or ""
    ).strip()
    if val:
        return val

    if isinstance(context, dict):
        rec = get_asset_record(shot, context)
        val = str(rec.get("subject", "") or "").strip()
        if val:
            return val

    parts = _source_parts(shot)
    return parts[1] if len(parts) >= 2 else ""


def get_action(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    val = str(
        shot.get("_preferred_action")
        or shot.get("preferred_action")
        or shot.get("action")
        or ""
    ).strip()
    if val:
        return val

    if isinstance(context, dict):
        rec = get_asset_record(shot, context)
        val = str(rec.get("action", "") or "").strip()
        if val:
            return val

    return ""


def get_content(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    # Transitional alias so older rules keep running while semantics move to subject/action.
    return get_subject(shot, context=context)


def get_coverage(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    val = str(
        shot.get("_preferred_coverage")
        or shot.get("preferred_coverage")
        or shot.get("coverage")
        or ""
    ).strip()
    if val:
        return val

    if isinstance(context, dict):
        rec = get_asset_record(shot, context)
        val = str(rec.get("coverage", "") or "").strip()
        if val:
            return val

    parts = _source_parts(shot)
    return parts[2] if len(parts) >= 3 else ""


def get_move(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    val = str(
        shot.get("_preferred_move")
        or shot.get("preferred_move")
        or shot.get("move")
        or ""
    ).strip()
    if val:
        return val

    if isinstance(context, dict):
        rec = get_asset_record(shot, context)
        val = str(rec.get("move", "") or "").strip()
        if val:
            return val

    parts = _source_parts(shot)
    return parts[3] if len(parts) >= 4 else ""


def get_primary_tag(shot: Dict[str, Any]) -> str:
    if isinstance(shot.get("tag"), str) and shot["tag"].strip():
        return shot["tag"].strip()

    tags = shot.get("tags")
    if isinstance(tags, list) and tags:
        t = str(tags[0]).strip()
        if t:
            return t

    parts = _source_parts(shot)
    return parts[0] if parts else ""


def is_hero_like(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    tags = set(get_tags(shot))
    if tags & HERO_TAGS:
        return True

    coverage = get_coverage(shot, context=context)
    subject = get_subject(shot, context=context)
    primary = get_primary_tag(shot)

    if coverage == "hero":
        return True
    if subject in {"brand", "product"} and coverage in {"wide", "hero"}:
        return True
    if primary in HERO_TAGS:
        return True

    return False


def is_randomish(shot: Dict[str, Any]) -> bool:
    src = str(shot.get("source") or "")
    return src.startswith("random") or "random:" in src or src.startswith("next") or "next:" in src


def same_scene(a: Dict[str, Any], b: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    sa = get_scene(a, context=context)
    sb = get_scene(b, context=context)
    return bool(sa and sb and sa == sb)


def same_subject(a: Dict[str, Any], b: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    sa = get_subject(a, context=context)
    sb = get_subject(b, context=context)
    return bool(sa and sb and sa == sb)


def same_content(a: Dict[str, Any], b: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    # Transitional alias for older rules
    return same_subject(a, b, context=context)


def same_family(a: Dict[str, Any], b: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    return same_scene(a, b, context=context) and same_subject(a, b, context=context)


def coverage_rank(shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> int:
    return COVERAGE_ORDER.get(get_coverage(shot, context=context), 99)


def is_progressive_coverage(prev_shot: Dict[str, Any], cur_shot: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    a = get_coverage(prev_shot, context=context)
    b = get_coverage(cur_shot, context=context)
    if not a or not b:
        return False
    if a == "wide" and b in {"medium", "detail"}:
        return True
    if a == "medium" and b == "detail":
        return True
    return False


def get_continuity_group(shot: Dict[str, Any], context: Dict[str, Any]) -> str:
    rec = get_asset_record(shot, context)
    return str(rec.get("continuity_group", "") or "").strip()


def get_energy(shot: Dict[str, Any], context: Dict[str, Any]) -> str:
    rec = get_asset_record(shot, context)
    val = str(rec.get("energy", "medium") or "medium").strip().lower()
    if val not in {"low", "medium", "high", "mid"}:
        return "medium"
    if val == "mid":
        return "medium"
    return val


def get_quality_status(shot: Dict[str, Any], context: Dict[str, Any]) -> str:
    rec = get_asset_record(shot, context)
    val = str(rec.get("quality_status", "") or "").strip().lower()
    if val not in {"approved", "review", "reject"}:
        return ""
    return val


def is_intro_safe(shot: Dict[str, Any], context: Dict[str, Any]) -> bool:
    rec = get_asset_record(shot, context)
    return bool(rec.get("intro_safe", False))


def is_hero_safe(shot: Dict[str, Any], context: Dict[str, Any]) -> bool:
    rec = get_asset_record(shot, context)
    return bool(rec.get("hero_safe", False))


def is_outro_safe(shot: Dict[str, Any], context: Dict[str, Any]) -> bool:
    rec = get_asset_record(shot, context)
    return bool(rec.get("outro_safe", False))


def get_beat_no(shot: Dict[str, Any]) -> int:
    """Return beat number from shot, 0 if not set."""
    return int(shot.get("_beat_no", 0) or 0)
