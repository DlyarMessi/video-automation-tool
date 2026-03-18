from __future__ import annotations

from pathlib import Path
import unittest

from src.voiceover_a2 import preflight_vo_timing


class TimingPreflightTests(unittest.TestCase):
    def test_preflight_marks_red_for_obviously_impossible_script(self) -> None:
        dsl_shots = [
            {
                "duration": 6.0,
                "vo": " ".join(["automation"] * 80),
                "subtitle": "Automation overview.",
            }
        ]

        report = preflight_vo_timing(
            {"audio": {"voiceover": {"language": "en-US"}}},
            dsl_shots,
            total_duration=6.0,
        )

        self.assertEqual(report["status"], "red")
        self.assertGreater(report["overrun_seconds"], 0.0)
        self.assertTrue(any(w["code"] == "vo_preflight_red" for w in report["warnings"]))

    def test_preflight_marks_green_for_reasonable_script(self) -> None:
        dsl_shots = [
            {
                "duration": 8.0,
                "vo": "Factory quality control keeps installation consistent.",
                "subtitle": "Factory quality control.",
            }
        ]

        report = preflight_vo_timing(
            {"audio": {"voiceover": {"language": "en-US"}}},
            dsl_shots,
            total_duration=8.0,
        )

        self.assertEqual(report["status"], "green")
        self.assertEqual(report["overrun_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
