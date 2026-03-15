from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from src.intake_compiler import CompilerBundle, compile_brief_to_constraints, load_compiler_bundle
from src.intake_models import (
    CompiledGenerationConstraints,
    NormalizedIntakeBrief,
    ScriptProviderRequest,
    ScriptProviderResponse,
    StyleReference,
)
from src.intake_validation import normalize_and_validate_brief
from src.script_provider_base import ScriptProvider


@dataclass
class ScriptPipelineResult:
    normalized_brief: NormalizedIntakeBrief
    compiled_constraints: CompiledGenerationConstraints
    provider_response: ScriptProviderResponse


def build_default_compiler_bundle(root: Path) -> CompilerBundle:
    return load_compiler_bundle(
        canonical_registry_path=root / "data" / "taxonomy" / "canonical_registry_v1.yaml",
        combo_rules_path=root / "data" / "taxonomy" / "combo_rules_v1.yaml",
        intent_mappings_path=root / "data" / "taxonomy" / "intent_mappings_v1.yaml",
    )


def validate_provider_response_shape(response: ScriptProviderResponse) -> None:
    if not response.script_draft.title:
        raise ValueError("provider response missing script_draft.title")
    if not isinstance(response.pool_plan_draft.rows, list):
        raise ValueError("provider response pool_plan_draft.rows must be list")


def run_script_pipeline(
    *,
    brief: NormalizedIntakeBrief,
    provider: ScriptProvider,
    bundle: CompilerBundle,
    provider_hints: list[str] | None = None,
    style_references: list[StyleReference] | None = None,
) -> ScriptPipelineResult:
    normalized = normalize_and_validate_brief(brief)
    constraints = compile_brief_to_constraints(normalized, bundle)

    request = ScriptProviderRequest(
        brief=normalized,
        constraints=constraints,
        style_references=style_references or [],
        provider_hints=provider_hints or [],
    )
    response = provider.generate(request)
    validate_provider_response_shape(response)
    return ScriptPipelineResult(
        normalized_brief=normalized,
        compiled_constraints=constraints,
        provider_response=response,
    )


def response_to_dict(result: ScriptPipelineResult) -> dict:
    return asdict(result)
