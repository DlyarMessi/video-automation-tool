from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
RENDER_PRESET_PATH = ROOT / "data" / "render_presets.json"


def load_render_presets() -> Dict[str, Any]:
    if not RENDER_PRESET_PATH.exists():
        return {}
    try:
        data = json.loads(RENDER_PRESET_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_default_fps() -> int:
    presets = load_render_presets()
    defaults = presets.get("defaults", {}) if isinstance(presets.get("defaults"), dict) else {}
    fps = defaults.get("fps", 60)
    try:
        return int(fps)
    except Exception:
        return 60


def get_language_family(lang_code: str) -> str:
    presets = load_render_presets()
    mapping = presets.get("language_to_family", {}) if isinstance(presets.get("language_to_family"), dict) else {}
    short = (lang_code or "en").split("-")[0].lower()
    family = mapping.get(short, "latin")
    return str(family or "latin")


def get_subtitle_style(lang_code: str) -> Dict[str, Any]:
    presets = load_render_presets()
    family = get_language_family(lang_code)
    subtitle_presets = presets.get("subtitle_presets", {}) if isinstance(presets.get("subtitle_presets"), dict) else {}
    style = subtitle_presets.get(family, {}) if isinstance(subtitle_presets.get(family), dict) else {}
    out = dict(style)
    out["family"] = family
    return out
