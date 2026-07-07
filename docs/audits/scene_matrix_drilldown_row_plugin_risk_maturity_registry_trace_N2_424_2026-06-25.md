# Scene Matrix Drilldown Row Plugin Risk Maturity Registry Trace N2.424

## Purpose

N2.423 made input/render/object/Word references auditable. The next row-level governance references are:

- `plugin_gate_ids`
- `risk_domain_ids`
- `maturity_gap_domain_ids`

`plugin_gate_ids` and `risk_domain_ids` are registry-backed by `PluginManualGate`. `maturity_gap_domain_ids` is a historical field name: current drilldown rows use it for both product maturity gap domains such as `boundary_gate` and retained boundary gap ids such as `real plugin ecosystem` or `finance plugin handoff`. N2.424 therefore audits it as a maturity gap reference set instead of a pure domain-only set.

The release invariant is that every row value in these three fields must resolve to a corresponding governance source:

- Plugin gate ids resolve to `plugin_manual_gate.py`.
- Risk domain ids resolve to `PluginManualGate.risk_domain_ids`.
- Maturity gap references resolve to `PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS`, product maturity row `gap_domain_ids`, guarded completion retained gaps, boundary subject dossier retained gaps, external handoff gap ids, boundary release envelope gap ids, or retained gap exit criteria gap ids.

## Implemented Chain

- `src/config/scene_matrix_drilldown.py`
  - Adds `_plugin_gate_reference_ids()` from `list_plugin_manual_gates()`.
  - Adds `_risk_domain_reference_ids()` from `PluginManualGate.risk_domain_ids`.
  - Adds `_maturity_gap_reference_ids()` from product maturity domains and retained boundary gap evidence.
  - Emits `unknown_row_plugin_gate_id` for unknown `plugin_gate_ids`.
  - Emits `unknown_row_risk_domain_id` for unknown `risk_domain_ids`.
  - Emits `unknown_row_maturity_gap_reference_id` for unknown `maturity_gap_domain_ids`.
  - Registers the row plugin/risk/maturity registry audit as source evidence.
  - Registers this N2.424 trace as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks runtime and payload `plugin_gate_ids` against plugin/manual gate references.
  - Locks runtime and payload `risk_domain_ids` against registered plugin/manual risk domains.
  - Locks runtime and payload `maturity_gap_domain_ids` against product maturity domains plus retained boundary gap references.
  - Adds a negative audit fixture for all three unknown row reference issue kinds.
  - Updates source evidence readiness expectations to `75/75 ready` for the N2.424 historical snapshot.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion to `drilldown_sources=75/75 ready` for the N2.424 historical snapshot.

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

N2.425 later added action/capability projection profiles, N2.426 added projection test-reference checks, N2.427 added projection source-reference checks, and N2.428 added projection surface-reference checks. Together they supersede the current source evidence readiness target to `83/83 ready`, with `0 missing`.

## Boundary

N2.424 intentionally leaves `action_behavior_ids` and `capability_ids` outside blocking audit. They carry a broader mix of behavior states, report markers, source ids, capability ids, payload fields, test ids, and evidence ids. They need either a typed split or a source-aware capability reference registry before a blocking audit can be faithful.

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
- `drilldown_sources=75/75 ready`
- `Source evidence: 75 / 75 ready (0 missing)`
- `unknown_row_plugin_gate_id`
- `unknown_row_risk_domain_id`
- `unknown_row_maturity_gap_reference_id`
