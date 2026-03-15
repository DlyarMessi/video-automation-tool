from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from src.ai_local_settings import AIProviderSettings, save_ai_run_payload
from src.intake_models import NormalizedIntakeBrief
from src.intake_prefill import build_merged_brief_from_quick_input
from src.intake_validation import normalize_and_validate_brief
from src.script_pipeline import build_default_compiler_bundle, run_script_pipeline
from src.intake_compiler import compile_brief_to_constraints
from src.script_provider_config import load_deepseek_config, load_openrouter_config
from src.script_provider_manual import ManualScriptProvider
from src.script_provider_openrouter import OpenRouterScriptProvider
from src.script_provider_deepseek import DeepSeekScriptProvider


STRUCTURED_FIELDS = [
    "brand_name",
    "product_name",
    "audience",
    "objective",
    "language",
    "orientation",
    "duration_s",
    "tone",
    "style_keywords",
    "must_include",
    "avoid",
    "available_locations",
    "available_assets",
    "available_people",
    "evidence_priorities",
    "notes",
]

TRANSIENT_TEXT_KEYS = [
    "ai_adv_style_text_v2",
    "ai_adv_must_text_v2",
    "ai_adv_avoid_text_v2",
    "ai_adv_locations_text_v2",
    "ai_adv_assets_text_v2",
    "ai_adv_people_text_v2",
    "ai_adv_evidence_text_v2",
    "ai_adv_notes_text_v2",
]


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
    if settings.provider == "deepseek":
        cfg = load_deepseek_config(model_override=settings.deepseek_model)
        return DeepSeekScriptProvider(
            api_key=settings.deepseek_api_key or cfg.api_key,
            model=settings.deepseek_model or cfg.model,
            base_url=settings.deepseek_base_url or cfg.base_url,
        )
    return ManualScriptProvider()


def _field_key(name: str) -> str:
    return f"ai_adv_{name}_v2"


def _get_edited_fields(session_state) -> set[str]:
    value = session_state.get("ai_structured_edited_fields_v1", set())
    if isinstance(value, set):
        return value
    return set()


def _mark_edited(field_name: str) -> None:
    import streamlit as st

    edited = _get_edited_fields(st.session_state)
    edited.add(field_name)
    st.session_state["ai_structured_edited_fields_v1"] = edited


def _render_structured_fields(default_brief: NormalizedIntakeBrief) -> NormalizedIntakeBrief:
    import streamlit as st

    for field_name in STRUCTURED_FIELDS:
        key = _field_key(field_name)
        if key not in st.session_state:
            st.session_state[key] = getattr(default_brief, field_name)

    c1, c2 = st.columns(2)
    with c1:
        brand_name = st.text_input("brand_name", key=_field_key("brand_name"), on_change=_mark_edited, args=("brand_name",))
        product_name = st.text_input("product_name", key=_field_key("product_name"), on_change=_mark_edited, args=("product_name",))
        audience = st.text_input("audience", key=_field_key("audience"), on_change=_mark_edited, args=("audience",))
        objective = st.text_input("objective", key=_field_key("objective"), on_change=_mark_edited, args=("objective",))
        language = st.text_input("language", key=_field_key("language"), on_change=_mark_edited, args=("language",))
        brief_orientation = st.selectbox(
            "orientation",
            ["portrait", "landscape"],
            index=0 if st.session_state[_field_key("orientation")] == "portrait" else 1,
            key=_field_key("orientation"),
            on_change=_mark_edited,
            args=("orientation",),
        )
        duration_s = st.number_input(
            "duration_s",
            min_value=1,
            max_value=600,
            step=1,
            key=_field_key("duration_s"),
            on_change=_mark_edited,
            args=("duration_s",),
        )
        tone = st.text_input("tone", key=_field_key("tone"), on_change=_mark_edited, args=("tone",))

    with c2:
        style_keywords = st.text_area(
            "style_keywords",
            value=", ".join(st.session_state[_field_key("style_keywords")]),
            help="Comma-separated or one per line",
            key="ai_adv_style_text_v2",
            on_change=_mark_edited,
            args=("style_keywords",),
        )
        must_include = st.text_area("must_include", value=", ".join(st.session_state[_field_key("must_include")]), key="ai_adv_must_text_v2", on_change=_mark_edited, args=("must_include",))
        avoid = st.text_area("avoid", value=", ".join(st.session_state[_field_key("avoid")]), key="ai_adv_avoid_text_v2", on_change=_mark_edited, args=("avoid",))
        available_locations = st.text_area("available_locations", value=", ".join(st.session_state[_field_key("available_locations")]), key="ai_adv_locations_text_v2", on_change=_mark_edited, args=("available_locations",))
        available_assets = st.text_area("available_assets", value=", ".join(st.session_state[_field_key("available_assets")]), key="ai_adv_assets_text_v2", on_change=_mark_edited, args=("available_assets",))
        available_people = st.text_area("available_people", value=", ".join(st.session_state[_field_key("available_people")]), key="ai_adv_people_text_v2", on_change=_mark_edited, args=("available_people",))
        evidence_priorities = st.text_area("evidence_priorities", value=", ".join(st.session_state[_field_key("evidence_priorities")]), key="ai_adv_evidence_text_v2", on_change=_mark_edited, args=("evidence_priorities",))
        notes = st.text_area("notes", value=str(st.session_state[_field_key("notes")]), key="ai_adv_notes_text_v2", on_change=_mark_edited, args=("notes",))

    return NormalizedIntakeBrief(
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


def _write_structured_brief_to_state(brief: NormalizedIntakeBrief) -> None:
    import streamlit as st

    for field_name in STRUCTURED_FIELDS:
        st.session_state[_field_key(field_name)] = getattr(brief, field_name)

    st.session_state["ai_adv_style_text_v2"] = ", ".join(brief.style_keywords)
    st.session_state["ai_adv_must_text_v2"] = ", ".join(brief.must_include)
    st.session_state["ai_adv_avoid_text_v2"] = ", ".join(brief.avoid)
    st.session_state["ai_adv_locations_text_v2"] = ", ".join(brief.available_locations)
    st.session_state["ai_adv_assets_text_v2"] = ", ".join(brief.available_assets)
    st.session_state["ai_adv_people_text_v2"] = ", ".join(brief.available_people)
    st.session_state["ai_adv_evidence_text_v2"] = ", ".join(brief.evidence_priorities)
    st.session_state["ai_adv_notes_text_v2"] = brief.notes


def reset_structured_state_for_context(session_state, default_brief: NormalizedIntakeBrief) -> None:
    for field_name in STRUCTURED_FIELDS:
        session_state[_field_key(field_name)] = getattr(default_brief, field_name)

    session_state["ai_adv_style_text_v2"] = ", ".join(default_brief.style_keywords)
    session_state["ai_adv_must_text_v2"] = ", ".join(default_brief.must_include)
    session_state["ai_adv_avoid_text_v2"] = ", ".join(default_brief.avoid)
    session_state["ai_adv_locations_text_v2"] = ", ".join(default_brief.available_locations)
    session_state["ai_adv_assets_text_v2"] = ", ".join(default_brief.available_assets)
    session_state["ai_adv_people_text_v2"] = ", ".join(default_brief.available_people)
    session_state["ai_adv_evidence_text_v2"] = ", ".join(default_brief.evidence_priorities)
    session_state["ai_adv_notes_text_v2"] = default_brief.notes
    session_state["ai_structured_edited_fields_v1"] = set()
    session_state.pop("ai_entry_last_result_v1", None)


def _clear_edited_state() -> None:
    import streamlit as st

    st.session_state["ai_structured_edited_fields_v1"] = set()


def render_ai_script_entry_panel(
    *,
    root: Path,
    company: str,
    orientation: str,
    global_language: str,
    provider_settings: AIProviderSettings,
) -> None:
    import streamlit as st

    st.markdown("### Create with AI")
    st.caption("1) Describe your video · 2) Review what the system understood · 3) Generate draft")

    context_key = f"{company}::{orientation}"
    initial_language = str(st.session_state.get("ai_quick_lang_v1", "Use global default") or "Use global default")
    if initial_language == "Use global default":
        initial_language = str(global_language or "en-US")

    initial_orientation = str(st.session_state.get("ai_quick_orientation_v1", "Use global default") or "Use global default")
    if initial_orientation == "Use global default":
        initial_orientation = orientation

    context_default_brief = NormalizedIntakeBrief(
        brand_name=company,
        language=initial_language,
        orientation=initial_orientation,
        duration_s=int(st.session_state.get("ai_quick_duration_v1", 45) or 45),
        notes=str(st.session_state.get("ai_quick_brief_v1", "") or ""),
    )
    if st.session_state.get("ai_structured_context_v1") != context_key:
        reset_structured_state_for_context(st.session_state, context_default_brief)
        st.session_state["ai_structured_context_v1"] = context_key

    quick_brief = st.text_area(
        "Quick Brief",
        key="ai_quick_brief_v1",
        height=160,
        placeholder="Describe your video goal in natural language. Example:\nAudience: operations teams\nObjective: show reliability and quality proof\nMust include: factory line, testing closeups",
    )

    qa, qb, qc, qd, qe = st.columns([1, 1, 1, 1, 1])
    with qa:
        quick_language = st.selectbox("This draft only · Output Language", ["Use global default", "en-US", "fr-FR", "es-ES", "ar-SA", "ru-RU"], key="ai_quick_lang_v1")
    with qb:
        quick_orientation = st.selectbox("This draft only · Format", ["Use global default", "portrait", "landscape"], key="ai_quick_orientation_v1")
    with qc:
        quick_duration = st.selectbox("Approx. Duration", [30, 45, 60, 90], index=1, key="ai_quick_duration_v1")
    with qd:
        quick_emphasis = st.selectbox("Emphasis", ["Balanced", "Proof & evidence", "Premium look", "Clear education", "Speed & efficiency"], key="ai_quick_emphasis_v1")
    with qe:
        quick_footage = st.selectbox("Existing Footage", ["Yes", "Partially", "No"], key="ai_quick_has_footage_v1")

    effective_language = str(st.session_state.get("ai_quick_lang_v1") or "Use global default")
    if effective_language == "Use global default":
        effective_language = str(global_language or "en-US")

    effective_orientation = str(st.session_state.get("ai_quick_orientation_v1") or "Use global default")
    if effective_orientation == "Use global default":
        effective_orientation = orientation

    default_brief = NormalizedIntakeBrief(
        brand_name=company,
        language=effective_language,
        orientation=effective_orientation,
        duration_s=int(quick_duration),
        notes=quick_brief,
    )

    with st.expander("Check what the system understood", expanded=False):
        st.caption("Review extracted brief details before generating. Your manual edits are protected.")
        brief = _render_structured_fields(default_brief)

    action_a, action_b, action_c = st.columns(3)
    if action_a.button("Refresh extracted brief", key="ai_quick_prefill_v1", use_container_width=True):
        merged = build_merged_brief_from_quick_input(
            current=brief,
            edited_fields=_get_edited_fields(st.session_state),
            quick_brief=quick_brief,
            company=company,
            output_language=effective_language,
            orientation=effective_orientation,
            duration_s=int(quick_duration),
            emphasis=quick_emphasis,
            has_existing_footage=quick_footage,
        )
        _write_structured_brief_to_state(merged)
        st.success("Extracted brief refreshed. Review details before generating your draft.")

    if action_b.button("Rebuild from brief", key="ai_quick_rebuild_v1", use_container_width=True):
        _clear_edited_state()
        rebuilt = build_merged_brief_from_quick_input(
            current=brief,
            edited_fields=set(),
            quick_brief=quick_brief,
            company=company,
            output_language=effective_language,
            orientation=effective_orientation,
            duration_s=int(quick_duration),
            emphasis=quick_emphasis,
            has_existing_footage=quick_footage,
        )
        _write_structured_brief_to_state(rebuilt)
        st.success("Extracted brief rebuilt from your quick brief.")

    if action_c.button("Reset extracted brief", key="ai_quick_reset_structured_v1", use_container_width=True):
        _clear_edited_state()
        reset_brief = NormalizedIntakeBrief(
            brand_name=company,
            language=effective_language,
            orientation=effective_orientation,
            duration_s=int(quick_duration),
            notes=quick_brief,
        )
        _write_structured_brief_to_state(reset_brief)
        st.success("Extracted brief reset to baseline defaults.")

    if st.button("✨ Generate Draft", use_container_width=True, key="ai_run_generate_v2"):
        try:
            effective_brief = build_merged_brief_from_quick_input(
                current=brief,
                edited_fields=_get_edited_fields(st.session_state),
                quick_brief=quick_brief,
                company=company,
                output_language=effective_language,
                orientation=effective_orientation,
                duration_s=int(quick_duration),
                emphasis=quick_emphasis,
                has_existing_footage=quick_footage,
            )
            _write_structured_brief_to_state(effective_brief)
            provider = _build_provider(provider_settings)
            _, _, bundle = compile_intake_brief(effective_brief, root=root)
            result = run_script_pipeline(brief=normalize_and_validate_brief(effective_brief), provider=provider, bundle=bundle)
            st.session_state["ai_entry_last_result_v1"] = {
                "mode": "compile_generate",
                "provider": provider.provider_name,
                "normalized_brief": asdict(result.normalized_brief),
                "compiled_constraints": asdict(result.compiled_constraints),
                "provider_response": asdict(result.provider_response),
            }
            st.success("Draft generated successfully.")
        except Exception as e:
            st.error(f"AI pipeline run failed: {e}")

    with st.expander("Secondary actions", expanded=False):
        if st.button("Rebuild constraints only", use_container_width=True, key="ai_run_compile_only_v2"):
            try:
                effective_brief = build_merged_brief_from_quick_input(
                    current=brief,
                    edited_fields=_get_edited_fields(st.session_state),
                    quick_brief=quick_brief,
                    company=company,
                    output_language=effective_language,
                    orientation=effective_orientation,
                    duration_s=int(quick_duration),
                    emphasis=quick_emphasis,
                    has_existing_footage=quick_footage,
                )
                _write_structured_brief_to_state(effective_brief)
                normalized, constraints, _ = compile_intake_brief(effective_brief, root=root)
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

        if st.button("Save result", use_container_width=True, key="ai_run_save_v2"):
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
