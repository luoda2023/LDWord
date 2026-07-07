# Scene Matrix Drilldown Projection Source Reference Trace N2.427

## Purpose

N2.426 closed stable `test_*` value references inside mixed
`action_behavior_ids` and `capability_ids`. The next stable projection class is
source-id references: values that are explicitly projected from source audit
fields such as `source_ids`, `surface_source_id`, `audit_source_id`, or
`source_id`.

N2.427 does not infer source ids from every `scene_*` token. Some `scene_*`
values are UI surfaces, requirement dimensions, sample fixture surfaces, or
trace ids. Instead, this pass replays the authoritative source fields for rows
where the drilldown builder deliberately projects source references.

## Registry Scope

The source-id registry is assembled from:

- `SCENE_MATRIX_DASHBOARD_SOURCE_IDS`;
- `SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID`;
- current drilldown source evidence ids;
- current drilldown item source ids.

The source-reference projection map is assembled from:

- `scene_terminal_release_exception_audit.rows[*].source_ids`;
- `scene_non_subject_release_trace_attribution_audit.rows[*].surface_source_id`;
- `scene_release_projection_surface_parity_audit.rows[*].audit_source_id`;
- `scene_release_closure_ledger_audit.rows[*].source_id`;
- `scene_release_acceptance_certificate_audit.rows[*].source_id`;
- `scene_release_acceptance_certificate_audit.requirement_dimension_rows[*].source_ids`.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_source_reference_ids()` to build the allowed source-id
    registry without importing release-gate scripts.
  - Adds `_projection_source_reference_map()` to replay source-report fields by
    `(drilldown_id, row_id, field_name)`.
  - Emits `unknown_projection_source_reference_id` when a replayed source id is
    absent from the dashboard/release/drilldown registry.
  - Emits `missing_projection_source_reference_id` when a replayed source id is
    not present in the corresponding drilldown row projection field.
  - Registers the projection source-reference audit as source evidence.
  - Registers this N2.427 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the source-id registry and source-reference map.
  - Locks runtime rows and exported payload rows so every replayed source id is
    registered and projected.
  - Adds a negative audit fixture for `missing_projection_source_reference_id`.
  - Updates source evidence readiness expectations to `81/81 ready` for the
    N2.427 historical snapshot.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=81/81 ready` for the N2.427 historical snapshot.

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
- Row delivery references covered by DeliveryPreset or delivery execution
  output-signal evidence.
- Row material references covered by MaterialSchema registry/audit ids or
  MaterialRepairFlow material signal ids.
- Row input sources covered by InputSource audit evidence.
- Row render sources covered by InputSource render/template evidence.
- Row object preflight targets covered by ObjectPreflight action evidence.
- Row Word risk surfaces covered by Word risk, ObjectPreflight, or fixed-layout
  evidence.
- Row plugin/manual gate ids covered by the PluginManualGate registry.
- Row risk domain ids covered by registered PluginManualGate risk domains.
- Row maturity gap references covered by product maturity domains or retained
  boundary gap evidence.
- Row action/capability projections covered by source-aware projection profiles.
- Projected `test_*` values covered by source audit `test_ids`.
- Projected source-id values covered by dashboard/release/drilldown source
  registries and by source-report field replay.

N2.428 later added projected runtime/UI/report surface field-replay checks and
superseded the current source evidence readiness target to `83/83 ready`, with
`0 missing`. Treat the `81/81` entries below as the historical verification
snapshot for N2.427; use the latest Release Gate output and N2.428 for the
current total.

## Boundary

N2.427 intentionally audits only source ids whose origin field is explicit.
It does not treat every `scene_*` value as a source id because the mixed
projection fields also carry UI surfaces, requirement dimensions, sample fixture
surfaces, trace ids, and other domain tokens.

The next safe value-level splits remain:

- path-like values against script/test/doc path evidence;
- evidence ids against release and boundary evidence ledgers;
- summary markers and release-gate check ids against their own registries.
- control/runtime scene surfaces against control contract and UI registries.

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
- `drilldown_sources=81/81 ready`
- `Source evidence: 81 / 81 ready (0 missing)`
- `missing_projection_source_reference_id`
- `unknown_projection_source_reference_id`
