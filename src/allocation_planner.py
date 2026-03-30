from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.material_index import find_asset_record


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
    def __init__(self, picker: Any):
        self.picker = picker
        self.context = AllocationContext()

    def build_intent(self, shot: Dict[str, Any], shot_index: int) -> ShotIntent:
        return ShotIntent(
            shot_index=shot_index,
            source_spec=str(shot.get("source") or shot.get("material") or ""),
            scene=str(shot.get("scene") or ""),
            subject=str(shot.get("subject") or ""),
            action=str(shot.get("action") or ""),
            coverage=str(shot.get("coverage") or ""),
            move=str(shot.get("move") or ""),
        )

    def _asset_record(self, candidate: Path) -> Dict[str, Any]:
        return find_asset_record(self.picker.asset_index_path, candidate.name) or {}

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

    def select_primary(self, intent: ShotIntent, shot: Optional[Dict[str, Any]] = None) -> SelectionDecision:
        context = shot if isinstance(shot, dict) else {}
        raw_candidates: List[Path] = self.picker.get_candidates(intent.source_spec, context=context)
        if not raw_candidates:
            return SelectionDecision(
                selected_path="",
                fallback_level="failed",
                reason=f"No candidates for spec: {intent.source_spec}",
                candidate_count=0,
                asset_id="",
            )

        allocatable = self._filter_allocatable_assets(raw_candidates)
        if not allocatable:
            return SelectionDecision(
                selected_path="",
                fallback_level="failed",
                reason="Candidates found, but none are valid_allocatable",
                candidate_count=len(raw_candidates),
                asset_id="",
            )

        fresh = self._filter_used_assets(allocatable)
        fallback_level = "exact"
        ranked_source = fresh

        if not ranked_source:
            ranked_source = allocatable
            fallback_level = "repeat_fallback"

        ranked = self._rank_candidates(ranked_source)
        selected = ranked[0]
        rec = self._register_selection(selected)

        return SelectionDecision(
            selected_path=str(selected),
            fallback_level=fallback_level,
            reason="Selected planner-owned candidate after allocatable filter, asset dedupe, and style ranking",
            candidate_count=len(allocatable),
            asset_id=str(rec.get("asset_id", "") or ""),
            primary_bucket_signature=str(rec.get("primary_bucket_signature", "") or ""),
            style_signature=str(rec.get("style_signature", "") or ""),
            ingest_status_label=str(rec.get("ingest_status_label", "") or ""),
        )
