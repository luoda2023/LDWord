# Scene Matrix Drilldown Projection Formula Output Watermark Trace N2.440

## Purpose

N2.439 closed external handoff target-plugin replay. N2.440 closes the next
formula/output/watermark visibility gap: the scene matrix must expose the
capability-level parameter paths, template baselines, control contracts, and
execution consumers that make formula, output, and watermark ownership
auditable.

Before this pass, `formula_output_watermark` only projected family rows. That
proved which families touched the F/O/W capability domains, but the matrix did
not directly expose the capability rows where ownership, controls, runtime
consumers, and plugin/manual boundaries are defined.

## Registry Scope

The replay is assembled from:

- `scene_formula_output_watermark_audit.capability_rows[*].capability_id`;
- `scene_formula_output_watermark_audit.capability_rows[*].expected_owner_layer`;
- `scene_formula_output_watermark_audit.capability_rows[*].parameter_paths`;
- `scene_formula_output_watermark_audit.capability_rows[*].template_baseline_paths`;
- `scene_formula_output_watermark_audit.capability_rows[*].control_contract_ids`;
- `scene_formula_output_watermark_audit.capability_rows[*].execution_consumers`;
- `scene_formula_output_watermark_audit.family_rows[*].capability_ids`.

The matrix now creates 3 capability rows:

- `capability:formula_policy`;
- `capability:output_delivery`;
- `capability:watermark_status`.

Those rows sit beside the 15 existing family rows, increasing
`formula_output_watermark` from 15 to 18 rows and total drilldown rows from 553
to 556.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Extends the `formula_output_watermark` projection profile to include
    `expected_owner_layer`, `parameter_paths`, `template_baseline_paths`,
    `control_contract_ids`, and `execution_consumers`.
  - Adds 3 capability-level drilldown rows for F/O/W capability ownership.
  - Adds `_projection_formula_output_watermark_reference_map()` with cached
    source-field replay for capability and family rows.
  - Emits `missing_projection_formula_output_watermark_reference_id` when a
    source-declared F/O/W value is absent from the matching matrix row field.
  - Registers the F/O/W replay audit as source evidence.
  - Registers this N2.440 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the F/O/W replay map.
  - Locks runtime rows and exported payload rows so every replayed F/O/W
    ownership value is projected into `action_behavior_ids` or `capability_ids`.
  - Adds a negative audit fixture for
    `missing_projection_formula_output_watermark_reference_id`.
  - Updates total drilldown row expectations to `556/556`.
  - Updates source evidence readiness expectations to `107/107 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertions to
    `drilldown_rows=556/556` and `drilldown_sources=107/107 ready`.

## Acceptance View

The drilldown visible-reference contract now additionally covers:

- Formula policy parameter paths and execution consumers.
- Output DeliveryPreset and artifact parameter paths.
- Watermark status parameter paths and control contract.
- Template baseline paths that remain template-owned rather than scene-owned.
- Family-to-capability mapping for every F/O/W family row.

Current source evidence readiness target is `107/107 ready`, with `0 missing`.

## Boundary

N2.440 verifies that formula/output/watermark ownership parameters are visible
and replay-protected in the scene matrix. It does not claim that every possible
formula, output, or watermark UI control is complete. Visual watermark styling,
full LaTeX/OCR/AI quality, and per-preset watermark variants remain governed by
their existing scene/control/plugin boundary contracts.

## Verification

Pending verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py`
- `python -m pytest tests/test_release_shell.py -q`
- `python -m pytest tests/test_scene_matrix_dashboard.py -q`
- `python scripts\verify_scene_matrix_release_gate.py`
- `python -m pytest tests/test_scene_matrix_drilldown.py -q`

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=556/556`
- `drilldown_sources=107/107 ready`
- `Source evidence: 107 / 107 ready (0 missing)`
- `missing_projection_formula_output_watermark_reference_id`
