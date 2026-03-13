from __future__ import annotations

from typing import List, Dict, Any

from .common import get_primary_tag, get_scene, get_content, get_coverage


def _signature(shot: Dict[str, Any]) -> str:
    return "|".join(
        [
            get_scene(shot),
            get_content(shot),
            get_coverage(shot),
            get_primary_tag(shot),
        ]
    )


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    profile = context.get("profile", {})
    rep_cfg = profile.get("repetition", {}) or {}
    max_consecutive = int(rep_cfg.get("max_consecutive_same_tag", 2) or 2)

    directed = [dict(s) for s in shots]

    last_sig = None
    streak = 0
    i = 0

    while i < len(directed):
        cur_sig = _signature(directed[i])

        if cur_sig and cur_sig == last_sig:
            streak += 1
        else:
            streak = 1
            last_sig = cur_sig

        if cur_sig and streak > max_consecutive:
            swap_idx = None
            for j in range(i + 1, len(directed)):
                other_sig = _signature(directed[j])
                if other_sig and other_sig != cur_sig:
                    swap_idx = j
                    break

            if swap_idx is not None:
                directed[i], directed[swap_idx] = directed[swap_idx], directed[i]
                last_sig = _signature(directed[i])
                streak = 1

        i += 1

    return directed
