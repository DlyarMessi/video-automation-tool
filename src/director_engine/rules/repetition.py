# src/director_engine/rules/repetition.py

from typing import List, Dict, Any


def _get_primary_tag(shot: Dict[str, Any]) -> str:
    if isinstance(shot.get("tag"), str) and shot["tag"].strip():
        return shot["tag"].strip()

    tags = shot.get("tags")
    if isinstance(tags, list) and tags:
        return str(tags[0]).strip()

    src = shot.get("source")
    if isinstance(src, str) and "tags:" in src:
        try:
            after = src.split("tags:", 1)[1]
            after = after.split()[0]
            return after.split(",")[0].strip()
        except Exception:
            pass

    return ""


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Prevent excessive repetition of the same tag.
    Strategy:
    - If the same tag appears more than max_consecutive_same_tag times in a row,
      attempt a minimal swap with a later shot of a different tag.
    """

    if not shots:
        return shots

    profile = context.get("profile", {})
    rep_cfg = profile.get("repetition", {}) or {}

    max_consecutive = rep_cfg.get("max_consecutive_same_tag", 2)
    cooldown = rep_cfg.get("tag_cooldown", 0)

    directed = [dict(s) for s in shots]

    last_tag = None
    streak = 0

    i = 0
    while i < len(directed):
        cur_tag = _get_primary_tag(directed[i])

        if cur_tag and cur_tag == last_tag:
            streak += 1
        else:
            streak = 1
            last_tag = cur_tag

        if cur_tag and streak > max_consecutive:
            # find a later shot with a different tag
            swap_idx = None
            for j in range(i + 1, len(directed)):
                other_tag = _get_primary_tag(directed[j])
                if other_tag and other_tag != cur_tag:
                    swap_idx = j
                    break

            if swap_idx is not None:
                # minimal disturbance swap
                directed[i], directed[swap_idx] = directed[swap_idx], directed[i]
                # reset streak after swap
                last_tag = _get_primary_tag(directed[i])
                streak = 1
            # if no swap candidate found, we accept repetition and move on

        i += 1

    return directed