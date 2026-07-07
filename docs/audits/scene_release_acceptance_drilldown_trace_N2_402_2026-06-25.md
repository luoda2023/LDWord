# Scene Release Acceptance Drilldown Trace N2.402

N2.400 made receipt alignment part of the release acceptance certificate. N2.401 projected that receipt expansion through the final release projection and closure-ledger stage. N2.402 makes the same receipt acceptance visible in the scene matrix drilldown, so users can inspect the final certificate rows rather than only seeing aggregate `14/14` and `15/15` counters.

## Closed Link

`release_acceptance_certificate` drilldown now exposes the two receipt-specific certificate rows:

| Drilldown row | Expected ratio | Trace marker |
| --- | ---: | --- |
| `retained_gap_external_receipts` | `6/6` | `acceptance_receipt_trace` |
| `release_residual_ratio_receipts` | `10/10` | `acceptance_receipt_trace` |

The drilldown row count moves from `22` to `24`: fourteen certificate rows plus ten requirement-dimension rows.

## Review Rule

The drilldown must let a reviewer search for `acceptance_receipt_trace` and land directly on the receipt certificate rows. Source evidence must also prove that the drilldown registry and the acceptance certificate source know about `release_residual_ratio_receipts`, `retained_gap_external_receipts`, and `acceptance_evidence=15/15`.

This closes the path from boundary receipts to retained gaps, residual ratios, final acceptance, release projection, closure ledger, and user-facing drilldown.

N2.403 carries the resulting `553/553` drilldown row coverage into the release gate human summary as `drilldown_rows=553/553`.
