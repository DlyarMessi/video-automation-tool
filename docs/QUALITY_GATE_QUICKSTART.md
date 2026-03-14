# Quality Gate Quickstart

Use this wrapper when you want one command to run the current brand-quality checks.

## Wrapper

`scripts/quality_gate_brand.sh`

## Basic usage

Run the full quality gate for a brand's default pool plan:

`bash scripts/quality_gate_brand.sh Siglen`

Run it for the starter template and also write reports:

`bash scripts/quality_gate_brand.sh _starter --write-report`

Run a specific plan:

`bash scripts/quality_gate_brand.sh Siglen --plan default`

## What it runs

The wrapper executes these tools in order:

1. `scripts/validate_canonical_registry.py`
2. `scripts/validate_pool_plan.py`
3. `scripts/audit_brand_setup.py`
4. `scripts/sync_pool_plan_from_registry.py`
5. `scripts/preflight_brand.py`

## Why this exists

This wrapper is meant to reduce friction when working on:

- taxonomy changes
- starter template changes
- brand onboarding
- pool plan edits
- registry / plan consistency work

Instead of remembering many commands, you can run one entry point first and inspect failures from there.
