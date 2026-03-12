# Script-First Video Automation Tool

A clean three-step workflow for promo-video production:

1. give a structured script
2. generate shooting tasks and fill footage slots
3. render the final video

## Core files

- `ui_app.py` — operator-facing UI
- `src/workflow.py` — core workflow logic
- `src/director_engine/` — editorial rules
- `src/tts_provider.py` — ElevenLabs provider
- `src/voiceover_a2.py` — voiceover event handling
- `src/subtitle_builder.py` — subtitle building
- `src/main.py` — CLI orchestration

## Notes

- ElevenLabs is the only supported TTS provider.
- The footage drive may live on external storage. The UI degrades safely if unavailable.
- Output is intentionally lightweight per run.
