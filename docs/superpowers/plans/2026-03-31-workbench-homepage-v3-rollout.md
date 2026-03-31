# Workbench Homepage V3 Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Workbench command-center homepage with the V3 dynamic-card homepage, while adding only the shared UI primitives that are actually required by the V3 flow.

**Architecture:** Implement this as a staged rollout instead of a component grab-bag. First land the shared navigation / section / feedback primitives, then refactor the Workbench shell to a dynamic navigation rail + right-side detail panes, then hook the existing execution path into the new quick-execute experience, and only after that add extra feature panes.

**Tech Stack:** Python, PySide6, existing `src/shared/ui` theme system, existing Workbench adapters / execution worker / pipeline path, `pytest`

---

## Scope Adjustment

The two source specs are broader than one safe execution plan:

- [`2026-03-31-workbench-homepage-redesign-v3-final.md`](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/docs/superpowers/specs/2026-03-31-workbench-homepage-redesign-v3-final.md)
- [`2026-03-31-ui-components-gap-analysis.md`](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/docs/superpowers/specs/2026-03-31-ui-components-gap-analysis.md)

They cover five different concerns:

1. shared navigation and card primitives
2. quick-execute page shell
3. execution feedback widgets
4. configuration management
5. advanced feature panes and future low-priority components

This rollout plan intentionally covers the blocking slices for the homepage reset:

- shared UI foundation required by V3
- V3 homepage shell
- quick-execute pane
- configuration management pane skeleton
- execution feedback integration
- first dynamic cards (`heading_numbering`, `quick_fill`) as real panes

This plan explicitly defers the following to follow-up plans after the V3 shell is stable:

- `MappingTable`
- full `DraggableModuleList`
- `SplitPane`
- `ContextMenu`
- `Timeline`
- `DataTable`
- notification / toast polish
- full execution-history browser beyond the latest run summary

## File Structure

### Shared UI additions / upgrades

- Create: `src/shared/ui/badge.py`
- Create: `src/shared/ui/navigation_card.py`
- Create: `src/shared/ui/dynamic_navigation_rail.py`
- Create: `src/shared/ui/flow_section.py`
- Create: `src/shared/ui/file_drop_zone.py`
- Create: `src/shared/ui/feature_toggle_row.py`
- Create: `src/shared/ui/module_status_list.py`
- Create: `src/shared/ui/log_stream_widget.py`
- Create: `src/shared/ui/execution_feedback_widget.py`
- Modify: `src/shared/ui/__init__.py`
- Modify: `src/shared/ui/card.py`

### Workbench homepage refactor

- Modify: `src/ui/panels/workbench/state.py`
- Create: `src/ui/panels/workbench/quick_execute_pane.py`
- Create: `src/ui/panels/workbench/config_management_pane.py`
- Create: `src/ui/panels/workbench/heading_numbering_pane.py`
- Create: `src/ui/panels/workbench/quick_fill_pane.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `src/ui/panels/workbench/styles.py`
- Modify: `src/ui/panels/workbench/command_bar.py`

### Tests

- Modify: `tests/test_ui_exports.py`
- Create: `tests/test_dynamic_navigation_rail.py`
- Create: `tests/test_file_drop_zone.py`
- Create: `tests/test_feature_toggle_row.py`
- Create: `tests/test_execution_feedback_widget.py`
- Modify: `tests/test_workbench_layout.py`
- Modify: `tests/test_workbench_panel.py`
- Modify: `tests/test_heading_quick_card.py`
- Modify: `tests/test_quick_fill_card.py`

## Naming Decisions

Use the V3 homepage naming, not the older object-first homepage naming:

- fixed left cards: `quick_execute`, `config_management`
- dynamic left cards: `heading_numbering`, `quick_fill`, `module_control`, `output_settings`, `execution_history`
- keep shared names generic even if the first use is Workbench-specific:
  - `DynamicNavigationRail`
  - `NavigationCard`
  - `FlowSection`
  - `ExecutionFeedbackWidget`

Do **not** introduce a broad `CardV2` rewrite in this plan. Instead:

- extend `Card` just enough to support slots / variants needed immediately
- put selectable behavior in `NavigationCard`
- put badge behavior in standalone `Badge`

This keeps the first V3 landing smaller and lowers rewrite risk.

### Task 1: Shared Navigation / Badge Foundation

**Files:**
- Create: `src/shared/ui/badge.py`
- Create: `src/shared/ui/navigation_card.py`
- Create: `src/shared/ui/dynamic_navigation_rail.py`
- Modify: `src/shared/ui/card.py`
- Modify: `src/shared/ui/__init__.py`
- Test: `tests/test_dynamic_navigation_rail.py`
- Test: `tests/test_ui_exports.py`

- [ ] **Step 1: Write failing shared navigation export tests**

```python
from src.shared.ui import Badge, DynamicNavigationRail, NavigationCard


def test_shared_ui_exports_include_v3_navigation_primitives():
    assert Badge.__name__ == "Badge"
    assert DynamicNavigationRail.__name__ == "DynamicNavigationRail"
    assert NavigationCard.__name__ == "NavigationCard"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui_exports.py -q`
Expected: `ImportError` or failed attribute assertions for `Badge`, `DynamicNavigationRail`, and `NavigationCard`

- [ ] **Step 3: Add shared badge / navigation card / rail primitives**

```python
# src/shared/ui/badge.py
class Badge(QWidget):
    def __init__(self, text: str = "", variant: str = "neutral", parent=None):
        super().__init__(parent)
        self._text = text
        self._variant = variant

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self.update()


# src/shared/ui/navigation_card.py
class NavigationCard(Card):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(title, parent=parent)
        self._selected = False
        self._subtitle_label = QLabel(subtitle)
        self._badge = Badge(parent=self)
        self.add_widget(self._subtitle_label)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def is_selected(self) -> bool:
        return self._selected

    def set_subtitle(self, text: str) -> None:
        self._subtitle_label.setText(text)

    def set_badge(self, text: str, variant: str = "neutral") -> None:
        self._badge.set_text(text)
        self._badge.set_variant(variant)


# src/shared/ui/dynamic_navigation_rail.py
class DynamicNavigationRail(QWidget):
    card_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, NavigationCard] = {}
        self._selected_card_id: str | None = None

    def add_card(self, card_id: str, card: NavigationCard) -> None:
        self._cards[card_id] = card

    def remove_card(self, card_id: str) -> None:
        card = self._cards.pop(card_id, None)
        if card_id == self._selected_card_id:
            self._selected_card_id = None
        if card is not None:
            card.setParent(None)

    def select_card(self, card_id: str) -> None:
        for current_id, current_card in self._cards.items():
            current_card.set_selected(current_id == card_id)
        self._selected_card_id = card_id
        self.card_selected.emit(card_id)

    def selected_card_id(self) -> str | None:
        return self._selected_card_id
```

- [ ] **Step 4: Update shared exports**

```python
# src/shared/ui/__init__.py
from .badge import Badge
from .dynamic_navigation_rail import DynamicNavigationRail
from .navigation_card import NavigationCard

__all__ = [
    "Badge",
    "DynamicNavigationRail",
    "NavigationCard",
    "SearchInput",
    "StyledComboBox",
    "ThemedRadioButton",
    "ThemedSlider",
]
```

- [ ] **Step 5: Add behavior tests for selection and dynamic add/remove**

```python
def test_dynamic_navigation_rail_tracks_selection():
    rail = DynamicNavigationRail()
    first = NavigationCard("快速执行")
    second = NavigationCard("配置管理")
    rail.add_card("quick_execute", first)
    rail.add_card("config_management", second)

    rail.select_card("config_management")

    assert rail.selected_card_id() == "config_management"
    assert second.is_selected() is True
    assert first.is_selected() is False
```

- [ ] **Step 6: Run shared navigation tests**

Run: `pytest tests/test_ui_exports.py tests/test_dynamic_navigation_rail.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/shared/ui/card.py src/shared/ui/__init__.py src/shared/ui/badge.py src/shared/ui/navigation_card.py src/shared/ui/dynamic_navigation_rail.py tests/test_ui_exports.py tests/test_dynamic_navigation_rail.py
git commit -m "feat: add shared navigation primitives for workbench v3"
```

### Task 2: Shared Quick-Execute Section Primitives

**Files:**
- Create: `src/shared/ui/flow_section.py`
- Create: `src/shared/ui/file_drop_zone.py`
- Create: `src/shared/ui/feature_toggle_row.py`
- Modify: `src/shared/ui/__init__.py`
- Test: `tests/test_file_drop_zone.py`
- Test: `tests/test_feature_toggle_row.py`

- [ ] **Step 1: Write failing tests for file selection and feature toggle interaction**

```python
def test_file_drop_zone_accepts_explicit_file_path(tmp_path):
    path = tmp_path / "input.docx"
    path.write_bytes(b"stub")
    zone = FileDropZone()

    zone.set_file(str(path))

    assert zone.file_path() == str(path)


def test_feature_toggle_row_disables_config_button_when_unchecked():
    row = FeatureToggleRow("标题编号")

    row.set_checked(False)

    assert row.is_checked() is False
    assert row.config_button().isEnabled() is False
```

- [ ] **Step 2: Run primitive tests to verify they fail**

Run: `pytest tests/test_file_drop_zone.py tests/test_feature_toggle_row.py -q`
Expected: module import failures because the widgets do not exist yet

- [ ] **Step 3: Implement `FlowSection`, `FileDropZone`, and `FeatureToggleRow`**

```python
class FlowSection(Card):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent=parent)
        self._collapsible = False
        self._expanded = True

    def set_collapsible(self, collapsible: bool) -> None:
        self._collapsible = collapsible

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.setVisible(True)


class FileDropZone(QWidget):
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = ""
        self._recent_files: list[str] = []

    def set_file(self, path: str) -> None:
        self._file_path = path
        self.file_selected.emit(path)

    def file_path(self) -> str:
        return self._file_path

    def set_recent_files(self, files: list[str]) -> None:
        self._recent_files = list(files)


class FeatureToggleRow(QWidget):
    toggled = Signal(bool)
    config_clicked = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._checkbox = QCheckBox(title, self)
        self._config_button = QPushButton("配置", self)
        self._config_button.setEnabled(False)

    def set_checked(self, checked: bool) -> None:
        self._checkbox.setChecked(checked)
        self._config_button.setEnabled(checked)
        self.toggled.emit(checked)

    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def config_button(self) -> QPushButton:
        return self._config_button
```

- [ ] **Step 4: Export the new primitives**

```python
from .feature_toggle_row import FeatureToggleRow
from .file_drop_zone import FileDropZone
from .flow_section import FlowSection
```

- [ ] **Step 5: Add signal-level interaction tests**

```python
def test_feature_toggle_row_emits_toggle_signal():
    seen = []
    row = FeatureToggleRow("内容填充")
    row.toggled.connect(seen.append)

    row.set_checked(True)

    assert seen[-1] is True
```

- [ ] **Step 6: Run the primitive test set**

Run: `pytest tests/test_file_drop_zone.py tests/test_feature_toggle_row.py tests/test_ui_exports.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/shared/ui/__init__.py src/shared/ui/flow_section.py src/shared/ui/file_drop_zone.py src/shared/ui/feature_toggle_row.py tests/test_file_drop_zone.py tests/test_feature_toggle_row.py
git commit -m "feat: add quick-execute shared section primitives"
```

### Task 3: Shared Execution Feedback Composite

**Files:**
- Create: `src/shared/ui/module_status_list.py`
- Create: `src/shared/ui/log_stream_widget.py`
- Create: `src/shared/ui/execution_feedback_widget.py`
- Modify: `src/shared/ui/__init__.py`
- Test: `tests/test_execution_feedback_widget.py`

- [ ] **Step 1: Write failing execution feedback tests**

```python
def test_execution_feedback_widget_updates_module_status_and_log():
    widget = ExecutionFeedbackWidget()
    widget.add_module("heading_numbering", "标题编号")
    widget.update_module_status("heading_numbering", "running", 45)
    widget.append_log("info", "processing heading numbering")

    assert widget.current_module_text() == "标题编号"
    assert "processing heading numbering" in widget.log_text()
```

- [ ] **Step 2: Run the feedback tests to verify they fail**

Run: `pytest tests/test_execution_feedback_widget.py -q`
Expected: module import failure for `ExecutionFeedbackWidget`

- [ ] **Step 3: Implement module list / log stream / feedback composite**

```python
class ModuleStatusList(QWidget):
    module_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, dict[str, object]] = {}

    def add_module(self, module_id: str, title: str) -> None:
        self._rows[module_id] = {"title": title, "status": "pending", "progress": 0}

    def update_status(self, module_id: str, status: str, progress: int = 0) -> None:
        self._rows[module_id]["status"] = status
        self._rows[module_id]["progress"] = progress


class LogStreamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[str] = []

    def append_log(self, level: str, message: str) -> None:
        self._lines.append(f"[{level}] {message}")

    def log_text(self) -> str:
        return "\n".join(self._lines)


class ExecutionFeedbackWidget(QWidget):
    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_module_text = ""
        self._summary_text = ""
        self._module_list = ModuleStatusList(self)
        self._log_stream = LogStreamWidget(self)

    def set_progress(self, current: int, total: int, module_title: str) -> None:
        self._current_module_text = module_title

    def add_module(self, module_id: str, title: str) -> None:
        self._module_list.add_module(module_id, title)

    def update_module_status(self, module_id: str, status: str, progress: int = 0) -> None:
        self._module_list.update_status(module_id, status, progress)

    def append_log(self, level: str, message: str) -> None:
        self._log_stream.append_log(level, message)

    def current_module_text(self) -> str:
        return self._current_module_text

    def log_text(self) -> str:
        return self._log_stream.log_text()

    def set_completed(self, success: bool, summary: dict) -> None:
        self._summary_text = f"成功处理 {summary['success_count']} 项"

    def summary_text(self) -> str:
        return self._summary_text
```

- [ ] **Step 4: Export the composite**

```python
from .execution_feedback_widget import ExecutionFeedbackWidget
from .log_stream_widget import LogStreamWidget
from .module_status_list import ModuleStatusList
```

- [ ] **Step 5: Add tests for completion summary and cancel signal**

```python
def test_execution_feedback_widget_surfaces_completion_summary():
    widget = ExecutionFeedbackWidget()
    widget.set_completed(True, {"success_count": 3, "warning_count": 1, "error_count": 0})

    assert "成功处理 3 项" in widget.summary_text()
```

- [ ] **Step 6: Run the feedback suite**

Run: `pytest tests/test_execution_feedback_widget.py tests/test_ui_exports.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/shared/ui/__init__.py src/shared/ui/module_status_list.py src/shared/ui/log_stream_widget.py src/shared/ui/execution_feedback_widget.py tests/test_execution_feedback_widget.py
git commit -m "feat: add shared execution feedback widgets"
```

### Task 4: Workbench V3 Shell and State Model

**Files:**
- Modify: `src/ui/panels/workbench/state.py`
- Create: `src/ui/panels/workbench/quick_execute_pane.py`
- Create: `src/ui/panels/workbench/config_management_pane.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `src/ui/panels/workbench/styles.py`
- Modify: `src/ui/panels/workbench/command_bar.py`
- Test: `tests/test_workbench_layout.py`
- Test: `tests/test_workbench_panel.py`

- [ ] **Step 1: Replace outdated layout assertions with V3 shell tests**

```python
def test_workbench_panel_uses_v3_dynamic_navigation_shell():
    panel = WorkbenchPanel(PanelBridge())
    assert hasattr(panel, "_navigation_rail")
    assert hasattr(panel, "_detail_stack")
    assert panel._navigation_rail.selected_card_id() == "quick_execute"


def test_workbench_panel_starts_with_quick_execute_and_config_cards_only():
    panel = WorkbenchPanel(PanelBridge())
    assert panel._navigation_order == ["quick_execute", "config_management"]
```

- [ ] **Step 2: Run focused Workbench layout tests to verify the current page fails**

Run: `pytest tests/test_workbench_layout.py tests/test_workbench_panel.py -q`
Expected: failures because the page still exposes `_strategy_card`, `_capability_grid`, `_execution_center`, and `_recent_run_panel` as the main shell

- [ ] **Step 3: Extend Workbench state for V3 navigation**

```python
@dataclass(slots=True)
class FeatureCardState:
    feature_id: str
    title: str
    enabled: bool = False
    subtitle: str = ""
    badge_text: str = ""
    badge_variant: str = "neutral"


@dataclass(slots=True)
class WorkbenchHomeState:
    selected_card_id: str = "quick_execute"
    enabled_features: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Refactor `WorkbenchPanel` into V3 shell**

```python
class WorkbenchPanel(BasePanel):
    def _setup_ui(self) -> None:
        self._command_bar = TaskCommandBar(self)
        self._navigation_rail = DynamicNavigationRail(self)
        self._detail_stack = QStackedWidget(self)
        self._quick_execute_pane = QuickExecutePane(self)
        self._config_management_pane = ConfigManagementPane(self)
```

- [ ] **Step 5: Seed the fixed cards and selection wiring**

```python
self._navigation_order = ["quick_execute", "config_management"]
self._navigation_rail.add_card("quick_execute", NavigationCard("快速执行"))
self._navigation_rail.add_card("config_management", NavigationCard("配置管理"))
self._navigation_rail.select_card("quick_execute")
```

- [ ] **Step 6: Run the V3 shell test set**

Run: `pytest tests/test_workbench_layout.py tests/test_workbench_panel.py -q`
Expected: PASS with updated layout assertions

- [ ] **Step 7: Commit**

```bash
git add src/ui/panels/workbench/state.py src/ui/panels/workbench/quick_execute_pane.py src/ui/panels/workbench/config_management_pane.py src/ui/panels/workbench/panel.py src/ui/panels/workbench/styles.py src/ui/panels/workbench/command_bar.py tests/test_workbench_layout.py tests/test_workbench_panel.py
git commit -m "feat: refactor workbench to v3 dynamic shell"
```

### Task 5: Quick Execute Pane and Dynamic Feature Cards

**Files:**
- Modify: `src/ui/panels/workbench/quick_execute_pane.py`
- Create: `src/ui/panels/workbench/heading_numbering_pane.py`
- Create: `src/ui/panels/workbench/quick_fill_pane.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `tests/test_workbench_panel.py`
- Modify: `tests/test_heading_quick_card.py`
- Modify: `tests/test_quick_fill_card.py`

- [ ] **Step 1: Write failing tests for dynamic feature-card appearance**

```python
def test_enabling_heading_numbering_adds_dynamic_navigation_card():
    panel = WorkbenchPanel(PanelBridge())

    panel._quick_execute_pane.set_feature_enabled("heading_numbering", True)

    assert "heading_numbering" in panel._navigation_order


def test_clicking_feature_config_switches_to_feature_pane():
    panel = WorkbenchPanel(PanelBridge())
    panel._quick_execute_pane.set_feature_enabled("quick_fill", True)

    panel._quick_execute_pane.open_feature_config("quick_fill")

    assert panel._navigation_rail.selected_card_id() == "quick_fill"
```

- [ ] **Step 2: Run the focused dynamic-card tests to verify they fail**

Run: `pytest tests/test_workbench_panel.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py -q`
Expected: failures because the V3 quick-execute pane has not wired dynamic cards yet

- [ ] **Step 3: Build the quick-execute pane sections**

```python
class QuickExecutePane(QWidget):
    feature_toggled = Signal(str, bool)
    feature_config_requested = Signal(str)
    execute_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._feature_enabled: dict[str, bool] = {}

    def set_feature_enabled(self, feature_id: str, enabled: bool) -> None:
        self._feature_enabled[feature_id] = enabled
        self.feature_toggled.emit(feature_id, enabled)

    def open_feature_config(self, feature_id: str) -> None:
        self.feature_config_requested.emit(feature_id)

    def set_execution_feedback_widget(self, widget: ExecutionFeedbackWidget) -> None:
        self._execution_feedback = widget

    def set_result_state(self, result_state: ExecutionResultState) -> None:
        self._result_state = result_state
```

- [ ] **Step 4: Wire feature toggles to dynamic navigation cards**

```python
def _on_feature_toggled(self, feature_id: str, enabled: bool) -> None:
    if enabled:
        self._ensure_feature_card(feature_id)
    else:
        self._remove_feature_card(feature_id)
```

- [ ] **Step 5: Add the first real dynamic panes**

```python
class HeadingNumberingPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._template = None

    def bind_template(self, template: TemplateConfig | None) -> None:
        self._template = template


class QuickFillPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._summary = ""

    def set_data_source_summary(self, text: str) -> None:
        self._summary = text
```

- [ ] **Step 6: Run the dynamic-card suite**

Run: `pytest tests/test_workbench_panel.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/ui/panels/workbench/quick_execute_pane.py src/ui/panels/workbench/heading_numbering_pane.py src/ui/panels/workbench/quick_fill_pane.py src/ui/panels/workbench/panel.py tests/test_workbench_panel.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py
git commit -m "feat: add quick execute dynamic feature cards"
```

### Task 6: Configuration Management and Execution Integration

**Files:**
- Modify: `src/ui/panels/workbench/config_management_pane.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `src/ui/panels/workbench/state.py`
- Modify: `tests/test_workbench_panel.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write failing tests for configuration management and quick-execute execution feedback**

```python
def test_config_management_pane_can_surface_saved_configs():
    panel = WorkbenchPanel(PanelBridge())
    panel._config_management_pane.set_saved_configs(
        [{"config_id": "cfg-1", "name": "论文标准", "description": "默认方案", "time": "2026-03-31 10:00"}]
    )

    assert "论文标准" in panel._config_management_pane.summary_text()


def test_quick_execute_reuses_existing_execution_worker_path():
    panel = WorkbenchPanel(PanelBridge())
    assert callable(panel._start_execution)
    assert panel._quick_execute_pane is not None
```

- [ ] **Step 2: Run the focused integration tests to verify the missing behavior**

Run: `pytest tests/test_workbench_layout.py tests/test_workbench_panel.py -q`
Expected: failures because config-management summary and quick-execute feedback wiring are not complete yet

- [ ] **Step 3: Add a small configuration-management surface**

```python
class ConfigManagementPane(QWidget):
    save_requested = Signal(str, str)
    load_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._configs: list[dict] = []

    def set_saved_configs(self, configs: list[dict]) -> None:
        self._configs = list(configs)

    def summary_text(self) -> str:
        return "\n".join(config["name"] for config in self._configs)
```

- [ ] **Step 4: Mount the shared execution feedback widget inside quick execute**

```python
self._execution_feedback = ExecutionFeedbackWidget(self)
self._quick_execute_pane.set_execution_feedback_widget(self._execution_feedback)
```

- [ ] **Step 5: Adapt existing execution callbacks to feed the new widget**

```python
def _on_execution_progress(self, current_step: int, total_steps: int, stage_text: str) -> None:
    self._execution_feedback.set_progress(current_step, total_steps, stage_text)

def apply_execution_result(self, result) -> None:
    payload = dict(result or {})
    result_state = self._execution_adapter.build_result_state(
        status=str(payload.get("status") or "failed"),
        output_path=str(payload.get("output_path") or ""),
        report_paths=list(payload.get("report_paths") or []),
        failed_count=int(payload.get("failed_count") or 0),
        error_text=str(payload.get("error_text") or ""),
    )
    self._quick_execute_pane.set_result_state(result_state)
    self._execution_feedback.set_completed(result_state.status == "success", {
        "success_count": max(0, 1 - result_state.failed_count),
        "warning_count": 0,
        "error_count": result_state.failed_count,
    })
```

- [ ] **Step 6: Run the homepage-focused suite**

Run: `pytest tests/test_workbench_layout.py tests/test_workbench_panel.py tests/test_execution_feedback_widget.py -q`
Expected: PASS

- [ ] **Step 7: Run the broad regression suite**

Run: `pytest tests/test_execution_worker.py tests/test_workbench_execution_center.py tests/test_recent_run_panel.py tests/test_workbench_layout.py tests/test_workbench_panel.py tests/test_ui_exports.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/ui/panels/workbench/config_management_pane.py src/ui/panels/workbench/panel.py src/ui/panels/workbench/state.py tests/test_workbench_layout.py tests/test_workbench_panel.py
git commit -m "feat: integrate config management and execution feedback into workbench v3"
```

## Follow-Up Plans Required After This Rollout

Do **not** continue adding these in the same branch without a new plan:

1. full `MappingTable` and quick-fill mapping editor
2. full `ModuleControl` pane with drag-and-drop ordering
3. full `OutputSettings` pane
4. full `ExecutionHistory` browser
5. generic low-priority shared widgets (`SplitPane`, `ContextMenu`, `Timeline`, `DataTable`)

## Verification Checklist

- `pytest tests/test_ui_exports.py tests/test_dynamic_navigation_rail.py tests/test_file_drop_zone.py tests/test_feature_toggle_row.py tests/test_execution_feedback_widget.py -q`
- `pytest tests/test_workbench_layout.py tests/test_workbench_panel.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py -q`
- `pytest tests/test_execution_worker.py tests/test_workbench_execution_center.py tests/test_recent_run_panel.py tests/test_workbench_layout.py tests/test_workbench_panel.py tests/test_ui_exports.py -q`

## Spec Coverage Notes

- V3 dynamic fixed + dynamic cards: covered by Tasks 4-5
- V3 quick-execute vertical flow: covered by Task 5
- V3 execution feedback in-context: covered by Tasks 3 and 6
- gap-analysis export cleanup: covered by Tasks 1-3
- gap-analysis shared missing widgets relevant to V3: covered by Tasks 1-3
- configuration management homepage slice: covered by Task 6
- advanced low-priority widgets: intentionally deferred
