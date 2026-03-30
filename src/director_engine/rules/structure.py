from __future__ import annotations

from typing import List, Dict, Any

from .common import (
    get_subject,
    get_action,
    get_coverage,
    is_hero_like,
    is_intro_safe,
    is_outro_safe,
    is_hero_safe,
)


def _swap_in_preferred_start(
    shots: List[Dict[str, Any]],
    context: Dict[str, Any],
    preferred_coverages: List[str],
) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    # first prefer explicit intro_safe
    if is_intro_safe(shots[0], context):
        return shots

    for i in range(1, min(len(shots), 5)):
        if is_intro_safe(shots[i], context):
            out = [dict(s) for s in shots]
            out[0], out[i] = out[i], out[0]
            return out

    first_cov = get_coverage(shots[0], context=context)
    if first_cov in preferred_coverages:
        return shots

    for i in range(1, min(len(shots), 5)):
        cov = get_coverage(shots[i], context=context)
        if cov in preferred_coverages:
            out = [dict(s) for s in shots]
            out[0], out[i] = out[i], out[0]
            return out

    return shots


def _reduce_detail_runs(shots: List[Dict[str, Any]], context: Dict[str, Any], max_run: int = 2) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    out = [dict(s) for s in shots]
    i = 0

    while i < len(out):
        if get_coverage(out[i], context=context) != "detail":
            i += 1
            continue

        run_end = i
        while run_end + 1 < len(out) and get_coverage(out[run_end + 1], context=context) == "detail":
            run_end += 1

        run_len = run_end - i + 1
        if run_len > max_run:
            swap_idx = None
            for j in range(run_end + 1, min(len(out), run_end + 5)):
                if get_coverage(out[j], context=context) != "detail":
                    swap_idx = j
                    break
            if swap_idx is not None:
                out[i + max_run], out[swap_idx] = out[swap_idx], out[i + max_run]

        i = run_end + 1

    return out


def _prefer_safe_ending(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    if is_outro_safe(shots[-1], context) or is_hero_safe(shots[-1], context):
        return shots

    best_idx = None
    for idx in range(len(shots) - 1, -1, -1):
        if is_outro_safe(shots[idx], context):
            best_idx = idx
            break

    if best_idx is None:
        for idx in range(len(shots) - 1, -1, -1):
            if is_hero_safe(shots[idx], context):
                best_idx = idx
                break

    if best_idx is None:
        last_beat = int(shots[-1].get("_beat_no", 0) or 0)
        for idx in range(len(shots) - 1, -1, -1):
            shot_beat = int(shots[idx].get("_beat_no", 0) or 0)
            # prefer hero from same beat as current ending, or unassigned
            if shot_beat and last_beat and shot_beat != last_beat:
                continue
            if is_hero_like(shots[idx], context=context):
                best_idx = idx
                break
    # fallback: search all shots if beat-constrained search found nothing
    if best_idx is None:
        for idx in range(len(shots) - 1, -1, -1):
            if is_hero_like(shots[idx], context=context):
                best_idx = idx
                break

    if best_idx is not None and best_idx != len(shots) - 1:
        out = [dict(s) for s in shots]
        best = out.pop(best_idx)
        out.append(best)
        return out

    return shots


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    profile = context.get("profile", {})
    structure_cfg = profile.get("structure", {}) or {}
    directed = [dict(s) for s in shots]

    first_subject = get_subject(directed[0], context=context)

    if first_subject in {"environment", "machine", ""}:
        directed = _swap_in_preferred_start(directed, context, ["wide", "medium"])

    if any(get_action(s, context=context) == "operate" for s in directed):
        directed = _swap_in_preferred_start(directed, context, ["wide", "medium"])

    if any(get_action(s, context=context) == "inspect" for s in directed):
        max_detail = int(structure_cfg.get("trust_max_consecutive_detail", 2) or 2)
        directed = _reduce_detail_runs(directed, context=context, max_run=max_detail)

    require_hero_last = bool(structure_cfg.get("require_hero_last", True))
    if require_hero_last:
        directed = _prefer_safe_ending(directed, context)

    return directed
