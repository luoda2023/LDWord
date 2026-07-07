# Assets Panel Step 13: Question Library Editor Presenter Extraction

Date: 2026-07-06

## Goal

Move the local question-figure library metadata editor/save behavior out of
`AssetsPanel`, while keeping the actual metadata mutation and history-record
construction in `src.services.material_assets`.

This continues the Step 12 extraction: the table presenter owned row display
and selection; this step makes the editor side follow the same boundary.

## Files Updated

- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets/question_library_presenter.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_assets_question_library_presenter.py`
- `tests/test_material_asset_services.py`

## What Moved

`QuestionFigureLibraryPresenterMixin` now owns:

- `_refresh_question_figure_library_editor`
- `_save_question_figure_library_metadata`

`AssetsPanel` still exposes the same methods through inheritance, so existing
UI call sites and tests do not need to change.

## Service Boundary

The non-UI metadata logic now lives in
`src.services.material_assets.question_library`:

- `apply_question_figure_library_metadata`
- `normalize_asset_item_payloads`
- `asset_item_payload`
- `normalized_asset_item_history_records`
- `question_figure_library_metadata_history_record`
- `question_figure_library_metadata_change_summary`
- `set_optional_metadata_value`

The presenter reads widgets, calls the service, persists the selected profile,
and refreshes UI state. It no longer owns the rules for field aliases,
structured payload normalization, or metadata history rows.

## Behavior Covered

- `source`, `asset_id`, and `alt_text` edits are applied to matching local
  question-figure payloads.
- Legacy field aliases such as `assetId` and `alt` are normalized to canonical
  keys on save.
- A `question_figure_library_metadata_update` history record is generated only
  when metadata changes.
- Existing history records are normalized before appending new records.
- Structure tests assert that `AssetsPanel` does not directly own the local
  question-library table/editor methods.

## Boundary

This step still intentionally excludes:

- remote writeback
- master-data sync
- governance tables
- subscription drift and approval queues
- version rollback and cross-version promotion flows

Those remain outside the local material core and should be extracted only as
frozen enterprise/governance presenters after the local question-figure surface
is stable.

## Next Step

The next healthy move is to reduce the remaining direct uses of
`_normalized_asset_item_history_records` inside `assets_panel.py` by grouping
enterprise/history projection flows behind explicit service or presenter
modules. The safe order is:

1. Keep local question-figure presenters stable.
2. Inventory remaining history-record call sites by domain.
3. Extract one domain at a time, starting with low-risk read-only projections.
4. Leave remote writeback/governance flows frozen until their API boundary is
   named and tested.
