from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.workflow import build_factory_filename, next_index_for


class PoolFillCanonicalSaveTests(unittest.TestCase):
    """
    Guard against Pool Fill save using legacy-derived subject/action instead of
    the card's explicit canonical values.

    Fixture: content="shipping" legacy-derives to action="transport" (workspace→transport
    branch in _legacy_subject_action_from_content).  With explicit subject/action the
    legacy derivation must be skipped entirely.
    """

    _CONTENT_THAT_DERIVES_TRANSPORT = "shipping"

    def test_build_factory_filename_uses_explicit_subject_action_not_legacy(self) -> None:
        name = build_factory_filename(
            "factory",
            self._CONTENT_THAT_DERIVES_TRANSPORT,
            "medium",
            "static",
            1,
            ".mp4",
            subject="workspace",
            action="display",
        )
        self.assertIn("display", name, "filename must contain explicit action 'display'")
        self.assertNotIn("transport", name, "filename must not contain legacy-derived action 'transport'")

    def test_build_factory_filename_legacy_path_still_derives_transport(self) -> None:
        """Confirm the legacy path still derives transport so the fixture assumption holds."""
        name = build_factory_filename(
            "factory",
            self._CONTENT_THAT_DERIVES_TRANSPORT,
            "medium",
            "static",
            1,
            ".mp4",
        )
        self.assertIn("transport", name, "legacy path must still derive action 'transport' from 'shipping'")

    def test_next_index_for_uses_explicit_subject_action_not_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp)
            # Seed two files using the explicit canonical name (display)
            (factory_dir / "factory_workspace_display_medium_static_v01.mp4").write_bytes(b"x")
            (factory_dir / "factory_workspace_display_medium_static_v02.mp4").write_bytes(b"x")
            # Also place a file that the legacy path would match (transport) — must NOT be counted
            (factory_dir / "factory_workspace_transport_medium_static_v01.mp4").write_bytes(b"x")

            nxt = next_index_for(
                factory_dir,
                "factory",
                self._CONTENT_THAT_DERIVES_TRANSPORT,
                "medium",
                "static",
                ".mp4",
                subject="workspace",
                action="display",
            )

        self.assertEqual(nxt, 3, "next index must be 3, counting only display files not transport files")


if __name__ == "__main__":
    unittest.main()
