# Assets Question Library Master Version Promotion Record Service Extraction

Date: 2026-07-06

## Scope

This step moved the pure master-version promotion execution record builder from `src/ui/panels/assets_panel.py` into `src/services/material_assets/question_library.py`.

New service function:

- `build_question_figure_library_master_version_promotion_record`

The legacy private name is retained as a compatibility alias:

- `_question_figure_library_master_version_promotion_record`

## Boundary

The panel still owns the stateful promotion workflow:

- read the selected table entry
- validate UI state
- mutate `EntityProfile.asset_items`
- append the execution record to affected profiles
- refresh summary and table state

The service owns the deterministic record shape:

- promotion action identifier
- canonical profile/package/version fields
- promoted field aggregation
- affected package/profile ids
- changed item JSON payload
- change summary text

## Why This Helps

Promotion planning and promotion execution now both use service-level record builders. That keeps governance records testable without Qt setup and reduces the amount of durable business data shape code inside `assets_panel.py`.

Registry sync payloads and subscription governance payloads remain in the panel for now because their surrounding flow still mixes connector execution, failure normalization, and UI status updates. They are the next candidates for extraction.

## Verification

Added service tests for:

- promotion record action and status fields
- canonical package/version fields
- promoted field aggregation
- package/profile/changed-item JSON payloads
- public facade export and legacy private alias identity
