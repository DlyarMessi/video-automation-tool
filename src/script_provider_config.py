from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class OpenRouterConfig:
    api_key: str
    model: str = "openrouter/free"
    site_url: str = ""
    app_name: str = ""


@dataclass
class DeepSeekConfig:
    api_key: str
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"


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


def load_deepseek_config(*, model_override: str = "") -> DeepSeekConfig:
    api_key = str(os.getenv("DEEPSEEK_API_KEY", "") or "").strip()
    env_model = str(os.getenv("DEEPSEEK_MODEL", "deepseek-chat") or "deepseek-chat").strip()
    model = str(model_override or env_model or "deepseek-chat").strip() or "deepseek-chat"
    base_url = str(os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com") or "https://api.deepseek.com").strip()
    return DeepSeekConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
    )
