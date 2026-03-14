from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def build_pool_plan_label_map(
    available_pool_plans: list[Path],
    legacy_pool_plan_dir: Path | None = None,
) -> tuple[list[str], dict[str, Path]]:
    labels: list[str] = []
    mapping: dict[str, Path] = {}

    for p in available_pool_plans:
        label = p.stem
        if legacy_pool_plan_dir is not None and p.parent == legacy_pool_plan_dir:
            label = f"{label} (legacy)"
        labels.append(label)
        mapping[label] = p

    return labels, mapping


def get_topic_names_from_pool_plan(pool_plan: dict[str, Any]) -> list[str]:
    topics = pool_plan.get("topics", []) if isinstance(pool_plan.get("topics"), list) else []
    return [
        str(t.get("name", "")).strip()
        for t in topics
        if isinstance(t, dict) and str(t.get("name", "")).strip()
    ]


def get_selected_pool_plan_data(
    *,
    selected_plan_label: str,
    pool_plan_map: dict[str, Path],
    load_pool_plan_from_path_fn: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    selected_label = _clean_text(selected_plan_label)
    selected_plan_path = pool_plan_map[selected_label]
    pool_plan = load_pool_plan_from_path_fn(selected_plan_path)
    topics = pool_plan.get("topics", []) if isinstance(pool_plan.get("topics"), list) else []
    topic_names = get_topic_names_from_pool_plan(pool_plan)

    return {
        "selected_plan_path": selected_plan_path,
        "pool_plan": pool_plan,
        "topics": topics,
        "topic_names": topic_names,
    }
