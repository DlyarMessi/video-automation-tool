from __future__ import annotations

from voiceover_a2 import build_voiceover_track, preflight_vo_timing
from subtitle_builder import build_subtitles_from_vo_events


def _read_render_fps(project: dict) -> int:
    try:
        output_cfg = project.get("output", {}) if isinstance(project.get("output", {}), dict) else {}
        fps = output_cfg.get("fps", 60)
        return int(fps)
    except Exception:
        return 60

# ✅ Director Engine (optional, safe)
from typing import cast, Type
try:
    from director_engine import DirectorEngine as _DirectorEngine
    DirectorEngine = cast(Type[_DirectorEngine], _DirectorEngine)
except Exception:
    DirectorEngine = None

import subprocess
import json
import os
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
    vfx,
)

try:
    from moviepy import MultiplyColor as _MultiplyColor
except Exception:
    try:
        from moviepy.video.fx.MultiplyColor import MultiplyColor as _MultiplyColor
    except Exception:
        try:
            from moviepy.video.fx.multiply_color import MultiplyColor as _MultiplyColor
        except Exception:
            _MultiplyColor = None

from config import (
    AUDIO_CODEC,
    BGM_VOLUME,
    CANVAS_PRESETS,
    COMPANY_CONFIG,
    FADEIN_SECONDS,
    FADEOUT_SECONDS,
    FONT_PATH,
    FPS,
    INPUT_DIR,
    KEEP_ORIGINAL_AUDIO,
    OUTPUT_DIR,
    PRESET,
    SCRIPT_EXT_PRIORITY,
    SCRIPTS_DIR,
    STYLE_PRESETS_LANDSCAPE,
    STYLE_PRESETS_PORTRAIT,
    THREADS,
    VIDEO_CODEC,
    WATERMARK_HEIGHT,
    WATERMARK_MARGIN,
    WATERMARK_OPACITY,
    WATERMARK_POSITION,
)

from script_loader import load_script
from material_index import load_asset_index, find_asset_record
from workflow import compile_creative_dict, apply_runtime_overrides_to_production_dict, MOVE_TOKEN_VOCAB

logger = logging.getLogger("video_automation")


def _usage_history_path() -> Path:
    base = OUTPUT_DIR
    if base.name in ("portrait", "landscape"):
        base = base.parent
    base.mkdir(parents=True, exist_ok=True)
    return base / "_usage_history.json"


def _load_usage_history() -> Dict[str, Any]:
    p = _usage_history_path()
    if not p.exists():
        return {"recent_files": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"recent_files": []}
    except Exception:
        return {"recent_files": []}


def _save_usage_history(data: Dict[str, Any]) -> None:
    p = _usage_history_path()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _remember_used_files(file_paths: List[Path], keep_last: int = 120) -> None:
    data = _load_usage_history()
    recent = data.get("recent_files", [])
    if not isinstance(recent, list):
        recent = []

    for p in file_paths:
        recent.append(str(p))

    recent = recent[-keep_last:]
    data["recent_files"] = recent
    _save_usage_history(data)


def _recently_used_set() -> set[str]:
    data = _load_usage_history()
    recent = data.get("recent_files", [])
    if not isinstance(recent, list):
        return set()
    return set(str(x) for x in recent)


def _asset_index_for_input_dir(input_dir: Path) -> Path:
    return input_dir / "factory" / "asset_index.json" if input_dir.name != "factory" else input_dir / "asset_index.json"


def _safe_float(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _apply_filter_preset(video, project: dict):
    filter_cfg = project.get("filter_preset", {}) if isinstance(project.get("filter_preset", {}), dict) else {}
    if not filter_cfg:
        return video

    enabled = bool(filter_cfg.get("enabled", False))
    name = str(filter_cfg.get("name", "clean") or "clean")

    # clean preset is intentionally very conservative
    brightness = _safe_float(filter_cfg.get("brightness", 1.0), 1.0)
    contrast = _safe_float(filter_cfg.get("contrast", 1.0), 1.0)
    saturation = _safe_float(filter_cfg.get("saturation", 1.0), 1.0)

    out = video

    try:
        if brightness != 1.0 and _MultiplyColor is not None:
            out = out.with_effects([_MultiplyColor(brightness)])
    except Exception:
        pass

    try:
        if contrast != 1.0:
            out = out.with_effects([vfx.LumContrast(0, int(round((contrast - 1.0) * 100)), 255)])
    except Exception:
        pass

    try:
        # MoviePy 2.x Effect name may differ by build; keep conservative fallback
        if saturation != 1.0:
            if hasattr(vfx, "MultiplyColor"):
                out = out.with_effects([vfx.MultiplyColor(saturation)])
            elif _MultiplyColor is not None:
                out = out.with_effects([_MultiplyColor(saturation)])
    except Exception:
        pass

    logger.info("🎨 Applied filter preset: %s", name)
    return out

# ============================================================
# ✅ NEW: orientation + run_name + dir resolver helpers
# ============================================================

def _orientation_from_format(fmt: Optional[str]) -> str:
    s = (fmt or "").strip().lower()
    return "landscape" if s.startswith("landscape") else "portrait"

def _normalize_run_name(stem: str) -> str:
    """
    Prevent output dirs like: test_run_v1.compiled/ when script is test_run_v1.compiled.yaml
    Also handle: *.shooting_guide.json naming.
    """
    name = stem
    for suffix in (".compiled", ".shooting_guide", ".shooting-guide", ".shootingguide"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name

def _resolve_output_root(orientation: str) -> Path:
    """
    OUTPUT_DIR might be:
      - output_videos
      - output_videos/portrait  (legacy in your environment)
    We normalize to base output_videos, then append orientation.
    """
    base = OUTPUT_DIR
    if base.name in ("portrait", "landscape"):
        base = base.parent
    return base / orientation

def _resolve_input_root() -> Path:
    """
    INPUT_DIR might be:
      - input_videos
      - input_videos/portrait/Siglen (legacy)
    We normalize to base input_videos.
    """
    base = INPUT_DIR
    if base.name.lower() in COMPANY_CONFIG.keys():
        # input_videos/portrait/<Company> style
        base = base.parent
    if base.name in ("portrait", "landscape"):
        base = base.parent
    return base

def _resolve_company_input_dir(company: str, orientation: str, input_dir_arg: Optional[str]) -> Path:
    """
    Priority:
      1) user provided --input:
         - can be root input_videos
         - or input_videos/portrait
         - or input_videos/portrait/<Company>
      2) fallback INPUT_DIR (normalized)
    """
    if input_dir_arg:
        p = Path(input_dir_arg).expanduser().resolve()
        # If already at .../<orientation>/<Company>
        if p.name.lower() == company.lower():
            return p
        if p.name in ("portrait", "landscape"):
            cand = p / company
            return cand if cand.exists() else p
        # root
        cand = p / orientation / company
        return cand if cand.exists() else p

    root = _resolve_input_root()
    cand = root / orientation / company
    if cand.exists():
        return cand

    # fallback: old single INPUT_DIR if user environment is single-company path
    return INPUT_DIR


# =========================
# Timeline export (VideoLingo)
# =========================
def _fmt_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000.0))
    hh = ms // 3600000
    ms -= hh * 3600000
    mm = ms // 60000
    ms -= mm * 60000
    ss = ms // 1000
    ms -= ss * 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def export_timeline_metadata(output_base: Path, segments: List[Dict[str, Any]]) -> Tuple[Path, Path]:
    json_path = output_base.with_suffix(".timeline.json")
    srt_path = output_base.with_suffix(".srt")
    json_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: List[str] = []
    srt_idx = 1
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        lines.append(str(srt_idx))
        lines.append(f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}")
        lines.append(text)
        lines.append("")
        srt_idx += 1

    srt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return json_path, srt_path


# =========================
# Legacy txt support (optional)
# =========================
@dataclass
class ShotLegacy:
    duration: float
    material: str
    caption: str


def parse_legacy_txt(script_path: Path) -> List[ShotLegacy]:
    text = script_path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    head_re = re.compile(r"^(镜头|shot)\s*\d+\s*[:：]\s*([\d.]+)\s*(秒|s|sec)?$", re.IGNORECASE)

    shots: List[ShotLegacy] = []
    i = 0
    while i < len(lines):
        m = head_re.match(lines[i])
        if not m:
            i += 1
            continue
        duration = float(m.group(2))
        if i + 2 >= len(lines):
            break
        material = lines[i + 1]
        caption_line = lines[i + 2]
        caption = caption_line
        if caption_line.startswith("文案"):
            caption = caption_line.split(":", 1)[-1].strip() if ":" in caption_line else caption_line.replace("文案", "").strip()
        shots.append(ShotLegacy(duration=duration, material=material, caption=caption))
        i += 3
    return shots


# =========================
# Material matching (recursive + flexible)
# =========================
class MaterialPicker:
    """Stateful picker for 'random'/'next' patterns with anti-repeat scheduling."""

    MOVE_TOKENS = set(MOVE_TOKEN_VOCAB)

    def __init__(self, input_dir: Path):
        self.input_dir = input_dir
        self.pool: List[Path] = []
        self._idx = 0
        self.used_in_run: set[str] = set()
        self.recently_used: set[str] = _recently_used_set()
        self.asset_index_path = _asset_index_for_input_dir(input_dir)
        self.last_picked_path: str = ""
        self.last_role: str = ""
        self.last_continuity_group: str = ""

        video_exts = {".mp4", ".mov", ".mkv", ".m4v"}
        for p in input_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("._"):
                continue
            if p.suffix.lower() in video_exts:
                self.pool.append(p)
        self.pool.sort()

    def _match_all_keywords(self, keywords: List[str]) -> List[Path]:
        if not keywords:
            return self.pool
        out: List[Path] = []
        for p in self.pool:
            try:
                hay = str(p.relative_to(self.input_dir)).lower()
            except Exception:
                hay = str(p).lower()
            if all(k.lower() in hay for k in keywords):
                out.append(p)
        return out

    def _match_regex(self, pattern: str) -> List[Path]:
        try:
            rgx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        out: List[Path] = []
        for p in self.pool:
            try:
                hay = str(p.relative_to(self.input_dir)).lower()
            except Exception:
                hay = str(p).lower()
            if rgx.search(hay):
                out.append(p)
        return out

    def _quality_rank(self, p: Path) -> int:
        rec = find_asset_record(self.asset_index_path, p.name)
        status = str(rec.get("quality_status", "") or "").strip().lower()
        if status == "approved":
            return 0
        if status == "review":
            return 1
        if status == "reject":
            return 9
        return 2

    def _asset_meta(self, p: Path) -> Dict[str, Any]:
        rec = find_asset_record(self.asset_index_path, p.name)
        if not isinstance(rec, dict):
            rec = {}
        return {
            "quality_status": str(rec.get("quality_status", "") or "").strip().lower(),
            "hero_safe": bool(rec.get("hero_safe", False)),
            "intro_safe": bool(rec.get("intro_safe", False)),
            "outro_safe": bool(rec.get("outro_safe", False)),
            "continuity_group": str(rec.get("continuity_group", "") or "").strip(),
        }

    def _selector_role(self, context: Optional[Dict[str, Any]]) -> str:
        if not isinstance(context, dict):
            return ""
        tag = str(context.get("tag", "") or "").strip().lower()
        if tag.startswith("context_") or "establish" in tag:
            return "establish_context"
        if tag.startswith("capability_") or "capability" in tag:
            return "show_capability"
        if tag.startswith("trust_") or "trust" in tag:
            return "build_trust"
        if tag.startswith("brand_") or "brand" in tag or "close" in tag:
            return "brand_close"
        return ""

    def _transition_rank(self, p: Path, context: Optional[Dict[str, Any]] = None) -> int:
        score = 0
        meta = self._asset_meta(p)
        role = self._selector_role(context)

        # never prefer the exact same file twice in a row if alternatives exist
        if self.last_picked_path and str(p) == self.last_picked_path:
            score += 9

        # role-aware soft preferences
        if role == "establish_context":
            if not meta["intro_safe"]:
                score += 2
            if not meta["hero_safe"]:
                score += 1

        elif role == "brand_close":
            if not meta["outro_safe"]:
                score += 3
            if not meta["hero_safe"]:
                score += 2

        elif role == "build_trust":
            if meta["quality_status"] and meta["quality_status"] != "approved":
                score += 1

        # continuity is a preference, not a law
        continuity_group = meta["continuity_group"]
        if (
            role
            and self.last_role
            and role == self.last_role
            and continuity_group
            and self.last_continuity_group
            and continuity_group == self.last_continuity_group
        ):
            score -= 1

        return score

    def _cooldown_rank(self, p: Path) -> int:
        return 1 if str(p) in self.recently_used else 0

    def _run_used_rank(self, p: Path) -> int:
        return 1 if str(p) in self.used_in_run else 0

    def _rank_candidates(self, candidates: List[Path], context: Optional[Dict[str, Any]] = None) -> List[Path]:
        ranked = sorted(
            candidates,
            key=lambda p: (
                self._run_used_rank(p),
                self._cooldown_rank(p),
                self._transition_rank(p, context),
                self._quality_rank(p),
                str(p),
            ),
        )
        return ranked

    def _prefer_fresh_candidates(self, candidates: List[Path]) -> List[Path]:
        if not candidates:
            return candidates

        unused_in_run = [p for p in candidates if str(p) not in self.used_in_run]
        if unused_in_run:
            candidates = unused_in_run

        not_recent = [p for p in candidates if str(p) not in self.recently_used]
        if not_recent:
            candidates = not_recent

        return candidates

    def _choose_candidate(
        self,
        candidates: List[Path],
        rotate: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        if not candidates:
            return None

        preferred = self._prefer_fresh_candidates(candidates)
        ranked = self._rank_candidates(preferred, context=context) if preferred else []
        if not ranked:
            ranked = self._rank_candidates(candidates, context=context)

        if not ranked:
            return None

        if rotate and len(ranked) > 1:
            chosen = ranked[self._idx % len(ranked)]
            self._idx += 1
        else:
            chosen = ranked[0]

        self.used_in_run.add(str(chosen))

        meta = self._asset_meta(chosen)
        self.last_picked_path = str(chosen)
        self.last_role = self._selector_role(context)
        self.last_continuity_group = str(meta.get("continuity_group", "") or "").strip()

        return chosen

    def pick(self, spec: str, context: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        if not self.pool:
            return None

        s = (spec or "").strip()
        if not s:
            return self._choose_candidate(self.pool, rotate=True, context=context)

        p = Path(s)
        if p.is_absolute() and p.exists():
            self.used_in_run.add(str(p))
            return p

        p2 = self.input_dir / s
        if p2.exists():
            self.used_in_run.add(str(p2))
            return p2

        mode = None
        inner = s
        if s.startswith("random"):
            mode = "random"
            inner = s[len("random"):].lstrip(":")
        elif s.startswith("next"):
            mode = "next"
            inner = s[len("next"):].lstrip(":")

        candidates = self.pool

        if inner.startswith("tags:"):
            tags = [t.strip() for t in inner[len("tags:"):].split(",") if t.strip()]
            candidates = self._match_all_keywords(tags)

            if not candidates and tags:
                hard_tags = []
                for t in tags:
                    tl = t.lower().strip()
                    if tl in self.MOVE_TOKENS:
                        continue
                    raw = t.strip()
                    if (" " in raw and len(raw) > 20) or len(raw) > 40:
                        continue
                    hard_tags.append(raw)
                if hard_tags:
                    candidates = self._match_all_keywords(hard_tags)

            if not candidates:
                return None

        elif inner.startswith("regex:"):
            candidates = self._match_regex(inner[len("regex:"):])
            if not candidates:
                return None

        elif inner:
            tokens = [t for t in re.split(r"\s+|,|，|;|；|\|", inner) if t]
            candidates = self._match_all_keywords(tokens)
            if not candidates:
                candidates = self.pool

        if not candidates:
            return None

        if mode == "random":
            return self._choose_candidate(candidates, rotate=True, context=context)

        if mode == "next":
            return self._choose_candidate(candidates, rotate=True, context=context)

        return self._choose_candidate(candidates, rotate=False, context=context)


# =========================
# Canvas fit (MoviePy 2.x)
# =========================
def _resized(clip, scale: float):
    if hasattr(clip, "resized"):
        return clip.resized(scale)
    return clip.with_effects([vfx.Resize(scale)])


def fit_to_canvas(clip, canvas_size: Tuple[int, int], mode: str = "cover"):
    W, H = canvas_size
    if not W or not H:
        return clip
    cw, ch = clip.size
    if (cw, ch) == (W, H):
        return clip
    mode = mode if mode in {"cover", "contain"} else "cover"
    scale = max(W / cw, H / ch) if mode == "cover" else min(W / cw, H / ch)
    resized = _resized(clip, scale)
    canvas = CompositeVideoClip([resized.with_position("center")], size=(W, H))
    return canvas.with_duration(clip.duration)


# =========================
# Watermark / Caption / Audio (MoviePy 2.x)
# =========================
def _assets_for_company(company_key: str):
    assets = COMPANY_CONFIG.get(company_key)
    if assets is None:
        return None
    if hasattr(assets, "logo") and hasattr(assets, "bgm"):
        return assets

    class Obj:
        def __init__(self, d):
            self.logo, self.bgm = d.get("logo"), d.get("bgm")
    return Obj(assets)


def add_watermark(clip, company_key: str):
    assets = _assets_for_company(company_key)
    if not assets:
        return clip
    logo_path = Path(assets.logo)
    if not logo_path.exists():
        return clip

    wm = ImageClip(str(logo_path))
    wm = wm.with_duration(clip.duration)
    wm = wm.with_opacity(WATERMARK_OPACITY)
    wm = wm.resized(height=WATERMARK_HEIGHT) if hasattr(wm, "resized") else wm.with_effects([vfx.Resize(height=WATERMARK_HEIGHT)])

    w, h = clip.size
    m = WATERMARK_MARGIN
    pos_map = {
        "top-right": (w - wm.w - m, m),
        "top-left": (m, m),
        "bottom-right": (w - wm.w - m, h - wm.h - m),
        "bottom-left": (m, h - wm.h - m),
    }
    pos = pos_map.get(WATERMARK_POSITION, pos_map["top-right"])
    wm = wm.with_position(pos)
    return CompositeVideoClip([clip, wm]).with_duration(clip.duration)


def _get_style_presets(fmt: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if (fmt or "").startswith("landscape"):
        return STYLE_PRESETS_LANDSCAPE
    return STYLE_PRESETS_PORTRAIT


def _ffmpeg_filter_escape_path(p: Path) -> str:
    s = str(p)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return s


def burn_subtitles_ffmpeg(
    video_in: Path,
    srt_path: Path,
    video_out: Path,
    font_name: str = "Arial",
    original_size: str = "1080x1920",
    font_size: int = 48,
    outline: int = 2,
    shadow: int = 0,
    margin_v: int = 140,
):
    try:
        PLAY_RES_X, PLAY_RES_Y = [int(part) for part in str(original_size).lower().split("x", 1)]
    except Exception:
        PLAY_RES_X, PLAY_RES_Y = 1080, 1920

    style = (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00101010,"
        f"BorderStyle=1,"
        f"Outline={outline},"
        f"Shadow={shadow},"
        f"Bold=0,"
        f"Spacing=0,"
        f"Alignment=2,"
        f"MarginL=72,"
        f"MarginR=72,"
        f"MarginV={margin_v},"
        f"PlayResX={PLAY_RES_X},"
        f"PlayResY={PLAY_RES_Y}"
    )
    vf = (
        f"subtitles=filename='{srt_path}':"
        f"original_size={original_size}:"
        f"force_style='{style}'"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-vf", vf,
        "-c:a", "copy",
        str(video_out),
    ]
    subprocess.run(cmd, check=True)


def _loop_audio_to_duration(audio: AudioFileClip, duration: float) -> AudioFileClip:
    if audio.duration >= duration:
        return audio.subclipped(0, duration)
    n = int(duration // audio.duration) + 1
    return concatenate_audioclips([audio] * n).subclipped(0, duration)


# =========================
# Transitions & Effects (MoviePy 2.x)
# =========================
def build_bgm_audio(project: dict, total_duration: float) -> Optional[AudioFileClip]:
    audio_cfg = project.get("audio", {}) if isinstance(project.get("audio", {}), dict) else {}
    bgm_cfg = audio_cfg.get("bgm", {}) if isinstance(audio_cfg.get("bgm", {}), dict) else {}
    bgm_file = bgm_cfg.get("file")
    if not bgm_file:
        return None

    p = Path(str(bgm_file))
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent.parent / p).resolve()
    if not p.exists():
        return None

    bgm = AudioFileClip(str(p))

    s = float(bgm_cfg.get("start", 0) or 0)
    e = bgm_cfg.get("end")
    if e is not None:
        e = float(e)
        bgm = bgm.subclip(s, min(e, bgm.duration))
    else:
        bgm = bgm.subclip(s, bgm.duration)

    if bgm.duration >= total_duration:
        bgm = bgm.subclip(0, total_duration)
    else:
        n = int(total_duration // bgm.duration) + 1
        bgm = concatenate_audioclips([bgm] * n).subclip(0, total_duration)

    vol = float(bgm_cfg.get("volume", BGM_VOLUME))
    bgm = bgm.volumex(vol)
    return bgm


def apply_fade(clip, fade_in: Optional[float], fade_out: Optional[float]):
    fi = float(FADEIN_SECONDS if fade_in is None else fade_in)
    fo = float(FADEOUT_SECONDS if fade_out is None else fade_out)
    effects = []
    if fi > 0:
        effects.append(vfx.FadeIn(fi))
    if fo > 0:
        effects.append(vfx.FadeOut(fo))
    return clip.with_effects(effects) if effects else clip


def apply_zoom(clip, start: float = 1.0, end: float = 1.06, t_start: float = 0.0, t_end: float = 1.0):
    if t_end <= t_start:
        return clip

    def scale(t: float):
        if t <= t_start:
            return start
        if t >= t_end:
            return end
        p = (t - t_start) / (t_end - t_start)
        return start + (end - start) * p

    return clip.with_effects([vfx.Resize(lambda t: scale(t))])


def apply_effects(clip, effects: Optional[list]):
    if not effects:
        return clip
    out = clip
    for ef in effects:
        if not isinstance(ef, dict):
            continue
        t = (ef.get("type") or "").lower()
        if t in {"fade", "fadeinout"}:
            out = apply_fade(out, ef.get("in"), ef.get("out"))
        elif t == "zoom":
            out = apply_zoom(
                out,
                start=float(ef.get("from", 1.0)),
                end=float(ef.get("to", 1.06)),
                t_start=float(ef.get("start", 0.0)),
                t_end=float(ef.get("end", min(1.0, out.duration))),
            )
    return out


# =========================
# DSL parsing
# =========================
def _find_script_file(company_name: str, script_path: str | None = None) -> Optional[Path]:
    if script_path:
        p = Path(script_path).expanduser().resolve()
        return p if p.exists() else None
    base = company_name.lower() + "_promo"
    for ext in SCRIPT_EXT_PRIORITY:
        p = SCRIPTS_DIR / f"{base}{ext}"
        if p.exists():
            return p
    return None


def _normalize_shots_from_dsl(dsl: dict) -> list:
    shots = dsl.get("timeline") or dsl.get("shots") or []
    if not isinstance(shots, list):
        raise ValueError("脚本的 timeline/shots 必须是数组")
    return shots


# =========================
# Main pipeline
# =========================
def process_company(company_name: str, script_path: str | None = None, input_dir: str | None = None):
    runtime_run_dir = str(os.environ.get("VIDEO_AUTOMATION_RUN_DIR", "") or "").strip()
    runtime_orientation = str(os.environ.get("VIDEO_AUTOMATION_ORIENTATION", "") or "").strip()
    runtime_lang = str(os.environ.get("VIDEO_AUTOMATION_LANG", "") or "").strip()
    runtime_model = str(os.environ.get("VIDEO_AUTOMATION_MODEL", "") or "").strip()
    runtime_filter_preset = str(os.environ.get("VIDEO_AUTOMATION_FILTER_PRESET", "clean") or "clean").strip() or "clean"
    runtime_profile_raw = str(os.environ.get("VIDEO_AUTOMATION_ELEVEN_PROFILE_PATH", "") or "").strip()
    runtime_profile_path = Path(runtime_profile_raw).expanduser().resolve() if runtime_profile_raw else None

    if company_name not in COMPANY_CONFIG:
        logger.error("未知公司：%s", company_name)
        return

    # ---- script discover ----
    if script_path:
        script_file = Path(script_path).expanduser().resolve()
        if not script_file.exists():
            logger.error("指定脚本不存在：%s", script_file)
            return
    else:
        script_file = _find_script_file(company_name)
        if not script_file:
            logger.error("未找到脚本：%s_promo.(yaml/yml/toml/json/txt)", company_name.lower())
            return

    logger.info("[%s] 使用脚本：%s", company_name, script_file.name)

    # ---- load DSL ----
    if script_file.suffix.lower() == ".txt":
        legacy = parse_legacy_txt(script_file)
        dsl_shots = [
            {
                "source": s.material,
                "duration": s.duration,
                "caption": {"text": s.caption, "style": "default"},
                "transition": {"in": {"type": "fade", "duration": FADEIN_SECONDS},
                               "out": {"type": "fade", "duration": FADEOUT_SECONDS}},
            }
            for s in legacy
        ]
        project = {"output": {"filename": f"{company_name}_Final_Promo.mp4"}}
    else:
        dsl = load_script(script_file)

        is_creative_script = (
            isinstance(dsl, dict)
            and isinstance(dsl.get("beats"), list)
            and not isinstance(dsl.get("timeline"), list)
            and not isinstance(dsl.get("shots"), list)
        )
        if is_creative_script:
            dsl = compile_creative_dict(dsl)

        if isinstance(dsl, dict):
            dsl = apply_runtime_overrides_to_production_dict(
                dsl,
                orientation=runtime_orientation or None,
                lang=runtime_lang or None,
                model=runtime_model or None,
                eleven_profile_path=runtime_profile_path,
                filter_preset_name=runtime_filter_preset,
            )

        project = dsl.get("project", {}) if isinstance(dsl.get("project", {}), dict) else {}
        dsl_shots = _normalize_shots_from_dsl(dsl)
        if not dsl_shots:
            logger.error("[%s] 脚本 timeline/shots 为空", company_name)
            return

    # =========================
    # ✅ Director Engine (Phase -1)
    # =========================
    if DirectorEngine is not None:
        profile_name = project.get("director_profile")
        if isinstance(profile_name, str) and profile_name.strip():
            try:
                profiles_dir = (
                    Path(__file__).resolve().parent
                    / "director_engine"
                    / "profiles"
                )
                engine = DirectorEngine(  # type: ignore[call-arg]
                    profile_name=profile_name,
                    profiles_dir=profiles_dir,
                )
                dsl_shots = engine.apply(dsl_shots)
                logger.info("[%s] DirectorEngine applied (profile=%s)", company_name, profile_name)
            except Exception as e:
                logger.warning("[%s] DirectorEngine failed, fallback to raw DSL: %s", company_name, e)

    # ---- output filenames/config ----
    out_cfg = project.get("output", {}) if isinstance(project.get("output", {}), dict) else {}
    fmt = out_cfg.get("format") if isinstance(out_cfg, dict) else None
    orientation = _orientation_from_format(str(fmt) if fmt else None)

    # ✅ normalize run_name (prevents *.compiled folder)
    # ✅ normalize run_name (prevents *.compiled folder)
    run_name = _normalize_run_name(script_file.stem)

    # ✅ output root = output_videos/{portrait|landscape}
    out_root = _resolve_output_root(orientation)
    if runtime_run_dir:
        output_dir = Path(runtime_run_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        internal_dir = output_dir / "_internal"
        internal_dir.mkdir(parents=True, exist_ok=True)
        run_name = output_dir.name
    elif script_file.parent.name == "_internal":
        internal_dir = script_file.parent
        output_dir = internal_dir.parent
        run_name = output_dir.name
    else:
        output_dir = out_root / company_name / run_name
        output_dir.mkdir(parents=True, exist_ok=True)
        internal_dir = output_dir / "_internal"
        internal_dir.mkdir(parents=True, exist_ok=True)

    # final output name
    out_name = out_cfg.get("filename") if isinstance(out_cfg, dict) else None
    if not out_name:
        out_name = "output.mp4"
    mp4_path = output_dir / out_name

    timeline_base = internal_dir / "timeline"

    # ---- canvas options ----
    canvas = None
    fit_mode = "cover"

    if isinstance(out_cfg, dict):
        # 1) size overrides
        if (
            out_cfg.get("size")
            and isinstance(out_cfg.get("size"), (list, tuple))
            and len(out_cfg["size"]) == 2
        ):
            canvas = (int(out_cfg["size"][0]), int(out_cfg["size"][1]))

        # 2) format preset
        if canvas is None and fmt:
            canvas = CANVAS_PRESETS.get(str(fmt))

        # 3) parse portrait_1080x1920
        if canvas is None and fmt and isinstance(fmt, str):
            s = fmt.strip()
            if "_" in s:
                s = s.split("_")[-1]
            if "x" in s:
                try:
                    w_str, h_str = s.lower().split("x", 1)
                    canvas = (int(w_str), int(h_str))
                except Exception:
                    pass

        if out_cfg.get("fit"):
            fit_mode = str(out_cfg.get("fit") or "cover")

    if canvas is None:
        canvas = CANVAS_PRESETS.get(str(PRESET)) or (1080, 1920)
        fit_mode = "cover"

    burn_subtitles = not (isinstance(out_cfg, dict) and out_cfg.get("burn_subtitles") is False)
    style_presets = _get_style_presets(str(fmt) if fmt else None)

    # ---- input dir (AUTO orientation + company) ----
    effective_input = _resolve_company_input_dir(company_name, orientation, input_dir)
    picker = MaterialPicker(effective_input)

    segments: List[Dict[str, Any]] = []
    current_t = 0.0
    final_clips = []
    opened = []

    # =========================
    # ✅ Phase 0: VO（只做一次）
    # =========================
    vo_cache = internal_dir / "cache_tts"
    planned_visual_duration = sum(
        float((shot or {}).get("duration", 0) or 0)
        for shot in dsl_shots
        if isinstance(shot, dict)
    )

    preflight = preflight_vo_timing(
        project,
        dsl_shots,
        total_duration=planned_visual_duration,
    )
    for warning in preflight.get("warnings", []):
        logger.warning("%s", warning.get("message", warning))
    if preflight.get("status") == "red":
        raise ValueError(preflight.get("summary") or "Timing preflight failed.")

    vo_result = build_voiceover_track(
        project,
        dsl_shots,
        total_duration=planned_visual_duration,
        cache_dir=vo_cache,
    )
    if vo_result:
        for warning in vo_result.get("warnings", []):
            logger.warning("%s", warning.get("message", warning))

    # =========================
    # ✅ Phase 1: 生成画面
    # =========================
    try:
        for i, s in enumerate(dsl_shots, 1):
            if not isinstance(s, dict):
                continue
            source_spec = str(s.get("source") or s.get("material") or "")
            src_path = picker.pick(source_spec, context=s)
            if not src_path:
                logger.error("找不到素材：%r", source_spec)
                return

            base = VideoFileClip(str(src_path), audio=False)
            opened.append(base)

            t_in = float(s.get("in", 0.0) or 0.0)
            t_out = s.get("out")
            dur = s.get("duration")

            if t_out is not None:
                t_out = float(t_out)
            elif dur is not None:
                t_out = t_in + float(dur)
            else:
                t_out = base.duration

            t_in = max(0.0, min(t_in, base.duration))
            t_out = max(t_in, min(float(t_out), base.duration))

            clip = base.subclipped(t_in, t_out)

            if canvas:
                clip = fit_to_canvas(clip, canvas, fit_mode)

            tr = s.get("transition") or {}
            fi = fo = None
            if isinstance(tr, dict):
                tin = tr.get("in") or {}
                tout = tr.get("out") or {}
                if isinstance(tin, dict) and tin.get("type") in {"fade", "fadein"}:
                    fi = tin.get("duration")
                if isinstance(tout, dict) and tout.get("type") in {"fade", "fadeout"}:
                    fo = tout.get("duration")

            if fi or fo:
                clip = apply_fade(clip, fi, fo)

            clip = apply_effects(clip, s.get("effects"))
            clip = add_watermark(clip, company_name)

            # ✅ 强制竖屏满屏 Crop to Fill（保留你的逻辑）
            # sizing is already handled by fit_to_canvas(clip, canvas, fit_mode)
            final_clips.append(clip)
            current_t += float(clip.duration)

        # =========================
        # ✅ Phase 2: 字幕生成（权威：VO events）
        # =========================
        segments = []
        if vo_result:
            segments = build_subtitles_from_vo_events(vo_result["events"])

        export_timeline_metadata(timeline_base, segments)
        logger.info("✅ 已导出时间轴：%s.timeline.json + %s.srt", timeline_base.name, timeline_base.name)

        # =========================
        # ✅ Phase 3: 拼视频 + 合成音轨
        # =========================
        final_video = concatenate_videoclips(final_clips, method="compose")
        vo_timeline_duration = float((vo_result or {}).get("timeline_duration", 0.0) or 0.0)
        if vo_timeline_duration > float(final_video.duration) and final_clips:
            extra_hold = vo_timeline_duration - float(final_video.duration)
            last_clip = final_clips[-1]
            freeze_frame = last_clip.get_frame(max(float(last_clip.duration) - 0.05, 0.0))
            hold_clip = ImageClip(freeze_frame)
            hold_clip = hold_clip.with_duration(extra_hold) if hasattr(hold_clip, "with_duration") else hold_clip.set_duration(extra_hold)
            final_video = concatenate_videoclips([final_video, hold_clip], method="compose")

        audio_cfg = project.get("audio", {}) if isinstance(project.get("audio", {}), dict) else {}
        ducking = float(audio_cfg.get("ducking", 1.0))
        bgm_audio = build_bgm_audio(project, final_video.duration)

        tracks = []
        if bgm_audio is not None:
            if vo_result is not None:
                bgm_audio = bgm_audio.volumex(ducking)
            tracks.append(bgm_audio)

        if vo_result is not None:
            tracks.append(vo_result["audio"])

        if tracks:
            final_video = final_video.with_audio(CompositeAudioClip(tracks))

        tmp_mp4 = internal_dir / "_render_tmp.mp4"
        logger.info("导出临时 MP4（无字幕）：%s", tmp_mp4)

        final_video.write_videofile(
            str(tmp_mp4),
            fps=FPS,
            codec=VIDEO_CODEC,
            audio_codec=AUDIO_CODEC,
            preset=PRESET,
            threads=THREADS,
            temp_audiofile=str(internal_dir / f"_temp_{company_name}.m4a"),
            remove_temp=True,
        )

        did_burn = False
        final_video = _apply_filter_preset(final_video, project)

        if burn_subtitles:
            srt_path = timeline_base.with_suffix(".srt")
            try:
                has_srt = srt_path.exists() and srt_path.stat().st_size > 10
            except Exception:
                has_srt = False

            if has_srt:
                st = style_presets.get("subtitle") or style_presets.get("default", {})
                project_subtitle_style = project.get("subtitle_style", {}) if isinstance(project.get("subtitle_style", {}), dict) else {}

                font_file = str(project_subtitle_style.get("font_file") or "").strip()
                font_name = str(project_subtitle_style.get("font_family") or "").strip()

                if font_file:
                    try:
                        font_name = Path(font_file).stem
                    except Exception:
                        pass

                if not font_name:
                    font_path = Path(st.get("font", FONT_PATH))
                    font_name = font_path.stem if font_path else "Arial"

                is_landscape = str(fmt or "").startswith("landscape")
                default_font_size = 56 if is_landscape else 54
                default_outline = 3 if is_landscape else 3
                default_shadow = 0
                default_margin_v = 72 if is_landscape else 154

                font_size = int(project_subtitle_style.get("font_size", default_font_size) or default_font_size)
                outline = int(project_subtitle_style.get("outline", default_outline) or default_outline)
                shadow = int(project_subtitle_style.get("shadow", default_shadow) or default_shadow)
                margin_v = int(project_subtitle_style.get("bottom_margin", default_margin_v) or default_margin_v)

                burn_subtitles_ffmpeg(
                    video_in=tmp_mp4,
                    srt_path=srt_path,
                    video_out=mp4_path,
                    font_name=font_name,
                    font_size=font_size,
                    outline=outline,
                    shadow=shadow,
                    margin_v=margin_v,
                    original_size=f"{final_video.w}x{final_video.h}",
                )
                did_burn = True
                logger.info("✅ 已输出最终（烧字幕）MP4：%s", mp4_path.name)
                try:
                    tmp_mp4.unlink()
                except Exception:
                    pass
            else:
                logger.warning("⚠️ 未检测到可用字幕文件（%s），将跳过烧字幕。", srt_path.name)

        if (not burn_subtitles) or (not did_burn):
            tmp_mp4.replace(mp4_path)
            logger.info("✅ 已输出最终（无字幕）MP4：%s", mp4_path.name)

    finally:
        for c in final_clips:
            try:
                c.close()
            except Exception:
                pass
        for c in opened:
            try:
                c.close()
            except Exception:
                pass
