# Assets Panel Step 12: Question Library Presenter Extraction

Date: 2026-07-06

## Goal

Extract the local question-figure library metadata table and row-selection
behavior from `AssetsPanel` without touching remote writeback or governance
tables.

## Files Added

- `src/services/material_assets/question_library.py`
- `src/ui/panels/assets/question_library_presenter.py`
- `tests/test_assets_question_library_presenter.py`

## Files Updated

- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_material_asset_services.py`

## What Moved

`QuestionFigureLibraryPresenterMixin` now owns:

- `_refresh_question_figure_library_table`
- `_on_question_figure_library_selection_changed`
- `_select_question_figure_library_row`

`AssetsPanel` inherits this mixin, so existing callers and tests can still use
the same method names.

## Service Boundary

The local row projection now lives in
`src.services.material_assets.question_library`:

- `question_figure_library_row_entries`
- `question_figure_library_rows`
- `question_figure_has_library_metadata`
- `question_figure_library_reference`

The presenter depends on these service rows rather than importing back from
`assets_panel.py`.

## Boundary

This extraction intentionally excludes:

- `_refresh_question_figure_library_governance_table`
- `_refresh_question_figure_library_bulk_governance_table`
- version history rollback flows
- master-data tables
- remote writeback tables
- subscription drift tables

Those remain governed by the enterprise boundary decisions from Step 6.

## Next Step

The next safe extraction is either:

- local question-figure editor/save behavior, after its metadata history helpers
  are moved behind a service boundary, or
- a dedicated frozen enterprise presenter for remote writeback/governance tables
  that keeps them visibly outside the local material core.
