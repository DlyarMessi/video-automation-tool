# UI Hardening · State and Controls v1

This hardening step continues reducing behavioral fragility without changing the visual layout.

## New modules

- `src/ui_state.py`
- `src/ui_pool_fill_controls.py`

## What moved

### `src/ui_state.py`
This module centralizes UI session default initialization.

It prevents the main page file from continuing to grow scattered `session_state.setdefault(...)` lines.

### `src/ui_pool_fill_controls.py`
This module centralizes:

- pool plan label / map building
- selected plan resolution
- topic-name extraction

## Why this matters

Before this step, `ui_app.py` still owned too much of the control-layer setup for Pool Fill:

- plan label generation
- legacy-label handling
- selected plan resolution
- topic name extraction

Those are not visual concerns. Moving them into a small control-model layer makes later changes safer.

## Current boundary

`ui_app.py` still owns:

- widget rendering
- selectboxes
- layout
- button flow

The new modules now own:

- stable session defaults
- pool fill control data preparation

## Result

This does not beautify the UI.

It makes the UI code less fragile before the final refinement phase.
