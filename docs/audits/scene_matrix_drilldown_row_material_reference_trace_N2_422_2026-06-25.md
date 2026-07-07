# Scene Matrix Drilldown Row Material Reference Trace N2.422

## Purpose

N2.421 left one explicit non-round gap: `SceneMatrixDrilldownRow.material_schema_ids` was named as a schema field, but the current drilldown rows use it for two material-facing references:

- MaterialSchema ids emitted by `scene_material_schema_audit`.
- Material repair and diagnostic signal ids emitted by `scene_material_repair_flow_audit`.

N2.422 keeps the payload-compatible field name and defines the audited meaning as `material_reference_ids`: the union of MaterialSchema registry/audit ids and MaterialRepairFlow material signal ids.

The release invariant is that every drilldown row `material_schema_ids` value must resolve to that material reference set. A value that is neither a known MaterialSchema id nor an audited repair/diagnostic signal id is a blocking drilldown issue.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_material_reference_ids()` as the shared row-level material reference set.
  - Reads schema ids from `list_material_schemas()` and `build_scene_material_schema_audit_report()`.
  - Reads repair/diagnostic signal ids from `build_scene_material_repair_flow_audit_report()`.
  - Emits `unknown_row_material_reference_id` when a row `material_schema_ids` value is outside the combined reference set.
  - Registers the material reference audit as source evidence.
  - Registers this N2.422 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime row `material_schema_ids` values against `material_reference_ids`.
  - Locks exported payload row `material_schema_ids` values against the same material reference set.
  - Adds a negative audit fixture for `unknown_row_material_reference_id`.
  - Updates source evidence readiness expectations to `71/71 ready` for the N2.422 historical snapshot.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=71/71 ready` for the N2.422 historical snapshot.

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
- Row material references covered by MaterialSchema registry/audit ids or MaterialRepairFlow material signal ids.
- Audit-level blocking issues for unknown row material reference ids.

N2.423 later added input/render/object-preflight/Word-risk row references, N2.424 added plugin/risk/maturity governance references, N2.425 added action/capability projection profiles, N2.426 added projection test-reference checks, N2.427 added projection source-reference checks, and N2.428 added projection surface-reference checks. The current source evidence readiness target is `83/83 ready`, with `0 missing`.

## Boundary

N2.422 does not rename `material_schema_ids` because downstream payload and UI projections may already depend on that key. The field remains payload-compatible, while the audit documents that it is currently a material-reference carrier rather than a pure schema-id-only field.

If a later schema migration is desired, it should introduce a separate `material_signal_ids` or `material_reference_ids` payload field with compatibility projection, then retire the overloaded name after UI and export consumers are updated.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with `6 passed`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with `7 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=71/71 ready`
- `Source evidence: 71 / 71 ready (0 missing)`
- `unknown_row_material_reference_id`
