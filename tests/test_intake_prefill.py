from __future__ import annotations

import unittest

from src.intake_models import NormalizedIntakeBrief
from src.intake_prefill import (
    build_merged_brief_from_quick_input,
    infer_brief_from_quick_input,
    merge_brief_preserving_user_fields,
)


class IntakePrefillTests(unittest.TestCase):
    def test_infer_brief_from_quick_input_extracts_key_fields(self) -> None:
        brief, notes = infer_brief_from_quick_input(
            quick_brief="""Audience: Facility managers
Objective: show reliability
Must include: testing line, closeup detail
Style: clean, premium""",
            company="Acme",
            output_language="en-US",
            orientation="portrait",
            duration_s=45,
            emphasis="Proof & evidence",
            has_existing_footage="Partially",
        )

        self.assertEqual(brief.brand_name, "Acme")
        self.assertEqual(brief.audience, "Facility managers")
        self.assertEqual(brief.objective, "show reliability")
        self.assertIn("testing line", brief.must_include)
        self.assertIn("premium", brief.style_keywords)
        self.assertIn("quality detail", brief.evidence_priorities)
        self.assertIn("pool gap closure", notes["footage"])

    def test_merge_preserves_user_edited_fields(self) -> None:
        current = NormalizedIntakeBrief(
            brand_name="Acme",
            audience="User Edited Audience",
            language="fr-FR",
            duration_s=60,
            style_keywords=["user-style"],
        )
        inferred = NormalizedIntakeBrief(
            brand_name="Acme",
            audience="Inferred Audience",
            language="en-US",
            duration_s=30,
            style_keywords=["inferred-style"],
        )

        merged = merge_brief_preserving_user_fields(
            current=current,
            inferred=inferred,
            edited_fields={"audience", "style_keywords"},
        )

        self.assertEqual(merged.audience, "User Edited Audience")
        self.assertEqual(merged.style_keywords, ["user-style"])
        self.assertEqual(merged.language, "en-US")
        self.assertEqual(merged.duration_s, 30)

    def test_build_merged_brief_from_quick_input_respects_edited_fields(self) -> None:
        current = NormalizedIntakeBrief(
            brand_name="Acme",
            audience="Existing Audience",
            objective="Existing Objective",
            language="fr-FR",
            orientation="portrait",
            duration_s=45,
        )

        merged = build_merged_brief_from_quick_input(
            current=current,
            edited_fields={"audience"},
            quick_brief="Audience: New Audience\nObjective: New Objective",
            company="Acme",
            output_language="en-US",
            orientation="landscape",
            duration_s=60,
            emphasis="Balanced",
            has_existing_footage="Yes",
        )

        self.assertEqual(merged.audience, "Existing Audience")
        self.assertEqual(merged.objective, "New Objective")
        self.assertEqual(merged.language, "en-US")
        self.assertEqual(merged.orientation, "landscape")
        self.assertEqual(merged.duration_s, 60)


if __name__ == "__main__":
    unittest.main()
