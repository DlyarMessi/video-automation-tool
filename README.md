# Script-First Video Automation System

A script-driven pipeline for generating promo videos from structured creative scripts, reusable footage pools, voiceover, subtitles, and rule-based editing logic.

## What it does
- Converts structured creative scripts into production-ready timelines
- Generates shooting guides from the same source script
- Reuses organized footage pools for batch promo video generation
- Supports TTS voiceover and subtitle alignment
- Applies rule-based editorial logic through a Director Engine

## Core architecture
Creative Script -> Production Script -> Shooting Guide -> Director Engine -> Render

## Key modules
- `src/creative/`: creative script compilation
- `src/shooting/`: shooting guide generation
- `src/director_engine/`: rule-based editing behavior
- `ui_app.py`: operator-facing workflow UI

## Why this project exists
This project started from real business needs for repeated promo-video production, then evolved into a reusable, script-first video automation pipeline.

## Current status
- End-to-end pipeline available
- UI-driven workflow available
- Director Engine rules in progress
- Footage pool reuse workflow under active design

## Roadmap
- richer shot metadata for Director Engine
- improved motion continuity / transition rules
- stronger footage-pool retrieval and reuse
- cleaner public demo assets and examples