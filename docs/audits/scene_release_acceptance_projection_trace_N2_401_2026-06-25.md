# Scene Release Acceptance Projection Trace N2.401

N2.400 made retained-gap and residual-ratio receipt alignment a first-class release acceptance certificate requirement. N2.401 carries that acceptance receipt trace into the final projection and closure-ledger stage so the release sequence does not still end with only the older requirement-dimension trace.

## Closed Link

`release_acceptance_certificate` now carries `acceptance_receipt_trace` as supplemental evidence in both final review layers:

| Review layer | Row or stage | Supplemental evidence | Supplemental records |
| --- | --- | --- | --- |
| `scene_release_projection_surface_parity_audit` | `release_acceptance_certificate` | `requirement_dimension_trace`, `acceptance_receipt_trace` | N2.395, N2.400, N2.401 |
| `scene_release_closure_ledger_audit` | `release_acceptance_certificate` | `requirement_dimension_trace`, `acceptance_receipt_trace` | N2.395, N2.400, N2.401 |

The release stage count remains `13/13`. This is a final-stage evidence projection update, not a new release stage.

## Review Rule

The final release acceptance stage must verify both families of supplemental evidence:

- requirement dimension trace: `requirement_dimensions=10/10`
- acceptance receipt trace: `acceptance_certificate=14/14` and `acceptance_evidence=15/15`

The projection and closure-ledger exports must expose `acceptance_receipt_trace` and the N2.400/N2.401 document paths. This keeps the certificate receipt expansion visible at the same final review layer where N2.395 already made requirement dimensions visible.

N2.402 carries the same `acceptance_receipt_trace` into the user-facing `release_acceptance_certificate` drilldown rows.
