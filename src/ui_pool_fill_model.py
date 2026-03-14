from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def get_topic_names(topics: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        name = _clean_text(topic.get("name", ""))
        if name:
            out.append(name)
    return out


def find_selected_topic(topics: list[dict[str, Any]], pool_topic: str) -> dict[str, Any] | None:
    pool_topic_clean = _clean_text(pool_topic)
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        if _clean_text(topic.get("name", "")) == pool_topic_clean:
            return topic
    return None


def split_pool_rows(slot_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active_rows = [r for r in slot_rows if int(r.get("missing", 0) or 0) > 0]
    completed_rows = [r for r in slot_rows if int(r.get("missing", 0) or 0) == 0]
    return active_rows, completed_rows


def prepare_pool_fill_runtime(
    *,
    pool_plan: dict[str, Any],
    pool_topic: str,
    factory_files: list[Path],
    registry_path: Path,
    load_registry_entries_fn: Callable[[Path], dict[str, dict[str, Any]]],
    hydrate_slot_fn: Callable[[dict[str, Any], dict[str, dict[str, Any]]], dict[str, Any]],
    attach_semantics_fn: Callable[[list[dict[str, Any]], list[dict[str, Any]]], list[dict[str, Any]]],
    build_card_view_fn: Callable[[dict[str, Any]], dict[str, Any]],
    build_pool_slot_rows_fn: Callable[[list[dict[str, Any]], list[Path]], list[dict[str, Any]]],
    sort_pool_slot_rows_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    summarize_pool_slot_rows_fn: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    topics = pool_plan.get("topics", []) if isinstance(pool_plan.get("topics"), list) else []
    topic_names = get_topic_names(topics)
    selected_topic = find_selected_topic(topics, pool_topic)

    slots = (
        selected_topic.get("slots", [])
        if isinstance(selected_topic, dict) and isinstance(selected_topic.get("slots"), list)
        else []
    )

    registry_map = load_registry_entries_fn(registry_path)
    hydrated_slots = [hydrate_slot_fn(slot, registry_map) for slot in slots]

    slot_rows = build_pool_slot_rows_fn(hydrated_slots, factory_files)
    slot_rows = attach_semantics_fn(slot_rows, hydrated_slots)
    slot_rows = [build_card_view_fn(r) for r in slot_rows]
    slot_rows = sort_pool_slot_rows_fn(slot_rows)

    summary = summarize_pool_slot_rows_fn(slot_rows)
    active_rows, completed_rows = split_pool_rows(slot_rows)

    return {
        "topics": topics,
        "topic_names": topic_names,
        "selected_topic": selected_topic,
        "slots": slots,
        "hydrated_slots": hydrated_slots,
        "slot_rows": slot_rows,
        "summary": summary,
        "active_rows": active_rows,
        "completed_rows": completed_rows,
    }
