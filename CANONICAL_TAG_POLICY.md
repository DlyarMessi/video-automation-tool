# Canonical Tag Policy v1

This document defines the current governance policy for the system's canonical shot language.

It is intentionally **policy-first**:
- strict enough to govern growth
- light enough to fit the current codebase
- designed for later registry-based evolution

This document does **not** replace current pool plans or runtime logic.
It defines the rules future taxonomy and registry work must follow.

---

## 1. Policy Goal

The system is now treated as a product-grade, reusable, and eventually open-source workflow.

That means:

1. the internal machine layer must remain strict
2. user-facing language must remain understandable
3. internal and external expressions may differ, but must map cleanly

The system therefore adopts:

- a **single canonical internal core**
- a **user-facing semantic layer**
- a future **governed mapping layer**

---

## 2. Current Canonical Core

The canonical matching language is currently defined by four fields:

- `scene`
- `content`
- `coverage`
- `move`

These are the only fields that should be treated as the **core matching tuple**.

They are used by:

- file naming
- footage matching
- slot counting
- material indexing
- render preparation
- selection and scheduling support
- downstream rule logic

Canonical filename pattern remains:

`scene_content_coverage_move_index.ext`

Example:

`factory_automation_wide_static_01.mp4`

---

## 3. Canonical Field Responsibilities

### scene
Defines the environment, place, or spatial context.

Rules:
- should represent a location or operating area
- should remain spatial, not narrative
- should not encode shot scale, purpose, or review meaning

Examples:
- `factory`
- `tower`
- `warehouse`
- `loading`
- `showroom`

### content
Defines the main object, process, or action center of the shot.

Rules:
- should describe the primary subject or operational focus
- should remain short and reusable
- should not become a natural-language sentence
- should not absorb scene meaning unless truly inseparable

Examples:
- `automation`
- `testing`
- `inspection`
- `building`
- `panel`
- `shipment`
- `product`

### coverage
Defines framing scale.

Current governed values:
- `wide`
- `medium`
- `detail`
- `hero`

### move
Defines camera movement.

Current governed common values:
- `static`
- `slide`
- `pushin`
- `follow`
- `orbit`
- `reveal`

Legacy motion tokens may still exist in old material sets, but new work should prefer the current governed set.

---

## 4. Core Matching Fields vs User-Facing Fields

The system now formally distinguishes two layers.

## Layer A — Core Matching Fields
These are strict internal fields:

- `scene`
- `content`
- `coverage`
- `move`

They must remain:
- governed
- enumerable
- stable
- difficult to change casually

## Layer B — User-Facing Semantic Fields
These are not core matching keys.
They exist to help humans understand and execute slots.

Current recommended user-facing semantic fields are:

- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

### Intended meanings

#### human_label
Short human-readable slot label for UI and exports.

#### shoot_brief
One or two sentences describing what to capture in practice.

#### success_criteria
How an operator decides that the slot is truly covered.

#### fallback
Allowed substitute path when the exact slot cannot be captured.

#### purpose
Why the slot exists in editorial or story terms.

---

## 5. Public Layer and Internal Layer Boundary

The user should not be forced to author raw internal tags directly.

The preferred future model is:

- users interact with human-friendly descriptions
- the system resolves them to canonical tags
- internal indexing remains canonical

This means:

- user-facing language may evolve
- canonical core must remain stable
- human-friendly expressions should not pollute canonical vocabulary

---

## 6. Content Governance Rules

`content` is now treated as **strictly governed but not namespaced**.

### v1 position
- do **not** introduce namespace-style content names by default
- do **not** explode content into overly long identifiers yet
- do **not** let content grow freely without review

### content must:
- remain short
- remain reusable
- remain distinct from scene and purpose
- avoid natural-language phrasing
- avoid duplicate synonyms
- avoid branding or per-user phrasing

### content growth policy
A new content value should only be added when:
- an existing value is clearly insufficient
- the meaning is reusable beyond one slot
- the boundary with neighboring content values is explainable

---

## 7. Scene–Content Relationship

`scene` and `content` are related, but not interchangeable.

Rules:
- `scene` describes where
- `content` describes what
- `content` may have different meaning across scenes, but should not be duplicated prematurely
- ambiguity should be governed first before adding namespace-style content

Example:
- `panel` may appear in multiple scenes
- do not immediately split into namespaced forms unless collision becomes operationally harmful

---

## 8. Soft Tags vs Canonical Tags

Canonical tags are not the same as metadata soft tags.

### Canonical tags
Used for:
- naming
- slot identity
- matching
- structural reuse

### Soft tags
Used for:
- editorial qualification
- quality control
- workflow support

Examples:
- `hero_safe`
- `intro_safe`
- `outro_safe`
- `continuity_group`
- `energy`
- `quality_status`
- `notes`

Soft tags may evolve more flexibly.
Canonical tags should evolve much more slowly.

---

## 9. Combo Rules Principle

Not every theoretical combination of canonical values should be treated as equally valid.

A future combo-rules layer should govern:
- allowed combinations
- discouraged combinations
- deprecated combinations
- scene-specific constraints

However, v1 keeps combo rules lightweight:
- define policy first
- add explicit machine-readable combo rules later
- avoid premature full DSL design

---

## 10. Versioning Principle

Versioning should begin early, but stay light.

Therefore the system will prefer:
- `canonical_registry_v1.yaml`
- `combo_rules_v1.yaml`
- `intent_mappings_v1.yaml`

rather than unversioned forever files.

v1 versioning means:
- schema is acknowledged as governed
- future changes can be evolved without breaking historical context
- migration can become explicit later

---

## 11. Three-Brand Principle

A new cross-system field should not automatically become global just because one brand needs it.

Guiding rule:

A candidate field should normally appear across at least **three independent brand use cases** before being promoted into the global governed core.

This prevents:
- single-brand pollution
- premature field inflation
- accidental schema bloat

Before global promotion, such fields should stay in:
- plan-local metadata
- brand-local extensions
- or future extension zones

---

## 12. Rich Central Registry Direction

The preferred long-term direction is not two separate parallel systems.

The preferred direction is a **rich central registry** where one canonical slot identity can carry:

- canonical fields
- user-facing label/brief
- success/fallback guidance
- editorial purpose metadata

That future direction may look like:

- one canonical slot identity
- one source of truth
- multiple consumer layers

But that is a later implementation phase.

v1 policy does **not** require converting all pool plans immediately.

---

## 13. Current Phase Decision

Current project phase:

### Phase 1 — Policy First
Do now:
- define policy
- clarify terminology
- stabilize field boundaries
- create taxonomy placeholders

Do not do yet:
- full registry hydration in UI
- full public-authoring engine
- template-only pool plans
- mapping engine refactor
- namespace-heavy content redesign

---

## 14. Immediate Implementation Consequence

From now on:

- all new canonical tags should be reviewed under this policy
- all new user-facing explanatory fields should remain outside the core matching tuple
- all future taxonomy files should align with this policy
- current code may remain incremental, but new structure should follow governed direction

---

## 15. Summary

The system now formally adopts:

- **strict canonical internal core**
- **clear human-facing explanation layer**
- **future governed mapping layer**
- **policy before registry**
- **registry before large-scale UI abstraction**

This is the v1 foundation for turning the project from a powerful internal workflow into a maintainable open-source production tool.
