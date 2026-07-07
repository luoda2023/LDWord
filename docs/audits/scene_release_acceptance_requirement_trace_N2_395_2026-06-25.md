# Scene Release Acceptance Requirement Trace N2.395

## Goal

N2.394 proves the release certificate components are present and ready. N2.395 adds a user-requirement trace inside the same certificate so the release can answer a stricter question: do the green release readings cover the scenario-board requirements that started this work, not only the internal audit components?

This is intentionally not a new product promise and does not promote Blue/Boundary subjects to Green/L5. It maps the current release evidence to the scenario definition dimensions that must stay visible: high-frequency coverage, natural request routing, template-consistent controls, input/material scope, Word/OOXML risks, formula/output/watermark ownership, delivery artifacts, business family boundaries, residual governance, and projection/export visibility.

## Requirement Dimensions

`SCENE_RELEASE_REQUIREMENT_DIMENSION_SPECS` now records 10 acceptance dimensions:

| Dimension | Purpose |
| --- | --- |
| `high_frequency_scene_coverage` | Prevent high-frequency scene packs from being hidden behind generic custom configuration. |
| `natural_request_to_scene_route` | Prove natural wording, request cells, and journeys land on explicit scene carriers. |
| `scene_board_control_style_consistency` | Keep scene controls aligned with the template-management control contracts, pairing, disabled states, units, and runtime consumers. |
| `input_material_scope` | Make processing scope, input profiles, material schemas, and repair flows explicit. |
| `word_ooxml_risk_scope` | Keep Word XML risks, object preflight, fixed-layout row height, and count profiles release-gated. |
| `formula_output_watermark_scene_ownership` | Keep formula, output, and watermark parameters in scene ownership with contracts and execution consumers. |
| `delivery_artifact_chain` | Connect delivery presets to runtime output, structured intermediates, reports, artifact drilldown, and visibility rules. |
| `business_family_boundary_catalog` | Keep business capabilities, planned families, professional boundaries, and import/AI boundaries explicit. |
| `residual_boundary_release_governance` | Explain retained gaps, L5 blockers, residual ratios, boundary scopes, and acceptance rows without overclaiming Green/L5. |
| `projection_export_visibility` | Ensure release proof reaches release gate, dashboard, drilldown, summary projection, export scripts, workflow, and docs. |

## Closure Rule

The release acceptance certificate now fails if any requirement dimension has a missing source, a failed source report, an empty denominator, or a non-full observed ratio. The release gate summary must expose `requirement_dimensions=10/10`, and the export script must show `Requirement dimensions ready: 10/10`.

`scene_release_projection_surface_parity_audit` and `scene_release_closure_ledger_audit` keep the release stage count at 13, but the final `release_acceptance_certificate` projection/stage now carries `requirement_dimension_trace` as supplemental evidence and points to this N2.395 record. This prevents the new requirement trace from living only inside the certificate payload while the release sequence still appears to end at the older N2.394 surface.

The projection and closure-ledger Markdown exports also include a `Supplemental` column so reviewers can see the `requirement_dimensions=` marker and this N2.395 document path without opening the JSON payload.

N2.396 extends the boundary capability matrix rows with risk domains, decision requirements, external receipt targets, and release guardrails. This keeps the `residual_boundary_release_governance` and `business_family_boundary_catalog` dimensions reviewable from the main boundary matrix instead of requiring reviewers to reconstruct the boundary story from separate handoff and exit-criteria reports.

N2.397 then links those boundary `external_receipt_ids` back into retained-gap `exit_signal_ids`, so the matrix-level receipt target and the release exit path cannot drift apart.

N2.398 carries the same receipt alignment into the release residual-ratio ledger, so non-full release readings such as `count_profiles=14/15`, `delivery_families=14/15`, and `maturity_l5_blocked=6/27` retain their external receipt trace.

This keeps the final certificate tied to the original scenario-board scope instead of only proving that internal reports agree with each other.
