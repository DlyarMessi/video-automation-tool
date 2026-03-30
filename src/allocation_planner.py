from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.material_index import find_asset_record, parse_canonical_stem


@dataclass
class ShotIntent:
    shot_index: int
    source_spec: str
    scene: str = ""
    subject: str = ""
    action: str = ""
    coverage: str = ""
    move: str = ""


@dataclass
class SelectionDecision:
    selected_path: str = ""
    fallback_level: str = "failed"
    reason: str = ""
    candidate_count: int = 0
    asset_id: str = ""
    primary_bucket_signature: str = ""
    style_signature: str = ""
    ingest_status_label: str = ""


@dataclass
class AllocationContext:
    used_asset_ids: set[str] = field(default_factory=set)
    recent_bucket_signatures: List[str] = field(default_factory=list)
    recent_style_signatures: List[str] = field(default_factory=list)


class AllocationPlanner:
    COVERAGE_NEIGHBORS = {
        "detail": {"close"},
        "close": {"detail", "medium"},
        "medium": {"close", "wide"},
        "wide": {"medium"},
    }

    def __init__(self, picker: Any):
        self.picker = picker
        self.context = AllocationContext()

    def build_intent(self, shot: Dict[str, Any], shot_index: int) -> ShotIntent:
        source_spec = str(shot.get("source") or shot.get("material") or "")

        scene = str(
            shot.get("_preferred_scene")
            or shot.get("preferred_scene")
            or shot.get("scene")
            or ""
        )
        subject = str(
            shot.get("_preferred_subject")
            or shot.get("preferred_subject")
            or shot.get("subject")
            or ""
        )
        action = str(
            shot.get("_preferred_action")
            or shot.get("preferred_action")
            or shot.get("action")
            or ""
        )
        coverage = str(
            shot.get("_preferred_coverage")
            or shot.get("preferred_coverage")
            or shot.get("coverage")
            or ""
        )
        move = str(
            shot.get("_preferred_move")
            or shot.get("preferred_move")
            or shot.get("move")
            or ""
        )

        # Allow planner to consume canonical direct source specs immediately.
        if source_spec and "_" in source_spec and not source_spec.startswith(("tags:", "regex:", "random", "next")):
            parsed = parse_canonical_stem(source_spec)
            if parsed.get("is_valid"):
                scene = scene or str(parsed.get("scene") or "")
                subject = subject or str(parsed.get("subject") or "")
                action = action or str(parsed.get("action") or "")
                coverage = coverage or str(parsed.get("coverage") or "")
                move = move or str(parsed.get("move") or "")

        return ShotIntent(
            shot_index=shot_index,
            source_spec=source_spec,
            scene=scene,
            subject=subject,
            action=action,
            coverage=coverage,
            move=move,
        )

    def _asset_record(self, candidate: Path) -> Dict[str, Any]:
        return find_asset_record(self.picker.asset_index_path, candidate.name) or {}

    def _base_candidates(self, intent: ShotIntent, shot: Optional[Dict[str, Any]]) -> List[Path]:
        context = shot if isinstance(shot, dict) else {}
        return self.picker.get_candidates(intent.source_spec, context=context)

    def _filter_allocatable_assets(self, candidates: List[Path]) -> List[Path]:
        out: List[Path] = []
        for candidate in candidates:
            rec = self._asset_record(candidate)
            if str(rec.get("ingest_status", "") or "") == "valid_allocatable":
                out.append(candidate)
        return out

    def _filter_used_assets(self, candidates: List[Path]) -> List[Path]:
        fresh: List[Path] = []
        for candidate in candidates:
            rec = self._asset_record(candidate)
            asset_id = str(rec.get("asset_id", "") or "")
            if asset_id and asset_id in self.context.used_asset_ids:
                continue
            fresh.append(candidate)
        return fresh

    def _matches_primary_bucket(self, rec: Dict[str, Any], intent: ShotIntent) -> bool:
        if intent.scene and str(rec.get("scene", "") or "") != intent.scene:
            return False
        if intent.subject and str(rec.get("subject", "") or "") != intent.subject:
            return False
        if intent.action and str(rec.get("action", "") or "") != intent.action:
            return False
        return True

    def _matches_exact_style(self, rec: Dict[str, Any], intent: ShotIntent) -> bool:
        if intent.coverage and str(rec.get("coverage", "") or "") != intent.coverage:
            return False
        if intent.move and str(rec.get("move", "") or "") != intent.move:
            return False
        return True

    def _matches_level1_style(self, rec: Dict[str, Any], intent: ShotIntent) -> bool:
        if intent.coverage and str(rec.get("coverage", "") or "") != intent.coverage:
            return False
        return True

    def _matches_level2_style(self, rec: Dict[str, Any], intent: ShotIntent) -> bool:
        if not intent.coverage:
            return True
        rec_cov = str(rec.get("coverage", "") or "")
        if rec_cov == intent.coverage:
            return True
        return rec_cov in self.COVERAGE_NEIGHBORS.get(intent.coverage, set())

    def _primary_bucket_candidates(self, candidates: List[Path], intent: ShotIntent) -> List[Path]:
        # If intent has no structured bucket fields yet, keep current source-spec path alive.
        if not (intent.scene or intent.subject or intent.action):
            return candidates
        out: List[Path] = []
        for candidate in candidates:
            rec = self._asset_record(candidate)
            if self._matches_primary_bucket(rec, intent):
                out.append(candidate)
        return out

    def _level0_candidates(self, candidates: List[Path], intent: ShotIntent) -> List[Path]:
        if not (intent.coverage or intent.move):
            return candidates
        out: List[Path] = []
        for candidate in candidates:
            rec = self._asset_record(candidate)
            if self._matches_exact_style(rec, intent):
                out.append(candidate)
        return out

    def _level1_candidates(self, candidates: List[Path], intent: ShotIntent) -> List[Path]:
        if not intent.coverage:
            return candidates
        out: List[Path] = []
        for candidate in candidates:
            rec = self._asset_record(candidate)
            if self._matches_level1_style(rec, intent):
                out.append(candidate)
        return out

    def _level2_candidates(self, candidates: List[Path], intent: ShotIntent) -> List[Path]:
        out: List[Path] = []
        for candidate in candidates:
            rec = self._asset_record(candidate)
            if self._matches_level2_style(rec, intent):
                out.append(candidate)
        return out

    def _style_penalty(self, candidate: Path) -> int:
        rec = self._asset_record(candidate)
        style = str(rec.get("style_signature", "") or "")
        if not style:
            return 0
        recent = self.context.recent_style_signatures[-3:]
        return 1 if style in recent else 0

    def _bucket_penalty(self, candidate: Path) -> int:
        rec = self._asset_record(candidate)
        bucket = str(rec.get("primary_bucket_signature", "") or "")
        if not bucket:
            return 0
        recent = self.context.recent_bucket_signatures[-2:]
        return 1 if bucket in recent else 0

    def _quality_rank(self, candidate: Path) -> int:
        rec = self._asset_record(candidate)
        status = str(rec.get("quality_status", "") or "").strip().lower()
        if status == "approved":
            return 0
        if status == "review":
            return 2
        if status == "reject":
            return 9
        return 1

    def _rank_candidates(self, candidates: List[Path]) -> List[Path]:
        return sorted(
            candidates,
            key=lambda p: (
                self._style_penalty(p),
                self._bucket_penalty(p),
                self._quality_rank(p),
                str(p),
            ),
        )

    def _register_selection(self, candidate: Path) -> Dict[str, Any]:
        rec = self._asset_record(candidate)
        asset_id = str(rec.get("asset_id", "") or "")
        bucket = str(rec.get("primary_bucket_signature", "") or "")
        style = str(rec.get("style_signature", "") or "")

        if asset_id:
            self.context.used_asset_ids.add(asset_id)
        if bucket:
            self.context.recent_bucket_signatures.append(bucket)
            self.context.recent_bucket_signatures = self.context.recent_bucket_signatures[-5:]
        if style:
            self.context.recent_style_signatures.append(style)
            self.context.recent_style_signatures = self.context.recent_style_signatures[-5:]
        return rec

    def _build_decision(
        self,
        *,
        candidate: Path,
        fallback_level: str,
        reason: str,
        candidate_count: int,
    ) -> SelectionDecision:
        rec = self._register_selection(candidate)
        return SelectionDecision(
            selected_path=str(candidate),
            fallback_level=fallback_level,
            reason=reason,
            candidate_count=candidate_count,
            asset_id=str(rec.get("asset_id", "") or ""),
            primary_bucket_signature=str(rec.get("primary_bucket_signature", "") or ""),
            style_signature=str(rec.get("style_signature", "") or ""),
            ingest_status_label=str(rec.get("ingest_status_label", "") or ""),
        )

    def select_primary(self, intent: ShotIntent, shot: Optional[Dict[str, Any]] = None) -> SelectionDecision:
        raw_candidates = self._base_candidates(intent, shot=shot)
        if not raw_candidates:
            return SelectionDecision(
                selected_path="",
                fallback_level="failed",
                reason=f"No candidates for spec: {intent.source_spec}",
                candidate_count=0,
            )

        allocatable = self._filter_allocatable_assets(raw_candidates)
        if not allocatable:
            return SelectionDecision(
                selected_path="",
                fallback_level="failed",
                reason="Candidates found, but none are valid_allocatable",
                candidate_count=len(raw_candidates),
            )

        primary_bucket = self._primary_bucket_candidates(allocatable, intent)
        if not primary_bucket:
            return SelectionDecision(
                selected_path="",
                fallback_level="failed",
                reason="Primary bucket empty; not auto-relaxing scene/subject/action",
                candidate_count=len(allocatable),
            )

        level0 = self._filter_used_assets(self._level0_candidates(primary_bucket, intent))
        if level0:
            ranked = self._rank_candidates(level0)
            return self._build_decision(
                candidate=ranked[0],
                fallback_level="level0_exact",
                reason="Selected exact scene+subject+action+coverage+move match",
                candidate_count=len(level0),
            )

        level1 = self._filter_used_assets(self._level1_candidates(primary_bucket, intent))
        if level1:
            ranked = self._rank_candidates(level1)
            return self._build_decision(
                candidate=ranked[0],
                fallback_level="level1_move_relaxed",
                reason="Selected exact bucket + coverage, with move relaxed",
                candidate_count=len(level1),
            )

        level2 = self._filter_used_assets(self._level2_candidates(primary_bucket, intent))
        if level2:
            ranked = self._rank_candidates(level2)
            return self._build_decision(
                candidate=ranked[0],
                fallback_level="level2_coverage_neighbor",
                reason="Selected exact bucket with neighbor coverage and move relaxed",
                candidate_count=len(level2),
            )

        return SelectionDecision(
            selected_path="",
            fallback_level="failed",
            reason="Primary bucket exists, but no selectable candidate survived level0/1/2",
            candidate_count=len(primary_bucket),
        )
