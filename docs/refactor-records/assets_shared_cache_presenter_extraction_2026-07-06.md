# Assets Panel Step 10: Shared Cache Presenter Extraction

Date: 2026-07-06

## Goal

Reduce the size and responsibility of `AssetsPanel` by moving the
question-figure shared-cache UI table coordination into a dedicated presenter
mixin.

## Files Added

- `src/ui/panels/assets/cache_presenter.py`
- `tests/test_assets_cache_presenter.py`

## Files Updated

- `src/ui/panels/assets_panel.py`

## What Moved

The following methods now live on
`QuestionFigureSharedCachePresenterMixin`:

- `_refresh_question_figure_shared_cache_dirs_table`
- `_refresh_question_figure_shared_cache_tasks_table`
- `_refresh_question_figure_shared_cache_trends_table`
- `_question_figure_shared_cache_task_scopes`
- `_refresh_question_figure_shared_cache_entries_table`
- `_refresh_question_figure_shared_cache_metrics_table`
- `_refresh_question_figure_shared_cache_cleanup_table`
- `_refresh_question_figure_shared_cache_cleanup_confirmation`
- `_record_question_figure_shared_cache_cleanup_confirmation`
- `_apply_question_figure_shared_cache_cleanup_execution_fields`
- `_selected_question_figure_shared_cache_dir`
- `_open_question_figure_shared_cache_dir`
- `_on_question_figure_shared_cache_dir_selection_changed`
- `_on_question_figure_shared_cache_entry_selection_changed`

`AssetsPanel` now inherits `QuestionFigureSharedCachePresenterMixin`, so the
external method surface remains compatible.

## Boundary

This presenter coordinates UI widgets and delegates data projection to
`src.services.material_assets`.

It must not become a place for:

- Remote writeback.
- Enterprise auth.
- Master-data governance.
- Subscription drift recovery.
- Non-question asset-family governance.

## Guardrails

`tests/test_assets_cache_presenter.py` verifies that:

- `AssetsPanel` inherits the shared-cache presenter mixin.
- The shared-cache UI methods are defined on the mixin.
- The same methods are no longer defined directly on `AssetsPanel`.

## Next Step

Continue shrinking `assets_panel.py` by extracting the local question-figure
table/preview presenter next. That slice should depend on
`src.services.material_assets` and remain separate from enterprise remote
writeback tables.
