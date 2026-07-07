# Scene Matrix Drilldown Row Pack Family Registry Trace N2.419

## Purpose

N2.418 made row-level sources traceable to source evidence. The next visible row reference surface is `pack_ids` and `family_ids`: these fields drive filtering, export review, and scenario coverage navigation. If a row references an unknown pack or family, the drilldown can still render while pointing reviewers to an index value that no registry owns.

N2.419 closes the row pack/family registry trace gap.

The release invariant is that every drilldown row `pack_ids` value is present in the scene coverage pack registry, and every row `family_ids` value is present in the planned scene family registry.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - `audit_scene_matrix_drilldown_report()` now reads coverage pack ids from `list_scene_coverage_packs()`.
  - The audit reads planned family ids from `list_planned_scene_families()`.
  - The audit emits `unknown_row_pack_id` when a row references a pack outside the coverage registry.
  - The audit emits `unknown_row_family_id` when a row references a family outside the planned family registry.
  - Registers the pack/family registry audit as source evidence.
  - Registers this N2.419 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime row pack ids as a subset of the coverage pack registry.
  - Locks runtime row family ids as a subset of the planned family registry.
  - Locks exported payload row pack/family ids against the same registries.
  - Builds an unknown pack/family report and verifies the audit returns `unknown_row_pack_id` and `unknown_row_family_id`.
  - Updates source evidence readiness expectations to `65/65 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=65/65 ready`.

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
- Audit-level blocking issues for unknown row pack or family ids.

N2.419 source evidence readiness was `65/65 ready`, with `0 missing`.

## Current Lineage

N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 adds action/capability projection profiles, N2.426 adds projection test-reference checks, N2.427 adds projection source-reference checks, and N2.428 adds projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `65/65` entries below as the historical verification snapshot for N2.419; use the latest Release Gate output and N2.428 for the current total.

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
- `drilldown_sources=65/65 ready`
- `Source evidence: 65 / 65 ready (0 missing)`
- `unknown_row_pack_id`
- `unknown_row_family_id`
