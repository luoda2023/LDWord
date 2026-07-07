# Scene Retained Gap Receipt Alignment N2.397

N2.396 made each boundary capability row carry `external_receipt_ids`. N2.397 closes the next link: those receipt targets must also appear in the retained-gap `exit_signal_ids`, otherwise the boundary matrix and the release exit criteria would describe two different ways to leave Blue/Boundary status.

## Closed Link

The retained-gap exit criteria report now carries:

| Field | Meaning |
| --- | --- |
| `boundary_capability_ids` | The boundary matrix row attached to the retained gap subject. |
| `external_receipt_ids` | The receipt or exit-signal targets declared by the boundary capability row. |
| `external_receipt_alignment_count` | Number of retained gaps whose boundary receipts are a subset of the retained-gap exit signals. |
| `external_receipt_target_count` | Unique external receipt targets across the retained boundary gaps. |

Acceptance markers: `retained_gap_receipt_alignment=6/6`, `external_receipt_targets=8`.

## Review Rule

Every retained boundary gap must now satisfy all of the following:

- It links to a release envelope.
- It links to an external handoff contract.
- It links to guarded boundary completion.
- It links to a boundary capability row.
- Its boundary capability `external_receipt_ids` are present in its retained-gap `exit_signal_ids`.

This keeps the release-allowed state and the future exit path aligned. It still does not promote professional disclosure, import/AI conversion, finance quote, patent, bilingual translation, or regulated disclosure to Green/L5.

N2.398 carries the same receipt alignment into `scene_release_residual_ratio_ledger_audit`, so the non-full `count_profiles`, `delivery_families`, and `maturity_l5_blocked` readings inherit the retained-gap receipt evidence instead of stopping at exit-criteria counts.
