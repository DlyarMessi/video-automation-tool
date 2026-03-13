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

        return directed_shots

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