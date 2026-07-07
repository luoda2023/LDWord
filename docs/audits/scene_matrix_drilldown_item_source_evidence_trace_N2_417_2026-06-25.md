# Scene Matrix Drilldown Item Source Evidence Trace N2.417

## Purpose

N2.416 made `drilldown_id` and `row_id` identity unique, but a remaining reference surface still needed a release contract: each drilldown item's `item.source_id` must be covered by the source evidence registry.

Without this check, a new drilldown item could appear in the UI, JSON export, Markdown export, and Release Gate counts while pointing to a source that is absent from the evidence list. That would leave reviewers with a visible drilldown row but no source evidence entry to inspect.

N2.417 closes the item source evidence trace gap.

The release invariant is that every drilldown item `source_id` is a member of the source evidence `source_id` set.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - `audit_scene_matrix_drilldown_report()` now builds `evidence_source_ids` and `item_source_ids`.
  - The audit emits `missing_item_source_evidence` when a drilldown item points to a source that is not present in source evidence.
  - Registers the item source evidence audit as source evidence.
  - Registers this N2.417 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime item source ids as a subset of report source evidence ids.
  - Locks exported payload item source ids as a subset of payload source evidence ids.
  - Builds a missing-source report and verifies the audit returns `missing_item_source_evidence`.
  - Updates source evidence readiness expectations to `61/61 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=61/61 ready`.

## Acceptance View

The drilldown identity and trace contract now covers:

- Unique source evidence ids.
- Unique drilldown item ids.
- Unique row ids inside each drilldown.
- Item source ids covered by source evidence.
- Audit-level blocking issues for duplicate item ids, duplicate row ids, or item source evidence gaps.

N2.417 source evidence readiness was `61/61 ready`, with `0 missing`.

## Current Lineage

N2.418 added row source evidence checks, N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 adds action/capability projection profiles, N2.426 adds projection test-reference checks, N2.427 adds projection source-reference checks, and N2.428 adds projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `61/61` entries below as the historical verification snapshot for N2.417; use the latest Release Gate output and N2.428 for the current total.

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
- `drilldown_sources=61/61 ready`
- `Source evidence: 61 / 61 ready (0 missing)`
- `missing_item_source_evidence`
