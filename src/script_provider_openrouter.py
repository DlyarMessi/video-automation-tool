from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from src.intake_models import (
    PoolPlanDraft,
    ScriptDraft,
    ScriptProviderRequest,
    ScriptProviderResponse,
    ScriptSectionDraft,
)
from src.script_provider_base import ScriptProvider


class OpenRouterProviderError(RuntimeError):
    pass


class OpenRouterScriptProvider(ScriptProvider):
    provider_name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "openrouter/free",
        site_url: str = "",
        app_name: str = "",
        provider_options: dict[str, Any] | None = None,
        timeout_s: float = 60.0,
        endpoint: str = "https://openrouter.ai/api/v1/chat/completions",
    ):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "openrouter/free").strip() or "openrouter/free"
        self.site_url = str(site_url or "").strip()
        self.app_name = str(app_name or "").strip()
        self.provider_options = provider_options or {}
        self.timeout_s = timeout_s
        self.endpoint = endpoint

    def _ensure_config(self) -> None:
        if not self.api_key:
            raise OpenRouterProviderError("OPENROUTER_API_KEY is required for openrouter provider")

    def build_prompt(self, req: ScriptProviderRequest) -> str:
        lines: list[str] = []
        lines.append("You generate ScriptProviderResponse JSON for a governed video pipeline.")
        lines.append("Follow all constraints exactly; do not bypass canonical/pool-plan-compatible logic.")
        lines.append("")
        lines.append("## Intake Brief")
        lines.append(json.dumps(asdict(req.brief), ensure_ascii=False, indent=2))
        lines.append("")
        lines.append("## Compiled Constraints")
        lines.append(json.dumps(asdict(req.constraints), ensure_ascii=False, indent=2))

        if req.style_references:
            lines.append("")
            lines.append("## Style References")
            lines.append(json.dumps([asdict(x) for x in req.style_references], ensure_ascii=False, indent=2))

        if req.provider_hints:
            lines.append("")
            lines.append("## Provider Hints")
            lines.append(json.dumps(req.provider_hints, ensure_ascii=False, indent=2))

        lines.append("")
        lines.append("## Output Contract Rules")
        lines.append("- Return ONLY valid JSON object; no markdown fences.")
        lines.append("- Keys must match ScriptProviderResponse fields exactly.")
        lines.append("- Preserve topic/evidence separation from compiled constraints.")
        lines.append("- Every section should include semantic-ready content for success_criteria and fallback.")
        lines.append("- Move usage must respect preferred/acceptable/avoid guidance and hard_rules.")
        lines.append("")
        lines.append("JSON schema shape:")
        lines.append(
            '{"script_draft":{"title":"...","key_message":"...","creative_brief":"...","sections":['
            '{"section_id":"S01","purpose":"...","narration":"...","on_screen_text":"...",'
            '"success_criteria":"...","evidence_needed":[],"preferred_scene":[],"acceptable_scene":[],'
            '"preferred_move":[],"acceptable_move":[],"avoid_move":[],"fallback":"","notes":""}],"warnings":[]},'
            '"pool_plan_draft":{"rows":[],"warnings":[]},"unresolved_risks":[],"confidence_notes":[]}'
        )
        return "\n".join(lines)

    def _build_payload(self, req: ScriptProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict JSON generator for governed video scripting.",
                },
                {
                    "role": "user",
                    "content": self.build_prompt(req),
                },
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        if self.provider_options:
            payload["provider"] = self.provider_options
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-OpenRouter-Title"] = self.app_name
        return headers

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            self.endpoint,
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            detail = f"HTTP {getattr(e, 'code', 'unknown')}"
            if err_body:
                detail += f" body={err_body[:500]}"
            raise OpenRouterProviderError(f"OpenRouter request failed: {detail}") from e
        except Exception as e:
            raise OpenRouterProviderError(f"OpenRouter request failed: {e}") from e

        try:
            parsed = json.loads(raw)
        except Exception as e:
            raise OpenRouterProviderError(f"OpenRouter returned non-JSON response: {raw[:500]}") from e
        if not isinstance(parsed, dict):
            raise OpenRouterProviderError("OpenRouter response root must be object")
        return parsed

    def _extract_content_text(self, response_obj: dict[str, Any]) -> str:
        choices = response_obj.get("choices", []) if isinstance(response_obj.get("choices"), list) else []
        if not choices or not isinstance(choices[0], dict):
            raise OpenRouterProviderError("OpenRouter response missing choices[0]")
        msg = choices[0].get("message", {}) if isinstance(choices[0].get("message"), dict) else {}
        content = msg.get("content", "")
        text = str(content or "").strip()
        if not text:
            raise OpenRouterProviderError("OpenRouter response message content is empty")
        return text

    def _parse_json_text(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            data = json.loads(cleaned)
        except Exception as e:
            raise OpenRouterProviderError(f"Could not parse model JSON output: {text[:500]}") from e
        if not isinstance(data, dict):
            raise OpenRouterProviderError("Model JSON output must be object")
        return data

    @staticmethod
    def _to_clean_str_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        out: list[str] = []
        for v in values:
            x = str(v or "").strip()
            if x:
                out.append(x)
        return out

    def parse_provider_response(self, payload: dict[str, Any]) -> ScriptProviderResponse:
        script_payload = payload.get("script_draft", {}) if isinstance(payload.get("script_draft"), dict) else {}
        pool_payload = payload.get("pool_plan_draft", {}) if isinstance(payload.get("pool_plan_draft"), dict) else {}

        sections: list[ScriptSectionDraft] = []
        raw_sections = script_payload.get("sections", []) if isinstance(script_payload.get("sections"), list) else []
        for item in raw_sections:
            if not isinstance(item, dict):
                continue
            sections.append(
                ScriptSectionDraft(
                    section_id=str(item.get("section_id", "")).strip() or "SXX",
                    purpose=str(item.get("purpose", "")).strip(),
                    narration=str(item.get("narration", "")).strip(),
                    on_screen_text=str(item.get("on_screen_text", "")).strip(),
                    success_criteria=str(item.get("success_criteria", "")).strip(),
                    evidence_needed=self._to_clean_str_list(item.get("evidence_needed", [])),
                    preferred_scene=self._to_clean_str_list(item.get("preferred_scene", [])),
                    acceptable_scene=self._to_clean_str_list(item.get("acceptable_scene", [])),
                    preferred_move=self._to_clean_str_list(item.get("preferred_move", [])),
                    acceptable_move=self._to_clean_str_list(item.get("acceptable_move", [])),
                    avoid_move=self._to_clean_str_list(item.get("avoid_move", [])),
                    fallback=str(item.get("fallback", "")).strip(),
                    notes=str(item.get("notes", "")).strip(),
                )
            )

        script = ScriptDraft(
            title=str(script_payload.get("title", "")).strip(),
            key_message=str(script_payload.get("key_message", "")).strip(),
            creative_brief=str(script_payload.get("creative_brief", "")).strip(),
            sections=sections,
            warnings=self._to_clean_str_list(script_payload.get("warnings", [])),
        )

        if not script.title:
            raise OpenRouterProviderError("Parsed response missing script_draft.title")

        pool = PoolPlanDraft(
            rows=pool_payload.get("rows", []) if isinstance(pool_payload.get("rows"), list) else [],
            warnings=self._to_clean_str_list(pool_payload.get("warnings", [])),
        )

        return ScriptProviderResponse(
            script_draft=script,
            pool_plan_draft=pool,
            unresolved_risks=self._to_clean_str_list(payload.get("unresolved_risks", [])),
            confidence_notes=self._to_clean_str_list(payload.get("confidence_notes", [])),
        )

    def generate(self, request: ScriptProviderRequest) -> ScriptProviderResponse:
        self._ensure_config()
        payload = self._build_payload(request)
        api_response = self._post_json(payload)
        text = self._extract_content_text(api_response)
        parsed_json = self._parse_json_text(text)
        return self.parse_provider_response(parsed_json)
