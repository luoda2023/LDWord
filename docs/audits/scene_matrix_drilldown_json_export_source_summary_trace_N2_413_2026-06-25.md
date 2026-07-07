# Scene Matrix Drilldown JSON Export Source Summary Trace N2.413

## Purpose

N2.412 made source evidence readiness visible in Markdown export headers. JSON export already used `report.to_payload()`, so the source evidence counts were present, but the export test did not lock that contract. A future JSON-specific refactor could accidentally drop the counts while leaving runtime reports and Markdown intact.

N2.413 turns JSON source evidence readiness into an explicit tested handoff contract.

## Implemented Chain

- `scripts/export_scene_matrix_drilldown.py`
  - JSON export continues to emit `json.dumps(report.to_payload(), ensure_ascii=False, indent=2)`.
- `src/config/scene_matrix_drilldown.py`
  - Registers the JSON export source-summary projection as source evidence.
  - Registers this N2.413 plan as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks JSON export source evidence counts.
  - Locks JSON export source evidence visibility for `scene_matrix_drilldown_export_json_source_summary_projection`.
  - Updates Summary, Release Gate payload, and Markdown assertions for the current source evidence set.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion for drilldown source evidence readiness.

## Acceptance View

The source evidence readiness lens is now explicit in both export formats:

- JSON export: counts and source evidence ids are present in the payload and tested.
- Markdown export: header shows source evidence ready/total with zero missing.
- Summary card: ready/total, with `0 missing` and all evidence ids.
- Release Gate terminal summary: `drilldown_sources=... ready`.

This closes the remaining export-format asymmetry for source evidence readiness.

## Current Lineage

N2.413 introduced the JSON export source evidence readiness contract at `53/53`. N2.414 then added payload/list consistency tests, N2.415 added source-evidence unique-id checks, N2.416 added drilldown item/row unique-id checks, N2.417 added item source evidence checks, N2.418 added row source evidence checks, N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 added action/capability projection profiles, N2.426 added projection test-reference checks, N2.427 added projection source-reference checks, and N2.428 added projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `53/53` entries below as the historical verification snapshot for N2.413; use the latest Release Gate output and N2.428 for the current total.

## Verification

Executed on 2026-06-25:

- `python -m py_compile scripts/export_scene_matrix_drilldown.py src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py`
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
- `drilldown_sources=53/53 ready`
- `Source evidence: 53 / 53 ready (0 missing)`
- `source_evidence_count=53`
- `ready_source_evidence_count=53`
- `count_delivery_receipts=4/4`
- `maturity_l5_receipts=6/6`
- `acceptance_receipts=2/2`
