from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.workflow import (
    allocate_coverage_across_beats,
    build_factory_filename,
    next_index_for,
    summarize_factory_coverage,
)


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


    def test_build_factory_filename_includes_coverage_and_move_tokens(self) -> None:
        name = build_factory_filename("Factory Floor", "Wide Shot", "closeup", "slide", 3, ".mp4")

        self.assertEqual(name, "factory_floor_workspace_display_detail_slide_v3.mp4")

    def test_next_index_for_counts_matching_scene_content_coverage_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_floor_workspace_display_detail_slide_v01.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_detail_slide_v02.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_detail_pushin_v09.mp4").write_bytes(b"x")

            nxt = next_index_for(factory_dir, "Factory Floor", "Wide Shot", "closeup", "slide", ".mp4")

        self.assertEqual(nxt, 3)


    def test_next_index_for_ignores_files_missing_required_coverage_or_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_floor_workspace_display_detail_slide_v01.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_v09.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_detail_v08.mp4").write_bytes(b"x")
            (factory_dir / "factory_floor_workspace_display_slide_v07.mp4").write_bytes(b"x")

            nxt = next_index_for(factory_dir, "Factory Floor", "Wide Shot", "closeup", "slide", ".mp4")

        self.assertEqual(nxt, 2)

    def test_summarize_factory_coverage_counts_double_factory_scene_prefix(self) -> None:
        rows = [
            {"Category": "Line", "Shot": "Hero"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            (factory_dir / "factory_factory_line_hero_static_01.mp4").write_bytes(b"x")

            summary = summarize_factory_coverage(rows, factory_dir)

        self.assertEqual(summary["total_need"], 1)
        self.assertEqual(summary["total_ready"], 0)
        self.assertEqual(summary["total_missing"], 1)

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
        self.assertEqual(summary["total_ready"], 0)
        self.assertEqual(summary["total_missing"], 2)


if __name__ == "__main__":
    unittest.main()
