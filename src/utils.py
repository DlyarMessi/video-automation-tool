from __future__ import annotations

from voiceover_a2 import build_voiceover_track
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

logger = logging.getLogger("video_automation")

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
    """Stateful picker for 'random'/'next' patterns. Recursively scans folders."""

    MOVE_TOKENS = {
        "static", "panl", "panr", "tiltu", "tiltd", "slidel", "slider",
        "pushin", "pullout", "follow", "pov", "orbit", "reveal", "expand",
        "zoom"
    }

    def __init__(self, input_dir: Path):
        self.input_dir = input_dir
        self.pool: List[Path] = []
        video_exts = {".mp4", ".mov", ".mkv", ".m4v"}
        for p in input_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("._"):
                continue
            if p.suffix.lower() in video_exts:
                self.pool.append(p)
        self.pool.sort()
        self._idx = 0

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

    def pick(self, spec: str) -> Optional[Path]:
        if not self.pool:
            return None
        s = (spec or "").strip()
        if not s:
            return random.choice(self.pool)

        p = Path(s)
        if p.is_absolute() and p.exists():
            return p

        p2 = self.input_dir / s
        if p2.exists():
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

                    # movement tokens are optional
                    if tl in self.MOVE_TOKENS:
                        continue

                    raw = t.strip()

                    # NEW: drop long descriptive tags (they won't exist in filenames)
                    # e.g. "Factory building hero view"
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

        if mode == "random":
            return random.choice(candidates)
        if mode == "next":
            chosen = candidates[self._idx % len(candidates)]
            self._idx += 1
            return chosen
        return candidates[0]


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
):
    PLAY_RES_X = 1080
    PLAY_RES_Y = 1920
    FONT_SIZE = 48
    MARGIN_V = 140
    style = (
        f"FontName={font_name},"
        f"FontSize={FONT_SIZE},"
        f"PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,"
        f"BorderStyle=1,"
        f"Outline=2,"
        f"Shadow=0,"
        f"Alignment=2,"
        f"MarginV={MARGIN_V},"
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
    run_name = _normalize_run_name(script_file.stem)

    # ✅ output root = output_videos/{portrait|landscape}
    out_root = _resolve_output_root(orientation)
    output_dir = out_root / company_name / run_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # final output name
    out_name = out_cfg.get("filename") if isinstance(out_cfg, dict) else None
    if not out_name:
        out_name = "output.mp4"
    mp4_path = output_dir / out_name

    timeline_base = output_dir / "timeline"

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
    vo_cache = output_dir / "cache_tts"
    vo_result = build_voiceover_track(project, dsl_shots, total_duration=0, cache_dir=vo_cache)

    # =========================
    # ✅ Phase 1: 生成画面
    # =========================
    try:
        for i, s in enumerate(dsl_shots, 1):
            if not isinstance(s, dict):
                continue
            source_spec = str(s.get("source") or s.get("material") or "")
            src_path = picker.pick(source_spec)
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
            TARGET_W, TARGET_H = 1080, 1920
            src_ratio = clip.w / clip.h
            target_ratio = TARGET_W / TARGET_H
            if abs(src_ratio - target_ratio) > 0.01:
                if src_ratio > target_ratio:
                    new_w = int(clip.h * target_ratio)
                    x1 = (clip.w - new_w) // 2
                    clip = clip.crop(x1=x1, y1=0, width=new_w, height=clip.h)
                else:
                    new_h = int(clip.w / target_ratio)
                    y1 = (clip.h - new_h) // 2
                    clip = clip.crop(x1=0, y1=y1, width=clip.w, height=new_h)

            if hasattr(clip, "resized"):
                clip = clip.resized((TARGET_W, TARGET_H))
            else:
                clip = clip.with_effects([vfx.Resize((TARGET_W, TARGET_H))])

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

        tmp_mp4 = output_dir / "_render_tmp.mp4"
        logger.info("导出临时 MP4（无字幕）：%s", tmp_mp4)

        final_video.write_videofile(
            str(tmp_mp4),
            fps=FPS,
            codec=VIDEO_CODEC,
            audio_codec=AUDIO_CODEC,
            preset=PRESET,
            threads=THREADS,
            temp_audiofile=str(output_dir / f"_temp_{company_name}.m4a"),
            remove_temp=True,
        )

        did_burn = False
        if burn_subtitles:
            srt_path = timeline_base.with_suffix(".srt")
            try:
                has_srt = srt_path.exists() and srt_path.stat().st_size > 10
            except Exception:
                has_srt = False

            if has_srt:
                st = style_presets.get("subtitle") or style_presets.get("default", {})
                font_path = Path(st.get("font", FONT_PATH))
                burn_subtitles_ffmpeg(
                    video_in=tmp_mp4,
                    srt_path=srt_path,
                    video_out=mp4_path,
                    font_name=font_path.stem if font_path else "Arial",
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