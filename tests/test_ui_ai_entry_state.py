from __future__ import annotations

import unittest

from src.intake_models import NormalizedIntakeBrief
from src.ui_ai_entry import reset_structured_state_for_context


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


if __name__ == "__main__":
    unittest.main()
