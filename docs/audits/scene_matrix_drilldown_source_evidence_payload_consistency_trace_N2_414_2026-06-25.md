# Scene Matrix Drilldown Source Evidence Payload Consistency Trace N2.414

## Purpose

N2.413 made JSON export source evidence readiness a tested contract, but the tests still primarily checked count fields and selected source ids. A payload could theoretically keep `source_evidence_count` correct while dropping rows from the `source_evidence` list or drifting ready/missing status totals.

N2.414 closes that count/list consistency gap.

The key invariant is payload list length parity: the exported source evidence list length must match the exported count, and the ready/missing row totals must match their count fields.

## Implemented Chain

- `tests/test_scene_matrix_drilldown.py`
  - Locks `len(report.source_evidence) == report.source_evidence_count`.
  - Locks `len(payload["source_evidence"]) == payload["counts"]["source_evidence_count"]`.
  - Locks ready source evidence rows against `ready_source_evidence_count`.
  - Locks non-ready source evidence rows against `missing_source_evidence_count`.
  - Applies the same consistency checks to the JSON export payload.
- `src/config/scene_matrix_drilldown.py`
  - Registers the payload consistency test surface as source evidence.
  - Registers this N2.414 plan as source evidence.

## Acceptance View

The source evidence readiness contract now covers both counts and payload contents:

- Report object: `55/55 ready`, `0 missing`, and source evidence list length matches the count.
- JSON payload: source evidence list length, ready rows, and missing rows match the exported counts.
- Summary card: `55/55 ready`, with `0 missing` and all evidence ids.
- Markdown export: `Source evidence: 55 / 55 ready (0 missing)`.
- Release Gate terminal summary: `drilldown_sources=55/55 ready`.

This prevents a payload from looking healthy through summary counts while silently losing source evidence rows.

## Current Lineage

N2.414 introduced payload/list consistency at `55/55`. N2.415 then added source evidence id uniqueness checks, N2.416 added drilldown item/row unique-id checks, N2.417 added item source evidence checks, N2.418 added row source evidence checks, N2.419 added row pack/family registry checks, N2.420 added row request/fixture registry checks, N2.421 added row count/delivery registry checks, N2.422 added row material-reference registry checks, N2.423 added row input/object/Word registry checks, N2.424 added row plugin/risk/maturity registry checks, N2.425 added action/capability projection profiles, N2.426 added projection test-reference checks, N2.427 added projection source-reference checks, and N2.428 added projection surface-reference checks, superseding the current count to `83/83 ready`. Treat the `55/55` entries below as the historical verification snapshot for N2.414; use the latest Release Gate output and N2.428 for the current total.

## Verification

Executed on 2026-06-25:

- `python -m py_compile src/config/scene_matrix_drilldown.py tests/test_scene_matrix_drilldown.py tests/test_scene_matrix_dashboard.py`
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
- `drilldown_sources=55/55 ready`
- `Source evidence: 55 / 55 ready (0 missing)`
- `source_evidence_count=55`
- `ready_source_evidence_count=55`
- `missing_source_evidence_count=0`
