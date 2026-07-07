# Scene Matrix Drilldown Item Row Unique Id Trace N2.416

## Purpose

N2.415 made source evidence ids unique, but the drilldown registry itself still had an unprotected identity surface: duplicate `drilldown_id` values can be hidden by dictionary lookups, and duplicate `row_id` values inside a drilldown can make UI row navigation, filtering, and export review ambiguous.

N2.416 closes the drilldown item/row identity gap.

The release invariant is unique drilldown_id coverage across the registry and unique row_id coverage inside each drilldown.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - `audit_scene_matrix_drilldown_report()` now emits `duplicate_drilldown_id` if two drilldown items share the same `drilldown_id`.
  - The same audit now emits `duplicate_row_id` if one drilldown item contains repeated `row_id` values.
  - Registers the item/row identity audit as source evidence.
  - Registers this N2.416 plan as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks uniqueness for runtime `drilldown_id` values.
  - Locks uniqueness for each runtime drilldown's `row_id` values.
  - Locks uniqueness for exported payload item ids and row ids.
  - Builds duplicate-id reports and verifies the audit returns `duplicate_drilldown_id` and `duplicate_row_id`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=59/59 ready`.

## Acceptance View

The drilldown identity contract now covers:

- Unique source evidence ids.
- Unique drilldown item ids.
- Unique row ids inside each drilldown.
- Audit-level blocking issues for duplicate item or row ids.

N2.416 source evidence readiness was `59/59 ready`, with `0 missing`.

## Current Lineage

N2.417 added item source evidence checks, N2.418 added row source evidence checks, N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 adds action/capability projection profiles, N2.426 adds projection test-reference checks, N2.427 adds projection source-reference checks, and N2.428 adds projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `59/59` entries below as the historical verification snapshot for N2.416; use the latest Release Gate output and N2.428 for the current total.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with `6 passed`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with `7 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=59/59 ready`
- `Source evidence: 59 / 59 ready (0 missing)`
- `duplicate_drilldown_id`
- `duplicate_row_id`
