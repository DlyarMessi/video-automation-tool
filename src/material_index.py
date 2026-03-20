from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v"}


def load_asset_index(index_path: Path) -> List[Dict[str, Any]]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and not str(x.get("filename", "")).startswith("._")]
        return []
    except Exception:
        return []


def save_asset_index(index_path: Path, items: List[Dict[str, Any]]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_filename_core(filename: str) -> Dict[str, str]:
    stem = Path(filename).stem
    parts = stem.split("_")

    # canonical factory filename:
    # factory_<scene>_<content>_<coverage>_<move>_<idx>
    if len(parts) >= 6 and parts[0].lower() == "factory":
        return {
            "scene": parts[1],
            "content": parts[2],
            "coverage": parts[3],
            "move": parts[4],
        }

    # fallback for shorter / legacy names
    return {
        "scene": parts[0] if len(parts) >= 1 else "",
        "content": parts[1] if len(parts) >= 2 else "",
        "coverage": parts[2] if len(parts) >= 3 else "",
        "move": parts[3] if len(parts) >= 4 else "",
    }


def probe_duration_seconds(video_path: Path) -> float:
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        out = subprocess.check_output(cmd, text=True).strip()
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
        out = subprocess.check_output(cmd, text=True).strip()
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


def make_asset_record(video_path: Path) -> Dict[str, Any]:
    core = parse_filename_core(video_path.name)
    raw_duration = probe_duration_seconds(video_path)
    usable = default_usable_window(raw_duration)

    return {
        "filename": video_path.name,
        "scene": core["scene"],
        "content": core["content"],
        "coverage": core["coverage"],
        "move": core["move"],
        "orientation": infer_orientation(video_path),
        "raw_duration": raw_duration,
        "usable_start": usable["usable_start"],
        "usable_end": usable["usable_end"],
        "usable_duration": usable["usable_duration"],
        "hero_safe": False,
        "intro_safe": False,
        "outro_safe": False,
        "continuity_group": "",
        "energy": "medium",
        "quality_status": "approved",
        "notes": "",
    }


def upsert_asset_record(index_path: Path, video_path: Path) -> Dict[str, Any]:
    # skip macOS resource fork files
    if video_path.name.startswith("._"):
        return {}
    items = load_asset_index(index_path)
    items_by_name = {str(item.get("filename", "")): item for item in items if isinstance(item, dict)}

    existing = items_by_name.get(video_path.name)
    fresh = make_asset_record(video_path)

    if existing:
        for key in [
            "hero_safe",
            "intro_safe",
            "outro_safe",
            "continuity_group",
            "energy",
            "quality_status",
            "notes",
        ]:
            fresh[key] = existing.get(key, fresh[key])

    items_by_name[video_path.name] = fresh
    merged = sorted(items_by_name.values(), key=lambda x: str(x.get("filename", "")))
    save_asset_index(index_path, merged)
    return fresh


def update_asset_record_fields(index_path: Path, filename: str, updates: Dict[str, Any]) -> bool:
    items = load_asset_index(index_path)
    changed = False

    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("filename", "")) != str(filename):
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
        break

    if changed:
        save_asset_index(index_path, items)

    return changed


def find_asset_record(index_path: Path, filename: str) -> Dict[str, Any]:
    items = load_asset_index(index_path)
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("filename", "")) == str(filename):
            return item
    return {}
