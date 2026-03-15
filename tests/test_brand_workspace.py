from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.brand_workspace import (
    build_managed_brand_paths,
    delete_brand_workspace,
    provision_brand_workspace,
    scan_brand_workspace,
)
from src.workflow import safe_slug


class BrandWorkspaceTests(unittest.TestCase):
    def test_provision_scan_delete_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input_videos"

            created = provision_brand_workspace(root=root, company="Acme Corp", slugify=safe_slug, input_root=input_root)
            self.assertTrue(any((root / "data" / "brands" / "acme_corp") == p for p in created))
            self.assertTrue((input_root / "portrait" / "Acme Corp" / "_INBOX").exists())

            sample_file = root / "creative_scripts" / "Acme Corp" / "draft.yaml"
            sample_file.parent.mkdir(parents=True, exist_ok=True)
            sample_file.write_text("beats: []\n", encoding="utf-8")

            scan = scan_brand_workspace(root=root, company="Acme Corp", slugify=safe_slug, input_root=input_root)
            self.assertTrue(scan["any_exists"])
            self.assertGreaterEqual(scan["total_files"], 1)

            deleted = delete_brand_workspace(root=root, company="Acme Corp", slugify=safe_slug, input_root=input_root)
            self.assertTrue(any("creative_scripts/Acme Corp" in p for p in deleted["deleted"]))
            self.assertFalse((root / "creative_scripts" / "Acme Corp").exists())

    def test_managed_paths_are_single_source_of_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input_videos"
            paths = build_managed_brand_paths(root=root, company="My Brand", slugify=safe_slug, input_root=input_root)
            keys = [p.key for p in paths]
            self.assertEqual(
                keys,
                [
                    "brand_data",
                    "creative_scripts",
                    "input_portrait",
                    "input_landscape",
                    "output_portrait",
                    "output_landscape",
                ],
            )


if __name__ == "__main__":
    unittest.main()
