# UI Hardening · Pool Fill Runtime v1

This hardening step continues the separation of runtime preparation logic away from `ui_app.py`.

## New module

`src/ui_pool_fill_model.py`

## What it now owns

This module centralizes the non-visual runtime preparation for Pool Fill:

- topic-name extraction
- current topic lookup
- registry hydration pass
- slot-row semantic attachment
- card-view shaping
- active/completed row split
- summary preparation

## Why this matters

The Pool Fill page had already become the heaviest runtime section in the current UI.

Even without visual redesign, it was doing too much inside the page block itself:

- reading topic data
- hydrating semantics
- shaping row display
- splitting workflow states

Moving these steps into a model-preparation layer helps the Streamlit page stay closer to a rendering shell.

## Current boundary

`ui_app.py` still controls:

- widget layout
- plan/topic selection widgets
- upload buttons
- card rendering

`src/ui_pool_fill_model.py` now controls:

- which topic is active
- what row data is prepared
- how rows are grouped into active/completed states

## Why this is useful before beautification

Later visual refinement becomes safer if the page is no longer also responsible for every runtime transformation step.

This phase reduces fragility without forcing a full UI rewrite.
