# Assets Panel Step 7: Local Material Service Extraction

Date: 2026-07-06

## Goal

Move confirmed local material logic out of the UI helper layer and into a
service boundary that can be reused by panels, tests, and future document
generation code without importing `assets_panel.py`.

## Scope

This step extracts only the capabilities classified as local core in the
enterprise boundary audit:

- Local question-figure metadata, ordering, matching, labels, and preview
  references.
- Local question-figure repair and rollback audit records.

It intentionally does not extract or promote:

- Remote writeback.
- Enterprise auth.
- Master-data governance.
- Subscription drift recovery.
- Non-question asset-family remote governance.

Those flows remain frozen or deletion candidates until a real backend contract
is confirmed.

## Files Added

- `src/services/__init__.py`
- `src/services/material_assets/__init__.py`
- `src/services/material_assets/question_figures.py`
- `src/services/material_assets/repair_audit.py`
- `tests/test_material_asset_services.py`

## Compatibility Files

The old UI helper modules now act as compatibility exports:

- `src/ui/panels/assets/question_figures.py`
- `src/ui/panels/assets/question_audit.py`

Existing `assets_panel.py` imports continue to work. New code should prefer the
public service functions from `src.services.material_assets`, such as:

- `question_figure_items`
- `question_figure_payload_matches_item`
- `parse_question_figure_repair_target`
- `build_question_figure_repair_audit_record`
- `append_question_figure_repair_audit_record`
- `read_question_figure_repair_audit_payload`

## Structural Rules Added

The service tests assert that:

- Service modules expose public, non-UI API names.
- UI helper modules remain compatibility exports for the same function objects.
- Service modules do not import `src.ui.panels` or `assets_panel`.

## Next Step

After this service boundary is stable, the next improvement should be gradual
call-site migration inside `assets_panel.py`:

1. Replace direct private helper imports for local question figures with service
   imports.
2. Replace direct private audit helper imports with service imports.
3. Keep the UI compatibility modules until architecture tests and downstream
   imports no longer depend on them.
4. Only after local call sites are migrated, consider extracting lightweight
   shared-cache projection into a separate service.
