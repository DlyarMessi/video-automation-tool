# Pool Fill Gap Report Workflow

Use this exporter when you want a real gap report based on:

- current brand pool plan
- current factory footage already in the material pool

## Tool

`scripts/export_pool_fill_gap_report.py`

## Examples

Export the full portrait report:

`python3 scripts/export_pool_fill_gap_report.py "Siglen" --plan default --orientation portrait`

Export a single topic:

`python3 scripts/export_pool_fill_gap_report.py "Siglen" --plan default --orientation portrait --topic "Factory Strength"`

Export with a custom output path:

`python3 scripts/export_pool_fill_gap_report.py "Siglen" --plan default --orientation portrait --out docs/my_gap_report.html`

## What it does

For each slot, the report shows:

- human-friendly label
- canonical tuple
- registry key
- shoot brief
- success criteria
- fallback
- purpose
- target count
- current existing count in factory
- missing count

## Why this is useful

This tool is designed for the real fill-pool workflow.

Instead of only seeing the governed plan structure, you get a current production gap report showing what still needs to be shot and added to the pool.
