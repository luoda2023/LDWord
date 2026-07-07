# Assets Question Library Master Version Promotion Helpers Service Extraction

Date: 2026-07-06

## Scope

This step moved pure master-version promotion helper logic out of `src/ui/panels/assets_panel.py` and into `src/services/material_assets/question_library.py`.

Moved service functions:

- `question_figure_master_version_promoted_metadata`
- `asset_metadata_reference_patch`
- `question_figure_master_version_changed_fields`

Related master-version rule helpers are now also exposed through the service package:

- `question_figure_master_version_canonical_occurrence`
- `question_figure_master_version_canonical_sort_key`
- `natural_version_sort_key`

## Boundary

The panel still owns the stateful promotion action because it mutates `EntityProfile.asset_items`, refreshes UI state, and writes execution history. The service now owns the deterministic data rules:

- choose promoted metadata values from the canonical occurrence
- normalize reference URL/cache fields into a patch
- compare before/after metadata and report changed fields
- select and sort canonical master-version candidates

## Why This Helps

Before this extraction, the panel had duplicate master-version rule code while the service already produced master-version governance entries. That made drift likely: a table row could be calculated with one rule set, while promotion could execute with another.

After this extraction, projection, planning, and promotion all use the same service-level helper rules. `assets_panel.py` is thinner, and the metadata promotion logic is directly unit-testable without creating Qt widgets.

## Verification

Added service tests for:

- promoted metadata values from canonical metadata
- reference patch normalization for URL/cache fields
- changed-field detection for version, ETag, updated time, alt text, and reference
- public `material_assets` facade exports matching `question_library`

Next candidates for extraction:

- pure master-version promotion execution record builder
- registry sync payload and response normalization
- subscription lock/change-callback payload builders
