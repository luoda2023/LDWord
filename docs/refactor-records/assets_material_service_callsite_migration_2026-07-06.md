# Assets Panel Step 8: Material Service Call-Site Migration

Date: 2026-07-06

## Goal

Start using the new local material service boundary from the real assets panel
instead of only keeping it as a copied helper implementation.

## What Changed

`src/ui/panels/assets_panel.py` now imports local question-figure and local
repair-audit behavior from `src.services.material_assets`.

The migrated call sites use public service names, including:

- `question_figure_items`
- `question_figure_payload_matches_item`
- `question_figure_target_label`
- `question_figure_target_value`
- `asset_item_remote_asset_id`
- `asset_item_preview_reference`
- `parse_question_figure_repair_target`
- `build_question_figure_repair_audit_record`
- `append_question_figure_repair_audit_record`
- `read_question_figure_repair_audit_payload`

The old module-level private names are retained in `assets_panel.py` as
compatibility aliases only. They are no longer the names used by local
question-figure and repair-audit call sites.

## Guardrails

`tests/test_material_asset_services.py` now verifies that:

- `assets_panel.py` imports `src.services.material_assets`.
- `assets_panel.py` does not import
  `src.ui.panels.assets.question_figures` or
  `src.ui.panels.assets.question_audit`.
- `assets_panel.py` does not call the legacy private local material helper
  names.
- The compatibility aliases still point to the same service functions.

## Why This Matters

Step 7 moved logic into service modules. This step makes that boundary real in
the primary UI file. The panel can still run unchanged from the outside, while
future refactors can safely reduce UI helper compatibility exports over time.

## Next Step

The next structurally useful move is to extract lightweight shared-cache
projection from `src/ui/panels/assets/question_cache.py` into
`src.services.material_assets.cache_projection`, while keeping remote downloads
and enterprise governance frozen behind the boundary established in Step 6.
