from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ManagedBrandPath:
    key: str
    relative_path: Path


def build_managed_brand_paths(*, root: Path, company: str, slugify: Callable[[str], str], input_root: Path) -> list[ManagedBrandPath]:
    company_clean = str(company or "").strip()
    company_slug = str(slugify(company_clean)).lower()

    return [
        ManagedBrandPath("brand_data", Path("data") / "brands" / company_slug),
        ManagedBrandPath("creative_scripts", Path("creative_scripts") / company_clean),
        ManagedBrandPath("input_portrait", input_root / "portrait" / company_clean),
        ManagedBrandPath("input_landscape", input_root / "landscape" / company_clean),
        ManagedBrandPath("output_portrait", Path("output_videos") / "portrait" / company_clean),
        ManagedBrandPath("output_landscape", Path("output_videos") / "landscape" / company_clean),
    ]


def provision_brand_workspace(*, root: Path, company: str, slugify: Callable[[str], str], input_root: Path) -> list[Path]:
    created_or_ensured: list[Path] = []
    for managed in build_managed_brand_paths(root=root, company=company, slugify=slugify, input_root=input_root):
        target = managed.relative_path if managed.relative_path.is_absolute() else (root / managed.relative_path)
        target.mkdir(parents=True, exist_ok=True)
        created_or_ensured.append(target)

    # Ensure pool fill subdirs used by runtime exist under input dirs.
    for orientation in ("portrait", "landscape"):
        company_root = input_root / orientation / str(company).strip()
        for leaf in ("_INBOX", "factory"):
            path = company_root / leaf
            path.mkdir(parents=True, exist_ok=True)
            created_or_ensured.append(path)

    return created_or_ensured


def scan_brand_workspace(*, root: Path, company: str, slugify: Callable[[str], str], input_root: Path) -> dict:
    paths: list[dict] = []
    total_files = 0
    any_exists = False

    for managed in build_managed_brand_paths(root=root, company=company, slugify=slugify, input_root=input_root):
        target = managed.relative_path if managed.relative_path.is_absolute() else (root / managed.relative_path)
        exists = target.exists()
        file_count = 0
        if exists and target.is_dir():
            file_count = sum(1 for p in target.rglob("*") if p.is_file())
        elif exists and target.is_file():
            file_count = 1

        any_exists = any_exists or exists
        total_files += file_count
        paths.append(
            {
                "key": managed.key,
                "path": str(target),
                "exists": exists,
                "file_count": file_count,
            }
        )

    return {
        "paths": paths,
        "any_exists": any_exists,
        "total_files": total_files,
    }


def delete_brand_workspace(*, root: Path, company: str, slugify: Callable[[str], str], input_root: Path) -> dict:
    deleted: list[str] = []
    skipped: list[str] = []

    for managed in build_managed_brand_paths(root=root, company=company, slugify=slugify, input_root=input_root):
        target = managed.relative_path if managed.relative_path.is_absolute() else (root / managed.relative_path)

        # safety: never touch starter/template-ish paths
        if any(token in {"_starter", "template"} for token in target.parts):
            skipped.append(str(target))
            continue

        if not target.exists():
            continue
        if target.is_file():
            target.unlink(missing_ok=True)
            deleted.append(str(target))
            continue
        shutil.rmtree(target)
        deleted.append(str(target))

    return {"deleted": deleted, "skipped": skipped}


def list_managed_brand_names(*, root: Path) -> list[str]:
    """Return selector-safe brand names from managed workspaces only."""
    brands_dir = root / "data" / "brands"
    if not brands_dir.exists():
        return []

    names: list[str] = []
    seen: set[str] = set()

    for brand_dir in sorted(brands_dir.iterdir(), key=lambda p: p.name.lower()):
        if not brand_dir.is_dir():
            continue
        if brand_dir.name.startswith(".") or brand_dir.name == "_starter":
            continue

        display_name = ""
        default_plan = brand_dir / "pool_plans" / "default.yaml"
        if default_plan.exists():
            try:
                for line in default_plan.read_text(encoding="utf-8").splitlines():
                    stripped = str(line or "").strip()
                    if stripped.lower().startswith("brand:"):
                        display_name = stripped.split(":", 1)[1].strip().strip('"\'')
                        break
            except Exception:
                display_name = ""

        candidate = display_name or brand_dir.name
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(candidate)

    return names
