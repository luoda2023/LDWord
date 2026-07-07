# Scene Matrix Drilldown Projection Control Runtime Reference Trace N2.434

## Purpose

N2.428 closed generic runtime/UI/report surface replay, but intentionally left
broader control-runtime token kinds out of scope. N2.434 closes that gap for
`scene_control_runtime_consistency_audit`: scene controls that must stay aligned
with template-management naming, grouping, units, disabled-state behavior, and
runtime consumers now have a dedicated projection replay guard.

This pass also fixes a visibility gap in the drilldown row itself. The source
audit already carried `template_surface_ids` and `runtime_consumer_ids`, but the
matrix row only exposed contracts, shared components, and scene surfaces. The
drilldown now exposes the template-side control surface and runtime write/consume
paths as first-class capability projections.

## Registry Scope

The control-runtime projection map is assembled from
`scene_control_runtime_consistency_audit.rows[*]`:

- `required_semantics` are replayed into `action_behavior_ids`;
- `contract_ids` are replayed into `capability_ids`;
- `shared_component_ids` are replayed into `capability_ids`;
- `scene_surface_ids` are replayed into `capability_ids`;
- `template_surface_ids` are replayed into `capability_ids`;
- `runtime_consumer_ids` are replayed into `capability_ids`.

The current control-runtime replay covers 24 row/field projection points and
158 unique control-runtime reference values across 12 source rows.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_control_runtime_reference_map()` with cached source-field
    replay.
  - Extends the `control_runtime_consistency` projection profile to include
    `template_surface_ids` and `runtime_consumer_ids`.
  - Extends `_control_runtime_consistency_item()` so each row capability also
    exposes template surfaces and runtime consumer paths.
  - Emits `missing_projection_control_runtime_reference_id` when a
    source-declared control-runtime value is not projected into the matching
    drilldown row field.
  - Registers the control-runtime projection audit as source evidence.
  - Registers this N2.434 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the control-runtime projection map.
  - Locks runtime rows and exported payload rows so every replayed
    control-runtime reference is projected.
  - Adds concrete assertions for paragraph indent and special-indent chains:
    scene control, template control, and runtime style paths must be visible in
    the matrix row.
  - Adds a negative audit fixture for
    `missing_projection_control_runtime_reference_id`.
  - Updates source evidence readiness expectations to `95/95 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=95/95 ready`.

## Acceptance View

The drilldown visible-reference contract now covers:

- Unique source evidence ids.
- Unique drilldown item ids.
- Unique row ids inside each drilldown.
- Item source ids covered by source evidence.
- Row source ids covered by source evidence.
- Row source ids aligned with parent item source ids.
- Row registry references for packs, families, request cells, fixtures, count
  profiles, delivery presets, materials, input sources, render sources, object
  preflight targets, Word risk surfaces, plugin gates, risk domains, and
  maturity gap domains.
- Row action/capability projections covered by source-aware projection profiles.
- Projected `test_*` values covered by source audit `test_ids`.
- Projected source-id values covered by dashboard/release/drilldown source
  registries and source-report field replay.
- Projected runtime/UI/report surface values covered by source-report field
  replay.
- Projected release script/test/doc paths covered by source-report field replay
  and repository file existence checks.
- Projected boundary/release evidence ids covered by source-report
  `evidence_ids` field replay.
- Projected release gate, dashboard card, drilldown, and summary markers
  covered by release projection/closure field replay.
- Projected release-stage and release trace/link ids covered by source-report
  release-chain field replay.
- Projected retained-gap exit contracts, release conditions, gap identities,
  exit signals, and prohibited core claims covered by retained-gap exit field
  replay.
- Projected control-runtime semantics, control contracts, shared components,
  scene surfaces, template surfaces, and runtime consumers covered by
  control-runtime field replay.

N2.434 set the source evidence readiness target to `95/95 ready`, with
`0 missing`. N2.435 subsequently superseded the current target to
`97/97 ready` by adding release metric reference replay.

## Boundary

N2.434 verifies projection presence and visibility for control-runtime
references. It does not duplicate the semantic validation already owned by
`scene_control_runtime_consistency_audit` and `control_contract_registry`.
Those source layers continue to prove that contract ids exist, evidence markers
resolve, and each control group has a scene-facing surface.

This layer specifically protects the scene matrix drilldown from losing that
source-owned control chain after it is built: scene control surface, template
control surface, shared component, and runtime consumer all remain visible in
the matrix/export/release path.

The next safe value-level splits are likely:

- external handoff contract ids against the external handoff contract source
  ledger, beyond projection presence;
- report artifact and delivery output markers against their owning report
  payload schemas.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=95/95 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=95/95 ready`
- `Source evidence: 95 / 95 ready (0 missing)`
- `missing_projection_control_runtime_reference_id`
