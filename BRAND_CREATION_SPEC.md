# Brand Creation Spec v1

This document defines the current product-facing rules for adding a new brand into the system.

It is a **specification-first** document.
It does not require a full UI flow yet.
Its purpose is to prevent future brand onboarding from becoming ad hoc.

---

## 1. Goal

The project is no longer treated as a one-off internal script tool.

It is moving toward a reusable, open, and product-grade system.

That means adding a new brand should eventually become:

- understandable
- guided
- auditable
- repeatable
- compatible with the canonical system core

This document defines the first stable rules for that onboarding path.

---

## 2. Design principle

Brand onboarding must follow this rule:

- **global layers stay governed**
- **brand layers stay local**
- **brand-local needs must not pollute the global system too early**

This means a new brand is not allowed to invent its own private protocol for:

- canonical tags
- core registry structure
- render profile schema
- global language family rules

A new brand may provide:
- local pool plans
- local logo / BGM assets
- local creative scripts
- local execution guidance
- temporary local overrides

---

## 3. Current directory expectation

The current recommended brand layout is:

`data/brands/<brand_slug>/`

Current expected substructure:

`data/brands/<brand_slug>/logo.png`
`data/brands/<brand_slug>/pool_plans/default.yaml`

Optional future substructure:

`data/brands/<brand_slug>/bgm/`
`data/brands/<brand_slug>/guides/`
`data/brands/<brand_slug>/overrides/`

### Current rule
For v1, the practical minimum brand package is:

- brand directory
- logo file
- one default pool plan

---

## 4. Brand slug rule

Each brand must have a stable slug.

### slug requirements
- lowercase
- filesystem-safe
- derived from a human-facing brand name
- should not contain random punctuation
- should not encode version numbers casually

Examples:
- `siglen`
- `fareo`

The slug should be the canonical filesystem identity for the brand layer.

---

## 5. Minimum required brand assets

### Required in v1

#### 1. logo
Expected path:

`data/brands/<brand_slug>/logo.png`

Used for:
- watermarking
- brand presence
- asset existence checks

#### 2. default pool plan
Expected path:

`data/brands/<brand_slug>/pool_plans/default.yaml`

Used for:
- Pool Fill Mode
- reusable footage intake
- execution planning
- slot structure seed

### Optional in v1

#### BGM
A brand may later provide brand-specific BGM.
This is not required to create the brand layer.

Preferred future direction:

`data/brands/<brand_slug>/bgm/`

Not:

- scattered ad hoc single-file placement
- hidden per-script assumptions

---

## 6. Brand pool plan rule

Each new brand should start with exactly one practical starter pool plan:

`default.yaml`

This keeps onboarding simple.

### Why
Because early-stage brand creation should not require the user to understand:

- multiple plan variants
- variant inheritance
- deep template branching
- plan routing logic

Those may come later.

For v1, a new brand gets:
- one default plan
- topic groups
- canonical slots
- optional semantic execution fields
- optional `registry_key` links

---

## 7. What belongs to the global layer

The following should remain globally governed:

### canonical core
- `scene`
- `content`
- `coverage`
- `move`

### taxonomy direction
- canonical registry format
- combo rules structure
- intent mapping structure

### render profile system
- language-to-family mapping
- subtitle preset structure
- filter preset structure

### policy documents
- canonical tag policy
- field boundaries
- row schema documentation
- terminology

A new brand should consume these layers, not redefine them.

---

## 8. What belongs to the brand layer

The following are brand-local:

### brand identity assets
- logo
- future BGM assets
- future guide assets

### brand pool plans
- topic grouping
- target counts
- priorities
- local execution emphasis

### brand creative inputs
- creative scripts
- campaign variants
- brand-specific message focus

### local overrides
- brand-specific explanatory notes
- temporary extensions
- non-global operational differences

---

## 9. Brand vs global boundary rule

A new field requested by one brand should **not** automatically become a global field.

Preferred rule:

- first test locally
- observe whether it is reusable
- promote globally only when justified

This aligns with the project's broader governance direction, including the three-brand principle.

---

## 10. Starter package checklist

A brand starter package should eventually be validated against this checklist.

### Required
- [ ] stable brand slug
- [ ] human-facing brand name
- [ ] `data/brands/<slug>/`
- [ ] `logo.png`
- [ ] `pool_plans/default.yaml`

### Recommended
- [ ] at least one topic in the default plan
- [ ] at least one high-priority slot
- [ ] semantic execution fields for operator readability
- [ ] registry linkage via `registry_key`

### Optional
- [ ] BGM folder
- [ ] downloadable guide
- [ ] local notes / overrides

---

## 11. Suggested future UI flow

This document does not implement the UI.
But it defines the intended future shape.

A future brand creation flow should likely ask for:

1. brand display name
2. brand slug
3. logo upload
4. optional BGM assets
5. starter pool plan creation path
   - create blank default plan
   - clone from starter template
   - clone from another brand
6. validation summary

The UI should validate:
- directory layout
- required assets
- pool plan presence
- filename collisions
- slug cleanliness

---

## 12. Validation expectations

A future brand creation validator should check:

### directory checks
- brand root exists
- required subfolders exist or can be created

### asset checks
- logo exists
- optional BGM paths are readable if provided

### plan checks
- default plan exists
- topics list is valid
- slots structure is valid
- canonical fields are present
- optional `registry_key` values are well-formed

### policy checks
- no private redefinition of canonical fields
- no global-schema drift
- no brand-local pollution of governed global layers

---

## 13. Recommended onboarding strategy

For the next implementation phase, the project should prefer:

### Step 1
Manual filesystem + spec-driven onboarding

### Step 2
Guided CLI or script-assisted onboarding

### Step 3
UI-assisted brand creation flow

This staged approach keeps code risk low while the product model becomes more stable.

---

## 14. Summary

Brand creation should become a first-class workflow, but not by weakening the global system.

The project therefore adopts this v1 principle:

- **global protocol stays strict**
- **brand onboarding becomes guided**
- **brand-local assets and plans stay local**
- **promotion to global structure happens slowly and intentionally**

This is the current foundation for future multi-brand onboarding.
