from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_registry_entries(bundle: CompilerBundle) -> dict[str, dict[str, Any]]:
    entries = bundle.canonical_registry.get("entries", {}) if isinstance(bundle.canonical_registry.get("entries"), dict) else {}
    return {str(k): v for k, v in entries.items() if isinstance(k, str) and isinstance(v, dict)}


def _extract_governed_vocab(bundle: CompilerBundle) -> dict[str, set[str]]:
    governed: dict[str, set[str]] = {
        "scene": set(),
        "subject": set(),
        "action": set(),
        "content": set(),
        "coverage": set(),
        "move": set(),
    }
    for entry in _extract_registry_entries(bundle).values():
        canonical = entry.get("canonical", {}) if isinstance(entry.get("canonical"), dict) else {}
        for field_name in governed:
            value = _clean_text(canonical.get(field_name, "")).lower()
            if value:
                governed[field_name].add(value)
    return governed


def _validate_vocab_values(
    *,
    context: str,
    field_name: str,
    values: list[str],
    governed_vocab: set[str],
    errors: list[str],
) -> None:
    if not governed_vocab:
        return
    for value in values:
        token = _clean_text(value).lower()
        if token and token not in governed_vocab:
            errors.append(f"{context} unknown canonical {field_name} '{value}'")


def validate_provider_response_shape(response: ScriptProviderResponse, bundle: CompilerBundle) -> None:
    if not response.script_draft.title:
        raise ValueError("provider response missing script_draft.title")
    if not isinstance(response.pool_plan_draft.rows, list):
        raise ValueError("provider response pool_plan_draft.rows must be list")

    governed = _extract_governed_vocab(bundle)
    errors: list[str] = []

    for idx, section in enumerate(response.script_draft.sections, 1):
        _validate_vocab_values(
            context=f"script_draft.sections[{idx}].preferred_scene",
            field_name="scene",
            values=section.preferred_scene,
            governed_vocab=governed["scene"],
            errors=errors,
        )
        _validate_vocab_values(
            context=f"script_draft.sections[{idx}].acceptable_scene",
            field_name="scene",
            values=section.acceptable_scene,
            governed_vocab=governed["scene"],
            errors=errors,
        )
        _validate_vocab_values(
            context=f"script_draft.sections[{idx}].preferred_move",
            field_name="move",
            values=section.preferred_move,
            governed_vocab=governed["move"],
            errors=errors,
        )
        _validate_vocab_values(
            context=f"script_draft.sections[{idx}].acceptable_move",
            field_name="move",
            values=section.acceptable_move,
            governed_vocab=governed["move"],
            errors=errors,
        )
        _validate_vocab_values(
            context=f"script_draft.sections[{idx}].avoid_move",
            field_name="move",
            values=section.avoid_move,
            governed_vocab=governed["move"],
            errors=errors,
        )

    field_aliases = {
        "scene": ["scene", "preferred_scene"],
        "subject": ["subject", "preferred_subject"],
        "action": ["action", "preferred_action"],
        "content": ["content", "preferred_content"],
        "coverage": ["coverage", "coverage_canonical", "preferred_coverage"],
        "move": ["move", "preferred_move"],
    }
    for idx, row in enumerate(response.pool_plan_draft.rows, 1):
        if not isinstance(row, dict):
            continue
        for governed_field, aliases in field_aliases.items():
            values = [_clean_text(row.get(alias, "")) for alias in aliases if _clean_text(row.get(alias, ""))]
            _validate_vocab_values(
                context=f"pool_plan_draft.rows[{idx}]",
                field_name=governed_field,
                values=values,
                governed_vocab=governed[governed_field],
                errors=errors,
            )

    if errors:
        raise ValueError("provider response contains unknown governed canonical vocabulary: " + "; ".join(errors))


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
    validate_provider_response_shape(response, bundle)
    return ScriptPipelineResult(
        normalized_brief=normalized,
        compiled_constraints=constraints,
        provider_response=response,
    )


def response_to_dict(result: ScriptPipelineResult) -> dict:
    return asdict(result)
