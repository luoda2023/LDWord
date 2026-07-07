# Scene Boundary Capability Matrix Governance Trace N2.396

N2.395 made the release acceptance certificate answer whether the scenario-board requirements are covered. N2.396 tightens the remaining Blue/Boundary surface: the six retained boundary subjects must not be represented only as "allowed exceptions". Each boundary capability row now carries the governance facts that explain why it can remain release-allowed without being promoted to Green/L5.

## Governance Fields

| Field | Purpose |
| --- | --- |
| `risk_domain_ids` | Names the professional, import, conversion, or assurance risk domains that core formatting must not silently claim. |
| `decision_requirement_ids` | Requires manual decision, external status recording, fallback reporting, and visible excluded-core claims. |
| `external_receipt_ids` | Names the receipt or exit-signal targets needed before the boundary can leave Blue/Boundary status. |
| `release_guardrail_ids` | Keeps the row explicitly release-allowed but not Green/L5 until a real plugin/manual receipt path exists. |

## Acceptance Reading

The boundary matrix remains at 6 ready rows, but the rows are now governed by four additional checks:

| Reading | Expected |
| --- | --- |
| `boundary_decision_requirements` | `6/6` rows carry the required decision set. |
| `external_receipt_targets` | `6/6` rows carry receipt or exit-signal targets. |
| `release_guardrails` | `6/6` rows carry the required guardrail set. |
| `risk_domain_visibility` | `6/6` rows expose at least one risk domain. |

Release marker summary: `boundary_decision_requirements=6/6`, `external_receipt_targets=6/6`, `release_guardrails=6/6`, `risk_domain_visibility=6/6`.

The release gate and dashboard also expose aggregate counts for risk domains, decision requirements, external receipts, and release guardrails. This keeps professional disclosure, import/AI conversion, finance quote, patent, bilingual translation, and regulated disclosure from becoming vague residual buckets.

## Boundary Outcome

This is not a new professional capability promise. It does not add finance assurance, patent judgment, translation quality review, audit assurance, legal conclusions, OCR truthfulness, PDF losslessness, or LaTeX conversion quality to the core formatter. It only makes the boundary contract reviewable in the same matrix surface that lists the boundary capability.

N2.396 therefore closes a visibility gap in the higher-level scenario ability matrix: release reviewers can now see the local scope, excluded claims, risk domains, required decision path, external receipt target, and release guardrails without reconstructing them from separate handoff and exit-criteria audits.

N2.397 follows this by requiring each boundary capability `external_receipt_ids` set to appear in the corresponding retained-gap `exit_signal_ids`, so the visible boundary matrix and the release exit criteria describe the same exit path.
