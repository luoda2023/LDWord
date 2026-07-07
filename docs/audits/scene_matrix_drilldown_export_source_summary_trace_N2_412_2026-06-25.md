# Scene Matrix Drilldown Export Source Summary Trace N2.412

## Purpose

N2.410 and N2.411 aligned source evidence readiness across payload, Release Gate terminal summary, and Summary cards. The Markdown export still had a narrower header: it showed status, drilldown readiness, row coverage, and filters, while source evidence readiness only appeared as a long detail section.

N2.412 adds the same ready/total source evidence lens to exported Markdown.

## Implemented Chain

- `scripts/export_scene_matrix_drilldown.py`
  - Markdown exports now print the source evidence ready/total count in the header summary.
  - JSON exports already carry `source_evidence_count`, `ready_source_evidence_count`, and `missing_source_evidence_count` in `report.to_payload()`.
- `src/config/scene_matrix_drilldown.py`
  - Registers the export source-summary projection as source evidence.
  - Registers this N2.412 plan as source evidence.
- `tests/test_scene_matrix_drilldown.py`
  - Locks report and payload source evidence counts.
  - Locks the Markdown header marker.
  - Locks Summary visibility for the new export source-summary evidence ids.
- `tests/test_scene_matrix_dashboard.py`
  - Updates the Release Gate terminal summary assertion for the current drilldown source evidence total.

## Acceptance View

The source evidence readiness lens is visible across all drilldown surfaces:

- Payload: source evidence count, ready source evidence count, and missing source evidence count.
- Summary card: ready/total count, with `0 missing` and all evidence ids in detail.
- Release Gate terminal summary: `drilldown_sources=... ready`.
- Markdown export: `Source evidence: ... ready (0 missing)`.

This prevents an exported Markdown handoff from losing the source evidence readiness signal that reviewers see in the app and Release Gate.

## Current Lineage

N2.412 introduced the Markdown export source evidence header at `51 / 51 ready`. N2.413 then added the JSON export source-summary contract, N2.414 added payload/list consistency tests, N2.415 added source-evidence unique-id checks, N2.416 added drilldown item/row unique-id checks, N2.417 added item source evidence checks, N2.418 added row source evidence checks, N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 added action/capability projection profiles, N2.426 added projection test-reference checks, N2.427 added projection source-reference checks, and N2.428 added projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `51/51` entries below as the historical verification snapshot for N2.412; use the latest Release Gate output and N2.428 for the current total.

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
- `drilldown_sources=51/51 ready`
- `Source evidence: 51 / 51 ready (0 missing)`
- `count_delivery_receipts=4/4`
- `maturity_l5_receipts=6/6`
- `acceptance_receipts=2/2`
