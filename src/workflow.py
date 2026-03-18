from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.script_loader import load_script
from src.render_profile import get_default_fps, get_subtitle_style, get_filter_preset


VIDEO_SUFFIXES = [".mp4", ".mov", ".mkv", ".m4v"]


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_slug(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "untitled"
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]+", "", s)
    return s[:80] or "untitled"


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


def validate_creative_schema(d: dict) -> tuple[bool, str]:
    if not isinstance(d, dict):
        return False, "Creative YAML is not a mapping."
    beats = d.get("beats")
    if not isinstance(beats, list) or not beats:
        return False, "Missing or empty 'beats' list."
    return True, "OK"


def normalize_coverage(cov) -> list[str]:
    if cov is None:
        return []
    if isinstance(cov, str):
        return [cov]
    if isinstance(cov, list):
        return [str(x) for x in cov]
    return []


def list_video_files(folder: Path, suffixes: Optional[list[str]] = None) -> list[Path]:
    suffixes = suffixes or VIDEO_SUFFIXES
    if not folder.exists() or not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in suffixes]
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


# =========================================================
# Storage layout
# =========================================================
def ensure_company_storage(input_root: Path, company: str) -> dict[str, Path]:
    """
    Ensure both orientations exist for one company.

    Creates:
      input_root/portrait/<company>/_INBOX
      input_root/portrait/<company>/factory
      input_root/landscape/<company>/_INBOX
      input_root/landscape/<company>/factory
    """
    out: dict[str, Path] = {}
    for orientation in ("portrait", "landscape"):
        company_root = input_root / orientation / company
        inbox = company_root / "_INBOX"
        factory = company_root / "factory"
        inbox.mkdir(parents=True, exist_ok=True)
        factory.mkdir(parents=True, exist_ok=True)
        out[f"{orientation}_company_root"] = company_root
        out[f"{orientation}_inbox"] = inbox
        out[f"{orientation}_factory"] = factory
    return out


def get_storage_dirs(input_root: Path, orientation: str, company: str) -> dict[str, Path]:
    ensure_company_storage(input_root, company)
    company_root = input_root / orientation / company
    return {
        "company_root": company_root,
        "inbox": company_root / "_INBOX",
        "factory": company_root / "factory",
    }


# =========================================================
# Video orientation
# =========================================================
def probe_video_dimensions(path: Path) -> tuple[Optional[int], Optional[int]]:
    """
    Uses ffprobe to read width/height.
    Returns (width, height) or (None, None) on failure.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(path),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if p.returncode != 0:
            return None, None
        data = json.loads(p.stdout or "{}")
        streams = data.get("streams", [])
        if not streams:
            return None, None
        stream = streams[0]
        w = stream.get("width")
        h = stream.get("height")
        if isinstance(w, int) and isinstance(h, int):
            return w, h
        return None, None
    except Exception:
        return None, None


def classify_orientation(path: Path) -> str:
    w, h = probe_video_dimensions(path)
    if not w or not h:
        return "unknown"
    if h > w:
        return "portrait"
    if w > h:
        return "landscape"
    return "square"


def orientation_matches(target_orientation: str, path: Path) -> bool:
    actual = classify_orientation(path)
    return actual == target_orientation


# =========================================================
# Task row generation
# =========================================================
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


def generate_shooting_rows(creative: dict) -> list[dict]:
    beats = beats_from_creative(creative)
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

    return rows


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
    return f"{css}<h2>Task Rows</h2><div class='small'>Generated: {now_tag()}</div><table>{thead}{tbody}</table>"


# =========================================================
# Footage pool helpers
# =========================================================
def build_factory_filename(scene: str, content: str, coverage: str, move: str, idx: int, ext: str) -> str:
    scene = safe_slug(scene).lower()
    content = safe_slug(content).lower()
    coverage = safe_slug(coverage).lower()
    move = safe_slug(move).lower() if str(move or "").strip() else ""

    core = f"factory_{scene}_{content}"
    if coverage:
        core += f"_{coverage}"
    if move:
        core += f"_{move}"
    core += f"_{idx:02d}"
    if not ext.startswith("."):
        ext = "." + ext
    return f"{core}{ext}"


def next_index_for(factory_dir: Path, scene: str, content: str, coverage: str, move: str, ext: str) -> int:
    scene = safe_slug(scene).lower()
    content = safe_slug(content).lower()
    coverage = safe_slug(coverage).lower()
    move = safe_slug(move).lower() if str(move or "").strip() else ""
    if not ext.startswith("."):
        ext = "." + ext

    core = f"factory_{scene}_{content}"
    if coverage:
        core += f"_{coverage}"
    if move:
        core += f"_{move}"

    pat = re.compile(rf"^{re.escape(core)}_(\d\d){re.escape(ext)}$", re.IGNORECASE)
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


def normalize_demo_content_token(token: str) -> str:
    normalized = safe_slug(str(token or "")).lower()
    if normalized in {"line", "factory_line", "automation", "building", "testing", "inspection", "panel"}:
        return "line"
    return normalized or "line"


def normalize_demo_coverage_token(token: str) -> str:
    normalized = safe_slug(str(token or "")).lower()
    if normalized in {"hero", "wide"} or normalized.startswith("hero_") or normalized.startswith("wide_"):
        return "hero"
    if normalized == "medium" or normalized.startswith("medium_"):
        return "medium"
    if normalized in {"detail", "close", "closeup"} or normalized.startswith("detail_") or normalized.startswith("close_"):
        return "detail"
    return normalized


def parse_factory_filename_key(path: Path) -> tuple[str, str] | None:
    stem = path.stem.lower()
    parts = stem.split("_")
    if len(parts) < 4 or parts[0] != "factory":
        return None

    if len(parts) >= 5 and parts[1] == "factory":
        content = parts[2]
        coverage = parts[3]
    else:
        content = parts[1]
        coverage = parts[2]

    content_key = normalize_demo_content_token(content)
    coverage_key = normalize_demo_coverage_token(coverage)
    if not content_key or not coverage_key:
        return None
    return content_key, coverage_key


def count_factory_clips_by_key(factory_files: list[Path]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for path in factory_files:
        key = parse_factory_filename_key(path)
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def allocate_coverage_across_beats(
    beat_needs: list[dict[tuple[str, str], int]],
    available_by_key: dict[tuple[str, str], int],
) -> list[dict[tuple[str, str], tuple[int, int]]]:
    remaining = dict(available_by_key)
    out: list[dict[tuple[str, str], tuple[int, int]]] = []

    for need in beat_needs:
        beat_out: dict[tuple[str, str], tuple[int, int]] = {}
        for key, required in need.items():
            available = int(remaining.get(key, 0) or 0)
            ready = min(int(required), available)
            missing = int(required) - ready
            remaining[key] = max(available - ready, 0)
            beat_out[key] = (ready, missing)
        out.append(beat_out)

    return out


def summarize_factory_coverage(rows: list[dict], factory_dir: Path) -> dict[str, int]:
    factory_files = list_video_files(factory_dir, VIDEO_SUFFIXES)
    need_by: dict[tuple[str, str], int] = {}
    for r in rows:
        cat = normalize_demo_content_token(str(r.get("Category", "") or ""))
        shot = normalize_demo_coverage_token(str(r.get("Shot", "") or ""))
        need_by[(cat, shot)] = need_by.get((cat, shot), 0) + 1

    match_counts = count_factory_clips_by_key(factory_files)

    total_need = sum(need_by.values())
    total_ready = sum(min(need, match_counts.get(k, 0)) for k, need in need_by.items())
    total_missing = total_need - total_ready
    return {"total_need": total_need, "total_ready": total_ready, "total_missing": total_missing}


# =========================================================
# Internal compile/render helpers
# =========================================================
def _normalize_purpose(purpose: str) -> str:
    p = (purpose or "").strip().lower()
    if p in {"establish_context", "show_capability", "build_trust", "brand_close"}:
        return p
    if "establish" in p or "capability" in p:
        return "establish_context"
    if "automation" in p or "show" in p:
        return "show_capability"
    if "quality" in p or "assurance" in p or "testing" in p or "qc" in p:
        return "build_trust"
    if "brand" in p or "close" in p or "hero" in p:
        return "brand_close"
    return "establish_context"


def _infer_scene_token(visual: str) -> str:
    v = (visual or "").lower()
    if "showroom" in v:
        return "showroom"
    if "villa" in v:
        return "villa"
    if "factory" in v:
        return "factory"
    return "factory"


def _shot(
    scene: str,
    content: str,
    coverage: str,
    move: str,
    duration: float,
    subtitle: str,
    tag: str,
    vo: Optional[str] = None,
) -> Dict[str, Any]:
    _ = move  # short-term demo path intentionally omits move tokens from generated source tags.
    tags = [scene, content, coverage]
    out: Dict[str, Any] = {
        "source": "next:tags:" + ",".join(tags),
        "duration": float(duration),
        "subtitle": subtitle if subtitle else None,
        "tag": tag,
    }
    if isinstance(vo, str) and vo.strip():
        out["vo"] = vo.strip()
    return out


def _compile_fallback_shot(beat: Dict[str, Any], default_scene: str) -> Dict[str, Any]:
    vo = beat.get("vo")
    vo_clean = str(vo).strip() if isinstance(vo, str) else ""
    subtitle = str(beat.get("subtitle") or "").strip()

    source = beat.get("source") or beat.get("source_hint")
    if isinstance(source, str) and source.strip():
        out: Dict[str, Any] = {"source": source.strip()}
        dur = beat.get("duration_hint")
        if isinstance(dur, (int, float)):
            out["duration"] = float(dur)
        if subtitle:
            out["subtitle"] = subtitle
        if vo_clean:
            out["vo"] = vo_clean
        out["tag"] = str(beat.get("purpose") or "beat")
        return out

    tags = beat.get("tags")
    if isinstance(tags, list) and tags:
        tag_str = ",".join([str(t).strip() for t in tags if str(t).strip()])
        out2: Dict[str, Any] = {"source": f"next:tags:{tag_str}" if tag_str else "next:tags:generic"}
        dur2 = beat.get("duration_hint")
        if isinstance(dur2, (int, float)):
            out2["duration"] = float(dur2)
        if subtitle:
            out2["subtitle"] = subtitle
        if vo_clean:
            out2["vo"] = vo_clean
        out2["tag"] = str(beat.get("purpose") or "beat")
        return out2

    visual = str(beat.get("visual") or "").strip()
    dur3 = beat.get("duration_hint")
    return {
        "source": f"next:tags:{default_scene},generic",
        "notes": visual if visual else None,
        "duration": float(dur3) if isinstance(dur3, (int, float)) else 3.0,
        "subtitle": subtitle or None,
        "vo": vo_clean or None,
        "tag": str(beat.get("purpose") or "beat"),
    }


def compile_creative_dict(creative: Dict[str, Any]) -> Dict[str, Any]:
    meta = creative.get("meta", {}) if isinstance(creative.get("meta"), dict) else {}
    target_len = float(meta.get("target_length", 20) or 20)
    beats = beats_from_creative(creative)

    seq: List[Dict[str, Any]] = []
    for beat in beats:
        purpose_raw = str(beat.get("purpose") or "").strip()
        purpose = _normalize_purpose(purpose_raw)
        subtitle = str(beat.get("subtitle") or "").strip()
        vo_text = str(beat.get("vo") or "").strip()
        visual = str(beat.get("visual") or "").strip()
        _ = beat.get("scene") or _infer_scene_token(visual) or "factory"
        scene = "factory"
        content = "line"

        if purpose == "establish_context":
            seq.extend(
                [
                    _shot(scene, content, "hero", "", 3.0, subtitle, tag="context_wide", vo=vo_text),
                    _shot(scene, content, "detail", "", 2.0, subtitle, tag="context_detail"),
                ]
            )
        elif purpose == "show_capability":
            seq.extend(
                [
                    _shot(scene, content, "medium", "", 3.0, subtitle, tag="automation_wide", vo=vo_text),
                    _shot(scene, content, "detail", "", 1.8, subtitle, tag="automation_detail"),
                    _shot(scene, content, "medium", "", 2.7, subtitle, tag="automation_medium"),
                ]
            )
        elif purpose == "build_trust":
            seq.extend(
                [
                    _shot(scene, content, "detail", "", 2.2, subtitle, tag="testing_detail", vo=vo_text),
                    _shot(scene, content, "medium", "", 2.8, subtitle, tag="testing_medium"),
                ]
            )
        elif purpose == "brand_close":
            close_sub = subtitle if subtitle else "SIGLEN"
            seq.append(_shot(scene, content, "hero", "", 4.5, close_sub, tag="hero", vo=vo_text))
        else:
            seq.append(_compile_fallback_shot(beat, default_scene=scene))

    total = sum(float(s.get("duration") or 0.0) for s in seq)
    if total > 0:
        scale = float(target_len) / float(total)
        scale = max(0.85, min(1.15, scale))
        for s in seq:
            if isinstance(s.get("duration"), (int, float)):
                s["duration"] = round(float(s["duration"]) * scale, 2)

    proj = {"meta": meta, "output": {"format": "portrait_1080x1920"}}
    if isinstance(creative.get("project"), dict):
        proj.update(creative["project"])

    return {"project": proj, "timeline": [{k: v for k, v in s.items() if v is not None} for s in seq]}


def dump_yaml(data: dict, out_path: Path) -> None:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(f"PyYAML required to write YAML: {e}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def compile_creative_file_to_production(creative_path: Path, out_path: Path) -> Path:
    creative = load_script(creative_path)
    production = compile_creative_dict(creative)
    dump_yaml(production, out_path)
    return out_path


def patch_compiled_yaml(
    compiled_path: Path,
    orientation: str,
    lang: str,
    model: str,
    eleven_profile_path: Optional[Path] = None,
    filter_preset_name: str = "clean",
) -> None:
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
    out["fps"] = get_default_fps()

    audio = project.get("audio", {})
    if not isinstance(audio, dict):
        audio = {}
    project["audio"] = audio

    voiceover = audio.get("voiceover", {})
    if not isinstance(voiceover, dict):
        voiceover = {}
    audio["voiceover"] = voiceover

    defaults = {}
    if eleven_profile_path and eleven_profile_path.exists():
        try:
            profile = json.loads(eleven_profile_path.read_text(encoding="utf-8"))
            defaults = profile.get("defaults", {}) if isinstance(profile.get("defaults", {}), dict) else {}
        except Exception:
            defaults = {}

    voiceover["provider"] = "elevenlabs"
    voiceover["language"] = lang
    voiceover["model"] = model
    voiceover["output_format"] = str(defaults.get("output_format", "mp3_44100_128"))
    voiceover.setdefault("volume", 1.0)

    project["subtitle_style"] = get_subtitle_style(lang)
    project["filter_preset"] = get_filter_preset(filter_preset_name)

    compiled_path.write_text(
        yaml.safe_dump(d, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
