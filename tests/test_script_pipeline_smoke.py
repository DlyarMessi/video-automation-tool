from __future__ import annotations

import unittest

from src.intake_compiler import CompilerBundle
from src.intake_models import (
    NormalizedIntakeBrief,
    PoolPlanDraft,
    ScriptDraft,
    ScriptProviderRequest,
    ScriptProviderResponse,
    ScriptSectionDraft,
    StyleReference,
)
from src.script_pipeline import run_script_pipeline
from src.script_provider_base import ScriptProvider
from src.script_provider_manual import ManualScriptProvider


class _CapturingProvider(ScriptProvider):
    provider_name = "capturing"

    def __init__(self) -> None:
        self.last_request: ScriptProviderRequest | None = None

    def generate(self, request: ScriptProviderRequest) -> ScriptProviderResponse:
        self.last_request = request
        return ScriptProviderResponse(
            script_draft=ScriptDraft(
                title="T",
                key_message="K",
                creative_brief="B",
                sections=[
                    ScriptSectionDraft(
                        section_id="S01",
                        purpose="P",
                        narration="N",
                        on_screen_text="O",
                        success_criteria="C",
                    )
                ],
            ),
            pool_plan_draft=PoolPlanDraft(rows=[]),
        )


class ScriptPipelineSmokeTests(unittest.TestCase):
    def test_pipeline_runs_with_manual_provider(self) -> None:
        brief = NormalizedIntakeBrief(
            brand_name="Siglen",
            objective="show factory reliability",
            audience="buyers",
            style_keywords=["proof"],
        )
        bundle = CompilerBundle(
            canonical_registry={"entries": {"factory.building.wide.static": {}}},
            combo_rules={},
            intent_mappings={"mappings": []},
        )
        provider = ManualScriptProvider()

        result = run_script_pipeline(brief=brief, provider=provider, bundle=bundle)
        self.assertEqual(result.normalized_brief.brand_name, "Siglen")
        self.assertTrue(result.compiled_constraints.orientation in {"portrait", "landscape"})
        self.assertTrue(result.provider_response.script_draft.title)
        self.assertGreaterEqual(len(result.provider_response.script_draft.sections), 1)

    def test_pipeline_passes_style_references_to_provider(self) -> None:
        brief = NormalizedIntakeBrief(brand_name="Siglen")
        bundle = CompilerBundle(canonical_registry={"entries": {}}, combo_rules={}, intent_mappings={"mappings": []})
        provider = _CapturingProvider()
        refs = [StyleReference(ref_id="r1", title="Ref", content="Text", tags=["industrial"])]

        result = run_script_pipeline(
            brief=brief,
            provider=provider,
            bundle=bundle,
            style_references=refs,
        )

        self.assertIsNotNone(provider.last_request)
        self.assertEqual(len(provider.last_request.style_references), 1)
        self.assertEqual(provider.last_request.style_references[0].ref_id, "r1")
        self.assertEqual(result.provider_response.script_draft.title, "T")


if __name__ == "__main__":
    unittest.main()
