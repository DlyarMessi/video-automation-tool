# System Fields Dictionary

This document defines the current field system used by the project.

It is the reference for:

- file naming
- material indexing
- pool-plan intake
- director rules
- UI editing scope
- canonical vs user-facing field boundaries

---

## 0. Governance Boundary

The project now formally distinguishes:

- **core matching fields** — machine-critical canonical fields
- **user-facing semantic fields** — human-readable guidance fields
- **soft tags** — editorial and workflow metadata

Current core matching fields remain:
- `scene`
- `content`
- `coverage`
- `move`

Recommended future user-facing semantic fields include:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

These are governed conceptually now, even if not yet fully hydrated across runtime structures.

## 1. Naming Fields

These fields are encoded in the core filename pattern.

Pattern:

`scene_content_coverage_move_index.ext`

Example:

`factory_automation_wide_slide_01.mp4`

### scene
High-level place or environment.

Examples:
- `factory`
- `showroom`
- `tower`
- `warehouse`
- `loading`

### content
What the shot mainly shows.

Examples:
- `automation`
- `testing`
- `inspection`
- `building`
- `product`
- `shipment`
- `storage`
- `panel`

### coverage
Shot scale / editorial use.

Current core values:
- `wide`
- `medium`
- `detail`
- `hero`

### move
Camera movement token.

Current commonly used values:
- `static`
- `slide`
- `pushin`
- `follow`
- `orbit`
- `reveal`

Legacy or extended tokens may still exist in older material sets.

### index
Two-digit sequence used when the previous fields are the same.

Examples:
- `01`
- `02`
- `03`

---

## 2. Material Index Fields

These fields are stored in `asset_index.json`.

### Auto-generated fields

#### filename
Actual file name in the factory pool.

#### scene
Parsed from file name.

#### content
Parsed from file name.

#### coverage
Parsed from file name.

#### move
Parsed from file name.

#### orientation
Auto-detected from media dimensions.

Values:
- `portrait`
- `landscape`

#### raw_duration
Original media duration in seconds.

#### usable_start
Suggested usable start point in seconds.

#### usable_end
Suggested usable end point in seconds.

#### usable_duration
Computed as:

`usable_end - usable_start`

### Human-edited soft tags

#### hero_safe
Whether this clip is safe for hero / brand-ending usage.

#### intro_safe
Whether this clip is safe for opening / establishing usage.

#### outro_safe
Whether this clip is safe for closing usage.

#### continuity_group
Soft grouping key for clips that belong to the same action chain, space chain, or coherent sequence.

#### energy
Pacing strength indicator.

Allowed values:
- `low`
- `medium`
- `high`

#### quality_status
Human review result.

Allowed values:
- `approved`
- `review`
- `reject`

#### notes
Freeform operator note.

---

## 3. Pool Fill / Pool Plan Fields

Pool plans are now brand-scoped and typically live under:

`data/brands/<company>/pool_plans/<plan>.yaml`

### brand
Brand name for the plan.

### topics
Top-level intake groups shown in Pool Fill.

Each topic contains:

- `name`
- `slots`

### slot fields

#### scene
Target environment for the slot.

#### content
Target subject / action for the slot.

#### coverage
Target framing scale for the slot.

#### move
Target camera movement token for the slot.

#### target
Desired clip count for this slot.

#### priority
Current values commonly used:
- `high`
- `medium`

#### defaults
Default soft-tag values to apply on upload.

Common keys:
- `energy`
- `quality_status`
- `continuity_group`
- `intro_safe`
- `hero_safe`
- `outro_safe`

---

## 4. Render / Subtitle Fields

These live in render presets and compiled project settings.

### FPS
Current default:
- `60`

### language_to_family
Maps language short code to subtitle family bucket.

Current notable mappings:
- `en` → `latin`
- `fr` → `latin`
- `es` → `latin`
- `ru` → `cyrillic`
- `kk` → `cyrillic`
- `tg` → `cyrillic`
- `ar` → `arabic`
- `ug` → `arabic`
- `uz` → `latin` (default bucket)

### subtitle_style
Per-language subtitle style payload.

Current fields:
- `family`
- `font_family`
- `font_file`
- `has_font_file`
- `font_size`
- `outline`
- `shadow`
- `bottom_margin`
- `max_lines`
- `line_spacing`

### script-family fallback
Language checks may allow more than one detected script family.

Current notable fallback behavior:
- `kk` accepts `cyrillic` or `latin`
- `uz` accepts `latin` or `cyrillic`

### filter_preset
Visual output preset.

Current presets:
- `clean`
- `industrial`
- `warm_brand`

Current fields:
- `name`
- `enabled`
- `brightness`
- `contrast`
- `saturation`

---

## 5. Pool Fill Row Layer (current render-facing integration layer)

The Pool Fill UI currently depends on a normalized row structure built before rendering cards.

Important current row fields include:
- `scene`
- `content`
- `coverage`
- `move`
- `registry_key`
- `slot_label`
- `canonical_slot_label`
- `human_label`
- `shoot_brief`
- `purpose`
- `framing_label`
- `move_label`
- `duration_label`
- `target`
- `existing`
- `missing`
- `priority`
- `success_criteria`
- `fallback`
- `defaults`

See also:
- `docs/POOL_FILL_ROW_SCHEMA.md`

## 6. Director Rule Inputs

These fields are currently consumed by director rules.

### structure
Uses:
- `coverage`
- `content`
- `intro_safe`
- `hero_safe`
- `outro_safe`

### motion_continuity
Uses:
- `scene`
- `content`
- `coverage`
- `move`
- `continuity_group`
- `quality_status`

### pacing
Uses:
- `duration`
- `coverage`
- `energy`

### ending
Uses:
- `hero_safe`
- `outro_safe`
- hero-like fallback logic
- random-ending avoidance

### repetition
Uses:
- `scene`
- `content`
- `coverage`
- primary tag signature

### transitions
Uses rule-specific timeline adjacency and pacing context.
