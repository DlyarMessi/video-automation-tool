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


def resolve_storage_root(requested_path: Path, default_path: Path) -> dict[str, Any]:
    requested = Path(requested_path).expanduser()
    default = Path(default_path).expanduser()

    requested_ok = requested.exists() and requested.is_dir()
    default_ok = default.exists() and default.is_dir()

    if requested_ok:
        return {
            "requested_root": requested,
            "effective_root": requested,
            "fallback_active": False,
            "reason": "",
        }

    if not default.exists():
        default.mkdir(parents=True, exist_ok=True)

    if default.is_dir():
        return {
            "requested_root": requested,
            "effective_root": default,
            "fallback_active": requested != default,
            "reason": "" if requested == default else f"Requested root unavailable: {requested}",
        }

    return {
        "requested_root": requested,
        "effective_root": default,
        "fallback_active": True,
        "reason": f"Both requested and default roots are unusable. requested={requested} default={default}",
    }


def compute_storage_state(
    *,
    requested_input_root: Path,
    requested_output_root: Path,
    default_input_root: Path,
    default_output_root: Path,
    company: str,
    orientation: str,
    ensure_company_storage_fn: Callable[[Path, str], None],
    get_storage_dirs_fn: Callable[[Path, str, str], dict[str, Path]],
) -> dict[str, Any]:
    input_state = resolve_storage_root(requested_input_root, default_input_root)
    output_state = resolve_storage_root(requested_output_root, default_output_root)

    storage_ready = True
    storage_error = ""

    input_root = input_state["effective_root"]
    output_root = output_state["effective_root"]

    try:
        ensure_company_storage_fn(input_root, company)
        output_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        storage_ready = False
        storage_error = str(e)

    dirs = get_storage_dirs_fn(input_root, orientation, company) if storage_ready else {}
    inbox_dir = dirs.get("inbox") if dirs else None
    factory_dir = dirs.get("factory") if dirs else None

    return {
        "storage_ready": storage_ready,
        "storage_error": storage_error,
        "input_root_requested": input_state["requested_root"],
        "input_root_effective": input_root,
        "input_fallback_active": bool(input_state["fallback_active"]),
        "output_root_requested": output_state["requested_root"],
        "output_root_effective": output_root,
        "output_fallback_active": bool(output_state["fallback_active"]),
        "dirs": dirs,
        "inbox_dir": inbox_dir,
        "factory_dir": factory_dir,
        "reason": " | ".join([x for x in [input_state["reason"], output_state["reason"]] if x]),
    }
