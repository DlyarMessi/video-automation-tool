from __future__ import annotations

from typing import List, Dict, Any

from .common import (
    same_scene,
    same_content,
    same_family,
    get_coverage,
    get_move,
    is_progressive_coverage,
    get_continuity_group,
    get_quality_status,
)


def _quality_bonus(shot: Dict[str, Any], context: Dict[str, Any]) -> int:
    q = get_quality_status(shot, context)
    if q == "approved":
        return 2
    if q == "review":
        return 0
    if q == "reject":
        return -6
    return 0


def _pair_score(prev_shot: Dict[str, Any], cur_shot: Dict[str, Any], context: Dict[str, Any]) -> int:
    score = 0

    if same_scene(prev_shot, cur_shot):
        score += 2
    if same_content(prev_shot, cur_shot):
        score += 2
    if same_family(prev_shot, cur_shot):
        score += 2
    if is_progressive_coverage(prev_shot, cur_shot):
        score += 3

    prev_group = get_continuity_group(prev_shot, context)
    cur_group = get_continuity_group(cur_shot, context)
    if prev_group and cur_group and prev_group == cur_group:
        score += 4

    prev_cov = get_coverage(prev_shot)
    cur_cov = get_coverage(cur_shot)
    if prev_cov == "detail" and cur_cov == "detail":
        score -= 4

    prev_move = get_move(prev_shot)
    cur_move = get_move(cur_shot)
    if prev_move and cur_move and prev_move != cur_move:
        score -= 1

    score += _quality_bonus(cur_shot, context)
    return score


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    profile = context.get("profile", {})
    continuity_cfg = profile.get("continuity", {}) or {}
    local_swap_window = int(continuity_cfg.get("local_swap_window", 4) or 4)

    directed = [dict(s) for s in shots]

    for i in range(1, len(directed)):
        prev_shot = directed[i - 1]
        cur_shot = directed[i]
        base_score = _pair_score(prev_shot, cur_shot, context)

        best_idx = i
        best_score = base_score

        for j in range(i + 1, min(len(directed), i + 1 + local_swap_window)):
            cand_score = _pair_score(prev_shot, directed[j], context)
            if cand_score > best_score:
                best_score = cand_score
                best_idx = j

        if best_idx != i:
            directed[i], directed[best_idx] = directed[best_idx], directed[i]

    return directed
