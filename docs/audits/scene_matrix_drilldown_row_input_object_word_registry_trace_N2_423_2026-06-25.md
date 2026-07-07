# Scene Matrix Drilldown Row Input Object Word Registry Trace N2.423

## Purpose

N2.422 made `material_schema_ids` auditable as material references. The next row-level reference fields with clear authoritative sources are:

- `input_source_ids`
- `render_source_ids`
- `object_preflight_target_ids`
- `word_risk_surface_ids`

These fields are not generic labels. They point to InputSourceProfile planning, delivery render targets, ObjectPreflight scan targets, and Word/OOXML risk surfaces. N2.423 makes those references blocking-audited instead of merely searchable in the drilldown payload.

The release invariant is that every row value in these four fields must resolve to a corresponding source audit:

- Input source ids resolve to `scene_input_source_audit` family/pack/format rows.
- Render source ids resolve to `scene_input_source_audit` render source or target template rows.
- Object preflight target ids resolve to `scene_object_preflight_action_audit` target/family rows.
- Word risk surface ids resolve to `scene_word_risk_closure_audit`, `scene_object_preflight_action_audit`, or `scene_fixed_layout_profile_audit`.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_input_render_reference_ids()` for input formats, structured formats, boundary input sources, render sources, and target templates.
  - Adds `_object_preflight_reference_ids()` for object preflight target ids and family-level recommended/actual/block/skip targets.
  - Adds `_word_risk_surface_reference_ids()` for Word risk closure surfaces, object preflight-linked surfaces, and fixed-layout surfaces.
  - Emits `unknown_row_input_source_id` for unknown `input_source_ids`.
  - Emits `unknown_row_render_source_id` for unknown `render_source_ids`.
  - Emits `unknown_row_object_preflight_target_id` for unknown `object_preflight_target_ids`.
  - Emits `unknown_row_word_risk_surface_id` for unknown `word_risk_surface_ids`.
  - Registers the row input/object/Word registry audit as source evidence.
  - Registers this N2.423 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime and payload `input_source_ids` against the input-source reference set.
  - Locks runtime and payload `render_source_ids` against the render-source reference set.
  - Locks runtime and payload `object_preflight_target_ids` against the object-preflight reference set.
  - Locks runtime and payload `word_risk_surface_ids` against the Word risk surface reference set.
  - Adds a negative audit fixture for all four unknown row reference issue kinds.
  - Updates source evidence readiness expectations to `73/73 ready` for the N2.423 historical snapshot.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=73/73 ready` for the N2.423 historical snapshot.

## Acceptance View

The drilldown visible-reference contract now covers:

- Unique source evidence ids.
- Unique drilldown item ids.
- Unique row ids inside each drilldown.
- Item source ids covered by source evidence.
- Row source ids covered by source evidence.
- Row source ids aligned with parent item source ids.
- Row pack ids covered by the scene coverage pack registry.
- Row family ids covered by the planned scene family registry.
- Row request cell ids covered by the request-cell fixture registry.
- Row fixture ids covered by the scene sample fixture registry.
- Row count profile ids covered by the CountProfile registry.
- Row delivery references covered by DeliveryPreset or delivery execution output-signal evidence.
- Row material references covered by MaterialSchema registry/audit ids or MaterialRepairFlow material signal ids.
- Row input sources covered by InputSource audit evidence.
- Row render sources covered by InputSource render/template evidence.
- Row object preflight targets covered by ObjectPreflight action evidence.
- Row Word risk surfaces covered by Word risk, ObjectPreflight, or fixed-layout evidence.

N2.424 later added plugin/risk/maturity governance row references, N2.425 added action/capability projection profiles, N2.426 added projection test-reference checks, N2.427 added projection source-reference checks, and N2.428 added projection surface-reference checks. The current source evidence readiness target is `83/83 ready`, with `0 missing`.

## Boundary

N2.423 intentionally does not audit `action_behavior_ids`, `capability_ids`, `maturity_gap_domain_ids`, `plugin_gate_ids`, or `risk_domain_ids`. Those fields are broader behavior/capability projection carriers and need their own scoped registries before they can be blocked safely.

## Verification

Executed verification commands:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py` passed.
- `python -m pytest tests/test_release_shell.py -q` passed with `9 passed`.
- `python -m pytest tests/test_scene_matrix_drilldown.py -q` passed with `7 passed`.
- `python -m pytest tests/test_scene_matrix_dashboard.py -q` passed with `6 passed`.
- `python scripts\verify_scene_matrix_release_gate.py` passed.

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=73/73 ready`
- `Source evidence: 73 / 73 ready (0 missing)`
- `unknown_row_input_source_id`
- `unknown_row_render_source_id`
- `unknown_row_object_preflight_target_id`
- `unknown_row_word_risk_surface_id`
