# Scene Matrix Drilldown Projection Target Plugin Trace N2.439

## Purpose

N2.438 closed release acceptance requirement-dimension replay. N2.439 closes
the next target-plugin gap: concrete external handoff target plugin ids must
not only exist in the handoff contract source audit; every matrix row that
claims those target plugins must project them visibly.

This pass keeps two related concepts separate:

- `plugin_manual_gate.plugin_entry_id` is the gate entry plugin for a pack-level
  confirmation workflow.
- `scene_external_handoff_contract_audit.rows[*].target_plugin_id` is the
  concrete external plugin or professional handoff target for a retained
  boundary gap.

N2.439 uses the external handoff contract target-plugin ledger as the
authoritative registry for target plugin ids.

## Registry Scope

The target plugin ledger is assembled from:

- `scene_external_handoff_contract_audit.rows[*].target_plugin_id`.

The projection replay is assembled from:

- `scene_external_handoff_contract_audit.rows[*].target_plugin_id` into
  `external_handoff_contract` row `capability_ids`;
- `scene_boundary_guarded_completion_audit.rows[*].target_plugin_ids` into
  `boundary_guarded_completion` row `capability_ids`.

The replay deliberately excludes plugin/manual gate ids. Those continue to be
checked by the existing row `plugin_gate_ids` registry audit.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_target_plugin_reference_ids()` as the target-plugin ledger.
  - Adds `_projection_target_plugin_reference_map()` with cached source-field
    replay for external handoff and guarded completion target plugin fields.
  - Emits `unknown_projection_target_plugin_reference_id` when a replayed target
    plugin id is absent from the external handoff target-plugin ledger.
  - Emits `missing_projection_target_plugin_reference_id` when a source-declared
    target plugin id is not projected into the matching drilldown row field.
  - Registers the target plugin replay audit as source evidence.
  - Registers this N2.439 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Mirrors the target-plugin ledger and projection map.
  - Locks runtime rows and exported payload rows so every replayed target plugin
    id is ledger-known and projected into `capability_ids`.
  - Adds a negative audit fixture for
    `missing_projection_target_plugin_reference_id`.
  - Updates source evidence readiness expectations to `105/105 ready`.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to
    `drilldown_sources=105/105 ready`.

## Acceptance View

The drilldown visible-reference contract now additionally covers:

- Projected external handoff target plugin ids covered by
  `scene_external_handoff_contract_audit.rows[*].target_plugin_id`.
- Projected guarded-completion target plugin ids covered by the same external
  handoff target-plugin ledger.
- Clear separation between plugin/manual gate ids, gate entry plugin ids, and
  concrete external handoff target plugin ids.

Current source evidence readiness target for N2.439 was `105/105 ready`, with
`0 missing`. N2.440 supersedes the active target to `107/107 ready` by adding
formula/output/watermark capability-row replay.

## Boundary

N2.439 verifies target plugin visibility and ledger membership in the scene
matrix. It does not validate plugin installation, execution, marketplace
availability, or professional review completion; those remain outside the core
formatter and are represented as retained boundary handoff obligations.

The formula/output/watermark scenario parameter split is now closed by N2.440.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- Quick build/audit check passed with
  `passed 37 37 553 105 105 0 0`.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with
  `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed with
  `drilldown_sources=105/105 ready`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with
  `7 passed`.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=105/105 ready`
- `Source evidence: 105 / 105 ready (0 missing)`
- `missing_projection_target_plugin_reference_id`
- `unknown_projection_target_plugin_reference_id`
