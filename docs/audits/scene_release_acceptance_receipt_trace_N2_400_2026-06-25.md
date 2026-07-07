# Scene Release Acceptance Receipt Trace N2.400

N2.397 aligned retained boundary gaps with external receipts. N2.398 carried those receipts into the release residual-ratio ledger. N2.399 projected the receipt trace through the final release projection and closure-ledger review surfaces. N2.400 makes the same receipt chain a first-class release acceptance certificate requirement.

## Closed Link

`scene_release_acceptance_certificate_audit` now certifies two receipt-specific rows:

| Certificate row | Source report | Expected ratio | Meaning |
| --- | --- | ---: | --- |
| `retained_gap_external_receipts` | `scene_retained_gap_exit_criteria_audit` | `6/6` | Every retained gap exit path carries the external receipt evidence declared by the boundary capability matrix. |
| `release_residual_ratio_receipts` | `scene_release_residual_ratio_ledger_audit` | `10/10` | Every residual-ratio exit criteria link keeps the retained-gap receipt evidence. |

The release acceptance certificate therefore moves from `12/12` to `14/14`, and certificate source evidence moves from `11/11` to `15/15` after receiving N2.397, N2.398, N2.399, and this N2.400 closure record.

## Review Rule

The `residual_boundary_release_governance` requirement dimension must include both receipt ratios:

- `retained_gap_external_receipts=6/6`
- `release_residual_ratio_receipts=10/10`

The release gate human summary must expose `retained_gap_receipts=6/6`, `residual_ratio_receipts=10/10`, `acceptance_certificate=14/14`, and `acceptance_evidence=15/15`. This prevents external receipt alignment from ending at the residual ledger while the final certificate still appears to accept only exit criteria and explanations.

N2.401 carries this certificate receipt expansion into the final release projection and closure-ledger stage through `acceptance_receipt_trace`.
