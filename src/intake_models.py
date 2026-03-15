from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedIntakeBrief:
    brand_name: str
    product_name: str = ""
    audience: str = ""
    objective: str = ""
    language: str = "zh"
    orientation: str = "portrait"
    duration_s: int = 45
    market_region: str = ""
    tone: str = ""
    style_keywords: list[str] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    available_locations: list[str] = field(default_factory=list)
    available_assets: list[str] = field(default_factory=list)
    available_people: list[str] = field(default_factory=list)
    evidence_priorities: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class CompiledGenerationConstraints:
    required_topics: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    preferred_moves: list[str] = field(default_factory=list)
    acceptable_moves: list[str] = field(default_factory=list)
    avoid_moves: list[str] = field(default_factory=list)
    required_semantic_fields: list[str] = field(default_factory=list)
    orientation: str = "portrait"
    duration_s: int = 45
    language: str = "zh"
    hard_rules: list[str] = field(default_factory=list)
    soft_preferences: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StyleReference:
    ref_id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ScriptProviderRequest:
    brief: NormalizedIntakeBrief
    constraints: CompiledGenerationConstraints
    style_references: list[StyleReference] = field(default_factory=list)
    provider_hints: list[str] = field(default_factory=list)


@dataclass
class ScriptSectionDraft:
    section_id: str
    purpose: str
    narration: str
    on_screen_text: str
    success_criteria: str
    evidence_needed: list[str] = field(default_factory=list)
    preferred_scene: list[str] = field(default_factory=list)
    acceptable_scene: list[str] = field(default_factory=list)
    preferred_move: list[str] = field(default_factory=list)
    acceptable_move: list[str] = field(default_factory=list)
    avoid_move: list[str] = field(default_factory=list)
    fallback: str = ""
    notes: str = ""


@dataclass
class ScriptDraft:
    title: str
    key_message: str
    creative_brief: str
    sections: list[ScriptSectionDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PoolPlanDraft:
    rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScriptProviderResponse:
    script_draft: ScriptDraft
    pool_plan_draft: PoolPlanDraft
    unresolved_risks: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)
