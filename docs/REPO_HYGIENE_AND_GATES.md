# Repo Hygiene and Master Gates

This document explains the current repository hygiene rules and the main quality-gate entry points.

## Why this exists

During iterative UI and workflow development, the project naturally produces:

- patch helper scripts
- backup files
- generated reports
- temporary exports

Those files are useful during active work, but they should not clutter normal git status output.

## `.gitignore` additions

The repository now ignores:

- generated brand audit reports
- generated pool plan export packs
- backup files with `.bak_*`
- patch/fix helper scripts named like `apply_*.sh` or `fix_*.sh`
- Python cache folders

## Main gate entry points

### UI hardening gate
`bash scripts/quality_gate_ui.sh`

Runs:
- compile checks
- UI foundation smoke checks
- Siglen brand quality gate wrapper

### Brand gate
`bash scripts/quality_gate_brand.sh Siglen`
`bash scripts/quality_gate_brand.sh _starter`

Runs:
- registry validation
- pool plan validation
- brand audit
- registry sync dry-run
- consolidated preflight

### Master project gate
`bash scripts/quality_gate_all.sh`

Runs:
1. UI hardening quality gate
2. canonical registry validation
3. Siglen brand quality gate
4. starter brand quality gate

## Recommended usage

Before pushing a larger batch of changes:

1. run `bash scripts/quality_gate_all.sh`
2. inspect `git status`
3. commit only the intended tracked files

This keeps the repository cleaner and makes the hardening phase easier to close safely.
