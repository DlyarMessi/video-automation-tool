from __future__ import annotations

from dataclasses import replace

from src.intake_models import NormalizedIntakeBrief


MIN_DURATION_S = 1
MAX_DURATION_S = 600
ALLOWED_ORIENTATIONS = {"portrait", "landscape"}
LIST_FIELDS = [
    "style_keywords",
    "must_include",
    "avoid",
    "available_locations",
    "available_assets",
    "available_people",
    "evidence_priorities",
]


class IntakeValidationError(ValueError):
    pass


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_list(values: list[str], *, dedupe: bool) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        clean = _clean_text(item)
        if not clean:
            continue
        key = clean.casefold()
        if dedupe and key in seen:
            continue
        out.append(clean)
        seen.add(key)
    return out


def normalize_intake_brief(brief: NormalizedIntakeBrief, *, dedupe_lists: bool = True) -> NormalizedIntakeBrief:
    normalized = replace(brief)
    normalized.brand_name = _clean_text(normalized.brand_name)
    normalized.product_name = _clean_text(normalized.product_name)
    normalized.audience = _clean_text(normalized.audience)
    normalized.objective = _clean_text(normalized.objective)
    normalized.language = _clean_text(normalized.language) or "zh"
    normalized.orientation = _clean_text(normalized.orientation).lower() or "portrait"
    normalized.market_region = _clean_text(normalized.market_region)
    normalized.tone = _clean_text(normalized.tone)
    normalized.notes = _clean_text(normalized.notes)

    for field_name in LIST_FIELDS:
        cleaned = _clean_list(getattr(normalized, field_name), dedupe=dedupe_lists)
        setattr(normalized, field_name, cleaned)

    return normalized


def validate_intake_brief(brief: NormalizedIntakeBrief) -> None:
    if not brief.brand_name:
        raise IntakeValidationError("brand_name is required")

    if brief.orientation not in ALLOWED_ORIENTATIONS:
        raise IntakeValidationError("orientation must be portrait or landscape")

    if brief.duration_s < MIN_DURATION_S or brief.duration_s > MAX_DURATION_S:
        raise IntakeValidationError(
            f"duration_s must be between {MIN_DURATION_S} and {MAX_DURATION_S}"
        )


def normalize_and_validate_brief(
    brief: NormalizedIntakeBrief,
    *,
    dedupe_lists: bool = True,
) -> NormalizedIntakeBrief:
    normalized = normalize_intake_brief(brief, dedupe_lists=dedupe_lists)
    validate_intake_brief(normalized)
    return normalized
