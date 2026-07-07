# Scene Release Residual Ratio Receipt Alignment N2.398

N2.397 aligned each retained boundary gap with the external receipts declared by the boundary capability matrix. N2.398 carries that alignment into the release residual-ratio ledger, so non-full release summary readings cannot stop at "has exit criteria" while losing the receipt evidence that explains how the boundary can eventually leave Blue/Boundary status.

## Closed Link

`scene_release_residual_ratio_ledger_audit` now records `retained_gap_receipt_alignment_ids` on each residual-ratio row:

| Ratio | Expected receipt-aligned criteria |
| --- | ---: |
| `count_profiles` | 2 |
| `delivery_families` | 2 |
| `maturity_l5_blocked` | 6 |

Release marker summary: `residual_ratio_receipt_alignment=10/10`, `retained_gap_receipts=6/6`.

## Review Rule

Every retained-gap exit criteria link used by a residual ratio must also be receipt-aligned. This binds the three non-full release readings to the same evidence chain:

- release envelope
- retained-gap exit criteria
- retained-gap external receipt alignment
- guarded boundary scope

The result is still a release-limited boundary reading, not a Green/L5 promotion. It only proves that the non-full ratio is publishable and traceable through the retained boundary contract.
