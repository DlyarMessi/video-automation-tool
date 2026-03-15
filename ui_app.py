#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import streamlit as st
import yaml

from src.ui_hardening import (
    load_registry_entries as ui_load_registry_entries,
    hydrate_slot_from_registry as ui_hydrate_slot_from_registry,
    attach_pool_row_semantics as ui_attach_pool_row_semantics,
    build_pool_card_view,
    get_brand_validation_status as hardening_get_brand_validation_status,
    build_brand_status_summary,
)
from src.ui_brand_ops import (
    clone_brand_starter_into_project as brandops_clone_brand_starter_into_project,
    save_brand_logo as brandops_save_brand_logo,
    save_brand_pool_plan as brandops_save_brand_pool_plan,
    list_brand_pool_plans as brandops_list_brand_pool_plans,
    load_pool_plan_from_path as brandops_load_pool_plan_from_path,
    pop_flash as ui_pop_flash,
    set_flash as ui_set_flash,
    ensure_valid_choice as ui_ensure_valid_choice,
)
from src.ui_pool_fill_model import prepare_pool_fill_runtime
from src.ui_state import ensure_ui_session_defaults
from src.ui_pool_fill_controls import (
    build_pool_plan_label_map,
    get_selected_pool_plan_data,
)
from src.ui_workspace import (
    build_workspace_controls_state,
    compute_storage_state,
)
from src.brand_workspace import (
    provision_brand_workspace,
    scan_brand_workspace,
    delete_brand_workspace,
)
from src.ui_provider_settings import render_ai_provider_settings
from src.ui_ai_entry import render_ai_script_entry_panel

from src.render_profile import get_default_fps, get_filter_preset
from src.language_checks import build_language_check
from src.material_index import load_asset_index, upsert_asset_record, update_asset_record_fields
from src.workflow import (
    now_tag,
    safe_slug,
    load_yaml_text,
    beats_from_creative,
    list_video_files,
    safe_write_file,
    validate_creative_schema,
    render_html_task_table,
    infer_category_from_beat,
    infer_shots_from_beat,
    infer_scene_from_beat,
    suggested_movement,
    default_seconds_for_shot,
    build_factory_filename,
    next_index_for,
    patch_compiled_yaml,
    summarize_factory_coverage,
    ensure_company_storage,
    get_storage_dirs,
    classify_orientation,
)

# =========================================================
# Paths
# =========================================================
ROOT = Path(__file__).resolve().parent
SRC_MAIN = ROOT / "src" / "main.py"

CREATIVE_ROOT = ROOT / "creative_scripts"
INPUT_ROOT_DEFAULT = ROOT / "input_videos"
OUTPUT_ROOT_DEFAULT = ROOT / "output_videos"

TTS_PROFILE_DIR = ROOT / "data" / "tts_profiles"
ELEVEN_PROFILE_PATH = TTS_PROFILE_DIR / "elevenlabs.json"
ELEVEN_SECRETS_PATH = TTS_PROFILE_DIR / "elevenlabs_secrets.json"

POOL_PLAN_DIR = ROOT / "data" / "pool_plans"
CANONICAL_REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"
BRANDS_DIR = ROOT / "data" / "brands"
DOCS_DIR = ROOT / "docs"

VIDEO_EXTS = ["mp4", "mov", "mkv", "m4v"]
VIDEO_SUFFIXES = ["." + e for e in VIDEO_EXTS]

# =========================================================
# UI
# =========================================================
st.set_page_config(page_title="Video Automation Tool", layout="wide")
st.markdown(
    """
    <style>
      .divider { margin: 1rem 0 0.9rem 0; border-bottom: 1px solid rgba(0,0,0,0.08); }
      .muted { color: rgba(0,0,0,0.55); }
      .tiny { color: rgba(0,0,0,0.55); font-size: 0.9rem; }
      code { white-space: pre-wrap !important; }
      .top-help { padding-top: 1.7rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Helpers
# =========================================================

def recommended_duration_for_slot(coverage: str, move: str) -> str:
    coverage = str(coverage or "").strip().lower()
    move = str(move or "").strip().lower()

    if coverage == "wide":
        return "5–7s"
    if coverage == "medium":
        return "5–7s"
    if coverage == "detail":
        return "4–6s"
    if coverage == "hero":
        return "6–8s"
    return "5–7s"


def movement_guidance(move: str) -> str:
    move = str(move or "").strip().lower()
    mapping = {
        "static": "stable",
        "slide": "slow side move",
        "pushin": "slow push-in",
        "follow": "smooth follow",
        "orbit": "slow orbit",
        "reveal": "controlled reveal",
    }
    return mapping.get(move, "controlled move")


def composition_guidance(scene: str, content: str, coverage: str) -> str:
    coverage = str(coverage or "").strip().lower()

    if coverage == "wide":
        return "show full space clearly"
    if coverage == "medium":
        return "one main subject readable"
    if coverage == "detail":
        return "one clear detail fills frame"
    if coverage == "hero":
        return "premium brand-style framing"
    return "clean readable framing"


def slot_display_name(scene: str, content: str, coverage: str, move: str) -> str:
    return f"{scene} / {content} / {coverage} / {move}"


def priority_badge(priority: str) -> str:
    priority = str(priority or "").strip().lower()
    if priority == "high":
        return "🔴 High"
    if priority == "medium":
        return "🟡 Medium"
    return "⚪️ Low"


def priority_score(priority: str) -> int:
    p = str(priority or "").strip().lower()
    if p == "high":
        return 2
    if p == "medium":
        return 1
    return 0


def build_pool_slot_rows(slots, factory_files):
    """Build normalized Pool Fill row dictionaries.

This function is the current render-facing integration point between:
- pool plan slots
- factory footage counting
- semantic enrichment
- registry hydration
- Pool Fill UI card rendering
"""
    rows = []

    for slot in slots:
        scene_name = str(slot.get("scene", "")).strip()
        content_name = str(slot.get("content", "")).strip()
        coverage_name = str(slot.get("coverage", "")).strip()
        move_name = str(slot.get("move", "")).strip()
        target = int(slot.get("target", 0) or 0)
        priority = str(slot.get("priority", "medium") or "medium")
        defaults = slot.get("defaults", {}) if isinstance(slot.get("defaults"), dict) else {}

        existing = count_pool_matches(factory_files, scene_name, content_name, coverage_name, move_name)
        missing = max(0, target - existing)

        rows.append(
            {
                "scene": scene_name,
                "content": content_name,
                "coverage": coverage_name,
                "move": move_name,
                "target": target,
                "priority": priority,
                "priority_score": priority_score(priority),
                "existing": existing,
                "missing": missing,
                "defaults": defaults,
                "slot_label": slot_display_name(scene_name, content_name, coverage_name, move_name),
                "duration_label": recommended_duration_for_slot(coverage_name, move_name),
                "move_label": movement_guidance(move_name),
                "framing_label": composition_guidance(scene_name, content_name, coverage_name),
            }
        )

    return rows


def summarize_pool_slot_rows(slot_rows):
    total_target = sum(int(r.get("target", 0) or 0) for r in slot_rows)
    total_existing = sum(int(r.get("existing", 0) or 0) for r in slot_rows)
    total_missing = sum(int(r.get("missing", 0) or 0) for r in slot_rows)

    missing_rows = [r for r in slot_rows if int(r.get("missing", 0)) > 0]

    if missing_rows:
        urgent = sorted(
            missing_rows,
            key=lambda r: (
                -int(r.get("priority_score", 0)),
                -int(r.get("missing", 0)),
                str(r.get("scene", "")),
                str(r.get("content", "")),
                str(r.get("coverage", "")),
            ),
        )[0]

        by_scene = {}
        for r in missing_rows:
            scene = str(r.get("scene", "") or "").strip() or "unknown"
            by_scene[scene] = by_scene.get(scene, 0) + int(r.get("missing", 0))

        focus_scene = sorted(by_scene.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        urgent_label = str(urgent.get("slot_label", "") or "")
    else:
        focus_scene = "All filled"
        urgent_label = "All slots complete"

    return {
        "total_target": total_target,
        "total_existing": total_existing,
        "total_missing": total_missing,
        "focus_scene": focus_scene,
        "urgent_label": urgent_label,
    }


def sort_pool_slot_rows(slot_rows):
    return sorted(
        slot_rows,
        key=lambda r: (
            0 if int(r.get("missing", 0)) > 0 else 1,
            -int(r.get("priority_score", 0)),
            -int(r.get("missing", 0)),
            str(r.get("scene", "")),
            str(r.get("content", "")),
            str(r.get("coverage", "")),
            str(r.get("move", "")),
        ),
    )


def save_pool_uploads(
    uploads,
    factory_dir: Path,
    ext_choice_pool: str,
    scene_name: str,
    content_name: str,
    coverage_name: str,
    move_name: str,
    hero_safe_default: bool,
    intro_safe_default: bool,
    outro_safe_default: bool,
    continuity_group_default: str,
    energy_default: str,
    quality_default: str,
    notes_default: str,
):
    cur = next_index_for(factory_dir, scene_name, content_name, coverage_name, move_name, ext_choice_pool)

    for uf in uploads:
        ext = Path(uf.name).suffix.lower() or ext_choice_pool
        fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, ext)
        saved_path = safe_write_file(factory_dir / fname, uf.getbuffer().tobytes())
        upsert_asset_record(factory_dir / "asset_index.json", saved_path)
        update_asset_record_fields(
            factory_dir / "asset_index.json",
            saved_path.name,
            {
                "hero_safe": hero_safe_default,
                "intro_safe": intro_safe_default,
                "outro_safe": outro_safe_default,
                "continuity_group": continuity_group_default.strip(),
                "energy": energy_default,
                "quality_status": quality_default,
                "notes": notes_default.strip(),
            },
        )
        cur += 1


def load_canonical_registry_entries() -> dict[str, dict]:
    registry_path = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"
    if not registry_path.exists():
        return {}
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        entries = data.get("entries", {}) if isinstance(data.get("entries"), dict) else {}
        return entries if isinstance(entries, dict) else {}
    except Exception:
        return {}


def merge_pool_semantic_fields(slot_rows: list[dict], slots: list[dict]) -> list[dict]:
    slot_semantic_map: dict[tuple[str, str, str, str], dict] = {}

    for slot in slots:
        if not isinstance(slot, dict):
            continue

        key = (
            str(slot.get("scene", "") or "").strip().lower(),
            str(slot.get("content", "") or "").strip().lower(),
            str(slot.get("coverage", "") or "").strip().lower(),
            str(slot.get("move", "") or "").strip().lower(),
        )

        slot_semantic_map[key] = {
            "registry_key": str(slot.get("registry_key", "") or "").strip(),
            "human_label": str(slot.get("human_label", "") or "").strip(),
            "shoot_brief": str(slot.get("shoot_brief", "") or "").strip(),
            "purpose": str(slot.get("purpose", "") or "").strip(),
            "success_criteria": slot.get("success_criteria") if isinstance(slot.get("success_criteria"), list) else [],
            "fallback": slot.get("fallback") if isinstance(slot.get("fallback"), list) else [],
        }

    registry_entries = load_canonical_registry_entries()
    merged_rows: list[dict] = []

    for row in slot_rows:
        if not isinstance(row, dict):
            merged_rows.append(row)
            continue

        merged = dict(row)
        key = (
            str(merged.get("scene", "") or "").strip().lower(),
            str(merged.get("content", "") or "").strip().lower(),
            str(merged.get("coverage", "") or "").strip().lower(),
            str(merged.get("move", "") or "").strip().lower(),
        )

        slot_semantic = slot_semantic_map.get(key, {})
        computed_registry_key = ".".join(key)
        registry_key = str(
            slot_semantic.get("registry_key", "")
            or merged.get("registry_key", "")
            or computed_registry_key
        ).strip()

        if registry_key:
            merged["registry_key"] = registry_key

        registry_entry = registry_entries.get(registry_key, {}) if isinstance(registry_entries.get(registry_key, {}), dict) else {}
        registry_public = registry_entry.get("public", {}) if isinstance(registry_entry.get("public"), dict) else {}
        registry_story = registry_entry.get("story", {}) if isinstance(registry_entry.get("story"), dict) else {}

        canonical_label = str(merged.get("slot_label", "") or "").strip()
        registry_human_label = str(registry_public.get("human_label", "") or "").strip()
        slot_human_label = str(slot_semantic.get("human_label", "") or "").strip()
        preferred_human_label = registry_human_label or slot_human_label

        if preferred_human_label:
            merged["canonical_slot_label"] = canonical_label
            merged["slot_label"] = preferred_human_label
            merged["human_label"] = preferred_human_label

        registry_shoot_brief = str(registry_public.get("shoot_brief", "") or "").strip()
        slot_shoot_brief = str(slot_semantic.get("shoot_brief", "") or "").strip()
        preferred_shoot_brief = registry_shoot_brief or slot_shoot_brief
        if preferred_shoot_brief:
            merged["shoot_brief"] = preferred_shoot_brief

        registry_purpose = str(registry_story.get("purpose_text", "") or "").strip()
        slot_purpose = str(slot_semantic.get("purpose", "") or "").strip()
        preferred_purpose = registry_purpose or slot_purpose
        if preferred_purpose:
            merged["purpose"] = preferred_purpose

        registry_success = registry_public.get("success_criteria") if isinstance(registry_public.get("success_criteria"), list) else []
        slot_success = slot_semantic.get("success_criteria") if isinstance(slot_semantic.get("success_criteria"), list) else []
        if registry_success or slot_success:
            merged["success_criteria"] = registry_success or slot_success

        registry_fallback = registry_public.get("fallback") if isinstance(registry_public.get("fallback"), list) else []
        slot_fallback = slot_semantic.get("fallback") if isinstance(slot_semantic.get("fallback"), list) else []
        if registry_fallback or slot_fallback:
            merged["fallback"] = registry_fallback or slot_fallback

        merged_rows.append(merged)

    return merged_rows




def render_pool_active_slot_card(row, pool_topic: str, i: int, factory_dir: Path, ext_choice_pool: str):
    scene_name = str(row.get("scene", "")).strip()
    content_name = str(row.get("content", "")).strip()
    coverage_name = str(row.get("coverage", "")).strip()
    move_name = str(row.get("move", "")).strip()
    target = int(row.get("target", 0) or 0)
    priority = str(row.get("priority", "medium") or "medium")
    existing = int(row.get("existing", 0) or 0)
    missing = int(row.get("missing", 0) or 0)
    defaults = row.get("defaults", {}) if isinstance(row.get("defaults"), dict) else {}

    default_energy = str(defaults.get("energy", "medium") or "medium")
    default_quality = str(defaults.get("quality_status", "approved") or "approved")
    default_group = str(defaults.get("continuity_group", "") or "")
    default_intro = bool(defaults.get("intro_safe", False))
    default_hero = bool(defaults.get("hero_safe", False))
    default_outro = bool(defaults.get("outro_safe", False))

    display_label = str(row.get("display_label", "") or "").strip() or str(row.get("slot_label", "Slot")).strip()
    slot_label_text = str(row.get("slot_label_text", "") or row.get("slot_label", "") or "").strip()
    canonical_tuple_text = str(row.get("canonical_tuple_text", "") or "").strip()
    registry_key_text = str(row.get("registry_key_text", "") or "").strip()
    shoot_brief_text = str(row.get("shoot_brief_text", "") or "").strip()

    with st.container(border=True):
        st.markdown(f"**{display_label}** {priority_badge(priority)}")
        if slot_label_text and display_label != slot_label_text:
            st.caption(f"`{slot_label_text}`")
        if canonical_tuple_text:
            st.caption(canonical_tuple_text)
        if registry_key_text:
            st.caption(f"registry_key: `{registry_key_text}`")
        st.markdown(f"🎬 `{move_name}` · ⏱️ `{row['duration_label']}` · ⚠️ **missing {missing}**")
        if shoot_brief_text:
            st.caption(shoot_brief_text)
        st.caption(f"💡 {row['framing_label']} · {row['move_label']}")

        progress_col, status_col = st.columns([3, 2])
        with progress_col:
            ratio = (existing / target) if target else 0
            st.progress(ratio)
        with status_col:
            st.markdown(
                f"<div style='font-size:0.92rem; text-align:right;'>"
                f"{existing}/{target} · "
                f"<span style='color:#FF4B4B; font-weight:600;'>need {missing}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        uploads = st.file_uploader(
            "Upload clips for this slot",
            type=VIDEO_EXTS,
            accept_multiple_files=True,
            key=f"pool_fill_v3_upload_{pool_topic}_{i}",
            label_visibility="collapsed",
        )

        with st.expander("Clip tags", expanded=False):
            meta1, meta2 = st.columns([1, 1])
            with meta1:
                energy_default = st.selectbox(
                    "energy",
                    ["low", "medium", "high"],
                    index=["low", "medium", "high"].index(default_energy) if default_energy in ["low", "medium", "high"] else 1,
                    key=f"pool_fill_v3_energy_{pool_topic}_{i}",
                )
                quality_default = st.selectbox(
                    "quality_status",
                    ["approved", "review", "reject"],
                    index=["approved", "review", "reject"].index(default_quality) if default_quality in ["approved", "review", "reject"] else 0,
                    key=f"pool_fill_v3_quality_{pool_topic}_{i}",
                )
            with meta2:
                continuity_group_default = st.text_input(
                    "continuity_group",
                    value=default_group,
                    key=f"pool_fill_v3_group_{pool_topic}_{i}",
                )
                notes_default = st.text_input(
                    "notes",
                    value="",
                    key=f"pool_fill_v3_notes_{pool_topic}_{i}",
                )

            t1, t2, t3 = st.columns(3)
            with t1:
                intro_safe_default = st.checkbox("intro_safe", value=default_intro, key=f"pool_fill_v3_intro_{pool_topic}_{i}")
            with t2:
                hero_safe_default = st.checkbox("hero_safe", value=default_hero, key=f"pool_fill_v3_hero_{pool_topic}_{i}")
            with t3:
                outro_safe_default = st.checkbox("outro_safe", value=default_outro, key=f"pool_fill_v3_outro_{pool_topic}_{i}")

        if st.button("Save to Pool", key=f"pool_fill_v3_save_{pool_topic}_{i}", use_container_width=True):
            if not uploads:
                st.warning("Please upload at least one clip.")
            else:
                save_pool_uploads(
                    uploads=uploads,
                    factory_dir=factory_dir,
                    ext_choice_pool=ext_choice_pool,
                    scene_name=scene_name,
                    content_name=content_name,
                    coverage_name=coverage_name,
                    move_name=move_name,
                    hero_safe_default=hero_safe_default,
                    intro_safe_default=intro_safe_default,
                    outro_safe_default=outro_safe_default,
                    continuity_group_default=continuity_group_default,
                    energy_default=energy_default,
                    quality_default=quality_default,
                    notes_default=notes_default,
                )
                st.success("Saved to pool.")
                st.rerun()


def render_pool_completed_slot_card(row, pool_topic: str, i: int, factory_dir: Path, ext_choice_pool: str):
    scene_name = str(row.get("scene", "")).strip()
    content_name = str(row.get("content", "")).strip()
    coverage_name = str(row.get("coverage", "")).strip()
    move_name = str(row.get("move", "")).strip()
    existing = int(row.get("existing", 0) or 0)
    defaults = row.get("defaults", {}) if isinstance(row.get("defaults"), dict) else {}

    default_energy = str(defaults.get("energy", "medium") or "medium")
    default_quality = str(defaults.get("quality_status", "approved") or "approved")
    default_group = str(defaults.get("continuity_group", "") or "")
    default_intro = bool(defaults.get("intro_safe", False))
    default_hero = bool(defaults.get("hero_safe", False))
    default_outro = bool(defaults.get("outro_safe", False))

    display_label = str(row.get("display_label", "") or "").strip() or str(row.get("slot_label", "Slot")).strip()
    slot_label_text = str(row.get("slot_label_text", "") or row.get("slot_label", "") or "").strip()
    canonical_tuple_text = str(row.get("canonical_tuple_text", "") or "").strip()
    registry_key_text = str(row.get("registry_key_text", "") or "").strip()
    shoot_brief_text = str(row.get("shoot_brief_text", "") or "").strip()

    with st.expander(f"✅ {display_label} · ready {existing}", expanded=False):
        if slot_label_text and display_label != slot_label_text:
            st.caption(f"`{slot_label_text}`")
        if canonical_tuple_text:
            st.caption(canonical_tuple_text)
        if registry_key_text:
            st.caption(f"registry_key: `{registry_key_text}`")
        if shoot_brief_text:
            st.caption(shoot_brief_text)
        st.caption(f"Current clips: {existing} · upload here only if you want replacements or alternates.")

        uploads = st.file_uploader(
            "Upload clips for this slot",
            type=VIDEO_EXTS,
            accept_multiple_files=True,
            key=f"pool_fill_v3_done_upload_{pool_topic}_{i}",
            label_visibility="collapsed",
        )

        meta1, meta2 = st.columns([1, 1])
        with meta1:
            energy_default = st.selectbox(
                "energy",
                ["low", "medium", "high"],
                index=["low", "medium", "high"].index(default_energy) if default_energy in ["low", "medium", "high"] else 1,
                key=f"pool_fill_v3_done_energy_{pool_topic}_{i}",
            )
            quality_default = st.selectbox(
                "quality_status",
                ["approved", "review", "reject"],
                index=["approved", "review", "reject"].index(default_quality) if default_quality in ["approved", "review", "reject"] else 0,
                key=f"pool_fill_v3_done_quality_{pool_topic}_{i}",
            )
        with meta2:
            continuity_group_default = st.text_input(
                "continuity_group",
                value=default_group,
                key=f"pool_fill_v3_done_group_{pool_topic}_{i}",
            )
            notes_default = st.text_input(
                "notes",
                value="",
                key=f"pool_fill_v3_done_notes_{pool_topic}_{i}",
            )

        t1, t2, t3 = st.columns(3)
        with t1:
            intro_safe_default = st.checkbox("intro_safe", value=default_intro, key=f"pool_fill_v3_done_intro_{pool_topic}_{i}")
        with t2:
            hero_safe_default = st.checkbox("hero_safe", value=default_hero, key=f"pool_fill_v3_done_hero_{pool_topic}_{i}")
        with t3:
            outro_safe_default = st.checkbox("outro_safe", value=default_outro, key=f"pool_fill_v3_done_outro_{pool_topic}_{i}")

        if st.button("Save Alternate to Pool", key=f"pool_fill_v3_done_save_{pool_topic}_{i}", use_container_width=True):
            if not uploads:
                st.warning("Please upload at least one clip.")
            else:
                save_pool_uploads(
                    uploads=uploads,
                    factory_dir=factory_dir,
                    ext_choice_pool=ext_choice_pool,
                    scene_name=scene_name,
                    content_name=content_name,
                    coverage_name=coverage_name,
                    move_name=move_name,
                    hero_safe_default=hero_safe_default,
                    intro_safe_default=intro_safe_default,
                    outro_safe_default=outro_safe_default,
                    continuity_group_default=continuity_group_default,
                    energy_default=energy_default,
                    quality_default=quality_default,
                    notes_default=notes_default,
                )
                st.success("Saved to pool.")
                st.rerun()

def render_pool_fill_downloads():
    guide_html = DOCS_DIR / "pool_fill_shooting_guide.html"

    with st.container():
        c1, c2 = st.columns([1, 5])

        with c1:
            if guide_html.exists():
                st.download_button(
                    "Get Guide",
                    data=guide_html.read_text(encoding="utf-8"),
                    file_name=guide_html.name,
                    mime="text/html",
                    use_container_width=True,
                    key="download_pool_guide_html",
                )
            else:
                st.caption("Guide missing")

        with c2:
            st.caption("Download the phone-friendly shooting guide for quick reference.")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_eleven_profile() -> dict:
    return _load_json(ELEVEN_PROFILE_PATH)

def save_eleven_profile(profile: dict) -> None:
    _save_json(ELEVEN_PROFILE_PATH, profile)

def load_eleven_api_key() -> str:
    d = _load_json(ELEVEN_SECRETS_PATH)
    return str(d.get("api_key", "") or "")

def save_eleven_api_key(key: str) -> None:
    _save_json(ELEVEN_SECRETS_PATH, {"api_key": key})

def ensure_default_eleven_profile() -> dict:
    profile = load_eleven_profile()
    profile.setdefault("defaults", {})
    profile.setdefault("languages", {})

    defaults = profile["defaults"] if isinstance(profile["defaults"], dict) else {}
    defaults.setdefault("model_id", "eleven_multilingual_v2")
    defaults.setdefault("output_format", "mp3_44100_128")
    defaults.setdefault("voice_settings", {"stability": 0.55, "similarity_boost": 0.75})
    profile["defaults"] = defaults

    langs = profile["languages"] if isinstance(profile["languages"], dict) else {}
    preset_ids = {
        "en": "21m00Tcm4TlvDq8ikWAM",
        "fr": "onwK4e9ZLuTAKqWW03F9",
        "es": "ErXwobaYiN019PkySvjV",
        "ru": "nPczCjzI2devNBz1zQrb",
        "ar": "N2lVS1w4EtoT3dr4eOWO",
    }
    for k, vid in preset_ids.items():
        entry = langs.get(k)
        if not isinstance(entry, dict):
            entry = {}
        if not str(entry.get("voice_id", "") or "").strip():
            entry["voice_id"] = vid
        langs[k] = entry

    profile["languages"] = langs
    save_eleven_profile(profile)
    return profile

def run_cmd_silent(cmd: list[str], env: dict) -> tuple[int, str]:
    p = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    lines: list[str] = []
    if p.stdout:
        for line in p.stdout:
            lines.append(line.rstrip())
            if len(lines) > 800:
                lines = lines[-800:]
    rc = p.wait() or 0
    return rc, "\n".join(lines)

def ensure_run_layout(run_dir: Path) -> dict[str, Path]:
    internal_dir = run_dir / "_internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    return {"run_dir": run_dir, "internal_dir": internal_dir}


def list_brand_pool_plans(company: str) -> list[Path]:
    return brandops_list_brand_pool_plans(ROOT, company, safe_slug, POOL_PLAN_DIR)


def load_pool_plan_from_path(path: Path) -> dict:
    return brandops_load_pool_plan_from_path(path)

def load_canonical_registry_map():
    if not CANONICAL_REGISTRY_PATH.exists():
        return {}

    try:
        data = yaml.safe_load(CANONICAL_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    entries = data.get("entries", data)
    if not isinstance(entries, dict):
        return {}

    out = {}
    for k, v in entries.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_") or k in {"version", "meta", "status", "about", "principles", "governed_fields", "notes", "entries"}:
            continue
        if isinstance(v, dict):
            out[k] = v
    return out


def _clone_registry_value(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def hydrate_slot_from_registry(slot: dict) -> dict:
    hydrated = dict(slot) if isinstance(slot, dict) else {}
    registry_key = str(hydrated.get("registry_key", "") or "").strip()
    if not registry_key:
        return hydrated

    registry = load_canonical_registry_map()
    entry = registry.get(registry_key, {})
    if not isinstance(entry, dict):
        return hydrated

    for key in ["human_label", "shoot_brief", "success_criteria", "fallback", "purpose"]:
        cur = hydrated.get(key)
        if (cur is None) or (isinstance(cur, str) and not cur.strip()) or (isinstance(cur, list) and not cur):
            if key in entry:
                hydrated[key] = _clone_registry_value(entry.get(key))

    entry_defaults = entry.get("defaults", {}) if isinstance(entry.get("defaults", {}), dict) else {}
    slot_defaults = hydrated.get("defaults", {}) if isinstance(hydrated.get("defaults", {}), dict) else {}
    merged_defaults = dict(slot_defaults)

    for key in ["energy", "quality_status", "continuity_group", "intro_safe", "hero_safe", "outro_safe"]:
        if key not in merged_defaults and key in entry_defaults:
            merged_defaults[key] = _clone_registry_value(entry_defaults.get(key))

    if merged_defaults:
        hydrated["defaults"] = merged_defaults

    return hydrated


def attach_pool_row_semantics(slot_rows: list[dict], hydrated_slots: list[dict]) -> list[dict]:
    by_registry = {}
    by_tuple = {}

    for slot in hydrated_slots:
        if not isinstance(slot, dict):
            continue
        rk = str(slot.get("registry_key", "") or "").strip()
        key_tuple = (
            str(slot.get("scene", "") or "").strip(),
            str(slot.get("content", "") or "").strip(),
            str(slot.get("coverage", "") or "").strip(),
            str(slot.get("move", "") or "").strip(),
        )
        if rk:
            by_registry[rk] = slot
        by_tuple[key_tuple] = slot

    out = []
    for row in slot_rows:
        if not isinstance(row, dict):
            out.append(row)
            continue

        merged = dict(row)
        row_rk = str(row.get("registry_key", "") or "").strip()
        key_tuple = (
            str(row.get("scene", "") or "").strip(),
            str(row.get("content", "") or "").strip(),
            str(row.get("coverage", "") or "").strip(),
            str(row.get("move", "") or "").strip(),
        )

        source = None
        if row_rk and row_rk in by_registry:
            source = by_registry[row_rk]
        elif key_tuple in by_tuple:
            source = by_tuple[key_tuple]

        if isinstance(source, dict):
            for key in ["registry_key", "human_label", "shoot_brief", "success_criteria", "fallback", "purpose"]:
                cur = merged.get(key)
                if key in source and ((cur is None) or (isinstance(cur, str) and not cur.strip()) or (isinstance(cur, list) and not cur)):
                    merged[key] = _clone_registry_value(source.get(key))

            source_defaults = source.get("defaults", {}) if isinstance(source.get("defaults", {}), dict) else {}
            row_defaults = merged.get("defaults", {}) if isinstance(merged.get("defaults", {}), dict) else {}
            for dkey, dval in source_defaults.items():
                if dkey not in row_defaults:
                    row_defaults[dkey] = _clone_registry_value(dval)
            if row_defaults:
                merged["defaults"] = row_defaults

        out.append(merged)

    return out


def count_pool_matches(factory_files: list[Path], scene: str, content: str, coverage: str, move: str) -> int:
    scene = safe_slug(scene).lower()
    content = safe_slug(content).lower()
    coverage = safe_slug(coverage).lower()
    move = safe_slug(move).lower()
    prefix = f"{scene}_{content}_{coverage}_{move}_"
    return len(
        [
            p for p in factory_files
            if p.is_file()
            and p.suffix.lower() in VIDEO_SUFFIXES
            and p.name.lower().startswith(prefix.lower())
        ]
    )

def list_brand_catalog_names() -> list[str]:
    brands_dir = ROOT / "data" / "brands"
    if not brands_dir.exists():
        return []

    names: list[str] = []

    for brand_dir in brands_dir.iterdir():
        if not brand_dir.is_dir():
            continue
        if brand_dir.name.startswith(".") or brand_dir.name == "_starter":
            continue

        default_plan = brand_dir / "pool_plans" / "default.yaml"
        display_name = ""
        if default_plan.exists():
            try:
                data = yaml.safe_load(default_plan.read_text(encoding="utf-8")) or {}
                if isinstance(data, dict):
                    display_name = str(data.get("brand", "") or "").strip()
            except Exception:
                pass

        names.append(display_name or brand_dir.name)

    return sorted([x for x in names if str(x).strip()], key=lambda x: str(x).lower())



def clone_brand_starter_into_project(brand_name: str, brand_slug: str = "") -> tuple[bool, str]:
    return brandops_clone_brand_starter_into_project(ROOT, brand_name, safe_slug, brand_slug)

def get_brand_validation_status(company: str) -> dict:
    return hardening_get_brand_validation_status(ROOT, company, safe_slug)


def save_brand_logo(company: str, uploaded_logo) -> tuple[bool, str]:
    return brandops_save_brand_logo(ROOT, company, safe_slug, uploaded_logo)


def save_brand_pool_plan(company: str, uploaded_plan, plan_name: str = "") -> tuple[bool, str, str]:
    return brandops_save_brand_pool_plan(ROOT, company, safe_slug, uploaded_plan, plan_name)


def render_brand_validation_checklist(company: str):
    status = get_brand_validation_status(company)
    logo_flash = ui_pop_flash(st.session_state, "brand_logo_flash_v1")

    with st.container(border=True):
        st.markdown("#### Brand Checklist")
        st.caption(f"Current brand: {status['company']}  |  slug: `{status['slug']}`")

        if logo_flash:
            st.success(logo_flash)

        st.caption(build_brand_status_summary(status))

        if not status["logo_exists"]:
            st.caption("No logo is required. If none is uploaded, watermarking will be skipped.")

        with st.expander("Logo (optional)", expanded=False):
            st.caption("Upload a transparent PNG only if you want watermark support for this brand.")
            logo_a, logo_b = st.columns([2, 1])
            with logo_a:
                uploaded_logo = st.file_uploader(
                    "Upload / Replace Logo",
                    type=["png"],
                    key=f"brand_logo_upload_{status['slug']}",
                    help="Recommended: transparent PNG brand logo.",
                )
            with logo_b:
                if st.button(
                    "Save Logo",
                    use_container_width=True,
                    key=f"brand_logo_save_{status['slug']}",
                ):
                    ok, msg = save_brand_logo(company, uploaded_logo)
                    if ok:
                        ui_set_flash(st.session_state, "brand_logo_flash_v1", msg)
                        st.rerun()
                    else:
                        st.warning(msg)

def list_companies(input_root: Path) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add_name(value: str) -> None:
        clean = str(value or "").strip()
        if not clean:
            return
        key = clean.casefold()
        if key in seen:
            return
        seen.add(key)
        names.append(clean)

    if CREATIVE_ROOT.exists():
        for p in CREATIVE_ROOT.iterdir():
            if p.is_dir():
                add_name(p.name)

    for ori in ("portrait", "landscape"):
        ori_root = input_root / ori
        if ori_root.exists():
            for p in ori_root.iterdir():
                if p.is_dir():
                    add_name(p.name)

    for brand_name in list_brand_catalog_names():
        add_name(brand_name)

    return sorted(names, key=lambda x: str(x).lower())

# =========================================================
# Session
# =========================================================
ensure_ui_session_defaults(st.session_state)

# =========================================================
# Header
# =========================================================
st.markdown("## 🎬 Video Automation Tool")
st.markdown(
    "<span class='muted'>Workflow: Project Mode (planning & script generation) → Pool Fill Mode (asset coverage and gap closure)</span>",
    unsafe_allow_html=True,
)

if not SRC_MAIN.exists():
    st.error(f"Missing entry: {SRC_MAIN}. Run UI from the project root.")
    st.stop()

# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.markdown("## Controls")
    orientation = st.radio("Layout", ["portrait", "landscape"], horizontal=True)

    st.markdown("### Language")
    lang_options = [
        ("English", "en-US"),
        ("French", "fr-FR"),
        ("Spanish", "es-ES"),
        ("Russian", "ru-RU"),
        ("Arabic", "ar-SA"),
        ("Uyghur", "ug-CN"),
        ("Kazakh", "kk-KZ"),
        ("Uzbek", "uz-UZ"),
        ("Tajik", "tg-TJ"),
        ("Other…", "other"),
    ]
    lang_labels = [f"{n} ({c})" if c != "other" else n for n, c in lang_options]
    sel = st.selectbox("Language", lang_labels, index=0)
    sel_code = dict(zip(lang_labels, [c for _, c in lang_options]))[sel]
    if sel_code == "other":
        lang_code = st.text_input("Custom Language (BCP-47)", value="", placeholder="e.g. zh-CN / en-GB").strip()
    else:
        lang_code = sel_code
    if not lang_code:
        lang_code = "en-US"

    st.markdown("### ElevenLabs")
    profile = ensure_default_eleven_profile()
    saved_key = load_eleven_api_key()
    eleven_key = st.text_input("API Key", value=saved_key, type="password")

    model_id = st.selectbox(
        "TTS Model",
        ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5", "eleven_v3"],
        index=0,
    )

    lang_short = (lang_code.split("-")[0] if lang_code else "en").lower()
    cur_voice_id = str(((profile.get("languages", {}) or {}).get(lang_short, {}) or {}).get("voice_id", "") or "")
    voice_id_input = st.text_input(
        f"Voice ID ({lang_short})",
        value=cur_voice_id,
        help="Must be an ElevenLabs voice_id.",
    )

    save_a, save_b = st.columns([1, 1])
    with save_a:
        if st.button("Save TTS", width="stretch"):
            if eleven_key.strip():
                save_eleven_api_key(eleven_key.strip())

            prof = load_eleven_profile()
            prof.setdefault("defaults", {})
            prof.setdefault("languages", {})

            if isinstance(prof.get("defaults"), dict):
                prof["defaults"]["model_id"] = model_id
                prof["defaults"].setdefault("output_format", "mp3_44100_128")

            if isinstance(prof.get("languages"), dict):
                prof["languages"].setdefault(lang_short, {})
                if isinstance(prof["languages"][lang_short], dict):
                    prof["languages"][lang_short]["voice_id"] = voice_id_input.strip()

            save_eleven_profile(prof)
            st.success("Saved")

    with save_b:
        with st.popover("Voice Map"):
            langs = profile.get("languages", {}) if isinstance(profile.get("languages", {}), dict) else {}
            rows_map = [{"lang": k, "voice_id": (v or {}).get("voice_id", "")} for k, v in sorted(langs.items())]
            st.dataframe(rows_map, width="stretch", hide_index=True)

    ai_provider_settings = render_ai_provider_settings(root=ROOT)

    st.markdown("### Output Defaults")
    target_fps = get_default_fps()
    filter_preset_name = st.selectbox("Visual Filter", ["clean", "industrial", "warm_brand"], index=1)
    _ = get_filter_preset(filter_preset_name)
    st.caption(f"FPS: {target_fps}  |  Filter: {filter_preset_name}")

    with st.expander("Advanced", expanded=False):
        input_root = st.text_input("Footage Root", value=str(INPUT_ROOT_DEFAULT))
        verbose = st.checkbox("Verbose Logs (Dev)", value=False)

# =========================================================
# ENV
# =========================================================
ENV = os.environ.copy()

_api = load_eleven_api_key()
if _api:
    ENV["ELEVENLABS_API_KEY"] = _api

_prof = load_eleven_profile()
_defaults = _prof.get("defaults", {}) if isinstance(_prof.get("defaults", {}), dict) else {}


ENV["ELEVENLABS_MODEL_ID"] = str(_defaults.get("model_id", "eleven_multilingual_v2"))
ENV["ELEVENLABS_OUTPUT_FORMAT"] = str(_defaults.get("output_format", "mp3_44100_128"))

_langs = _prof.get("languages", {}) if isinstance(_prof.get("languages", {}), dict) else {}
for k, v in _langs.items():
    if isinstance(v, dict):
        vid = str(v.get("voice_id", "") or "").strip()
        if vid:
            ENV[f"ELEVENLABS_VOICE_ID_{k.upper()}"] = vid

# =========================================================
# Top controls
# =========================================================
input_root_path = Path(input_root) if "input_root" in locals() else INPUT_ROOT_DEFAULT
output_root_path = OUTPUT_ROOT_DEFAULT

companies = list_companies(input_root_path)
preferred_company = str(st.session_state.pop("pending_company_select_top", "") or "").strip()
if preferred_company and preferred_company in companies:
    default_idx = companies.index(preferred_company)
else:
    default_idx = 0 if companies else None

top_a, top_b = st.columns([1, 1])
with top_a:
    if companies:
        if preferred_company and preferred_company in companies:
            st.session_state["company_select_top"] = preferred_company
        company = st.selectbox("Company", companies, index=default_idx, key="company_select_top")
    else:
        company = ""
        st.info("No company workspace found yet. Create your first company workspace to start planning.")
with top_b:
    work_mode = st.radio(
        "Work Mode",
        ["Project Mode", "Pool Fill Mode"],
        horizontal=True,
        key="work_mode",
    )

brand_create_a, brand_create_b = st.columns([2, 1])
with brand_create_a:
    new_brand_name = st.text_input(
        "Create Company Workspace",
        value="",
        placeholder="e.g. Acme Elevators",
        key="create_brand_name_v1_main",
    )

brand_creation_flash = str(st.session_state.pop("brand_creation_flash_v1", "") or "").strip()
if brand_creation_flash:
    st.success(brand_creation_flash)
with brand_create_b:
    slug_preview = safe_slug(new_brand_name).lower() if new_brand_name.strip() else ""
    brand_dir_exists = bool(slug_preview) and (ROOT / "data" / "brands" / slug_preview).exists()
    create_disabled = (not new_brand_name.strip()) or (not slug_preview) or brand_dir_exists

    st.caption(f"Slug: {slug_preview or '(waiting)'}")
    if brand_dir_exists:
        st.caption("Status: company workspace already exists")
    elif slug_preview:
        st.caption("Creates managed company folders and starter brand config")

    if st.button(
        "Create Company Workspace",
        use_container_width=True,
        key="create_brand_skeleton_v1_main",
        disabled=create_disabled,
    ):
        ok, msg = clone_brand_starter_into_project(new_brand_name)
        if ok:
            provision_brand_workspace(
                root=ROOT,
                company=new_brand_name.strip(),
                slugify=safe_slug,
                input_root=input_root_path,
            )
            st.session_state["pending_company_select_top"] = new_brand_name.strip()
            st.session_state["brand_creation_flash_v1"] = msg
            st.rerun()
        else:
            st.warning(msg)

if company:
    with st.expander("Delete Company Workspace", expanded=False):
        st.caption("Danger zone: deletion removes only managed directories for this company.")
        deletion_scan = scan_brand_workspace(root=ROOT, company=company, slugify=safe_slug, input_root=input_root_path)
        rows = deletion_scan["paths"]
        st.dataframe(rows, hide_index=True, use_container_width=True)

        requires_confirm = bool(deletion_scan["total_files"] > 0)
        if requires_confirm:
            st.warning(f"This workspace currently contains {deletion_scan['total_files']} file(s). Type the exact company name to enable deletion.")
            delete_confirm_name = st.text_input("Type company name to confirm", value="", key="delete_company_confirm_name_v1")
            delete_enabled = delete_confirm_name.strip() == company
        else:
            st.caption("No files detected under managed paths. Deletion can proceed without typed confirmation.")
            delete_enabled = True

        if st.button("Delete Company Workspace", key="delete_company_workspace_v1", disabled=not delete_enabled):
            result = delete_brand_workspace(root=ROOT, company=company, slugify=safe_slug, input_root=input_root_path)
            st.success(f"Deleted {len(result['deleted'])} managed path(s).")
            st.session_state.pop("company_select_top", None)
            st.rerun()

if company:
    render_brand_validation_checklist(company)
else:
    st.caption("Create your first company workspace above, then select it to continue.")
    st.stop()

# =========================================================
# Storage
# =========================================================
if company:
    storage_state = compute_storage_state(
        input_root_path=input_root_path,
        company=company,
        orientation=orientation,
        ensure_company_storage_fn=ensure_company_storage,
        get_storage_dirs_fn=get_storage_dirs,
    )
else:
    storage_state = {
        "storage_ready": False,
        "storage_error": "No company selected.",
        "dirs": {},
        "inbox_dir": None,
        "factory_dir": None,
    }

storage_ready = storage_state["storage_ready"]
storage_error = storage_state["storage_error"]
dirs = storage_state["dirs"]
inbox_dir = storage_state["inbox_dir"]
factory_dir = storage_state["factory_dir"]

if not storage_ready:
    st.warning("Footage storage is unavailable. You can still edit scripts and settings, but footage actions are disabled.")
    st.caption(f"Footage Root: {input_root_path}")
    if storage_error:
        st.caption(f"Reason: {storage_error}")

if work_mode == "Project Mode" and company:
    render_ai_script_entry_panel(
        root=ROOT,
        company=company,
        orientation=orientation,
        provider_settings=ai_provider_settings,
    )

# =========================================================
# Pool Fill Mode (independent page)
# =========================================================
if work_mode == "Pool Fill Mode":
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("## Pool Fill Mode")
    st.caption("Coverage stage after planning: use pool plans to close footage gaps and backfill required slot coverage.")

    if not storage_ready or not factory_dir:
        st.info("Footage storage is unavailable. Pool Fill Mode is currently disabled.")
        st.stop()

    available_pool_plans = list_brand_pool_plans(company)
    pool_plan_flash = ui_pop_flash(st.session_state, "pool_plan_manager_flash_v1")
    if pool_plan_flash:
        st.success(pool_plan_flash)

    with st.expander("Manage Pool Plans", expanded=False):
        st.caption("Upload the first plan for a new brand, or add / replace plans for the current brand.")

        manage_a, manage_b = st.columns([2, 1])
        with manage_a:
            uploaded_plan_file = st.file_uploader(
                "Upload Plan YAML",
                type=["yaml", "yml"],
                key=f"pool_plan_manager_upload_{safe_slug(company).lower()}",
                help="Upload a YAML pool plan for the current brand.",
            )
        with manage_b:
            plan_name_input = st.text_input(
                "Save as",
                value="",
                placeholder="default / campaign-a / showroom-v2",
                key=f"pool_plan_manager_name_{safe_slug(company).lower()}",
            )

        if st.button(
            "Save Pool Plan",
            use_container_width=True,
            key=f"pool_plan_manager_save_{safe_slug(company).lower()}",
        ):
            ok, msg, saved_label = save_brand_pool_plan(company, uploaded_plan_file, plan_name_input)
            if ok:
                st.session_state["pool_plan_select_v4"] = saved_label
                ui_set_flash(st.session_state, "pool_plan_manager_flash_v1", msg)
                st.rerun()
            else:
                st.warning(msg)

    if not available_pool_plans:
        st.info("No pool plans found for this brand yet. Upload one in Manage Pool Plans to continue.")
        st.stop()

    pool_plan_labels, pool_plan_map = build_pool_plan_label_map(available_pool_plans, POOL_PLAN_DIR)

    ui_ensure_valid_choice(st.session_state, "pool_plan_select_v4", pool_plan_labels)

    toolbar_a, toolbar_b, toolbar_c, toolbar_d = st.columns([1.2, 1.2, 1, 2])
    with toolbar_a:
        selected_plan_label = st.selectbox("Pool Plan", pool_plan_labels, key="pool_plan_select_v4")
    with toolbar_b:
        ext_choice_pool = st.selectbox("Default Ext", [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice_pool_v4")
    with toolbar_c:
        selected_plan_data = get_selected_pool_plan_data(
            selected_plan_label=selected_plan_label,
            pool_plan_map=pool_plan_map,
            load_pool_plan_from_path_fn=load_pool_plan_from_path,
        )
        selected_plan_path = selected_plan_data["selected_plan_path"]
        pool_plan = selected_plan_data["pool_plan"]
        topics = selected_plan_data["topics"]
        topic_names = selected_plan_data["topic_names"]
        if not topic_names:
            st.error("Selected pool plan has no valid topics.")
            st.stop()
        ui_ensure_valid_choice(st.session_state, "pool_topic_v4", topic_names)
        pool_topic = st.selectbox("Pool Topic", topic_names, key="pool_topic_v4")
    with toolbar_d:
        st.markdown('<div class="top-help"></div>', unsafe_allow_html=True)
        st.caption("Workflow continuity: planning defines needs → Pool Fill closes missing coverage with matching clips.")

        try:
            current_plan_path = pool_plan_map[selected_plan_label]
            st.download_button(
                "Download Selected Plan",
                data=current_plan_path.read_text(encoding="utf-8"),
                file_name=current_plan_path.name,
                mime="text/yaml",
                use_container_width=True,
                key=f"download_selected_plan_{safe_slug(company).lower()}_{selected_plan_label}",
            )
        except Exception:
            st.caption("Selected plan could not be read for download.")

    factory_files = list_video_files(factory_dir, VIDEO_SUFFIXES)

    pool_fill_runtime = prepare_pool_fill_runtime(
        pool_plan=pool_plan,
        pool_topic=pool_topic,
        factory_files=factory_files,
        registry_path=CANONICAL_REGISTRY_PATH,
        load_registry_entries_fn=ui_load_registry_entries,
        hydrate_slot_fn=ui_hydrate_slot_from_registry,
        attach_semantics_fn=ui_attach_pool_row_semantics,
        build_card_view_fn=build_pool_card_view,
        build_pool_slot_rows_fn=build_pool_slot_rows,
        sort_pool_slot_rows_fn=sort_pool_slot_rows,
        summarize_pool_slot_rows_fn=summarize_pool_slot_rows,
    )

    selected_topic = pool_fill_runtime["selected_topic"]
    slot_rows = pool_fill_runtime["slot_rows"]
    summary = pool_fill_runtime["summary"]
    active_rows = pool_fill_runtime["active_rows"]
    completed_rows = pool_fill_runtime["completed_rows"]

    with st.container(border=True):
        st.markdown("#### 📋 Today’s Intake Brief")
        st.markdown(f"📍 **Best scene to fill:** {summary['focus_scene']}")
        st.markdown(f"🔥 **Most urgent slot:** {summary['urgent_label']}")
        st.caption(
            f"Need {summary['total_missing']} more clips · "
            f"Existing {summary['total_existing']} / Target {summary['total_target']}"
        )

        guide_html = DOCS_DIR / "pool_fill_shooting_guide.html"
        guide_a, guide_b = st.columns([1.1, 3.2])
        with guide_a:
            if guide_html.exists():
                st.download_button(
                    "Get Guide",
                    data=guide_html.read_text(encoding="utf-8"),
                    file_name=guide_html.name,
                    mime="text/html",
                    use_container_width=True,
                    key="download_pool_guide_html_inline",
                )
        with guide_b:
            st.caption("Field reference for crew phone use. Download once and keep it with the shooting board.")

    st.markdown("### Task Board")
    st.caption("Open missing slots first. Completed slots are folded to the bottom.")

    for i, row in enumerate(active_rows):
        render_pool_active_slot_card(
            row=row,
            pool_topic=pool_topic,
            i=i,
            factory_dir=factory_dir,
            ext_choice_pool=ext_choice_pool,
        )
        st.write("")

    if completed_rows:
        st.markdown("### Filled Slots")
        st.caption("These slots already meet target count. Expand only if you want replacements or alternates.")
        for j, row in enumerate(completed_rows):
            render_pool_completed_slot_card(
                row=row,
                pool_topic=pool_topic,
                i=j,
                factory_dir=factory_dir,
                ext_choice_pool=ext_choice_pool,
            )

    st.stop()

# =========================================================
# Project Mode · Step 1
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Project Planning")
st.caption("Choose your planning path. AI-first is primary. Existing script remains fast for manual workflows.")

planning_path = st.radio(
    "Planning Path",
    ["Create with AI (Primary)", "Use Existing Script (Manual)"],
    horizontal=True,
    key="planning_path_v1",
)

src_mode = "Paste Script YAML"
if planning_path == "Use Existing Script (Manual)":
    src_mode = st.selectbox("Manual Script Source", ["Paste Script YAML", "Use Existing Script YAML"], key="src_mode")

if planning_path == "Create with AI (Primary)":
    st.info("Use the Create with AI section above to compile and draft script intent. Manual YAML is available below only when needed.")

colA, colB = st.columns([2, 1])

selected_path: Path | None = None
with colA:
    if planning_path == "Create with AI (Primary)":
        with st.expander("Manual YAML (optional downstream)", expanded=False):
            st.caption("Keep this collapsed unless you intentionally want to continue via manual YAML.")
            st.session_state["creative_draft"] = st.text_area(
                "Script YAML",
                value=st.session_state.get("creative_draft", ""),
                height=180,
                placeholder="Paste your Creative Script YAML here…",
                label_visibility="collapsed",
            )
    else:
        if src_mode == "Paste Script YAML":
            st.session_state["creative_draft"] = st.text_area(
                "Script YAML",
                value=st.session_state.get("creative_draft", ""),
                height=180,
                placeholder="Paste your Creative Script YAML here…",
                label_visibility="collapsed",
            )
        else:
            creative_dir = CREATIVE_ROOT / company
            creative_dir.mkdir(parents=True, exist_ok=True)
            files = sorted(creative_dir.glob("*.yaml"))
            if not files:
                st.warning("No script YAML files were found for this company.")
            else:
                selected_path = st.selectbox("Select Script YAML", files, format_func=lambda p: p.name, key="select_yaml")
                st.caption("The selected script will be used as-is.")

with colB:
    st.markdown("**Actions**")
    draft_text = str(st.session_state.get("creative_draft", "") or "").strip()
    if planning_path == "Create with AI (Primary)":
        generate_ready = bool(draft_text)
        generate_help = "In AI-primary mode, paste manual YAML in the optional manual section before generating task rows."
    elif src_mode == "Use Existing Script YAML":
        generate_ready = selected_path is not None
        generate_help = "Select an existing script YAML to generate task rows."
    else:
        generate_ready = bool(draft_text)
        generate_help = "Paste script YAML to generate task rows."

    generate_btn = st.button(
        "Generate Task Rows",
        use_container_width=True,
        key="generate_tasks",
        disabled=not generate_ready,
        help=generate_help,
    )
    compact_view = st.checkbox("Compact View", value=True, key="compact_view")
    export_html = st.checkbox("Export Printable HTML", value=True, key="export_html")

    if not generate_ready:
        st.caption(generate_help)

if generate_btn:
    if src_mode == "Use Existing Script YAML" and selected_path:
        creative_text = selected_path.read_text(encoding="utf-8")
        name_seed = selected_path.stem
    else:
        creative_text = (st.session_state.get("creative_draft") or "").strip()
        name_seed = "pasted"

    d = load_yaml_text(creative_text)
    ok, msg = validate_creative_schema(d)
    if not ok:
        st.error(msg)
    else:
        lang_check = build_language_check(d, lang_code, voice_id_input, load_eleven_profile())

        if lang_check["blocking"]:
            st.error(lang_check["summary"])
            for item in lang_check["messages"]:
                st.write(f"- {item}")
        else:
            st.info(lang_check["summary"])
            for item in lang_check["messages"]:
                st.caption(f"• {item}")
            if lang_check.get("sample"):
                st.caption(f"Sample text: {lang_check['sample']}")

            project = str((d.get("meta", {}) or {}).get("project", "") or name_seed)
            run_id = f"{safe_slug(project)}_{now_tag()[:15]}"
            run_dir = output_root_path / orientation / company / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            layout = ensure_run_layout(run_dir)
            internal_dir = layout["internal_dir"]
            st.session_state["run_dir"] = str(run_dir)

            creative_path = internal_dir / f"{run_id}.creative.yaml"
            creative_path.write_text(creative_text, encoding="utf-8")
            st.session_state["active_creative_path"] = str(creative_path)

            compiled_out = internal_dir / f"{run_id}.compiled.yaml"
            st.session_state["compiled_out_path"] = str(compiled_out)

            beats = beats_from_creative(d)
            rows: list[dict] = []
            row_i = 1

            for i, beat in enumerate(beats, start=1):
                category = infer_category_from_beat(beat)
                scene = infer_scene_from_beat(beat)
                visual = str(beat.get("visual") or beat.get("visual_description") or "")
                duration_hint = beat.get("duration_hint")
                seconds_default = str(duration_hint) if duration_hint else ""
                shots = infer_shots_from_beat(beat)

                for shot in shots:
                    shot_norm = "detail" if shot in ["close"] else shot
                    rows.append(
                        {
                            "Row": f"S{row_i:03d}",
                            "Beat": i,
                            "Category": category,
                            "Scene": scene,
                            "Shot": shot_norm,
                            "Seconds": seconds_default or default_seconds_for_shot(shot_norm),
                            "Movement": suggested_movement(shot_norm),
                            "Notes": visual,
                            "BeatPurpose": str(beat.get("purpose") or ""),
                        }
                    )
                    row_i += 1

            st.session_state["shooting_rows"] = rows
            (internal_dir / "shooting_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

            if export_html:
                (run_dir / "task_rows.html").write_text(render_html_task_table(rows), encoding="utf-8")

            st.success(f"Generated {len(rows)} task rows.")
            st.caption(f"Run Folder: {run_dir}")

rows = st.session_state.get("shooting_rows") or []
run_dir = Path(st.session_state["run_dir"]) if st.session_state.get("run_dir") else None

if rows and run_dir:
    if storage_ready and factory_dir:
        coverage = summarize_factory_coverage(rows, factory_dir)
        total_need = coverage["total_need"]
        total_ready = coverage["total_ready"]
        total_missing = coverage["total_missing"]
    else:
        total_need = len(rows)
        total_ready = 0
        total_missing = total_need

    m1, m2, m3 = st.columns([1, 1, 1])
    m1.metric("Total Shots", total_need)
    m2.metric("Ready", total_ready)
    m3.metric("Missing", total_missing)

    show_cols = (
        ["Row", "Scene", "Shot", "Seconds", "Movement", "Notes"]
        if compact_view
        else ["Row", "Beat", "Category", "Scene", "Shot", "Seconds", "Movement", "Notes"]
    )
    st.dataframe([{k: r.get(k, "") for k in show_cols} for r in rows], width="stretch", hide_index=True)

    if export_html:
        html_path = run_dir / "task_rows.html"
        if html_path.exists():
            st.download_button(
                "Download Printable HTML",
                data=html_path.read_text(encoding="utf-8"),
                file_name=html_path.name,
                mime="text/html",
                width="stretch",
            )

# =========================================================
# Project Mode · Step 2
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 2 · Footage Board")
st.caption("Project-driven intake. Missing task slots can be filled by upload or inbox transfer.")

if not storage_ready or not inbox_dir or not factory_dir:
    st.info("Footage storage is unavailable. Step 2 is currently disabled.")
elif rows:
    auto_use_factory = st.checkbox("Auto-match Existing Factory Footage", value=True, key="auto_use_factory")
    show_matches = st.checkbox("Show Matched Filenames", value=False, key="show_matches")
    ext_choice = st.selectbox("Default Upload Extension", [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice")

    factory_files = list_video_files(factory_dir, VIDEO_SUFFIXES)
    inbox_files = list_video_files(inbox_dir, VIDEO_SUFFIXES)

    beats_map: dict[int, list[dict]] = {}
    for r in rows:
        beats_map.setdefault(int(r["Beat"]), []).append(r)

    with st.expander("Factory Asset Index Preview", expanded=False):
        preview_items = load_asset_index(factory_dir / "asset_index.json")
        if preview_items:
            preview_rows = []
            for item in preview_items[:30]:
                preview_rows.append(
                    {
                        "filename": item.get("filename", ""),
                        "scene": item.get("scene", ""),
                        "content": item.get("content", ""),
                        "coverage": item.get("coverage", ""),
                        "move": item.get("move", ""),
                        "raw_duration": item.get("raw_duration", ""),
                        "usable_duration": item.get("usable_duration", ""),
                        "quality_status": item.get("quality_status", ""),
                    }
                )
            st.dataframe(preview_rows, width="stretch", hide_index=True)
        else:
            st.info("No indexed factory assets yet.")

    with st.expander("Edit Asset Soft Tags", expanded=False):
        editable_items = load_asset_index(factory_dir / "asset_index.json")
        if not editable_items:
            st.info("No indexed factory assets yet.")
        else:
            selected_filename = st.selectbox(
                "Asset",
                [str(item.get("filename", "")) for item in editable_items],
                key="asset_editor_filename",
            )

            selected_item = None
            for item in editable_items:
                if str(item.get("filename", "")) == selected_filename:
                    selected_item = item
                    break

            if selected_item:
                c1, c2, c3 = st.columns(3)
                with c1:
                    hero_safe = st.checkbox("hero_safe", value=bool(selected_item.get("hero_safe", False)), key="edit_hero_safe")
                    intro_safe = st.checkbox("intro_safe", value=bool(selected_item.get("intro_safe", False)), key="edit_intro_safe")
                with c2:
                    outro_safe = st.checkbox("outro_safe", value=bool(selected_item.get("outro_safe", False)), key="edit_outro_safe")
                    continuity_group = st.text_input("continuity_group", value=str(selected_item.get("continuity_group", "") or ""), key="edit_continuity_group")
                with c3:
                    energy = st.selectbox("energy", ["low", "medium", "high"], index=["low", "medium", "high"].index(str(selected_item.get("energy", "medium") or "medium")) if str(selected_item.get("energy", "medium") or "medium") in ["low", "medium", "high"] else 1, key="edit_energy")
                    quality_status = st.selectbox("quality_status", ["approved", "review", "reject"], index=["approved", "review", "reject"].index(str(selected_item.get("quality_status", "approved") or "approved")) if str(selected_item.get("quality_status", "approved") or "approved") in ["approved", "review", "reject"] else 0, key="edit_quality_status")

                notes = st.text_area("notes", value=str(selected_item.get("notes", "") or ""), height=80, key="edit_notes")

                if st.button("Save Asset Tags", key="save_asset_tags"):
                    ok = update_asset_record_fields(
                        factory_dir / "asset_index.json",
                        selected_filename,
                        {
                            "hero_safe": hero_safe,
                            "intro_safe": intro_safe,
                            "outro_safe": outro_safe,
                            "continuity_group": continuity_group.strip(),
                            "energy": energy,
                            "quality_status": quality_status,
                            "notes": notes.strip(),
                        },
                    )
                    if ok:
                        st.success("Asset tags saved.")
                        st.rerun()
                    else:
                        st.warning("No asset changes were saved.")

    for beat_no in sorted(beats_map.keys()):
        beat_rows = beats_map[beat_no]
        beat_title = beat_rows[0].get("BeatPurpose") or f"Beat {beat_no}"

        with st.expander(f"Beat {beat_no} · {beat_title}", expanded=False):
            need: dict[tuple[str, str], int] = {}
            for rr in beat_rows:
                key = (rr["Category"], rr["Shot"])
                need[key] = need.get(key, 0) + 1

            for (cat, shot), n_need in need.items():
                scene_name = "factory"
                content_name = cat
                coverage_name = shot
                move_name = "static"

                matched = [
                    p for p in factory_files
                    if p.name.lower().startswith(f"{safe_slug(scene_name)}_{safe_slug(content_name)}_{safe_slug(coverage_name)}_")
                ]
                ready = min(n_need, len(matched)) if auto_use_factory else 0
                missing = n_need - ready

                st.markdown(f"**{cat.upper()} · {shot.upper()}** — required {n_need}, ready {ready}, missing {missing}")

                if show_matches and matched:
                    st.code("\n".join([p.name for p in matched[:20]]), language="text")

                if missing <= 0:
                    st.markdown("<span class='tiny'>No action needed.</span>", unsafe_allow_html=True)
                    st.markdown("---")
                    continue

                move_name = st.selectbox(
                    f"Move token for {cat}_{shot}",
                    ["static", "slide", "pushin", "follow", "orbit", "reveal"],
                    index=0,
                    key=f"move_token_{beat_no}_{cat}_{shot}",
                )

                uploads = st.file_uploader(
                    f"Upload missing clips for {cat}_{shot}",
                    type=VIDEO_EXTS,
                    accept_multiple_files=True,
                    key=f"up_{beat_no}_{cat}_{shot}",
                )

                pick_inbox = st.multiselect(
                    f"Move from Inbox ({len(inbox_files)})",
                    options=inbox_files,
                    format_func=lambda p: f"{p.name}  [{classify_orientation(p)}]",
                    key=f"inbox_{beat_no}_{cat}_{shot}",
                )

                if st.button("Save to Factory Pool", key=f"save_{beat_no}_{cat}_{shot}"):
                    cur = next_index_for(factory_dir, scene_name, content_name, coverage_name, move_name, ext_choice)
                    rejected_msgs: list[str] = []
                    saved_count = 0

                    if uploads:
                        for uf in uploads:
                            tmp_ext = Path(uf.name).suffix.lower() or ext_choice
                            tmp_path = inbox_dir / f"__tmp_check_{now_tag()}_{safe_slug(Path(uf.name).stem)}{tmp_ext}"
                            try:
                                tmp_path.write_bytes(uf.getbuffer().tobytes())
                                actual = classify_orientation(tmp_path)
                                if actual != orientation:
                                    rejected_msgs.append(f"{uf.name}: {actual} does not match current layout ({orientation}).")
                                    tmp_path.unlink(missing_ok=True)
                                    continue

                                fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, tmp_ext)
                                saved_path = safe_write_file(factory_dir / fname, uf.getbuffer().tobytes())
                                upsert_asset_record(factory_dir / "asset_index.json", saved_path)
                                saved_count += 1
                                cur += 1
                            finally:
                                if tmp_path.exists():
                                    tmp_path.unlink(missing_ok=True)

                    if pick_inbox:
                        for src in pick_inbox:
                            actual = classify_orientation(src)
                            if actual != orientation:
                                rejected_msgs.append(f"{src.name}: {actual} does not match current layout ({orientation}).")
                                continue

                            ext = src.suffix.lower() or ext_choice
                            fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, ext)
                            dst = factory_dir / fname
                            if dst.exists():
                                dst = factory_dir / f"{Path(fname).stem}_{now_tag()}{ext}"
                            try:
                                src.rename(dst)
                                upsert_asset_record(factory_dir / "asset_index.json", dst)
                                saved_count += 1
                                cur += 1
                            except Exception as e:
                                st.error(f"Move Failed: {src.name} → {dst.name} ({e})")

                    if rejected_msgs:
                        st.warning("Some clips were rejected due to orientation mismatch:")
                        for msg in rejected_msgs:
                            st.write(f"- {msg}")

                    if saved_count > 0:
                        st.success(f"Saved {saved_count} clip(s) to the Factory Pool. Refreshing…")
                        st.rerun()
                    elif not rejected_msgs:
                        st.info("No clips were saved.")

                st.markdown("---")
else:
    st.info("Generate Task Rows in Step 1 first.")

# =========================================================
# Project Mode · Step 3
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 3 · Create Video")
st.caption("Creates the final video with lightweight run logs and default 60fps output.")

active_creative_path = Path(st.session_state["active_creative_path"]) if st.session_state.get("active_creative_path") else None
run_dir = Path(st.session_state["run_dir"]) if st.session_state.get("run_dir") else None
compiled_out = Path(st.session_state["compiled_out_path"]) if st.session_state.get("compiled_out_path") else None

if not storage_ready:
    st.info("Footage storage is unavailable. Step 3 is currently disabled.")
elif not (active_creative_path and run_dir and compiled_out and active_creative_path.exists()):
    st.info("Generate Task Rows in Step 1 first.")
else:
    if st.button("Create Video", width="stretch", key="create_video"):
        progress = st.progress(0)
        status = st.empty()

        try:
            status.markdown("**Preparing Workflow…**")
            progress.progress(10)

            status.markdown("**Preparing Timeline…**")
            progress.progress(30)

            cmd_compile = [sys.executable, str(SRC_MAIN)]
            if "verbose" in locals() and verbose:
                cmd_compile.append("-v")
            cmd_compile += ["compile", "--creative", str(active_creative_path), "--out", str(compiled_out)]

            rc, compile_logs = run_cmd_silent(cmd_compile, ENV)
            (run_dir / "_internal" / "compile.log").write_text(compile_logs, encoding="utf-8")
            if rc != 0:
                progress.progress(100)
                st.error("Timeline preparation failed. See _internal/compile.log in the Run Folder.")
                raise SystemExit(0)

            status.markdown("**Applying Render Settings…**")
            progress.progress(50)
            patch_compiled_yaml(compiled_out, orientation, lang_code, model_id, ELEVEN_PROFILE_PATH, filter_preset_name=filter_preset_name)

            status.markdown("**Rendering Final Video…**")
            progress.progress(70)

            cmd_run = [sys.executable, str(SRC_MAIN)]
            if "verbose" in locals() and verbose:
                cmd_run.append("-v")
            cmd_run += ["run", "--company", company, "--script", str(compiled_out), "--input", str(input_root_path)]

            rc2, render_logs = run_cmd_silent(cmd_run, ENV)
            (run_dir / "_internal" / "render.log").write_text(render_logs, encoding="utf-8")

            if rc2 != 0:
                progress.progress(100)
                st.error("Video rendering failed. See _internal/render.log in the Run Folder.")
                raise SystemExit(0)

            status.markdown("**Completed.**")
            progress.progress(100)
            st.success("Final video created successfully.")

        except SystemExit:
            pass
        except Exception as e:
            progress.progress(100)
            st.error(f"Unexpected Error: {e}")

    st.link_button("Open Run Folder", f"file://{run_dir}", width="stretch")
