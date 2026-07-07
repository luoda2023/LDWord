# Scene Release Acceptance Dashboard Receipt Trace N2.404

## Purpose

N2.400 added two receipt-backed release acceptance rows:

- `release_residual_ratio_receipts` verifies `10/10` residual-ratio exit links retain external receipt evidence.
- `retained_gap_external_receipts` verifies `6/6` retained-gap exits carry boundary-declared external receipt evidence.

Before N2.404 these rows were included in the release acceptance total (`14/14`) and source evidence total (`15/15`), but Dashboard and Summary did not expose receipt certificates as a named sub-count. That made receipt readiness visible only by drilling into the certificate rows.

## Implemented Chain

- `src/config/scene_release_acceptance_certificate_audit.py`
  - Added `SCENE_RELEASE_ACCEPTANCE_RECEIPT_CERTIFICATE_IDS`.
  - Added `receipt_certificate_count=2` and `ready_receipt_certificate_count=2`.
  - Added both counts to `report.to_payload()["counts"]`.
  - Strengthened self-evidence markers for Dashboard, Summary, Release Gate, export script, and tests.
- `scripts/export_scene_release_acceptance_certificate_audit.py`
  - Added `Receipt certificates ready: 2/2` to markdown exports.
- `src/config/scene_matrix_dashboard.py`
  - Added dashboard payload counts:
    - `release_acceptance_certificate_receipt_count`
    - `release_acceptance_certificate_ready_receipt_count`
  - Added `2/2 receipt certificates` to the `release_acceptance_certificate` card detail.
- `src/ui/panels/scene_summary_projection.py`
  - Added `2/2 receipt certificates` to boundary and evidence summary details.
- `scripts/verify_scene_matrix_release_gate.py`
  - Added release-gate payload counts:
    - `scene_release_acceptance_certificate_receipt_count`
    - `scene_release_acceptance_certificate_ready_receipt_count`
  - Added `acceptance_receipts=2/2` to the human release-gate summary.

## Acceptance View

The release acceptance certificate still remains `14/14`, and the source evidence remains `15/15`. N2.404 does not add a new certificate row; it classifies and exposes the two existing receipt rows as an explicit readiness dimension.

Expected visible chain:

- Audit payload: `ready_receipt_certificate_count=2/2`.
- Export markdown: `Receipt certificates ready: 2/2`.
- Dashboard card: `2/2 receipt certificates`.
- Summary projection: `2/2 receipt certificates`.
- Release gate: `acceptance_receipts=2/2`.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/config/scene_release_acceptance_certificate_audit.py scripts/export_scene_release_acceptance_certificate_audit.py src/config/scene_matrix_dashboard.py src/ui/panels/scene_summary_projection.py scripts/verify_scene_matrix_release_gate.py tests/test_scene_release_acceptance_certificate_audit.py tests/test_scene_matrix_dashboard.py`
- `python -m pytest tests/test_scene_release_acceptance_certificate_audit.py -q`
  - `3 passed`
- `python -m pytest tests/test_scene_matrix_dashboard.py -q`
  - `6 passed`
- `python scripts\verify_scene_matrix_release_gate.py`
  - `Scene matrix release gate: passed`
  - Summary includes `acceptance_certificate=14/14`, `acceptance_receipts=2/2`, `acceptance_evidence=15/15`, and `drilldown_rows=553/553`.
- `python -m pytest tests/test_release_shell.py -q`
  - `9 passed`
