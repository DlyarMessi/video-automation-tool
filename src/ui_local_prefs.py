from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class UILocalPrefs:
    last_company: str = ""
    last_orientation: str = ""
    last_tts_language: str = ""
    last_eleven_model_id: str = "eleven_multilingual_v2"
    last_voice_ids: dict[str, str] | None = None
    last_input_root: str = ""
    last_output_root: str = ""
    last_work_mode: str = ""
    last_planning_entry_mode_key: str = ""
    last_src_mode: str = ""
    last_active_creative_path: str = ""
    last_selected_script_path: str = ""

    def __post_init__(self) -> None:
        if self.last_voice_ids is None:
            self.last_voice_ids = {}


def _prefs_path(root: Path) -> Path:
    return root / ".workspace" / "ui" / "ui_prefs.json"


def load_ui_local_prefs(root: Path) -> UILocalPrefs:
    path = _prefs_path(root)
    if not path.exists():
        return UILocalPrefs()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return UILocalPrefs()

    if not isinstance(payload, dict):
        return UILocalPrefs()

    raw_voice_ids = payload.get("last_voice_ids", {})
    if not isinstance(raw_voice_ids, dict):
        raw_voice_ids = {}

    return UILocalPrefs(
        last_company=str(payload.get("last_company", "") or "").strip(),
        last_orientation=str(payload.get("last_orientation", "") or "").strip(),
        last_tts_language=str(payload.get("last_tts_language", "") or "").strip(),
        last_eleven_model_id=str(payload.get("last_eleven_model_id", "eleven_multilingual_v2") or "eleven_multilingual_v2").strip(),
        last_input_root=str(payload.get("last_input_root", "") or "").strip(),
        last_output_root=str(payload.get("last_output_root", "") or "").strip(),
        last_work_mode=str(payload.get("last_work_mode", "") or "").strip(),
        last_planning_entry_mode_key=str(payload.get("last_planning_entry_mode_key", "") or "").strip(),
        last_src_mode=str(payload.get("last_src_mode", "") or "").strip(),
        last_active_creative_path=str(payload.get("last_active_creative_path", "") or "").strip(),
        last_selected_script_path=str(payload.get("last_selected_script_path", "") or "").strip(),
        last_voice_ids={
            str(k).strip().lower(): str(v or "").strip()
            for k, v in raw_voice_ids.items()
            if str(k).strip()
        },
    )


def save_ui_local_prefs(root: Path, prefs: UILocalPrefs) -> Path:
    path = _prefs_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(prefs), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def remember_last_company(root: Path, company: str) -> None:
    clean = str(company or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_company == clean:
        return
    prefs.last_company = clean
    save_ui_local_prefs(root, prefs)


def clear_last_company(root: Path) -> None:
    prefs = load_ui_local_prefs(root)
    if not prefs.last_company:
        return
    prefs.last_company = ""
    save_ui_local_prefs(root, prefs)


def remember_last_orientation(root: Path, orientation: str) -> None:
    clean = str(orientation or "").strip()
    if clean not in ("portrait", "landscape"):
        return
    prefs = load_ui_local_prefs(root)
    if prefs.last_orientation == clean:
        return
    prefs.last_orientation = clean
    save_ui_local_prefs(root, prefs)


def remember_last_tts_language(root: Path, lang_code: str) -> None:
    clean = str(lang_code or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_tts_language == clean:
        return
    prefs.last_tts_language = clean
    save_ui_local_prefs(root, prefs)


def remember_last_eleven_model_id(root: Path, model_id: str) -> None:
    clean = str(model_id or "").strip() or "eleven_multilingual_v2"
    prefs = load_ui_local_prefs(root)
    if prefs.last_eleven_model_id == clean:
        return
    prefs.last_eleven_model_id = clean
    save_ui_local_prefs(root, prefs)


def remember_last_voice_id(root: Path, lang_short: str, voice_id: str) -> None:
    key = str(lang_short or "").strip().lower()
    if not key:
        return
    clean_voice = str(voice_id or "").strip()
    prefs = load_ui_local_prefs(root)
    current = dict(prefs.last_voice_ids or {})
    if current.get(key, "") == clean_voice:
        return
    current[key] = clean_voice
    prefs.last_voice_ids = current
    save_ui_local_prefs(root, prefs)


def remember_last_input_root(root: Path, input_root: str) -> None:
    clean = str(input_root or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_input_root == clean:
        return
    prefs.last_input_root = clean
    save_ui_local_prefs(root, prefs)


def remember_last_output_root(root: Path, output_root: str) -> None:
    clean = str(output_root or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_output_root == clean:
        return
    prefs.last_output_root = clean
    save_ui_local_prefs(root, prefs)


def get_last_input_root(root: Path, default: Path) -> Path:
    prefs = load_ui_local_prefs(root)
    raw = str(prefs.last_input_root or "").strip()
    return Path(raw).expanduser() if raw else default


def get_last_output_root(root: Path, default: Path) -> Path:
    prefs = load_ui_local_prefs(root)
    raw = str(prefs.last_output_root or "").strip()
    return Path(raw).expanduser() if raw else default


def remember_last_work_mode(root: Path, work_mode: str) -> None:
    clean = str(work_mode or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_work_mode == clean:
        return
    prefs.last_work_mode = clean
    save_ui_local_prefs(root, prefs)


def remember_last_planning_entry_mode_key(root: Path, mode_key: str) -> None:
    clean = str(mode_key or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_planning_entry_mode_key == clean:
        return
    prefs.last_planning_entry_mode_key = clean
    save_ui_local_prefs(root, prefs)


def remember_last_src_mode(root: Path, src_mode: str) -> None:
    clean = str(src_mode or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_src_mode == clean:
        return
    prefs.last_src_mode = clean
    save_ui_local_prefs(root, prefs)


def remember_last_active_creative_path(root: Path, creative_path: str) -> None:
    clean = str(creative_path or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_active_creative_path == clean:
        return
    prefs.last_active_creative_path = clean
    save_ui_local_prefs(root, prefs)


def remember_last_selected_script_path(root: Path, script_path: str) -> None:
    clean = str(script_path or "").strip()
    prefs = load_ui_local_prefs(root)
    if prefs.last_selected_script_path == clean:
        return
    prefs.last_selected_script_path = clean
    save_ui_local_prefs(root, prefs)
