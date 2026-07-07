# Scene Matrix Drilldown Projection Release Metric Reference Trace N2.435

## Purpose

N2.434 closed control-runtime reference replay. N2.435 closes the next
source-specific metric-string gap: release metrics that look like compact
summary text, but are actually governed by release reports, must be replayed
from their owning source rows into the scene matrix drilldown.

This pass does not treat every string containing `=` as a metric registry
member. It only covers release-owned metric strings whose source reports already
declare the governing fields:

- residual ratio receipt metrics derived from
  `scene_release_residual_ratio_ledger_audit`;
- residual explanation summary markers declared by
  `scene_release_residual_explanation_audit`.

## Registry Scope

The release metric projection map is assembled from:

- `scene_release_residual_ratio_ledger_audit.rows[*].retained_gap_receipt_alignment_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].retained_gap_exit_criteria_ids`;
- `scene_release_residual_ratio_ledger_audit.rows[*].ratio_id`;
- `scene_release_residual_explanation_audit.rows[*].summary_marker`.

For residual ratio rows, the metric replay derives:

- `receipt_alignments={receipt_count}/{exit_criteria_count}`;
- `count_delivery_receipts={receipt_count}/{exit_criteria_count}` for
  `count_profiles` and `delivery_families`;
- `maturity_l5_receipts={receipt_count}/{exit_criteria_count}` for
  `maturity_l5_blocked`.

For residual explanation rows, the metric replay projects the exact
`summary_marker` string into `action_behavior_ids`.

The current release metric replay covers 17 row/field projection points and 18
unique release metric reference values.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_release_metric_reference_map()` with cached source-field
    replay.
  - Replays residual ratio receipt metrics from retained-gap receipt/exit
    criteria counts.
  - Replays residual explanation `summary_marker` values.
  - Emits `missing_projection_release_metric_reference_id` when a source-owned
    release metric is not projected into the matching drilldown row field.
  - Registers the release metric projection audit as source evidence.
  - Registers this N2.435 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the release metric projection map with an independent receipt metric
    derivation helper.
  - Locks runtime rows and exported payload rows so every replayed release
    metric is projected.
  - Adds a negative audit fixture for
    `missing_projection_release_metric_reference_id`.
  - Updates source evidence readiness expectations to `97/97 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=97/97 ready`.

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

N2.435 set the source evidence readiness target to `97/97 ready`, with
`0 missing`. N2.436 subsequently superseded the current target to
`99/99 ready` by adding external handoff contract ledger replay.

## Boundary

N2.435 verifies projection presence for release-owned metric strings. It does
not duplicate semantic count validation owned by
`scene_release_residual_ratio_ledger_audit`,
`scene_release_residual_explanation_audit`, the dashboard, and the Release Gate.
Those owning reports continue to prove whether the counts are correct and
publishable.

N2.435 intentionally does not include arbitrary detail strings, UI labels, or
other values that merely contain `=`. Future metric splits should name the
owning source report and source fields before adding a replay guard.

The next safe value-level splits are likely:

- report artifact and delivery output markers against their owning report
  payload schemas;
- acceptance certificate requirement dimension strings against the acceptance
  certificate source report.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=97/97 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=97/97 ready`
- `Source evidence: 97 / 97 ready (0 missing)`
- `missing_projection_release_metric_reference_id`
