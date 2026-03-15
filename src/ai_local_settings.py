from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AIProviderSettings:
    provider: str = "manual"
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"


def _workspace_root(root: Path) -> Path:
    return root / ".workspace" / "ai"


def provider_settings_path(root: Path) -> Path:
    return _workspace_root(root) / "provider_settings.json"


def ai_runs_dir(root: Path) -> Path:
    return _workspace_root(root) / "ai_runs"


def load_ai_provider_settings(root: Path) -> AIProviderSettings:
    path = provider_settings_path(root)
    if not path.exists():
        return AIProviderSettings()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return AIProviderSettings()

    if not isinstance(payload, dict):
        return AIProviderSettings()

    provider = str(payload.get("provider", "manual") or "manual").strip().lower()
    if provider not in {"manual", "openrouter", "deepseek"}:
        provider = "manual"

    return AIProviderSettings(
        provider=provider,
        openrouter_api_key=str(payload.get("openrouter_api_key", "") or "").strip(),
        openrouter_model=str(payload.get("openrouter_model", "openrouter/free") or "openrouter/free").strip() or "openrouter/free",
        deepseek_api_key=str(payload.get("deepseek_api_key", "") or "").strip(),
        deepseek_model=str(payload.get("deepseek_model", "deepseek-chat") or "deepseek-chat").strip() or "deepseek-chat",
        deepseek_base_url=str(payload.get("deepseek_base_url", "https://api.deepseek.com") or "https://api.deepseek.com").strip() or "https://api.deepseek.com",
    )


def save_ai_provider_settings(root: Path, settings: AIProviderSettings) -> Path:
    path = provider_settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def save_ai_run_payload(root: Path, payload: dict[str, Any], *, brand_name: str = "") -> Path:
    out_dir = ai_runs_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(brand_name or "run")).strip("_") or "run"
    path = out_dir / f"{timestamp}_{slug}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
