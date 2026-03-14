# UI Hardening · Workspace Layer v1

This hardening step separates top-of-page workspace preparation logic from the main Streamlit page file.

## New module

`src/ui_workspace.py`

## What it now owns

This module centralizes:

- company list discovery
- default company selection
- workspace control data preparation
- storage readiness computation

## Why this matters

The top control layer of the app still mixed together:

- company discovery
- default selection behavior
- work-mode context
- storage checks
- storage dir resolution

Those are not page-rendering concerns.

Moving them into a dedicated layer makes the UI more stable before final beautification.

## Current boundary

`ui_app.py` still owns:

- Streamlit widgets
- page layout
- captions / warnings / rendering

`src/ui_workspace.py` now owns:

- workspace control preparation
- storage-state preparation

## Result

This step does not change the visual UI.

It makes the top workspace section less fragile by reducing direct runtime logic inside the page file.
