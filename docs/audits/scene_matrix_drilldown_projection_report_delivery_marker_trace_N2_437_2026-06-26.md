# Scene Matrix Drilldown Projection Report Delivery Marker Trace N2.437

## Purpose

N2.436 closed external handoff contract replay. N2.437 closes the next
report/delivery output-marker gap: typed report artifact and delivery execution
markers must not only exist in their owning source audits; they must be visible
in the matching scene matrix drilldown rows.

This pass also fixes a profile naming mismatch. The report artifact source
schema does not expose `artifact_group_ids`; its typed output field is
`artifact_kind_ids`. The projection profile now treats `repair_target_types` as
the action-side repair target field and `artifact_kind_ids` as the
capability/output marker field.

## Registry Scope

This replay intentionally stays inside typed source schema fields. It does not
parse row labels, detail strings, or natural-language route hints.

The projection replay is assembled from:

- `scene_report_artifact_drilldown_audit.rows[*].artifact_kind_ids` into
  `report_artifact_drilldown` row `capability_ids`;
- `scene_delivery_preset_execution_audit.rows[*].payload_keys` into
  `delivery_execution` row `action_behavior_ids`;
- `scene_delivery_preset_execution_audit.rows[*].required_output_signal_ids`
  into `delivery_execution` row `capability_ids`.

The replay deliberately excludes `report_surface_ids`, `runtime_surface_ids`,
and `ui_surface_ids` because N2.428 already protects those through surface
projection replay.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_projection_report_delivery_marker_reference_map()` with cached
    source-field replay for report artifact kinds, delivery payload keys, and
    required output signals.
  - Emits `missing_projection_report_delivery_marker_reference_id` when a
    source-declared report/delivery marker is not projected into the matching
    drilldown row field.
  - Corrects the `report_artifact_drilldown` projection profile from the stale
    `artifact_group_ids` action field to `repair_target_types`, and adds
    `artifact_kind_ids` to capability source fields.
  - Registers the report/delivery marker replay audit as source evidence.
  - Registers this N2.437 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the report/delivery marker replay map.
  - Locks runtime rows and exported payload rows so every replayed output marker
    is projected into `action_behavior_ids` or `capability_ids`.
  - Adds a negative audit fixture for
    `missing_projection_report_delivery_marker_reference_id`.
  - Updates source evidence readiness expectations to `101/101 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=101/101 ready`.

## Acceptance View

The drilldown visible-reference contract now additionally covers:

- Projected report artifact kind ids covered by report artifact source-report
  `artifact_kind_ids` field replay.
- Projected delivery payload keys covered by delivery execution source-report
  `payload_keys` field replay.
- Projected required output signal ids covered by delivery execution
  source-report `required_output_signal_ids` field replay.
- A corrected report artifact projection profile whose action/capability field
  declarations match the owning source schema and row payload.

Current source evidence readiness target for N2.437 was `101/101 ready`, with
`0 missing`. N2.438 supersedes the active target to `103/103 ready` by adding
release acceptance requirement-dimension replay.

## Boundary

N2.437 verifies visibility of typed report/delivery output markers in the scene
matrix. It does not validate the semantic completeness of report generation,
payload rendering, or delivery preset execution; those checks remain owned by
`scene_report_artifact_drilldown_audit` and
`scene_delivery_preset_execution_audit`.

N2.437 also does not reopen formula/output/watermark capability planning. Those
belong to the higher-level scene capability matrix and should be handled in a
separate capability-scope pass.

The acceptance certificate requirement dimension split is now closed by N2.438.
The next safe value-level splits are likely:

- target plugin ids against the plugin/manual gate or handoff ledger where a
  stable target-plugin registry exists;
- formula/output/watermark scenario parameters after the higher-level scene
  capability matrix defines their owning scope.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- Quick build/audit check passed with
  `passed 37 37 553 101 101 0 0`.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=101/101 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=101/101 ready`
- `Source evidence: 101 / 101 ready (0 missing)`
- `missing_projection_report_delivery_marker_reference_id`
