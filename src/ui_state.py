from __future__ import annotations

from typing import Any


UI_SESSION_DEFAULTS: dict[str, Any] = {
    "active_creative_path": None,
    "creative_draft": "",
    "run_dir": None,
    "shooting_rows": [],
    "compiled_out_path": None,
    "work_mode": "Project Mode",
}


def _clone_default(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def ensure_ui_session_defaults(session_state) -> None:
    for key, value in UI_SESSION_DEFAULTS.items():
        if key not in session_state:
            session_state[key] = _clone_default(value)
