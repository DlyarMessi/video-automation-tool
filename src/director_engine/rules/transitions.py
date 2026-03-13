from __future__ import annotations

from typing import List, Dict, Any

from .common import same_family, get_primary_tag, get_coverage


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    profile = context.get("profile", {})
    trans_cfg = profile.get("transitions", {}) or {}

    default_transition = str(trans_cfg.get("default", "cut") or "cut")
    fade_duration = float(trans_cfg.get("fade_duration", 0.25) or 0.25)
    disable_fade_when_same_tag = bool(trans_cfg.get("disable_fade_when_same_tag", True))

    directed = [dict(s) for s in shots]
    prev_tag = None

    for i, shot in enumerate(directed):
        cur_tag = get_primary_tag(shot)

        if i == 0:
            shot["transition"] = {"type": "cut"}
            prev_tag = cur_tag
            continue

        prev_shot = directed[i - 1]
        transition_type = default_transition

        # same family should almost always hard cut
        if same_family(prev_shot, shot):
            transition_type = "cut"

        # repeated detail chain should not fade
        if get_coverage(prev_shot) == "detail" and get_coverage(shot) == "detail":
            transition_type = "cut"

        if disable_fade_when_same_tag and cur_tag and cur_tag == prev_tag:
            transition_type = "cut"

        if transition_type == "fade":
            shot["transition"] = {"type": "fade", "duration": fade_duration}
        else:
            shot["transition"] = {"type": "cut"}

        prev_tag = cur_tag

    return directed
