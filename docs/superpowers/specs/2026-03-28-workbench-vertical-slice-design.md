# Workbench Vertical Slice Design

## Goal

Land the first real **Workbench** panel inside the existing V1.0 UI shell, and make it the first usable end-to-end entrypoint for the product. This slice must replace the current workbench placeholder with a real panel that can:

- load a `.docx` document,
- choose a template/scene baseline,
- expose one real formatting capability through the UI,
- execute the pipeline,
- and display the result/report summary.

For this first slice, the integrated capability is **Heading Numbering**, reusing the existing `HeadingNumberingPanel` as the first embedded configuration block.

## Why this slice is next

The project-level planning baseline (`project master planning document`) says:

- the product is evolving from a thesis-only formatter into a **composable document formatting platform**;
- the **Workbench** is the default homepage and is intended to carry most daily operations;
- the current codebase is still a **phase-based UI shell**, not the final product shape.

That means the next priority is not another isolated feature page. The next priority is turning the shell into a real product entrypoint.

## Scope

### In scope

1. Replace the `workbench` placeholder with a real `WorkbenchPanel`.
2. Keep the existing shell (`TitleBar + Sidebar + PanelStack`) and build inside it.
3. Load one usable template baseline and one usable scene baseline.
4. Embed `HeadingNumberingPanel` as the first real editable capability inside Workbench.
5. Execute the real pipeline from the Workbench panel.
6. Show pipeline progress, completion state, output path, and report paths.
7. Add focused runtime tests for panel registration, default state, and execution.

### Out of scope

1. Rebuild the outer shell into the final toolbar/statusbar layout.
2. Implement the full Scene Config / Template Config / Assets panels.
3. Add asynchronous worker-thread execution in this slice.
4. Add persistence of user-selected template/scene/doc paths.
5. Add a full scene library or template browser UX.

## Current codebase baseline

The existing code already provides the right seam for this slice:

- `src/ui/main_window.py` already owns the main shell and panel stack.
- `src/ui/panel_registry.py` already declares `workbench` as the first navigation target.
- `src/ui/sidebar.py` and `src/ui/title_bar.py` already form the shell frame.
- `src/ui/base_panel.py` already defines the panel lifecycle contract.
- `src/ui/panels/heading_numbering_panel.py` already provides the most mature real business-facing configuration UI in the repo.
- `src/config/loader.py`, `src/config/resolver.py`, `src/modules/registry.py`, `src/pipeline/runner.py`, and `src/report_writer.py` already make one-shot runtime execution possible.

So this slice should **compose** existing pieces, not invent a parallel architecture.

## Architecture

### 1. Keep the current shell, do not restart the UI architecture

The shell remains:

- `TitleBar`
- `Sidebar`
- `QStackedWidget`

The only change at this level is that the `workbench` slot should instantiate a real panel instead of `_PlaceholderPanel`.

This keeps the implementation aligned with the planning baseline that the current code is an intermediate shell on the road to the final layout.

### 2. Introduce `WorkbenchPanel` as a BasePanel implementation

Create `src/ui/panels/workbench_panel.py`.

Responsibilities:

- own the current document path,
- own the current in-memory template/scene selection,
- host the first embedded capability editor,
- execute the formatting pipeline,
- render execution state and result/report summary.

It should **not** absorb the detailed heading-numbering editing logic. That remains inside `HeadingNumberingPanel`.

### 3. Use a vertical-slice scene baseline, not a fake full platform

The Workbench slice should load:

- a real template baseline from `defaults/thesis.yaml`,
- an in-memory built-in scene tuned for this vertical slice.

That built-in scene should enable only the minimum structure modules needed for the first Workbench capability:

- `heading_recognition`
- `heading_numbering`
- `toc`

This keeps the first Workbench slice focused, predictable, and fast, while still using the real config -> resolve -> pipeline path.

This is temporary product scaffolding, not the final scene-management solution.

### 4. Integrate Heading Numbering through composition

The Workbench panel should host an embedded `HeadingNumberingPanel` inside a collapsible/sectioned card.

Integration contract:

- Workbench owns the current `TemplateConfig` object.
- The embedded heading panel edits that same template object.
- Workbench emits `bridge.template_changed` whenever the baseline template changes.
- `HeadingNumberingPanel` should listen to `bridge.template_changed` so it can be reused as either an embedded panel or a future standalone panel.

This makes Heading Numbering the first real "capability block" inside the Workbench without turning Workbench into a giant special-case page.

### 5. Execute synchronously for MVP, but keep progress/cancel semantics

This slice should use the existing synchronous `Pipeline.execute()` path.

To keep the UI usable without introducing threading yet:

- pass a `progress_callback` that updates `ProgressIndicator`,
- call `QApplication.processEvents()` inside that callback,
- store a cancel flag that `cancel_check` reads.

This provides a lightweight MVP cancellation/progress experience while avoiding the complexity of QThread/worker orchestration in the first Workbench slice.

### 6. Workbench result rendering

After execution, the panel should show:

- final status (`success` / `partial_success` / `failed` / `cancelled`),
- output `.docx` path,
- JSON report path,
- Markdown report path,
- failure count if any,
- error message if execution failed.

This should make the Workbench feel like a real user entrypoint rather than just another config form.

## UI structure for the slice

The first Workbench panel should use a simple stacked layout inside the existing shell:

1. **Header block**
   - title + one-sentence description
2. **Top summary row**
   - Document card
   - Template/scene card
3. **Capability section**
   - embedded `HeadingNumberingPanel`
4. **Execution section**
   - run button
   - progress indicator
5. **Result section**
   - status summary
   - output/report paths

This is intentionally smaller than the final Workbench vision in the planning doc, but it preserves the final information architecture: document -> configuration -> execution -> results.

## Data flow

### Template flow

- Workbench loads `defaults/thesis.yaml` via `load_template()`.
- Workbench stores the resulting `TemplateConfig` in memory.
- Workbench emits `bridge.template_changed(template)`.
- Embedded heading panel updates itself from that template.
- The user edits heading numbering.
- Workbench later resolves config from the mutated template + scene.

### Scene flow

- Workbench creates an in-memory built-in scene profile for the vertical slice.
- Workbench emits `bridge.scene_changed(scene)`.
- The scene determines which modules are enabled during pipeline selection.

### Execution flow

- User chooses document path.
- Workbench resolves config with `resolve_config(template, scene)`.
- Workbench instantiates all modules.
- Workbench prunes to enabled modules.
- Workbench executes `Pipeline`.
- Workbench writes JSON/Markdown reports.
- Workbench renders output summary.

## Testing strategy

### Focused tests

1. `MainWindow` registers a real `WorkbenchPanel` in the workbench slot.
2. `WorkbenchPanel` loads defaults and embeds `HeadingNumberingPanel`.
3. `WorkbenchPanel.run_pipeline()` can execute against `tests/test_input.docx` and produce output/report files.

### Regression expectations

- Existing heading-numbering tests must continue to pass.
- Existing UI shell tests must continue to pass.
- Full repo test suite must remain green.

## Risks and mitigations

### Risk 1: Workbench grows into a second monolithic main window
Mitigation: keep Workbench focused on orchestration, not detailed editing logic.

### Risk 2: HeadingNumberingPanel becomes tightly coupled to Workbench
Mitigation: integrate via bridge/template lifecycle rather than by reaching into adapter private state.

### Risk 3: Synchronous execution freezes the UI
Mitigation: use `progress_callback + processEvents + cancel_check` for MVP; defer threading to a later slice.

### Risk 4: The first scene baseline accidentally runs too many modules
Mitigation: use a built-in vertical-slice scene profile that only enables structure modules needed for heading numbering.

## Follow-up after this slice

If this Workbench slice lands cleanly, the next recommended order is:

1. add a second capability block to Workbench, or
2. build the real Scene Config panel, or
3. build the real Template Config panel.

But only after the Workbench entrypoint is proven usable.
