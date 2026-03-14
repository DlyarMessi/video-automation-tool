# Pool Plan Validation Workflow

Use this validator before pushing pool plan changes.

## Tool

`scripts/validate_pool_plan.py`

## Example

Validate Siglen default plan:

`python3 scripts/validate_pool_plan.py "Siglen" --plan default`

Validate starter default plan:

`python3 scripts/validate_pool_plan.py "_starter" --plan default`

## What it checks

- YAML structure
- topic / slot structure
- required core fields
- allowed coverage values
- allowed priority values
- target integer validity
- registry key existence
- registry key consistency with canonical tuple
- registry key presence in canonical registry
- duplicate registry keys
- semantic/default coverage summary

## Exit behavior

- exit code `0` = validation passed
- exit code `1` = validation failed

This makes it suitable for future git hooks or CI checks.
