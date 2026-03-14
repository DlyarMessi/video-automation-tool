# UI Hardening Smoke Checks v1

This script provides lightweight smoke checks for the non-visual UI foundation modules.

## Tool

`scripts/smoke_ui_foundation.py`

## What it checks

- session default initialization
- nested canonical registry loading
- brand status summary generation
- pool plan control preparation
- pool fill runtime preparation
- starter-brand cloning
- pool plan save + reload cycle

## Why this matters

The UI hardening phase is reducing fragility by moving logic out of `ui_app.py`.

This smoke script verifies that those extracted layers still behave correctly even without relying on manual clicking inside the Streamlit app.

## Run

`python3 scripts/smoke_ui_foundation.py`

## Scope

This is not browser automation.

It is a foundation-level smoke check for the logic layers that support:

- Brand onboarding
- Pool Fill runtime preparation
- Registry hydration
- File operation helpers
