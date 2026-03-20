from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class UILocalPrefs:
    last_company: str = ""
    last_orientation: str = ""


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

    return UILocalPrefs(last_company=str(payload.get("last_company", "") or "").strip())


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
