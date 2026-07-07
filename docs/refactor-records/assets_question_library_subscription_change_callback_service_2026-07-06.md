# Assets Question Library Subscription Change Callback Service Extraction

Date: 2026-07-06

## Scope

This step moved pure subscription-change callback helpers from `src/ui/panels/assets_panel.py` into `src/services/material_assets/question_library.py`.

New service functions:

- `question_figure_master_subscription_change_callback_result`
- `question_figure_master_subscription_change_remote_metadata`
- `question_figure_master_subscription_change_local_metadata`
- `question_figure_master_subscription_change_diff_fields`
- `subscription_change_payload_value`
- `subscription_change_payload_candidates`
- `build_question_figure_library_master_subscription_change_callback_base_record`

The panel now also uses the service-level `question_figure_master_subscription_change_callback_endpoint` instead of keeping a duplicate endpoint scanner.

Legacy private names are retained as aliases for older panel code and tests.

## Boundary

The service now owns deterministic callback data shape:

- endpoint lookup
- callback payload candidate traversal
- remote metadata extraction
- local canonical metadata extraction
- remote/local diff fields
- callback result row
- durable base execution record

The panel still owns side effects:

- HTTP GET execution
- auth header preparation
- HTTP and JSON exception handling
- status label updates
- profile metadata mutation after successful callback processing

## Why This Helps

The remote governance chain now has service-level data contracts for registry sync, subscription lock, and subscription change callback. This removes another durable record shape from the Qt panel and leaves the panel closer to a coordinator instead of a business-rule container.

The next high-value extraction point is the remaining profile-history lookup helpers and small state mutation helpers around remote governance.

## Verification

Added service tests for:

- subscription change callback endpoint lookup
- callback result normalization
- remote/local metadata diff detection
- callback payload value fallback traversal
- base execution record fields and JSON affected items
- facade export and legacy alias identity
