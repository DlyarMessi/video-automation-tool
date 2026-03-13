from __future__ import annotations

import re
from typing import Any, Dict, List

from src.render_profile import get_language_family


ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF\u0500-\u052F]")
LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]")


def get_lang_short(lang_code: str) -> str:
    return (lang_code or "en").split("-")[0].lower()


def extract_script_texts(creative: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    beats = creative.get("beats", [])
    if not isinstance(beats, list):
        return out

    for beat in beats:
        if not isinstance(beat, dict):
            continue
        for key in ("subtitle", "vo"):
            value = beat.get(key)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
    return out


def detect_text_family(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"

    arabic_hits = len(ARABIC_RE.findall(text))
    cyrillic_hits = len(CYRILLIC_RE.findall(text))
    latin_hits = len(LATIN_RE.findall(text))

    counts = {
        "arabic": arabic_hits,
        "cyrillic": cyrillic_hits,
        "latin": latin_hits,
    }
    family = max(counts, key=counts.get)
    if counts[family] <= 0:
        return "unknown"
    return family


def detect_creative_family(creative: Dict[str, Any]) -> Dict[str, Any]:
    texts = extract_script_texts(creative)
    if not texts:
        return {
            "family": "unknown",
            "text_count": 0,
            "sample": "",
        }

    merged = "\n".join(texts)
    family = detect_text_family(merged)
    sample = texts[0][:120] if texts else ""
    return {
        "family": family,
        "text_count": len(texts),
        "sample": sample,
    }


def build_language_check(
    creative: Dict[str, Any],
    selected_lang_code: str,
    selected_voice_id: str,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    detected = detect_creative_family(creative)
    detected_family = detected["family"]
    expected_family = get_language_family(selected_lang_code)
    lang_short = get_lang_short(selected_lang_code)

    messages: List[str] = []
    blocking = False
    summary = ""

    if detected_family != "unknown" and detected_family != expected_family:
        blocking = True
        summary = "Script language does not match the selected language family."
        messages.append(
            f"Detected script family: {detected_family}. Selected language expects: {expected_family}."
        )
    elif detected_family == "unknown":
        summary = "Language check is partial because no clear subtitle/voice text was detected."
        messages.append("No strong script language signal was found in subtitle/vo fields.")
    else:
        summary = f"Script language family check passed ({detected_family})."

    languages = profile.get("languages", {}) if isinstance(profile.get("languages"), dict) else {}
    lang_cfg = languages.get(lang_short, {}) if isinstance(languages.get(lang_short), dict) else {}
    saved_voice_id = str(lang_cfg.get("voice_id", "") or "").strip()
    chosen_voice_id = str(selected_voice_id or "").strip()

    if not chosen_voice_id:
        messages.append(f"No Voice ID is currently set for the selected language ({lang_short}).")
    elif saved_voice_id and chosen_voice_id != saved_voice_id:
        messages.append(
            f"The current Voice ID differs from the saved profile mapping for {lang_short}."
        )
    elif not saved_voice_id and chosen_voice_id:
        messages.append(
            f"A Voice ID is provided for {lang_short}, but no saved mapping exists yet."
        )

    return {
        "blocking": blocking,
        "summary": summary,
        "messages": messages,
        "detected_family": detected_family,
        "expected_family": expected_family,
        "text_count": detected["text_count"],
        "sample": detected["sample"],
    }
