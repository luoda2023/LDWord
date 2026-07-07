# Scene Matrix Drilldown Projection Release Link Trace N2.432

## Purpose

N2.431 closed release marker projection. N2.432 closes structured release-link
projection: upstream stages, release traces, readiness rows, release envelopes,
exit criteria, and receipt alignment ids that source audits already expose as
typed tuple fields.

This pass does not infer trace or stage ids from free text. It only replays
explicit release-chain fields such as `upstream_stage_ids`, `source_trace_ids`,
`terminal_exception_ids`, `readiness_row_ids`, `terminal_trace_ids`,
`dossier_trace_ids`, `release_envelope_ids`,
`retained_gap_exit_criteria_ids`, and `retained_gap_receipt_alignment_ids`.

## Registry Scope

The release link projection map is assembled from:

- `scene_terminal_release_exception_audit.rows[*].source_trace_ids`;
- `scene_boundary_subject_release_dossier_audit.rows[*].terminal_exception_ids`;
- `scene_boundary_subject_release_dossier_audit.rows[*].readiness_reconciliation_row_ids`;
- `scene_boundary_subject_release_dossier_audit.rows[*].release_exception_trace_ids`;
- `scene_non_subject_release_trace_attribution_audit.rows[*].terminal_exception_id`;
- `scene_non_subject_release_trace_attribution_audit.rows[*].source_trace_id`;
- `scene_release_trace_partition_guard_audit.rows[*].trace_ids`;
- `scene_boundary_subject_release_continuity_audit.rows[*].readiness_row_ids`;
- `scene_boundary_subject_release_continuity_audit.rows[*].terminal_trace_ids`;
- `scene_boundary_subject_release_continuity_audit.rows[*].dossier_trace_ids`;
- `scene_release_closure_ledger_audit.rows[*].upstream_stage_ids`;
- `scene_boundary_maturity_release_envelope_audit.rows[*].readiness_row_ids`;
- `scene_boundary_maturity_release_envelope_audit.rows[*].terminal_trace_ids`;
- `scene_boundary_maturity_release_envelope_audit.rows[*].dossier_trace_ids`;
- `scene_retained_gap_exit_criteria_audit.rows[*].release_envelope_id`;
- `scene_release_residual_ratio_ledger_audit.rows[*].terminal_exception_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].readiness_reconciliation_row_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].release_envelope_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].retained_gap_exit_criteria_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].retained_gap_receipt_alignment_ids`.

The current release link replay covers 76 row/field projection points and 104
unique release link values.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_release_link_reference_map()` with cached source-field
    replay.
  - Audits action-field links such as terminal exception ids and retained-gap
    release envelope ids.
  - Audits capability-field links such as source traces, readiness rows,
    upstream release stages, release envelopes, exit criteria, and receipt
    alignment ids.
  - Emits `missing_projection_release_link_reference_id` when a source-declared
    release-chain link is not projected into the matching drilldown row field.
  - Registers the projection release-link audit as source evidence.
  - Registers this N2.432 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the release link projection map.
  - Locks runtime rows and exported payload rows so every replayed link is
    projected.
  - Adds a negative audit fixture for
    `missing_projection_release_link_reference_id`.
  - Updates source evidence readiness expectations to `91/91 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=91/91 ready`.

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
- Projected release-stage and release trace/link ids covered by source-report
  release-chain field replay.

N2.432 set the source evidence readiness target to `91/91 ready`, with
`0 missing`. N2.433 subsequently superseded the current target to `93/93 ready`
by adding retained-gap exit reference replay.

## Boundary

N2.432 intentionally does not validate that every release-chain id points to a
row in its owning source ledger. The owning source audits and Release Gate
continue to enforce semantic validity and counts. This layer verifies that once
those audits declare structured release-link fields, the scene matrix drilldown
does not silently drop them.

The next safe value-level splits are likely:

- control/runtime scene surfaces against control contract and UI registries;
- source-specific metric strings such as receipt and ratio markers against
  their owning release reports;
- external handoff contract ids against their owning source ledger beyond
  projection presence.

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
- `drilldown_sources=91/91 ready`
- `Source evidence: 91 / 91 ready (0 missing)`
- `missing_projection_release_link_reference_id`
