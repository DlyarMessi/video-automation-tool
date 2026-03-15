from __future__ import annotations

import re
from dataclasses import asdict

from src.intake_models import NormalizedIntakeBrief


def _split_items(value: str) -> list[str]:
    parts = re.split(r"[,\n;]+", str(value or ""))
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        clean = str(part or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _looks_like_language(text: str) -> str:
    lower = text.lower()
    if "english" in lower or "en-us" in lower:
        return "en-US"
    if "french" in lower or "fr-fr" in lower:
        return "fr-FR"
    if "spanish" in lower or "es-es" in lower:
        return "es-ES"
    if "arabic" in lower or "ar-sa" in lower:
        return "ar-SA"
    if "russian" in lower or "ru-ru" in lower:
        return "ru-RU"
    return ""


def infer_brief_from_quick_input(
    *,
    quick_brief: str,
    company: str,
    output_language: str,
    orientation: str,
    duration_s: int,
    emphasis: str,
    has_existing_footage: str,
) -> tuple[NormalizedIntakeBrief, dict[str, str]]:
    text = str(quick_brief or "").strip()
    notes: dict[str, str] = {}

    inferred_language = _looks_like_language(text) or output_language

    style_keywords: list[str] = []
    must_include: list[str] = []
    evidence_priorities: list[str] = []

    if emphasis == "Proof & evidence":
        evidence_priorities.extend(["before/after", "quality detail"])
        style_keywords.append("credible")
    elif emphasis == "Premium look":
        style_keywords.extend(["premium", "cinematic"])
    elif emphasis == "Clear education":
        style_keywords.extend(["clear", "instructional"])
    elif emphasis == "Speed & efficiency":
        style_keywords.extend(["efficient", "results-first"])

    if has_existing_footage == "Yes":
        notes["footage"] = "User indicated they already have footage to reuse."
    elif has_existing_footage == "Partially":
        notes["footage"] = "User has partial footage; expect pool gap closure."
    else:
        notes["footage"] = "User needs fresh footage collection."

    for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
        lower = line.lower()
        if lower.startswith(("must include:", "include:")):
            must_include.extend(_split_items(line.split(":", 1)[1]))
        elif lower.startswith(("avoid:", "exclude:")):
            notes["avoid"] = ", ".join(_split_items(line.split(":", 1)[1]))
        elif lower.startswith(("audience:",)):
            notes["audience"] = line.split(":", 1)[1].strip()
        elif lower.startswith(("objective:", "goal:")):
            notes["objective"] = line.split(":", 1)[1].strip()
        elif lower.startswith(("product:", "service:")):
            notes["product"] = line.split(":", 1)[1].strip()
        elif lower.startswith(("tone:", "style:")):
            style_keywords.extend(_split_items(line.split(":", 1)[1]))

    brief = NormalizedIntakeBrief(
        brand_name=company,
        product_name=notes.get("product", ""),
        audience=notes.get("audience", ""),
        objective=notes.get("objective", ""),
        language=inferred_language,
        orientation=orientation,
        duration_s=int(duration_s),
        tone="",
        style_keywords=_split_items(", ".join(style_keywords)),
        must_include=_split_items(", ".join(must_include)),
        evidence_priorities=_split_items(", ".join(evidence_priorities)),
        notes=text,
    )
    return brief, notes


def merge_brief_preserving_user_fields(
    *,
    current: NormalizedIntakeBrief,
    inferred: NormalizedIntakeBrief,
    edited_fields: set[str],
) -> NormalizedIntakeBrief:
    payload = asdict(current)
    inferred_payload = asdict(inferred)

    for key, inferred_value in inferred_payload.items():
        if key in edited_fields:
            continue
        if key == "brand_name":
            continue
        payload[key] = inferred_value

    return NormalizedIntakeBrief(**payload)


def build_merged_brief_from_quick_input(
    *,
    current: NormalizedIntakeBrief,
    edited_fields: set[str],
    quick_brief: str,
    company: str,
    output_language: str,
    orientation: str,
    duration_s: int,
    emphasis: str,
    has_existing_footage: str,
) -> NormalizedIntakeBrief:
    inferred, _ = infer_brief_from_quick_input(
        quick_brief=quick_brief,
        company=company,
        output_language=output_language,
        orientation=orientation,
        duration_s=duration_s,
        emphasis=emphasis,
        has_existing_footage=has_existing_footage,
    )
    return merge_brief_preserving_user_fields(
        current=current,
        inferred=inferred,
        edited_fields=edited_fields,
    )
