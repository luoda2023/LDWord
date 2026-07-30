# Scene surface fixed registry record

Date: 2026-07-09

## Context

The product rule is explicit scene/function selection:

- Users switch to a function or scene.
- The UI exposes only the fixed options for that selected surface.
- Scene option sets are not user-editable display configuration.

The previous implementation used keyword heuristics in selected scene text:

- `scene_id`
- `category`
- `category_label`
- `name`
- `description`

That meant a custom scene named like `exam notes` or described as `question paper cleanup` could accidentally show exam-paper UI, while a true exam scene without those words could miss it.

## Decision

Use a code-owned fixed registry for scene UI surfaces.

The selected scene still comes from the user's explicit selection. After selection, UI visibility and specialized option groups are resolved through `scene_surface_registry`, not through display text.

Current fixed exam-paper identities:

- Scene ids: `exam`, `exam_default`, `exam_teaching`
- Categories: `exam`, `exam_paper`, `exam_teaching`

Unknown/custom scenes fall back to the general surface even if their name or description contains exam-like words.

## Implementation

- Added `src/ui/panels/scene_surface_registry.py`.
- Changed `scene_is_exam()` in `src/ui/panels/scene_state_projection.py` to resolve via the fixed surface registry.
- Changed `scene_should_show_content_card()` to read the surface rule instead of hard-coding exam logic.
- Changed `src/ui/panels/scene_overview_projection.py` so overview rows use the same fixed exam surface rule.
- Changed `src/ui/panels/scene_style_override_service.py` so generic style variants use the same fixed exam surface rule.
- Added `tests/test_scene_surface_registry.py` to lock the false-positive case.

## Verification

Command:

```powershell
pytest tests/test_scene_surface_registry.py tests/test_scene_overview_projection.py::test_scene_overview_projection_uses_exam_assembly_rows_for_exam_scene tests/test_scene_panel_architecture.py::test_scene_panel_output_rules_card_controls_exam_answer_delivery
```

Result:

```text
4 passed in 2.89s
```

## Follow-up

The next useful cleanup is naming:

- Keep public compatibility function names such as `scene_is_exam()` for now.
- Later rename internal semantics toward `scene_uses_exam_paper_surface()` or `scene_surface_for_scene()` once callers are thinner.
- If more fixed surfaces appear, expand `SceneSurfaceSpec` with explicit card ids and output mode ids instead of adding new text-based predicates.
