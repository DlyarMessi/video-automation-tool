# src/director_engine/engine.py

from pathlib import Path
import yaml
import importlib
from typing import List, Dict, Any


class DirectorEngine:
    """
    DirectorEngine applies editorial rules to an existing timeline
    based on a selected Director Profile.
    """

    def __init__(self, profile_name: str, profiles_dir: Path):
        self.profile_name = profile_name
        self.profiles_dir = profiles_dir
        self.profile = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        profile_path = self.profiles_dir / f"{self.profile_name}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Director profile not found: {profile_path}")

        with profile_path.open("r", encoding="utf-8") as f:
            profile = yaml.safe_load(f)

        return profile

    def apply(self, shots: List[Dict[str, Any]], extra_context: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        Apply enabled director rules sequentially to the timeline shots.
        """
        rules = self.profile.get("rules_enabled", [])
        context = {
            "profile": self.profile,
            "asset_index_path": self.profile.get("asset_index_path"),
        }

        if isinstance(extra_context, dict):
            context.update(extra_context)

        directed_shots = shots

        for rule_name in rules:
            directed_shots = self._apply_rule(rule_name, directed_shots, context)

        directed_shots = self._materialize_preferred_fields(directed_shots)
        directed_shots = self._enforce_medium_before_detail(directed_shots)
        return directed_shots

    def _enforce_medium_before_detail(self, shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = [dict(s) if isinstance(s, dict) else s for s in shots]

        def _cov(item: Dict[str, Any]) -> str:
            return str(
                item.get("_preferred_coverage")
                or item.get("coverage_canonical")
                or item.get("coverage")
                or ""
            ).strip().lower()

        def _group_key(item: Dict[str, Any]) -> tuple:
            return (
                int(item.get("_beat_no", 0) or 0),
                str(item.get("request_family", "") or "").strip(),
                str(item.get("_preferred_scene") or item.get("scene") or "").strip(),
                str(item.get("_preferred_subject") or item.get("subject") or "").strip(),
                str(item.get("_preferred_action") or item.get("action") or "").strip(),
            )

        i = 0
        while i < len(out) - 1:
            a = out[i]
            b = out[i + 1]

            if not isinstance(a, dict) or not isinstance(b, dict):
                i += 1
                continue

            if _group_key(a) == _group_key(b):
                a_cov = _cov(a)
                b_cov = _cov(b)
                if a_cov == "detail" and b_cov == "medium":
                    out[i], out[i + 1] = out[i + 1], out[i]
                    i += 2
                    continue

            i += 1

        return out


    def _materialize_preferred_fields(self, shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for shot in shots:
            if not isinstance(shot, dict):
                out.append(shot)
                continue

            new_shot = dict(shot)

            # Only materialize what the current rule stack can speak reliably today.
            if str(new_shot.get("scene", "") or "").strip():
                new_shot["_preferred_scene"] = str(new_shot.get("scene") or "").strip()

            if str(new_shot.get("subject", "") or "").strip():
                new_shot["_preferred_subject"] = str(new_shot.get("subject") or "").strip()

            if str(new_shot.get("action", "") or "").strip():
                new_shot["_preferred_action"] = str(new_shot.get("action") or "").strip()

            preferred_coverage_source = (
                str(new_shot.get("coverage_canonical", "") or "").strip()
                or str(new_shot.get("coverage", "") or "").strip()
            )
            if preferred_coverage_source:
                new_shot["_preferred_coverage"] = preferred_coverage_source

            if str(new_shot.get("move", "") or "").strip():
                new_shot["_preferred_move"] = str(new_shot.get("move") or "").strip()

            out.append(new_shot)

        return out

    def _apply_rule(
        self,
        rule_name: str,
        shots: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Dynamically load and apply a single rule module.
        """
        try:
            module = importlib.import_module(
                f"director_engine.rules.{rule_name}"
            )
        except ModuleNotFoundError:
            raise RuntimeError(f"Director rule module not found: {rule_name}")

        if not hasattr(module, "apply"):
            raise RuntimeError(
                f"Director rule '{rule_name}' must define an apply(shots, context) function"
            )

        return module.apply(shots, context)