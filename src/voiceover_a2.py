# src/voiceover_a2.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from moviepy import AudioFileClip, CompositeAudioClip

# ElevenLabs / Provider router
from tts_provider import synthesize as tts_synthesize, TTSRequest

DEFAULT_VO_MIN_GAP = 0.12
DEFAULT_SEVERE_SHIFT_THRESHOLD = 0.75
DEFAULT_MAJOR_OVERRUN_THRESHOLD = 0.5
DEFAULT_WARN_OVERRUN_SECONDS = 0.75
DEFAULT_FAIL_OVERRUN_SECONDS = 3.0
DEFAULT_FAIL_OVERRUN_RATIO = 0.50


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

    for s in dsl_shots:
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
                        duration=0.0,  # 稍后由音频长度决定
                        vo_text=vo_clean,
                        subtitle_text=str(subtitle_text).strip(),
                        language=str(s.get("vo_language") or default_language),
                        voice=str(s.get("vo_voice") or default_voice),
                        volume=float(s.get("vo_volume") or default_volume),
                        wav_path=Path(),
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
            if overrun >= DEFAULT_FAIL_OVERRUN_SECONDS or overrun / float(total_duration) >= DEFAULT_FAIL_OVERRUN_RATIO:
                raise ValueError(
                    "Narration timing exceeds available visual pacing budget "
                    f"by {overrun:.2f}s (visual={float(total_duration):.2f}s, narration={timeline_duration:.2f}s)."
                )
            if overrun >= DEFAULT_WARN_OVERRUN_SECONDS:
                warnings.append(
                    VOSchedulingWarning(
                        code="vo_timeline_extend",
                        message=(
                            "Narration timing warning: actual VO exceeds planned visual pacing "
                            f"by {overrun:.2f}s; render will extend visuals to stay coherent."
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
