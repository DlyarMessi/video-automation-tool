#!/usr/bin/env python3
import json
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

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
    list_managed_brand_names,
)
from src.ui_provider_settings import render_ai_provider_settings
from src.ui_ai_entry import render_ai_script_entry_panel
from src.ui_local_prefs import load_ui_local_prefs, remember_last_company, clear_last_company, remember_last_orientation

from src.render_profile import get_default_fps, get_filter_preset
from src.language_checks import build_language_check
from src.material_index import load_asset_index, upsert_asset_record, update_asset_record_fields, parse_filename_core
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
    summarize_factory_coverage,
    allocate_coverage_across_beats,
    parse_factory_filename_key,
    normalize_demo_content_token,
    ensure_company_storage,
    get_storage_dirs,
    classify_orientation,
    normalize_demo_coverage_token,
    build_project_slots_from_creative,
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
    """Build normalized slot rows with budget-aware counting.
    
    Multiple slots sharing the same pool bucket (scene/content/coverage)
    share the available clips. One clip cannot satisfy two slots.
    """
    rows = []

    # Phase 1: count total pool clips per bucket (scene/content/coverage)
    bucket_pool_count: dict[tuple[str,str,str], int] = {}
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        key = (
            str(slot.get("scene", "")).strip().lower(),
            str(slot.get("content", "")).strip().lower(),
            str(slot.get("coverage", "")).strip().lower(),
        )
        if key not in bucket_pool_count:
            bucket_pool_count[key] = count_pool_matches(
                factory_files,
                key[0], key[1], key[2], "",
            )

    # Phase 2: budget remaining clips across slots per bucket
    bucket_remaining: dict[tuple[str,str,str], int] = dict(bucket_pool_count)

    for slot in slots:
        if not isinstance(slot, dict):
            continue

        scene_name = str(slot.get("scene", "")).strip()
        content_name = str(slot.get("content", "")).strip()
        coverage_name = str(slot.get("coverage", "")).strip()
        move_name = str(slot.get("move", "")).strip()
        target = int(slot.get("target", 0) or 0)
        priority = str(slot.get("priority", "medium") or "medium")
        defaults = slot.get("defaults", {}) if isinstance(slot.get("defaults"), dict) else {}

        key = (scene_name.lower(), content_name.lower(), coverage_name.lower())
        available = bucket_remaining.get(key, 0)
        allocated = min(target, available)
        bucket_remaining[key] = max(0, available - allocated)
        missing = max(0, target - allocated)

        row = dict(slot)
        row.update(
            {
                "scene": scene_name,
                "content": content_name,
                "coverage": coverage_name,
                "move": move_name,
                "target": target,
                "priority": priority,
                "priority_score": priority_score(priority),
                "existing": allocated,
                "missing": missing,
                "defaults": defaults,
            }
        )
        row.setdefault("slot_label", slot_display_name(scene_name, content_name, coverage_name, move_name))
        row["duration_label"] = recommended_duration_for_slot(coverage_name, move_name)
        row["move_label"] = movement_guidance(move_name)
        row["framing_label"] = composition_guidance(scene_name, content_name, coverage_name)

        rows.append(row)

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
        existing_human_label = str(merged.get("human_label", "") or "").strip()
        registry_human_label = str(registry_public.get("human_label", "") or "").strip()
        slot_human_label = str(slot_semantic.get("human_label", "") or "").strip()
        preferred_human_label = existing_human_label or registry_human_label or slot_human_label

        if preferred_human_label:
            merged["canonical_slot_label"] = canonical_label
            merged["slot_label"] = preferred_human_label
            merged["human_label"] = preferred_human_label

        existing_shoot_brief = str(merged.get("shoot_brief", "") or "").strip()
        registry_shoot_brief = str(registry_public.get("shoot_brief", "") or "").strip()
        slot_shoot_brief = str(slot_semantic.get("shoot_brief", "") or "").strip()
        preferred_shoot_brief = existing_shoot_brief or registry_shoot_brief or slot_shoot_brief
        if preferred_shoot_brief:
            merged["shoot_brief"] = preferred_shoot_brief

        existing_purpose = str(merged.get("purpose", "") or "").strip()
        registry_purpose = str(registry_story.get("purpose_text", "") or "").strip()
        slot_purpose = str(slot_semantic.get("purpose", "") or "").strip()
        preferred_purpose = existing_purpose or registry_purpose or slot_purpose
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




def render_pool_active_slot_card(
    row,
    pool_topic: str,
    i: int,
    factory_dir: Path,
    ext_choice_pool: str,
    inbox_dir: Optional[Path] = None,
    orientation: Optional[str] = None,
):
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

    inbox_files = list_video_files(inbox_dir, VIDEO_SUFFIXES) if inbox_dir and inbox_dir.exists() else []

    with st.container(border=True):
        st.markdown(f"**{display_label}** {priority_badge(priority)}")
        if slot_label_text and display_label != slot_label_text:
            st.caption(f"`{slot_label_text}`")
        if canonical_tuple_text:
            st.caption(canonical_tuple_text)
        if registry_key_text:
            st.caption(f"registry_key: `{registry_key_text}`")
        st.markdown(f"🎬 recommended `{row.get('move', 'static')}` · ⏱️ `{row['duration_label']}` · ⚠️ **missing {missing}**")
        if shoot_brief_text:
            st.caption(shoot_brief_text)
        st.caption(f"💡 {row['framing_label']} · {row['move_label']}")

        progress_col, status_col = st.columns([3, 2])
        with progress_col:
            ratio = 0.0 if target <= 0 else max(0.0, min(existing / target, 1.0))
            st.progress(ratio)
        with status_col:
            st.markdown(
                f"<div style='font-size:0.92rem; text-align:right;'>"
                f"{existing}/{target} · "
                f"<span style='color:#FF4B4B; font-weight:600;'>need {missing}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        _move_options = ["static", "slide", "pushin", "follow", "orbit", "reveal", "pan"]
        _move_default_idx = _move_options.index(move_name) if move_name in _move_options else 0
        _sel_col, _upload_col = st.columns([1, 3])
        with _sel_col:
            move_name = st.selectbox(
                "Move",
                _move_options,
                index=_move_default_idx,
                key=f"pool_fill_v3_move_{pool_topic}_{i}",
                help="Recommended: " + str(row.get("move", "static")) + " — choose based on your actual footage",
            )
        with _upload_col:
            uploads = st.file_uploader(
                "Upload clips for this slot",
                type=VIDEO_EXTS,
                accept_multiple_files=True,
                key=f"pool_fill_v3_upload_{pool_topic}_{i}",
                label_visibility="collapsed",
            )

        pick_inbox = []
        if inbox_files:
            pick_inbox = st.multiselect(
                f"Move from Inbox ({len(inbox_files)})",
                options=inbox_files,
                format_func=lambda p: f"{p.name}  [{classify_orientation(p)}]",
                key=f"pool_fill_v3_inbox_{pool_topic}_{i}",
            )

        with st.expander(tr("Clip tags"), expanded=False):
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

        if st.button(tr("Save to Pool"), key=f"pool_fill_v3_save_{pool_topic}_{i}", use_container_width=True):
            if not uploads and not pick_inbox:
                st.warning("Please upload at least one clip or move one from Inbox.")
            else:
                rejected_msgs = []
                saved_count = 0
                cur = next_index_for(factory_dir, scene_name, content_name, coverage_name, move_name, ext_choice_pool)

                def _apply_defaults(saved_name: str):
                    update_asset_record_fields(
                        factory_dir / "asset_index.json",
                        saved_name,
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

                if uploads:
                    for uf in uploads:
                        ext = Path(uf.name).suffix.lower() or ext_choice_pool
                        tmp_path = factory_dir / f"__tmp_check_{now_tag()}_{safe_slug(Path(uf.name).stem)}{ext}"
                        try:
                            tmp_path.write_bytes(uf.getbuffer().tobytes())
                            if orientation:
                                actual = classify_orientation(tmp_path)
                                if actual != orientation:
                                    rejected_msgs.append(f"{uf.name}: {actual} does not match current layout ({orientation}).")
                                    continue

                            fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, ext)
                            saved_path = safe_write_file(factory_dir / fname, uf.getbuffer().tobytes())
                            upsert_asset_record(factory_dir / "asset_index.json", saved_path)
                            _apply_defaults(saved_path.name)
                            saved_count += 1
                            cur += 1
                        finally:
                            if tmp_path.exists():
                                tmp_path.unlink(missing_ok=True)

                if pick_inbox:
                    for src in pick_inbox:
                        if orientation:
                            actual = classify_orientation(src)
                            if actual != orientation:
                                rejected_msgs.append(f"{src.name}: {actual} does not match current layout ({orientation}).")
                                continue

                        ext = src.suffix.lower() or ext_choice_pool
                        fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, ext)
                        dst = factory_dir / fname
                        if dst.exists():
                            dst = factory_dir / f"{Path(fname).stem}_{now_tag()}{ext}"

                        try:
                            src.rename(dst)
                            upsert_asset_record(factory_dir / "asset_index.json", dst)
                            _apply_defaults(dst.name)
                            saved_count += 1
                            cur += 1
                        except Exception as e:
                            st.error(f"Move Failed: {src.name} → {dst.name} ({e})")

                if rejected_msgs:
                    st.warning("Some clips were rejected due to orientation mismatch:")
                    for msg in rejected_msgs:
                        st.write(f"- {msg}")

                if saved_count > 0:
                    st.session_state["_pool_save_flash"] = f"Saved {saved_count} clip(s) to pool."
                    st.rerun()
                elif not rejected_msgs:
                    st.info("No clips were saved.")

def render_pool_completed_slot_card(
    row,
    pool_topic: str,
    i: int,
    factory_dir: Path,
    ext_choice_pool: str,
    inbox_dir: Optional[Path] = None,
    orientation: Optional[str] = None,
):
    scene_name = str(row.get("scene", "")).strip()
    content_name = str(row.get("content", "")).strip()
    coverage_name = str(row.get("coverage", "")).strip()
    move_name = str(row.get("move", "")).strip()
    target = int(row.get("target", 0) or 0)
    priority = str(row.get("priority", "medium") or "medium")
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

    inbox_files = list_video_files(inbox_dir, VIDEO_SUFFIXES) if inbox_dir and inbox_dir.exists() else []

    with st.container(border=True):
        st.markdown(f"**{display_label}** {priority_badge(priority)}")
        if slot_label_text and display_label != slot_label_text:
            st.caption(f"`{slot_label_text}`")
        if canonical_tuple_text:
            st.caption(canonical_tuple_text)
        if registry_key_text:
            st.caption(f"registry_key: `{registry_key_text}`")
        st.markdown(f"🎬 recommended `{row.get('move', 'static')}` · ⏱️ `{row['duration_label']}` · ✅ **ready {existing}/{target}**")
        if shoot_brief_text:
            st.caption(shoot_brief_text)
        st.caption(f"💡 {row['framing_label']} · {row['move_label']}")

        progress_col, status_col = st.columns([3, 2])
        with progress_col:
            ratio = 0.0 if target <= 0 else max(0.0, min(existing / target, 1.0))
            st.progress(ratio)
        with status_col:
            st.markdown(
                f"<div style='font-size:0.92rem; text-align:right;'>"
                f"{existing}/{target} · "
                f"<span style='color:#16a34a; font-weight:600;'>ready</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.caption("Current clips already meet target. Upload here only if you want replacements or alternates.")

        _move_options_d = ["static", "slide", "pushin", "follow", "orbit", "reveal", "pan"]
        _move_default_idx_d = _move_options_d.index(move_name) if move_name in _move_options_d else 0
        _sel_col_d, _upload_col_d = st.columns([1, 3])
        with _sel_col_d:
            move_name = st.selectbox(
                "Move",
                _move_options_d,
                index=_move_default_idx_d,
                key=f"pool_fill_v3_done_move_{pool_topic}_{i}",
                help="Recommended: " + str(row.get("move", "static")) + " — choose based on your actual footage",
            )
        with _upload_col_d:
            uploads = st.file_uploader(
                "Upload clips for this slot",
                type=VIDEO_EXTS,
                accept_multiple_files=True,
                key=f"pool_fill_v3_done_upload_{pool_topic}_{i}",
                label_visibility="collapsed",
            )

        pick_inbox = []
        if inbox_files:
            pick_inbox = st.multiselect(
                f"Move from Inbox ({len(inbox_files)})",
                options=inbox_files,
                format_func=lambda p: f"{p.name}  [{classify_orientation(p)}]",
                key=f"pool_fill_v3_done_inbox_{pool_topic}_{i}",
            )

        with st.expander(tr("Clip tags"), expanded=False):
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

        if st.button(tr("Save Alternate to Pool"), key=f"pool_fill_v3_done_save_{pool_topic}_{i}", use_container_width=True):
            if not uploads and not pick_inbox:
                st.warning("Please upload at least one clip or move one from Inbox.")
            else:
                rejected_msgs = []
                saved_count = 0
                cur = next_index_for(factory_dir, scene_name, content_name, coverage_name, move_name, ext_choice_pool)

                def _apply_defaults(saved_name: str):
                    update_asset_record_fields(
                        factory_dir / "asset_index.json",
                        saved_name,
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

                if uploads:
                    for uf in uploads:
                        ext = Path(uf.name).suffix.lower() or ext_choice_pool
                        tmp_path = factory_dir / f"__tmp_check_{now_tag()}_{safe_slug(Path(uf.name).stem)}{ext}"
                        try:
                            tmp_path.write_bytes(uf.getbuffer().tobytes())
                            if orientation:
                                actual = classify_orientation(tmp_path)
                                if actual != orientation:
                                    rejected_msgs.append(f"{uf.name}: {actual} does not match current layout ({orientation}).")
                                    continue

                            fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, ext)
                            saved_path = safe_write_file(factory_dir / fname, uf.getbuffer().tobytes())
                            upsert_asset_record(factory_dir / "asset_index.json", saved_path)
                            _apply_defaults(saved_path.name)
                            saved_count += 1
                            cur += 1
                        finally:
                            if tmp_path.exists():
                                tmp_path.unlink(missing_ok=True)

                if pick_inbox:
                    for src in pick_inbox:
                        if orientation:
                            actual = classify_orientation(src)
                            if actual != orientation:
                                rejected_msgs.append(f"{src.name}: {actual} does not match current layout ({orientation}).")
                                continue

                        ext = src.suffix.lower() or ext_choice_pool
                        fname = build_factory_filename(scene_name, content_name, coverage_name, move_name, cur, ext)
                        dst = factory_dir / fname
                        if dst.exists():
                            dst = factory_dir / f"{Path(fname).stem}_{now_tag()}{ext}"

                        try:
                            src.rename(dst)
                            upsert_asset_record(factory_dir / "asset_index.json", dst)
                            _apply_defaults(dst.name)
                            saved_count += 1
                            cur += 1
                        except Exception as e:
                            st.error(f"Move Failed: {src.name} → {dst.name} ({e})")

                if rejected_msgs:
                    st.warning("Some clips were rejected due to orientation mismatch:")
                    for msg in rejected_msgs:
                        st.write(f"- {msg}")

                if saved_count > 0:
                    st.session_state["_pool_save_flash"] = f"Saved {saved_count} clip(s) to pool."
                    st.rerun()
                elif not rejected_msgs:
                    st.info("No clips were saved.")

def render_pool_fill_downloads():
    guide_html = DOCS_DIR / "pool_fill_shooting_guide.html"

    with st.container():
        c1, c2 = st.columns([1, 5])

        with c1:
            if guide_html.exists():
                st.download_button(
                    tr("Get Guide"),
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
    # move is a soft preference, not a hard filter
    # scene + content + coverage is the real identity

    count = 0
    for p in factory_files:
        if not p.is_file() or p.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        if p.name.startswith("._"):
            continue

        core = parse_filename_core(p.name)
        core_scene = safe_slug(str(core.get("scene", "") or "")).lower()
        core_content = safe_slug(str(core.get("content", "") or "")).lower()
        core_coverage = safe_slug(str(core.get("coverage", "") or "")).lower()

        if core_scene != scene:
            continue
        if core_content != content:
            continue
        if core_coverage != coverage:
            continue

        count += 1

    return count

def list_companies() -> list[str]:
    """Company selector source of truth: managed brand workspaces only."""
    return list_managed_brand_names(root=ROOT)


def render_brand_validation_checklist(company: str) -> None:
    """Render lightweight brand setup status for the active company."""
    status = hardening_get_brand_validation_status(ROOT, company, safe_slug)

    logo_ready = bool(status.get("logo_exists"))
    default_plan_ready = bool(status.get("default_plan_exists"))
    available_plans = status.get("available_plans", [])
    if not isinstance(available_plans, list):
        available_plans = []

    if str(st.session_state.get("display_lang", "en") or "en") == "zh":
        parts = [
            f"{tr('logo ready') if logo_ready else tr('logo missing')}",
            f"{tr('default plan ready') if default_plan_ready else tr('default plan missing')}",
            f"{len(available_plans)} 个计划" if available_plans else f"{tr('Available plans')} 0",
        ]
        st.caption(f"{tr('Status:')} " + " · ".join(parts))
    else:
        st.caption(build_brand_status_summary(status))

    all_ready = logo_ready and default_plan_ready
    with st.expander(tr("Brand Validation Checklist"), expanded=not all_ready):
        if str(st.session_state.get("display_lang", "en") or "en") == "zh":
            st.markdown(f"- {'✅' if logo_ready else '⚪'} {tr('Brand logo')} ({status.get('logo_path')})")
            st.markdown(f"- {'✅' if default_plan_ready else '⚪'} {tr('Default pool plan')} ({status.get('default_plan_path')})")
            st.markdown(f"- ℹ️ {tr('Available plans')}：**{', '.join(available_plans) if available_plans else tr('none')}**")
        else:
            st.markdown(f"- {'✅' if logo_ready else '⚪'} Brand logo ({status.get('logo_path')})")
            st.markdown(f"- {'✅' if default_plan_ready else '⚪'} Default pool plan ({status.get('default_plan_path')})")
            st.markdown(f"- ℹ️ Available plans: **{', '.join(available_plans) if available_plans else 'none'}**")



UI_TEXT_ZH = {
    "Video Automation Tool": "视频自动化工具",
    "Workflow: Project Mode (planning & script generation) → Pool Fill Mode (asset coverage and gap closure)": "工作流：项目模式（规划与剧本生成）→ 素材池补充模式（素材覆盖与缺口补齐）",

    "Workspace": "工作区",
    "Global company context for planning, coverage, and export workflows.": "用于规划、补素材与导出流程的全局公司上下文。",
    "Current Company": "当前公司",
    "Create Company Workspace": "创建公司工作区",
    "Display Language": "界面语言",
    "Workflow": "工作流",
    "Current Stage": "当前阶段",
    "Script Planning / Project Mode": "脚本规划 / 项目模式",
    "Shoot Tasks / Coverage / Pool Fill": "拍摄任务 / 覆盖补齐 / 素材池补充",
    "Render / Export becomes available after planning and coverage completion.": "完成规划与素材覆盖后即可进行渲染 / 导出。",

    "System Settings": "系统设置",
    "Default Format": "默认画幅",
    "Language": "语言",
    "Global Default Language": "全局默认语言",
    "ElevenLabs": "ElevenLabs",
    "API Key": "API 密钥",
    "TTS Model": "TTS 模型",
    "Save TTS": "保存 TTS",
    "Voice Map": "语音映射",
    "Output Defaults": "输出默认设置",
    "Visual Filter": "视觉滤镜",
    "Advanced": "高级",
    "Footage Root": "素材根目录",
    "Verbose Logs (Dev)": "详细日志（开发）",

    "AI Provider Settings": "AI 提供方设置",
    "Script Provider": "剧本提供方",
    "DeepSeek API Key": "DeepSeek API 密钥",
    "DeepSeek Model": "DeepSeek 模型",
    "DeepSeek Base URL (optional)": "DeepSeek Base URL（可选）",
    "Save AI Provider": "保存 AI 提供方",

    "Brand Validation Checklist": "品牌校验清单",
    "Brand logo": "品牌 Logo",
    "Default pool plan": "默认素材池计划",
    "Available plans": "可用计划",
    "Status:": "状态：",
    "logo ready": "Logo 已就绪",
    "logo missing": "Logo 缺失",
    "default plan ready": "默认计划已就绪",
    "default plan missing": "默认计划缺失",
    "none": "无",

    "Project Planning": "步骤 1 · 项目规划",
    "Pick a planning path: AI Script Planning is the default workflow, and Import Existing Script stays available for manual control.": "选择规划方式：AI 剧本规划为默认流程，也可导入现有剧本进行手动控制。",
    "✨ AI Script Planning": "✨ AI 剧本规划",
    "📝 Import Existing Script": "📝 导入现有剧本",
    "Manual YAML fallback (optional)": "手动 YAML 备用入口（可选）",
    "Use this only when you intentionally want to import or paste an existing script.": "仅当你明确想导入或粘贴现有剧本时使用。",
    "Script YAML": "剧本 YAML",
    "Manual Script Source": "手动剧本来源",
    "Paste Script YAML": "粘贴剧本 YAML",
    "Use Existing Script YAML": "使用已有剧本 YAML",
    "Select Script YAML": "选择剧本 YAML",
    "The selected script will be used as-is.": "将按原样使用所选剧本。",
    "Generate Task Rows": "生成任务行",
    "Compact View": "紧凑视图",
    "Export Printable HTML": "导出打印版 HTML",
    "Download Printable HTML": "下载打印版 HTML",
    "Paste script YAML to generate task rows.": "粘贴剧本 YAML 以生成任务行。",
    "Select an existing script YAML to generate task rows.": "选择已有剧本 YAML 以生成任务行。",
    "How the current demo categories work": "当前演示分类说明",

    "Create with AI": "AI 生成剧本",
    "Quick Brief": "简要需求",
    "Describe your video goal in natural language. Example:": "请用自然语言描述你的视频目标。示例：",
    "Audience: retail buyers and channel partners": "受众：零售买家与渠道合作伙伴",
    "Objective: explain why this product solves a key pain point": "目标：说明该产品如何解决关键痛点",
    "Must include: product demo, customer scenario, proof point": "必须包含：产品演示、客户场景、证明点",
    "This draft only · Output Language": "仅本次草稿 · 输出语言",
    "This draft only · Format": "仅本次草稿 · 画幅",
    "Approx. Duration": "大致时长",
    "Emphasis": "强调重点",
    "Existing Footage": "是否已有素材",
    "Check what the system understood": "查看系统理解结果",
    "Refresh extracted brief": "刷新提取结果",
    "Rebuild from brief": "根据需求重建",
    "Reset extracted brief": "重置提取结果",
    "Generate Draft": "生成草稿",
    "Secondary actions": "次级操作",
    "Manual YAML fallback (optional)": "手动 YAML 备用入口（可选）",

    "Total Shots": "总镜头数",
    "Ready": "已就绪",
    "Missing": "缺失",
    "Row": "序号",
    "Beat": "段落",
    "Category": "类别",
    "Scene": "场景",
    "Shot": "景别",
    "Seconds": "时长",
    "Movement": "运镜",
    "Notes": "说明",

    "Step 2 · Footage Board": "步骤 2 · 素材看板",
    "Project-driven intake. Missing task slots can be filled by upload or inbox transfer.": "按项目驱动补素材。缺失槽位可通过上传或从收件箱转入来补齐。",
    "Auto-match Existing Factory Footage": "自动匹配现有素材池",
    "Show Matched Filenames": "显示已匹配文件名",
    "Default Upload Extension": "默认上传格式",
    "Factory Asset Index Preview": "素材索引预览",
    "Edit Asset Soft Tags": "编辑素材软标签",
    "Asset": "素材",
    "Save Asset Tags": "保存素材标签",
    "Factory file actions": "素材文件操作",
    "Move to content": "改到内容类别",
    "Move to coverage": "改到景别类别",
    "Move token": "运镜标签",
    "Reclassify / Rename Asset": "重分类 / 重命名素材",
    "Delete Asset": "删除素材",

    "Opening Context": "开场建立",
    "Capability": "能力展示",
    "Trust / Proof": "信任 / 证明",
    "Brand Close": "品牌收束",
    "Ready slots": "已满足槽位",
    "Clip tags": "素材标签",
    "Save to Pool": "保存到素材池",
    "Save Alternate to Pool": "保存备选到素材池",

    "Upload opening context: exterior, entrance, showroom, headquarters, or a clean overall establishing visual. Avoid fragmented close details.": "请上传开场建立素材：外立面、入口、展厅、总部，或干净完整的整体建立镜头。避免碎片化近景。",
    "Upload process visuals: machine action, workflow medium shots, and clear operating details. Avoid empty exterior-only shots.": "请上传流程展示素材：机器动作、流程中景、清晰操作细节。避免只有外景没有过程的镜头。",
    "Upload proof visuals: inspection, testing, certificates, achievements, or stable support detail. Avoid flashy or overly busy motion.": "请上传证明类素材：检验、测试、证书、成果墙，或稳定的支撑性细节。避免花哨或过于繁忙的运动。",
    "Upload the strongest final hero visual: clean, stable, complete, and suitable for closing. Avoid fragmented detail shots.": "请上传最强的收尾 Hero 画面：干净、稳定、完整，适合作为结尾。避免碎片化细节镜头。",

    "Shoot Tasks · Coverage & Missing Assets": "拍摄任务 · 覆盖与缺口补齐",
    "Footage gap-closure stage after planning: use pool plans to close missing coverage and complete required assets.": "规划完成后，进入素材缺口补齐阶段：使用素材池计划补齐缺失覆盖并完成所需素材。",
    "Manage Pool Plans": "管理素材池计划",
    "Upload the first plan for a new brand, or add / replace plans for the current brand.": "可为新品牌上传第一份计划，或为当前品牌新增 / 替换计划。",
    "Upload Plan YAML": "上传计划 YAML",
    "Save as": "另存为",
    "Save Pool Plan": "保存素材池计划",
    "No pool plans found for this brand yet. Upload one in Manage Pool Plans to continue.": "当前品牌还没有素材池计划。请先在“管理素材池计划”中上传后再继续。",
    "Pool Plan": "素材池计划",
    "Default Ext": "默认格式",
    "Pool Topic": "素材池主题",
    "Workflow continuity: planning defines needs → Pool Fill closes missing coverage with matching clips.": "流程连续性：规划定义需求 → 素材池补充负责用匹配素材补齐缺口。",
    "Download Selected Plan": "下载当前计划",
    "Today’s Intake Brief": "今日采集简报",
    "Best scene to fill:": "当前最该补的场景：",
    "Most urgent slot:": "当前最紧急槽位：",
    "Get Guide": "获取指引",
    "Field reference for crew phone use. Download once and keep it with the shooting board.": "给拍摄人员手机端使用的现场参考。下载一次后可与拍摄任务单配合使用。",
    "Task Board": "任务看板",
    "Open missing slots first. Completed slots are folded to the bottom.": "优先展开缺失槽位。已满足的槽位会折叠到下方。",
    "Filled Slots": "已补齐槽位",
    "These slots already meet target count. Expand only if you want replacements or alternates.": "这些槽位已达到目标数量。只有在需要替换或补充备选时再展开。",

    "Step 3 · Create Video": "步骤 3 · 生成视频",
    "Creates the final video with lightweight run logs and default 60fps output.": "生成最终视频，并保留轻量运行日志；默认输出 60fps。",
    "Create Video": "生成视频",
    "Completed.": "已完成。",
    "Final video created successfully.": "最终视频已成功生成。",
    "Render Failed.": "渲染失败。",
    "Render finished without a final video file. See _internal/render.log for the real failure.": "渲染结束但未生成最终视频文件。真实失败原因请查看 _internal/render.log。",
    "Generate Task Rows in Step 1 first.": "请先在步骤 1 生成任务行。",
}

def tr(text: str) -> str:
    code = str(st.session_state.get("display_lang", "en") or "en")
    if code == "zh":
        return UI_TEXT_ZH.get(text, text)
    return text





def _load_json_list_for_restore(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _restore_project_session_from_generated(company: str) -> bool:
    company = str(company or "").strip()
    if not company:
        return False

    generated_dir = CREATIVE_ROOT / company / "generated"
    if not generated_dir.exists():
        return False

    candidates: list[Path] = []
    active_raw = str(st.session_state.get("active_creative_path", "") or "").strip()
    if active_raw:
        active_path = Path(active_raw).expanduser()
        if generated_dir in active_path.parents or active_path.parent == generated_dir:
            candidates.append(active_path)

    candidates.extend(
        sorted(
            generated_dir.glob("*.creative.yaml"),
            key=lambda pp: pp.stat().st_mtime,
            reverse=True,
        )
    )

    seen: set[str] = set()
    for creative_path in candidates:
        key = str(creative_path.resolve()) if creative_path.exists() else str(creative_path)
        if key in seen:
            continue
        seen.add(key)

        if not creative_path.exists():
            continue

        task_rows_json = creative_path.with_name(f"{creative_path.stem}.shooting_rows.json")
        project_slots_json = creative_path.with_name(f"{creative_path.stem}.project_slots.json")
        task_rows_html = creative_path.with_name(f"{creative_path.stem}.task_rows.html")

        rows = _load_json_list_for_restore(task_rows_json)
        project_slots = _load_json_list_for_restore(project_slots_json)

        if not rows and not project_slots:
            continue

        st.session_state["active_creative_path"] = str(creative_path)
        st.session_state["task_rows_json_path"] = str(task_rows_json)
        st.session_state["project_slots_json_path"] = str(project_slots_json)
        st.session_state["task_rows_html_path"] = str(task_rows_html)

        if rows:
            st.session_state["shooting_rows"] = rows
        if project_slots:
            st.session_state["project_slots"] = project_slots

        return True

    return False


# =========================================================
# Session
# =========================================================
ensure_ui_session_defaults(st.session_state)

# UI_POLISH_CSS_V1
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
               "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
}
h1, h2, h3, h4 {
  letter-spacing: -0.01em;
}
div[data-testid="stMarkdownContainer"] p {
  line-height: 1.52;
}
div[data-testid="stExpander"] details summary p {
  font-weight: 600;
}
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
  border-radius: 10px;
  font-weight: 500;
}
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
  line-height: 1.48;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# Header
# =========================================================
st.markdown(f"## 🎬 {tr('Video Automation Tool')}")
st.markdown(
    "<span class='muted'>" + tr("Workflow: Project Mode (planning & script generation) → Pool Fill Mode (asset coverage and gap closure)") + "</span>",
    unsafe_allow_html=True,
)

if not SRC_MAIN.exists():
    st.error(f"Missing entry: {SRC_MAIN}. Run UI from the project root.")
    st.stop()

# =========================================================
# Sidebar
# =========================================================
input_root = str(INPUT_ROOT_DEFAULT)
input_root_path = Path(input_root)
companies = list_companies()
ui_prefs = load_ui_local_prefs(ROOT)
preferred_company = str(st.session_state.pop("pending_company_select_top", "") or "").strip()
remembered_company = str(ui_prefs.last_company or "").strip()
if preferred_company and preferred_company in companies:
    default_idx = companies.index(preferred_company)
elif remembered_company and remembered_company in companies:
    default_idx = companies.index(remembered_company)
else:
    default_idx = 0 if companies else None

with st.sidebar:
    st.markdown(f"## {tr('Workspace')}")
    st.caption(tr("Global company context for planning, coverage, and export workflows."))

    if companies:
        if preferred_company and preferred_company in companies:
            st.session_state["company_select_top"] = preferred_company
        company = st.selectbox(tr("Current Company"), companies, index=default_idx, key="company_select_top")
        remember_last_company(ROOT, company)
    else:
        company = ""
        st.info("Create your first company workspace to get started.")

    new_brand_name = st.text_input(
        tr("Create Company Workspace"),
        value="",
        placeholder="e.g. Northwind, Blue Harbor, Acme",
        key="create_brand_name_v1_main",
    )

    slug_preview = safe_slug(new_brand_name).lower() if new_brand_name.strip() else ""
    brand_dir_exists = bool(slug_preview) and (ROOT / "data" / "brands" / slug_preview).exists()
    create_disabled = (not new_brand_name.strip()) or (not slug_preview) or brand_dir_exists

    st.caption(f"Slug: {slug_preview or '(waiting)'}")
    if brand_dir_exists:
        st.caption("Status: company workspace already exists")
    elif slug_preview:
        st.caption("Creates managed company folders and starter brand config")

    if st.button(
        tr("Create Company Workspace"),
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
            created_company = new_brand_name.strip()
            st.session_state["pending_company_select_top"] = created_company
            remember_last_company(ROOT, created_company)
            st.session_state["brand_creation_flash_v1"] = msg
            st.rerun()
        else:
            st.warning(msg)

    st.markdown(f"### {tr('Display Language')}")
    display_lang_label = st.selectbox(
        tr("Display Language"),
        ["English", "中文"],
        index=0 if str(st.session_state.get("display_lang", "en") or "en") == "en" else 1,
        key="display_lang_label_top_v1",
        label_visibility="collapsed",
    )
    st.session_state["display_lang"] = "zh" if display_lang_label == "中文" else "en"

    if "work_mode" not in st.session_state:
        st.session_state["work_mode"] = "Script Planning / Project Mode"

    st.markdown(f"### {tr('Workflow')}")
    work_mode = st.radio(
        tr("Current Stage"),
        ["Script Planning / Project Mode", "Shoot Tasks / Coverage / Pool Fill"],
        format_func=tr,
        key="work_mode",
    )
    st.caption(tr("Render / Export becomes available after planning and coverage completion."))

    with st.expander(tr("System Settings"), expanded=False):
        _saved_orient = load_ui_local_prefs(ROOT).last_orientation or "portrait"
        orientation = st.radio(tr("Default Format"), ["portrait", "landscape"], index=0 if _saved_orient == "portrait" else 1, horizontal=True)
        remember_last_orientation(ROOT, orientation)

        st.markdown(f"### {tr('Language')}")
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
        sel = st.selectbox(tr("Global Default Language"), lang_labels, index=0)
        sel_code = dict(zip(lang_labels, [c for _, c in lang_options]))[sel]
        if sel_code == "other":
            lang_code = st.text_input("Custom Language (BCP-47)", value="", placeholder="e.g. zh-CN / en-GB").strip()
        else:
            lang_code = sel_code
        if not lang_code:
            lang_code = "en-US"

        st.markdown(f"### {tr('ElevenLabs')}")
        profile = ensure_default_eleven_profile()
        saved_key = load_eleven_api_key()
        eleven_key = st.text_input(tr("API Key"), value=saved_key, type="password")

        model_id = st.selectbox(
            tr("TTS Model"),
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
            if st.button(tr("Save TTS"), use_container_width=True):
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
            with st.popover(tr("Voice Map")):
                langs = profile.get("languages", {}) if isinstance(profile.get("languages", {}), dict) else {}
                rows_map = [{"lang": k, "voice_id": (v or {}).get("voice_id", "")} for k, v in sorted(langs.items())]
                st.dataframe(rows_map, width="stretch", hide_index=True)

        ai_provider_settings = render_ai_provider_settings(root=ROOT)

        st.markdown(f"### {tr('Output Defaults')}")
        target_fps = get_default_fps()
        filter_preset_name = st.selectbox(tr("Visual Filter"), ["clean", "industrial", "warm_brand"], index=1)
        _ = get_filter_preset(filter_preset_name)
        st.caption(f"FPS: {target_fps}  |  Filter: {filter_preset_name}")

        with st.expander(tr("Advanced"), expanded=False):
            input_root = st.text_input(tr("Footage Root"), value=str(INPUT_ROOT_DEFAULT))
            verbose = st.checkbox(tr("Verbose Logs (Dev)"), value=False)

        if company:
            with st.expander("Danger Zone", expanded=False):
                st.caption("Delete only if you want to remove this company workspace and managed files.")
                deletion_scan = scan_brand_workspace(root=ROOT, company=company, slugify=safe_slug, input_root=Path(input_root))
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
                    deleted_company = company
                    result = delete_brand_workspace(root=ROOT, company=deleted_company, slugify=safe_slug, input_root=Path(input_root))
                    if load_ui_local_prefs(ROOT).last_company == deleted_company:
                        clear_last_company(ROOT)
                    st.success(f"Deleted {len(result['deleted'])} managed path(s).")
                    st.session_state.pop("company_select_top", None)
                    st.rerun()

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

brand_creation_flash = str(st.session_state.pop("brand_creation_flash_v1", "") or "").strip()
if brand_creation_flash:
    st.success(brand_creation_flash)

normalized_work_mode = "Project Mode" if work_mode == "Script Planning / Project Mode" else "Pool Fill Mode"

active_creative_restore_path = Path(st.session_state["active_creative_path"]) if st.session_state.get("active_creative_path") else None
restore_needed = (
    bool(company)
    and (
        active_creative_restore_path is None
        or not active_creative_restore_path.exists()
        or not st.session_state.get("shooting_rows")
        or not st.session_state.get("project_slots")
    )
)
if restore_needed:
    _restore_project_session_from_generated(company)

if company:
    render_brand_validation_checklist(company)
else:
    st.markdown("### Welcome")
    st.info("Create your first company workspace from the sidebar to start your workflow.")
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

# =========================================================
# Pool Fill Mode (independent page)
# =========================================================
if normalized_work_mode == "Pool Fill Mode":
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown(f"## 📦 {tr('Shoot Tasks · Coverage & Missing Assets')}")
    st.caption(tr("Footage gap-closure stage after planning: use pool plans to close missing coverage and complete required assets."))

    if not storage_ready or not factory_dir:
        st.info("Footage storage is unavailable. Pool Fill Mode is currently disabled.")
        st.stop()

    available_pool_plans = list_brand_pool_plans(company)
    pool_plan_flash = ui_pop_flash(st.session_state, "pool_plan_manager_flash_v1")
    if pool_plan_flash:
        st.success(pool_plan_flash)

    with st.expander(tr("Manage Pool Plans"), expanded=False):
        st.caption(tr("Upload the first plan for a new brand, or add / replace plans for the current brand."))

        manage_a, manage_b = st.columns([2, 1])
        with manage_a:
            uploaded_plan_file = st.file_uploader(
                tr("Upload Plan YAML"),
                type=["yaml", "yml"],
                key=f"pool_plan_manager_upload_{safe_slug(company).lower()}",
                help="Upload a YAML pool plan for the current brand.",
            )
        with manage_b:
            plan_name_input = st.text_input(
                tr("Save as"),
                value="",
                placeholder="default / campaign-a / showroom-v2",
                key=f"pool_plan_manager_name_{safe_slug(company).lower()}",
            )

        if st.button(
            tr("Save Pool Plan"),
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
        st.info(tr("No pool plans found for this brand yet. Upload one in Manage Pool Plans to continue."))
        st.stop()

    pool_plan_labels, pool_plan_map = build_pool_plan_label_map(available_pool_plans, POOL_PLAN_DIR)

    ui_ensure_valid_choice(st.session_state, "pool_plan_select_v4", pool_plan_labels)

    toolbar_a, toolbar_b, toolbar_c, toolbar_d = st.columns([1.2, 1.2, 1, 2])
    with toolbar_a:
        selected_plan_label = st.selectbox(tr("Pool Plan"), pool_plan_labels, key="pool_plan_select_v4")
    with toolbar_b:
        ext_choice_pool = st.selectbox(tr("Default Ext"), [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice_pool_v4")
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
        pool_topic = st.selectbox(tr("Pool Topic"), topic_names, key="pool_topic_v4")
    with toolbar_d:
        st.markdown('<div class="top-help"></div>', unsafe_allow_html=True)
        st.caption(tr("Workflow continuity: planning defines needs → Pool Fill closes missing coverage with matching clips."))

        try:
            current_plan_path = pool_plan_map[selected_plan_label]
            st.download_button(
                tr("Download Selected Plan"),
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
        st.markdown(f"#### 📋 {tr('Today’s Intake Brief')}")
        st.markdown(f"📍 **{tr('Best scene to fill:')}** {summary['focus_scene']}")
        st.markdown(f"🔥 **{tr('Most urgent slot:')}** {summary['urgent_label']}")
        st.caption(
            f"Need {summary['total_missing']} more clips · "
            f"Existing {summary['total_existing']} / Target {summary['total_target']}"
        )

        guide_html = DOCS_DIR / "pool_fill_shooting_guide.html"
        guide_a, guide_b = st.columns([1.1, 3.2])
        with guide_a:
            if guide_html.exists():
                st.download_button(
                    tr("Get Guide"),
                    data=guide_html.read_text(encoding="utf-8"),
                    file_name=guide_html.name,
                    mime="text/html",
                    use_container_width=True,
                    key="download_pool_guide_html_inline",
                )
        with guide_b:
            st.caption(tr("Field reference for crew phone use. Download once and keep it with the shooting board."))

    _pool_flash_pf = str(st.session_state.pop("_pool_save_flash", "") or "").strip()
    if _pool_flash_pf:
        st.success(_pool_flash_pf)

    st.markdown(f"### {tr('Task Board')}")
    st.caption(tr("Open missing slots first. Completed slots are folded to the bottom."))

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
        st.markdown(f"### {tr('Filled Slots')}")
        st.caption(tr("These slots already meet target count. Expand only if you want replacements or alternates."))
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
st.markdown(f"## 📝 {tr('Project Planning')}")
st.caption(tr("Pick a planning path: AI Script Planning is the default workflow, and Import Existing Script stays available for manual control."))


if "planning_entry_mode_key" not in st.session_state:
    st.session_state["planning_entry_mode_key"] = "existing" if st.session_state.get("active_creative_path") else "ai"

planning_entry_mode_key = st.radio(
    "planning_entry_mode",
    ["ai", "existing"],
    horizontal=True,
    key="planning_entry_mode_key",
    label_visibility="collapsed",
    format_func=lambda v: tr("✨ AI Script Planning") if v == "ai" else tr("📝 Import Existing Script"),
)

src_mode = "Paste Script YAML"
selected_path: Path | None = None

active_creative_for_ui = Path(st.session_state["active_creative_path"]) if st.session_state.get("active_creative_path") else None
if "src_mode" not in st.session_state:
    st.session_state["src_mode"] = (
        "Use Existing Script YAML"
        if active_creative_for_ui and active_creative_for_ui.exists()
        else "Paste Script YAML"
    )

generate_ready = False
generate_help = ""

if planning_entry_mode_key == "ai":
    render_ai_script_entry_panel(
        root=ROOT,
        company=company,
        orientation=orientation,
        global_language=lang_code,
        provider_settings=ai_provider_settings,
    )
    with st.expander(tr("Manual YAML fallback (optional)"), expanded=False):
        st.caption(tr("Use this only when you intentionally want to import or paste an existing script."))
        st.session_state["creative_draft"] = st.text_area(
            tr("Script YAML"),
            value=st.session_state.get("creative_draft", ""),
            height=180,
            placeholder="Paste your Creative Script YAML here…",
            label_visibility="collapsed",
            key="script_yaml_ai_fallback_v1",
        )
    draft_text = str(st.session_state.get("creative_draft", "") or "").strip()
    generate_ready = bool(draft_text)
    generate_help = tr("Paste script YAML to generate task rows.")
else:
    src_mode = st.selectbox(
        tr("Manual Script Source"),
        ["Paste Script YAML", "Use Existing Script YAML"],
        key="src_mode",
        format_func=tr,
    )
    if src_mode == "Paste Script YAML":
        st.session_state["creative_draft"] = st.text_area(
            tr("Script YAML"),
            value=st.session_state.get("creative_draft", ""),
            height=180,
            placeholder="Paste your Creative Script YAML here…",
            label_visibility="collapsed",
            key="script_yaml_manual_v1",
        )
    else:
        creative_dir = CREATIVE_ROOT / company
        creative_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(creative_dir.rglob("*.yaml"))
        if not files:
            st.warning("No script YAML files were found for this company.")
        else:
            if (
                active_creative_for_ui
                and active_creative_for_ui.exists()
                and active_creative_for_ui in files
                and "select_yaml" not in st.session_state
            ):
                st.session_state["select_yaml"] = active_creative_for_ui

            selected_path = st.selectbox(
                tr("Select Script YAML"),
                files,
                format_func=lambda pp: pp.name,
                key="select_yaml",
            )
            st.caption(tr("The selected script will be used as-is."))

    draft_text = str(st.session_state.get("creative_draft", "") or "").strip()
    if src_mode == "Use Existing Script YAML":
        generate_ready = selected_path is not None
        generate_help = tr("Select an existing script YAML to generate task rows.")
    else:
        generate_ready = bool(draft_text)
        generate_help = tr("Paste script YAML to generate task rows.")

action_a, action_b, action_c = st.columns([1, 1, 1])
with action_a:
    generate_btn = st.button(
        tr("Generate Task Rows"),
        use_container_width=True,
        key="generate_tasks",
        disabled=not generate_ready,
        help=generate_help,
    )
with action_b:
    compact_view = st.checkbox(tr("Compact View"), value=True, key="compact_view")
with action_c:
    reload_project_btn = st.button(
        "重新载入当前项目" if str(st.session_state.get("display_lang", "en") or "en") == "zh" else "Reload Current Project",
        use_container_width=True,
        key="reload_current_project_v1",
        disabled=not bool(company),
    )
export_html = st.checkbox(tr("Export Printable HTML"), value=True, key="export_html")

if reload_project_btn:
    restored = _restore_project_session_from_generated(company)
    if restored:
        st.success("已重新载入当前项目。" if str(st.session_state.get("display_lang", "en") or "en") == "zh" else "Current project reloaded.")
        st.rerun()
    else:
        st.warning("未找到可恢复的项目产物。" if str(st.session_state.get("display_lang", "en") or "en") == "zh" else "No restorable project artifacts were found.")

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
            project_slug = safe_slug(project) or safe_slug(name_seed) or "script"
            generated_dir = CREATIVE_ROOT / company / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)

            content_hash = hashlib.sha1(creative_text.encode("utf-8")).hexdigest()[:10]
            creative_path = generated_dir / f"{project_slug}_{content_hash}.creative.yaml"
            if not creative_path.exists():
                creative_path.write_text(creative_text, encoding="utf-8")

            st.session_state["active_creative_path"] = str(creative_path)
            st.session_state["run_dir"] = ""

            task_rows_json = generated_dir / f"{creative_path.stem}.shooting_rows.json"
            task_rows_html = generated_dir / f"{creative_path.stem}.task_rows.html"
            project_slots_json = generated_dir / f"{creative_path.stem}.project_slots.json"
            st.session_state["task_rows_json_path"] = str(task_rows_json)
            st.session_state["task_rows_html_path"] = str(task_rows_html)
            st.session_state["project_slots_json_path"] = str(project_slots_json)

            project_slots = build_project_slots_from_creative(d)

            beats = beats_from_creative(d)
            _beat_durations = {}
            for _bi, _beat in enumerate(beats, start=1):
                _beat_durations[_bi] = _beat.get("duration_hint")

            rows: list[dict] = []
            row_i = 1
            for _slot in project_slots:
                _beat_no = int(_slot.get("beat_no", 0) or 0)
                _dur = _beat_durations.get(_beat_no)
                _repeat = max(1, int(_slot.get("target", 1) or 1))
                for _ in range(_repeat):
                    rows.append({
                        "Row": f"S{row_i:03d}",
                        "Beat": _beat_no,
                        "Category": str(_slot.get("content", "") or "").strip(),
                        "Scene": str(_slot.get("scene", "") or "").strip(),
                        "Shot": str(_slot.get("coverage", "") or "").strip(),
                        "Seconds": str(_dur) if _dur else "3",
                        "Movement": str(_slot.get("move", "static") or "static").strip(),
                        "Notes": str(_slot.get("shoot_brief", "") or "").strip(),
                        "BeatPurpose": str(_slot.get("beat_purpose", "") or "").strip(),
                    })
                    row_i += 1
            st.session_state["shooting_rows"] = rows
            st.session_state["project_slots"] = project_slots
            task_rows_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            project_slots_json.write_text(json.dumps(project_slots, ensure_ascii=False, indent=2), encoding="utf-8")

            if export_html:
                task_rows_html.write_text(render_html_task_table(rows), encoding="utf-8")
            elif task_rows_html.exists():
                task_rows_html.unlink()

            st.success(f"Generated {len(rows)} task rows.")
            st.caption(f"Script File: {creative_path}")
            st.caption(f"Task Rows File: {task_rows_json}")

rows = st.session_state.get("shooting_rows") or []
project_slots = st.session_state.get("project_slots") or []
task_rows_html_path = Path(st.session_state["task_rows_html_path"]) if st.session_state.get("task_rows_html_path") else None

if rows:
    if storage_ready and factory_dir:
        if project_slots:
            _mf = list_video_files(factory_dir, VIDEO_SUFFIXES)
            _sr = build_pool_slot_rows(project_slots, _mf)
            _sm = summarize_pool_slot_rows(_sr)
            total_need = _sm["total_target"]
            total_ready = _sm["total_existing"]
            total_missing = _sm["total_missing"]
        else:
            coverage = summarize_factory_coverage(rows, factory_dir)
            total_need = coverage["total_need"]
            total_ready = coverage["total_ready"]
            total_missing = coverage["total_missing"]
    else:
        total_need = len(rows)
        total_ready = 0
        total_missing = total_need

    m1, m2, m3 = st.columns([1, 1, 1])
    m1.metric(tr("Total Shots"), total_need)
    m2.metric(tr("Ready"), total_ready)
    m3.metric(tr("Missing"), total_missing)

    with st.expander(tr("How the current demo categories work"), expanded=False):
        st.markdown(
            "- **Exterior / Product Hero** = opening / closing hero visuals\n"
            "- **Factory Process** = production, automation, workflow coverage\n"
            "- **Hero / Establishing** = strongest opening or closing visual\n"
            "- **Medium Shot** = stable process support visual\n"
            "- **Detail Close-up** = machine, hand, control, or inspection detail"
        )

    show_cols = (
        ["Row", "Scene", "Shot", "Seconds", "Movement", "Notes"]
        if compact_view
        else ["Row", "Beat", "Category", "Scene", "Shot", "Seconds", "Movement", "Notes"]
    )

    display_rows = []
    for r in rows:
        row_view = {k: r.get(k, "") for k in show_cols}
        if "Category" in row_view:
            row_view["Category"] = {
                "building": "Exterior / Product Hero" if str(st.session_state.get("display_lang", "en") or "en") != "zh" else "外景 / 产品 Hero",
                "line": "Factory Process" if str(st.session_state.get("display_lang", "en") or "en") != "zh" else "工厂流程",
            }.get(str(r.get("Category", "")).strip().lower(), str(r.get("Category", "")).replace("_", " ").title())
        if "Shot" in row_view:
            row_view["Shot"] = {
                "hero": "Hero / Establishing" if str(st.session_state.get("display_lang", "en") or "en") != "zh" else "Hero / 建立镜头",
                "medium": "Medium Shot" if str(st.session_state.get("display_lang", "en") or "en") != "zh" else "中景",
                "detail": "Detail Close-up" if str(st.session_state.get("display_lang", "en") or "en") != "zh" else "细节近景",
                "wide": "Wide / Establishing" if str(st.session_state.get("display_lang", "en") or "en") != "zh" else "大全景 / 建立镜头",
            }.get(str(r.get("Shot", "")).strip().lower(), str(r.get("Shot", "")).replace("_", " ").title())
        label_map = {
            "Row": tr("Row"),
            "Beat": tr("Beat"),
            "Category": tr("Category"),
            "Scene": tr("Scene"),
            "Shot": tr("Shot"),
            "Seconds": tr("Seconds"),
            "Movement": tr("Movement"),
            "Notes": tr("Notes"),
        }
        row_view = {label_map.get(k, k): v for k, v in row_view.items()}
        display_rows.append(row_view)

    st.dataframe(display_rows, width="stretch", hide_index=True)

    if task_rows_html_path and task_rows_html_path.exists():
        st.download_button(
            tr("Download Printable HTML"),
            data=task_rows_html_path.read_text(encoding="utf-8"),
            file_name=task_rows_html_path.name,
            mime="text/html",
            use_container_width=True,
        )

# =========================================================
# Project Mode · Step 2
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown(f"## 🎞️ {tr('Step 2 · Footage Board')}")
st.caption(tr("Project-driven intake. Missing task slots can be filled by upload or inbox transfer."))

_pool_flash = str(st.session_state.pop("_pool_save_flash", "") or "").strip()
if _pool_flash:
    st.success(_pool_flash)

if not storage_ready or not inbox_dir or not factory_dir:
    st.info("Footage storage is unavailable. Step 2 is currently disabled.")
elif project_slots:
    auto_use_factory = st.checkbox(tr("Auto-match Existing Factory Footage"), value=True, key="auto_use_factory")
    show_matches = st.checkbox(tr("Show Matched Filenames"), value=False, key="show_matches")
    ext_choice = st.selectbox(tr("Default Upload Extension"), [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice")

    factory_files = list_video_files(factory_dir, VIDEO_SUFFIXES)
    inbox_files = list_video_files(inbox_dir, VIDEO_SUFFIXES)

    beats_map: dict[int, list[dict]] = {}
    for r in rows:
        beats_map.setdefault(int(r["Beat"]), []).append(r)

    with st.expander(tr("Factory Asset Index Preview"), expanded=False):
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

    with st.expander(tr("Edit Asset Soft Tags"), expanded=False):
        editable_items = load_asset_index(factory_dir / "asset_index.json")
        if not editable_items:
            st.info("No indexed factory assets yet.")
        else:
            selected_filename = st.selectbox(
                tr("Asset"),
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

                if st.button(tr("Save Asset Tags"), key="save_asset_tags"):
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

                    st.markdown("---")
                    st.caption(tr("Factory file actions"))

                    current_asset_path = factory_dir / selected_filename
                    current_content = str(selected_item.get("content", "line") or "line")
                    current_coverage = str(selected_item.get("coverage", "medium") or "medium")
                    current_move = str(selected_item.get("move", "static") or "static")

                    content_options = ["building", "line"]
                    coverage_options = ["hero", "medium", "detail"]
                    move_options = MOVE_TOKEN_OPTIONS

                    c_move_1, c_move_2, c_move_3 = st.columns(3)
                    with c_move_1:
                        reclass_content = st.selectbox(
                            tr("Move to content"),
                            content_options,
                            index=content_options.index(current_content) if current_content in content_options else 1,
                            key=f"reclass_content_{safe_slug(selected_filename)}",
                        )
                    with c_move_2:
                        reclass_coverage = st.selectbox(
                            tr("Move to coverage"),
                            coverage_options,
                            index=coverage_options.index(current_coverage) if current_coverage in coverage_options else 1,
                            key=f"reclass_coverage_{safe_slug(selected_filename)}",
                        )
                    with c_move_3:
                        reclass_move = st.selectbox(
                            tr("Move token"),
                            move_options,
                            index=move_options.index(current_move) if current_move in move_options else 0,
                            key=f"reclass_move_{safe_slug(selected_filename)}",
                        )

                    action_c1, action_c2 = st.columns(2)

                    with action_c1:
                        if st.button(tr("Reclassify / Rename Asset"), key=f"reclassify_asset_{safe_slug(selected_filename)}"):
                            if not current_asset_path.exists():
                                st.error(f"Asset file not found: {selected_filename}")
                            else:
                                ext = current_asset_path.suffix.lower() or ".mp4"
                                next_idx = next_index_for(factory_dir, "factory", reclass_content, reclass_coverage, reclass_move, ext)
                                new_name = build_factory_filename("factory", reclass_content, reclass_coverage, reclass_move, next_idx, ext)
                                dst = factory_dir / new_name
                                if dst.exists():
                                    dst = factory_dir / f"{Path(new_name).stem}_{now_tag()}{ext}"

                                current_asset_path.rename(dst)

                                index_path = factory_dir / "asset_index.json"
                                records = load_asset_index(index_path)
                                updated_records = []
                                replaced = False
                                for rec in records:
                                    if str(rec.get("filename", "")) == selected_filename:
                                        new_rec = dict(rec)
                                        new_rec["filename"] = dst.name
                                        new_rec["scene"] = "factory"
                                        new_rec["content"] = reclass_content
                                        new_rec["coverage"] = reclass_coverage
                                        new_rec["move"] = reclass_move
                                        updated_records.append(new_rec)
                                        replaced = True
                                    else:
                                        updated_records.append(rec)

                                if not replaced:
                                    updated_records.append(
                                        {
                                            "filename": dst.name,
                                            "scene": "factory",
                                            "content": reclass_content,
                                            "coverage": reclass_coverage,
                                            "move": reclass_move,
                                        }
                                    )

                                index_path.write_text(json.dumps(updated_records, ensure_ascii=False, indent=2), encoding="utf-8")
                                upsert_asset_record(index_path, dst)

                                st.success(f"Moved {selected_filename} → {dst.name}")
                                st.rerun()

                    with action_c2:
                        if st.button(tr("Delete Asset"), type="secondary", key=f"delete_asset_{safe_slug(selected_filename)}"):
                            if not current_asset_path.exists():
                                st.error(f"Asset file not found: {selected_filename}")
                            else:
                                current_asset_path.unlink()

                                index_path = factory_dir / "asset_index.json"
                                records = load_asset_index(index_path)
                                updated_records = [
                                    rec for rec in records
                                    if str(rec.get("filename", "")) != selected_filename
                                ]
                                index_path.write_text(json.dumps(updated_records, ensure_ascii=False, indent=2), encoding="utf-8")

                                st.success(f"Deleted {selected_filename}")
                                st.rerun()

    slot_rows = build_pool_slot_rows(project_slots, factory_files)
    slot_rows = merge_pool_semantic_fields(slot_rows, project_slots)

    for row in slot_rows:
        display_label = str(row.get("human_label", "") or row.get("slot_label", "") or "Slot").strip()
        slot_label_text = str(row.get("canonical_slot_label", "") or row.get("slot_label", "") or "").strip()
        scene_text = str(row.get("scene", "") or "").strip()
        content_text = str(row.get("content", "") or "").strip()
        coverage_text = str(row.get("coverage", "") or "").strip()
        move_text = str(row.get("move", "") or "static").strip() or "static"

        row["display_label"] = display_label
        row["slot_label_text"] = slot_label_text
        row["canonical_tuple_text"] = f"`{scene_text} · {content_text} · {coverage_text} · {move_text}`"
        row["registry_key_text"] = str(row.get("registry_key", "") or "").strip()
        row["shoot_brief_text"] = str(row.get("shoot_brief", "") or "").strip()

    beat_groups: dict[int, list[dict]] = {}
    for row in slot_rows:
        beat_no = int(row.get("beat_no", 0) or 0)
        if beat_no > 0:
            beat_groups.setdefault(beat_no, []).append(row)

    ordered_beat_nos = sorted(beat_groups.keys())

    first_missing_beat = None
    for _beat_no in ordered_beat_nos:
        _rows = beat_groups.get(_beat_no, [])
        if any(int(rr.get("missing", 0) or 0) > 0 for rr in _rows):
            first_missing_beat = _beat_no
            break

    if "project_step2_focus_beat" not in st.session_state:
        st.session_state["project_step2_focus_beat"] = str(first_missing_beat or (ordered_beat_nos[0] if ordered_beat_nos else "all"))

    valid_focus_values = {"all"} | {str(x) for x in ordered_beat_nos}
    if str(st.session_state.get("project_step2_focus_beat", "all")) not in valid_focus_values:
        st.session_state["project_step2_focus_beat"] = str(first_missing_beat or (ordered_beat_nos[0] if ordered_beat_nos else "all"))

    focus_label = "当前编辑 Beat" if str(st.session_state.get("display_lang", "en") or "en") == "zh" else "Current Editing Beat"
    focus_options = ["all"] + [str(x) for x in ordered_beat_nos]
    selected_focus = st.selectbox(
        focus_label,
        focus_options,
        key="project_step2_focus_beat",
        format_func=lambda v: (
            ("全部 Beat" if str(st.session_state.get("display_lang", "en") or "en") == "zh" else "All Beats")
            if v == "all"
            else f"Beat {v}"
        ),
    )

    for beat_no in ordered_beat_nos:
        beat_slot_rows = sort_pool_slot_rows(beat_groups[beat_no])
        beat_purpose = str(beat_slot_rows[0].get("beat_purpose", "") or "").strip().lower()
        request_family = str(beat_slot_rows[0].get("request_family", "") or "").strip().lower()

        beat_label = tr({
            "establish_context": "Opening Context",
            "show_capability": "Capability",
            "build_trust": "Trust / Proof",
            "brand_close": "Brand Close",
        }.get(beat_purpose, beat_purpose.replace("_", " ").title() or f"Beat {beat_no}"))

        beat_hint = {
            "opening": "Upload opening context: exterior, entrance, showroom, headquarters, or a clean overall establishing visual. Avoid fragmented close details.",
            "capability": "Upload process visuals: machine action, workflow medium shots, and clear operating details. Avoid empty exterior-only shots.",
            "trust": "Upload proof visuals: inspection, testing, certificates, achievements, or stable support detail. Avoid flashy or overly busy motion.",
            "close": "Upload the strongest final hero visual: clean, stable, complete, and suitable for closing. Avoid fragmented detail shots.",
        }.get(request_family, "Upload visuals that clearly support this beat.")

        with st.expander(
            f"Beat {beat_no} · {beat_label}",
            expanded=(selected_focus == "all" and beat_no == (first_missing_beat or (ordered_beat_nos[0] if ordered_beat_nos else beat_no))) or (selected_focus == str(beat_no)),
        ):
            if beat_hint:
                st.caption(tr(beat_hint))

            active_slot_rows = [r for r in beat_slot_rows if int(r.get("missing", 0)) > 0]
            completed_slot_rows = [r for r in beat_slot_rows if int(r.get("missing", 0)) <= 0]

            for i, row in enumerate(active_slot_rows):
                render_pool_active_slot_card(
                    row=row,
                    pool_topic=f"project_beat_{beat_no}",
                    i=i,
                    factory_dir=factory_dir,
                    ext_choice_pool=ext_choice,
                    inbox_dir=inbox_dir,
                    orientation=orientation,
                )
                st.write("")

            if completed_slot_rows:
                st.caption(tr("Ready slots"))
                for j, row in enumerate(completed_slot_rows):
                    render_pool_completed_slot_card(
                        row=row,
                        pool_topic=f"project_beat_{beat_no}_done",
                        i=j,
                        factory_dir=factory_dir,
                        ext_choice_pool=ext_choice,
                    )

# =========================================================
# Project Mode · Step 3
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown(f"## 🚀 {tr('Step 3 · Create Video')}")
st.caption(tr("Creates the final video with lightweight run logs and default 60fps output."))

active_creative_path = Path(st.session_state["active_creative_path"]) if st.session_state.get("active_creative_path") else None

if not storage_ready:
    st.info("Footage storage is unavailable. Step 3 is currently disabled.")
elif not (active_creative_path and active_creative_path.exists()):
    st.info(tr("Generate Task Rows in Step 1 first."))
else:
    if st.button(tr("Create Video"), use_container_width=True, key="create_video"):
        progress = st.progress(0)
        status = st.empty()

        try:
            creative_name = active_creative_path.stem.replace(".creative", "")
            run_id = f"{creative_name}_{now_tag()[:15]}"
            run_dir = output_root_path / orientation / company / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            layout = ensure_run_layout(run_dir)
            internal_dir = layout["internal_dir"]

            st.session_state["run_dir"] = str(run_dir)

            status.markdown("**Preparing Workflow…**")
            progress.progress(10)

            run_env = dict(ENV)
            run_env["VIDEO_AUTOMATION_RUN_DIR"] = str(run_dir)
            run_env["VIDEO_AUTOMATION_ORIENTATION"] = str(orientation)
            run_env["VIDEO_AUTOMATION_LANG"] = str(lang_code)
            run_env["VIDEO_AUTOMATION_MODEL"] = str(model_id)
            run_env["VIDEO_AUTOMATION_FILTER_PRESET"] = str(filter_preset_name)
            run_env["VIDEO_AUTOMATION_ELEVEN_PROFILE_PATH"] = str(ELEVEN_PROFILE_PATH)

            status.markdown("**Preparing Render Plan…**")
            progress.progress(35)

            status.markdown("**Rendering Final Video…**")
            progress.progress(70)

            cmd_run = [sys.executable, str(SRC_MAIN)]
            if "verbose" in locals() and verbose:
                cmd_run.append("-v")
            cmd_run += ["run", "--company", company, "--script", str(active_creative_path), "--input", str(input_root_path)]

            rc2, render_logs = run_cmd_silent(cmd_run, run_env)
            (internal_dir / "render.log").write_text(render_logs, encoding="utf-8")

            if rc2 != 0:
                progress.progress(100)

                preflight_summary = None
                for line in render_logs.splitlines():
                    if "Timing preflight failed:" in line:
                        preflight_summary = line.split("Timing preflight failed:", 1)[1].strip()
                        break

                if preflight_summary:
                    status.markdown("**Timing Preflight Blocked Video Creation.**")
                    st.error(f"Timing preflight blocked video creation: {preflight_summary}")
                    st.info("Shorten narration or increase visual timing, then try again.")
                else:
                    st.error("Video rendering failed. See _internal/render.log in the Run Folder.")

                raise SystemExit(0)

            rendered_mp4s = sorted([pp for pp in run_dir.iterdir() if pp.is_file() and pp.suffix.lower() == ".mp4"])
            if not rendered_mp4s:
                progress.progress(100)
                status.markdown(f"**{tr('Render Failed.')}**")
                st.error(tr("Render finished without a final video file. See _internal/render.log for the real failure."))
                raise SystemExit(0)

            status.markdown(f"**{tr('Completed.')}**")
            progress.progress(100)
            st.success(tr("Final video created successfully."))

        except SystemExit:
            pass
        except Exception as e:
            progress.progress(100)
            st.error(f"Unexpected Error: {e}")

