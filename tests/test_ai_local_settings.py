from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.ai_local_settings import (
    AIProviderSettings,
    load_ai_provider_settings,
    provider_settings_path,
    save_ai_provider_settings,
    save_ai_run_payload,
)
from src.ui_ai_entry import compile_intake_brief, parse_list_text
from src.intake_models import NormalizedIntakeBrief


class AILocalSettingsTests(unittest.TestCase):
    def test_load_defaults_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            settings = load_ai_provider_settings(root)
            self.assertEqual(settings.provider, "manual")
            self.assertEqual(settings.openrouter_model, "openrouter/free")

    def test_save_and_load_provider_settings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            saved = AIProviderSettings(provider="openrouter", openrouter_api_key="abc", openrouter_model="m")
            path = save_ai_provider_settings(root, saved)
            self.assertEqual(path, provider_settings_path(root))

            loaded = load_ai_provider_settings(root)
            self.assertEqual(loaded.provider, "openrouter")
            self.assertEqual(loaded.openrouter_api_key, "abc")
            self.assertEqual(loaded.openrouter_model, "m")

    def test_save_ai_run_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = save_ai_run_payload(root, {"ok": True}, brand_name="Siglen Labs")
            self.assertTrue(path.exists())
            self.assertIn("siglen_labs", path.name)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, {"ok": True})


class AIEntryHelpersTests(unittest.TestCase):
    def test_parse_list_text_dedupes_and_strips(self) -> None:
        values = parse_list_text(" proof, ROI\nproof\n,  durability ")
        self.assertEqual(values, ["proof", "ROI", "durability"])

    def test_compile_intake_brief_compile_only_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        brief = NormalizedIntakeBrief(brand_name="Siglen", objective="Show proof")

        normalized, constraints, bundle = compile_intake_brief(brief, root=root)
        self.assertEqual(normalized.brand_name, "Siglen")
        self.assertTrue(isinstance(constraints.hard_rules, list))
        self.assertIsNotNone(bundle)


if __name__ == "__main__":
    unittest.main()
