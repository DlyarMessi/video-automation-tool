from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from src.intake_models import (
    PoolPlanDraft,
    ScriptDraft,
    ScriptProviderRequest,
    ScriptProviderResponse,
    ScriptSectionDraft,
)
from src.script_provider_base import ScriptProvider


class ManualScriptProvider(ScriptProvider):
    provider_name = "manual"

    def __init__(self, response_path: Path | None = None):
        self.response_path = response_path

    def _load_response_payload(self) -> dict[str, Any] | None:
        if not self.response_path:
            return None
        if not self.response_path.exists():
            raise FileNotFoundError(f"Manual provider file not found: {self.response_path}")
        text = self.response_path.read_text(encoding="utf-8")
        if self.response_path.suffix.lower() == ".json":
            data = json.loads(text) or {}
            return data if isinstance(data, dict) else None
        try:
            import yaml  # type: ignore
        except Exception:
            return None
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else None

    def _build_scaffold(self, request: ScriptProviderRequest) -> ScriptProviderResponse:
        topic_summary = ", ".join(request.constraints.required_topics[:3]) or "governed topics"
        section = ScriptSectionDraft(
            section_id="S01",
            purpose="Establish key value and proof direction",
            narration=f"{request.brief.brand_name} delivers reliable value for {request.brief.audience or 'target customers' }.",
            on_screen_text=request.brief.product_name or request.brief.brand_name,
            success_criteria="Section aligns with compiled constraints and evidence requirements.",
            evidence_needed=request.constraints.required_evidence[:3],
            preferred_scene=request.brief.available_locations[:2],
            acceptable_scene=request.brief.available_locations[2:4],
            preferred_move=request.constraints.preferred_moves[:2],
            acceptable_move=request.constraints.acceptable_moves[:3],
            avoid_move=request.constraints.avoid_moves[:2],
            fallback="Use another valid canonical slot with equivalent purpose.",
            notes=f"Topic focus: {topic_summary}",
        )
        script = ScriptDraft(
            title=f"{request.brief.brand_name} Script Draft",
            key_message=request.brief.objective or "Brand value with operational proof",
            creative_brief=request.brief.notes or "Generated via manual scaffold provider.",
            sections=[section],
            warnings=["Manual scaffold output; refine before production compile."] if not self.response_path else [],
        )
        pool = PoolPlanDraft(rows=[], warnings=["No automatic pool plan rows in manual scaffold mode."])
        return ScriptProviderResponse(script_draft=script, pool_plan_draft=pool)

    def generate(self, request: ScriptProviderRequest) -> ScriptProviderResponse:
        payload = self._load_response_payload()
        if not payload:
            return self._build_scaffold(request)

        script_payload = payload.get("script_draft", {}) if isinstance(payload.get("script_draft"), dict) else {}
        pool_payload = payload.get("pool_plan_draft", {}) if isinstance(payload.get("pool_plan_draft"), dict) else {}

        sections: list[ScriptSectionDraft] = []
        for item in script_payload.get("sections", []) if isinstance(script_payload.get("sections"), list) else []:
            if not isinstance(item, dict):
                continue
            sections.append(
                ScriptSectionDraft(
                    section_id=str(item.get("section_id", "")).strip() or "SXX",
                    purpose=str(item.get("purpose", "")).strip(),
                    narration=str(item.get("narration", "")).strip(),
                    on_screen_text=str(item.get("on_screen_text", "")).strip(),
                    success_criteria=str(item.get("success_criteria", "")).strip(),
                    evidence_needed=[str(x).strip() for x in item.get("evidence_needed", []) if str(x).strip()],
                    preferred_scene=[str(x).strip() for x in item.get("preferred_scene", []) if str(x).strip()],
                    acceptable_scene=[str(x).strip() for x in item.get("acceptable_scene", []) if str(x).strip()],
                    preferred_move=[str(x).strip() for x in item.get("preferred_move", []) if str(x).strip()],
                    acceptable_move=[str(x).strip() for x in item.get("acceptable_move", []) if str(x).strip()],
                    avoid_move=[str(x).strip() for x in item.get("avoid_move", []) if str(x).strip()],
                    fallback=str(item.get("fallback", "")).strip(),
                    notes=str(item.get("notes", "")).strip(),
                )
            )

        script = ScriptDraft(
            title=str(script_payload.get("title", "")).strip() or f"{request.brief.brand_name} Script Draft",
            key_message=str(script_payload.get("key_message", "")).strip() or request.brief.objective,
            creative_brief=str(script_payload.get("creative_brief", "")).strip(),
            sections=sections,
            warnings=[str(x).strip() for x in script_payload.get("warnings", []) if str(x).strip()],
        )
        pool = PoolPlanDraft(
            rows=pool_payload.get("rows", []) if isinstance(pool_payload.get("rows"), list) else [],
            warnings=[str(x).strip() for x in pool_payload.get("warnings", []) if str(x).strip()],
        )

        return ScriptProviderResponse(
            script_draft=script,
            pool_plan_draft=pool,
            unresolved_risks=[str(x).strip() for x in payload.get("unresolved_risks", []) if str(x).strip()],
            confidence_notes=[str(x).strip() for x in payload.get("confidence_notes", []) if str(x).strip()],
        )

    @staticmethod
    def dump_template(path: Path) -> None:
        sample = ScriptProviderResponse(
            script_draft=ScriptDraft(
                title="Sample Draft",
                key_message="Core claim",
                creative_brief="Manual template",
                sections=[
                    ScriptSectionDraft(
                        section_id="S01",
                        purpose="Intro",
                        narration="Narration...",
                        on_screen_text="On-screen text",
                        success_criteria="Criteria",
                    )
                ],
            ),
            pool_plan_draft=PoolPlanDraft(rows=[]),
        )
        if path.suffix.lower() == ".json":
            path.write_text(json.dumps(asdict(sample), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return
        try:
            import yaml  # type: ignore
        except Exception:
            path.write_text(json.dumps(asdict(sample), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return
        path.write_text(yaml.safe_dump(asdict(sample), sort_keys=False, allow_unicode=True), encoding="utf-8")
