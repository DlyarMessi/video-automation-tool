# SIGLEN Pool Plan Audit v1

Audit target:

- `data/brands/siglen/pool_plans/default.yaml`

Audit basis:

- `CANONICAL_TAG_POLICY.md`
- current governed core = `scene + content + coverage + move`
- current goal = review current slot quality before introducing full registry hydration

---

## 1. Overall status

- Total topics: **4**
- Total slots: **19**
- Structurally acceptable slots: **19**
- Slots needing naming/governance attention: **9**
- Slots recommended for future user-facing semantic enrichment: **19**

Current high-level conclusion:

- The current SIGLEN plan is already usable as a canonical-slot plan.
- Most current values fit the governed `scene / content / coverage / move` model.
- The main next improvement is not large renaming, but adding a human-friendly execution layer.
- The main naming watchpoints are currently around broad or cross-context content values such as `testing`, `panel`, `shipment`, and `building`.

---

## 2. Slots that are structurally acceptable

These slots fit the current canonical policy well enough to remain in place for v1.

- **Factory Strength** · `factory / building / wide / static`  
  target=8 · priority=high
- **Factory Strength** · `factory / building / hero / orbit`  
  target=6 · priority=high
- **Factory Strength** · `factory / automation / wide / static`  
  target=10 · priority=high
- **Factory Strength** · `factory / automation / medium / slide`  
  target=10 · priority=high
- **Factory Strength** · `factory / automation / detail / static`  
  target=12 · priority=high
- **Quality & Safety** · `tower / testing / medium / static`  
  target=8 · priority=high
- **Quality & Safety** · `tower / testing / detail / static`  
  target=10 · priority=high
- **Quality & Safety** · `tower / panel / detail / static`  
  target=8 · priority=medium
- **Quality & Safety** · `factory / inspection / detail / static`  
  target=8 · priority=medium
- **Warehouse & Delivery** · `warehouse / storage / wide / static`  
  target=8 · priority=high
- **Warehouse & Delivery** · `warehouse / storage / detail / static`  
  target=8 · priority=medium
- **Warehouse & Delivery** · `loading / shipment / medium / follow`  
  target=8 · priority=high
- **Warehouse & Delivery** · `loading / shipment / detail / static`  
  target=8 · priority=medium
- **Warehouse & Delivery** · `weighing / shipment / detail / static`  
  target=6 · priority=medium
- **Product Showcase** · `showroom / product / wide / static`  
  target=8 · priority=high
- **Product Showcase** · `showroom / product / medium / slide`  
  target=8 · priority=high
- **Product Showcase** · `showroom / cabin / detail / static`  
  target=10 · priority=medium
- **Product Showcase** · `showroom / panel / detail / static`  
  target=8 · priority=medium
- **Product Showcase** · `showroom / product / hero / orbit`  
  target=6 · priority=high

---

## 3. Slots needing naming / governance attention

These do **not** necessarily need immediate renaming.
They should be watched because they may become ambiguous as the system grows.

### Factory Strength · `factory / building / wide / static`

Governance watch notes:
- broad but currently still usable; may need tighter semantics later depending on growth

### Factory Strength · `factory / building / hero / orbit`

Governance watch notes:
- broad but currently still usable; may need tighter semantics later depending on growth

### Quality & Safety · `tower / testing / medium / static`

Governance watch notes:
- broad but currently acceptable if tower/testing remains a stable, reusable concept

### Quality & Safety · `tower / testing / detail / static`

Governance watch notes:
- broad but currently acceptable if tower/testing remains a stable, reusable concept

### Quality & Safety · `tower / panel / detail / static`

Governance watch notes:
- cross-scene meaning may become ambiguous later

### Warehouse & Delivery · `loading / shipment / medium / follow`

Governance watch notes:
- may represent workflow stage rather than primary visible subject

### Warehouse & Delivery · `loading / shipment / detail / static`

Governance watch notes:
- may represent workflow stage rather than primary visible subject

### Warehouse & Delivery · `weighing / shipment / detail / static`

Governance watch notes:
- may represent workflow stage rather than primary visible subject

### Product Showcase · `showroom / panel / detail / static`

Governance watch notes:
- cross-scene meaning may become ambiguous later

---

## 4. Slots recommended for user-facing semantic fields

Per current policy, canonical tags should remain strict, while public-facing execution guidance should be attached separately.
The following slots are good candidates for the first semantic enrichment pass.

### Factory Strength · `factory / building / wide / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators

### Factory Strength · `factory / building / hero / orbit`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- hero usage needs editorial explanation for operators

### Factory Strength · `factory / automation / wide / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Factory Strength · `factory / automation / medium / slide`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Factory Strength · `factory / automation / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Quality & Safety · `tower / testing / medium / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- location/task context benefits from more explicit field guidance

### Quality & Safety · `tower / testing / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- location/task context benefits from more explicit field guidance

### Quality & Safety · `tower / panel / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- location/task context benefits from more explicit field guidance

### Quality & Safety · `factory / inspection / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Warehouse & Delivery · `warehouse / storage / wide / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Warehouse & Delivery · `warehouse / storage / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Warehouse & Delivery · `loading / shipment / medium / follow`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- location/task context benefits from more explicit field guidance

### Warehouse & Delivery · `loading / shipment / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- location/task context benefits from more explicit field guidance

### Warehouse & Delivery · `weighing / shipment / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators
- location/task context benefits from more explicit field guidance

### Product Showcase · `showroom / product / wide / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Product Showcase · `showroom / product / medium / slide`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Product Showcase · `showroom / cabin / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- all production-facing slots will benefit from a public execution layer in future

### Product Showcase · `showroom / panel / detail / static`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- content may be clear internally but not instantly clear to field operators

### Product Showcase · `showroom / product / hero / orbit`

Recommended semantic fields:
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Why this slot benefits from semantic enrichment:
- hero usage needs editorial explanation for operators

---

## 5. Suggested next action

Recommended next implementation step:

1. Do **not** rename the whole SIGLEN plan yet.
2. Select a small first batch of slots and add human-friendly semantic fields.
3. Start with the most operator-sensitive groups, especially:
   - tower / testing
   - factory / inspection
   - loading / shipment
   - showroom / product / hero
4. Keep canonical tags stable while the user-facing layer is introduced.

Recommended first semantic pilot fields:

- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`

Recommended next file-change direction:

- either enrich `default.yaml` directly with semantic helper fields
- or create a first lightweight registry-linked semantic layer for a subset of SIGLEN slots
