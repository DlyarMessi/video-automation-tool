# Pool Plan Export Workflow

Use this exporter when you want to turn a real brand pool plan into a crew-readable HTML pack.

## Tool

`scripts/export_pool_plan_pack.py`

## Examples

Export the full default plan:

`python3 scripts/export_pool_plan_pack.py "Siglen" --plan default`

Export a single topic:

`python3 scripts/export_pool_plan_pack.py "Siglen" --plan default --topic "Factory Strength"`

Export with a custom output path:

`python3 scripts/export_pool_plan_pack.py "Siglen" --plan default --out docs/my_siglen_pack.html`

## What it does

The exporter reads:

- the brand pool plan
- the canonical registry

Then it builds an HTML pack that displays:

- human-friendly slot label
- canonical tuple
- registry key
- shoot brief
- success criteria
- fallback
- purpose
- target
- priority

If a plan slot is missing semantic fields, the exporter attempts to hydrate them from the registry via `registry_key`.

## Intended use

This is useful when you want to:

- send a topic-specific shooting pack to photographers
- export a cleaner field-facing brief from the real plan
- avoid manually rewriting slot semantics into a separate document
