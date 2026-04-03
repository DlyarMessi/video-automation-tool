# Project: video-automation-tool

## Current Branch
fix/render-inventory-preflight (tip: e6bec6e)

## Architecture Quick Ref
- Pool Fill UI: ui_app.py → render_pool_active_slot_card() / render_pool_completed_slot_card()
- Filename generation: src/workflow.py → build_factory_filename(), next_index_for(), _legacy_subject_action_from_content()
- Canonical allocator: uses 5D tuple (subject, action, framing, motion, variant)
- Script pipeline: src/script_pipeline.py
- Render pipeline: src/utils.py → process_company()

## Current P0 Bug
Pool Fill save writes wrong canonical action in filename.
- Card shows action=display, but file saved as action=transport
- Root cause: save path calls _legacy_subject_action_from_content() instead of using the card's explicit canonical subject/action
- Fix: make build_factory_filename() and next_index_for() accept explicit subject/action params; pass them from UI card context

## Testing
- Run focused tests: pytest tests/test_render_inventory_preflight.py
- Run smoke tests: pytest tests/test_script_pipeline_smoke.py
- Do NOT commit anything in docs/pool_gap_reports/

## Rules
- Keep patches minimal and narrow
- Do not touch: prompts, HTML tools, UI styling, docs/
- Do not mix Windows compat fixes into this branch

## Known Debt
1. `save_pool_uploads` (~ln 528 in workflow.py) still uses legacy subject/action derivation — no card row context available. Audit callers.
2. `summarize_factory_coverage` — `safe_slug("")` returns `"untitled"` (truthy), causing it to take the wrong branch. Separate fix needed.
3. `test_workflow_compile_pool_tags` — pre-existing failure, `allowed` set doesn't match current `compile_creative_dict` output. Needs fixture update.
4. Reclass path (~ln 2817 in ui_app.py) round-trips canonical subject/action back through legacy content string — wasteful but currently correct.