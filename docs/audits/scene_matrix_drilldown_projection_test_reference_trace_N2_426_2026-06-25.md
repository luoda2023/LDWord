# Scene Matrix Drilldown Projection Test Reference Trace N2.426

## Purpose

N2.425 added source-aware projection profiles for mixed `action_behavior_ids` and
`capability_ids`. That closed the provenance layer, but the value layer still had
one stable class that could be audited without overfitting the mixed projection
field: `test_*` references.

N2.426 therefore treats projected test references as a blocking registry-backed
contract. Any `action_behavior_ids` or `capability_ids` value that starts with
`test_` must resolve to a real `test_ids` value emitted by the source audit rows
that currently project test references into the drilldown.

## Registry Scope

The authoritative `test_ids` registry for this pass is assembled from:

- `scene_material_repair_flow_audit`
- `scene_fixed_layout_profile_audit`
- `scene_report_artifact_drilldown_audit`
- `scene_delivery_preset_execution_audit`

The current drilldown data contains 65 projected `test_*` references and 71
registered source `test_ids`; all 65 projected references resolve.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_test_reference_ids()` from the four source audit reports.
  - Audits both `action_behavior_ids` and `capability_ids` for values beginning
    with `test_`.
  - Emits `unknown_projection_test_reference_id` when a projected test id is not
    registered in source audit `test_ids`.
  - Registers the projection test-reference audit as source evidence.
  - Registers this N2.426 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime row `test_*` projection values against the mirrored source
    `test_ids` registry.
  - Locks exported payload `test_*` projection values against the same registry.
  - Adds a negative audit fixture for `unknown_projection_test_reference_id`.
  - Updates source evidence readiness expectations to `79/79 ready` for the
    N2.426 historical snapshot.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=79/79 ready` for the N2.426 historical snapshot.

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

N2.427 later added projected source-id field-replay checks, and N2.428 added
projected runtime/UI/report surface field-replay checks. Together they
supersede the current source evidence readiness target to `83/83 ready`, with
`0 missing`.
Treat the `79/79` entries below as the historical verification snapshot for
N2.426; use the latest Release Gate output and N2.428 for the current total.

## Boundary

N2.426 intentionally audits only projected test references. Other
`action_behavior_ids` and `capability_ids` values still include statuses,
behavior labels, source ids, UI surfaces, report surfaces, OOXML tags, evidence
ids, paths, payload keys, and derived receipt markers. Those should continue to
be split by stable token kind before adding blocking value-level registries.

The next safe value-level splits are likely:

- UI surface ids against source-specific UI surface registries;
- report surface ids against report/export surface registries;
- path-like values against script/test/doc path evidence;
- evidence ids against release and boundary evidence ledgers.
- summary markers and release-gate check ids against their own registries.

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
- `drilldown_sources=79/79 ready`
- `Source evidence: 79 / 79 ready (0 missing)`
- `unknown_projection_test_reference_id`
