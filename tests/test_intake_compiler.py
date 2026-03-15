from __future__ import annotations

import unittest

from src.intake_compiler import CompilerBundle, compile_brief_to_constraints
from src.intake_models import NormalizedIntakeBrief


class IntakeCompilerTests(unittest.TestCase):
    def test_compiler_returns_meaningful_constraints(self) -> None:
        brief = NormalizedIntakeBrief(
            brand_name="Siglen",
            objective="show quality proof",
            audience="B2B buyers",
            evidence_priorities=["testing proof", "factory consistency"],
            style_keywords=["technical", "premium"],
            available_assets=["drone"],
        )
        bundle = CompilerBundle(
            canonical_registry={
                "entries": {
                    "factory.testing.detail.static": {
                        "canonical": {"move": "static"},
                        "purpose": "proof",
                    },
                    "factory.building.hero.orbit": {"canonical": {"move": "orbit"}},
                    "factory.automation.medium.slide": {"canonical": {"move": "slide"}},
                    "factory.automation.medium.pushin": {"canonical": {"move": "pushin"}},
                    "factory.automation.wide.reveal": {"canonical": {"move": "reveal"}},
                }
            },
            combo_rules={"allowed_overrides": []},
            intent_mappings={
                "current_reference_intents": ["testing & quality"],
                "mappings": [
                    {
                        "objective_keywords": ["quality", "proof"],
                        "required_topics": ["Testing & Quality"],
                        "required_evidence": ["inspection detail"],
                    }
                ],
            },
        )

        out = compile_brief_to_constraints(brief, bundle)
        self.assertIn("Testing & Quality", out.required_topics)
        self.assertIn("inspection detail", out.required_evidence)
        self.assertIn("testing proof", out.required_evidence)
        self.assertNotIn("B2B buyers", " ".join(out.required_evidence))
        self.assertIn("Audience alignment required: B2B buyers", out.soft_preferences)
        self.assertIn("purpose", out.required_semantic_fields)
        self.assertIn("orbit", out.preferred_moves)
        self.assertIn("RULE:canonical_tuple_required:", out.hard_rules[0])
        self.assertTrue(any("combo_rules bundle is loaded" in w for w in out.warnings))

    def test_must_include_prefix_routing(self) -> None:
        brief = NormalizedIntakeBrief(
            brand_name="Siglen",
            must_include=["topic:Factory Strength", "evidence:inspection detail", "unprefixed-item"],
        )
        bundle = CompilerBundle(
            canonical_registry={"entries": {"factory.testing.detail.static": {"canonical": {"move": "static"}}}},
            combo_rules={},
            intent_mappings={"mappings": []},
        )

        out = compile_brief_to_constraints(brief, bundle)
        self.assertIn("Factory Strength", out.required_topics)
        self.assertIn("inspection detail", out.required_evidence)
        self.assertIn("unprefixed-item", out.required_topics)
        self.assertTrue(any("must_include item treated as topic" in w for w in out.warnings))

    def test_acceptable_moves_filtered_by_governed_vocab(self) -> None:
        brief = NormalizedIntakeBrief(brand_name="Siglen", style_keywords=["technical"])
        bundle = CompilerBundle(
            canonical_registry={
                "entries": {
                    "k1": {"canonical": {"move": "static"}},
                    "k2": {"canonical": {"move": "slide"}},
                }
            },
            combo_rules={},
            intent_mappings={"mappings": []},
        )

        out = compile_brief_to_constraints(brief, bundle)
        self.assertEqual(out.acceptable_moves, ["static", "slide"])
        self.assertTrue(any("acceptable_move 'pushin' dropped" in w for w in out.warnings))


if __name__ == "__main__":
    unittest.main()
