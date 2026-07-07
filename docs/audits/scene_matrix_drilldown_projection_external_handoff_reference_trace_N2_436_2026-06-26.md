# Scene Matrix Drilldown Projection External Handoff Reference Trace N2.436

## Purpose

N2.435 closed release metric replay. N2.436 closes the next handoff-ledger gap:
external handoff contract ids must not only appear in source audits; every
matrix projection that references them must point back to
`scene_external_handoff_contract_audit.rows[*].contract_id`.

This pass also fixes a visibility gap in `boundary_subject_release_dossier`.
The source row already counted `external_handoff_contract_ids`, but the
drilldown row only exposed the count in `detail`. The actual contract ids now
project into `capability_ids`, making them searchable/exportable and protected
by the same ledger replay.

## Registry Scope

The external handoff ledger is assembled from
`scene_external_handoff_contract_audit.rows[*].contract_id`.

The projection replay is assembled from:

- `scene_boundary_guarded_completion_audit.rows[*].external_handoff_contract_ids`;
- `scene_boundary_subject_release_dossier_audit.rows[*].external_handoff_contract_ids`;
- `scene_boundary_maturity_release_envelope_audit.rows[*].external_handoff_contract_id`;
- `scene_retained_gap_exit_criteria_audit.rows[*].external_handoff_contract_id`.

The current external handoff replay covers 24 row/field projection points and 6
unique external handoff contract ids. All 6 ids resolve to the external handoff
contract ledger.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_external_handoff_contract_reference_ids()` as the authoritative
    drilldown-side ledger set.
  - Adds `_projection_external_handoff_contract_reference_map()` with cached
    source-field replay.
  - Extends the `boundary_subject_release_dossier` projection profile to
    include `external_handoff_contract_ids`.
  - Extends `_boundary_subject_release_dossier_item()` so each row capability
    exposes external handoff contract ids.
  - Emits `unknown_projection_external_handoff_contract_reference_id` when a
    source-declared handoff id is absent from the external handoff ledger.
  - Emits `missing_projection_external_handoff_contract_reference_id` when a
    source-declared handoff id is not projected into the matching drilldown row
    field.
  - Registers the external handoff projection audit as source evidence.
  - Registers this N2.436 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the external handoff ledger and projection map.
  - Locks runtime rows and exported payload rows so every replayed handoff id is
    both ledger-known and projected.
  - Adds a concrete visibility assertion for
    `boundary_subject_release_dossier`.
  - Adds a negative audit fixture for
    `missing_projection_external_handoff_contract_reference_id`.
  - Updates source evidence readiness expectations to `99/99 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=99/99 ready`.

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
- Projected release metric strings covered by residual ratio and residual
  explanation source-report field replay.
- Projected external handoff contract ids covered by the external handoff
  contract ledger and source-report field replay.

Current source evidence readiness target for N2.436 was `99/99 ready`, with
`0 missing`. N2.437 supersedes the active target to `101/101 ready` by adding
report/delivery output-marker replay.

## Boundary

N2.436 verifies that external handoff contract references are visible in the
matrix and resolve to the external handoff ledger. It does not duplicate the
semantic readiness checks owned by `scene_external_handoff_contract_audit`,
`scene_boundary_guarded_completion_audit`,
`scene_boundary_maturity_release_envelope_audit`, or
`scene_retained_gap_exit_criteria_audit`.

N2.436 also does not infer handoff ids from labels, target plugin ids, or
natural-language detail strings. Only typed `external_handoff_contract_id(s)`
fields participate in this replay.

The report artifact and delivery output marker split is now closed by N2.437.
The next safe value-level splits are likely:

- acceptance certificate requirement dimension strings against the acceptance
  certificate source report;
- target plugin ids against the plugin/manual gate or handoff ledger where a
  stable target-plugin registry exists.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=99/99 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=99/99 ready`
- `Source evidence: 99 / 99 ready (0 missing)`
- `missing_projection_external_handoff_contract_reference_id`
- `unknown_projection_external_handoff_contract_reference_id`
