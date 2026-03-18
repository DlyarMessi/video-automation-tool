from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from src.subtitle_builder import build_subtitles_from_vo_events
from src.voiceover_a2 import build_voiceover_track


class _FakeAudioClip:
    def __init__(self, duration: float) -> None:
        self.duration = duration
        self.start = 0.0

    def with_start(self, start: float):
        self.start = start
        return self

    def set_start(self, start: float):
        self.start = start
        return self


class _FakeCompositeAudioClip:
    def __init__(self, clips):
        self.clips = list(clips)
        self.duration = max((clip.start + clip.duration for clip in self.clips), default=0.0)


class TimingContractTests(unittest.TestCase):
    def test_voiceover_overrun_reflows_and_warns_for_visual_extension(self) -> None:
        durations = iter([2.8, 1.2])
        dsl_shots = [
            {
                "duration": 1.0,
                "vo": "Factory reliability comes from disciplined automation.",
                "subtitle": "Disciplined automation.",
            },
            {
                "duration": 2.0,
                "vo": "Every subsystem is tested before delivery.",
                "subtitle": "Every subsystem tested.",
            },
        ]

        with patch("src.voiceover_a2.tts_synthesize", side_effect=lambda *args, **kwargs: Path("fake.mp3")), patch(
            "src.voiceover_a2.AudioFileClip", side_effect=lambda *args, **kwargs: _FakeAudioClip(next(durations))
        ), patch("src.voiceover_a2.CompositeAudioClip", _FakeCompositeAudioClip):
            result = build_voiceover_track(
                {"audio": {"voiceover": {}}},
                dsl_shots,
                total_duration=3.0,
                cache_dir=Path("/tmp/test_cache"),
            )

        self.assertIsNotNone(result)
        events = result["events"]
        self.assertAlmostEqual(events[0].start, 0.0)
        self.assertAlmostEqual(events[1].start, 2.92, places=2)
        self.assertGreater(result["timeline_duration"], 3.0)
        self.assertTrue(any("extend visuals" in w["message"] for w in result["warnings"]))

    def test_voiceover_bad_overrun_fails_fast(self) -> None:
        with patch("src.voiceover_a2.tts_synthesize", side_effect=lambda *args, **kwargs: Path("fake.mp3")), patch(
            "src.voiceover_a2.AudioFileClip", return_value=_FakeAudioClip(6.5)
        ), patch("src.voiceover_a2.CompositeAudioClip", _FakeCompositeAudioClip):
            with self.assertRaisesRegex(ValueError, "Narration timing exceeds available visual pacing budget"):
                build_voiceover_track(
                    {"audio": {"voiceover": {}}},
                    [{"duration": 2.0, "vo": "A much longer narration than the visual budget allows.", "subtitle": "Long narration."}],
                    total_duration=2.0,
                    cache_dir=Path("/tmp/test_cache"),
                )

    def test_subtitles_follow_corrected_vo_timeline(self) -> None:
        durations = iter([2.0, 1.0])
        dsl_shots = [
            {
                "duration": 1.0,
                "vo": "Precision machining keeps every lift component consistent.",
                "subtitle": "Precision machining.",
            },
            {
                "duration": 1.0,
                "vo": "Final inspection confirms smooth installation readiness.",
                "subtitle": "Final inspection ready.",
            },
        ]

        with patch("src.voiceover_a2.tts_synthesize", side_effect=lambda *args, **kwargs: Path("fake.mp3")), patch(
            "src.voiceover_a2.AudioFileClip", side_effect=lambda *args, **kwargs: _FakeAudioClip(next(durations))
        ), patch("src.voiceover_a2.CompositeAudioClip", _FakeCompositeAudioClip):
            result = build_voiceover_track(
                {"audio": {"voiceover": {}}},
                dsl_shots,
                total_duration=4.0,
                cache_dir=Path("/tmp/test_cache"),
            )

        segments = build_subtitles_from_vo_events(result["events"])
        self.assertEqual(segments[0]["text"], "Precision machining.")
        self.assertAlmostEqual(segments[0]["start"], 0.0)
        self.assertAlmostEqual(segments[1]["start"], 2.12)
        self.assertAlmostEqual(segments[1]["end"], 3.12)
        self.assertFalse(any("not tightly aligned" in w["message"] for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
