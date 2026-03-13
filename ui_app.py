#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
import yaml

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

def load_pool_plan(company: str) -> dict:
    path = POOL_PLAN_DIR / f"{str(company).strip().lower()}.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

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

def list_companies(input_root: Path) -> list[str]:
    names = set()
    if CREATIVE_ROOT.exists():
        names.update([p.name for p in CREATIVE_ROOT.iterdir() if p.is_dir()])
    for ori in ("portrait", "landscape"):
        ori_root = input_root / ori
        if ori_root.exists():
            names.update([p.name for p in ori_root.iterdir() if p.is_dir()])
    return sorted([x for x in names if x.strip()])

# =========================================================
# Session
# =========================================================
st.session_state.setdefault("active_creative_path", None)
st.session_state.setdefault("creative_draft", "")
st.session_state.setdefault("run_dir", None)
st.session_state.setdefault("shooting_rows", [])
st.session_state.setdefault("compiled_out_path", None)
st.session_state.setdefault("work_mode", "Project Mode")

# =========================================================
# Header
# =========================================================
st.markdown("## 🎬 Video Automation Tool")
st.markdown(
    "<span class='muted'>Project Mode: script → tasks → render · Pool Fill Mode: plan-driven asset intake</span>",
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
default_idx = companies.index("Siglen") if "Siglen" in companies else (0 if companies else None)

top_a, top_b = st.columns([1, 1])
with top_a:
    company = st.selectbox("Company", companies, index=default_idx, key="company_select_top")
with top_b:
    work_mode = st.radio(
        "Work Mode",
        ["Project Mode", "Pool Fill Mode"],
        horizontal=True,
        key="work_mode",
    )

# =========================================================
# Storage
# =========================================================
storage_ready = True
storage_error = ""

try:
    if input_root_path.exists() and not input_root_path.is_dir():
        storage_ready = False
        storage_error = f"Footage root exists but is not a directory: {input_root_path}"
    else:
        ensure_company_storage(input_root_path, company)
except Exception as e:
    storage_ready = False
    storage_error = str(e)

dirs = get_storage_dirs(input_root_path, orientation, company) if storage_ready else {}
inbox_dir = dirs.get("inbox") if dirs else None
factory_dir = dirs.get("factory") if dirs else None

if not storage_ready:
    st.warning("Footage storage is unavailable. You can still edit scripts and settings, but footage actions are disabled.")
    st.caption(f"Footage Root: {input_root_path}")
    if storage_error:
        st.caption(f"Reason: {storage_error}")

# =========================================================
# Pool Fill Mode (independent page)
# =========================================================
if work_mode == "Pool Fill Mode":
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("## Pool Fill Mode")
    st.info(
        "Use this page to build the reusable footage pool. "
        "Choose a topic, inspect missing slots, then upload clips directly into the matching slot. "
        "The system will auto-name files and update the asset index."
    )

    if not storage_ready or not factory_dir:
        st.info("Footage storage is unavailable. Pool Fill Mode is currently disabled.")
        st.stop()

    pool_plan = load_pool_plan(company)
    if not pool_plan:
        st.error(f"No pool plan found for {company}. Expected: data/pool_plans/{str(company).lower()}.yaml")
        st.stop()

    topics = pool_plan.get("topics", []) if isinstance(pool_plan.get("topics"), list) else []
    topic_names = [str(t.get("name", "")) for t in topics if isinstance(t, dict) and str(t.get("name", "")).strip()]
    if not topic_names:
        st.error("Pool plan has no valid topics.")
        st.stop()

    toolbar_a, toolbar_b, toolbar_c = st.columns([1, 1, 2])
    with toolbar_a:
        pool_topic = st.selectbox("Pool Topic", topic_names, key="pool_topic_v2")
    with toolbar_b:
        ext_choice_pool = st.selectbox("Default Ext", [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice_pool")
    with toolbar_c:
        st.markdown('<div class="top-help"></div>', unsafe_allow_html=True)
        st.caption("Workflow: choose topic → inspect missing slots → upload matching clips → system auto-names + auto-indexes.")

    factory_files = list_video_files(factory_dir, VIDEO_SUFFIXES)

    selected_topic = None
    for topic in topics:
        if isinstance(topic, dict) and str(topic.get("name", "")) == pool_topic:
            selected_topic = topic
            break

    slots = selected_topic.get("slots", []) if isinstance(selected_topic, dict) and isinstance(selected_topic.get("slots"), list) else []

    summary_rows = []
    total_target = 0
    total_existing = 0
    total_missing = 0

    for slot in slots:
        scene_name = str(slot.get("scene", "")).strip()
        content_name = str(slot.get("content", "")).strip()
        coverage_name = str(slot.get("coverage", "")).strip()
        move_name = str(slot.get("move", "")).strip()
        target = int(slot.get("target", 0) or 0)
        priority = str(slot.get("priority", "medium") or "medium")

        existing = count_pool_matches(factory_files, scene_name, content_name, coverage_name, move_name)
        missing = max(0, target - existing)

        total_target += target
        total_existing += existing
        total_missing += missing

        summary_rows.append(
            {
                "priority": priority,
                "scene": scene_name,
                "content": content_name,
                "coverage": coverage_name,
                "move": move_name,
                "target": target,
                "existing": existing,
                "missing": missing,
            }
        )

    m1, m2, m3 = st.columns(3)
    m1.metric("Target clips", total_target)
    m2.metric("Existing clips", total_existing)
    m3.metric("Missing clips", total_missing)

    st.markdown("### Slot Summary")
    st.dataframe(summary_rows, width="stretch", hide_index=True)

    st.markdown("### Capture Sheet")
    st.caption("Screenshot-friendly shooting board. Focus on high-priority slots with the biggest gaps first.")

    sorted_slots = sorted(
        slots,
        key=lambda slot: (
            0 if str(slot.get("priority", "medium")).lower() == "high" else
            1 if str(slot.get("priority", "medium")).lower() == "medium" else 2,
            str(slot.get("scene", "")),
            str(slot.get("content", "")),
            str(slot.get("coverage", "")),
        ),
    )

    compact_rows = []
    for slot in sorted_slots:
        scene_name = str(slot.get("scene", "")).strip()
        content_name = str(slot.get("content", "")).strip()
        coverage_name = str(slot.get("coverage", "")).strip()
        move_name = str(slot.get("move", "")).strip()
        target = int(slot.get("target", 0) or 0)
        priority = str(slot.get("priority", "medium") or "medium")

        existing = count_pool_matches(factory_files, scene_name, content_name, coverage_name, move_name)
        missing = max(0, target - existing)

        compact_rows.append(
            {
                "Priority": priority_badge(priority),
                "Slot": slot_display_name(scene_name, content_name, coverage_name, move_name),
                "Target": target,
                "Existing": existing,
                "Missing": missing,
                "Duration": recommended_duration_for_slot(coverage_name, move_name),
                "Move": movement_guidance(move_name),
                "Framing": composition_guidance(scene_name, content_name, coverage_name),
            }
        )

    st.dataframe(compact_rows, width="stretch", hide_index=True)

    st.markdown("### Upload by Slot")
    st.caption("Open the matching slot below and upload clips directly. Files will be auto-named and indexed.")

    for i, slot in enumerate(sorted_slots):
        scene_name = str(slot.get("scene", "")).strip()
        content_name = str(slot.get("content", "")).strip()
        coverage_name = str(slot.get("coverage", "")).strip()
        move_name = str(slot.get("move", "")).strip()
        target = int(slot.get("target", 0) or 0)
        priority = str(slot.get("priority", "medium") or "medium")
        defaults = slot.get("defaults", {}) if isinstance(slot.get("defaults"), dict) else {}

        existing = count_pool_matches(factory_files, scene_name, content_name, coverage_name, move_name)
        missing = max(0, target - existing)

        default_energy = str(defaults.get("energy", "medium") or "medium")
        default_quality = str(defaults.get("quality_status", "approved") or "approved")
        default_group = str(defaults.get("continuity_group", "") or "")
        default_intro = bool(defaults.get("intro_safe", False))
        default_hero = bool(defaults.get("hero_safe", False))
        default_outro = bool(defaults.get("outro_safe", False))

        with st.expander(
            f"{priority_badge(priority)} · {slot_display_name(scene_name, content_name, coverage_name, move_name)} · missing {missing}",
            expanded=(missing > 0 and priority == "high"),
        ):
            head1, head2, head3, head4 = st.columns(4)
            head1.metric("Target", target)
            head2.metric("Existing", existing)
            head3.metric("Missing", missing)
            head4.write(f"**{recommended_duration_for_slot(coverage_name, move_name)}**  \n{movement_guidance(move_name)}")

            uploads = st.file_uploader(
                "Upload clips for this slot",
                type=VIDEO_EXTS,
                accept_multiple_files=True,
                key=f"pool_fill_v2_upload_{pool_topic}_{i}",
            )

            meta1, meta2 = st.columns([1, 1])
            with meta1:
                energy_default = st.selectbox(
                    "energy",
                    ["low", "medium", "high"],
                    index=["low", "medium", "high"].index(default_energy) if default_energy in ["low", "medium", "high"] else 1,
                    key=f"pool_fill_v2_energy_{pool_topic}_{i}",
                )
                quality_default = st.selectbox(
                    "quality_status",
                    ["approved", "review", "reject"],
                    index=["approved", "review", "reject"].index(default_quality) if default_quality in ["approved", "review", "reject"] else 0,
                    key=f"pool_fill_v2_quality_{pool_topic}_{i}",
                )
            with meta2:
                continuity_group_default = st.text_input(
                    "continuity_group",
                    value=default_group,
                    key=f"pool_fill_v2_group_{pool_topic}_{i}",
                )
                notes_default = st.text_input(
                    "notes",
                    value="",
                    key=f"pool_fill_v2_notes_{pool_topic}_{i}",
                )

            t1, t2, t3 = st.columns(3)
            with t1:
                intro_safe_default = st.checkbox("intro_safe", value=default_intro, key=f"pool_fill_v2_intro_{pool_topic}_{i}")
            with t2:
                hero_safe_default = st.checkbox("hero_safe", value=default_hero, key=f"pool_fill_v2_hero_{pool_topic}_{i}")
            with t3:
                outro_safe_default = st.checkbox("outro_safe", value=default_outro, key=f"pool_fill_v2_outro_{pool_topic}_{i}")

            if st.button("Save to Pool", key=f"pool_fill_v2_save_{pool_topic}_{i}"):
                if not uploads:
                    st.warning("Please upload at least one clip.")
                else:
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

                    st.success("Saved to pool.")
                    st.rerun()

    st.stop()

# =========================================================
# Project Mode · Step 1
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 1 · Creative Script → Task Rows")
st.caption("Use this mode when you already have a script and want task rows + final rendering.")

src_mode = st.selectbox("Script Source", ["Paste Script YAML", "Use Existing Script YAML"], key="src_mode")
colA, colB = st.columns([2, 1])

selected_path: Path | None = None
with colA:
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
    generate_btn = st.button("Generate Task Rows", width="stretch", key="generate_tasks")
    compact_view = st.checkbox("Compact View", value=True, key="compact_view")
    export_html = st.checkbox("Export Printable HTML", value=True, key="export_html")

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
