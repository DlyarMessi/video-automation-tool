from __future__ import annotations

from dataclasses import asdict
from pathlib import Path


from src.ai_local_settings import AIProviderSettings, save_ai_run_payload
from src.intake_models import NormalizedIntakeBrief
from src.intake_validation import normalize_and_validate_brief
from src.script_pipeline import build_default_compiler_bundle, run_script_pipeline
from src.intake_compiler import compile_brief_to_constraints
from src.script_provider_config import load_openrouter_config
from src.script_provider_manual import ManualScriptProvider
from src.script_provider_openrouter import OpenRouterScriptProvider


def parse_list_text(value: str) -> list[str]:
    parts = str(value or "").replace("\n", ",").split(",")
    out: list[str] = []
    seen: set[str] = set()
    for item in parts:
        clean = str(item or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def compile_intake_brief(brief: NormalizedIntakeBrief, *, root: Path):
    bundle = build_default_compiler_bundle(root)
    normalized = normalize_and_validate_brief(brief)
    constraints = compile_brief_to_constraints(normalized, bundle)
    return normalized, constraints, bundle


def _build_provider(settings: AIProviderSettings):
    if settings.provider == "openrouter":
        cfg = load_openrouter_config(model_override=settings.openrouter_model)
        return OpenRouterScriptProvider(
            api_key=settings.openrouter_api_key or cfg.api_key,
            model=settings.openrouter_model or cfg.model,
            site_url=cfg.site_url,
            app_name=cfg.app_name,
        )
    return ManualScriptProvider()


def render_ai_script_entry_panel(*, root: Path, company: str, orientation: str, provider_settings: AIProviderSettings) -> None:
    import streamlit as st

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    with st.expander("AI Script Entry (Beta)", expanded=False):
        st.caption("Governed flow: intake brief → compiled constraints → provider response.")

        c1, c2 = st.columns(2)
        with c1:
            brand_name = st.text_input("brand_name", value=company, key="ai_brief_brand_v1")
            product_name = st.text_input("product_name", value="", key="ai_brief_product_v1")
            audience = st.text_input("audience", value="", key="ai_brief_audience_v1")
            objective = st.text_input("objective", value="", key="ai_brief_objective_v1")
            language = st.text_input("language", value="en-US", key="ai_brief_language_v1")
            brief_orientation = st.selectbox(
                "orientation",
                ["portrait", "landscape"],
                index=0 if orientation == "portrait" else 1,
                key="ai_brief_orientation_v1",
            )
            duration_s = st.number_input("duration_s", min_value=1, max_value=600, value=45, step=1, key="ai_brief_duration_v1")
            tone = st.text_input("tone", value="", key="ai_brief_tone_v1")

        with c2:
            style_keywords = st.text_area("style_keywords", value="", help="Comma-separated or one per line", key="ai_brief_style_v1")
            must_include = st.text_area("must_include", value="", help="Comma-separated or one per line", key="ai_brief_must_v1")
            avoid = st.text_area("avoid", value="", help="Comma-separated or one per line", key="ai_brief_avoid_v1")
            available_locations = st.text_area("available_locations", value="", key="ai_brief_locations_v1")
            available_assets = st.text_area("available_assets", value="", key="ai_brief_assets_v1")
            available_people = st.text_area("available_people", value="", key="ai_brief_people_v1")
            evidence_priorities = st.text_area("evidence_priorities", value="", key="ai_brief_evidence_v1")
            notes = st.text_area("notes", value="", key="ai_brief_notes_v1")

        brief = NormalizedIntakeBrief(
            brand_name=brand_name,
            product_name=product_name,
            audience=audience,
            objective=objective,
            language=language,
            orientation=brief_orientation,
            duration_s=int(duration_s),
            tone=tone,
            style_keywords=parse_list_text(style_keywords),
            must_include=parse_list_text(must_include),
            avoid=parse_list_text(avoid),
            available_locations=parse_list_text(available_locations),
            available_assets=parse_list_text(available_assets),
            available_people=parse_list_text(available_people),
            evidence_priorities=parse_list_text(evidence_priorities),
            notes=notes,
        )

        run_a, run_b, run_c = st.columns(3)
        if run_a.button("Compile + Generate Draft", use_container_width=True, key="ai_run_generate_v1"):
            try:
                provider = _build_provider(provider_settings)
                normalized, constraints, bundle = compile_intake_brief(brief, root=root)
                result = run_script_pipeline(brief=normalized, provider=provider, bundle=bundle)
                st.session_state["ai_entry_last_result_v1"] = {
                    "mode": "compile_generate",
                    "provider": provider.provider_name,
                    "normalized_brief": asdict(result.normalized_brief),
                    "compiled_constraints": asdict(result.compiled_constraints),
                    "provider_response": asdict(result.provider_response),
                }
                st.success("Compile + generation completed.")
            except Exception as e:
                st.error(f"AI pipeline run failed: {e}")

        if run_b.button("Compile Only", use_container_width=True, key="ai_run_compile_only_v1"):
            try:
                normalized, constraints, _ = compile_intake_brief(brief, root=root)
                st.session_state["ai_entry_last_result_v1"] = {
                    "mode": "compile_only",
                    "provider": provider_settings.provider,
                    "normalized_brief": asdict(normalized),
                    "compiled_constraints": asdict(constraints),
                    "provider_response": None,
                }
                st.success("Compile-only completed.")
            except Exception as e:
                st.error(f"Compile-only failed: {e}")

        if run_c.button("Save Result", use_container_width=True, key="ai_run_save_v1"):
            last = st.session_state.get("ai_entry_last_result_v1")
            if not isinstance(last, dict):
                st.warning("No result to save yet.")
            else:
                path = save_ai_run_payload(root, last, brand_name=brief.brand_name)
                st.success(f"Saved: {path}")

        latest = st.session_state.get("ai_entry_last_result_v1")
        if isinstance(latest, dict):
            st.markdown("#### Normalized Brief")
            st.json(latest.get("normalized_brief", {}), expanded=False)
            st.markdown("#### Compiled Constraints")
            st.json(latest.get("compiled_constraints", {}), expanded=False)
            st.markdown("#### Provider Response")
            st.json(latest.get("provider_response", {}), expanded=False)
