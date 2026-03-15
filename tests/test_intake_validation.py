from __future__ import annotations

import unittest

from src.intake_models import NormalizedIntakeBrief
from src.intake_validation import IntakeValidationError, normalize_and_validate_brief


class IntakeValidationTests(unittest.TestCase):
    def test_invalid_orientation_rejected(self) -> None:
        brief = NormalizedIntakeBrief(brand_name="Siglen", orientation="square")
        with self.assertRaises(IntakeValidationError):
            normalize_and_validate_brief(brief)

    def test_empty_brand_rejected(self) -> None:
        brief = NormalizedIntakeBrief(brand_name="   ")
        with self.assertRaises(IntakeValidationError):
            normalize_and_validate_brief(brief)

    def test_list_cleanup_and_dedupe(self) -> None:
        brief = NormalizedIntakeBrief(
            brand_name="Siglen",
            style_keywords=[" proof ", "", "Proof", "technical"],
        )
        normalized = normalize_and_validate_brief(brief)
        self.assertEqual(normalized.style_keywords, ["proof", "technical"])


if __name__ == "__main__":
    unittest.main()
