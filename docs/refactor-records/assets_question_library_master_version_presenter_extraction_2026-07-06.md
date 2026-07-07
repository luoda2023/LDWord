# Assets Panel Step 17: Master Version Presenter Extraction

Date: 2026-07-06

## Goal

Move the cross-package question-figure master-version table presenter out of
`AssetsPanel`, while keeping all action methods in `AssetsPanel`.

Step 16 moved the read-only projection into `src.services.material_assets`.
This step moves the matching table rendering, row lookup, and row selection
logic into a dedicated presenter.

## Files Added

- `src/ui/panels/assets/question_library_master_version_presenter.py`

## Files Updated

- `src/ui/panels/assets_panel.py`
- `tests/test_assets_question_library_presenter.py`

## What Moved

`QuestionFigureLibraryMasterVersionPresenterMixin` now owns:

- `_refresh_question_figure_library_master_version_table`
- `_on_question_figure_library_master_version_selection_changed`
- `_question_figure_library_master_version_entry_for_row`
- `_select_question_figure_library_master_version_row`

`AssetsPanel` inherits this mixin, so existing action methods can keep calling
the same method names through `self`.

## Boundary

This step intentionally keeps these action methods in `AssetsPanel`:

- `_record_question_figure_library_master_version_plan_row`
- `_execute_question_figure_library_master_version_promotion_row`
- registry sync execution
- subscription lock execution
- subscription change callback execution

The presenter wires buttons to those existing methods but does not implement
their mutation, connector, or history-record logic.

## Behavior Covered

- The table is rendered from `question_figure_library_master_version_entries`.
- Buttons are still shown according to plan/promotion/registry/subscription
  state.
- Row selection still jumps to the first affected profile/question occurrence.
- Structure tests assert that `AssetsPanel` no longer directly owns the
  master-version table presenter methods.

## Next Step

The next safe extraction is the first action-service slice for master-version
governance: start with `_record_question_figure_library_master_version_plan_row`
because it only records local history and does not make remote calls. Promotion
and registry/subscription actions should stay in `AssetsPanel` until that
local-plan action boundary is tested.
