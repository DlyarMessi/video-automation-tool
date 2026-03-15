from __future__ import annotations

from src.intake_models import ScriptProviderRequest, ScriptProviderResponse
from src.script_provider_base import ScriptProvider


class GeminiScriptProvider(ScriptProvider):
    provider_name = "gemini"

    def __init__(self, api_key: str = "", model: str = "gemini-1.5-pro"):
        self.api_key = (api_key or "").strip()
        self.model = (model or "gemini-1.5-pro").strip()

    def build_prompt(self, request: ScriptProviderRequest) -> str:
        constraints = request.constraints
        brief = request.brief

        lines = [
            "You are generating a script draft constrained by governed production rules.",
            f"Brand: {brief.brand_name}",
            f"Objective: {brief.objective}",
            f"Audience: {brief.audience}",
            f"Language: {constraints.language}",
            f"Orientation: {constraints.orientation}",
            f"Duration seconds: {constraints.duration_s}",
            f"Required topics: {', '.join(constraints.required_topics)}",
            f"Required evidence: {', '.join(constraints.required_evidence)}",
            f"Preferred moves: {', '.join(constraints.preferred_moves)}",
            f"Acceptable moves: {', '.join(constraints.acceptable_moves)}",
            f"Avoid moves: {', '.join(constraints.avoid_moves)}",
            f"Required semantic fields: {', '.join(constraints.required_semantic_fields)}",
            "Hard rules:",
        ]
        lines.extend([f"- {rule}" for rule in constraints.hard_rules])
        lines.append("Return JSON aligned to ScriptProviderResponse contract.")
        return "\n".join(lines)

    def parse_response_payload(self, _: str) -> ScriptProviderResponse:
        raise NotImplementedError("Gemini response parsing is not implemented in this scaffold.")

    def generate(self, request: ScriptProviderRequest) -> ScriptProviderResponse:
        _ = self.build_prompt(request)
        raise NotImplementedError(
            "Gemini API call is intentionally not implemented yet. "
            "Use ManualScriptProvider for local/no-API workflows."
        )
