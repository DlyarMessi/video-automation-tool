#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import re
import shutil
import tempfile
from typing import Any

import yaml

from src.ui_state import ensure_ui_session_defaults
from src.ui_hardening import (
    load_registry_entries,
    hydrate_slot_from_registry,
    attach_pool_row_semantics,
    build_pool_card_view,
    get_brand_validation_status,
    build_brand_status_summary,
)
from src.ui_brand_ops import (
    clone_brand_starter_into_project,
    save_brand_pool_plan,
    list_brand_pool_plans,
    load_pool_plan_from_path,
)
from src.ui_pool_fill_controls import (
    build_pool_plan_label_map,
    get_selected_pool_plan_data,
)
from src.ui_pool_fill_model import prepare_pool_fill_runtime
from src.ui_workspace import (
    list_companies_from_roots,
    get_default_company_index,
    build_workspace_controls_state,
    compute_storage_state,
)

REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"
LEGACY_POOL_PLAN_DIR = ROOT / "data" / "pool_plans"


def simple_slug(text: str) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


class UploadedPlanStub:
    def __init__(self, name: str, content: str):
        self.name = name
        self._raw = content.encode("utf-8")

    def getbuffer(self):
        return memoryview(self._raw)


def fake_build_pool_slot_rows(slots: list[dict[str, Any]], factory_files) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, slot in enumerate(slots, start=1):
        target = int(slot.get("target", 0) or 0)
        rows.append(
            {
                **slot,
                "slot_label": f"{slot.get('scene', '')} / {slot.get('content', '')} / {slot.get('coverage', '')} / {slot.get('move', '')}",
                "duration_label": "2–4s",
                "framing_label": str(slot.get("coverage", "") or ""),
                "move_label": str(slot.get("move", "") or ""),
                "existing": 0,
                "missing": target,
                "_row_index": idx,
            }
        )
    return rows


def fake_sort_pool_slot_rows(slot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(slot_rows)


def fake_summarize_pool_slot_rows(slot_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_target = sum(int(r.get("target", 0) or 0) for r in slot_rows)
    total_existing = sum(int(r.get("existing", 0) or 0) for r in slot_rows)
    total_missing = sum(int(r.get("missing", 0) or 0) for r in slot_rows)

    focus_scene = ""
    urgent_label = ""
    if slot_rows:
        focus_scene = str(slot_rows[0].get("scene", "") or "").strip() or "n/a"
        urgent_label = str(slot_rows[0].get("display_label", "") or slot_rows[0].get("slot_label", "") or "").strip() or "n/a"

    return {
        "total_target": total_target,
        "total_existing": total_existing,
        "total_missing": total_missing,
        "focus_scene": focus_scene or "n/a",
        "urgent_label": urgent_label or "n/a",
    }


def fake_ensure_company_storage(input_root_path: Path, company: str) -> None:
    for orientation in ("portrait", "landscape"):
        base = input_root_path / orientation / company
        (base / "_INBOX").mkdir(parents=True, exist_ok=True)
        (base / "factory").mkdir(parents=True, exist_ok=True)


def fake_get_storage_dirs(input_root_path: Path, orientation: str, company: str) -> dict[str, Path]:
    base = input_root_path / orientation / company
    return {
        "inbox": base / "_INBOX",
        "factory": base / "factory",
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def smoke_session_defaults() -> None:
    session_state = {}
    ensure_ui_session_defaults(session_state)
    require(session_state.get("work_mode") == "Project Mode", "work_mode default missing")
    require("creative_draft" in session_state, "creative_draft default missing")
    require(isinstance(session_state.get("shooting_rows"), list), "shooting_rows default invalid")


def smoke_registry_loading() -> dict[str, dict[str, Any]]:
    registry = load_registry_entries(REGISTRY_PATH)
    require(isinstance(registry, dict), "registry load did not return dict")
    require(len(registry) > 0, "registry entries unexpectedly empty")
    require("factory.building.wide.static" in registry, "expected registry key missing")
    return registry


def smoke_brand_status() -> None:
    status = get_brand_validation_status(ROOT, "Siglen", simple_slug)
    require(status["slug"] == "siglen", "brand status slug mismatch")
    require(isinstance(status["plan_count"], int), "brand status plan_count invalid")
    summary = build_brand_status_summary(status)
    require("Status" in summary, "brand status summary not built")


def smoke_workspace_layer() -> None:
    companies = list_companies_from_roots(
        creative_root=ROOT / "creative_scripts",
        input_root=ROOT / "input_videos",
    )
    require(isinstance(companies, list), "workspace companies not a list")
    require(len(companies) > 0, "workspace companies unexpectedly empty")

    idx = get_default_company_index(companies, preferred_company="Siglen")
    require(idx is None or isinstance(idx, int), "default company index invalid")

    state = build_workspace_controls_state(
        creative_root=ROOT / "creative_scripts",
        input_root_path=ROOT / "input_videos",
        preferred_company="Siglen",
    )
    require("companies" in state and "default_idx" in state, "workspace state keys missing")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        storage = compute_storage_state(
            input_root_path=tmp_root / "input_videos",
            company="Siglen",
            orientation="portrait",
            ensure_company_storage_fn=fake_ensure_company_storage,
            get_storage_dirs_fn=fake_get_storage_dirs,
        )
        require(storage["storage_ready"] is True, "storage state should be ready")
        require(storage["inbox_dir"] is not None, "storage inbox_dir missing")
        require(storage["factory_dir"] is not None, "storage factory_dir missing")


def smoke_plan_controls() -> tuple[dict[str, Any], str]:
    plans = list_brand_pool_plans(ROOT, "Siglen", simple_slug, LEGACY_POOL_PLAN_DIR)
    require(len(plans) > 0, "siglen plans not found")

    labels, mapping = build_pool_plan_label_map(plans, LEGACY_POOL_PLAN_DIR)
    require(len(labels) > 0, "pool plan labels empty")

    selected = labels[0]
    selected_data = get_selected_pool_plan_data(
        selected_plan_label=selected,
        pool_plan_map=mapping,
        load_pool_plan_from_path_fn=load_pool_plan_from_path,
    )
    require(selected_data["selected_plan_path"].exists(), "selected plan path missing")
    require(isinstance(selected_data["pool_plan"], dict), "selected pool plan is not dict")
    require(len(selected_data["topic_names"]) > 0, "topic names empty")

    return selected_data["pool_plan"], selected_data["topic_names"][0]


def smoke_pool_fill_runtime(pool_plan: dict[str, Any], topic_name: str, registry: dict[str, dict[str, Any]]) -> None:
    runtime = prepare_pool_fill_runtime(
        pool_plan=pool_plan,
        pool_topic=topic_name,
        factory_files=[],
        registry_path=REGISTRY_PATH,
        load_registry_entries_fn=lambda _path: registry,
        hydrate_slot_fn=hydrate_slot_from_registry,
        attach_semantics_fn=attach_pool_row_semantics,
        build_card_view_fn=build_pool_card_view,
        build_pool_slot_rows_fn=fake_build_pool_slot_rows,
        sort_pool_slot_rows_fn=fake_sort_pool_slot_rows,
        summarize_pool_slot_rows_fn=fake_summarize_pool_slot_rows,
    )

    require(runtime["selected_topic"] is not None, "selected topic not resolved")
    require(len(runtime["slot_rows"]) > 0, "slot rows empty")
    require(len(runtime["active_rows"]) == len(runtime["slot_rows"]), "active rows split mismatch")
    first_row = runtime["slot_rows"][0]
    require(str(first_row.get("display_label", "")).strip() != "", "display_label missing from pool card view")
    require("summary" in runtime and isinstance(runtime["summary"], dict), "runtime summary missing")


def smoke_starter_clone_and_plan_save() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        (tmp_root / "data" / "brands").mkdir(parents=True, exist_ok=True)

        src_starter = ROOT / "data" / "brands" / "_starter"
        require(src_starter.exists(), "_starter brand template missing in project")
        shutil.copytree(src_starter, tmp_root / "data" / "brands" / "_starter")

        ok, msg = clone_brand_starter_into_project(tmp_root, "Acme Elevators", simple_slug)
        require(ok, f"starter clone failed: {msg}")

        brand_dir = tmp_root / "data" / "brands" / "acme-elevators"
        require(brand_dir.exists(), "cloned brand dir missing")
        require((brand_dir / "pool_plans" / "default.yaml").exists(), "cloned default plan missing")

        uploaded = UploadedPlanStub(
            "campaign_a.yaml",
            yaml.safe_dump(
                {
                    "brand": "Acme Elevators",
                    "topics": [
                        {
                            "name": "Test Topic",
                            "slots": [
                                {
                                    "scene": "factory",
                                    "content": "building",
                                    "coverage": "wide",
                                    "move": "static",
                                    "registry_key": "factory.building.wide.static",
                                    "target": 2,
                                    "priority": "high",
                                }
                            ],
                        }
                    ],
                },
                sort_keys=False,
                allow_unicode=True,
            ),
        )

        ok, msg, saved_label = save_brand_pool_plan(
            tmp_root,
            "Acme Elevators",
            simple_slug,
            uploaded,
            "campaign-a",
        )
        require(ok, f"save_brand_pool_plan failed: {msg}")
        require(saved_label == "campaign-a", "saved plan label mismatch")

        plans = list_brand_pool_plans(tmp_root, "Acme Elevators", simple_slug, None)
        require(any(p.stem == "campaign-a" for p in plans), "saved plan not listed")

        loaded = load_pool_plan_from_path(brand_dir / "pool_plans" / "campaign-a.yaml")
        require(isinstance(loaded, dict), "loaded saved plan is not dict")
        require(str(loaded.get("brand", "")) == "Acme Elevators", "saved plan brand mismatch")


def main() -> None:
    print("=== UI Hardening Smoke Checks ===")

    smoke_session_defaults()
    print("PASS  session defaults")

    registry = smoke_registry_loading()
    print("PASS  nested registry loading")

    smoke_brand_status()
    print("PASS  brand status summary")

    smoke_workspace_layer()
    print("PASS  workspace layer")

    pool_plan, topic_name = smoke_plan_controls()
    print("PASS  pool plan controls")

    smoke_pool_fill_runtime(pool_plan, topic_name, registry)
    print("PASS  pool fill runtime preparation")

    smoke_starter_clone_and_plan_save()
    print("PASS  starter clone + plan save")

    print("ALL PASS")


if __name__ == "__main__":
    main()
