#!/usr/bin/env python3
import os
import sys
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st

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

VIDEO_EXTS = ["mp4", "mov", "mkv", "m4v"]
VIDEO_SUFFIXES = ["." + e for e in VIDEO_EXTS]

# =========================================================
# UI Style
# =========================================================
st.set_page_config(page_title="Video Automation Tool", layout="wide")
st.markdown(
    """
    <style>
      .divider { margin: 1.1rem 0 1.0rem 0; border-bottom: 1px solid rgba(0,0,0,0.08); }
      .muted { color: rgba(0,0,0,0.55); }
      .tiny { color: rgba(0,0,0,0.55); font-size: 0.9rem; }
      code { white-space: pre-wrap !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistent config helpers
# =========================================================
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
    """
    Create/normalize data/tts_profiles/elevenlabs.json.
    Only fills blank fields; won't overwrite existing values.
    """
    profile = load_eleven_profile()
    profile.setdefault("defaults", {})
    profile.setdefault("languages", {})

    defaults = profile["defaults"] if isinstance(profile["defaults"], dict) else {}
    defaults.setdefault("model_id", "eleven_multilingual_v2")
    defaults.setdefault("output_format", "mp3_44100_128")
    defaults.setdefault("voice_settings", {"stability": 0.55, "similarity_boost": 0.75})
    profile["defaults"] = defaults

    langs = profile["languages"] if isinstance(profile["languages"], dict) else {}

    # ✅ 常用语言：预置真实 voice_id（你后面可换成自己账号里的 voice_id）
    # en: Rachel = 21m00Tcm4TlvDq8ikWAM（官方示例中标注 name=Rachel）[2](https://api.asm.skype.com/v1/objects/0-ea-d9-2e7ef5fbf9f23f5c73042a56cdae6947/views/original/ui_app.py)
    # 其余为公开 premade voice id 列表中常见项，用于快速跑通链路
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

# =========================================================
# Generic helpers
# =========================================================
def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def safe_slug(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "untitled"
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]+", "", s)
    return s[:80] or "untitled"

def list_companies() -> list[str]:
    if CREATIVE_ROOT.exists():
        return sorted([p.name for p in CREATIVE_ROOT.iterdir() if p.is_dir()])
    return []

def load_yaml_text(text: str) -> dict:
    try:
        import yaml  # type: ignore
        d = yaml.safe_load(text) or {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def beats_from_creative(creative: dict) -> list[dict]:
    beats = creative.get("beats", [])
    if not isinstance(beats, list):
        return []
    return [b for b in beats if isinstance(b, dict)]

def normalize_coverage(cov) -> list[str]:
    if cov is None:
        return []
    if isinstance(cov, str):
        return [cov]
    if isinstance(cov, list):
        return [str(x) for x in cov]
    return []

def list_video_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files

def safe_write_file(dst: Path, data: bytes) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        dst.write_bytes(data)
        return dst
    stamped = dst.with_name(f"{dst.stem}_{now_tag()}{dst.suffix}")
    stamped.write_bytes(data)
    return stamped

def validate_creative_schema(d: dict) -> tuple[bool, str]:
    if not isinstance(d, dict):
        return False, "Creative YAML is not a mapping."
    beats = d.get("beats")
    if not isinstance(beats, list) or not beats:
        return False, "Missing or empty 'beats' list."
    return True, "OK"

def render_html_task_table(rows: list[dict]) -> str:
    css = """
    <style>
      body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial;margin:24px;}
      h2{margin:0 0 12px 0;}
      table{border-collapse:collapse;width:100%;}
      th,td{border:1px solid #ddd;padding:8px;vertical-align:top;font-size:12px;}
      th{background:#f3f3f3;font-weight:700;}
      .small{color:#666;font-size:11px;}
    </style>
    """
    headers = ["Row", "Beat", "Category", "Scene", "Shot", "Seconds", "Suggested Movement", "Notes"]
    thead = "<tr>" + "".join([f"<th>{h}</th>" for h in headers]) + "</tr>"
    trs = []
    for r in rows:
        trs.append(
            "<tr>"
            + f"<td>{r.get('Row','')}</td>"
            + f"<td>{r.get('Beat','')}</td>"
            + f"<td>{r.get('Category','')}</td>"
            + f"<td>{r.get('Scene','')}</td>"
            + f"<td>{r.get('Shot','')}</td>"
            + f"<td>{r.get('Seconds','')}</td>"
            + f"<td>{r.get('Movement','')}</td>"
            + f"<td>{r.get('Notes','')}</td>"
            + "</tr>"
        )
    tbody = "\n".join(trs)
    return f"{css}<h2>Shooting Guide</h2><div class='small'>Generated: {now_tag()}</div><table>{thead}{tbody}</table>"

# ---- naming / inference ----
def infer_category_from_beat(beat: dict) -> str:
    tags = beat.get("tags", [])
    if isinstance(tags, list):
        t = [str(x).lower() for x in tags]
        for key in ["automation", "testing", "line", "building", "hero"]:
            if key in t:
                return "building" if key in ["building", "hero"] else key
    purpose = str(beat.get("purpose", "")).lower()
    if "automation" in purpose:
        return "automation"
    if "testing" in purpose or "qc" in purpose:
        return "testing"
    if "line" in purpose or "production" in purpose:
        return "line"
    if "brand" in purpose or "close" in purpose or "hero" in purpose:
        return "building"
    return "line"

def infer_shots_from_beat(beat: dict) -> list[str]:
    bs = beat.get("beat_structure")
    if isinstance(bs, list) and bs:
        return [str(x).lower() for x in bs]
    cov_list = normalize_coverage(beat.get("coverage"))
    if cov_list:
        out = []
        for x in cov_list:
            xl = str(x).lower()
            out.append("detail" if xl in ["close", "detail"] else xl)
        return out
    return ["wide", "detail"]

def infer_scene_from_beat(beat: dict) -> str:
    scene = str(beat.get("scene") or beat.get("location") or "").strip()
    if scene:
        return scene
    visual = str(beat.get("visual") or beat.get("visual_description") or "").lower()
    purpose = str(beat.get("purpose") or "").lower()
    t = f"{purpose} {visual}"
    if "exterior" in t or "building" in t:
        return "Factory exterior"
    if "testing" in t or "inspection" in t:
        return "Testing area"
    if "automation" in t or "robot" in t or "sensor" in t:
        return "Factory floor (automation)"
    if "line" in t or "production" in t:
        return "Factory floor (line)"
    return "Factory floor"

def suggested_movement(shot: str) -> str:
    s = (shot or "").lower()
    if s == "detail":
        return "static | slow push-in | micro pan"
    if s == "medium":
        return "static | slow pan"
    if s in ["wide", "hero"]:
        return "static | slow pan | tilt"
    return "static | slow pan"

def default_seconds_for_shot(_: str) -> str:
    return "4–6"

def build_factory_filename(category: str, shot: str, custom: str, idx: int, ext: str) -> str:
    category = safe_slug(category).lower()
    shot = safe_slug(shot).lower()
    custom = safe_slug(custom).lower()
    core = f"factory_{category}_{shot}"
    if custom:
        core += f"_{custom}"
    core += f"_{idx:02d}"
    if not ext.startswith("."):
        ext = "." + ext
    return f"{core}{ext}"

def next_index_for(factory_dir: Path, category: str, shot: str, custom: str, ext: str) -> int:
    category = category.lower()
    shot = shot.lower()
    custom = safe_slug(custom).lower()
    pat = re.compile(
        rf"^factory_{re.escape(category)}_{re.escape(shot)}(?:_{re.escape(custom)})?_(\d\d){re.escape(ext)}$",
        re.IGNORECASE,
    )
    mx = 0
    if not factory_dir.exists():
        return 1
    for p in factory_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ext.lower():
            continue
        m = pat.match(p.name)
        if m:
            try:
                mx = max(mx, int(m.group(1)))
            except Exception:
                pass
    return mx + 1

# ---- patch compiled yaml ----
def patch_compiled_yaml(compiled_path: Path, orientation: str, lang: str, model: str) -> None:
    try:
        import yaml  # type: ignore
    except Exception:
        raise RuntimeError("PyYAML not installed. Run: python -m pip install pyyaml")

    d = yaml.safe_load(compiled_path.read_text(encoding="utf-8")) or {}
    if not isinstance(d, dict):
        d = {}

    project = d.get("project", {})
    if not isinstance(project, dict):
        project = {}
    d["project"] = project

    out = project.get("output", {})
    if not isinstance(out, dict):
        out = {}
    project["output"] = out
    out["format"] = "portrait_1080x1920" if orientation == "portrait" else "landscape_1920x1080"

    audio = project.get("audio", {})
    if not isinstance(audio, dict):
        audio = {}
    project["audio"] = audio

    voiceover = audio.get("voiceover", {})
    if not isinstance(voiceover, dict):
        voiceover = {}
    audio["voiceover"] = voiceover

    profile = load_eleven_profile()
    defaults = profile.get("defaults", {}) if isinstance(profile.get("defaults", {}), dict) else {}

    voiceover["provider"] = "elevenlabs"
    voiceover["language"] = lang
    voiceover["model"] = model
    voiceover["output_format"] = str(defaults.get("output_format", "mp3_44100_128"))
    voiceover.setdefault("volume", 1.0)

    compiled_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")

# ---- silent subprocess (clean UI) ----
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

# =========================================================
# Session state
# =========================================================
st.session_state.setdefault("active_creative_path", None)
st.session_state.setdefault("creative_draft", "")
st.session_state.setdefault("run_dir", None)
st.session_state.setdefault("shooting_rows", [])
st.session_state.setdefault("compiled_out_path", None)

# =========================================================
# Header
# =========================================================
st.markdown("## 🎬 Video Automation Tool")
st.markdown("<span class='muted'>Step 1: Script → Tasks  ·  Step 2: Footage Board  ·  Step 3: Create</span>", unsafe_allow_html=True)

if not SRC_MAIN.exists():
    st.error(f"Missing entry: {SRC_MAIN}. Run UI from project root.")
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
        lang_code = st.text_input("Custom language (BCP‑47)", value="", placeholder="e.g. zh-CN / en-GB").strip()
    else:
        lang_code = sel_code
    if not lang_code:
        lang_code = "en-US"

    st.markdown("### ElevenLabs (saved)")
    profile = ensure_default_eleven_profile()

    saved_key = load_eleven_api_key()
    eleven_key = st.text_input("API Key", value=saved_key, type="password")

    model_id = st.selectbox(
        "Model",
        ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5", "eleven_v3"],
        index=0,
    )

    lang_short = (lang_code.split("-")[0] if lang_code else "en").lower()
    cur_voice_id = str(((profile.get("languages", {}) or {}).get(lang_short, {}) or {}).get("voice_id", "") or "")

    voice_id_input = st.text_input(
        f"Voice ID ({lang_short})",
        value=cur_voice_id,
        help="Must be an ElevenLabs voice_id. Example: Rachel = 21m00Tcm4TlvDq8ikWAM.",
    )

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
            rows = [{"lang": k, "voice_id": (v or {}).get("voice_id", "")} for k, v in sorted(langs.items())]
            st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Troubleshooting", expanded=False):
        input_root = st.text_input("Input root", value=str(INPUT_ROOT_DEFAULT))
        verbose = st.checkbox("Verbose logs (dev)", value=False)

# =========================================================
# ENV injection (key point!)
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
    if not isinstance(v, dict):
        continue
    vid = str(v.get("voice_id", "") or "").strip()
    if vid:
        ENV[f"ELEVENLABS_VOICE_ID_{k.upper()}"] = vid

# =========================================================
# Company + dirs
# =========================================================
companies = list_companies()
default_idx = companies.index("Siglen") if "Siglen" in companies else (0 if companies else None)
company = st.selectbox("Company", companies, index=default_idx)

input_root_path = Path(input_root) if "input_root" in locals() else INPUT_ROOT_DEFAULT
inbox_dir = input_root_path / orientation / company / "_INBOX"
factory_dir = input_root_path / orientation / company / "factory"
inbox_dir.mkdir(parents=True, exist_ok=True)
factory_dir.mkdir(parents=True, exist_ok=True)

# =========================================================
# Step 1 · Script → Tasks
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 1 · Script → Tasks")

src_mode = st.selectbox("Creative source", ["Paste YAML", "Select existing YAML"], key="src_mode")
colA, colB = st.columns([2, 1])

selected_path: Path | None = None
with colA:
    if src_mode == "Paste YAML":
        st.session_state["creative_draft"] = st.text_area(
            "YAML script",
            value=st.session_state.get("creative_draft", ""),
            height=160,
            placeholder="Paste your Creative Script YAML here…",
            label_visibility="collapsed",
        )
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
        run_id = f"{safe_slug(project)}_{now_tag()[:15]}"  # yyyyMMdd_HHmm

        run_dir = OUTPUT_ROOT_DEFAULT / orientation / company / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        st.session_state["run_dir"] = str(run_dir)

        creative_path = run_dir / f"{run_id}.creative.yaml"
        creative_path.write_text(creative_text, encoding="utf-8")
        st.session_state["active_creative_path"] = str(creative_path)

        compiled_out = run_dir / f"{run_id}.compiled.yaml"
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
                rows.append({
                    "Row": f"S{row_i:03d}",
                    "Beat": i,
                    "Category": category,
                    "Scene": scene,
                    "Shot": shot_norm,
                    "Seconds": seconds_default or default_seconds_for_shot(shot_norm),
                    "Movement": suggested_movement(shot_norm),
                    "Notes": visual,
                    "BeatPurpose": str(beat.get("purpose") or ""),
                })
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
    factory_files = list_video_files(factory_dir)
    need_by: dict[tuple[str, str], int] = {}
    for r in rows:
        need_by[(r["Category"], r["Shot"])] = need_by.get((r["Category"], r["Shot"]), 0) + 1

    match_counts: dict[tuple[str, str], int] = {}
    for (cat, shot), need in need_by.items():
        pat = re.compile(rf"^factory_{re.escape(cat)}_{re.escape(shot)}_.*", re.IGNORECASE)
        match_counts[(cat, shot)] = len([p for p in factory_files if pat.match(p.name)])

    total_need = sum(need_by.values())
    total_ready = sum(min(need, match_counts.get(k, 0)) for k, need in need_by.items())
    total_missing = total_need - total_ready

    k1, k2, k3 = st.columns([1, 1, 1])
    k1.metric("Total shots", total_need)
    k2.metric("Ready (factory)", total_ready)
    k3.metric("Missing", total_missing)

    show_cols = ["Row", "Scene", "Shot", "Seconds", "Movement", "Notes"] if screenshot_mode else ["Row", "Beat", "Category", "Scene", "Shot", "Seconds", "Movement", "Notes"]
    st.dataframe([{k: r.get(k, "") for k in show_cols} for r in rows], use_container_width=True, hide_index=True)

    if export_html:
        html_path = run_dir / "shooting_guide.html"
        if html_path.exists():
            st.download_button(
                "Download print-ready HTML",
                data=html_path.read_text(encoding="utf-8"),
                file_name=html_path.name,
                mime="text/html",
                use_container_width=True,
            )

# =========================================================
# Step 2 · Footage Board
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 2 · Footage Board")
st.caption("Beat expanders. Each missing slot has its own custom tag and uploader. Files are saved into the factory pool.")

if rows:
    auto_use_factory = st.checkbox("Auto-use existing factory pool when possible", value=True, key="auto_use_factory")
    show_matches = st.checkbox("Show matched factory filenames", value=False, key="show_matches")
    ext_choice = st.selectbox("Default extension for uploads", [".mp4", ".mov", ".m4v", ".mkv"], index=0, key="ext_choice")

    factory_files = list_video_files(factory_dir)
    inbox_files = list_video_files(inbox_dir)

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

                slot_custom = st.text_input(
                    f"Custom tag for {cat}_{shot} (optional)",
                    value="",
                    placeholder="e.g. fromAutomation / angleA / takeB",
                    key=f"slot_custom_{beat_no}_{cat}_{shot}",
                )

                uploads = st.file_uploader(
                    f"Upload missing clips for {cat}_{shot}",
                    type=VIDEO_EXTS,
                    accept_multiple_files=True,
                    key=f"up_{beat_no}_{cat}_{shot}",
                )

                pick_inbox = st.multiselect(
                    f"Or move from _INBOX ({len(inbox_files)})",
                    options=inbox_files,
                    format_func=lambda p: p.name,
                    key=f"inbox_{beat_no}_{cat}_{shot}",
                )

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

# =========================================================
# Step 3 · Create (clean UI + progress)
# =========================================================
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("## Step 3 · Create Video")
st.caption("Runs silently. Logs saved to run folder (compile.log / render.log). No terminal spam.")

active_creative_path = Path(st.session_state["active_creative_path"]) if st.session_state.get("active_creative_path") else None
run_dir = Path(st.session_state["run_dir"]) if st.session_state.get("run_dir") else None
compiled_out = Path(st.session_state["compiled_out_path"]) if st.session_state.get("compiled_out_path") else None

if not (active_creative_path and run_dir and compiled_out and active_creative_path.exists()):
    st.info("Generate tasks in Step 1 first.")
else:
    if st.button("Create Video", use_container_width=True, key="create_video"):
        progress = st.progress(0)
        status = st.empty()

        try:
            status.markdown("**Preparing…**")
            progress.progress(10)

            # --- Compile (A: output to run_dir) ---
            status.markdown("**Compiling…**")
            progress.progress(30)

            cmd_compile = [sys.executable, str(SRC_MAIN)]
            if "verbose" in locals() and verbose:
                cmd_compile.append("-v")
            cmd_compile += ["compile", "--company", company, "--creative", str(active_creative_path), "--out", str(compiled_out)]

            rc, compile_logs = run_cmd_silent(cmd_compile, ENV)
            (run_dir / "compile.log").write_text(compile_logs, encoding="utf-8")
            if rc != 0:
                progress.progress(100)
                st.error("❌ Compile failed. See compile.log in run folder.")
                raise SystemExit(0)

            # --- Patch voiceover / format settings into compiled.yaml ---
            status.markdown("**Applying settings…**")
            progress.progress(50)
            patch_compiled_yaml(compiled_out, orientation, lang_code, model_id)

            # --- Render ---
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