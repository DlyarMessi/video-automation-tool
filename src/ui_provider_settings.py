from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ai_local_settings import AIProviderSettings, load_ai_provider_settings, save_ai_provider_settings


def render_ai_provider_settings(*, root: Path) -> AIProviderSettings:
    saved = load_ai_provider_settings(root)

    st.markdown("### AI Provider Settings")
    provider = st.selectbox(
        "Script Provider",
        ["manual", "openrouter"],
        index=0 if saved.provider == "manual" else 1,
        key="ai_provider_selector_v1",
    )
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

    current = AIProviderSettings(
        provider=provider,
        openrouter_api_key=openrouter_api_key.strip(),
        openrouter_model=openrouter_model.strip() or "openrouter/free",
    )

    if st.button("Save AI Provider", use_container_width=True, key="ai_provider_save_btn_v1"):
        save_ai_provider_settings(root, current)
        st.success("AI provider settings saved locally.")

    st.caption("Local only: saved to .workspace/ai/provider_settings.json (git-ignored).")
    st.caption("API keys are stored as plain local file text (not a secure vault).")
    return current
