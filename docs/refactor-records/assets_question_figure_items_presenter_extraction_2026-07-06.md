# Assets Panel Step 11: Question-Figure Item Presenter Extraction

Date: 2026-07-06

## Goal

Continue reducing `AssetsPanel` by moving the local question-figure item table
rendering and row-selection behavior into a dedicated presenter mixin.

## Files Added

- `src/ui/panels/assets/question_figures_presenter.py`
- `tests/test_assets_question_figures_presenter.py`

## Files Updated

- `src/services/material_assets/question_figures.py`
- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets/question_figures.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_material_asset_services.py`

## What Moved

`QuestionFigureItemsPresenterMixin` now owns:

- `_refresh_question_figure_items_table`
- `_on_question_figure_item_selection_changed`

`AssetsPanel` inherits the mixin, so the existing method surface remains
compatible for tests and callers.

## Service Boundary Improvement

The local row projection previously embedded in `assets_panel.py` as
`_question_figure_detail_rows` now lives in
`src.services.material_assets.question_figures` as:

- `question_figure_detail_rows`

The legacy `_question_figure_detail_rows` name remains as a compatibility alias.

## Boundary

This presenter is limited to local question-figure item rows and selection
preview coordination. It must stay separate from:

- Question-figure library metadata tables.
- Remote writeback tables.
- Enterprise governance tables.
- Subscription drift and failure recovery tables.

## Guardrails

The tests verify that:

- `AssetsPanel` inherits `QuestionFigureItemsPresenterMixin`.
- The item-table methods are defined on the mixin, not directly on
  `AssetsPanel`.
- The row projection function is exposed through the material asset service
  boundary.
- `assets_panel.py` does not call the legacy private local material helper names.

## Next Step

The next extraction candidate is the local question-figure library metadata
presenter. It should include local metadata editing and history display only;
remote writeback and governance tables should remain frozen behind the
enterprise boundary.
