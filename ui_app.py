#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path
import re

import streamlit as st

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
)

ROOT = Path(__file__).resolve().parent
SRC_MAIN = ROOT / "src" / "main.py"
CREATIVE_ROOT = ROOT / "creative_scripts"
INPUT_ROOT_DEFAULT = ROOT / "input_videos"
OUTPUT_ROOT_DEFAULT = ROOT / "output_videos"
TTS_PROFILE_DIR = ROOT / "data" / "tts_profiles"
ELEVEN_PROFILE_PATH = TTS_PROFILE_DIR / "elevenlabs.json"
ELEVEN_SECRETS_PATH = TTS_PROFILE_DIR / "elevenlabs_secrets.json"
VIDEO_EXTS = ["mp4", "mov", "mkv", "m4v"]
VIDEO_SUFFIXES = ["." + e for e in VIDEO_EXTS]

st.set_page_config(page_title="Video Automation Tool", layout="wide")
st.markdown("""
<style>
.divider { margin: 1.1rem 0 1rem 0; border-bottom: 1px solid rgba(0,0,0,0.08); }
.muted { color: rgba(0,0,0,0.55); }
.tiny { color: rgba(0,0,0,0.55); font-size: 0.9rem; }
code { white-space: pre-wrap !important; }
</style>
""", unsafe_allow_html=True)

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
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
    preset_ids = {"en": "21m00Tcm4TlvDq8ikWAM", "fr": "onwK4e9ZLuTAKqWW03F9", "es": "ErXwobaYiN019PkySvjV", "ru": "nPczCjzI2devNBz1zQrb", "ar": "N2lVS1w4EtoT3dr4eOWO"}
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
    p = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
    lines = []
    if p.stdout:
        for line in p.stdout:
            lines.append(line.rstrip())
            if len(lines) > 800:
                lines = lines[-800:]
    rc = p.wait() or 0
    return rc, "\n".join(lines)

st.session_state.setdefault("active_creative_path", None)
st.session_state.setdefault("creative_draft", "")
st.session_state.setdefault("run_dir", None)
st.session_state.setdefault("shooting_rows", [])
st.session_state.setdefault("compiled_out_path", None)

st.markdown("## 🎬 Video Automation Tool")
st.markdown("<span class='muted'>Step 1: Script → Tasks  ·  Step 2: Footage Board  ·  Step 3: Create</span>", unsafe_allow_html=True)

if not SRC_MAIN.exists():
    st.error(f"Missing entry: {SRC_MAIN}. Run UI from project root.")
    st.stop()

with st.sidebar:
    st.markdown("## Controls")
    orientation = st.radio("Layout", ["portrait", "landscape"], horizontal=True)
    st.markdown("### Language")
    lang_options = [("English", "en-US"), ("French", "fr-FR"), ("Spanish", "es-ES"), ("Russian", "ru-RU"), ("Arabic", "ar-SA"), ("Other…", "other")]
    lang_labels = [f"{n} ({c})" if c != "other" else n for n, c in lang_options]
    sel = st.selectbox("Language", lang_labels, index=0)
    sel_code = dict(zip(lang_labels, [c for _, c in lang_options]))[sel]
    if sel_code == "other":
        lang_code = st.text_input("Custom language (BCP-47)", value="", placeholder="e.g. zh-CN / en-GB").strip()
    else:
        lang_code = sel_code
    if not lang_code:
        lang_code = "en-US"

    st.markdown("### ElevenLabs (saved)")
    profile = ensure_default_eleven_profile()
    saved_key = load_eleven_api_key()
    eleven_key = st.text_input("API Key", value=saved_key, type="password")
    model_id = st.selectbox("Model", ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5", "eleven_v3"], index=0)

    lang_short = (lang_code.split("-")[0] if lang_code else "en").lower()
    cur_voice_id = str(((profile.get("languages", {}) or {}).get(lang_short, {}) or {}).get("voice_id", "") or "")
    voice_id_input = st.text_input(f"Voice ID ({lang_short})", value=cur_voice_id, help="Must be an ElevenLabs voice_id.")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Save ElevenLabs", use_container_width=True):
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

    with c2:
        with st.popover("Mappings"):
            langs = profile.get("languages", {}) if isinstance(profile.get("languages", {}), dict) else {}
            rows_map = [{"lang": k, "voice_id": (v or {}).get("voice_id", "")} for k, v in sorted(langs.items())]
            st.dataframe(rows_map, use_container_width=True, hide_index=True)

    with st.expander("Troubleshooting", expanded=False):
        input_root = st.text_input("Input root", value=str(INPUT_ROOT_DEFAULT))
        verbose = st.checkbox("Verbose logs (dev)", value=False)

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

def list_companies() -> list[str]:
    if CREATIVE_ROOT.exists():
        return sorted([p.name for p in CREATIVE_ROOT.iterdir() if p.is_dir()])
    return []

companies = list_companies()
default_idx = companies.index("Siglen") if "Siglen" in companies else (0 if companies else None)
company = st.selectbox("Company", companies, index=default_idx)
input_root_path = Path(input_root) if "input_root" in locals() else INPUT_ROOT_DEFAULT
inbox_dir = input_root_path / orientation / company / "_INBOX"
factory_dir = input_root_path / orientation / company / "factory"

storage_ready = True
storage_error = ""
try:
    if input_root_path.exists() and not input_root_path.is_dir():
        storage_ready = False
        storage_error = f"Input root exists but is not a directory: {input_root_path}"
    else:
        inbox_dir.mkdir(parents=True, exist_ok=True)
        factory_dir.mkdir(parents=True, exist_ok=True)
except Exception as e:
    storage_ready = False
    storage_error = str(e)

if not storage_ready:
    st.warning("素材盘当前不可用。你仍然可以编辑脚本和配置，但素材相关功能会受限。")
    st.caption(f"Input root: {input_root_path}")
    if storage_error:
        st.caption(f"Reason: {storage_error}")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 1 · Script → Tasks")

src_mode = st.selectbox("Creative source", ["Paste YAML", "Select existing YAML"], key="src_mode")
colA, colB = st.columns([2, 1])
selected_path: Path | None = None

with colA:
    if src_mode == "Paste YAML":
        st.session_state["creative_draft"] = st.text_area("YAML script", value=st.session_state.get("creative_draft", ""), height=160, placeholder="Paste your Creative Script YAML here…", label_visibility="collapsed")
    else:
        creative_dir = CREATIVE_ROOT / company
        creative_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(creative_dir.glob("*.yaml"))
        if not files:
            st.warning("No YAML files found in creative_scripts for this company.")
        else:
            selected_path = st.selectbox("Select YAML", files, format_func=lambda p: p.name, key="select_yaml")
            st.caption("This will use the selected file as-is.")

with colB:
    st.markdown("**Actions**")
    generate_btn = st.button("Generate Tasks", use_container_width=True, key="generate_tasks")
    screenshot_mode = st.checkbox("Screenshot mode", value=True, key="screenshot_mode")
    export_html = st.checkbox("Export print-ready HTML", value=True, key="export_html")

if generate_btn:
    if src_mode == "Select existing YAML" and selected_path:
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
        project = str((d.get("meta", {}) or {}).get("project", "") or name_seed)
        run_id = f"{safe_slug(project)}_{now_tag()[:15]}"
        run_dir = OUTPUT_ROOT_DEFAULT / orientation / company / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        st.session_state["run_dir"] = str(run_dir)
        creative_path = run_dir / f"{run_id}.creative.yaml"
        creative_path.write_text(creative_text, encoding="utf-8")
        st.session_state["active_creative_path"] = str(creative_path)
        compiled_out = run_dir / f"{run_id}.compiled.yaml"
        st.session_state["compiled_out_path"] = str(compiled_out)

        beats = beats_from_creative(d)
        rows = []
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
                rows.append({"Row": f"S{row_i:03d}", "Beat": i, "Category": category, "Scene": scene, "Shot": shot_norm, "Seconds": seconds_default or default_seconds_for_shot(shot_norm), "Movement": suggested_movement(shot_norm), "Notes": visual, "BeatPurpose": str(beat.get("purpose") or "")})
                row_i += 1

        st.session_state["shooting_rows"] = rows
        (run_dir / "shooting_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if export_html:
            (run_dir / "shooting_guide.html").write_text(render_html_task_table(rows), encoding="utf-8")
        st.success(f"Generated {len(rows)} task rows.")
        st.caption(f"Run folder: {run_dir}")

rows = st.session_state.get("shooting_rows") or []
run_dir = Path(st.session_state["run_dir"]) if st.session_state.get("run_dir") else None

if rows and run_dir:
    if storage_ready:
        coverage = summarize_factory_coverage(rows, factory_dir)
        total_need = coverage["total_need"]
        total_ready = coverage["total_ready"]
        total_missing = coverage["total_missing"]
    else:
        total_need = len(rows)
        total_ready = 0
        total_missing = total_need

    k1, k2, k3 = st.columns([1, 1, 1])
    k1.metric("Total shots", total_need)
    k2.metric("Ready (factory)", total_ready)
    k3.metric("Missing", total_missing)

    show_cols = ["Row", "Scene", "Shot", "Seconds", "Movement", "Notes"] if screenshot_mode else ["Row", "Beat", "Category", "Scene", "Shot", "Seconds", "Movement", "Notes"]
    st.dataframe([{k: r.get(k, "") for k in show_cols} for r in rows], use_container_width=True, hide_index=True)

    if export_html:
        html_path = run_dir / "shooting_guide.html"
        if html_path.exists():
            st.download_button("Download print-ready HTML", data=html_path.read_text(encoding="utf-8"), file_name=html_path.name, mime="text/html", use_container_width=True)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 2 · Footage Board")
st.caption("Beat expanders. Each missing slot has its own custom tag and uploader. Files are saved into the factory pool.")

if not storage_ready:
    st.info("素材盘未连接，Step 2 当前不可用。")
elif rows:
    auto_use_factory = st.checkbox("Auto-use existing factory pool when possible", value=True, key="auto_use_factory")
    show_matches = st.checkbox("Show matched factory filenames", value=False, key="show_matches")
    ext_choice = st.selectbox("Default extension for uploads", [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice")

    factory_files = list_video_files(factory_dir, VIDEO_SUFFIXES)
    inbox_files = list_video_files(inbox_dir, VIDEO_SUFFIXES)

    beats_map: dict[int, list[dict]] = {}
    for r in rows:
        beats_map.setdefault(int(r["Beat"]), []).append(r)

    for beat_no in sorted(beats_map.keys()):
        beat_rows = beats_map[beat_no]
        beat_title = beat_rows[0].get("BeatPurpose") or f"Beat {beat_no}"

        with st.expander(f"Beat {beat_no} · {beat_title}", expanded=False):
            need: dict[tuple[str, str], int] = {}
            for rr in beat_rows:
                key = (rr["Category"], rr["Shot"])
                need[key] = need.get(key, 0) + 1

            for (cat, shot), n_need in need.items():
                pat = re.compile(rf"^factory_{re.escape(cat)}_{re.escape(shot)}_.*", re.IGNORECASE)
                matched = [p for p in factory_files if pat.match(p.name)]
                ready = min(n_need, len(matched)) if auto_use_factory else 0
                missing = n_need - ready
                st.markdown(f"**{cat.upper()} · {shot.upper()}** — need {n_need}, ready {ready}, missing {missing}")

                if show_matches and matched:
                    st.code("\n".join([p.name for p in matched[:20]]), language="text")

                if missing <= 0:
                    st.markdown("<span class='tiny'>No action needed.</span>", unsafe_allow_html=True)
                    st.markdown("---")
                    continue

                slot_custom = st.text_input(f"Custom tag for {cat}_{shot} (optional)", value="", placeholder="e.g. angleA / takeB", key=f"slot_custom_{beat_no}_{cat}_{shot}")
                uploads = st.file_uploader(f"Upload missing clips for {cat}_{shot}", type=[e.lstrip(".") for e in VIDEO_SUFFIXES], accept_multiple_files=True, key=f"up_{beat_no}_{cat}_{shot}")
                pick_inbox = st.multiselect(f"Or move from _INBOX ({len(inbox_files)})", options=inbox_files, format_func=lambda p: p.name, key=f"inbox_{beat_no}_{cat}_{shot}")

                if st.button("Save to factory", key=f"save_{beat_no}_{cat}_{shot}"):
                    cur = next_index_for(factory_dir, cat, shot, slot_custom, ext_choice)
                    if uploads:
                        for uf in uploads:
                            ext = Path(uf.name).suffix.lower() or ext_choice
                            fname = build_factory_filename(cat, shot, slot_custom, cur, ext)
                            safe_write_file(factory_dir / fname, uf.getbuffer().tobytes())
                            cur += 1

                    if pick_inbox:
                        for src in pick_inbox:
                            ext = src.suffix.lower() or ext_choice
                            fname = build_factory_filename(cat, shot, slot_custom, cur, ext)
                            dst = factory_dir / fname
                            if dst.exists():
                                dst = factory_dir / f"{Path(fname).stem}_{now_tag()}{ext}"
                            try:
                                src.rename(dst)
                            except Exception as e:
                                st.error(f"Move failed: {src.name} → {dst.name} ({e})")
                            cur += 1
                    st.success("Saved. Refreshing…")
                    st.rerun()
                st.markdown("---")
else:
    st.info("Generate tasks in Step 1 first.")

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 3 · Create Video")
st.caption("Runs silently. Logs saved to run folder. No terminal spam.")

active_creative_path = Path(st.session_state["active_creative_path"]) if st.session_state.get("active_creative_path") else None
run_dir = Path(st.session_state["run_dir"]) if st.session_state.get("run_dir") else None
compiled_out = Path(st.session_state["compiled_out_path"]) if st.session_state.get("compiled_out_path") else None

if not storage_ready:
    st.info("素材盘未连接，Step 3 当前不可用。")
elif not (active_creative_path and run_dir and compiled_out and active_creative_path.exists()):
    st.info("Generate tasks in Step 1 first.")
else:
    if st.button("Create Video", use_container_width=True, key="create_video"):
        progress = st.progress(0)
        status = st.empty()
        try:
            status.markdown("**Preparing…**")
            progress.progress(10)

            status.markdown("**Compiling…**")
            progress.progress(30)
            cmd_compile = [sys.executable, str(SRC_MAIN)]
            if "verbose" in locals() and verbose:
                cmd_compile.append("-v")
            cmd_compile += ["compile", "--creative", str(active_creative_path), "--out", str(compiled_out)]
            rc, compile_logs = run_cmd_silent(cmd_compile, ENV)
            (run_dir / "compile.log").write_text(compile_logs, encoding="utf-8")
            if rc != 0:
                progress.progress(100)
                st.error("❌ Compile failed. See compile.log in run folder.")
                raise SystemExit(0)

            status.markdown("**Applying settings…**")
            progress.progress(50)
            patch_compiled_yaml(compiled_out, orientation, lang_code, model_id, ELEVEN_PROFILE_PATH)

            status.markdown("**Rendering…**")
            progress.progress(70)
            cmd_run = [sys.executable, str(SRC_MAIN)]
            if "verbose" in locals() and verbose:
                cmd_run.append("-v")
            cmd_run += ["run", "--company", company, "--script", str(compiled_out), "--input", str(input_root_path)]
            rc2, render_logs = run_cmd_silent(cmd_run, ENV)
            (run_dir / "render.log").write_text(render_logs, encoding="utf-8")
            if rc2 != 0:
                progress.progress(100)
                st.error("❌ Render failed. See render.log in run folder.")
                raise SystemExit(0)

            status.markdown("**Done.**")
            progress.progress(100)
            st.success("✅ Video created successfully.")
        except SystemExit:
            pass
        except Exception as e:
            progress.progress(100)
            st.error(f"❌ Unexpected error: {e}")

    st.link_button("Open run folder", f"file://{run_dir}", use_container_width=True)
