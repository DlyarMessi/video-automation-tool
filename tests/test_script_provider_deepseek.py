from __future__ import annotations

import json
import unittest
from unittest import mock
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError

from src.intake_models import (
    CompiledGenerationConstraints,
    NormalizedIntakeBrief,
    ScriptProviderRequest,
    StyleReference,
)
from src.script_provider_deepseek import DeepSeekProviderError, DeepSeekScriptProvider


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DeepSeekProviderTests(unittest.TestCase):
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
        provider = DeepSeekScriptProvider(api_key="k")
        prompt = provider.build_prompt(self._request())
        self.assertIn("Siglen", prompt)
        self.assertIn("Testing & Quality", prompt)
        self.assertIn("inspection detail", prompt)
        self.assertIn("r1", prompt)
        self.assertIn("keep concise", prompt)

    def test_missing_api_key_raises_clear_error(self) -> None:
        provider = DeepSeekScriptProvider(api_key="")
        with self.assertRaises(DeepSeekProviderError) as ctx:
            provider.generate(self._request())
        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))

    def test_generate_parses_mock_response(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")
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

    def test_retries_once_without_response_format_when_unsupported(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")
        model_json = {
            "script_draft": {
                "title": "Siglen Draft",
                "key_message": "Quality proof",
                "creative_brief": "Brief",
                "sections": [],
                "warnings": [],
            },
            "pool_plan_draft": {"rows": [], "warnings": []},
            "unresolved_risks": [],
            "confidence_notes": [],
        }
        api_payload = {"choices": [{"message": {"content": json.dumps(model_json)}}]}

        seen_payloads: list[dict] = []

        def _mock_urlopen(req, timeout=0):
            payload = json.loads(req.data.decode("utf-8"))  # type: ignore[arg-type]
            seen_payloads.append(payload)
            if len(seen_payloads) == 1:
                err = HTTPError(
                    url="https://api.deepseek.com/chat/completions",
                    code=400,
                    msg="Bad Request",
                    hdrs=None,
                    fp=None,
                )
                err.read = lambda: b'{"error":{"message":"unsupported parameter: response_format json_object"}}'  # type: ignore[attr-defined]
                raise err
            return _FakeHTTPResponse(api_payload)

        with mock.patch("urllib.request.urlopen", side_effect=_mock_urlopen):
            out = provider.generate(self._request())

        self.assertEqual(out.script_draft.title, "Siglen Draft")
        self.assertEqual(len(seen_payloads), 2)
        self.assertIn("response_format", seen_payloads[0])
        self.assertNotIn("response_format", seen_payloads[1])


    def test_retries_once_on_remote_disconnect_and_succeeds(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")
        model_json = {
            "script_draft": {
                "title": "Siglen Draft",
                "key_message": "Quality proof",
                "creative_brief": "Brief",
                "sections": [],
                "warnings": [],
            },
            "pool_plan_draft": {"rows": [], "warnings": []},
            "unresolved_risks": [],
            "confidence_notes": [],
        }
        api_payload = {"choices": [{"message": {"content": json.dumps(model_json)}}]}

        calls = {"count": 0}

        def _mock_urlopen(req, timeout=0):
            calls["count"] += 1
            if calls["count"] == 1:
                raise URLError(RemoteDisconnected("Remote end closed connection without response"))
            return _FakeHTTPResponse(api_payload)

        with mock.patch("urllib.request.urlopen", side_effect=_mock_urlopen):
            out = provider.generate(self._request())

        self.assertEqual(out.script_draft.title, "Siglen Draft")
        self.assertEqual(calls["count"], 2)

    def test_retries_once_on_remote_disconnect_then_raises_with_clear_error(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")

        def _mock_urlopen(req, timeout=0):
            raise URLError(RemoteDisconnected("Remote end closed connection without response"))

        with mock.patch("urllib.request.urlopen", side_effect=_mock_urlopen):
            with self.assertRaises(DeepSeekProviderError) as ctx:
                provider.generate(self._request())

        message = str(ctx.exception)
        self.assertIn("transient connection error", message)
        self.assertIn("Remote end closed connection without response", message)

    def test_auth_error_has_clear_category(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")
        err = HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        err.read = lambda: b'{"error":"invalid api key"}'  # type: ignore[attr-defined]

        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(DeepSeekProviderError) as ctx:
                provider.generate(self._request())

        self.assertIn("auth/config error", str(ctx.exception))

    def test_malformed_model_json_error_has_clear_category(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")
        api_payload = {"choices": [{"message": {"content": "{not-json"}}]}

        with mock.patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(api_payload)):
            with self.assertRaises(DeepSeekProviderError) as ctx:
                provider.generate(self._request())

        self.assertIn("malformed response error", str(ctx.exception))

    def test_http_error_includes_response_body_when_available(self) -> None:
        provider = DeepSeekScriptProvider(api_key="k")
        err = HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        err.read = lambda: b'{"error":"invalid api key"}'  # type: ignore[attr-defined]

        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(DeepSeekProviderError) as ctx:
                provider.generate(self._request())

        self.assertIn("HTTP 401", str(ctx.exception))
        self.assertIn("invalid api key", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
