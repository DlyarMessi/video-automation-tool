from __future__ import annotations

from typing import List, Dict, Any

from .common import get_coverage, get_energy


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not shots:
        return shots

    profile = context.get("profile", {})
    pacing_cfg = profile.get("pacing", {}) or {}
    duration_cfg = pacing_cfg.get("shot_duration", {}) or {}
    energy_cfg = pacing_cfg.get("energy_adjustments", {}) or {}

    min_dur = duration_cfg.get("min")
    max_dur = duration_cfg.get("max")

    adjusted = []

    for shot in shots:
        new_shot = dict(shot)
        dur = new_shot.get("duration")

        if isinstance(dur, (int, float)):
            target = float(dur)

            energy = get_energy(new_shot, context)
            mul = float(energy_cfg.get(energy, 1.0) or 1.0)
            target *= mul

            coverage = get_coverage(new_shot)
            if coverage == "detail":
                target *= 0.92
            elif coverage == "hero":
                target *= 1.08

            shot_hint = float(new_shot.get("_beat_duration_hint", 0) or 0)
            if shot_hint > 0:
                target = max(min(float(min_dur or 2.5), shot_hint), 1.5)
                if max_dur is not None:
                    target = min(float(max_dur), target)
            else:
                if min_dur is not None:
                    target = max(float(min_dur), target)
                if max_dur is not None:
                    target = min(float(max_dur), target)

            new_shot["duration"] = round(float(target), 3)

        adjusted.append(new_shot)

    return adjusted
