from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_VO_MIN_GAP = 0.12
DEFAULT_SEVERE_SHIFT_THRESHOLD = 0.75
DEFAULT_MAJOR_OVERRUN_THRESHOLD = 0.5


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


def extract_vo_events(
    dsl_shots: List[Dict[str, Any]],
    default_language: str,
    default_voice: str,
    default_volume: float,
) -> List[VOEvent]:
    """
    VO 是段落级，而不是 shot 级。
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
                        duration=0.0,
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
                        f"VO event {idx} moved by {shift:.2f}s because generated narration exceeded available gap."
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
                        f"VO event {idx} TTS duration exceeded the planned shot duration by {overrun:.2f}s."
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
    返回:
      - audio: CompositeAudioClip
      - events: List[VOEvent]
      - warnings: scheduling warnings
    """
    from moviepy import AudioFileClip, CompositeAudioClip
    from tts_provider import TTSRequest, synthesize as tts_synthesize

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

    scheduled_clips = []
    for ac, event in zip(raw_clips, events):
        ac = ac.with_start(event.start) if hasattr(ac, "with_start") else ac.set_start(event.start)
        scheduled_clips.append(ac)

    vo_audio = CompositeAudioClip(scheduled_clips)

    if total_duration and total_duration > 0 and vo_audio.duration > total_duration:
        if hasattr(vo_audio, "subclipped"):
            vo_audio = vo_audio.subclipped(0, total_duration)
        else:
            vo_audio = vo_audio.subclip(0, total_duration)

    return {
        "audio": vo_audio,
        "events": events,
        "warnings": [warning.__dict__ for warning in warnings],
    }
