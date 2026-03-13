from __future__ import annotations

from typing import List, Dict, Any

from .common import is_hero_like, is_randomish, is_outro_safe, is_hero_safe


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    profile = context.get("profile", {})
    ending_cfg = profile.get("ending", {}) or {}
    pacing_cfg = profile.get("pacing", {}) or {}

    ending_hold = float(pacing_cfg.get("ending_hold", 0.0) or 0.0)
    require_hero = bool(ending_cfg.get("require_hero_tag", False))
    forbid_random_last = bool(ending_cfg.get("forbid_random_last", False))

    directed = [dict(s) for s in shots]

    if require_hero or forbid_random_last:
        last = directed[-1]
        need_replace = False

        if require_hero and not (is_outro_safe(last, context) or is_hero_safe(last, context) or is_hero_like(last)):
            need_replace = True

        if forbid_random_last and is_randomish(last):
            need_replace = True

        if need_replace:
            best_idx = None

            for idx in range(len(directed) - 1, -1, -1):
                cand = directed[idx]
                if is_outro_safe(cand, context) and (not forbid_random_last or not is_randomish(cand)):
                    best_idx = idx
                    break

            if best_idx is None:
                for idx in range(len(directed) - 1, -1, -1):
                    cand = directed[idx]
                    if is_hero_safe(cand, context) and (not forbid_random_last or not is_randomish(cand)):
                        best_idx = idx
                        break

            if best_idx is None:
                for idx in range(len(directed) - 1, -1, -1):
                    cand = directed[idx]
                    if is_hero_like(cand) and (not forbid_random_last or not is_randomish(cand)):
                        best_idx = idx
                        break

            if best_idx is not None and best_idx != len(directed) - 1:
                best = directed.pop(best_idx)
                directed.append(best)

    if ending_hold > 0:
        last = dict(directed[-1])
        dur = last.get("duration")
        if isinstance(dur, (int, float)):
            last["duration"] = float(dur) + ending_hold
        else:
            last["duration"] = ending_hold
        directed[-1] = last

    return directed
