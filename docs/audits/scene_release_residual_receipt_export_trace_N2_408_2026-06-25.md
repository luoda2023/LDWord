# Scene Release Residual Receipt Export Trace N2.408

## Purpose

N2.407 made residual receipt alignment readable inside the scene matrix drilldown model. N2.408 closes the next surface: exported drilldown artifacts must carry the same markers, otherwise reviewers can see the receipt chain in the app/runtime report but lose it when handing off JSON or Markdown evidence.

## Implemented Chain

- `scripts/export_scene_matrix_drilldown.py`
  - JSON export already serializes `report.to_payload()`, so `item.detail` and each `row.detail` remain lossless.
  - Markdown export now prints `item.detail` below each drilldown heading before the row table.
  - Markdown row tables continue to print `row.detail`.
- `tests/test_scene_matrix_drilldown.py`
  - JSON export now locks the residual ratio source output:
    - `count_delivery_receipts=4/4`
    - `maturity_l5_receipts=6/6`
    - row-level `receipt_alignments=2/2`
    - row-level `receipt_alignments=6/6`
  - Markdown export now locks the same aggregate and row markers.
- `src/config/scene_matrix_drilldown.py`
  - Adds source evidence for the export projection itself.
  - Adds this N2.408 plan as a release-gate evidence marker.

## Acceptance View

The residual receipt chain is now visible in all review surfaces:

- Release Gate summary: aggregate receipt readiness.
- Dashboard summary: count/delivery and maturity L5 receipt alignment.
- Drilldown runtime payload: item-level and row-level receipt markers.
- Exported JSON: `item.detail` plus each `row.detail` and action marker.
- Exported Markdown: item-level detail plus visible row details.

This prevents a handoff gap where a reviewer exporting the drilldown can no longer see why residual ratios below 100% are accepted.

## Verification

Executed on 2026-06-25:

- `python -m py_compile scripts/export_scene_matrix_drilldown.py src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py`
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
