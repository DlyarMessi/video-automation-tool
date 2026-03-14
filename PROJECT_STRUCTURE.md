# Project Structure

This project is organized around a three-step production workflow:

1. provide a script
2. generate shooting tasks and manage footage slots
3. render final videos from an indexed material pool

---

## Root

### `ui_app.py`
Operator-facing Streamlit UI.

### `run.sh`
Current-stage helper script for launching UI, checking status, running CLI jobs, and cleaning junk files.

### `README.md`
Project overview.

### `PROJECT_STRUCTURE.md`
This file.

### `SYSTEM_FIELDS.md`
Field dictionary for naming, indexing, pool plans, director rules, and UI.

### `TERMINOLOGY.md`
Core vocabulary for the project.

### `docs/`
Human-facing reference documents.

### `CANONICAL_TAG_POLICY.md`
Policy document defining canonical-tag governance and future public/internal schema boundaries.

### `data/`
Project data assets and presets.

### `src/`
Core application logic.

---

## `docs/`

### `docs/pool_fill_shooting_guide.html`
Phone-friendly downloadable field guide for Pool Fill operators and photographers.

### `docs/POOL_FILL_ROW_SCHEMA.md`
Documentation contract for the current Pool Fill row structure used between plan loading, semantic merge, registry hydration, and UI rendering.

---

## `data/`

### `data/brands/`
Brand-scoped assets and pool plans.

Recommended structure:

`data/brands/<company>/logo.png`
`data/brands/<company>/bgm/`
`data/brands/<company>/pool_plans/<plan>.yaml`

Current example:

`data/brands/siglen/pool_plans/default.yaml`

### `data/taxonomy/`
Early taxonomy and governance placeholder files.

Current files:
- `data/taxonomy/canonical_registry_v1.yaml`
- `data/taxonomy/combo_rules_v1.yaml`
- `data/taxonomy/intent_mappings_v1.yaml`

### `data/render_presets.json`
Render defaults, subtitle family mapping, subtitle presets, and filter presets.

### `data/fonts/`
Managed subtitle font assets.

Current buckets:
- `data/fonts/latin/`
- `data/fonts/cyrillic/`
- `data/fonts/arabic/`

### `data/tts_profiles/`
Local ElevenLabs config and language-to-voice mappings.

---

## `src/`

### `src/main.py`
CLI entry point.

### `src/workflow.py`
Creative-to-production workflow helpers and patch logic.

### `src/utils.py`
Main render pipeline and material selection logic.

### `src/render_profile.py`
Render preset and language-family access layer.

### `src/material_index.py`
Material pool indexing helpers.

### `src/subtitle_builder.py`
Subtitle segment generation.

### `src/voiceover_a2.py`
Voiceover event building.

### `src/tts_provider.py`
TTS provider interface.

### `src/script_loader.py`
Script loading utility.

### `src/language_checks.py`
Script-family checking and language-family validation helpers.

---

## `src/director_engine/`

Director rules layer.

### `engine.py`
Rule runner.

### `profiles/content_factory.yaml`
Current main director profile.

### `rules/common.py`
Shared parsing helpers for rule modules.

### `rules/structure.py`
Sequence structure logic.

### `rules/motion_continuity.py`
Continuity scoring and local reordering.

### `rules/pacing.py`
Duration shaping.

### `rules/repetition.py`
Repetition control.

### `rules/transitions.py`
Transition decisions.

### `rules/ending.py`
Ending selection and hold logic.

---

## Material Pool Layout

Input footage is expected under orientation and company folders.

Recommended structure:

`input_videos/<orientation>/<company>/_INBOX/`
`input_videos/<orientation>/<company>/factory/`

### `_INBOX`
Raw intake area.

### `factory`
Named and indexed reusable material pool.

### `factory/asset_index.json`
Structured material metadata used by scheduling and director logic.

---

## Output Layout

Recommended output structure:

`output_videos/<orientation>/<company>/<run_id>/`

Internal run artifacts are stored under:

`output_videos/<orientation>/<company>/<run_id>/_internal/`

A global usage memory file may exist at:

`output_videos/_usage_history.json`

This supports anti-repeat scheduling.

---

## Design Intent

This project is no longer just a script-based renderer.

It is moving toward:

- a reusable indexed material pool
- brand-scoped asset and plan organization
- pool-plan-driven intake
- director-aware shot sequencing
- controlled output styling
- repeatable batch generation
