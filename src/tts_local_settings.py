from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class TTSRoutingSettings:
    default_provider: str = "elevenlabs"
    use_mms_for_low_resource: bool = True
    mms_override_languages: list[str] | None = None

    def __post_init__(self) -> None:
        if self.mms_override_languages is None:
            self.mms_override_languages = ["kk", "tg", "ky", "ug", "uz"]


def _workspace_root(root: Path) -> Path:
    return root / ".workspace" / "tts"


def tts_settings_path(root: Path) -> Path:
    return _workspace_root(root) / "provider_settings.json"


def load_tts_routing_settings(root: Path) -> TTSRoutingSettings:
    path = tts_settings_path(root)
    if not path.exists():
        return TTSRoutingSettings()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return TTSRoutingSettings()

    default_provider = str(payload.get("default_provider", "elevenlabs") or "elevenlabs").strip().lower()
    if default_provider not in {"elevenlabs", "mms_local"}:
        default_provider = "elevenlabs"

    use_mms_for_low_resource = bool(payload.get("use_mms_for_low_resource", True))

    raw_langs = payload.get("mms_override_languages", ["kk", "tg", "ky", "ug", "uz"])
    if isinstance(raw_langs, list):
        langs = [str(x).strip().lower() for x in raw_langs if str(x).strip()]
    else:
        langs = ["kk", "tg", "ky", "ug", "uz"]

    return TTSRoutingSettings(
        default_provider=default_provider,
        use_mms_for_low_resource=use_mms_for_low_resource,
        mms_override_languages=langs,
    )


def save_tts_routing_settings(root: Path, settings: TTSRoutingSettings) -> Path:
    path = tts_settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_tts_provider(
    *,
    language: str,
    explicit_provider: str = "",
    settings: TTSRoutingSettings | None = None,
) -> str:
    short = str(language or "").split("-", 1)[0].strip().lower()
    explicit = str(explicit_provider or "").strip().lower()

    if explicit in {"elevenlabs", "mms_local", "human_voice_wip"}:
        return explicit

    if short in {"kk", "tg", "ky"}:
        return "mms_local"

    if short == "ug":
        return "human_voice_wip"

    return "elevenlabs"


MMS_MODEL_MAP: dict[str, str] = {
    "kk": "facebook/mms-tts-kaz",
    "tg": "facebook/mms-tts-tgk",
    "ky": "facebook/mms-tts-kir",
    "ug": "facebook/mms-tts-uig-script_arabic",
    "uz": "facebook/mms-tts-uzb-script_cyrillic",
}
