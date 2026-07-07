# Scene Matrix Drilldown Row Count Delivery Registry Trace N2.421

## Purpose

N2.420 made request-cell and fixture references traceable to their sample registries. The next execution-facing row reference surface is `count_profile_ids` and `delivery_preset_ids`: these fields connect a drilldown row to counting behavior and output delivery behavior.

`count_profile_ids` is a pure registry reference and must resolve to the CountProfile registry. `delivery_preset_ids` is historical naming: in the drilldown rows it includes both business `DeliveryPreset` ids and delivery execution output-signal ids. N2.421 therefore treats it as a delivery reference set and verifies it against the union of DeliveryPreset audit ids and DeliveryPreset execution required output signals.

N2.421 closes the row count/delivery registry trace gap.

The release invariant is that every drilldown row `count_profile_ids` value is present in the CountProfile registry, and every row `delivery_preset_ids` value is present in the DeliveryPreset audit or delivery execution output-signal registry.

## Current Lineage

N2.421 is the historical `69/69 ready` snapshot for count/delivery references. N2.422 resolves the material-schema note below by treating row `material_schema_ids` as `material_reference_ids`. N2.423 adds input/render/object-preflight/Word-risk row references. N2.424 adds plugin/risk/maturity governance references. N2.425 adds action/capability projection profiles. N2.426 adds projection test-reference checks. N2.427 adds projection source-reference checks. N2.428 adds projection surface-reference checks, raising the current source evidence readiness to `83/83 ready`.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - `audit_scene_matrix_drilldown_report()` now reads count profile ids from `list_count_profiles()`.
  - The audit builds delivery reference ids from `build_scene_delivery_preset_audit_report()` and `build_scene_delivery_preset_execution_audit_report()`.
  - The audit emits `unknown_row_count_profile_id` when a row references a count profile outside the registry.
  - The audit emits `unknown_row_delivery_reference_id` when a row references a delivery preset or output signal outside the delivery evidence set.
  - Registers the count/delivery registry audit as source evidence.
  - Registers this N2.421 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime row count profile ids as a subset of the CountProfile registry.
  - Locks runtime row delivery ids as a subset of the delivery reference set.
  - Locks exported payload row count/delivery ids against the same registries.
  - Builds an unknown count/delivery report and verifies the audit returns `unknown_row_count_profile_id` and `unknown_row_delivery_reference_id`.
  - Updates source evidence readiness expectations to `69/69 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=69/69 ready`.

## Acceptance View

The drilldown visible-reference contract now covers:

- Unique source evidence ids.
- Unique drilldown item ids.
- Unique row ids inside each drilldown.
- Item source ids covered by source evidence.
- Row source ids covered by source evidence.
- Row source ids aligned with parent item source ids.
- Row pack ids covered by the scene coverage pack registry.
- Row family ids covered by the planned scene family registry.
- Row request cell ids covered by the request-cell fixture registry.
- Row fixture ids covered by the scene sample fixture registry.
- Row count profile ids covered by the CountProfile registry.
- Row delivery references covered by DeliveryPreset or delivery execution output-signal evidence.
- Audit-level blocking issues for unknown row count profile or delivery reference ids.

Current source evidence readiness is `69/69 ready`, with `0 missing`.

## Material Schema Note

`material_schema_ids` was not hardened in N2.421 because current drilldown rows use that field for both material schema ids and material repair/diagnostic signal ids. N2.422 resolves this by keeping the payload-compatible field name and auditing it against a combined material reference set.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with `7 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=69/69 ready`
- `Source evidence: 69 / 69 ready (0 missing)`
- `unknown_row_count_profile_id`
- `unknown_row_delivery_reference_id`
