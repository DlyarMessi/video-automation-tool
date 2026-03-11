# src/director_engine/rules/pacing.py

from typing import List, Dict, Any


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enforce pacing constraints on shot durations.

    This rule ensures that each shot duration falls within
    the [min, max] range defined in the director profile.
    """

    profile = context.get("profile", {})
    pacing_cfg = profile.get("pacing", {})

    duration_cfg = pacing_cfg.get("shot_duration", {})
    min_dur = duration_cfg.get("min")
    max_dur = duration_cfg.get("max")

    # If no pacing limits defined, do nothing
    if min_dur is None and max_dur is None:
        return shots

    adjusted = []

    for shot in shots:
        new_shot = dict(shot)  # shallow copy to avoid mutating original
        dur = new_shot.get("duration")

        if isinstance(dur, (int, float)):
            if min_dur is not None and dur < min_dur:
                new_shot["duration"] = float(min_dur)

            elif max_dur is not None and dur > max_dur:
                new_shot["duration"] = float(max_dur)

        adjusted.append(new_shot)

    return adjusted