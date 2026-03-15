from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ai_local_settings import AIProviderSettings, load_ai_provider_settings, save_ai_provider_settings


def render_ai_provider_settings(*, root: Path) -> AIProviderSettings:
    saved = load_ai_provider_settings(root)

    st.markdown("### AI Provider Settings")
    provider_options = ["manual", "openrouter", "deepseek"]
    try:
        provider_index = provider_options.index(saved.provider)
    except ValueError:
        provider_index = 0

    provider = st.selectbox(
        "Script Provider",
        provider_options,
        index=provider_index,
        key="ai_provider_selector_v1",
    )

    openrouter_api_key = saved.openrouter_api_key
    openrouter_model = saved.openrouter_model
    deepseek_api_key = saved.deepseek_api_key
    deepseek_model = saved.deepseek_model
    deepseek_base_url = saved.deepseek_base_url

    if provider == "openrouter":
        openrouter_api_key = st.text_input(
            "OpenRouter API Key",
            value=saved.openrouter_api_key,
            type="password",
            key="ai_openrouter_api_key_v1",
        )
        openrouter_model = st.text_input(
            "OpenRouter Model",
            value=saved.openrouter_model,
            placeholder="openrouter/free",
            key="ai_openrouter_model_v1",
        )
    elif provider == "deepseek":
        deepseek_api_key = st.text_input(
            "DeepSeek API Key",
            value=saved.deepseek_api_key,
            type="password",
            key="ai_deepseek_api_key_v1",
        )
        deepseek_model = st.text_input(
            "DeepSeek Model",
            value=saved.deepseek_model,
            placeholder="deepseek-chat",
            key="ai_deepseek_model_v1",
        )
        deepseek_base_url = st.text_input(
            "DeepSeek Base URL (optional)",
            value=saved.deepseek_base_url,
            placeholder="https://api.deepseek.com",
            key="ai_deepseek_base_url_v1",
        )

    current = AIProviderSettings(
        provider=provider,
        openrouter_api_key=openrouter_api_key.strip(),
        openrouter_model=openrouter_model.strip() or "openrouter/free",
        deepseek_api_key=deepseek_api_key.strip(),
        deepseek_model=deepseek_model.strip() or "deepseek-chat",
        deepseek_base_url=deepseek_base_url.strip() or "https://api.deepseek.com",
    )

    if st.button("Save AI Provider", use_container_width=True, key="ai_provider_save_btn_v1"):
        save_ai_provider_settings(root, current)
        st.success("AI provider settings saved locally.")

    st.caption("Local only: saved to .workspace/ai/provider_settings.json (git-ignored).")
    st.caption("API keys are stored as plain local file text (not a secure vault).")
    return current
