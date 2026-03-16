from __future__ import annotations

import unittest

from src.intake_models import NormalizedIntakeBrief
from src.ui_ai_entry import (
    PENDING_ACTION_KEY,
    PENDING_STRUCTURED_BRIEF_KEY,
    STRUCTURED_FLASH_KEY,
    _apply_pending_structured_brief,
    reset_structured_state_for_context,
)


class UIAIEntryStateTests(unittest.TestCase):
    def test_reset_structured_state_for_context_reinitializes_fields_and_clears_result(self) -> None:
        session_state = {
            "ai_adv_brand_name_v2": "Old Brand",
            "ai_adv_audience_v2": "Old Audience",
            "ai_adv_notes_text_v2": "Old notes",
            "ai_structured_edited_fields_v1": {"audience", "notes"},
            "ai_entry_last_result_v1": {"mode": "compile_only"},
        }

        baseline = NormalizedIntakeBrief(
            brand_name="New Brand",
            audience="New Audience",
            language="en-US",
            orientation="portrait",
            duration_s=45,
            style_keywords=["clean"],
            notes="Fresh notes",
        )

        reset_structured_state_for_context(session_state, baseline)

        self.assertEqual(session_state["ai_adv_brand_name_v2"], "New Brand")
        self.assertEqual(session_state["ai_adv_audience_v2"], "New Audience")
        self.assertEqual(session_state["ai_adv_style_text_v2"], "clean")
        self.assertEqual(session_state["ai_adv_notes_text_v2"], "Fresh notes")
        self.assertEqual(session_state["ai_structured_edited_fields_v1"], set())
        self.assertNotIn("ai_entry_last_result_v1", session_state)


    def test_apply_pending_structured_brief_updates_widget_keys_pre_render(self) -> None:
        session_state = {
            PENDING_STRUCTURED_BRIEF_KEY: {
                "brand_name": "Northwind",
                "product_name": "Widget Pro",
                "audience": "buyers",
                "objective": "awareness",
                "language": "en-US",
                "orientation": "portrait",
                "duration_s": 45,
                "tone": "confident",
                "style_keywords": ["clean"],
                "must_include": ["demo"],
                "avoid": ["hype"],
                "available_locations": ["showroom"],
                "available_assets": ["logo"],
                "available_people": ["host"],
                "evidence_priorities": ["proof"],
                "notes": "new notes",
            }
        }
        fallback = NormalizedIntakeBrief(brand_name="Fallback", language="en-US", orientation="portrait", duration_s=30)

        applied = _apply_pending_structured_brief(session_state, fallback)

        self.assertTrue(applied)
        self.assertNotIn(PENDING_STRUCTURED_BRIEF_KEY, session_state)
        self.assertEqual(session_state["ai_adv_brand_name_v2"], "Northwind")
        self.assertEqual(session_state["ai_adv_style_text_v2"], "clean")
        self.assertEqual(session_state["ai_adv_notes_text_v2"], "new notes")

    def test_reset_structured_state_clears_pending_transient_keys(self) -> None:
        session_state = {
            PENDING_STRUCTURED_BRIEF_KEY: {"brand_name": "Ghost"},
            PENDING_ACTION_KEY: "generate",
            STRUCTURED_FLASH_KEY: {"level": "info", "message": "x"},
        }
        baseline = NormalizedIntakeBrief(brand_name="Acme", language="en-US", orientation="portrait", duration_s=45)

        reset_structured_state_for_context(session_state, baseline)

        self.assertNotIn(PENDING_STRUCTURED_BRIEF_KEY, session_state)
        self.assertNotIn(PENDING_ACTION_KEY, session_state)
        self.assertNotIn(STRUCTURED_FLASH_KEY, session_state)


if __name__ == "__main__":
    unittest.main()
