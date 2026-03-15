# AGENTS.md

Repository-level guidance for contributors and agents.

## Scope
This file applies to the entire repository tree.

## Architecture constraints
- Treat AI script generation as a front-end compiler into governed production logic.
- Do not bypass canonical/semantic/pool-plan constraints when adding AI entry points.
- Keep manual/no-API paths possible.
- Prefer additive changes and avoid unrelated refactors.

## Task hygiene
- Keep changes narrow and deterministic.
- Add tests for new contract/validation/compiler/pipeline behavior.
- Avoid UI changes unless explicitly requested.
