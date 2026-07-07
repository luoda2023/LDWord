# Assets Panel Step 9: Cache Projection Service Extraction

Date: 2026-07-06

## Goal

Move lightweight question-figure cache projection out of the UI helper layer and
into the material asset service boundary.

## Scope

This step covers cache status and cache ledger projection only:

- Shared cache directory rows.
- Shared cache entry rows from `index.json` and current `AssetItem` metadata.
- Metrics rows from `metrics_history.json`.
- Hit-rate trend rows.
- Cleanup task rows from `cleanup_history.json`.
- Cleanup confirmation state and confirmation records.
- Cache status labels, invalidation labels, and lightweight scalar helpers.

This step does not promote enterprise functionality:

- No remote writeback.
- No enterprise auth.
- No master-data governance.
- No subscription drift recovery.
- No remote cleanup execution connector.

## Files Added

- `src/services/material_assets/common.py`
- `src/services/material_assets/cache_projection.py`

## Files Updated

- `src/services/material_assets/__init__.py`
- `src/ui/panels/assets/question_cache.py`
- `src/ui/panels/assets_panel.py`
- `tests/test_material_asset_services.py`

## Compatibility

`src/ui/panels/assets/question_cache.py` is now a compatibility export over
`src.services.material_assets.cache_projection`.

`assets_panel.py` now imports cache projection functions from
`src.services.material_assets` and uses the public names at call sites. Legacy
module-level private names remain as aliases only, so older tests and imports
continue to resolve.

## Guardrails

The service tests verify that:

- Cache projection services do not import `src.ui.panels` or `assets_panel`.
- `assets_panel.py` does not import `src.ui.panels.assets.question_cache`.
- `assets_panel.py` does not call the legacy private cache helper names.
- UI compatibility exports point to the same service functions.

## Next Step

The next healthy move is not to expand cache governance. Instead:

1. Keep remote writeback and enterprise governance frozen.
2. Start reducing `assets_panel.py` itself by extracting one UI presenter slice
   at a time, beginning with the local question-figure/cache table refresh
   methods.
3. Add line-count and import-boundary architecture checks once the first UI
   presenter slice exists.
