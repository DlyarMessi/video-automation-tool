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
moviepy_stub.CompositeAudioClip = lambda tracks: tracks
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


class _FakeClip:
    def __init__(self, path: str = "", duration: float = 1.0, size: tuple[int, int] = (1920, 1080)) -> None:
        self.path = path
        self.duration = duration
        self.w, self.h = size
        self.write_calls: list[dict[str, object]] = []

    def subclipped(self, t_in: float, t_out: float):
        return _FakeClip(self.path, max(float(t_out) - float(t_in), 0.0), (self.w, self.h))

    def with_duration(self, duration: float):
        self.duration = duration
        return self

    def set_duration(self, duration: float):
        self.duration = duration
        return self

    def with_audio(self, audio):
        return self

    def get_frame(self, _t: float):
        return [[0]]

    def write_videofile(self, path: str, **kwargs):
        self.write_calls.append({"path": path, **kwargs})
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake-video")

    def close(self):
        return None


class _FakeFinalVideo(_FakeClip):
    pass


class RenderFPSPipelineTests(unittest.TestCase):
    def test_process_company_uses_render_default_fps_for_temp_and_subtitle_burn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_path = root / "script.yaml"
            selected_asset = root / "input_videos" / "landscape" / "Siglen" / "factory" / "clip.mp4"
            selected_asset.parent.mkdir(parents=True, exist_ok=True)
            selected_asset.write_bytes(b"video")
            script_path.write_text("timeline: []\n", encoding="utf-8")

            dsl = {
                "project": {
                    "output": {
                        "format": "landscape_1920x1080",
                        "filename": "output.mp4",
                    },
                    "audio": {
                        "voiceover": {
                            "language": "uz",
                            "provider": "elevenlabs",
                        }
                    },
                },
                "timeline": [
                    {
                        "source": str(selected_asset),
                        "duration": 1.0,
                        "vo": "Everything starts on this production floor.",
                        "subtitle": "Built where it matters.",
                    }
                ],
            }

            class PassingPlanner:
                def __init__(self, picker) -> None:
                    self.picker = picker

                def build_intent(self, shot, shot_index):
                    return SimpleNamespace(source_spec=str(shot.get("source") or ""))

                def select_primary(self, intent, shot=None):
                    return SimpleNamespace(
                        selected_path=str(selected_asset),
                        asset_id="asset-1",
                        primary_bucket_signature="factory|workspace|display",
                        style_signature="wide|static",
                        ingest_status_label="Ready",
                        fallback_level="level0_exact",
                        candidate_count=1,
                        reason="Selected direct path",
                    )

            final_video_holder: dict[str, _FakeFinalVideo] = {}

            def fake_video_file_clip(path: str, audio: bool = False):
                return _FakeClip(path=path, duration=1.0)

            def fake_concatenate_videoclips(clips, method="compose"):
                total_duration = sum(float(getattr(clip, "duration", 0.0) or 0.0) for clip in clips)
                final = _FakeFinalVideo(duration=total_duration or 1.0)
                final_video_holder["clip"] = final
                return final

            with mock.patch.object(utils, "COMPANY_CONFIG", {"Siglen": object()}), \
                 mock.patch.object(utils, "INPUT_DIR", root / "input_videos"), \
                 mock.patch.object(utils, "OUTPUT_DIR", root / "output_videos"), \
                 mock.patch.object(utils, "AllocationPlanner", PassingPlanner), \
                 mock.patch.object(utils, "load_script", return_value=dsl), \
                 mock.patch.object(utils, "apply_runtime_overrides_to_production_dict", side_effect=lambda d, **_: d), \
                 mock.patch.object(utils, "preflight_vo_timing", return_value={"warnings": [], "status": "green"}), \
                 mock.patch.object(utils, "build_voiceover_track", return_value={"audio": object(), "events": [object()], "warnings": [], "timeline_duration": 0.0}), \
                 mock.patch.object(utils, "build_subtitles_from_vo_events", return_value=[{"start": 0.0, "end": 0.8, "text": "Built where it matters."}]), \
                 mock.patch.object(utils, "VideoFileClip", side_effect=fake_video_file_clip), \
                 mock.patch.object(utils, "concatenate_videoclips", side_effect=fake_concatenate_videoclips), \
                 mock.patch.object(utils, "build_bgm_audio", return_value=None), \
                 mock.patch.object(utils, "fit_to_canvas", side_effect=lambda clip, canvas, fit_mode: clip), \
                 mock.patch.object(utils, "apply_effects", side_effect=lambda clip, effects: clip), \
                 mock.patch.object(utils, "add_watermark", side_effect=lambda clip, company_name: clip), \
                 mock.patch.object(utils, "apply_fade", side_effect=lambda clip, fi, fo: clip), \
                 mock.patch.object(utils, "_apply_filter_preset", side_effect=lambda clip, project: clip), \
                 mock.patch.object(utils, "_log_video_stream_details"), \
                 mock.patch.object(utils, "burn_subtitles_ffmpeg") as burn_mock:
                utils.process_company("Siglen", script_path=str(script_path), input_dir=str(root / "input_videos"))

            final_video = final_video_holder["clip"]
            self.assertEqual(len(final_video.write_calls), 1)
            self.assertEqual(final_video.write_calls[0]["fps"], 60)
            burn_mock.assert_called_once()
            self.assertEqual(burn_mock.call_args.kwargs["fps"], 60)


if __name__ == "__main__":
    unittest.main()
