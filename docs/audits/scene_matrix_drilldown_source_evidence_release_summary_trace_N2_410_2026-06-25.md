# Scene Matrix Drilldown Source Evidence Release Summary Trace N2.410

## Purpose

N2.409 aligned the Summary card with the actual `report.source_evidence` list. The Release Gate payload already carried `scene_matrix_drilldown_missing_source_evidence_count`, but the terminal summary only exposed `drilldowns` and `drilldown_rows`.

That left source evidence readiness visible to machines but not to the human `[OK]` release summary. N2.410 closes that visibility gap.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `source_evidence_count`.
  - Adds `ready_source_evidence_count`.
  - Includes both counts in `SceneMatrixDrilldownReport.to_payload()`.
  - Registers the Release Gate source-summary projection and this N2.410 plan as source evidence.
- `scripts/verify_scene_matrix_release_gate.py`
  - Adds `scene_matrix_drilldown_source_evidence_count`.
  - Adds `scene_matrix_drilldown_ready_source_evidence_count`.
  - Introduces the `drilldown_sources=... ready` Release Gate terminal summary marker.
- `tests/test_scene_matrix_drilldown.py`
  - Locks the new report counts, payload counts, source evidence markers, and Summary visibility.
- `tests/test_scene_matrix_dashboard.py`
  - Locks the terminal summary marker for drilldown source evidence readiness.

## Acceptance View

The source evidence chain now has consistent visibility:

- Drilldown payload: source evidence count and ready source evidence count.
- Summary card: all source evidence ids, including projection and N2 trace documents.
- Release Gate terminal summary: `drilldown_sources=... ready`.

This prevents a release reviewer from seeing drilldown row coverage without knowing whether the evidence sources behind those rows are also fully ready.

## Current Lineage

N2.410 introduced the terminal summary signal at `47/47`. Later N2.411 through N2.428 added more source evidence records and superseded the current count to `83/83 ready`. Treat the `47/47` entries below as the historical verification snapshot for N2.410; use the latest Release Gate output and N2.428 for the current total.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/config/scene_matrix_drilldown.py scripts/verify_scene_matrix_release_gate.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py`
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
- `drilldown_sources=47/47 ready`
- `count_delivery_receipts=4/4`
- `maturity_l5_receipts=6/6`
- `acceptance_receipts=2/2`
