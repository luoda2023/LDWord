# Scene Matrix Drilldown Projection Surface Reference Trace N2.428

## Purpose

N2.427 closed source-id projections by replaying explicit source fields. The
next stable value class is surface projections where source audit rows expose
fields named `runtime_surface_ids`, `ui_surface_ids`, or `report_surface_ids`.

N2.428 does not treat every value containing the word `surface` as a surface
registry member. Several projection profiles carry broader control, component,
OOXML, requirement, or trace tokens. This pass only audits source fields whose
names explicitly define runtime, UI, or report surfaces.

## Registry Scope

The surface projection map is assembled from:

- `scene_ambiguity_clarification_ui_audit.rows[*].ui_surface_ids`;
- `scene_external_handoff_contract_audit.rows[*].ui_surface_ids`;
- `scene_material_repair_flow_audit.rows[*].runtime_surface_ids`;
- `scene_material_repair_flow_audit.rows[*].ui_surface_ids`;
- `scene_fixed_layout_profile_audit.rows[*].runtime_surface_ids`;
- `scene_fixed_layout_profile_audit.rows[*].ui_surface_ids`;
- `scene_fixed_layout_profile_audit.rows[*].report_surface_ids`;
- `scene_report_artifact_drilldown_audit.rows[*].runtime_surface_ids`;
- `scene_report_artifact_drilldown_audit.rows[*].ui_surface_ids`;
- `scene_report_artifact_drilldown_audit.rows[*].report_surface_ids`;
- `scene_delivery_preset_execution_audit.rows[*].runtime_surface_ids`;
- `scene_delivery_preset_execution_audit.rows[*].ui_surface_ids`;
- `scene_delivery_preset_execution_audit.rows[*].report_surface_ids`.

The current source-field replay covers 98 row/field projection points and 209
unique runtime/UI/report surface values.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_surface_reference_map()` with cached source-field replay.
  - Audits both `action_behavior_ids` and `capability_ids` for expected surface
    projections.
  - Emits `missing_projection_surface_reference_id` when a source-declared
    runtime/UI/report surface is not projected into the matching drilldown row
    field.
  - Registers the projection surface-reference audit as source evidence.
  - Registers this N2.428 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the surface projection map.
  - Locks runtime rows and exported payload rows so every replayed surface id is
    projected.
  - Adds a negative audit fixture for `missing_projection_surface_reference_id`.
  - Updates source evidence readiness expectations to `83/83 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=83/83 ready`.

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
  registries and source-report field replay.
- Projected runtime/UI/report surface values covered by source-report field
  replay.

N2.428's historical source evidence readiness target is `83/83 ready`, with
`0 missing`. N2.429 later added explicit script/test/doc path field replay and
superseded the current target to `85/85 ready`.

## Boundary

N2.428 intentionally excludes broader profile token kinds such as
`scene_surface`, `control_semantic`, `shared_component`, `word_ooxml_touchpoint`,
`requirement_dimension`, `trace_id`, and report summary markers. Those values
need their own token-kind-specific registries.

The next safe value-level splits are likely:

- evidence ids against release and boundary evidence ledgers;
- summary markers and release-gate check ids against their own registries;
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
- `drilldown_sources=83/83 ready`
- `Source evidence: 83 / 83 ready (0 missing)`
- `missing_projection_surface_reference_id`
