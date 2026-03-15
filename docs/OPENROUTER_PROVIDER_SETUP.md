# OpenRouter Provider Setup

This repository now includes a first live external provider adapter:

- `OpenRouterScriptProvider` in `src/script_provider_openrouter.py`

It is integrated into the existing intake/compiler/provider contract and **does not bypass** governed constraints.

## Why OpenRouter here

OpenRouter is used as an optional provider backend for generated script drafts while preserving:

- normalized intake brief validation,
- governed constraint compilation,
- contract-shaped `ScriptProviderResponse` output.

Manual mode remains first-class and no-API workflows are still supported.

## Required environment variables

- `OPENROUTER_API_KEY` (required for openrouter mode)

## Optional environment variables

- `OPENROUTER_MODEL` (default: `openrouter/free`)
- `OPENROUTER_SITE_URL` (optional attribution header)
- `OPENROUTER_APP_NAME` (optional attribution header)

## Default model

If no override is provided, the provider uses:

- `openrouter/free`

## Run local CLI pipeline with OpenRouter

Example with env vars:

```bash
export OPENROUTER_API_KEY="<your_key>"
export OPENROUTER_MODEL="openrouter/free"
python3 scripts/run_script_pipeline.py --intake /path/to/intake.json --provider openrouter
```

Optional model override from CLI:

```bash
python3 scripts/run_script_pipeline.py \
  --intake /path/to/intake.json \
  --provider openrouter \
  --openrouter-model openrouter/free
```

## Manual mode still available

```bash
python3 scripts/run_script_pipeline.py --intake /path/to/intake.json --provider manual
```

## Deferred by design

- UI/sidebar integration for provider settings is intentionally deferred.
- Real provider selection UX in Streamlit is intentionally deferred.
- The OpenRouter provider is additive to the existing contract layer; it is not a contract redesign.
