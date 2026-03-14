from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def list_companies_from_roots(
    *,
    creative_root: Path,
    input_root: Path,
) -> list[str]:
    names = set()

    if creative_root.exists():
        names.update([p.name for p in creative_root.iterdir() if p.is_dir()])

    for orientation in ("portrait", "landscape"):
        orientation_root = input_root / orientation
        if orientation_root.exists():
            names.update([p.name for p in orientation_root.iterdir() if p.is_dir()])

    return sorted([name for name in names if _clean_text(name)])


def get_default_company_index(companies: list[str], preferred_company: str = "Siglen") -> int | None:
    if not companies:
        return None
    if preferred_company in companies:
        return companies.index(preferred_company)
    return 0


def build_workspace_controls_state(
    *,
    creative_root: Path,
    input_root_path: Path,
    preferred_company: str = "Siglen",
) -> dict[str, Any]:
    companies = list_companies_from_roots(
        creative_root=creative_root,
        input_root=input_root_path,
    )
    default_idx = get_default_company_index(companies, preferred_company=preferred_company)

    return {
        "companies": companies,
        "default_idx": default_idx,
    }


def compute_storage_state(
    *,
    input_root_path: Path,
    company: str,
    orientation: str,
    ensure_company_storage_fn: Callable[[Path, str], None],
    get_storage_dirs_fn: Callable[[Path, str, str], dict[str, Path]],
) -> dict[str, Any]:
    storage_ready = True
    storage_error = ""

    try:
        if input_root_path.exists() and not input_root_path.is_dir():
            storage_ready = False
            storage_error = f"Footage root exists but is not a directory: {input_root_path}"
        else:
            ensure_company_storage_fn(input_root_path, company)
    except Exception as e:
        storage_ready = False
        storage_error = str(e)

    dirs = get_storage_dirs_fn(input_root_path, orientation, company) if storage_ready else {}
    inbox_dir = dirs.get("inbox") if dirs else None
    factory_dir = dirs.get("factory") if dirs else None

    return {
        "storage_ready": storage_ready,
        "storage_error": storage_error,
        "dirs": dirs,
        "inbox_dir": inbox_dir,
        "factory_dir": factory_dir,
    }
