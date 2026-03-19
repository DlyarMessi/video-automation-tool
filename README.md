# Script-First Video Automation Tool

A production-oriented workflow for short-form brand video generation:

1. provide a structured script
2. generate shooting tasks and fill the indexed material pool
3. render final videos from reusable assets

---

## What the system does

This project is evolving from a one-off editing helper into a reusable content production system.

Current foundation includes:
- governed canonical-tag direction

- script-first workflow
- indexed reusable footage pool
- Pool Fill Mode as an independent intake page
- brand-scoped pool plan selection
- managed subtitle font buckets
- ElevenLabs-based voice pipeline
- 60fps output defaults
- visual filter presets
- anti-repeat material scheduling
- director-rule-based sequencing

---

## Current operator workflow

### Project Mode
AI-first planning workflow with two paths:

- **Create with AI (Primary):** quick brief, heuristic prefill, governed compile/generate
- **Use Existing Script (Manual):** fast direct YAML path for existing workflows

Project mode is used to:

- generate task rows
- review footage readiness
- render final output

### Pool Fill Mode
Downstream coverage/gap-closure stage after planning.

Current capabilities include:

- select company
- select pool plan
- select topic
- inspect missing slots
- upload clips directly into matching slots
- auto-name clips into the factory pool
- auto-update `asset_index.json`
- download a phone-friendly HTML shooting guide

See `docs/STORAGE_MODEL_AND_WORKSPACES.md` for workspace provisioning and storage guidance.

---

## Core files

- `ui_app.py` — operator-facing UI
- `run.sh` — lightweight helper entry for current project-stage workflows
- `src/main.py` — CLI entry point
- `src/workflow.py` — workflow helpers
- `src/utils.py` — render pipeline and material scheduling
- `src/material_index.py` — material index logic
- `src/render_profile.py` — subtitle and render preset access
- `src/director_engine/` — editorial rule system

---

## Material philosophy

The long-term goal is not to manually edit every new video.

The system is moving toward:

- a standardized footage pool
- reusable clip metadata
- script-driven pool reuse
- controlled visual variation through scheduling and director rules

That is why the project now separates:

- file naming
- material indexing
- pool-plan-driven intake
- director logic
- render presets
- brand assets

---

## Current layout highlights

### Brand assets
Brand-scoped assets now live under:

`data/brands/<company>/`

Example:

- `data/brands/siglen/logo.png`
- `data/brands/siglen/pool_plans/default.yaml`

### Fonts
Managed subtitle buckets currently include:

- `latin`
- `cyrillic`
- `arabic`

Language-family mappings currently include:

- `en`, `fr`, `es` → `latin`
- `ru`, `kk`, `tg` → `cyrillic`
- `ar`, `ug` → `arabic`
- `uz` → `latin` by default, with script fallback support

### Guide output
Current downloadable field guide:

- `docs/pool_fill_shooting_guide.html`

---

## Current TTS note

ElevenLabs is the only active TTS provider in the current system.

The UI now includes language entries for:

- Uyghur
- Kazakh
- Uzbek
- Tajik

Voice IDs can be mapped per language short code in:

`data/tts_profiles/elevenlabs.json`

---

## Important documents

- `PROJECT_STRUCTURE.md` — folder and module layout
- `CANONICAL_TAG_POLICY.md` — governance rules for canonical tags and public/internal boundaries
- `BRAND_CREATION_SPEC.md` — rules for onboarding new brands into the system
- `SYSTEM_FIELDS.md` — naming, index, pool-plan, rule, and UI field dictionary
- `TERMINOLOGY.md` — core project vocabulary

---

## Current output policy

The system favors:

- cleaner run folders
- reusable material pools
- lightweight internal artifacts
- controlled repeatability over uncontrolled randomness

## Brand starter template

- starter brand template under `data/brands/_starter/`


## Brand onboarding helper

The project now includes a starter clone helper:

`python3 scripts/clone_brand_starter.py "My Brand"`

This creates a new brand-local skeleton from `data/brands/_starter/`.

---

## Current reliability notes

Recent stabilization now includes:

- Project Mode coverage and render contract aligned through project-slot planning
- final render success now requires an actual output video file
- generated project artifacts can be restored after refresh / reload
- operator-facing UI now supports a Chinese-friendly display layer without changing internal schema
- Project Mode and Pool Fill Mode are both intended to remain operator-first surfaces over stable internal models

