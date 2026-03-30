# Workbench Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Workbench placeholder with a real Workbench panel that loads a document, exposes heading-numbering configuration, executes the pipeline, and shows output/report results.

**Architecture:** Keep the existing `TitleBar + Sidebar + PanelStack` shell intact, instantiate a real `WorkbenchPanel` in the workbench slot, and use the existing `HeadingNumberingPanel` as the first embedded capability editor. Load a real template from `defaults/thesis.yaml`, use a built-in vertical-slice scene profile for structure modules, and execute the real pipeline synchronously with progress/cancel callbacks.

**Tech Stack:** Python, PySide6, pytest, python-docx, existing config/pipeline/report infrastructure

---

> Note: this workspace is **not** a git repository, so normal commit steps cannot be executed here. Keep verification explicit at each task boundary.

## File map

- Create: `src/ui/panels/workbench_panel.py`
- Modify: `src/ui/panels/__init__.py`
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/panel_registry.py`
- Modify: `src/ui/panels/heading_numbering_panel.py`
- Create: `tests/test_workbench_panel.py`

### Task 1: Register a real Workbench panel in the existing shell

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/panel_registry.py`
- Create: `tests/test_workbench_panel.py`

- [ ] **Step 1: Write the failing test**

```python
from src.qt_api import QApplication
from src.ui.main_window import MainWindow
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_main_window_registers_real_workbench_panel():
    _app()
    window = MainWindow()
    try:
        assert isinstance(window.panel_stack.widget(0), WorkbenchPanel)
    finally:
        window.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_workbench_panel.py::test_main_window_registers_real_workbench_panel -v`

Expected: FAIL because the workbench slot still uses `_PlaceholderPanel`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panel_registry.py

def create_panel(panel_id: str, bridge):
    if panel_id == "workbench":
        from src.ui.panels.workbench_panel import WorkbenchPanel
        return WorkbenchPanel(bridge)
    return None
```

```python
# src/ui/main_window.py
from src.ui.panel_registry import PANEL_SPECS, create_panel

for spec in PANEL_SPECS:
    panel = create_panel(spec.id, self.bridge) or _PlaceholderPanel(spec.title)
    self.panel_stack.addWidget(panel)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_workbench_panel.py::test_main_window_registers_real_workbench_panel -v`

Expected: PASS

### Task 2: Build Workbench MVP UI and load default template/scene state

**Files:**
- Create: `src/ui/panels/workbench_panel.py`
- Modify: `src/ui/panels/__init__.py`
- Modify: `src/ui/panels/heading_numbering_panel.py`
- Modify: `tests/test_workbench_panel.py`

- [ ] **Step 1: Write the failing test**

```python
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_loads_defaults_and_embeds_heading_numbering_panel():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel.findChild(HeadingNumberingPanel) is not None
        assert panel._template_combo.count() >= 1
        assert panel._scene_combo.count() >= 1
        assert panel._current_template is not None
        assert panel._current_scene is not None
    finally:
        panel.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_workbench_panel.py::test_workbench_panel_loads_defaults_and_embeds_heading_numbering_panel -v`

Expected: FAIL because `WorkbenchPanel` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench_panel.py
class WorkbenchPanel(BasePanel):
    def _setup_ui(self) -> None:
        self._current_template = load_template(ROOT / "defaults" / "thesis.yaml")
        self._current_scene = self._build_heading_numbering_scene()
        self._heading_panel = HeadingNumberingPanel(self.bridge, self)
        self._template_combo.addItem("Default thesis template", str(ROOT / "defaults" / "thesis.yaml"))
        self._scene_combo.addItem("Builtin heading-numbering slice", "builtin_heading_numbering")
        self._heading_panel = HeadingNumberingPanel(self.bridge, self)
        self.bridge.template_changed.emit(self._current_template)
        self.bridge.scene_changed.emit(self._current_scene)
```

```python
# src/ui/panels/heading_numbering_panel.py
self.bridge.template_changed.connect(self.on_template_changed)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_workbench_panel.py::test_workbench_panel_loads_defaults_and_embeds_heading_numbering_panel -v`

Expected: PASS

### Task 3: Wire real execution, progress, and result/report output

**Files:**
- Modify: `src/ui/panels/workbench_panel.py`
- Modify: `tests/test_workbench_panel.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench_panel import WorkbenchPanel

ROOT = Path(__file__).resolve().parent.parent


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_run_pipeline_formats_selected_document(tmp_path):
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        panel.set_document_path(str(ROOT / "tests" / "test_input.docx"))
        panel.set_output_dir(str(tmp_path / "output"))

        result = panel.run_pipeline()

        assert result is not None
        assert result.success is True
        assert Path(result.output_paths["final"]).exists()
        assert (tmp_path / "output" / "test_input_changes.json").exists()
        assert (tmp_path / "output" / "test_input_changes.md").exists()
    finally:
        panel.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_workbench_panel.py::test_workbench_panel_run_pipeline_formats_selected_document -v`

Expected: FAIL because Workbench has no execution path yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench_panel.py
resolved = resolve_config(self._current_template, self._current_scene)
modules = create_all_modules()
enabled, auto_pruned = select_enabled_modules(modules, resolved.is_module_enabled)
pipeline = Pipeline(
    modules=enabled,
    config=resolved,
    output_dir=str(output_dir),
    output_suffix="_formatted",
    progress_callback=self._on_pipeline_progress,
    cancel_check=lambda: self._cancel_requested,
)
result = pipeline.execute(str(doc_path))
write_json_report(
    result,
    input_path=doc_path,
    output_path=Path(result.output_paths["final"]),
    report_path=output_dir / f"{doc_path.stem}_changes.json",
    elapsed=elapsed,
    modules_enabled=len(enabled),
    modules_total=len(modules),
)
write_markdown_report(
    result,
    input_path=doc_path,
    report_path=output_dir / f"{doc_path.stem}_changes.md",
    elapsed=elapsed,
    modules_enabled=len(enabled),
    modules_total=len(modules),
)
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/test_workbench_panel.py -v`

Expected: PASS

### Task 4: Run regression verification

**Files:**
- Modify: `docs/superpowers/plans/2026-03-28-workbench-vertical-slice.md`

- [ ] **Step 1: Run the focused UI + workbench slice tests**

Run: `pytest tests/test_workbench_panel.py tests/test_heading_panel_level_slider.py tests/test_heading_panel_mode_controls.py tests/test_heading_numbering_logic.py -v`

Expected: PASS

- [ ] **Step 2: Run the full suite**

Run: `pytest tests -q`

Expected: PASS

- [ ] **Step 3: Manual smoke**

Run: `python main.py --gui`

Expected:
- the first sidebar item opens a real Workbench panel,
- the Workbench shows document/template/scene/execution/result sections,
- the embedded heading-numbering editor is visible and usable,
- running on a test document produces output and report files.
