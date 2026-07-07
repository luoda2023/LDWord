# Scene Release Residual Receipt Source Summary Trace N2.409

## Purpose

N2.407 and N2.408 made residual receipt alignment visible in the drilldown runtime model and exported artifacts. One surface still used the older source list: the scene summary card for `scene_matrix_drilldown_sources` showed drilldown item sources, while its value reported missing source evidence.

That mismatch could hide projection-only evidence such as the residual receipt projection, the export projection, and the N2.408 handoff document from the Summary view even when Release Gate source evidence was ready.

## Implemented Chain

- `src/ui/panels/scene_summary_projection.py`
  - `scene_matrix_drilldown_sources.detail` now lists `report.source_evidence`.
  - The card value still reports `missing_source_evidence_count`.
- `src/config/scene_matrix_drilldown.py`
  - Adds source evidence for the Summary source projection itself.
  - Adds this N2.409 plan as a release-gate evidence marker.
- `tests/test_scene_matrix_drilldown.py`
  - Locks N2.407, N2.408, and N2.409 source evidence as `ready`.
  - Locks Summary visibility for:
    - `scene_matrix_drilldown_residual_receipt_projection`
    - `scene_matrix_drilldown_export_receipt_projection`
    - `scene_matrix_drilldown_source_summary_projection`
    - `n2_407_residual_receipt_drilldown_plan`
    - `n2_408_residual_receipt_export_plan`
    - `n2_409_residual_receipt_source_summary_plan`

## Acceptance View

The source evidence chain now uses one consistent lens:

- Release Gate checks all source evidence markers.
- Drilldown payload exports all source evidence.
- Summary card lists the same source evidence ids that are counted by `missing_source_evidence_count`.

This closes the UI summary gap where source evidence could pass the gate but remain invisible in the human-facing summary card.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/ui/panels/scene_summary_projection.py src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py`
- `python -m pytest tests/test_scene_matrix_drilldown.py -q`
  - `6 passed`
- `python -m pytest tests/test_release_shell.py -q`
  - `9 passed`
- `python scripts\verify_scene_matrix_release_gate.py`
  - `Scene matrix release gate: passed`

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `count_delivery_receipts=4/4`
- `maturity_l5_receipts=6/6`
- `acceptance_receipts=2/2`
