# Assets Panel Step 14: Question Library History Presenter Extraction

Date: 2026-07-06

## Goal

Move local question-figure library version history and rollback behavior out of
`AssetsPanel`, while keeping remote writeback and enterprise governance frozen
outside this local-material extraction.

This follows Step 13: metadata editor/save moved into the local library
presenter, and this step moves the matching local history surface.

## Files Added

- `src/ui/panels/assets/question_library_history_presenter.py`

## Files Updated

- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_assets_question_library_presenter.py`
- `tests/test_material_asset_services.py`

## What Moved

`QuestionFigureLibraryHistoryPresenterMixin` now owns:

- `_refresh_question_figure_library_version_history_table`
- `_on_question_figure_library_version_history_selection_changed`
- `_select_question_figure_library_version_history_row`
- `_rollback_question_figure_library_version_history_row`

`AssetsPanel` inherits the mixin, so existing callers still use the same method
names through the panel instance.

## Service Boundary

The non-UI history and rollback rules now live in
`src.services.material_assets.question_library`:

- `question_figure_library_version_history_entries`
- `rollback_question_figure_library_metadata`
- `question_figure_library_metadata_rollback_record`
- `question_figure_history_changed_fields`
- `question_figure_history_record_matches_current`
- `question_figure_history_record_question_row`
- `question_figure_history_fields_label`

The presenter reads the selected table row, calls the rollback service, persists
the selected profile, refreshes the summary, and updates selection/status text.
It does not decide which fields are recoverable or how rollback records are
serialized.

## Behavior Covered

- Version history rows are projected newest-first from normalized local
  `asset_item_history`.
- Local rollback restores `source`, `asset_id`, and `alt_text` only when the
  current metadata still matches the selected history record's `*_after` state.
- Rollback appends a `question_figure_library_metadata_rollback` record with a
  `rollback_from_changed_at` link to the source update.
- Structure tests assert that `AssetsPanel` does not directly own the local
  version-history presenter methods.

## Boundary

This extraction intentionally does not move or redesign:

- remote writeback handoff/execution/conflict handling
- remote rollback and second compensation
- master-data version plans
- subscription drift queues
- bulk governance/SLA/background-worker tables

Those remain enterprise/governance surfaces and should be extracted behind a
separate frozen boundary, not folded into the local question-figure presenter.

## Next Step

The next healthy step is to inventory remaining
`_normalized_asset_item_history_records` call sites by domain and split the
first read-only enterprise projection into its own presenter/service pair.
Candidate boundaries:

- remote writeback table projection, without execution actions
- master version table projection, without subscription drift actions
- governance issue table projection, without batch governance mutations

Pick one domain, move projection first, then move actions only after its service
boundary has explicit tests.
