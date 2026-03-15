from __future__ import annotations

import json
import unittest
from unittest import mock
from urllib.error import HTTPError

from src.intake_models import (
    CompiledGenerationConstraints,
    NormalizedIntakeBrief,
    ScriptProviderRequest,
    StyleReference,
)
from src.script_provider_openrouter import OpenRouterProviderError, OpenRouterScriptProvider


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OpenRouterProviderTests(unittest.TestCase):
    def _request(self) -> ScriptProviderRequest:
        return ScriptProviderRequest(
            brief=NormalizedIntakeBrief(
                brand_name="Siglen",
                objective="show quality proof",
                audience="procurement",
                style_keywords=["technical"],
            ),
            constraints=CompiledGenerationConstraints(
                required_topics=["Testing & Quality"],
                required_evidence=["inspection detail"],
                preferred_moves=["static"],
                acceptable_moves=["static", "slide"],
                avoid_moves=["orbit"],
                hard_rules=["RULE:canonical_tuple_required: ..."],
                soft_preferences=["Audience alignment required: procurement"],
            ),
            style_references=[StyleReference(ref_id="r1", title="Ref", content="Industrial", tags=["industrial"])],
            provider_hints=["keep concise"],
        )

    def test_prompt_builder_includes_core_context(self) -> None:
        provider = OpenRouterScriptProvider(api_key="k")
        prompt = provider.build_prompt(self._request())
        self.assertIn("Siglen", prompt)
        self.assertIn("Testing & Quality", prompt)
        self.assertIn("inspection detail", prompt)
        self.assertIn("r1", prompt)
        self.assertIn("keep concise", prompt)

    def test_missing_api_key_raises_clear_error(self) -> None:
        provider = OpenRouterScriptProvider(api_key="")
        with self.assertRaises(OpenRouterProviderError) as ctx:
            provider.generate(self._request())
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    def test_generate_parses_mock_openrouter_response(self) -> None:
        provider = OpenRouterScriptProvider(api_key="k")
        model_json = {
            "script_draft": {
                "title": "Siglen Draft",
                "key_message": "Quality proof",
                "creative_brief": "Brief",
                "sections": [
                    {
                        "section_id": "S01",
                        "purpose": "Intro",
                        "narration": "Narr",
                        "on_screen_text": "Text",
                        "success_criteria": "Criteria",
                        "evidence_needed": ["inspection detail"],
                        "preferred_scene": ["factory"],
                        "acceptable_scene": ["tower"],
                        "preferred_move": ["static"],
                        "acceptable_move": ["slide"],
                        "avoid_move": ["orbit"],
                        "fallback": "Fallback",
                        "notes": "Notes",
                    }
                ],
                "warnings": [],
            },
            "pool_plan_draft": {"rows": [], "warnings": []},
            "unresolved_risks": [],
            "confidence_notes": ["ok"],
        }
        api_payload = {
            "choices": [
                {"message": {"content": json.dumps(model_json)}}
            ]
        }

        with mock.patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(api_payload)):
            out = provider.generate(self._request())

        self.assertEqual(out.script_draft.title, "Siglen Draft")
        self.assertEqual(out.script_draft.sections[0].section_id, "S01")
        self.assertEqual(out.confidence_notes, ["ok"])

    def test_headers_use_openrouter_title_header(self) -> None:
        provider = OpenRouterScriptProvider(api_key="k", site_url="https://example.com", app_name="VideoTool")
        headers = provider._headers()
        self.assertEqual(headers.get("HTTP-Referer"), "https://example.com")
        self.assertEqual(headers.get("X-OpenRouter-Title"), "VideoTool")
        self.assertNotIn("X-Title", headers)

    def test_http_error_includes_response_body_when_available(self) -> None:
        provider = OpenRouterScriptProvider(api_key="k")
        err = HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=None,
        )
        err.read = lambda: b'{"error":"invalid request"}'  # type: ignore[attr-defined]

        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(OpenRouterProviderError) as ctx:
                provider.generate(self._request())

        self.assertIn("HTTP 400", str(ctx.exception))
        self.assertIn("invalid request", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
