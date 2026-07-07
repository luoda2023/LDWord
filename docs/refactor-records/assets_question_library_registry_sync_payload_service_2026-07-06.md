# Assets Question Library Registry Sync Payload Service Extraction

Date: 2026-07-06

## Scope

This step moved pure registry-sync data helpers from `src/ui/panels/assets_panel.py` into `src/services/material_assets/question_library.py`.

New service functions:

- `question_figure_master_registry_sync_payload`
- `question_figure_master_registry_sync_canonical_payload`
- `question_figure_master_registry_sync_affected_items`
- `build_question_figure_library_master_registry_sync_base_record`
- `registry_sync_response_value`

The panel also now uses the existing service-level `question_figure_master_registry_sync_endpoint` instead of keeping a duplicate endpoint scanner.

Legacy private names are retained as aliases for older panel code and tests.

## Boundary

The service now owns deterministic registry-sync data shape:

- outbound operation payload
- canonical master-version payload
- affected item rows
- durable base execution record
- response-field fallback lookup
- registry sync endpoint lookup

The panel still owns side effects:

- HTTP request construction and execution
- auth header preparation
- exception handling around `urlopen`
- success/failure status label updates
- profile metadata mutation after a successful registry sync

## Why This Helps

Registry sync is part of the remote-writeback governance chain. Before this extraction, payload shape, record shape, and response normalization lived beside UI refresh logic and network code. Moving the pure pieces into the material asset service makes the remote-writeback contract testable without Qt or network calls.

This keeps the next extraction path clear: the HTTP connector can later be split into a gateway/service boundary, while the panel remains responsible only for user interaction and state refresh.

## Verification

Added service tests for:

- registry-sync request payload shape
- canonical payload and affected item projection
- base execution record JSON fields
- registry response fallback lookup
- endpoint lookup through occurrence metadata
- facade export and legacy alias identity
