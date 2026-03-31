from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class RescuePolicy:
    # Very small safe extension that does not look obviously awkward.
    max_soft_extend_s: float = 0.35

    # Level 0: same exact semantic need
    allow_same_need_key: bool = True

    # Level 1: same beat/request family/scene/subject/action
    allow_same_rescue_key: bool = True

    # Level 2: same beat only, but must be explicitly invoked later
    allow_same_beat_family: bool = False

    # Hard stop after this level
    max_level: int = 1


@dataclass
class RescueCandidate:
    level: int
    reason: str
    source_index: int
    need_key: str = ""
    rescue_key: str = ""
    beat_no: int = 0
    request_family: str = ""
    scene: str = ""
    subject: str = ""
    action: str = ""
    coverage_canonical: str = ""
    move: str = ""


@dataclass
class RescuePlan:
    anchor_index: int
    overrun_s: float
    soft_extend_s: float = 0.0
    candidates: List[RescueCandidate] = field(default_factory=list)
    blocked_reason: str = ""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def build_rescue_candidate_map(seq: List[Dict[str, Any]]) -> Dict[int, List[RescueCandidate]]:
    out: Dict[int, List[RescueCandidate]] = {}

    by_need: Dict[str, List[int]] = {}
    by_rescue: Dict[str, List[int]] = {}
    by_beat: Dict[int, List[int]] = {}

    for idx, shot in enumerate(seq):
        if not isinstance(shot, dict):
            continue

        need_key = _clean_text(shot.get("_need_key", ""))
        rescue_key = _clean_text(shot.get("_rescue_key", ""))
        beat_no = _as_int(shot.get("_beat_no", 0))

        if need_key:
            by_need.setdefault(need_key, []).append(idx)
        if rescue_key:
            by_rescue.setdefault(rescue_key, []).append(idx)
        if beat_no > 0:
            by_beat.setdefault(beat_no, []).append(idx)

    for idx, shot in enumerate(seq):
        if not isinstance(shot, dict):
            out[idx] = []
            continue

        need_key = _clean_text(shot.get("_need_key", ""))
        rescue_key = _clean_text(shot.get("_rescue_key", ""))
        beat_no = _as_int(shot.get("_beat_no", 0))

        candidates: List[RescueCandidate] = []

        # Level 0 — same semantic need
        for other_idx in by_need.get(need_key, []):
            if other_idx == idx:
                continue
            other = seq[other_idx]
            if not isinstance(other, dict):
                continue
            candidates.append(
                RescueCandidate(
                    level=0,
                    reason="same_need_key",
                    source_index=other_idx,
                    need_key=_clean_text(other.get("_need_key", "")),
                    rescue_key=_clean_text(other.get("_rescue_key", "")),
                    beat_no=_as_int(other.get("_beat_no", 0)),
                    request_family=_clean_text(other.get("request_family", "")),
                    scene=_clean_text(other.get("scene", "")),
                    subject=_clean_text(other.get("subject", "")),
                    action=_clean_text(other.get("action", "")),
                    coverage_canonical=_clean_text(other.get("coverage_canonical", "")),
                    move=_clean_text(other.get("move", "")),
                )
            )

        # Level 1 — same rescue group
        for other_idx in by_rescue.get(rescue_key, []):
            if other_idx == idx:
                continue
            if any(c.source_index == other_idx for c in candidates):
                continue
            other = seq[other_idx]
            if not isinstance(other, dict):
                continue
            candidates.append(
                RescueCandidate(
                    level=1,
                    reason="same_rescue_key",
                    source_index=other_idx,
                    need_key=_clean_text(other.get("_need_key", "")),
                    rescue_key=_clean_text(other.get("_rescue_key", "")),
                    beat_no=_as_int(other.get("_beat_no", 0)),
                    request_family=_clean_text(other.get("request_family", "")),
                    scene=_clean_text(other.get("scene", "")),
                    subject=_clean_text(other.get("subject", "")),
                    action=_clean_text(other.get("action", "")),
                    coverage_canonical=_clean_text(other.get("coverage_canonical", "")),
                    move=_clean_text(other.get("move", "")),
                )
            )

        # Level 2 — same beat only (recorded, but not enabled by default)
        for other_idx in by_beat.get(beat_no, []):
            if other_idx == idx:
                continue
            if any(c.source_index == other_idx for c in candidates):
                continue
            other = seq[other_idx]
            if not isinstance(other, dict):
                continue
            candidates.append(
                RescueCandidate(
                    level=2,
                    reason="same_beat_only",
                    source_index=other_idx,
                    need_key=_clean_text(other.get("_need_key", "")),
                    rescue_key=_clean_text(other.get("_rescue_key", "")),
                    beat_no=_as_int(other.get("_beat_no", 0)),
                    request_family=_clean_text(other.get("request_family", "")),
                    scene=_clean_text(other.get("scene", "")),
                    subject=_clean_text(other.get("subject", "")),
                    action=_clean_text(other.get("action", "")),
                    coverage_canonical=_clean_text(other.get("coverage_canonical", "")),
                    move=_clean_text(other.get("move", "")),
                )
            )

        out[idx] = sorted(candidates, key=lambda c: (c.level, c.source_index))

    return out


def plan_duration_rescue(
    *,
    seq: List[Dict[str, Any]],
    anchor_index: int,
    overrun_s: float,
    policy: RescuePolicy | None = None,
) -> RescuePlan:
    policy = policy or RescuePolicy()
    plan = RescuePlan(anchor_index=anchor_index, overrun_s=float(overrun_s))

    if overrun_s <= 0:
        return plan

    # Always allow a tiny, visually-safe extension before clip insertion.
    plan.soft_extend_s = min(float(overrun_s), float(policy.max_soft_extend_s))

    candidate_map = build_rescue_candidate_map(seq)
    raw_candidates = candidate_map.get(anchor_index, [])

    allowed_levels = {0}
    if policy.allow_same_rescue_key:
        allowed_levels.add(1)
    if policy.allow_same_beat_family:
        allowed_levels.add(2)

    plan.candidates = [c for c in raw_candidates if c.level in allowed_levels and c.level <= policy.max_level]

    if not plan.candidates and overrun_s > plan.soft_extend_s:
        plan.blocked_reason = "No allowed rescue candidates under current policy."

    return plan
