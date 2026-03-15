from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class OpenRouterConfig:
    api_key: str
    model: str = "openrouter/free"
    site_url: str = ""
    app_name: str = ""


def load_openrouter_config(*, model_override: str = "") -> OpenRouterConfig:
    api_key = str(os.getenv("OPENROUTER_API_KEY", "") or "").strip()
    env_model = str(os.getenv("OPENROUTER_MODEL", "openrouter/free") or "openrouter/free").strip()
    model = str(model_override or env_model or "openrouter/free").strip() or "openrouter/free"
    site_url = str(os.getenv("OPENROUTER_SITE_URL", "") or "").strip()
    app_name = str(os.getenv("OPENROUTER_APP_NAME", "") or "").strip()
    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        site_url=site_url,
        app_name=app_name,
    )
