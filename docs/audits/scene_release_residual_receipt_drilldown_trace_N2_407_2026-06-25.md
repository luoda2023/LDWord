# Scene Release Residual Receipt Drilldown Trace N2.407

## Purpose

N2.405 and N2.406 made receipt readiness visible in release summaries:

- `count_delivery_receipts=4/4`
- `maturity_l5_receipts=6/6`

Before N2.407, the release residual ratio drilldown still required readers to infer those receipt alignments from generic evidence IDs and retained-gap links. The Dashboard and Release Gate were clearer than the drilldown surface.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Added residual-ratio row detail markers:
    - `receipt_alignments=2/2` for `count_profiles`
    - `receipt_alignments=2/2` for `delivery_families`
    - `receipt_alignments=6/6` for `maturity_l5_blocked`
  - Added row action markers:
    - `count_delivery_receipts=2/2`
    - `maturity_l5_receipts=6/6`
  - Added item-level detail:
    - `count_delivery_receipts=4/4`
    - `maturity_l5_receipts=6/6`
  - Kept the drilldown row count unchanged at `553/553`.

## Acceptance View

The drilldown now mirrors the same receipt language used by release gate and dashboard:

- Release Gate: `count_delivery_receipts=4/4`, `maturity_l5_receipts=6/6`.
- Dashboard: `4/4 count/delivery receipts aligned`, `6/6 L5 receipts aligned`.
- Drilldown: row-level `receipt_alignments=...` plus item-level `count_delivery_receipts=4/4` and `maturity_l5_receipts=6/6`.

This closes the visibility gap where receipt alignment was present in the model but not readable in the drilldown row text.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py`
- `python -m pytest tests/test_scene_matrix_drilldown.py -q`
  - `6 passed`
- `python scripts\verify_scene_matrix_release_gate.py`
  - `Scene matrix release gate: passed`
  - Summary includes `drilldowns=37/37`, `drilldown_rows=553/553`, `count_delivery_receipts=4/4`, `maturity_l5_receipts=6/6`, and `acceptance_receipts=2/2`.
