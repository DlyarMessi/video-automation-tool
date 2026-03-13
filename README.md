# Script-First Video Automation Tool

A three-step workflow for industrial promo-video production.

1. Provide a structured script  
2. Generate shooting tasks and fill footage slots  
3. Render the final video

This project is designed to turn repeatable video production into a cleaner, more stable workflow for internal teams.

## Core idea

The system is built around a script-first approach.

A structured script is the primary input.  
From that single input, the system can:

- generate shooting tasks
- organize footage requirements
- prepare timeline logic
- apply editorial rules
- render a final video

## Current workflow

### Step 1 — Script → Tasks
The operator provides a creative script in YAML format.

The system parses the script and generates:

- task rows
- scene / category / shot breakdown
- missing footage requirements
- optional printable task output

### Step 2 — Footage Board
The operator reviews required footage and fills missing slots.

This step supports:

- checking existing factory footage
- identifying missing assets
- uploading new clips
- moving clips from inbox to factory pool
- applying naming rules consistently

### Step 3 — Create Video
The system prepares an internal production timeline, applies render settings, and generates the final video.

## Project structure

- `ui_app.py` — operator-facing UI
- `src/workflow.py` — main workflow logic for the three-step system
- `src/main.py` — CLI entry point
- `src/director_engine/` — editorial rule layer
- `src/tts_provider.py` — ElevenLabs TTS provider
- `src/voiceover_a2.py` — voiceover event handling
- `src/subtitle_builder.py` — subtitle building
- `creative_scripts/` — script inputs and examples
- `data/tts_profiles/` — local TTS configuration

See `PROJECT_STRUCTURE.md` for a more detailed breakdown.

## Design principles

- script-first
- stable over flashy
- reusable over one-off
- workflow clarity over experimental complexity
- lightweight output per run

## Notes

- ElevenLabs is the only supported TTS provider.
- The footage drive may live on external storage.
- The UI is designed to degrade safely if footage storage is unavailable.
- The output structure is intentionally lightweight per run.

## Next direction

The next development focus is not repository cleanup, but workflow refinement:

- stronger script schema
- cleaner footage-slot logic
- better metadata for the Director Engine
- bilingual documentation
- future Chinese UI support
