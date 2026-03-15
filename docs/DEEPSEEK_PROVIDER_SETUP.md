# DeepSeek Provider Setup

This repository supports `DeepSeekScriptProvider` as an additive AI script generation provider alongside `manual` and `openrouter`.

It uses DeepSeek's OpenAI-compatible chat completions API while preserving the same governed script output contract (`ScriptProviderResponse`) and compiled constraint enforcement.

## Environment variables

Required for deepseek mode:
- `DEEPSEEK_API_KEY`

Optional:
- `DEEPSEEK_MODEL` (default: `deepseek-chat`)
- `DEEPSEEK_BASE_URL` (default: `https://api.deepseek.com`)

## CLI usage

Basic:

```bash
export DEEPSEEK_API_KEY="<your_key>"
python3 scripts/run_script_pipeline.py --intake /path/to/intake.json --provider deepseek
```

With model override:

```bash
python3 scripts/run_script_pipeline.py \
  --intake /path/to/intake.json \
  --provider deepseek \
  --deepseek-model deepseek-chat
```

## UI/sidebar usage

In the AI provider settings panel:
1. Select provider = `deepseek`
2. Set `DeepSeek API Key`
3. Optionally adjust `DeepSeek Model` and `DeepSeek Base URL`
4. Save settings locally

Settings are local-only in `.workspace/ai/provider_settings.json`.

## Governance note

This provider is additive only. It does not bypass intake compilation, canonical constraints, semantic checks, or pool-plan governance behavior.
