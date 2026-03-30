from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.script_loader import load_script
from src.render_profile import get_default_fps, get_subtitle_style, get_filter_preset
from src.tts_local_settings import load_tts_routing_settings, resolve_tts_provider


VIDEO_SUFFIXES = [".mp4", ".mov", ".mkv", ".m4v"]

MOVE_TOKEN_OPTIONS = ["static", "pan", "slide", "pushin", "follow", "orbit", "reveal"]
MOVE_TOKEN_VOCAB = set(
    MOVE_TOKEN_OPTIONS
    + [
        "panl",
        "panr",
        "tiltu",
        "tiltd",
        "slidel",
        "slider",
        "pullout",
        "pov",
        "expand",
        "zoom",
    ]
)




# External vocabulary loader
_TAXONOMY_DIR = Path(__file__).resolve().parent.parent / "data" / "taxonomy"
_vocab_cache: Dict[str, Any] = {}


def _load_vocabulary(name: str) -> Dict[str, Any]:
    if name in _vocab_cache:
        return _vocab_cache[name]
    path = _TAXONOMY_DIR / f"{name}.yaml"
    if not path.exists():
        _vocab_cache[name] = {}
        return {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _vocab_cache[name] = data if isinstance(data, dict) else {}
        return _vocab_cache[name]
    except Exception:
        _vocab_cache[name] = {}
        return {}


def reload_vocabularies() -> None:
    _vocab_cache.clear()

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



def _project_slot(
    beat_no: int,
    beat_purpose: str,
    request_family: str,
    scene: str,
    content: str,
    coverage: str,
    move: str,
    target: int,
    priority: str,
    human_label: str,
    shoot_brief: str,
    defaults: Optional[dict] = None,
    subtitle: str = "",
    vo: str = "",
    tag: str = "",
    duration_hint: float = 0.0,
    subject: str = "",
    action: str = "",
) -> dict:
    content_clean = str(content or "").strip()
    subject_clean = str(subject or "").strip()
    action_clean = str(action or "").strip()

    if not subject_clean or not action_clean:
        _derived_subject, _derived_action = _legacy_subject_action_from_content(
            content=content_clean,
            purpose=str(beat_purpose or request_family or "").strip(),
        )
        subject_clean = subject_clean or _derived_subject
        action_clean = action_clean or _derived_action

    return {
        "beat_no": int(beat_no),
        "beat_purpose": str(beat_purpose or "").strip(),
        "request_family": str(request_family or "").strip(),
        "scene": str(scene or "").strip(),
        "content": content_clean,
        "subject": subject_clean,
        "action": action_clean,
        "coverage": str(coverage or "").strip(),
        "move": str(move or "").strip(),
        "target": int(target or 0),
        "priority": str(priority or "medium").strip(),
        "defaults": dict(defaults or {}),
        "human_label": str(human_label or "").strip(),
        "shoot_brief": str(shoot_brief or "").strip(),
        "subtitle": str(subtitle or "").strip(),
        "vo": str(vo or "").strip(),
        "tag": str(tag or "").strip(),
        "_duration_hint": float(duration_hint) if duration_hint else 0.0,
    }


def _infer_move_from_visual(visual: str) -> str:
    """Derive move token. Reads from data/taxonomy/move_vocabulary.yaml."""
    v = (visual or "").lower()

    vocab = _load_vocabulary("move_vocabulary")
    entries = vocab.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            keywords = entry.get("keywords", [])
            token = str(entry.get("token", "")).strip()
            if not token or not isinstance(keywords, list):
                continue
            if any(str(kw).lower() in v for kw in keywords):
                return token

    return str(vocab.get("default", "static"))


def _visual_snippet(visual: str, max_len: int = 40) -> str:
    """Short snippet from visual description for card differentiation."""
    v = (visual or "").strip()
    if not v:
        return ""
    return v[:max_len] + ("\u2026" if len(v) > max_len else "")




def _visual_keyword(visual: str) -> str:
    """Extract the most distinctive keyword from visual for tag differentiation."""
    v = (visual or "").lower()
    keywords = [
        "welding", "weld", "assembly", "panel", "wiring", "electrical",
        "testing", "inspection", "certificate", "robot", "cnc", "conveyor",
        "paint", "packaging", "shipping", "warehouse", "showroom", "exterior",
        "entrance", "lobby", "product", "motor", "control", "sensor",
        "display", "award", "exhibition", "door", "frame", "steel",
        "surface", "quality", "measure", "load", "safety", "install",
    ]
    for kw in keywords:
        if kw in v:
            return kw
    words = [w for w in v.split() if len(w) > 3 and w.isalpha() and w not in (
        "factory", "shot", "visual", "clean", "stable", "clear", "quick",
        "strong", "hero", "detail", "medium", "wide", "flash",
    )]
    return words[0] if words else ""

def build_project_slots_from_creative(creative: dict) -> list[dict]:
    beats = beats_from_creative(creative)
    out: list[dict] = []

    for i, beat in enumerate(beats, start=1):
        purpose = str(beat.get("purpose") or "").strip().lower()
        visual = str(beat.get("visual") or beat.get("visual_description") or "").strip()
        subtitle = str(beat.get("subtitle") or "").strip()
        vo_text = str(beat.get("vo") or "").strip()
        duration_hint = float(beat.get("duration_hint", 0) or 0)
        scene = str(beat.get("scene") or "factory").strip()
        move = _infer_move_from_visual(visual)
        snippet = _visual_snippet(visual)
        vkw = _visual_keyword(visual)

        # ── establish_context ──────────────────────────────
        if purpose == "establish_context":
            _content = _infer_content_from_visual(visual, purpose)
            out.append(
                _project_slot(
                    beat_no=i,
                    beat_purpose=purpose,
                    request_family="opening",
                    scene=_infer_scene_from_visual(visual, scene),
                    content=_content,
                    coverage="hero",
                    move=move,
                    target=1,
                    priority="high",
                    human_label=f"Opening \u00b7 {snippet}" if snippet else "Opening / Context \u00b7 Hero Establishing",
                    shoot_brief=visual or "Upload a clean exterior, entrance, showroom, headquarters, or overall establishing visual.",
                    defaults={"intro_safe": True, "hero_safe": True, "quality_status": "approved"},
                    subtitle=subtitle,
                    vo=vo_text,
                    tag="opening_hero",
                    duration_hint=duration_hint,
                )
            )

        # ── show_capability ────────────────────────────────
        elif purpose == "show_capability":
            if duration_hint > 0 and duration_hint <= 3.0:
                med_count, det_count = 1, 0
            elif duration_hint > 0 and duration_hint <= 5.0:
                med_count, det_count = 1, 1
            else:
                med_count, det_count = 2, 1

            _cap_content = _infer_content_from_visual(visual, purpose)
            _cap_scene = _infer_scene_from_visual(visual, scene)

            med_scene = str(beat.get("medium_scene") or _cap_scene).strip() or _cap_scene
            med_content = str(beat.get("medium_content") or _cap_content).strip() or _cap_content
            med_move = str(beat.get("medium_move") or move).strip() or move or "static"

            det_scene = str(beat.get("detail_scene") or med_scene).strip() or med_scene
            det_content = str(
                beat.get("detail_content")
                or (med_content if med_scene == "showroom" else "line")
            ).strip() or (med_content if med_scene == "showroom" else "line")
            det_move_override = str(beat.get("detail_move") or "").strip()

            if isinstance(beat.get("medium_target"), (int, float)):
                med_count = max(0, int(beat.get("medium_target") or 0))
            if isinstance(beat.get("detail_target"), (int, float)):
                det_count = max(0, int(beat.get("detail_target") or 0))
            if med_count > 0:
                out.append(
                    _project_slot(
                        beat_no=i,
                        beat_purpose=purpose,
                        request_family="capability",
                        scene=med_scene,
                        content=med_content,
                        coverage="medium",
                        move=med_move,
                        target=med_count,
                        priority="high",
                        human_label=f"Capability \u00b7 {snippet}" if snippet else "Capability / Process \u00b7 Stable Medium",
                        shoot_brief=visual or "Upload process coverage that clearly shows machines, workflow, or operation in a stable medium shot.",
                        defaults={"quality_status": "approved"},
                        subtitle=subtitle,
                        vo=vo_text,
                        tag=f"capability_{vkw}" if vkw else "capability_medium",
                        duration_hint=duration_hint,
                    )
                )

            if det_count > 0:
                det_move = det_move_override or (med_move if med_move not in ("orbit", "reveal") else "static")
                out.append(
                    _project_slot(
                        beat_no=i,
                        beat_purpose=purpose,
                        request_family="capability",
                        scene=det_scene,
                        content=det_content,
                        coverage="detail",
                        move=det_move,
                        target=det_count,
                        priority="medium",
                        human_label=f"Capability Detail \u00b7 {snippet}" if snippet else "Capability / Process \u00b7 Detail Action",
                        shoot_brief=visual or "Upload clear operating detail: hands, controls, machine action, or mechanism detail.",
                        defaults={"quality_status": "approved"},
                        subtitle=subtitle,
                        tag=f"capability_detail_{vkw}" if vkw else "capability_detail",
                        duration_hint=duration_hint,
                    )
                )

        # ── build_trust ────────────────────────────────────
        elif purpose == "build_trust":
            if duration_hint > 0 and duration_hint <= 3.0:
                med_count, det_count = 1, 0
            else:
                med_count, det_count = 1, 1

            _trust_content = _infer_content_from_visual(visual, purpose)
            _trust_scene = _infer_scene_from_visual(visual, scene)
            if med_count > 0:
                out.append(
                    _project_slot(
                        beat_no=i,
                        beat_purpose=purpose,
                        request_family="trust",
                        scene=_trust_scene,
                        content=_trust_content,
                        coverage="medium",
                        move=move,
                        target=med_count,
                        priority="high",
                        human_label=f"Trust \u00b7 {snippet}" if snippet else "Trust / Proof \u00b7 Stable Support Medium",
                        shoot_brief=visual or "Upload inspection, testing, certificates, achievements, or a stable support visual.",
                        defaults={"quality_status": "approved"},
                        subtitle=subtitle,
                        vo=vo_text,
                        tag=f"trust_{vkw}" if vkw else "trust_medium",
                        duration_hint=duration_hint,
                    )
                )

            if det_count > 0:
                det_move = move if move not in ("orbit", "reveal") else "static"
                out.append(
                    _project_slot(
                        beat_no=i,
                        beat_purpose=purpose,
                        request_family="trust",
                        scene=_trust_scene,
                        content=_trust_content,
                        coverage="detail",
                        move=det_move,
                        target=det_count,
                        priority="high",
                        human_label=f"Trust Detail \u00b7 {snippet}" if snippet else "Trust / Proof \u00b7 Inspection Detail",
                        shoot_brief=visual or "Upload proof-support close detail: inspection action, certified detail, or evidence-style support shot.",
                        defaults={"quality_status": "approved"},
                        subtitle=subtitle,
                        tag=f"trust_detail_{vkw}" if vkw else "trust_detail",
                        duration_hint=duration_hint,
                    )
                )

        # ── brand_close ────────────────────────────────────
        elif purpose == "brand_close":
            _close_content = _infer_content_from_visual(visual, purpose)
            out.append(
                _project_slot(
                    beat_no=i,
                    beat_purpose=purpose,
                    request_family="close",
                    scene=_infer_scene_from_visual(visual, scene),
                    content=_close_content,
                    coverage="hero",
                    move=move,
                    target=1,
                    priority="high",
                    human_label=f"Close \u00b7 {snippet}" if snippet else "Closing / Brand Hero",
                    shoot_brief=visual or "Upload the strongest clean final hero visual suitable for closing.",
                    defaults={"outro_safe": True, "hero_safe": True, "quality_status": "approved"},
                    subtitle=subtitle,
                    vo=vo_text,
                    tag="brand_close",
                    duration_hint=duration_hint,
                )
            )

        # ── fallback (unknown purpose) ─────────────────────
        else:
            content = infer_category_from_beat(beat)
            first = True
            for shot in infer_shots_from_beat(beat):
                shot_norm = "detail" if shot in ["close"] else shot
                out.append(
                    _project_slot(
                        beat_no=i,
                        beat_purpose=purpose or "beat",
                        request_family="support",
                        scene=scene,
                        content=content,
                        coverage=shot_norm,
                        move=move,
                        target=1,
                        priority="medium",
                        human_label=f"{str(purpose or 'Support').replace('_', ' ').title()} \u00b7 {snippet}" if snippet else f"{str(purpose or 'Support').replace('_', ' ').title()} \u00b7 {shot_norm.title()}",
                        shoot_brief=visual or "Upload a clean supporting visual that matches this beat.",
                        defaults={"quality_status": "approved"},
                        subtitle=subtitle,
                        vo=vo_text if first else "",
                        tag=str(purpose or "support"),
                        duration_hint=duration_hint,
                    )
                )
                first = False

    return out

def _duration_for_project_slot(slot: Dict[str, Any]) -> float:
    """Duration source priority: beat duration_hint > slot defaults."""
    # If the slot carries a duration_hint from the beat, use it directly
    hint = slot.get("_duration_hint")
    if isinstance(hint, (int, float)) and float(hint) > 0:
        return float(hint)

    family = str(slot.get("request_family", "") or "").strip().lower()
    coverage = str(slot.get("coverage", "") or "").strip().lower()

    if family == "opening":
        return 4.2
    if family == "close":
        return 4.6
    if family == "capability" and coverage == "medium":
        return 3.1
    if family == "capability" and coverage == "detail":
        return 1.8
    if family == "trust" and coverage == "medium":
        return 2.8
    if family == "trust" and coverage == "detail":
        return 1.9

    if coverage == "hero":
        return 4.0
    if coverage == "medium":
        return 3.0
    if coverage == "detail":
        return 2.0
    return 3.0


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
    scene = safe_slug(scene).lower() or "factory-floor"
    subject, action = _legacy_subject_action_from_content(content, purpose="")
    subject = safe_slug(subject).lower() or "workspace"
    action = safe_slug(action).lower() or "display"
    coverage = _canonical_coverage_from_legacy(coverage)
    move = safe_slug(move).lower() if str(move or "").strip() else "static"

    variant = f"v{int(idx)}"
    if not ext.startswith("."):
        ext = "." + ext
    return f"{scene}_{subject}_{action}_{coverage}_{move}_{variant}{ext}"


def next_index_for(factory_dir: Path, scene: str, content: str, coverage: str, move: str, ext: str) -> int:
    scene = safe_slug(scene).lower() or "factory-floor"
    subject, action = _legacy_subject_action_from_content(content, purpose="")
    subject = safe_slug(subject).lower() or "workspace"
    action = safe_slug(action).lower() or "display"
    coverage = _canonical_coverage_from_legacy(coverage)
    move = safe_slug(move).lower() if str(move or "").strip() else "static"
    if not ext.startswith("."):
        ext = "." + ext

    core = f"{scene}_{subject}_{action}_{coverage}_{move}_v"
    pat = re.compile(rf"^{re.escape(core)}(\d\d){re.escape(ext)}$", re.IGNORECASE)
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
    try:
        from src.material_index import parse_canonical_stem
        parsed = parse_canonical_stem(path.name)
        if parsed.get("is_valid"):
            subject = str(parsed.get("subject", "") or "").strip()
            action = str(parsed.get("action", "") or "").strip()
            coverage = str(parsed.get("coverage", "") or "").strip()
            content_key = normalize_demo_content_token(_legacy_content_from_subject_action(subject, action))
            coverage_key = normalize_demo_coverage_token(coverage)
            if content_key and coverage_key:
                return content_key, coverage_key
    except Exception:
        pass

    # legacy fallback
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


def _infer_scene_from_visual(visual: str, beat_scene: str) -> str:
    """Infer scene token. Reads from data/taxonomy/scene_vocabulary.yaml."""
    v = (visual or "").strip().lower()
    s = (beat_scene or "").strip().lower()

    if s and s not in ("factory", ""):
        return s

    vocab = _load_vocabulary("scene_vocabulary")
    entries = vocab.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            keywords = entry.get("keywords", [])
            token = str(entry.get("token", "")).strip()
            if not token or not isinstance(keywords, list):
                continue
            if any(str(kw).lower() in v for kw in keywords):
                return token

    return s if s else "factory"


def _infer_content_from_visual(visual: str, purpose: str) -> str:
    """Infer content token from visual description.
    Reads from data/taxonomy/content_vocabulary.yaml.
    """
    v = (visual or "").strip().lower()
    p = (purpose or "").strip().lower()

    vocab = _load_vocabulary("content_vocabulary")
    entries = vocab.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            keywords = entry.get("keywords", [])
            token = str(entry.get("token", "")).strip()
            if not token or not isinstance(keywords, list):
                continue
            if any(str(kw).lower() in v for kw in keywords):
                return token

    fallback = vocab.get("purpose_fallback", {})
    if isinstance(fallback, dict) and p in fallback:
        return str(fallback[p])

    return "workshop"


def _infer_demo_content_token(purpose: str, visual: str) -> str:
    """Backward-compatible wrapper for compile path."""
    return _infer_content_from_visual(visual, purpose)


def _legacy_subject_action_from_content(content: str, purpose: str) -> tuple[str, str]:
    c = safe_slug(str(content or "")).lower()
    p = _normalize_purpose(str(purpose or ""))

    if c in {"product", "brand", "display"}:
        subject = "product"
    elif c in {"panel"}:
        subject = "panel"
    elif c in {"motor", "sensor", "control", "door", "frame", "steel"}:
        subject = "part"
    elif c in {"line", "automation", "machine", "robot", "cnc", "conveyor", "assembly", "wiring", "electrical", "welding"}:
        subject = "machine"
    elif c in {"testing", "inspection", "certificate", "quality", "safety", "measure", "load"}:
        subject = "workspace"
    elif c in {"warehouse", "shipping", "packaging"}:
        subject = "workspace"
    elif c in {"people", "team", "worker", "staff"}:
        subject = "person"
    else:
        subject = "workspace"

    if c in {"assembly", "wiring", "electrical", "welding"}:
        action = "assemble"
    elif c in {"testing", "inspection", "certificate", "quality", "safety", "measure", "load"}:
        action = "inspect"
    elif c in {"warehouse", "shipping", "packaging", "conveyor"}:
        action = "transport"
    elif p == "show_capability":
        action = "operate"
    elif p == "build_trust":
        action = "inspect"
    else:
        action = "display"

    return subject, action


def _legacy_content_from_subject_action(subject: str, action: str) -> str:
    s = safe_slug(str(subject or "")).lower()
    a = safe_slug(str(action or "")).lower()

    if s == "product":
        return "product"
    if s == "panel":
        return "panel"
    if s == "part":
        return "testing" if a == "inspect" else "panel"
    if s == "machine":
        return "line"
    if s == "workspace":
        if a == "inspect":
            return "testing"
        if a == "transport":
            return "warehouse"
        return "line"
    if s == "person":
        return "people"
    return "line"


def _canonical_coverage_from_legacy(token: str) -> str:
    c = safe_slug(str(token or "")).lower()
    if c in {"hero", "wide"}:
        return "wide"
    if c == "medium":
        return "medium"
    if c in {"detail", "close", "closeup"}:
        return "detail"
    return c or "medium"


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
    _ = move  # current stable path omits move tokens from generated source tags.
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
    purpose = _normalize_purpose(str(beat.get("purpose") or "").strip())
    content = _infer_demo_content_token(purpose, visual)
    dur3 = beat.get("duration_hint")
    return {
        "source": f"next:tags:{default_scene},{content},hero",
        "notes": visual if visual else None,
        "duration": float(dur3) if isinstance(dur3, (int, float)) else 3.0,
        "subtitle": subtitle or None,
        "vo": vo_clean or None,
        "tag": str(beat.get("purpose") or "beat"),
    }


def compile_creative_dict(creative: Dict[str, Any]) -> Dict[str, Any]:
    meta = creative.get("meta", {}) if isinstance(creative.get("meta"), dict) else {}
    target_len = float(meta.get("target_length", 20) or 20)

    project_slots = build_project_slots_from_creative(creative)
    seq: List[Dict[str, Any]] = []

    for slot in project_slots:
        scene = str(slot.get("scene", "") or "factory").strip()
        content = str(slot.get("content", "") or "line").strip()
        subject = str(slot.get("subject", "") or "").strip()
        action = str(slot.get("action", "") or "").strip()
        if not subject or not action:
            _derived_subject, _derived_action = _legacy_subject_action_from_content(
                content=content,
                purpose=str(slot.get("beat_purpose", "") or slot.get("request_family", "") or ""),
            )
            subject = subject or _derived_subject
            action = action or _derived_action

        coverage = str(slot.get("coverage", "") or "medium").strip()
        source_coverage = _canonical_coverage_from_legacy(coverage)
        move_tok = str(slot.get("move", "") or "").strip()

        source_tags = [scene, subject, action, source_coverage]
        if move_tok and move_tok != "static":
            source_tags.append(move_tok)
        source = "next:tags:" + ",".join([str(x).strip() for x in source_tags if str(x).strip()])

        subtitle = str(slot.get("subtitle", "") or "").strip()
        vo_text = str(slot.get("vo", "") or "").strip()
        tag = str(slot.get("tag", "") or slot.get("beat_purpose", "") or slot.get("request_family", "") or "slot").strip()
        repeat = max(1, int(slot.get("target", 1) or 1))
        duration = float(_duration_for_project_slot(slot))

        for idx in range(repeat):
            shot: Dict[str, Any] = {
                "source": source,
                "duration": duration,
                "subtitle": subtitle or None,
                "vo": vo_text if idx == 0 and vo_text else None,
                "tag": tag,
                "_beat_no": int(slot.get("beat_no", 0) or 0),
                "_beat_duration_hint": float(slot.get("_duration_hint", 0) or 0),
            }
            seq.append({k: v for k, v in shot.items() if v is not None})

    total = sum(float(s.get("duration") or 0.0) for s in seq)
    if total > 0:
        scale = float(target_len) / float(total)
        scale = max(0.85, min(1.15, scale))
        for s in seq:
            if isinstance(s.get("duration"), (int, float)):
                s["duration"] = round(float(s["duration"]) * scale, 2)

    proj = {"meta": meta, "output": {"format": "portrait_1080x1920"}, "director_profile": "content_factory"}
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


def apply_runtime_overrides_to_production_dict(
    production: Dict[str, Any],
    orientation: Optional[str] = None,
    lang: Optional[str] = None,
    model: Optional[str] = None,
    eleven_profile_path: Optional[Path] = None,
    filter_preset_name: str = "clean",
) -> Dict[str, Any]:
    d = json.loads(json.dumps(production or {}))
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

    resolved_orientation = str(orientation or "").strip().lower()
    if resolved_orientation in {"portrait", "landscape"}:
        out["format"] = "portrait_1080x1920" if resolved_orientation == "portrait" else "landscape_1920x1080"
    out.setdefault("format", "portrait_1080x1920")
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

    if lang:
        explicit_provider = str(voiceover.get("provider", "") or "").strip().lower()
        tts_settings = load_tts_routing_settings(Path(__file__).resolve().parent.parent)
        resolved_provider = resolve_tts_provider(
            language=lang,
            explicit_provider=explicit_provider,
            settings=tts_settings,
        )
        voiceover["provider"] = resolved_provider
        voiceover["language"] = lang
        if resolved_provider == "elevenlabs":
            voiceover["output_format"] = str(defaults.get("output_format", "mp3_44100_128"))
        voiceover.setdefault("volume", 1.0)

    if model:
        voiceover["model"] = model

    subtitle_lang = str(lang or voiceover.get("language") or "en-US")
    project["subtitle_style"] = get_subtitle_style(subtitle_lang)
    project["filter_preset"] = get_filter_preset(filter_preset_name)

    return d


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
    d = apply_runtime_overrides_to_production_dict(
        d,
        orientation=orientation,
        lang=lang,
        model=model,
        eleven_profile_path=eleven_profile_path,
        filter_preset_name=filter_preset_name,
    )

    compiled_path.write_text(
        yaml.safe_dump(d, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
