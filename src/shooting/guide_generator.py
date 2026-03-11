# src/shooting/guide_generator.py
from typing import Dict, Any, List, Optional


class ShootingGuideGenerator:
    """
    Generate shooting requirements from a Creative Script.

    Output is a structured checklist (not cinematography lessons).
    """

    def generate(self, creative: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_creative(creative)

        meta = creative.get("meta", {}) if isinstance(creative.get("meta"), dict) else {}
        beats = creative.get("beats", [])

        guide = {
            "meta": meta,
            "required_shots": self._extract_required_shots(beats),
        }
        return guide

    def _validate_creative(self, creative: Dict[str, Any]) -> None:
        if not isinstance(creative, dict):
            raise ValueError("Creative Script must be a dict")
        if "beats" not in creative or not isinstance(creative.get("beats"), list):
            raise ValueError("Creative Script missing 'beats' list")

    def _extract_required_shots(self, beats: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        for beat in beats:
            if not isinstance(beat, dict):
                continue

            visual = beat.get("visual")
            if not isinstance(visual, str) or not visual.strip():
                continue

            dur = beat.get("duration_hint")
            dur_range = self._duration_range(dur)

            item: Dict[str, Any] = {
                "purpose": beat.get("purpose", "") or "",
                "visual_description": visual.strip(),
                "coverage": self._infer_coverage(visual.strip()),
                "recommended_duration_range": dur_range,
            }

            # pass-through optional fields for planning
            if isinstance(beat.get("tags"), list):
                item["tags"] = [str(t).strip() for t in beat["tags"] if str(t).strip()]

            if isinstance(beat.get("location"), str) and beat["location"].strip():
                item["location"] = beat["location"].strip()

            out.append(item)

        return out

    def _duration_range(self, dur: Any) -> List[float]:
        """
        Conservative duration planning range.
        If dur_hint provided, give +/- 25% range.
        """
        if isinstance(dur, (int, float)) and dur > 0:
            d = float(dur)
            return [round(d * 0.75, 2), round(d * 1.25, 2)]
        return [2.5, 5.0]

    def _infer_coverage(self, visual: str) -> List[str]:
        """
        Infer coverage types from description.
        Defaults to wide/medium/detail.
        Adds optional types when keywords appear (conservative).
        """
        v = visual.lower()
        coverage = ["wide", "medium", "detail"]

        if any(k in v for k in ["interaction", "gesture", "voice", "touchless"]):
            coverage.append("interaction")

        if any(k in v for k in ["hero", "logo", "brand", "ending"]):
            coverage.append("hero")

        if any(k in v for k in ["testing", "inspection", "lab", "quality"]):
            coverage.append("testing")

        # de-dup keep order
        seen = set()
        final = []
        for c in coverage:
            if c not in seen:
                final.append(c)
                seen.add(c)
        return final


def generate_rename_plan(guide: dict) -> str:
    """
    Generate rename_plan.txt content based on shooting_guide.json
    Order strictly follows required_shots order.
    Naming:
      <scene>_<content>_<coverage>_<move>_<index>
    """

    meta = guide.get("meta", {})
    shots = guide.get("required_shots", [])

    lines = []
    lines.append(f"# rename_plan | project={meta.get('project','')} brand={meta.get('brand','')}")
    lines.append("# Paste names sequentially while renaming clips")
    lines.append("")

    index = 1

    for item in shots:
        purpose = item.get("purpose", "")
        visual = (item.get("visual_description") or "").lower()
        coverage = item.get("coverage", [])

        # ---- infer scene ----
        if "factory" in visual:
            scene = "factory"
        elif "showroom" in visual:
            scene = "showroom"
        else:
            scene = "generic"

        # ---- infer content ----
        if "automation" in visual:
            content = "automation"
        elif "testing" in visual:
            content = "testing"
        elif "line" in visual:
            content = "line"
        elif "building" in visual or "logo" in visual:
            content = "building"
        else:
            content = purpose or "generic"

        # ---- generate one name per coverage (order matters!) ----
        for cov in coverage:
            name = f"{scene}_{content}_{cov}_static_{index:02d}"
            lines.append(name)
            index += 1

        lines.append("")

    return "\n".join(lines)