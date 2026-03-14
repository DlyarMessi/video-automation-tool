# UI Hardening Operations Layer v1

This phase continues the UI hardening work without changing the visual design.

## New module

`src/ui_brand_ops.py`

## What moved conceptually

This layer groups together the current brand-facing file operations and lightweight UI state helpers:

- starter-brand cloning
- logo saving
- pool-plan saving
- pool-plan listing
- pool-plan loading
- flash-message helpers
- safe selection cleanup helpers

## Why this matters

Before this step, these behaviors lived directly inside `ui_app.py`.

That made the page file responsible for both:

- page rendering
- file-system brand operations
- brand onboarding state cleanup

Separating these concerns helps the UI become stronger before any final beautification pass.

## Current boundary

`ui_app.py` still owns:

- Streamlit rendering
- page layout
- button flow
- widget placement

`src/ui_brand_ops.py` now owns:

- brand file operations
- light state helper primitives
- pool-plan file access helpers

## Why this is safer

This hardening step avoids a full UI rewrite.

It introduces a cleaner boundary with minimal runtime risk, while reducing the chance that future layout edits accidentally break file-operation behavior.

## Next likely hardening steps

- standardize more session-state namespaces
- move more Pool Fill preparation logic out of `ui_app.py`
- reduce direct business logic inside page-mode blocks
- define a thin view-model layer for more UI sections
