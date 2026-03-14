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
Used when you already have a creative script and want to:

- generate task rows
- review footage readiness
- render final output

### Pool Fill Mode
Used when you want to build the reusable material pool directly.

Current capabilities include:

- select company
- select pool plan
- select topic
- inspect missing slots
- upload clips directly into matching slots
- auto-name clips into the factory pool
- auto-update `asset_index.json`
- download a phone-friendly HTML shooting guide

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
- `SYSTEM_FIELDS.md` — naming, index, pool-plan, rule, and UI field dictionary
- `TERMINOLOGY.md` — core project vocabulary

---

## Current output policy

The system favors:

- cleaner run folders
- reusable material pools
- lightweight internal artifacts
- controlled repeatability over uncontrolled randomness
