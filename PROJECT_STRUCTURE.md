# Project Structure

This project is organized around a three-step production workflow:

1. provide a script
2. generate shooting tasks and manage footage slots
3. render final videos from an indexed material pool

---

## Root

### `ui_app.py`
Operator-facing Streamlit UI.

### `README.md`
Project overview.

### `PROJECT_STRUCTURE.md`
This file.

### `SYSTEM_FIELDS.md`
Field dictionary for naming, indexing, director rules, and UI.

### `data/`
Project data assets and presets.

### `src/`
Core application logic.

---

## `data/`

### `data/render_presets.json`
Render defaults, subtitle presets, and filter presets.

### `data/fonts/`
Project-managed subtitle font assets.

Suggested structure:
- `data/fonts/latin/`
- `data/fonts/cyrillic/`
- `data/fonts/arabic/`

---

## `src/`

### `src/main.py`
CLI entry point.

### `src/workflow.py`
Creative-to-production workflow helpers and patch logic.

### `src/utils.py`
Main render pipeline and material selection logic.

### `src/render_profile.py`
Render preset access layer.

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

This folder is the long-term production asset pool.

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
- director-aware shot sequencing
- controlled output styling
- repeatable batch generation

