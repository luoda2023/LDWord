# Scene Matrix Drilldown Projection Retained Gap Exit Reference Trace N2.433

## Purpose

N2.432 closed the retained-gap `release_envelope_id` as part of the broader
release-link replay. N2.433 closes the next retained-gap exit gap: the same
source rows also expose external handoff contracts, release conditions, exit
signals, and prohibited core claims, but those fields did not yet have a
dedicated projection replay guard.

This pass makes the retained-gap exit criteria visible as an independently
audited matrix projection contract. It ensures the scene matrix drilldown cannot
silently drop a source-declared handoff/condition/signal/claim value from the
matching action or capability field.

## Registry Scope

The retained-gap exit projection map is assembled from
`scene_retained_gap_exit_criteria_audit.rows[*]`:

- `external_handoff_contract_id` is replayed into `action_behavior_ids`;
- `release_condition_ids` are replayed into `action_behavior_ids`;
- `gap_id` is replayed into `capability_ids`;
- `exit_signal_ids` are replayed into `capability_ids`;
- `prohibited_core_claim_ids` are replayed into `capability_ids`.

The current retained-gap exit replay covers 12 row/field projection points and
46 unique retained-gap exit reference values across 6 source rows.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_retained_gap_exit_reference_map()` with cached
    source-field replay.
  - Replays retained-gap exit action references from
    `external_handoff_contract_id` and `release_condition_ids`.
  - Replays retained-gap exit capability references from `gap_id`,
    `exit_signal_ids`, and `prohibited_core_claim_ids`.
  - Emits `missing_projection_retained_gap_exit_reference_id` when a
    source-declared retained-gap exit value is not projected into the matching
    drilldown row field.
  - Registers the retained-gap exit projection audit as source evidence.
  - Registers this N2.433 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the retained-gap exit projection map.
  - Locks runtime rows and exported payload rows so every replayed retained-gap
    exit reference is projected.
  - Adds a negative audit fixture for
    `missing_projection_retained_gap_exit_reference_id`.
  - Updates source evidence readiness expectations to `93/93 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=93/93 ready`.

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

N2.433 set the source evidence readiness target to `93/93 ready`, with
`0 missing`. N2.434 subsequently superseded the current target to
`95/95 ready` by adding control-runtime reference replay.

## Boundary

N2.433 does not validate that every retained-gap exit reference is semantically
valid in its owning source ledger. The retained-gap exit audit, external
handoff contract audit, boundary release envelope audit, and Release Gate remain
responsible for semantic validity and counts. This layer verifies that once the
source audit declares structured retained-gap exit fields, the scene matrix
drilldown does not silently drop them.

N2.433 also intentionally leaves `release_envelope_id` under the N2.432
release-link replay, because that field is the cross-release envelope edge
rather than a retained-gap exit condition itself. Status values such as
`status` and `guarded_completion_status` are not treated as ID references in
this pass.

The next safe value-level splits are likely:

- source-specific metric strings such as receipt and ratio markers against
  their owning release reports;
- external handoff contract ids against the external handoff contract source
  ledger, beyond projection presence.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=93/93 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=93/93 ready`
- `Source evidence: 93 / 93 ready (0 missing)`
- `missing_projection_retained_gap_exit_reference_id`
