# Pool Plan → Registry Consistency Check v1

Scope:

- `data/brands/siglen/pool_plans/default.yaml`
- `data/taxonomy/canonical_registry_v1.yaml`

---

## 1. Key alignment summary

- Plan slot count: **19**
- Registry entry count: **19**
- Shared keys: **19**
- Only in plan: **0**
- Only in registry: **0**

Result: all current SIGLEN pool-plan keys are represented in the registry.

---

## 2. registry_key linkage check

- registry_key matches canonical key: **19**
- registry_key mismatches: **0**

Result: every SIGLEN slot now carries a correct explicit `registry_key`.

---

## 3. Semantic field consistency

- Semantic matches: **19**
- Semantic drift: **0**

Result: semantic fields currently match between pool plan and registry for all shared entries.

---

## 4. Default operational field consistency

- Defaults matches: **19**
- Defaults drift: **0**

Result: defaults currently match between pool plan and registry for all shared entries.

---

## 5. Current interpretation

- The system now has two aligned representations of the same 19 SIGLEN slots.
- The pool plan remains the active execution source for UI/runtime.
- The registry is now a real seeded knowledge layer, but not yet the runtime source of truth.
- The new `registry_key` field creates an explicit connection between runtime slots and registry entries.
- Because semantic and defaults fields are still duplicated in both places, future drift is still possible unless responsibilities are clarified.

Current best interpretation:

- `default.yaml` is still the **runtime execution document**.
- `canonical_registry_v1.yaml` is now the **governed taxonomy / knowledge document**.
- `registry_key` is now the explicit bridge between them.

---

## 6. Recommended responsibility split (next phase)

### Keep in pool plan

- `topic` grouping
- `target`
- `priority`
- brand/plan-local execution overrides
- temporary duplicated transition fields while migration is still in progress

### Candidate to become registry-owned later

- canonical tuple: `scene/content/coverage/move`
- `human_label`
- `shoot_brief`
- `success_criteria`
- `fallback`
- `purpose`
- reusable default soft-tag patterns when globally stable

### Still runtime-owned for now

- upload state
- existing/missing counts
- current factory coverage
- plan-specific target counts

---

## 7. Suggested next move

Recommended next implementation step:

1. Keep runtime ownership unchanged for now.
2. Use `registry_key` as the first-class bridge field.
3. Let future UI or validation layers optionally hydrate semantic fields from registry first, then fall back to pool plan.
4. Delay full deduplication until that hydration path exists.

Practical next target:

- add a lightweight registry hydration helper in UI/runtime
- decide whether `human_label` and `shoot_brief` should prefer registry values first
