# Scene Matrix Drilldown Action Capability Projection Profile Trace N2.425

## Purpose

N2.424 closed plugin/risk/maturity governance references. The remaining broad drilldown fields are:

- `action_behavior_ids`
- `capability_ids`

These fields are intentionally mixed projection fields. Current values include statuses, behavior labels, report markers, source ids, test ids, function names, payload keys, OOXML tags, UI surfaces, evidence ids, paths, and derived receipt markers. A single value registry would be inaccurate and would either miss real sources or block valid source-specific projections.

N2.425 therefore adds a source-aware projection profile layer. Every drilldown that emits `action_behavior_ids` or `capability_ids` must declare:

- the source audit it belongs to;
- the source row fields used to populate `action_behavior_ids`;
- the token kinds represented by those action values;
- the source row fields used to populate `capability_ids`;
- the token kinds represented by those capability values.

The release invariant is that no drilldown row can expose action/capability projection values without an explicit projection profile.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `SceneMatrixDrilldownProjectionProfile`.
  - Adds `SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES` for all current drilldown items that emit action or capability projection values.
  - Adds `SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP`.
  - Emits `missing_action_behavior_projection_profile` when a row exposes `action_behavior_ids` without a profile that declares action source fields.
  - Emits `missing_capability_projection_profile` when a row exposes `capability_ids` without a profile that declares capability source fields.
  - Emits `projection_profile_source_mismatch` when a profile source no longer matches the drilldown item source.
  - Registers the action/capability projection profile audit as source evidence.
  - Registers this N2.425 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks every item with action projection rows to a profile with action source fields and token kinds.
  - Locks every item with capability projection rows to a profile with capability source fields and token kinds.
  - Adds a negative audit fixture for missing action/capability projection profiles.
  - Updates source evidence readiness expectations to `77/77 ready` for the N2.425 historical snapshot.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=77/77 ready` for the N2.425 historical snapshot.

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
- Row plugin/manual gate ids covered by the PluginManualGate registry.
- Row risk domain ids covered by registered PluginManualGate risk domains.
- Row maturity gap references covered by product maturity domains or retained boundary gap evidence.
- Row action/capability projections covered by source-aware projection profiles.

N2.426 later added projected `test_*` value-level registry checks, and N2.427
added projected source-id field-replay checks. N2.428 added projected runtime,
UI, and report surface field-replay checks. Together they supersede
the current source evidence readiness target to `83/83 ready`, with `0 missing`.
Treat the `77/77` entries below as the historical verification snapshot for
N2.425; use the latest Release Gate output and N2.428 for the current total.

## Boundary

N2.425 is a typing/provenance gate, not a full value-level registry for `action_behavior_ids` and `capability_ids`. N2.426 starts the value-level split with stable `test_*` references. Remaining safe splits still need token-kind-specific registries, such as source ids, paths, UI surface ids, report surface ids, and evidence ids.

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
- `drilldown_sources=77/77 ready`
- `Source evidence: 77 / 77 ready (0 missing)`
- `missing_action_behavior_projection_profile`
- `missing_capability_projection_profile`
