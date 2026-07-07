# Scene Matrix Drilldown Projection Path Reference Trace N2.429

## Purpose

N2.428 closed runtime/UI/report surface projections. N2.429 closes the next
explicit value class: release script, test, and closure-document paths that are
declared by release audit rows and projected into the scene matrix drilldown.

The goal is not to infer paths from arbitrary strings. This pass only trusts
source fields that are explicitly typed as path-bearing release evidence:
`export_script_path`, `test_path`, `closure_doc_path`, and
`supplemental_closure_doc_paths`.

## Registry Scope

The path projection map is assembled from:

- `scene_release_projection_surface_parity_audit.rows[*].export_script_path`;
- `scene_release_projection_surface_parity_audit.rows[*].test_path`;
- `scene_release_projection_surface_parity_audit.rows[*].closure_doc_path`;
- `scene_release_projection_surface_parity_audit.rows[*].supplemental_closure_doc_paths`;
- `scene_release_closure_ledger_audit.rows[*].export_script_path`;
- `scene_release_closure_ledger_audit.rows[*].test_path`;
- `scene_release_closure_ledger_audit.rows[*].closure_doc_path`;
- `scene_release_closure_ledger_audit.rows[*].supplemental_closure_doc_paths`.

The current path replay covers 26 row/field projection points and 44 unique
script/test/doc paths. All 44 files exist in the repository.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_path_reference_map()` with cached source-field replay.
  - Projects supplemental closure documents into `release_projection_surface_parity`
    and `release_closure_ledger` row `capability_ids`.
  - Audits both path projection presence and file existence for the matched
    drilldown row field.
  - Emits `missing_projection_path_reference_id` when a source-declared
    script/test/doc path is not projected into the matching drilldown row field.
  - Emits `missing_projection_path_file` when a projected script/test/doc path
    does not exist in the repository.
  - Registers the projection path-reference audit as source evidence.
  - Registers this N2.429 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the path projection map.
  - Locks runtime rows and exported payload rows so every replayed path id is
    projected.
  - Verifies every replayed path resolves to an existing repository file.
  - Adds a negative audit fixture for `missing_projection_path_reference_id`.
  - Updates source evidence readiness expectations to `85/85 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=85/85 ready`.

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

N2.429's historical source evidence readiness target is `85/85 ready`, with
`0 missing`. N2.430 later added explicit boundary/release `evidence_ids` field
replay and superseded the current target to `87/87 ready`.

## Boundary

N2.429 intentionally excludes path-like values that are not declared by explicit
release path fields. It also does not validate path semantics beyond repository
existence; for example, it does not execute export scripts or inspect closure
document content. Those behaviors remain owned by their source audits and the
Release Gate.

The next safe value-level splits are likely:

- summary markers and release-gate check ids against their own registries;
- control/runtime scene surfaces against control contract and UI registries;
- source-specific metric strings such as receipt and ratio markers against
  their owning release reports.

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
- `drilldown_sources=85/85 ready`
- `Source evidence: 85 / 85 ready (0 missing)`
- `missing_projection_path_reference_id`
- `missing_projection_path_file`
