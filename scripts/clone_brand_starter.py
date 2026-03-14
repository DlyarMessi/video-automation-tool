#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
STARTER_DIR = ROOT / "data" / "brands" / "_starter"
BRANDS_DIR = ROOT / "data" / "brands"


def safe_slug(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value


def clone_brand_starter(brand_name: str, slug: str | None = None) -> Path:
    if not STARTER_DIR.exists():
        raise FileNotFoundError(f"Starter directory not found: {STARTER_DIR}")

    brand_name_clean = (brand_name or "").strip()
    if not brand_name_clean:
        raise ValueError("brand_name cannot be empty")

    brand_slug = safe_slug(slug or brand_name_clean)
    if not brand_slug:
        raise ValueError("Could not derive a valid brand slug")

    if brand_slug == "_starter":
        raise ValueError("Brand slug '_starter' is reserved")

    target_dir = BRANDS_DIR / brand_slug
    if target_dir.exists():
        raise FileExistsError(f"Target brand directory already exists: {target_dir}")

    shutil.copytree(STARTER_DIR, target_dir)

    default_plan = target_dir / "pool_plans" / "default.yaml"
    if default_plan.exists():
        data = yaml.safe_load(default_plan.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            data["brand"] = brand_name_clean
            default_plan.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

    return target_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clone the brand starter package into a new data/brands/<slug>/ directory."
    )
    parser.add_argument("brand_name", help="Human-facing brand name, e.g. 'Acme Elevators'")
    parser.add_argument(
        "--slug",
        default="",
        help="Optional filesystem slug. If omitted, a slug is derived from brand_name.",
    )
    args = parser.parse_args()

    out = clone_brand_starter(args.brand_name, args.slug or None)
    print(f"Created brand starter at: {out}")
    print(f"Next expected asset: {out / 'logo.png'}")
    print(f"Starter pool plan: {out / 'pool_plans' / 'default.yaml'}")


if __name__ == "__main__":
    main()
