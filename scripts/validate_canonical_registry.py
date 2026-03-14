#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"

ALLOWED_COVERAGE = {"wide", "medium", "detail", "hero"}
ALLOWED_ENERGY = {"low", "medium", "high"}
ALLOWED_QUALITY = {"approved", "review", "reject"}
NON_ENTRY_KEYS = {"version", "meta", "status", "about", "principles", "governed_fields", "notes", "entries"}


def load_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def extract_registry_entries(data: Any) -> tuple[dict[str, dict[str, Any]], str]:
    if not isinstance(data, dict):
        return {}, "invalid"

    if isinstance(data.get("entries"), dict):
        entries = data.get("entries") or {}
        out: dict[str, dict[str, Any]] = {}
        for k, v in entries.items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k] = v
        return out, "nested"

    out: dict[str, dict[str, Any]] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_") or k in NON_ENTRY_KEYS:
            continue
        if isinstance(v, dict):
            out[k] = v
    return out, "flat"


def split_registry_key(key: str) -> list[str]:
    return [p.strip() for p in str(key or "").split(".") if p.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate canonical_registry_v1.yaml structure with nested-entry support."
    )
    parser.add_argument(
        "--path",
        default=str(REGISTRY_PATH),
        help="Optional path to registry YAML (default: data/taxonomy/canonical_registry_v1.yaml)",
    )
    args = parser.parse_args()

    registry_path = Path(args.path).expanduser().resolve()
    data = load_yaml(registry_path)

    errors: list[str] = []
    warnings: list[str] = []

    entries, registry_mode = extract_registry_entries(data)
    if registry_mode == "invalid":
        print("Registry root must be a dictionary.")
        sys.exit(1)

    for key, value in entries.items():
        parts = split_registry_key(str(key))
        if len(parts) != 4:
            errors.append(f"{key}: registry key must have 4 dot-separated parts")
            continue

        scene_k, content_k, coverage_k, move_k = parts

        for field_name, expected in [
            ("scene", scene_k),
            ("content", content_k),
            ("coverage", coverage_k),
            ("move", move_k),
        ]:
            if field_name in value:
                actual = str(value.get(field_name, "") or "").strip().lower()
                if actual and actual != expected:
                    errors.append(f"{key}: field '{field_name}'='{actual}' does not match key part '{expected}'")
            else:
                warnings.append(f"{key}: canonical field '{field_name}' not present in entry body")

        if coverage_k not in ALLOWED_COVERAGE:
            warnings.append(f"{key}: coverage '{coverage_k}' is outside current governed set")

        human_label = value.get("human_label")
        if human_label is not None and not isinstance(human_label, str):
            errors.append(f"{key}: human_label must be a string if present")

        shoot_brief = value.get("shoot_brief")
        if shoot_brief is not None and not isinstance(shoot_brief, str):
            errors.append(f"{key}: shoot_brief must be a string if present")

        success_criteria = value.get("success_criteria")
        if success_criteria is not None and not isinstance(success_criteria, list):
            errors.append(f"{key}: success_criteria must be a list if present")

        fallback = value.get("fallback")
        if fallback is not None and not isinstance(fallback, list):
            errors.append(f"{key}: fallback must be a list if present")

        purpose = value.get("purpose")
        if purpose is not None and not isinstance(purpose, (str, list)):
            errors.append(f"{key}: purpose must be a string or list if present")

        defaults = value.get("defaults")
        if defaults is not None:
            if not isinstance(defaults, dict):
                errors.append(f"{key}: defaults must be a dictionary if present")
            else:
                energy = defaults.get("energy")
                if energy is not None and str(energy).strip().lower() not in ALLOWED_ENERGY:
                    errors.append(f"{key}: defaults.energy '{energy}' is invalid")

                quality_status = defaults.get("quality_status")
                if quality_status is not None and str(quality_status).strip().lower() not in ALLOWED_QUALITY:
                    errors.append(f"{key}: defaults.quality_status '{quality_status}' is invalid")

                for flag in ["intro_safe", "hero_safe", "outro_safe"]:
                    if flag in defaults and not isinstance(defaults.get(flag), bool):
                        errors.append(f"{key}: defaults.{flag} must be boolean if present")

    print("=== Canonical Registry Validation ===")
    print(f"path              : {registry_path}")
    print(f"registry_mode     : {registry_mode}")
    print(f"entry_count       : {len(entries)}")
    print(f"errors            : {len(errors)}")
    print(f"warnings          : {len(warnings)}")

    if warnings:
        print("warning_items:")
        for item in warnings[:80]:
            print(f"  - {item}")

    if errors:
        print("error_items:")
        for item in errors[:80]:
            print(f"  - {item}")
        sys.exit(1)

    print("validation        : PASS")


if __name__ == "__main__":
    main()
