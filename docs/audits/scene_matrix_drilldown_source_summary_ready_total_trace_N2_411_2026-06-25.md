# Scene Matrix Drilldown Source Summary Ready Total Trace N2.411

## Purpose

N2.409 made the Summary card list real source evidence ids, and N2.410 made the Release Gate terminal summary expose drilldown source evidence readiness. The Summary card still used `0 missing` as its primary value, so the UI showed absence of missing evidence but not the ready/total evidence volume.

N2.411 aligns the Summary card with the Release Gate readiness lens.

## Implemented Chain

- `src/ui/panels/scene_summary_projection.py`
  - `scene_matrix_drilldown_sources.value` now uses the ready/total source evidence count.
  - `scene_matrix_drilldown_sources.detail` keeps the full source evidence id list and prefixes `0 missing`.
- `src/config/scene_matrix_drilldown.py`
  - Registers the Summary ready/total projection as source evidence.
  - Registers this N2.411 plan as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks report and payload source evidence counts.
  - Locks the Summary card value and detail.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion for the current drilldown source evidence total.

## Acceptance View

The drilldown source evidence readiness is now consistent across surfaces:

- Payload: source evidence count, ready source evidence count, and missing source evidence count.
- Summary card: ready/total count, with `0 missing` and all evidence ids in detail.
- Release Gate terminal summary: `drilldown_sources=... ready`.

This prevents a reviewer from seeing only that no evidence is missing while losing the size and readiness of the full evidence set.

## Current Lineage

N2.411 introduced the Summary card ready/total view at `49/49`. Later N2.412 through N2.428 added export, payload-consistency, source-evidence unique-id, drilldown item/row unique-id, item source evidence, row source evidence, row pack/family registry, row request/fixture registry, row count/delivery registry, row material-reference registry, row input/object/Word registry, row plugin/risk/maturity registry, action/capability projection profile records, projection test-reference records, projection source-reference records, and projection surface-reference records and superseded the current count to `83/83 ready`. Treat the `49/49` entries below as the historical verification snapshot for N2.411; use the latest Release Gate output and N2.428 for the current total.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/ui/panels/scene_summary_projection.py src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py`
- `python -m pytest tests/test_scene_matrix_drilldown.py -q`
  - `6 passed`
- `python -m pytest tests/test_scene_matrix_dashboard.py -q`
  - `6 passed`
- `python -m pytest tests/test_release_shell.py -q`
  - `9 passed`
- `python scripts\verify_scene_matrix_release_gate.py`
  - `Scene matrix release gate: passed`

Release markers:

- `drilldowns=37/37`
- `drilldown_rows=553/553`
- `drilldown_sources=49/49 ready`
- `count_delivery_receipts=4/4`
- `maturity_l5_receipts=6/6`
- `acceptance_receipts=2/2`
