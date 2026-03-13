# Director Engine

The Director Engine is the editorial rule layer of the system.

It is responsible for improving timeline consistency after the workflow has already generated a usable sequence.

## Responsibilities

- apply pacing rules
- reduce undesirable repetition
- apply transition logic
- control ending behavior
- keep editorial style consistent

## Non-responsibilities

The Director Engine does not:

- generate scripts
- generate shooting tasks
- manage footage uploads
- perform TTS generation
- build subtitles
- render the final video

## Input

The Director Engine operates on a normalized timeline.

Typical input includes:
- shot order
- tags
- duration
- transition-related metadata

## Output

The output is a modified timeline with editorial decisions applied.

## Current role in the project

In the current architecture:

- `ui_app.py` handles the operator workflow
- `src/workflow.py` handles the three-step product logic
- `src/director_engine/` handles editorial behavior

This separation keeps the Director Engine focused on style and structure, rather than product flow.
