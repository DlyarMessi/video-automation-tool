# src/director_engine/rules/transitions.py

from typing import List, Dict, Any


def _get_primary_tag(shot: Dict[str, Any]) -> str:
    """
    Get a primary tag for transition comparison.
    Priority:
      1) shot["tag"] if present
      2) first element of shot["tags"] if list
      3) best-effort parse from source spec (tags:...)
      4) empty string
    """
    if isinstance(shot.get("tag"), str) and shot["tag"].strip():
        return shot["tag"].strip()

    tags = shot.get("tags")
    if isinstance(tags, list) and tags:
        t = str(tags[0]).strip()
        if t:
            return t

    src = shot.get("source")
    if isinstance(src, str) and "tags:" in src:
        try:
            after = src.split("tags:", 1)[1]
            after = after.split()[0]
            first = after.split(",")[0].strip()
            return first
        except Exception:
            pass

    return ""


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply transition decisions between shots based on tag continuity.
    """
    if not shots:
        return shots

    profile = context.get("profile", {})
    trans_cfg = profile.get("transitions", {}) or {}

    default_transition = trans_cfg.get("default", "cut")
    fade_duration = trans_cfg.get("fade_duration", 0.25)
    disable_fade_when_same_tag = bool(
        trans_cfg.get("disable_fade_when_same_tag", True)
    )

    directed = [dict(s) for s in shots]

    prev_tag = None

    for i, shot in enumerate(directed):
        cur_tag = _get_primary_tag(shot)

        # First shot: no incoming transition
        if i == 0:
            shot["transition"] = {"type": "cut"}
            prev_tag = cur_tag
            continue

        transition_type = default_transition

        if disable_fade_when_same_tag and cur_tag and cur_tag == prev_tag:
            transition_type = "cut"

        if transition_type == "fade":
            shot["transition"] = {
                "type": "fade",
                "duration": float(fade_duration),
            }
        else:
            shot["transition"] = {"type": "cut"}

        prev_tag = cur_tag

    return directed