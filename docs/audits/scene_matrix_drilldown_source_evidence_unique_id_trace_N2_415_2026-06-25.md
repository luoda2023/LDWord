# Scene Matrix Drilldown Source Evidence Unique Id Trace N2.415

## Purpose

N2.414 locked count/list consistency for source evidence payloads. One remaining structural risk was duplicate `source_id` values: many tests and UI summaries build lookup dictionaries by `source_id`, so duplicates could silently overwrite earlier evidence rows even if list length and ready/missing counts still looked correct.

N2.415 closes that identity gap.

The release invariant is unique source_id coverage across the runtime report and exported JSON payload.

## Implemented Chain

- `tests/test_scene_matrix_drilldown.py`
  - Adds `report_source_ids` and verifies `len(report_source_ids) == len(set(report_source_ids))`.
  - Adds `payload_source_ids` and verifies JSON payload source evidence ids are unique.
  - Applies uniqueness checks to the runtime report payload and the exported JSON payload.
- `src/config/scene_matrix_drilldown.py`
  - Registers the unique-id test surface as source evidence.
  - Registers this N2.415 plan as source evidence.

## Acceptance View

The source evidence contract now covers:

- Count/list parity.
- Ready/missing status parity.
- Unique `source_id` identity in runtime payloads.
- Unique `source_id` identity in JSON exports.

N2.415 established source evidence `source_id` uniqueness at `57/57 ready`, with `0 missing`.

## Current Lineage

N2.416 added drilldown item and row identity checks, N2.417 added item source evidence checks, N2.418 added row source evidence checks, N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 adds action/capability projection profiles, N2.426 adds projection test-reference checks, N2.427 adds projection source-reference checks, and N2.428 adds projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `57/57` entries below as the historical verification snapshot for N2.415; use the latest Release Gate output and N2.428 for the current total.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py`
- `python -m pytest tests/test_scene_matrix_drilldown.py -q`
  - `6 passed`
- `python -m pytest tests/test_scene_matrix_dashboard.py -q`
  - `6 passed`
- `python -m pytest tests/test_release_shell.py -q`
  - `9 passed`
- `python scripts\verify_scene_matrix_release_gate.py`
  - `Scene matrix release gate: passed`

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=57/57 ready`
- `Source evidence: 57 / 57 ready (0 missing)`
- unique `source_id`
