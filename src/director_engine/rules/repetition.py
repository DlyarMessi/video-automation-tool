from __future__ import annotations

from typing import List, Dict, Any

from .common import get_primary_tag, get_scene, get_subject, get_action, get_coverage


def _signature(shot: Dict[str, Any], context: Dict[str, Any]) -> str:
    return "|".join(
        [
            get_scene(shot, context=context),
            get_subject(shot, context=context),
            get_action(shot, context=context),
            get_coverage(shot, context=context),
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
        cur_sig = _signature(directed[i], context)

        if cur_sig and cur_sig == last_sig:
            streak += 1
        else:
            streak = 1
            last_sig = cur_sig

        if cur_sig and streak > max_consecutive:
            cur_beat = int(directed[i].get("_beat_no", 0) or 0)
            swap_idx = None
            for j in range(i + 1, len(directed)):
                # never swap across beat boundaries
                cand_beat = int(directed[j].get("_beat_no", 0) or 0)
                if cur_beat and cand_beat and cand_beat != cur_beat:
                    continue
                other_sig = _signature(directed[j], context)
                if other_sig and other_sig != cur_sig:
                    swap_idx = j
                    break

            if swap_idx is not None:
                directed[i], directed[swap_idx] = directed[swap_idx], directed[i]
                last_sig = _signature(directed[i], context)
                streak = 1

        i += 1

    return directed
