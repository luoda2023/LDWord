# Scene Matrix Drilldown Projection Evidence Reference Trace N2.430

## Purpose

N2.429 closed explicit script/test/doc path projections. N2.430 closes the next
explicit value class: source-report `evidence_ids` that must remain visible in
the scene matrix drilldown.

The goal is not to classify every arbitrary capability token as evidence. Many
tokens in `action_behavior_ids` and `capability_ids` are trace ids, status
values, profile ids, paths, summary markers, or domain labels. This pass only
replays fields explicitly named `evidence_ids` from the boundary and release
audits whose projection profiles declare `evidence_id` token semantics.

## Registry Scope

The evidence projection map is assembled from:

- `scene_boundary_guarded_completion_audit.rows[*].evidence_ids`;
- `scene_residual_warning_governance_audit.rows[*].evidence_ids`;
- `scene_boundary_readiness_reconciliation_audit.rows[*].evidence_ids`;
- `scene_terminal_release_exception_audit.rows[*].evidence_ids`;
- `scene_boundary_subject_release_dossier_audit.rows[*].evidence_ids`;
- `scene_non_subject_release_trace_attribution_audit.rows[*].evidence_ids`;
- `scene_release_trace_partition_guard_audit.rows[*].evidence_ids`;
- `scene_release_projection_surface_parity_audit.rows[*].evidence_ids`;
- `scene_boundary_subject_release_continuity_audit.rows[*].evidence_ids`;
- `scene_release_closure_ledger_audit.rows[*].evidence_ids`;
- `scene_boundary_maturity_release_envelope_audit.rows[*].evidence_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].evidence_ids`;
- `scene_release_acceptance_certificate_audit.rows[*].evidence_ids`;
- `scene_release_acceptance_certificate_audit.requirement_dimension_rows[*].evidence_ids`.

The current evidence replay covers 120 row/field projection points and 106
unique source evidence-id values.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_evidence_reference_map()` with cached source-field replay.
  - Preserves the special `boundary_guarded_completion` placement where
    source `evidence_ids` are projected through `action_behavior_ids`.
  - Audits the remaining boundary/release evidence rows through
    `capability_ids`.
  - Emits `missing_projection_evidence_reference_id` when a source-declared
    evidence id is not projected into the matching drilldown row field.
  - Registers the projection evidence-reference audit as source evidence.
  - Registers this N2.430 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the evidence projection map.
  - Locks runtime rows and exported payload rows so every replayed evidence id
    is projected.
  - Adds a negative audit fixture for
    `missing_projection_evidence_reference_id`.
  - Updates source evidence readiness expectations to `87/87 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=87/87 ready`.

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

N2.430's historical source evidence readiness target is `87/87 ready`, with
`0 missing`. N2.431 later added explicit release gate, dashboard card,
drilldown, and summary marker field replay and superseded the current target
to `89/89 ready`.

## Boundary

N2.430 intentionally excludes arbitrary strings that merely look
evidence-related. It does not infer evidence ids from labels, summaries,
details, paths, receipt metrics, source ids, or trace ids. It also does not
re-validate each source audit's own evidence ledger semantics; those remain
owned by the source audits and the Release Gate. This layer verifies that once
the source audit declares `evidence_ids`, the scene matrix drilldown does not
drop them.

The next safe value-level splits are likely:

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
- `drilldown_sources=87/87 ready`
- `Source evidence: 87 / 87 ready (0 missing)`
- `missing_projection_evidence_reference_id`
