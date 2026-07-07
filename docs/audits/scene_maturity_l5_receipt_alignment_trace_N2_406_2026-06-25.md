# Scene Maturity L5 Receipt Alignment Trace N2.406

## Purpose

The release gate intentionally reports `maturity_l5_blocked=6/27` because six Blue/Boundary subjects remain outside Green/L5 and are released through retained boundary governance.

Before N2.406, the release summary proved this chain through:

- `maturity_l5_enveloped=6/6`
- `maturity_l5_alignment=6/6`
- `retained_gap_receipts=6/6`
- `residual_ratio_receipts=10/10`

Those counts were correct, but the receipt proof for the visible `maturity_l5_blocked=6/27` ratio was still indirect. N2.406 exposes the maturity-L5 receipt path as a named sub-count.

## Implemented Chain

- `src/config/scene_release_residual_ratio_ledger_audit.py`
  - Added `maturity_l5_blocker_receipt_alignment_ids`.
  - Added `maturity_l5_blocker_receipt_alignment_count=6`.
  - Added `maturity_l5_blocker_receipt_alignment_link_count=6`.
  - Added an issue when `maturity_l5_blocked` release envelopes do not retain receipt alignment for the same ID set.
- `scripts/export_scene_release_residual_ratio_ledger_audit.py`
  - Added `Maturity L5 receipt alignments: 6/6`.
- `src/config/scene_matrix_dashboard.py`
  - Added dashboard payload counts for maturity-L5 receipt alignment.
  - Added `6/6 L5 receipts aligned` to the release residual ratios card.
- `src/ui/panels/scene_summary_projection.py`
  - Added `6/6 L5 receipts aligned` to boundary, evidence, and readiness summary details.
- `scripts/verify_scene_matrix_release_gate.py`
  - Added release-gate payload counts.
  - Added `maturity_l5_receipts=6/6` to the human release summary.

## Acceptance View

N2.406 does not change the retained blocker count. It makes the existing receipt path explicit:

- `maturity_l5_blocked=6/27`
- `maturity_l5_enveloped=6/6`
- `maturity_l5_alignment=6/6`
- `maturity_l5_receipts=6/6`

This prevents the most visible retained maturity ratio from depending only on global receipt totals.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/config/scene_release_residual_ratio_ledger_audit.py scripts/export_scene_release_residual_ratio_ledger_audit.py src/config/scene_matrix_dashboard.py src/ui/panels/scene_summary_projection.py scripts/verify_scene_matrix_release_gate.py tests/test_scene_release_residual_ratio_ledger_audit.py tests/test_scene_matrix_dashboard.py`
- `python -m pytest tests/test_scene_release_residual_ratio_ledger_audit.py -q`
  - `5 passed`
- `python -m pytest tests/test_scene_matrix_dashboard.py -q`
  - `6 passed`
- `python scripts\verify_scene_matrix_release_gate.py`
  - `Scene matrix release gate: passed`
  - Summary includes `maturity_l5_enveloped=6/6`, `maturity_l5_alignment=6/6`, `maturity_l5_receipts=6/6`, `count_delivery_receipts=4/4`, `acceptance_receipts=2/2`, and `drilldown_rows=553/553`.
- `python -m pytest tests/test_release_shell.py -q`
  - `9 passed`
