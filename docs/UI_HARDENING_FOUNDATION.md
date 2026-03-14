# UI Hardening Foundation v1

This phase is not about beautification.

It is about making the current UI logic less fragile before final visual refinement.

## Current strategy

Instead of continuing to grow all behavior directly inside `ui_app.py`, the first hardening step introduces:

- `src/ui_hardening.py`

This module centralizes:

- registry entry extraction
- registry-based slot hydration
- pool-row semantic attachment
- pool-card view shaping
- brand status summary helpers

## Why this matters

The UI had started to accumulate:

- runtime hydration logic
- crew-facing display logic
- brand readiness logic

inside the main Streamlit file.

That made iterative changes possible, but also made layout changes more likely to break unrelated behavior.

## Hardening boundary

The first goal is:

- keep current behavior
- reduce duplicated logic
- create a safer bridge between governed data and rendered UI

## What is now separated

### Registry / taxonomy side
- nested or flat registry entry extraction
- slot hydration from registry

### Pool Fill rendering side
- crew-facing display label
- canonical tuple text
- normalized shoot brief / purpose / lists

### Brand readiness side
- brand status loading
- summary-line generation

## What this phase intentionally does not do

- redesign the visual layout
- restyle cards
- restructure the full Streamlit page hierarchy
- change the final user-facing appearance

Those belong to later UI beautification and refinement stages.

## Next likely hardening steps

- standardize session-state keys into clearer namespaces
- move more Pool Fill helpers out of `ui_app.py`
- reduce direct business logic inside render functions
- add lightweight smoke checks for critical UI flows
