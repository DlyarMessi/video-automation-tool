# src/voiceover_a2.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from moviepy import AudioFileClip, CompositeAudioClip

# ElevenLabs / Provider router
from tts_provider import synthesize as tts_synthesize, TTSRequest


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


def extract_vo_events(
    dsl_shots: List[Dict[str, Any]],
    default_language: str,
    default_voice: str,
    default_volume: float,
) -> List[VOEvent]:
    """
    ✅ VO 是“段落级”的，而不是 shot 级
    ✅ 连续相同 vo 文案只生成一个 VOEvent
    ✅ VOEvent 是字幕与时间轴的唯一权威
    """
    t = 0.0
    events: List[VOEvent] = []

    for s in dsl_shots:
        dur = float(s.get("duration", 0) or 0)

        vo_text = s.get("vo")
        subtitle_text = s.get("subtitle") or ""

        if isinstance(vo_text, str) and vo_text.strip():
            vo_clean = vo_text.strip()

            # ✅ 如果与上一个 VOEvent 文案相同，不新建 VO
            if events and events[-1].vo_text == vo_clean:
                pass
            else:
                events.append(
                    VOEvent(
                        start=t,
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


def build_voiceover_track(
    project: dict,
    dsl_shots: List[Dict[str, Any]],
    total_duration: float,
    cache_dir: Path,
) -> Optional[Dict[str, Any]]:
    """
    ✅ 返回：
      - audio: CompositeAudioClip
      - events: List[VOEvent]（包含真实 duration + wav_path）
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
    clips = []

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
        e.duration = ac.duration
        e.wav_path = audio_path

        if e.volume != 1.0:
            if hasattr(ac, "with_volume_scaled"):
                ac = ac.with_volume_scaled(e.volume)
            else:
                from moviepy.audio.fx import all as afx
                ac = ac.fx(afx.volumex, e.volume)

        ac = ac.with_start(e.start) if hasattr(ac, "with_start") else ac.set_start(e.start)
        clips.append(ac)

    vo_audio = CompositeAudioClip(clips)

    if total_duration and total_duration > 0 and vo_audio.duration > total_duration:
        if hasattr(vo_audio, "subclipped"):
            vo_audio = vo_audio.subclipped(0, total_duration)
        else:
            vo_audio = vo_audio.subclip(0, total_duration)

    return {
        "audio": vo_audio,
        "events": events,
    }