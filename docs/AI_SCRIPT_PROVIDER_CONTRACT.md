# AI Script Provider Contract (v1)

## Why this layer exists

This layer introduces a formal AI script intake/compile/provider contract without creating a parallel prototype lane.

The architecture direction is:

1. normalize user intent,
2. compile intent into governed constraints using project taxonomy/semantics,
3. call a replaceable provider adapter,
4. return structured draft outputs that stay compatible with existing production logic.

## Not a bypass path

This contract is intentionally a **front-end compiler** into existing governed production concepts:

- canonical tuple semantics (`scene/content/coverage/move`)
- semantic slot fields (`human_label`, `shoot_brief`, `success_criteria`, `fallback`, `purpose`)
- pool-plan compatible thinking (topics/evidence/moves)

The provider layer is not allowed to bypass governance.

## Contract objects

Defined in `src/intake_models.py`:

- `NormalizedIntakeBrief`
- `CompiledGenerationConstraints`
- `StyleReference`
- `ScriptProviderRequest`
- `ScriptSectionDraft`
- `ScriptDraft`
- `PoolPlanDraft`
- `ScriptProviderResponse`

These are the stable v1 boundary models for intake and provider interop.

## Compile path

`src/intake_compiler.py` compiles `NormalizedIntakeBrief` + taxonomy bundle into `CompiledGenerationConstraints`.

v1 compiler behavior is intentionally minimal but real:

- maps objective to topic/evidence via `intent_mappings` (when available)
- keeps `required_topics` and `required_evidence` semantically distinct
- supports explicit `must_include` routing:
  - `topic:<value>` -> `required_topics`
  - `evidence:<value>` -> `required_evidence`
  - unprefixed values are currently treated as topics (with warning)
- derives move preferences from intake style/asset hints, then validates against canonical registry move vocabulary and emits warnings for out-of-vocab values
- enforces required semantic fields used by governed pool-fill flows
- emits machine-oriented hard rules + soft preferences + warnings

## Concrete examples

### Example `NormalizedIntakeBrief`

```yaml
brand_name: Siglen
product_name: Passenger Elevator
audience: Real-estate procurement teams
objective: Show quality proof and factory capability
language: zh
orientation: portrait
duration_s: 45
style_keywords:
  - technical
  - premium
must_include:
  - topic:Testing & Quality
  - evidence:inspection detail
  - Factory Strength
evidence_priorities:
  - panel readout proof
available_assets:
  - drone
```

### Example compiled `CompiledGenerationConstraints`

```yaml
required_topics:
  - Testing & Quality
  - Factory Strength
required_evidence:
  - inspection detail
  - panel readout proof
preferred_moves:
  - orbit
  - slide
  - static
  - pushin
  - reveal
acceptable_moves:
  - static
  - slide
  - pushin
  - follow
  - orbit
  - reveal
avoid_moves: []
required_semantic_fields:
  - human_label
  - shoot_brief
  - success_criteria
  - fallback
  - purpose
orientation: portrait
duration_s: 45
language: zh
hard_rules:
  - "RULE:canonical_tuple_required: section planning MUST remain compatible with canonical scene/content/coverage/move."
  - "RULE:semantic_fields_required: each generated section MUST support human_label/shoot_brief/success_criteria/fallback/purpose semantics."
warnings:
  - "must_include item treated as topic (use 'topic:'/'evidence:' prefix for explicit routing): Factory Strength"
```

### Example `ScriptProviderResponse`

```yaml
script_draft:
  title: Siglen Script Draft
  key_message: Quality-proven manufacturing capability
  creative_brief: Intro + proof + brand close
  sections:
    - section_id: S01
      purpose: Establish capability context
      narration: Siglen delivers reliable elevator manufacturing at factory scale.
      on_screen_text: Siglen Factory Capability
      success_criteria: Must align to compiled required topics/evidence and semantic fields.
      evidence_needed:
        - inspection detail
      preferred_scene:
        - factory
      acceptable_scene:
        - tower
      preferred_move:
        - static
      acceptable_move:
        - slide
      avoid_move: []
      fallback: Use another canonical slot with same purpose.
      notes: Manual provider scaffold output.
  warnings:
    - Manual scaffold output; refine before production compile.
pool_plan_draft:
  rows: []
  warnings:
    - No automatic pool plan rows in manual scaffold mode.
unresolved_risks: []
confidence_notes: []
```

## Provider abstraction

`src/script_provider_base.py` defines the abstract provider interface:

- `provider_name`
- `generate(request: ScriptProviderRequest) -> ScriptProviderResponse`

Current providers:

- `ManualScriptProvider` (`src/script_provider_manual.py`)
  - supports local/no-API workflow
  - can load response from local file or return a deterministic scaffold
- `GeminiScriptProvider` (`src/script_provider_gemini.py`)
  - scaffold only in v1
  - includes prompt-builder and parsing/API placeholders
  - no network call implemented yet
- `OpenRouterScriptProvider` (`src/script_provider_openrouter.py`)
  - first live provider integration using OpenRouter OpenAI-compatible chat API
  - consumes normalized brief + compiled constraints + style references + provider hints in prompt
  - parses strict JSON output into `ScriptProviderResponse`

## Pipeline entry

`src/script_pipeline.py` orchestrates:

1. intake normalize + validate
2. brief -> constraints compile
3. provider generation
4. response shape validation
5. return `ScriptPipelineResult` envelope containing normalized brief + compiled constraints + provider response

CLI entry for local development:

- `scripts/run_script_pipeline.py`

Pipeline return object (v1):

- `normalized_brief`
- `compiled_constraints`
- `provider_response`

`run_script_pipeline(...)` also accepts optional `style_references` and forwards them to `ScriptProviderRequest.style_references`.

## OpenRouter mode (first live provider)

OpenRouter mode is optional and env-driven:

- required: `OPENROUTER_API_KEY`
- optional: `OPENROUTER_MODEL` (default `openrouter/free`)
- optional attribution headers: `OPENROUTER_SITE_URL`, `OPENROUTER_APP_NAME`

See `docs/OPENROUTER_PROVIDER_SETUP.md` for usage and examples.

## Manual mode

Manual mode is first-class for open-source/no-API usage:

- run pipeline with `--provider manual`
- optionally pass `--manual-response <path>`
- if no response file is supplied, provider returns a deterministic scaffold draft

## What is still heuristic in v1

Still heuristic:

- style/asset -> move preference mapping (simple deterministic rules)
- objective keyword matching when intent mappings are sparse
- unprefixed `must_include` values default to topic routing

Expected to become more governed later:

- richer mapping from canonical + combo rules + intent data into constraints
- stronger typed topic/evidence schema and stricter must-include routing
- explicit machine-checkable rule objects in the contract (if/when contract version advances)

## Future extension points

Planned adapter expansions can plug into the same base contract:

- `gemini_api`
- `openai_api`
- `custom_http_provider`

The compile contract and governed constraints stay constant while provider implementations change.

## Current non-goals (v1)

- no real API network integration
- no UI integration changes
- no taxonomy redesign
- no bypass of existing pool-plan/canonical governance
- no broad refactor of render/director systems


DeepSeek setup and usage: `docs/DEEPSEEK_PROVIDER_SETUP.md`.
