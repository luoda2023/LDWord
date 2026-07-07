# Assets Panel Step 18: Master Version Plan Action Service

Date: 2026-07-06

## Goal

Move the local cross-package master-version governance plan action out of
`AssetsPanel` and into `src.services.material_assets.question_library`.

This is the first master-version action-service slice after Step 17. It is safe
to extract before promotion/Registry/subscription actions because it only
normalizes local history and appends plan records; it does not call remote
connectors.

## Files Updated

- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_material_asset_services.py`

## What Moved

The service now owns:

- `record_question_figure_library_master_version_plan`
- `build_question_figure_library_master_version_plan_record`

`assets_panel.py` keeps compatibility aliases for older private-name imports,
but the old inline `_question_figure_library_master_version_plan_record`
implementation has been removed.

## UI Boundary

`AssetsPanel._record_question_figure_library_master_version_plan_row` still owns
UI responsibilities:

- require explicit confirmation
- persist the current editor first
- resolve the selected table row
- write returned histories back to profiles
- refresh summary and material-batch selection
- update the status label and selected row

The service owns the non-UI rules:

- select affected profile indexes from `entry["occurrences"]`
- skip profiles that already have a plan for the same master key
- build one consistent `changed_at` plan record per affected profile
- return updated histories without importing the UI layer

## Behavior Covered

- Plan records are generated for all affected profiles.
- Duplicate plan calls do not append duplicate records.
- Plan records include package/profile summaries, diff fields, affected items,
  next step, and change summary.
- Existing UI architecture tests still cover the full plan -> promotion flow.

## Next Step

The next safe master-version action slice is promotion planning internals, but
the actual promotion action mutates asset metadata across profiles. Before
moving it, extract and test the pure helpers for canonical occurrence selection,
promoted metadata, and changed-field calculation as service APIs.
