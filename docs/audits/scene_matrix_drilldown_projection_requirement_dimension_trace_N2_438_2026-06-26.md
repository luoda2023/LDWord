# Scene Matrix Drilldown Projection Requirement Dimension Trace N2.438

## Purpose

N2.437 closed report/delivery output-marker replay. N2.438 closes the next
release acceptance requirement-dimension gap: each typed requirement dimension
row in the acceptance certificate must project its own `dimension_id` into the
matching scene matrix drilldown row.

The source and evidence sides of requirement dimensions were already protected
by source-id and evidence-id replay. This pass adds the missing identity-level
contract for the requirement dimension id itself, so a row cannot keep its
source/evidence links while silently dropping the dimension marker that makes it
searchable and filterable.

## Registry Scope

This replay is assembled from:

- `scene_release_acceptance_certificate_audit.requirement_dimension_rows[*].dimension_id`
  into `release_acceptance_certificate` row `capability_ids`.

The matching drilldown row id is
`requirement:{dimension_id}`.

The replay deliberately excludes `source_ids` and `evidence_ids` because those
are already covered by N2.427 source reference replay and N2.430 evidence
reference replay.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_requirement_dimension_reference_map()` with cached
    source-field replay for release acceptance requirement dimensions.
  - Emits `missing_projection_requirement_dimension_reference_id` when a
    source-declared requirement dimension id is not projected into the matching
    drilldown row capability field.
  - Registers the requirement dimension replay audit as source evidence.
  - Registers this N2.438 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the requirement dimension replay map.
  - Locks runtime rows and exported payload rows so every replayed requirement
    dimension id is projected into `capability_ids`.
  - Adds a negative audit fixture for
    `missing_projection_requirement_dimension_reference_id`.
  - Updates source evidence readiness expectations to `103/103 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=103/103 ready`.

## Acceptance View

The drilldown visible-reference contract now additionally covers:

- Projected acceptance requirement dimension ids covered by the acceptance
  certificate source-report `dimension_id` field replay.
- The `release_acceptance_certificate` projection profile declares
  `requirement_dimension_ids`, and this replay proves the concrete row
  `dimension_id` values are present in matrix `capability_ids`.
- Searchable/filterable requirement dimension rows whose row id and capability
  marker remain aligned to the owning acceptance certificate row.

Current source evidence readiness target for N2.438 was `103/103 ready`, with
`0 missing`. N2.439 supersedes the active target to `105/105 ready` by adding
external handoff target-plugin replay.

## Boundary

N2.438 verifies identity visibility for requirement dimensions in the scene
matrix. It does not re-evaluate the semantic completeness of each requirement
dimension. Those checks remain owned by
`scene_release_acceptance_certificate_audit`.

The target plugin id split is now closed by N2.439. The next safe value-level
split is likely:

- formula/output/watermark scenario parameters after the higher-level scene
  capability matrix defines their owning scope.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- Quick build/audit check passed with
  `passed 37 37 553 103 103 0 0`.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=103/103 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=103/103 ready`
- `Source evidence: 103 / 103 ready (0 missing)`
- `missing_projection_requirement_dimension_reference_id`
