# Scene Matrix Drilldown Projection Release Marker Trace N2.431

## Purpose

N2.430 closed boundary/release `evidence_ids` projection. N2.431 closes the
release marker layer that binds release-gate checks, dashboard cards,
drilldown ids, and summary markers into the scene matrix drilldown.

This pass does not infer markers from arbitrary text. It only replays explicit
release projection fields: `release_gate_check_id`, `dashboard_card_id`,
`drilldown_id`, and `summary_marker`.

## Registry Scope

The release marker projection map is assembled from:

- `scene_release_projection_surface_parity_audit.rows[*].release_gate_check_id`;
- `scene_release_projection_surface_parity_audit.rows[*].dashboard_card_id`;
- `scene_release_projection_surface_parity_audit.rows[*].drilldown_id`;
- `scene_release_projection_surface_parity_audit.rows[*].summary_marker`;
- `scene_release_closure_ledger_audit.rows[*].release_gate_check_id`;
- `scene_release_closure_ledger_audit.rows[*].dashboard_card_id`;
- `scene_release_closure_ledger_audit.rows[*].drilldown_id`;
- `scene_release_closure_ledger_audit.rows[*].summary_marker`.

The current release marker replay covers 39 row/field projection points and 48
unique release marker values.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_release_marker_reference_map()` with cached source-field
    replay.
  - Audits `release_projection_surface_parity` action markers for release gate,
    dashboard card, and target drilldown ids.
  - Audits `release_projection_surface_parity` capability markers for summary
    projection labels.
  - Audits `release_closure_ledger` action markers for release gate, dashboard
    card, target drilldown, and summary markers.
  - Emits `missing_projection_release_marker_reference_id` when a source-declared
    release marker is not projected into the matching drilldown row field.
  - Registers the projection release-marker audit as source evidence.
  - Registers this N2.431 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the release marker projection map.
  - Locks runtime rows and exported payload rows so every replayed marker is
    projected.
  - Adds a negative audit fixture for
    `missing_projection_release_marker_reference_id`.
  - Updates source evidence readiness expectations to `89/89 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=89/89 ready`.

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
- Projected release script/test/doc paths covered by source-report field replay
  and repository file existence checks.
- Projected boundary/release evidence ids covered by source-report
  `evidence_ids` field replay.
- Projected release gate, dashboard card, drilldown, and summary markers
  covered by release projection/closure field replay.

N2.431's historical source evidence readiness target is `89/89 ready`, with
`0 missing`. N2.432 later added explicit release-stage and release trace/link
field replay and superseded the current target to `91/91 ready`.

## Boundary

N2.431 intentionally does not re-parse the release gate script, dashboard card
definitions, or summary text. The source audits still own semantic validation
that those markers exist in their target surfaces. This layer verifies that
once the source audit declares a release marker, the scene matrix drilldown
does not drop it from the projected action/capability field.

The next safe value-level splits are likely:

- control/runtime scene surfaces against control contract and UI registries;
- source-specific metric strings such as receipt and ratio markers against
  their owning release reports;
- handoff and release-condition ids against their source ledgers.

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
- `drilldown_sources=89/89 ready`
- `Source evidence: 89 / 89 ready (0 missing)`
- `missing_projection_release_marker_reference_id`
