import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from src.subtitle_builder import build_subtitles_from_vo_events
from src.voiceover_a2 import VOEvent, schedule_vo_events


class RenderTimingOutputTests(unittest.TestCase):
    def test_schedule_vo_events_prevents_overlap_and_preserves_large_gap(self):
        events = [
            VOEvent(
                start=0.0,
                requested_start=0.0,
                requested_duration=1.0,
                duration=2.2,
                vo_text="First line",
                subtitle_text="First sub",
                language="en-US",
                voice="",
                volume=1.0,
                wav_path=Path("first.mp3"),
            ),
            VOEvent(
                start=1.0,
                requested_start=1.0,
                requested_duration=1.0,
                duration=1.1,
                vo_text="Second line",
                subtitle_text="Second sub",
                language="en-US",
                voice="",
                volume=1.0,
                wav_path=Path("second.mp3"),
            ),
            VOEvent(
                start=5.0,
                requested_start=5.0,
                requested_duration=1.5,
                duration=1.0,
                vo_text="Third line",
                subtitle_text="Third sub",
                language="en-US",
                voice="",
                volume=1.0,
                wav_path=Path("third.mp3"),
            ),
        ]

        warnings = schedule_vo_events(events, min_gap=0.12, severe_shift_threshold=0.5)

        self.assertEqual(events[0].start, 0.0)
        self.assertAlmostEqual(events[1].start, 2.32, places=2)
        self.assertEqual(events[2].start, 5.0)
        self.assertTrue(any(w.code == "vo_overlap_shift" for w in warnings))
        self.assertIn("shifted", events[1].schedule_note)

    def test_subtitles_follow_rescheduled_vo_timing(self):
        events = [
            VOEvent(
                start=0.0,
                requested_start=0.0,
                requested_duration=1.0,
                duration=2.0,
                vo_text="Alpha",
                subtitle_text="",
                language="en-US",
                voice="",
                volume=1.0,
                wav_path=Path("alpha.mp3"),
            ),
            VOEvent(
                start=2.12,
                requested_start=1.0,
                requested_duration=1.0,
                duration=1.0,
                vo_text="Beta",
                subtitle_text="Beta sub",
                language="en-US",
                voice="",
                volume=1.0,
                wav_path=Path("beta.mp3"),
                schedule_note="shifted +1.12s to prevent overlap",
            ),
        ]

        segments = build_subtitles_from_vo_events(events, min_gap=0.12)

        self.assertEqual(segments[0]["text"], "Alpha")
        self.assertAlmostEqual(segments[0]["end"], 2.0, places=2)
        self.assertAlmostEqual(segments[1]["start"], 2.12, places=2)
        self.assertAlmostEqual(segments[1]["end"], 3.12, places=2)
        self.assertIn("shifted", segments[1]["note"])


if __name__ == "__main__":
    unittest.main()
