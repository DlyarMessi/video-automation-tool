# Script-First Video Automation Tool

A production-oriented three-step workflow for short-form brand video generation:

1. provide a structured script
2. generate shooting tasks and fill the indexed material pool
3. render final videos from reusable assets

---

## What the system does

This project is designed to evolve from a one-off editing helper into a reusable content production system.

Current foundation includes:

- script-first workflow
- indexed reusable footage pool
- multi-language subtitle styling
- managed font assets
- ElevenLabs-based voice pipeline
- 60fps output defaults
- visual filter presets
- anti-repeat material scheduling
- director-rule-based sequencing

---

## Core files

- `ui_app.py` — operator-facing UI
- `src/main.py` — CLI entry point
- `src/workflow.py` — workflow helpers
- `src/utils.py` — render pipeline and material scheduling
- `src/material_index.py` — material index logic
- `src/render_profile.py` — preset access layer
- `src/director_engine/` — editorial rule system

---

## Material philosophy

The long-term goal is not to manually edit every new video.

The long-term goal is to:

- build a standardized footage pool
- index it with reusable metadata
- let new scripts repeatedly call the pool
- keep outputs varied through scheduling and director rules

That is why the system now separates:

- file naming
- material indexing
- director logic
- render presets

---

## Current workflow

### Step 1 — Script → Tasks
Generate task rows from a creative script.

### Step 2 — Footage Board
Fill required footage slots and manage the factory pool.

### Step 3 — Create Video
Compile, apply render settings, and render the final video.

---

## Key system layers

### Naming layer
Core filename pattern:

`scene_content_coverage_move_index.ext`

### Index layer
Each factory pool uses `asset_index.json` to store:
- durations
- usable windows
- continuity groups
- energy
- quality review
- intro / outro / hero suitability

### Director layer
The director engine currently applies:
- structure rules
- motion continuity rules
- repetition control
- transition logic
- pacing logic
- ending logic

### Render layer
The render system currently supports:
- subtitle style presets
- font asset routing
- filter presets
- 60fps defaults

---

## Important documents

- `PROJECT_STRUCTURE.md` — folder and module layout
- `SYSTEM_FIELDS.md` — naming, index, rule, and UI field dictionary

---

## Current TTS policy

ElevenLabs is the only active TTS provider in the current system.

---

## Current output policy

The system favors:
- cleaner run folders
- reusable material pools
- lightweight internal artifacts
- controlled repeatability over uncontrolled randomness

