# Project Structure

This document explains the current structure after the workflow consolidation.

## Primary layers

### `ui_app.py`
The operator-facing application.

Responsibilities:
- collect input from the user
- display the three workflow steps
- show task rows and footage status
- trigger render actions

Non-responsibilities:
- does not define editorial rules
- does not own TTS implementation
- does not own deep workflow logic

### `src/workflow.py`
The core workflow layer.

Responsibilities:
- validate structured scripts
- generate shooting task rows
- infer task metadata used by the UI
- manage footage naming helpers
- summarize footage coverage
- prepare internal production YAML
- patch final render settings

This file is intentionally the main “product logic” layer.

### `src/director_engine/`
The editorial rule layer.

Responsibilities:
- apply pacing rules
- apply repetition control
- apply transitions
- apply ending behavior

This layer modifies timeline behavior, but does not create the product workflow itself.

### `src/main.py`
The CLI entry point.

Responsibilities:
- expose compile / guide / run commands
- connect workflow logic to rendering logic

### TTS / subtitle / voiceover files
- `src/tts_provider.py`
- `src/voiceover_a2.py`
- `src/subtitle_builder.py`

These files are engine-level support modules.

## Input directories

### `creative_scripts/`
Stores structured script inputs and examples.

### `data/tts_profiles/`
Stores local ElevenLabs profile configuration.

## Output philosophy

The output structure is intentionally lightweight.

A run should keep only what is necessary, such as:
- creative script snapshot
- task rows
- render logs
- final video

The repository no longer treats debug artifacts as first-class outputs.
