# Scene Matrix Drilldown Row Request Fixture Registry Trace N2.420

## Purpose

N2.419 made row-level `pack_ids` and `family_ids` traceable to their authoritative registries. The next visible row reference surface is `request_cell_ids` and `fixture_ids`: these fields point reviewers from a drilldown row to concrete high-frequency request samples and DOCX fixture evidence. If either id drifts outside its registry, the row can still render while the sample or fixture evidence cannot be inspected.

N2.420 closes the row request-cell and fixture registry trace gap.

The release invariant is that every drilldown row `request_cell_ids` value is present in the request-cell fixture registry, and every row `fixture_ids` value is present in the scene sample fixture registry.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - `audit_scene_matrix_drilldown_report()` now reads request cell ids from `list_scene_request_cell_fixtures()`.
  - The audit reads sample fixture ids from `list_scene_sample_fixtures()`.
  - The audit emits `unknown_row_request_cell_id` when a row references a request cell outside the registry.
  - The audit emits `unknown_row_fixture_id` when a row references a sample fixture outside the registry.
  - Registers the request/fixture registry audit as source evidence.
  - Registers this N2.420 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime row request cell ids as a subset of the request-cell fixture registry.
  - Locks runtime row fixture ids as a subset of the scene sample fixture registry.
  - Locks exported payload row request/fixture ids against the same registries.
  - Builds an unknown request/fixture report and verifies the audit returns `unknown_row_request_cell_id` and `unknown_row_fixture_id`.
  - Updates source evidence readiness expectations to `67/67 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=67/67 ready`.

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
- Audit-level blocking issues for unknown row request cell or fixture ids.

N2.420 source evidence readiness was `67/67 ready`, with `0 missing`.

## Current Lineage

N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 adds action/capability projection profiles, N2.426 adds projection test-reference checks, N2.427 adds projection source-reference checks, and N2.428 adds projection surface-reference checks and supersedes the current count to `83/83 ready`. Treat the `67/67` entries below as the historical verification snapshot for N2.420; use the latest Release Gate output and N2.428 for the current total.

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
- `drilldown_sources=67/67 ready`
- `Source evidence: 67 / 67 ready (0 missing)`
- `unknown_row_request_cell_id`
- `unknown_row_fixture_id`
