# src/voiceover_a2.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from moviepy import AudioFileClip, CompositeAudioClip

# ElevenLabs / Provider router
from tts_provider import synthesize as tts_synthesize, TTSRequest
from duration_rescue import plan_duration_rescue

DEFAULT_VO_MIN_GAP = 0.12
DEFAULT_SEVERE_SHIFT_THRESHOLD = 0.75
DEFAULT_MAJOR_OVERRUN_THRESHOLD = 0.5
DEFAULT_WARN_OVERRUN_SECONDS = 0.75
DEFAULT_FAIL_OVERRUN_SECONDS = 3.0
DEFAULT_FAIL_OVERRUN_RATIO = 0.50

DEFAULT_PREFLIGHT_WARN_OVERRUN_SECONDS = 2.0
DEFAULT_PREFLIGHT_FAIL_OVERRUN_SECONDS = 8.0
DEFAULT_PREFLIGHT_WARN_OVERRUN_RATIO = 0.10
DEFAULT_PREFLIGHT_FAIL_OVERRUN_RATIO = 0.35


@dataclass
class VOEvent:
    start: float
    duration: float
    vo_text: str
    subtitle_text: str
    language: str
    voice: str
    volume: float
    wav_path: Path
    source_shot_index: int = -1
    requested_start: float = 0.0
    requested_duration: float = 0.0
    schedule_note: str = ""


@dataclass
class VOSchedulingWarning:
    code: str
    message: str
    event_index: int
    delta_seconds: float


def _tokenize_semantic_text(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(tok) >= 3}


def _estimate_vo_text_duration(text: str, language: str = "") -> float:
    """
    Cheap preflight estimate to avoid wasting TTS/render on obviously impossible scripts.
    English-ish text uses word rate; non-space-heavy text falls back to char rate.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return 0.0

    words = re.findall(r"[A-Za-z0-9']+", cleaned)
    if words:
        # ~144 wpm baseline, conservative enough for demo narration planning.
        return max(len(words) / 2.4, 0.8)

    # Fallback for non-space-heavy scripts.
    return max(len(cleaned) / 7.5, 0.8)


def validate_subtitle_policy(events: List[VOEvent]) -> List[VOSchedulingWarning]:
    warnings: List[VOSchedulingWarning] = []

    for idx, ev in enumerate(events, 1):
        subtitle = (ev.subtitle_text or "").strip()
        narration = (ev.vo_text or "").strip()
        if not subtitle or not narration:
            continue

        subtitle_tokens = _tokenize_semantic_text(subtitle)
        narration_tokens = _tokenize_semantic_text(narration)

        if subtitle_tokens and narration_tokens and subtitle_tokens.isdisjoint(narration_tokens):
            warnings.append(
                VOSchedulingWarning(
                    code="subtitle_semantic_mismatch",
                    message=(
                        f"Subtitle policy warning for VO {idx}: subtitle text is not tightly aligned "
                        "with narration semantics."
                    ),
                    event_index=idx,
                    delta_seconds=0.0,
                )
            )

        if len(subtitle) > len(narration) + 12:
            warnings.append(
                VOSchedulingWarning(
                    code="subtitle_too_long",
                    message=(
                        f"Subtitle policy warning for VO {idx}: subtitle text should stay shorter "
                        "than narration for demo pacing."
                    ),
                    event_index=idx,
                    delta_seconds=0.0,
                )
            )

    return warnings


def extract_vo_events(
    dsl_shots: List[Dict[str, Any]],
    default_language: str,
    default_voice: str,
    default_volume: float,
) -> List[VOEvent]:
    """
    VO 是“段落级”的，而不是 shot 级。
    连续相同 vo 文案只生成一个 VOEvent。
    """
    t = 0.0
    events: List[VOEvent] = []

    for shot_idx, s in enumerate(dsl_shots):
        dur = float(s.get("duration", 0) or 0)
        vo_text = s.get("vo")
        subtitle_text = s.get("subtitle") or ""

        if isinstance(vo_text, str) and vo_text.strip():
            vo_clean = vo_text.strip()

            if not (events and events[-1].vo_text == vo_clean):
                events.append(
                    VOEvent(
                        start=t,
                        requested_start=t,
                        requested_duration=max(dur, 0.0),
                        duration=0.0,
                        vo_text=vo_clean,
                        subtitle_text=str(subtitle_text).strip(),
                        language=str(s.get("vo_language") or default_language),
                        voice=str(s.get("vo_voice") or default_voice),
                        volume=float(s.get("vo_volume") or default_volume),
                        wav_path=Path(),
                        source_shot_index=shot_idx,
                    )
                )

        t += dur

    return events


def schedule_vo_events(
    events: List[VOEvent],
    *,
    min_gap: float = DEFAULT_VO_MIN_GAP,
    severe_shift_threshold: float = DEFAULT_SEVERE_SHIFT_THRESHOLD,
    major_overrun_threshold: float = DEFAULT_MAJOR_OVERRUN_THRESHOLD,
) -> List[VOSchedulingWarning]:
    """
    Re-schedule VO events to avoid overlap while preserving intentional larger gaps.
    """
    warnings: List[VOSchedulingWarning] = []
    prev_end = 0.0

    for idx, event in enumerate(events, 1):
        requested_start = float(event.requested_start)
        requested_gap_start = prev_end + float(min_gap) if idx > 1 else requested_start
        actual_start = max(requested_start, requested_gap_start)

        actual_duration = max(float(event.duration), 0.0)
        planned_duration = max(float(event.requested_duration), 0.0)

        shift = max(0.0, actual_start - requested_start)
        overrun = max(0.0, actual_duration - planned_duration)

        event.start = round(actual_start, 3)
        event.duration = actual_duration

        notes: List[str] = []
        if shift > 0.0:
            notes.append(f"shifted +{shift:.2f}s to prevent overlap")
        if overrun > 0.0:
            notes.append(f"tts overran planned slot by {overrun:.2f}s")
        event.schedule_note = "; ".join(notes)

        if shift >= severe_shift_threshold:
            warnings.append(
                VOSchedulingWarning(
                    code="vo_overlap_shift",
                    message=(
                        f"VO event {idx} moved by {shift:.2f}s because generated narration "
                        "exceeded available gap."
                    ),
                    event_index=idx,
                    delta_seconds=round(shift, 3),
                )
            )

        if overrun >= major_overrun_threshold:
            warnings.append(
                VOSchedulingWarning(
                    code="vo_duration_overrun",
                    message=(
                        f"VO event {idx} TTS duration exceeded the planned shot duration "
                        f"by {overrun:.2f}s."
                    ),
                    event_index=idx,
                    delta_seconds=round(overrun, 3),
                )
            )

        prev_end = actual_start + actual_duration

    return warnings


def _build_rescue_hint(
    *,
    dsl_shots: List[Dict[str, Any]],
    events: List[VOEvent],
    warnings: List[VOSchedulingWarning],
    overrun_s: float,
) -> str:
    overrun_warning = None
    for w in warnings:
        if getattr(w, "code", "") == "vo_duration_overrun":
            if overrun_warning is None or float(w.delta_seconds) > float(overrun_warning.delta_seconds):
                overrun_warning = w

    if overrun_warning and int(overrun_warning.event_index) > 0:
        event_idx = int(overrun_warning.event_index) - 1
        if 0 <= event_idx < len(events):
            anchor_index = int(events[event_idx].source_shot_index)
        else:
            anchor_index = -1
    else:
        anchor_index = int(events[-1].source_shot_index) if events else -1

    if anchor_index < 0:
        return ""

    plan = plan_duration_rescue(
        seq=dsl_shots,
        anchor_index=anchor_index,
        overrun_s=float(overrun_s),
    )

    parts: List[str] = []
    if plan.soft_extend_s > 0:
        parts.append(f"soft_extend={plan.soft_extend_s:.2f}s")

    if plan.candidates:
        top = plan.candidates[:2]
        cand_text = ", ".join([f"L{c.level}:{c.reason}@shot{c.source_index}" for c in top])
        parts.append(f"candidates={cand_text}")
    elif plan.blocked_reason:
        parts.append(plan.blocked_reason)

    return (" Rescue hint: " + " | ".join(parts)) if parts else ""


def preflight_vo_timing(
    project: dict,
    dsl_shots: List[Dict[str, Any]],
    total_duration: float,
) -> Dict[str, Any]:
    """
    Cheap timing preflight before spending TTS credits / render compute.
    Returns green / yellow / red status.
    """
    audio_cfg = project.get("audio", {}) if isinstance(project.get("audio", {}), dict) else {}
    vo_cfg = audio_cfg.get("voiceover", {}) if isinstance(audio_cfg.get("voiceover", {}), dict) else {}

    default_language = str(vo_cfg.get("language", "en-US"))
    default_voice = str(vo_cfg.get("voice", "") or "")
    default_volume = float(vo_cfg.get("volume", 1.0))

    events = extract_vo_events(
        dsl_shots,
        default_language,
        default_voice,
        default_volume,
    )

    if not events:
        return {
            "status": "green",
            "planned_visual_duration": float(total_duration or 0.0),
            "estimated_narration_duration": 0.0,
            "overrun_seconds": 0.0,
            "warnings": [],
            "summary": "Timing preflight OK: no narration events found.",
        }

    for ev in events:
        ev.duration = _estimate_vo_text_duration(ev.vo_text, ev.language)

    warnings = schedule_vo_events(events)
    estimated_timeline_duration = max((float(ev.start) + float(ev.duration) for ev in events), default=0.0)
    planned_visual_duration = float(total_duration or 0.0)
    overrun_seconds = max(0.0, estimated_timeline_duration - planned_visual_duration)
    overrun_ratio = (overrun_seconds / planned_visual_duration) if planned_visual_duration > 0 else 0.0

    status = "green"

    if overrun_seconds > 0:
        if (
            overrun_seconds >= DEFAULT_PREFLIGHT_FAIL_OVERRUN_SECONDS
            or overrun_ratio >= DEFAULT_PREFLIGHT_FAIL_OVERRUN_RATIO
        ):
            status = "red"
            warnings.append(
                VOSchedulingWarning(
                    code="vo_preflight_red",
                    message=(
                        "Timing preflight failed: estimated narration exceeds planned visual pacing "
                        f"by {overrun_seconds:.2f}s (visual={planned_visual_duration:.2f}s, "
                        f"estimated narration={estimated_timeline_duration:.2f}s)."
                    ),
                    event_index=0,
                    delta_seconds=round(overrun_seconds, 3),
                )
            )
        elif (
            overrun_seconds >= DEFAULT_PREFLIGHT_WARN_OVERRUN_SECONDS
            or overrun_ratio >= DEFAULT_PREFLIGHT_WARN_OVERRUN_RATIO
        ):
            status = "yellow"
            warnings.append(
                VOSchedulingWarning(
                    code="vo_preflight_yellow",
                    message=(
                        "Timing preflight warning: estimated narration exceeds planned visual pacing "
                        f"by {overrun_seconds:.2f}s (visual={planned_visual_duration:.2f}s, "
                        f"estimated narration={estimated_timeline_duration:.2f}s). "
                        "Script density may need reduction or visuals may need extension."
                    ),
                    event_index=0,
                    delta_seconds=round(overrun_seconds, 3),
                )
            )

    rescue_hint = _build_rescue_hint(
        dsl_shots=dsl_shots,
        events=events,
        warnings=warnings,
        overrun_s=overrun_seconds,
    ) if overrun_seconds > 0 else ""

    if status == "green":
        summary = (
            "Timing preflight OK: planned visual pacing "
            f"{planned_visual_duration:.2f}s, estimated narration {estimated_timeline_duration:.2f}s."
        )
    else:
        summary = warnings[-1].message + rescue_hint

    return {
        "status": status,
        "planned_visual_duration": planned_visual_duration,
        "estimated_narration_duration": round(estimated_timeline_duration, 3),
        "overrun_seconds": round(overrun_seconds, 3),
        "warnings": [asdict(w) for w in warnings],
        "summary": summary,
    }


def build_voiceover_track(
    project: dict,
    dsl_shots: List[Dict[str, Any]],
    total_duration: float,
    cache_dir: Path,
) -> Optional[Dict[str, Any]]:
    """
    返回：
      - audio: CompositeAudioClip
      - events: List[VOEvent]（包含真实 duration + wav_path）
      - warnings: list[dict]
      - timeline_duration: authoritative VO timeline duration
    """
    audio_cfg = project.get("audio", {}) if isinstance(project.get("audio", {}), dict) else {}
    vo_cfg = audio_cfg.get("voiceover", {}) if isinstance(audio_cfg.get("voiceover", {}), dict) else {}

    default_language = str(vo_cfg.get("language", "en-US"))
    default_voice = str(vo_cfg.get("voice", "") or "")
    default_volume = float(vo_cfg.get("volume", 1.0))
    provider = str(vo_cfg.get("provider", "elevenlabs")).strip().lower()
    model = vo_cfg.get("model")
    output_format = str(vo_cfg.get("output_format", "mp3_44100_128"))

    events = extract_vo_events(
        dsl_shots,
        default_language,
        default_voice,
        default_volume,
    )

    if not events:
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_clips = []

    for e in events:
        audio_path = tts_synthesize(
            TTSRequest(
                text=e.vo_text,
                language=e.language,
                provider=provider,
                voice=e.voice or None,
                model=model,
                output_format=output_format,
            ),
            cache_dir=cache_dir,
        )

        ac = AudioFileClip(str(audio_path))
        e.duration = float(ac.duration or 0.0)
        e.wav_path = audio_path

        if e.volume != 1.0:
            if hasattr(ac, "with_volume_scaled"):
                ac = ac.with_volume_scaled(e.volume)
            else:
                from moviepy.audio.fx import all as afx
                ac = ac.fx(afx.volumex, e.volume)

        raw_clips.append(ac)

    warnings = schedule_vo_events(events)
    warnings.extend(validate_subtitle_policy(events))

    timeline_duration = max((float(ev.start) + float(ev.duration) for ev in events), default=0.0)

    if total_duration and total_duration > 0:
        overrun = timeline_duration - float(total_duration)
        if overrun > 0:
            rescue_hint = _build_rescue_hint(
                dsl_shots=dsl_shots,
                events=events,
                warnings=warnings,
                overrun_s=overrun,
            )

            if overrun >= DEFAULT_FAIL_OVERRUN_SECONDS or overrun / float(total_duration) >= DEFAULT_FAIL_OVERRUN_RATIO:
                raise ValueError(
                    "Narration timing exceeds available visual pacing budget "
                    f"by {overrun:.2f}s (visual={float(total_duration):.2f}s, narration={timeline_duration:.2f}s)."
                    + rescue_hint
                )
            if overrun >= DEFAULT_WARN_OVERRUN_SECONDS:
                warnings.append(
                    VOSchedulingWarning(
                        code="vo_timeline_extend",
                        message=(
                            "Narration timing warning: actual VO exceeds planned visual pacing "
                            f"by {overrun:.2f}s; render will extend visuals to stay coherent."
                            + rescue_hint
                        ),
                        event_index=0,
                        delta_seconds=round(overrun, 3),
                    )
                )

    scheduled_clips = []
    for ac, event in zip(raw_clips, events):
        ac = ac.with_start(event.start) if hasattr(ac, "with_start") else ac.set_start(event.start)
        scheduled_clips.append(ac)

    vo_audio = CompositeAudioClip(scheduled_clips)

    return {
        "audio": vo_audio,
        "events": events,
        "warnings": [asdict(warning) for warning in warnings],
        "timeline_duration": timeline_duration,
    }
