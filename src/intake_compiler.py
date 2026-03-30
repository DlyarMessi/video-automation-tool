from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.intake_models import CompiledGenerationConstraints, NormalizedIntakeBrief

PUBLIC_SEMANTIC_FIELDS = [
    "human_label",
    "shoot_brief",
    "success_criteria",
    "fallback",
    "purpose",
]

DEFAULT_ACCEPTABLE_MOVES = ["static", "slide", "pushin", "follow", "orbit", "reveal"]


@dataclass
class CompilerBundle:
    canonical_registry: dict[str, Any]
    combo_rules: dict[str, Any]
    intent_mappings: dict[str, Any]
    pool_plan_template: dict[str, Any] | None = None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(values: list[Any] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        text = _clean_text(item)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _extract_registry_entries(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = data.get("entries", {}) if isinstance(data.get("entries"), dict) else {}
    return {str(k): v for k, v in entries.items() if isinstance(k, str) and isinstance(v, dict)}


def _extract_registry_move_vocab(registry_entries: dict[str, dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for entry in registry_entries.values():
        if not isinstance(entry, dict):
            continue
        canonical = entry.get("canonical", {}) if isinstance(entry.get("canonical"), dict) else {}
        move = _clean_text(canonical.get("move", "")).lower()
        if move:
            out.add(move)
    return out


def _extract_governed_topics(bundle: CompilerBundle) -> set[str]:
    topics: set[str] = set()
    if isinstance(bundle.intent_mappings.get("current_reference_intents"), list):
        topics.update(
            _clean_text(v).lower()
            for v in bundle.intent_mappings.get("current_reference_intents", [])
            if _clean_text(v)
        )

    mappings = bundle.intent_mappings.get("mappings", []) if isinstance(bundle.intent_mappings.get("mappings"), list) else []
    for item in mappings:
        if not isinstance(item, dict):
            continue
        topics.update(_clean_text(v).lower() for v in item.get("required_topics", []) if _clean_text(v))
    return topics


def _mapping_for_objective(intent_mappings: dict[str, Any], objective: str) -> dict[str, Any]:
    by_objective = intent_mappings.get("by_objective", {}) if isinstance(intent_mappings.get("by_objective"), dict) else {}
    lowered = objective.casefold()
    if lowered in by_objective and isinstance(by_objective[lowered], dict):
        return by_objective[lowered]

    mappings = intent_mappings.get("mappings", []) if isinstance(intent_mappings.get("mappings"), list) else []
    for item in mappings:
        if not isinstance(item, dict):
            continue
        triggers = [str(x).casefold() for x in (item.get("objective_keywords") or []) if str(x).strip()]
        if any(t in lowered for t in triggers):
            return item
    return {}


def _split_must_include(values: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return (topics, evidence, warnings).

    v1 rule:
    - prefix `topic:` routes to topics
    - prefix `evidence:` routes to evidence
    - unprefixed values are treated as topics for backward compatibility
    """
    topics: list[str] = []
    evidence: list[str] = []
    warnings: list[str] = []

    for value in values:
        raw = _clean_text(value)
        if not raw:
            continue
        low = raw.lower()
        if low.startswith("topic:"):
            topic = _clean_text(raw.split(":", 1)[1])
            if topic:
                topics.append(topic)
            continue
        if low.startswith("evidence:"):
            item = _clean_text(raw.split(":", 1)[1])
            if item:
                evidence.append(item)
            continue

        topics.append(raw)
        warnings.append(
            f"must_include item treated as topic (use 'topic:'/'evidence:' prefix for explicit routing): {raw}"
        )

    return _clean_list(topics), _clean_list(evidence), _clean_list(warnings)


def load_compiler_bundle(
    *,
    canonical_registry_path: Path,
    combo_rules_path: Path,
    intent_mappings_path: Path,
    pool_plan_template_path: Path | None = None,
) -> CompilerBundle:
    def load_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            import yaml  # type: ignore
        except Exception:
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}

    return CompilerBundle(
        canonical_registry=load_yaml(canonical_registry_path),
        combo_rules=load_yaml(combo_rules_path),
        intent_mappings=load_yaml(intent_mappings_path),
        pool_plan_template=load_yaml(pool_plan_template_path) if pool_plan_template_path else None,
    )


def compile_brief_to_constraints(
    brief: NormalizedIntakeBrief,
    bundle: CompilerBundle,
) -> CompiledGenerationConstraints:
    warnings: list[str] = []
    soft_preferences: list[str] = []

    objective = _clean_text(brief.objective)
    audience = _clean_text(brief.audience)

    objective_mapping = _mapping_for_objective(bundle.intent_mappings, objective)
    mapped_topics = _clean_list(objective_mapping.get("required_topics", []))
    mapped_evidence = _clean_list(objective_mapping.get("required_evidence", []))

    must_topics, must_evidence, must_warnings = _split_must_include(brief.must_include)
    warnings.extend(must_warnings)

    # Keep topics/evidence strictly separate.
    required_topics = _clean_list(mapped_topics + must_topics)
    required_evidence = _clean_list(mapped_evidence + brief.evidence_priorities + must_evidence)

    if objective and not mapped_topics:
        soft_preferences.append(f"Objective provided but no explicit topic mapping found: {objective}")

    if audience:
        soft_preferences.append(f"Audience alignment required: {audience}")

    style = [x.casefold() for x in brief.style_keywords]
    assets = [x.casefold() for x in brief.available_assets]

    preferred_moves: list[str] = []
    avoid_moves: list[str] = []

    # v1 deterministic move hints (heuristic, constrained by governed vocab checks below).
    if "hero" in style or "premium" in style:
        preferred_moves.extend(["orbit", "slide"])
    if "technical" in style or "proof" in style:
        preferred_moves.extend(["static", "pushin"])
    if "handheld" in style:
        avoid_moves.append("follow")

    if any("drone" in x for x in assets):
        preferred_moves.append("reveal")

    if brief.orientation == "portrait":
        soft_preferences.append("Portrait-safe framing and text-safe areas should be prioritized.")
    else:
        soft_preferences.append("Landscape-friendly continuity and wider compositions should be prioritized.")

    for banned in brief.avoid:
        if "move:" in banned.casefold():
            avoid_moves.append(_clean_text(banned.split(":", 1)[1]).lower())

    preferred_moves = [x.lower() for x in _clean_list(preferred_moves)]
    avoid_moves = [x.lower() for x in _clean_list(avoid_moves)]

    registry_entries = _extract_registry_entries(bundle.canonical_registry)
    governed_move_vocab = _extract_registry_move_vocab(registry_entries)
    if not registry_entries:
        warnings.append("Canonical registry bundle appears empty; compiler used fallback constraints.")

    if governed_move_vocab:
        unknown_pref = [m for m in preferred_moves if m not in governed_move_vocab]
        unknown_avoid = [m for m in avoid_moves if m not in governed_move_vocab]
        for m in unknown_pref:
            warnings.append(f"preferred_move '{m}' is outside canonical registry move vocabulary")
        for m in unknown_avoid:
            warnings.append(f"avoid_move '{m}' is outside canonical registry move vocabulary")
    else:
        warnings.append("Canonical registry has no move vocabulary; move governance check skipped.")

    # keep internal consistency
    preferred_moves = [m for m in preferred_moves if m not in set(avoid_moves)]

    acceptable_moves = [m for m in DEFAULT_ACCEPTABLE_MOVES if m not in set(avoid_moves)]

    if governed_move_vocab:
        dropped_defaults = [m for m in acceptable_moves if m not in governed_move_vocab]
        for m in dropped_defaults:
            warnings.append(f"acceptable_move '{m}' dropped because it is outside canonical registry move vocabulary")
        acceptable_moves = [m for m in acceptable_moves if m in governed_move_vocab]

        # keep preferred/acceptable aligned to governed vocab too
        preferred_moves = [m for m in preferred_moves if m in governed_move_vocab]

    for m in preferred_moves:
        if m not in acceptable_moves:
            acceptable_moves.append(m)

    governed_topics = _extract_governed_topics(bundle)
    if governed_topics and required_topics:
        for topic in required_topics:
            if topic.lower() not in governed_topics:
                warnings.append(
                    f"required_topic '{topic}' is outside current governed topic vocabulary from intent mappings"
                )

    if bundle.pool_plan_template and not required_topics:
        warnings.append(
            "Pool-plan template supplied but no safe topic derivation rule is defined in v1; no template-derived topics were added."
        )

    hard_rules = [
        "RULE:canonical_tuple_required: section planning MUST remain compatible with canonical scene/subject/action/coverage/move.",
        "RULE:semantic_fields_required: each generated section MUST support human_label/shoot_brief/success_criteria/fallback/purpose semantics.",
        "RULE:provider_output_contract: provider output MUST be representable as ScriptProviderResponse without ad hoc fields.",
    ]

    if bundle.combo_rules:
        warnings.append("combo_rules bundle is loaded but not yet enforced by v1 compile constraints.")

    if not required_topics:
        warnings.append("No required topics derived; provider output may be generic.")

    if not required_evidence:
        warnings.append("No required evidence derived; add evidence_priorities or evidence-prefixed must_include entries.")

    return CompiledGenerationConstraints(
        required_topics=required_topics,
        required_evidence=required_evidence,
        preferred_moves=preferred_moves,
        acceptable_moves=acceptable_moves,
        avoid_moves=avoid_moves,
        required_semantic_fields=list(PUBLIC_SEMANTIC_FIELDS),
        orientation=brief.orientation,
        duration_s=brief.duration_s,
        language=brief.language,
        hard_rules=hard_rules,
        soft_preferences=soft_preferences,
        warnings=_clean_list(warnings),
    )
