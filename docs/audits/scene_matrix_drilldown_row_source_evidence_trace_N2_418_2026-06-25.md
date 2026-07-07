# Scene Matrix Drilldown Row Source Evidence Trace N2.418

## Purpose

N2.417 made each drilldown item's `item.source_id` traceable to source evidence. The row model still has its own `row.source_id`, and that field is exported in payloads and participates in search. If row-level sources drift from source evidence, a reviewer can land on a visible row that no longer has a release evidence entry.

N2.418 closes the row source evidence trace gap.

The release invariant is that every drilldown row `source_id` is covered by source evidence and matches the parent drilldown item's `source_id`.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - `audit_scene_matrix_drilldown_report()` now builds `row_source_ids`.
  - The audit emits `missing_row_source_evidence` when a row points to a source that is not present in source evidence.
  - The audit emits `row_source_mismatch` when a row source differs from its parent drilldown item source.
  - Registers the row source evidence audit as source evidence.
  - Registers this N2.418 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime row source ids as a subset of report source evidence ids.
  - Locks each runtime row source id to its parent drilldown item source id.
  - Locks exported payload row source ids as a subset of payload source evidence ids.
  - Locks each exported payload row source id to its exported parent item source id.
  - Builds a mismatched row-source report and verifies the audit returns `missing_row_source_evidence` and `row_source_mismatch`.
  - Updates source evidence readiness expectations to `63/63 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=63/63 ready`.

## Acceptance View

The drilldown identity and trace contract now covers:

- Unique source evidence ids.
- Unique drilldown item ids.
- Unique row ids inside each drilldown.
- Item source ids covered by source evidence.
- Row source ids covered by source evidence.
- Row source ids aligned with their parent item source ids.
- Audit-level blocking issues for duplicate item ids, duplicate row ids, item source evidence gaps, row source evidence gaps, and row/item source mismatches.

N2.418 source evidence readiness was `63/63 ready`, with `0 missing`.

## Current Lineage

N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 adds action/capability projection profiles, N2.426 adds projection test-reference checks, N2.427 adds projection source-reference checks, and N2.428 adds projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `63/63` entries below as the historical verification snapshot for N2.418; use the latest Release Gate output and N2.428 for the current total.

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
- `drilldown_sources=63/63 ready`
- `Source evidence: 63 / 63 ready (0 missing)`
- `missing_row_source_evidence`
- `row_source_mismatch`
