# Assets Panel Step 15: Question Library Governance Presenter Extraction

Date: 2026-07-06

## Goal

Move the lightweight local question-figure governance issue tables out of
`AssetsPanel`, without pulling remote writeback, master-data subscription
drift, approval, SLA, or background-worker actions into the local presenter.

This step follows the Step 14 version-history extraction. The remaining
enterprise flows are broad and action-heavy, so this step intentionally chooses
the smallest useful read-only governance surface first.

## Files Added

- `src/ui/panels/assets/question_library_governance_presenter.py`

## Files Updated

- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_assets_question_library_presenter.py`
- `tests/test_material_asset_services.py`

## What Moved

`QuestionFigureLibraryGovernancePresenterMixin` now owns:

- `_refresh_question_figure_library_governance_table`
- `_refresh_question_figure_library_bulk_governance_table`
- `_on_question_figure_library_governance_selection_changed`
- `_on_question_figure_library_bulk_governance_selection_changed`
- `_select_question_figure_library_governance_row`
- `_select_question_figure_library_bulk_governance_row`

`AssetsPanel` still owns `_select_question_figure_library_governance_question_row`
because remote writeback, master version, and other enterprise flows use it as a
shared navigation primitive.

## Service Boundary

The non-UI governance projection now lives in
`src.services.material_assets.question_library`:

- `question_figure_library_governance_issue_entries`
- `question_figure_library_bulk_governance_entries`
- `question_figure_bulk_governance_scope`
- `question_figure_bulk_governance_next_step`
- `question_figure_library_source_label`
- `question_figure_library_asset_label`
- `question_figure_requires_library_identity`

`assets_panel.py` keeps legacy `_...` aliases pointing to these service
functions, but no longer contains the duplicate implementations.

## Behavior Covered

- Individual issue rows cover missing alt text, missing source, missing asset
  ID, and duplicated source/asset ID pairs.
- Bulk rows group issues by type, keep the first affected question row, and
  present the expected next step.
- The presenter only renders rows and locates the affected question item.
- Structure tests assert that `AssetsPanel` does not directly own the lightweight
  governance presenter methods.

## Boundary

This extraction intentionally does not move:

- remote writeback handoff/execution/retry/conflict handling
- remote rollback and second compensation
- master version plans or promotion actions
- subscription drift queues, approvals, field merges, or SLA centers
- background worker and cross-archive governance tables

Those remain enterprise/governance domains. They should be split only after
their read-only projections and action services are named separately.

## Next Step

The next healthy step is a read-only enterprise projection extraction. Good
candidates:

1. Master version table projection, leaving plan/promotion/callback actions in
   place.
2. Remote writeback table row projection, leaving connector execution actions in
   place.
3. Subscription drift queue projection, leaving approval and batch mutation
   flows untouched.

The safest next move is master version table projection because it groups
existing profile metadata and history records without making network calls.
