# Assets Question Library Master Governance Record Lookup Service Extraction

Date: 2026-07-06

## Scope

This step moved master-governance history lookup helpers out of `src/ui/panels/assets_panel.py` and into `src/services/material_assets/question_library.py`.

New service functions:

- `question_figure_library_master_registry_sync_record_for_profiles`
- `question_figure_library_master_subscription_lock_record_for_profiles`
- `question_figure_library_master_subscription_change_callback_record_for_profiles`

The panel now also uses service aliases for existing single-history lookup helpers:

- `question_figure_library_master_version_plan_for`
- `question_figure_library_master_version_promotion_for`
- `question_figure_library_master_registry_sync_for`
- `question_figure_library_master_subscription_lock_for`
- `question_figure_library_master_subscription_change_callback_for`

## Boundary

The service now owns deterministic governance record lookup:

- latest matching master-data record by action
- optional success-only status filtering
- cross-profile search over normalized `asset_item_history`

The panel still owns workflow coordination:

- deciding which action the user triggered
- writing new records to affected profiles
- refreshing summary/table state
- showing status messages

## Why This Helps

The previous panel code duplicated the same action-name and success-status matching rules already used by the service-level master-version projection. Centralizing these lookups prevents drift where the table projection might consider a record complete while a panel action searches for it differently.

This is a small but important cleanup after extracting registry sync, subscription lock, and subscription callback payload/record builders.

## Verification

Added service tests for:

- success-only filtering on failed registry sync attempts
- cross-profile registry sync lookup
- cross-profile subscription lock lookup
- cross-profile subscription change callback lookup
- facade export and legacy alias identity
