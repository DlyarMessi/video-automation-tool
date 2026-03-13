# System Fields Dictionary

This document defines the current field system used by the project.

It is the reference for:
- file naming
- material indexing
- director rules
- UI editing scope

---

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
- `villa`

### content
What the shot mainly shows.

Examples:
- `automation`
- `testing`
- `line`
- `building`

### coverage
Shot scale / editorial use.

Allowed core values:
- `wide`
- `medium`
- `detail`
- `hero`

### move
Camera movement token.

Current core values:
- `static`
- `panl`
- `panr`
- `tiltu`
- `tiltd`
- `slidel`
- `slider`
- `pushin`
- `pullout`
- `follow`
- `pov`
- `orbit`
- `reveal`
- `expand`

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
Auto-read from file metadata.

#### usable_start
Suggested usable start point in seconds.
Default is inferred automatically.

#### usable_end
Suggested usable end point in seconds.
Default is inferred automatically.

#### usable_duration
Computed as:

`usable_end - usable_start`

### Human-edited soft tags

#### hero_safe
Whether this clip is safe for hero/brand-ending usage.

Values:
- `true`
- `false`

#### intro_safe
Whether this clip is safe for opening / establishing usage.

Values:
- `true`
- `false`

#### outro_safe
Whether this clip is safe for final closing usage.

Values:
- `true`
- `false`

#### continuity_group
Soft grouping key for clips that belong to the same action chain,
space observation chain, or coherent sequence.

Examples:
- `automation_line_a`
- `testing_station_b`
- `factory_exterior_orbit`

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

## 3. Render / Subtitle Fields

These live in render presets and compiled project settings.

### FPS
Current default:
- `60`

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

## 4. Director Rule Inputs

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
Uses:
- same-family continuity
- repeated detail checks
- primary tag continuity

---

## 5. UI Editing Scope

### Automatically generated in UI / system
- file naming shell
- raw duration
- orientation
- usable window defaults
- subtitle preset selection
- filter preset selection

### Human-editable in UI
- `hero_safe`
- `intro_safe`
- `outro_safe`
- `continuity_group`
- `energy`
- `quality_status`
- `notes`

### Not yet exposed for editing
- manual override of `usable_start`
- manual override of `usable_end`
- explicit per-shot reuse weight
- explicit clip priority score

---

## 6. Field Design Principles

### Keep filenames short
Do not overload filenames with soft editorial meaning.

### Put reusable semantics into the material index
Anything likely to affect:
- director logic
- scheduling
- repetition control
- shot suitability

should live in the index, not in the filename.

### Prefer defaults over heavy manual annotation
If a field can be:
- inferred from file structure
- inferred from duration
- standardized by shooting rules

it should not become a required manual step.

### Human review should focus on high-value judgment
The operator should mainly decide:
- whether a clip is intro-safe / outro-safe / hero-safe
- whether a clip belongs to a continuity group
- the energy level
- the quality status

