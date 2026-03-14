from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable


import yaml


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def get_brand_dir(root: Path, company: str, slugify: Callable[[str], str]) -> Path:
    company_clean = _clean_text(company)
    slug = str(slugify(company_clean)).lower()
    return root / "data" / "brands" / slug


def clone_brand_starter_into_project(
    root: Path,
    brand_name: str,
    slugify: Callable[[str], str],
    brand_slug: str = "",
) -> tuple[bool, str]:
    starter_dir = root / "data" / "brands" / "_starter"
    brands_dir = root / "data" / "brands"

    if not starter_dir.exists():
        return False, "Starter brand template is missing at data/brands/_starter/"

    brand_name_clean = _clean_text(brand_name)
    if not brand_name_clean:
        return False, "Please enter a brand name."

    slug = str(slugify(brand_slug or brand_name_clean)).lower()
    if not slug:
        return False, "Could not derive a valid brand slug."

    if slug == "_starter":
        return False, "The slug '_starter' is reserved."

    target_dir = brands_dir / slug
    if target_dir.exists():
        return False, f"Brand directory already exists: data/brands/{slug}/"

    try:
        shutil.copytree(starter_dir, target_dir)

        default_plan = target_dir / "pool_plans" / "default.yaml"
        if default_plan.exists():
            data = yaml.safe_load(default_plan.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                data["brand"] = brand_name_clean
                default_plan.write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )

        return True, (
            f"Created brand skeleton: data/brands/{slug}/  |  "
            f"Next: add logo.png and refine pool_plans/default.yaml"
        )
    except Exception as e:
        return False, f"Failed to create brand skeleton: {e}"


def save_brand_logo(
    root: Path,
    company: str,
    slugify: Callable[[str], str],
    uploaded_logo,
) -> tuple[bool, str]:
    company_clean = _clean_text(company)
    slug = str(slugify(company_clean)).lower()
    if not slug:
        return False, "Could not determine a valid brand slug."

    if uploaded_logo is None:
        return False, "Please choose a logo file first."

    brand_dir = root / "data" / "brands" / slug
    brand_dir.mkdir(parents=True, exist_ok=True)
    logo_path = brand_dir / "logo.png"

    try:
        logo_path.write_bytes(uploaded_logo.getbuffer().tobytes())
        return True, f"Saved logo to data/brands/{slug}/logo.png"
    except Exception as e:
        return False, f"Failed to save logo: {e}"


def save_brand_pool_plan(
    root: Path,
    company: str,
    slugify: Callable[[str], str],
    uploaded_plan,
    plan_name: str = "",
) -> tuple[bool, str, str]:
    company_clean = _clean_text(company)
    slug = str(slugify(company_clean)).lower()
    if not slug:
        return False, "Could not determine a valid brand slug.", ""

    if uploaded_plan is None:
        return False, "Please choose a YAML file first.", ""

    try:
        raw = uploaded_plan.getbuffer().tobytes().decode("utf-8")
    except Exception:
        return False, "Could not decode uploaded YAML as UTF-8.", ""

    try:
        data = yaml.safe_load(raw) or {}
    except Exception as e:
        return False, f"Invalid YAML: {e}", ""

    if not isinstance(data, dict):
        return False, "Pool plan YAML must be a dictionary at the top level.", ""

    topics = data.get("topics", [])
    if not isinstance(topics, list):
        return False, "Pool plan YAML must contain a list field: topics", ""

    data["brand"] = company_clean

    original_name = ""
    try:
        original_name = Path(str(getattr(uploaded_plan, "name", "") or "")).stem
    except Exception:
        original_name = ""

    final_name = str(slugify(plan_name or original_name)).lower() or "default"

    brand_dir = root / "data" / "brands" / slug
    pool_plan_dir = brand_dir / "pool_plans"
    pool_plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = pool_plan_dir / f"{final_name}.yaml"

    try:
        plan_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return True, f"Saved pool plan to data/brands/{slug}/pool_plans/{final_name}.yaml", final_name
    except Exception as e:
        return False, f"Failed to save pool plan: {e}", ""


def list_brand_pool_plans(
    root: Path,
    company: str,
    slugify: Callable[[str], str],
    legacy_pool_plan_dir: Path | None = None,
) -> list[Path]:
    company_clean = _clean_text(company)
    slug = str(slugify(company_clean)).lower()

    plans: list[Path] = []
    brand_dir = root / "data" / "brands" / slug / "pool_plans"
    if brand_dir.exists():
        plans.extend(sorted(brand_dir.glob("*.yaml")))

    if legacy_pool_plan_dir is not None:
        legacy = legacy_pool_plan_dir / f"{slug}.yaml"
        if legacy.exists():
            plans.append(legacy)

    unique: list[Path] = []
    seen = set()
    for p in plans:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def load_pool_plan_from_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def pop_flash(session_state, key: str) -> str:
    return _clean_text(session_state.pop(key, ""))


def set_flash(session_state, key: str, value: str) -> None:
    session_state[key] = _clean_text(value)


def ensure_valid_choice(session_state, key: str, valid_values: list[str]) -> None:
    if key not in session_state:
        return
    if session_state.get(key) not in valid_values:
        session_state.pop(key, None)
