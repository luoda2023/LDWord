# Assets Panel Step 16: Master Version Projection Service

Date: 2026-07-06

## Goal

Move the read-only cross-package question-figure master-version table projection
out of `AssetsPanel`, while leaving all plan, promotion, registry sync,
subscription lock, and subscription change callback actions in place.

This continues the structural-health work after Step 15. The master-version
table is the safest enterprise-adjacent next step because its first layer is a
pure projection over profile metadata and local history records.

## Files Updated

- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_material_asset_services.py`

## What Moved

The old `_question_figure_library_master_version_entries` implementation was
removed from `assets_panel.py`. The same legacy name now points to the service
function:

- `question_figure_library_master_version_entries`

The service also owns the read helpers needed by that projection:

- `asset_items_from_payloads`
- `question_figure_library_master_version_plan_for`
- `question_figure_library_master_version_promotion_for`
- `question_figure_library_master_registry_sync_for`
- `question_figure_library_master_subscription_lock_for`
- `question_figure_library_master_subscription_change_callback_for`
- `question_figure_master_version_diff_fields`
- `question_figure_master_version_has_version_statement`
- `question_figure_master_version_package_summary`
- `question_figure_master_version_summary`
- `question_figure_master_version_diff_summary`
- `question_figure_master_version_status_label`

## Boundary

This step intentionally keeps these action paths in `AssetsPanel`:

- `_record_question_figure_library_master_version_plan_row`
- `_execute_question_figure_library_master_version_promotion_row`
- registry sync execution
- subscription lock execution
- subscription change callback execution

Those paths still mutate profiles, write history records, or call remote
connectors. They need a separate action-service extraction after the projection
boundary is stable.

## Behavior Covered

- Cross-profile question figures are grouped by `source/asset_id`.
- Only assets shared across at least two packages produce master-version rows.
- Version, ETag, updated time, alt text, and reference drift are summarized.
- Plan/promotion/registry/subscription status is read from normalized local
  `asset_item_history`.
- Existing UI architecture tests still cover the full plan and promotion flow
  using the service projection.

## Next Step

The next healthy move is to extract the master-version table presenter itself,
while still leaving action methods in `AssetsPanel`. That would move table row
rendering and row lookup into a presenter, but keep plan/promotion/remote
execution methods untouched.
