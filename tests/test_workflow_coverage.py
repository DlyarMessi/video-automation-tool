from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.workflow import allocate_coverage_across_beats, summarize_factory_coverage


class WorkflowCoverageTests(unittest.TestCase):
    def test_allocate_coverage_across_beats_consumes_shared_inventory(self) -> None:
        beat_needs = [
            {("line", "wide"): 1},
            {("line", "wide"): 1},
            {("line", "wide"): 1},
        ]
        available = {("line", "wide"): 2}

        out = allocate_coverage_across_beats(beat_needs, available)

        self.assertEqual(out[0][("line", "wide")], (1, 0))
        self.assertEqual(out[1][("line", "wide")], (1, 0))
        self.assertEqual(out[2][("line", "wide")], (0, 1))

    def test_summarize_factory_coverage_slug_normalizes_row_values(self) -> None:
        rows = [
            {"Category": "Factory Line", "Shot": "Wide Shot"},
            {"Category": "Factory Line", "Shot": "Wide Shot"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_factory_line_wide_shot_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 2)
        self.assertEqual(summary["total_ready"], 1)
        self.assertEqual(summary["total_missing"], 1)


if __name__ == "__main__":
    unittest.main()
