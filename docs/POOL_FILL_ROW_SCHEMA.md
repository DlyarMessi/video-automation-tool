# Pool Fill Row Schema v1

This document defines the current row structure produced for the Pool Fill task board.

It is not yet a formal runtime schema file.
It is a documentation contract for the current `build_pool_slot_rows(...)` output and downstream UI consumption.

---

## 1. Purpose

Pool Fill currently builds a normalized list of row dictionaries before rendering task cards.

This row layer is important because it now sits between:

- pool plans
- factory footage counting
- semantic enrichment
- registry hydration
- UI task-board rendering

If this structure is not documented, future work such as:

- registry-first rendering
- plan/template linkage
- brand creation flows
- natural-language slot generation

will become fragile.

---

## 2. Current lifecycle

The current conceptual pipeline is:

1. pool plan slots are loaded
2. footage pool is scanned
3. canonical counts are computed
4. row dictionaries are built
5. semantic fields are merged
6. registry hydration may override or enrich semantic values
7. UI cards render from row dictionaries

This means the row object is currently the main **render-facing integration layer** for Pool Fill.

---

## 3. Canonical identity fields

These fields identify the slot in canonical terms.

### `scene`
Canonical scene token.

Examples:
- `factory`
- `tower`
- `warehouse`
- `loading`
- `showroom`
- `weighing`

### `content`
Canonical content token.

Examples:
- `building`
- `automation`
- `testing`
- `panel`
- `inspection`
- `shipment`
- `storage`
- `product`
- `cabin`

### `coverage`
Canonical framing scale.

Current common values:
- `wide`
- `medium`
- `detail`
- `hero`

### `move`
Canonical movement token.

Current common values:
- `static`
- `slide`
- `pushin`
- `follow`
- `orbit`
- `reveal`

### `registry_key`
Explicit bridge key between runtime slot and canonical registry.

Format:

`scene.content.coverage.move`

Example:

`factory.automation.medium.slide`

---

## 4. Display-facing fields

These are fields consumed primarily by Pool Fill UI.

### `slot_label`
Primary display label shown in task cards.

Current rule:
- may start as canonical display text
- may later be replaced by `human_label`
- should remain the final card-ready label

### `canonical_slot_label`
Optional backup label preserving the canonical-style display label after semantic hydration.

### `human_label`
Human-friendly slot title.

Examples:
- `Factory exterior wide establishing shot`
- `Shipment follow shot`
- `Showroom product hero orbit`

### `shoot_brief`
Short execution explanation shown near the title.

Should answer:
- what to shoot
- how to frame the action in simple operator language

### `purpose`
Short editorial-purpose text.

Current examples:
- establish context
- show capability
- build trust
- brand emphasis

### `framing_label`
Existing framing guidance text used when no better semantic brief is available.

### `move_label`
Existing movement guidance text used for quick operator instruction.

### `duration_label`
Recommended clip duration label.

Examples:
- `5–7s`
- `4–6s`
- `6–8s`

---

## 5. Quantitative slot state fields

These fields reflect runtime coverage state.

### `target`
Desired clip count for the slot.

### `existing`
How many matching clips already exist in the factory pool.

### `missing`
How many more matching clips are still needed.

Computed as:

`max(0, target - existing)`

### `priority`
Current execution priority.

Current common values:
- `high`
- `medium`

---

## 6. Semantic support fields

These fields help convert internal canonical slots into execution-ready task cards.

### `success_criteria`
List of statements describing what counts as a valid capture.

### `fallback`
List of allowed substitutes if the ideal shot is not practical.

These fields are not yet heavily used in the UI, but they are now part of the slot knowledge layer and should be treated as valid row-level enrichment data.

---

## 7. Defaults / operational metadata

Rows may also carry through plan-level defaults.

### `defaults`
A nested dictionary containing soft-tag defaults such as:

- `energy`
- `quality_status`
- `continuity_group`
- `intro_safe`
- `hero_safe`
- `outro_safe`

These are not the same as canonical identity.
They are operational/editorial metadata.

---

## 8. Source-of-truth interpretation (current phase)

Current best interpretation:

### Pool plan owns
- topic grouping
- target count
- priority
- brand/plan-local execution setup

### Registry owns or will increasingly own
- canonical identity
- human-facing semantic meaning
- reusable slot explanation
- reusable fallback logic
- reusable purpose description

### Row layer owns
- render-ready merged view for Pool Fill UI
- current coverage state
- final per-card resolved display payload

---

## 9. Recommended stability rule

From now on, any new Pool Fill feature should try to fit into one of three layers:

1. **plan layer**
2. **registry layer**
3. **row/render layer**

New UI features should avoid directly inventing ad hoc row keys unless the new key is documented here or in a successor schema document.

---

## 10. Current status

This document is **v1 documentation**, not yet a machine-enforced schema.

Later evolution may introduce:

- a formal row typed model
- validation helpers
- registry-first card hydration rules
- template-driven Pool Fill generation
