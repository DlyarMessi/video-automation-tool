# Registry Sync Workflow

This tool helps keep brand pool plans aligned with the canonical registry without forcing a full runtime refactor.

## Tool

`scripts/sync_pool_plan_from_registry.py`

## Default behavior

The default mode is:

- `fill-missing`

That means:

- missing semantic fields in the plan can be filled from the registry
- missing default soft-tag fields can be filled from the registry
- existing plan values are left in place

## Safer first pass

Run a dry audit first:

`python3 scripts/sync_pool_plan_from_registry.py "Siglen" --plan default`

Then write only if the summary looks correct:

`python3 scripts/sync_pool_plan_from_registry.py "Siglen" --plan default --write`

## Overwrite mode

If you intentionally want the registry to replace plan-side values:

`python3 scripts/sync_pool_plan_from_registry.py "Siglen" --plan default --mode overwrite --write`

Use this carefully.

## Intended use

This tool is useful when:

- starter plans are cloned from templates
- registry entries evolve
- plan semantic fields drift over time
- a brand plan needs to be rehydrated from governed taxonomy content

## Current boundary

This tool does **not** change:

- topic grouping
- target counts
- priorities
- upload/runtime state

It only syncs candidate registry-owned descriptive fields.
