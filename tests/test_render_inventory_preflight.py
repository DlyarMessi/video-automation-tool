from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

moviepy_stub = ModuleType("moviepy")
moviepy_stub.AudioFileClip = object
moviepy_stub.CompositeAudioClip = object
moviepy_stub.CompositeVideoClip = object
moviepy_stub.ImageClip = object
moviepy_stub.VideoFileClip = object
moviepy_stub.concatenate_audioclips = lambda *args, **kwargs: None
moviepy_stub.concatenate_videoclips = lambda *args, **kwargs: None
moviepy_stub.vfx = SimpleNamespace()
sys.modules.setdefault("moviepy", moviepy_stub)

voiceover_stub = ModuleType("voiceover_a2")
voiceover_stub.build_voiceover_track = lambda *args, **kwargs: None
voiceover_stub.preflight_vo_timing = lambda *args, **kwargs: {}
sys.modules.setdefault("voiceover_a2", voiceover_stub)

subtitle_stub = ModuleType("subtitle_builder")
subtitle_stub.build_subtitles_from_vo_events = lambda *args, **kwargs: []
sys.modules.setdefault("subtitle_builder", subtitle_stub)

from src import utils


class _StopAfterGate(RuntimeError):
    pass


class RenderInventoryPreflightTests(unittest.TestCase):
    def _make_script_path(self, root: Path) -> Path:
        script_path = root / "script.yaml"
        script_path.write_text("timeline: []\n", encoding="utf-8")
        return script_path

    def _base_dsl(self) -> dict:
        return {
            "project": {
                "output": {
                    "format": "portrait_1080x1920",
                    "filename": "output.mp4",
                }
            },
            "timeline": [
                {
                    "source": "next:tags:factory,machine,operate,medium",
                    "duration": 1.0,
                }
            ],
        }

    def test_process_company_fails_before_vo_tts_when_inventory_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_path = self._make_script_path(root)
            input_root = root / "input_videos"
            output_root = root / "output_videos"
            (input_root / "portrait" / "Siglen").mkdir(parents=True, exist_ok=True)

            class FailingPlanner:
                def __init__(self, picker) -> None:
                    self.picker = picker

                def build_intent(self, shot, shot_index):
                    return SimpleNamespace(source_spec=str(shot.get("source") or ""))

                def select_primary(self, intent, shot=None):
                    return SimpleNamespace(
                        selected_path="",
                        asset_id="",
                        primary_bucket_signature="",
                        style_signature="",
                        ingest_status_label="",
                        fallback_level="failed",
                        candidate_count=0,
                        reason="Primary bucket empty; not auto-relaxing scene/subject/action",
                    )

            with mock.patch.object(utils, "COMPANY_CONFIG", {"Siglen": object()}), \
                 mock.patch.object(utils, "INPUT_DIR", input_root), \
                 mock.patch.object(utils, "OUTPUT_DIR", output_root), \
                 mock.patch.object(utils, "MaterialPicker"), \
                 mock.patch.object(utils, "AllocationPlanner", FailingPlanner), \
                 mock.patch.object(utils, "load_script", return_value=self._base_dsl()), \
                 mock.patch.object(utils, "apply_runtime_overrides_to_production_dict", side_effect=lambda d, **_: d), \
                 mock.patch.object(utils, "preflight_vo_timing") as preflight_mock, \
                 mock.patch.object(utils, "build_voiceover_track") as tts_mock:
                with self.assertRaisesRegex(
                    ValueError,
                    r"Inventory preflight failed: shot 1: source='next:tags:factory,machine,operate,medium'; "
                    r"reason=Primary bucket empty; not auto-relaxing scene/subject/action",
                ):
                    utils.process_company("Siglen", script_path=str(script_path), input_dir=str(input_root))

                preflight_mock.assert_not_called()
                tts_mock.assert_not_called()

    def test_process_company_reaches_vo_preflight_when_inventory_preflight_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_path = self._make_script_path(root)
            input_root = root / "input_videos"
            output_root = root / "output_videos"
            selected_asset = input_root / "portrait" / "Siglen" / "factory" / "clip.mp4"
            selected_asset.parent.mkdir(parents=True, exist_ok=True)
            selected_asset.write_bytes(b"not-a-real-video")

            class PassingPlanner:
                def __init__(self, picker) -> None:
                    self.picker = picker

                def build_intent(self, shot, shot_index):
                    return SimpleNamespace(source_spec=str(shot.get("source") or ""))

                def select_primary(self, intent, shot=None):
                    return SimpleNamespace(
                        selected_path=str(selected_asset),
                        asset_id="asset-1",
                        primary_bucket_signature="factory|machine|operate",
                        style_signature="medium|static",
                        ingest_status_label="valid_allocatable",
                        fallback_level="level0_exact",
                        candidate_count=1,
                        reason="Selected exact scene+subject+action+coverage+move match",
                    )

            with mock.patch.object(utils, "COMPANY_CONFIG", {"Siglen": object()}), \
                 mock.patch.object(utils, "INPUT_DIR", input_root), \
                 mock.patch.object(utils, "OUTPUT_DIR", output_root), \
                 mock.patch.object(utils, "MaterialPicker"), \
                 mock.patch.object(utils, "AllocationPlanner", PassingPlanner), \
                 mock.patch.object(utils, "load_script", return_value=self._base_dsl()), \
                 mock.patch.object(utils, "apply_runtime_overrides_to_production_dict", side_effect=lambda d, **_: d), \
                 mock.patch.object(utils, "preflight_vo_timing", side_effect=_StopAfterGate("vo preflight reached")) as preflight_mock, \
                 mock.patch.object(utils, "build_voiceover_track") as tts_mock:
                with self.assertRaisesRegex(_StopAfterGate, "vo preflight reached"):
                    utils.process_company("Siglen", script_path=str(script_path), input_dir=str(input_root))

                preflight_mock.assert_called_once()
                tts_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
