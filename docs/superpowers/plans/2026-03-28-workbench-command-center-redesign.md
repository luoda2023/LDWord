# Workbench Command Center Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the current Workbench homepage into a high-frequency command center with a current-task bar, execution-strategy card, quick capability grid, fixed execution center, and recent-run panel.

**Architecture:** Keep the existing main shell and navigation stable, but move Workbench internals into a dedicated `src/ui/panels/workbench/` package. Introduce thin adapter/state layers so the homepage can treat "current document + current strategy" as the primary task object, render quick cards instead of full editors, and keep execution logic isolated from layout composition.

**Tech Stack:** Python, PySide6, pytest, existing config/loader/resolver/pipeline/report infrastructure, shared UI theme/card/form/progress components

---

> Note: this workspace is **not** a git repository, so normal commit steps cannot be executed here. Keep each task isolated in the diff and verify before moving on.

## File map

- Modify: `src/ui/panels/workbench_panel.py`
  - Keep the stable import path and re-export the real Workbench panel from the new package
- Create: `src/ui/panels/workbench/__init__.py`
  - Public exports for Workbench subcomponents
- Create: `src/ui/panels/workbench/panel.py`
  - Real Workbench panel composition and orchestration
- Create: `src/ui/panels/workbench/state.py`
  - Dataclasses for current-task, strategy summary, readiness, execution summary, and recent-run state
- Create: `src/ui/panels/workbench/styles.py`
  - Tokenized Workbench-specific stylesheet helpers
- Create: `src/ui/panels/workbench/command_bar.py`
  - Top "current task" command bar
- Create: `src/ui/panels/workbench/strategy_card.py`
  - Execution strategy summary card + actions
- Create: `src/ui/panels/workbench/capability_grid.py`
  - Left-column quick-card container
- Create: `src/ui/panels/workbench/heading_quick_card.py`
  - Homepage summary card for heading numbering
- Create: `src/ui/panels/workbench/quick_fill_card.py`
  - Homepage summary card for quick fill
- Create: `src/ui/panels/workbench/execution_center.py`
  - Fixed right-rail execution center
- Create: `src/ui/panels/workbench/recent_run_panel.py`
  - Bottom recent-run / report / error summary panel
- Create: `src/ui/panels/workbench/more_capabilities_card.py`
  - Overflow entry point for non-default homepage capabilities
- Create: `src/ui/adapters/workbench_strategy_adapter.py`
  - Strategy summary, switching, save-as, duplicate, rename, restore operations
- Create: `src/ui/adapters/workbench_execution_adapter.py`
  - Readiness computation, run summary, pipeline execution, recent-run state
- Modify: `src/ui/adapters/__init__.py`
  - Export the new adapters if the package already centralizes adapter imports
- Modify: `src/ui/main_window.py`
  - No layout rewrite; only ensure the workbench import path continues to resolve cleanly after package split
- Modify: `src/ui/panel_registry.py`
  - Keep workbench registration stable via the existing ID
- Modify: `src/ui/panels/heading_numbering_panel.py`
  - Keep advanced editor behavior, but make it safe to open from the Workbench quick-card flow
- Create: `tests/test_workbench_layout.py`
  - Structure-level tests for command bar / strategy card / grid / execution center / recent-run panel
- Create: `tests/test_workbench_strategy_card.py`
  - Strategy model/card behavior tests
- Create: `tests/test_workbench_execution_center.py`
  - Readiness / summary / result rendering tests
- Create: `tests/test_heading_quick_card.py`
  - Heading quick-card summary and advanced-entry tests
- Create: `tests/test_quick_fill_card.py`
  - Quick-fill card presence, summary, and action tests
- Modify: `tests/test_workbench_panel.py`
  - Update old Workbench MVP tests to point at the redesigned command-center surface

### Task 1: Split Workbench into a dedicated package and keep the old import path stable

**Files:**
- Modify: `src/ui/panels/workbench_panel.py`
- Create: `src/ui/panels/workbench/__init__.py`
- Create: `src/ui/panels/workbench/panel.py`
- Modify: `tests/test_workbench_panel.py`
- Create: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_workbench_panel_import_path_stays_stable_after_package_split():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel.__class__.__name__ == "WorkbenchPanel"
        assert panel.objectName() == "WorkbenchPanel"
    finally:
        panel.close()


def test_workbench_panel_exposes_command_center_regions():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_command_bar")
        assert hasattr(panel, "_strategy_card")
        assert hasattr(panel, "_capability_grid")
        assert hasattr(panel, "_execution_center")
        assert hasattr(panel, "_recent_run_panel")
    finally:
        panel.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_import_path_stays_stable_after_package_split tests/test_workbench_layout.py::test_workbench_panel_exposes_command_center_regions -v`

Expected: FAIL because the current Workbench still lives in one file and does not expose the command-center regions.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench_panel.py
from .workbench.panel import WorkbenchPanel

__all__ = ["WorkbenchPanel"]
```

```python
# src/ui/panels/workbench/__init__.py
from .panel import WorkbenchPanel

__all__ = ["WorkbenchPanel"]
```

```python
# src/ui/panels/workbench/panel.py
from __future__ import annotations

from src.qt_api import QVBoxLayout

from src.ui.base_panel import BasePanel


class WorkbenchPanel(BasePanel):
    def _setup_ui(self) -> None:
        self.setObjectName("WorkbenchPanel")
        self._root_layout = QVBoxLayout(self)
        self._command_bar = None
        self._strategy_card = None
        self._capability_grid = None
        self._execution_center = None
        self._recent_run_panel = None

    def _connect_signals(self) -> None:
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_import_path_stays_stable_after_package_split tests/test_workbench_layout.py::test_workbench_panel_exposes_command_center_regions -v`

Expected: PASS

### Task 2: Add Workbench state models and the top current-task command bar

**Files:**
- Create: `src/ui/panels/workbench/state.py`
- Create: `src/ui/panels/workbench/command_bar.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Create: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py
from src.ui.panels.workbench.command_bar import TaskCommandBar
from src.ui.panels.workbench.state import CurrentTaskState


def test_current_task_state_defaults_to_not_ready():
    state = CurrentTaskState()

    assert state.document_label == "未选择文档"
    assert state.strategy_label == "未选择策略"
    assert state.ready is False
    assert state.status_text == "待执行"


def test_task_command_bar_renders_document_strategy_and_ready_status(qtbot=None):
    _app()
    bar = TaskCommandBar()
    state = CurrentTaskState(
        document_label="thesis.docx",
        strategy_label="论文标准",
        ready=True,
        status_text="Ready",
    )

    bar.set_state(state)

    assert bar._doc_value.text() == "thesis.docx"
    assert bar._strategy_value.text() == "论文标准"
    assert bar._status_value.text() == "Ready"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_current_task_state_defaults_to_not_ready tests/test_workbench_layout.py::test_task_command_bar_renders_document_strategy_and_ready_status -v`

Expected: FAIL because the state model and command bar do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/state.py
from dataclasses import dataclass


@dataclass(slots=True)
class CurrentTaskState:
    document_label: str = "未选择文档"
    strategy_label: str = "未选择策略"
    ready: bool = False
    status_text: str = "待执行"
```

```python
# src/ui/panels/workbench/command_bar.py
from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QPushButton, QWidget
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.theme import bind_theme, get_theme
from .state import CurrentTaskState


class TaskCommandBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self._doc_value = QLabel()
        self._strategy_value = QLabel()
        self._status_value = QLabel()
        self._run_button = QPushButton("开始执行")
        apply_button_variant(self._run_button, "primary")
        layout.addWidget(self._doc_value)
        layout.addWidget(self._strategy_value)
        layout.addWidget(self._status_value)
        layout.addStretch(1)
        layout.addWidget(self._run_button)
        self.set_state(CurrentTaskState())
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_state(self, state: CurrentTaskState) -> None:
        self._doc_value.setText(state.document_label)
        self._strategy_value.setText(state.strategy_label)
        self._status_value.setText(state.status_text)
        self._run_button.setEnabled(state.ready)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(f"QWidget {{ background: {t.bg_card}; border: 1px solid {t.border}; border-radius: {t.radius_md}px; }}")
```

```python
# src/ui/panels/workbench/panel.py
from .command_bar import TaskCommandBar

self._command_bar = TaskCommandBar(self)
self._root_layout.addWidget(self._command_bar)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_layout.py::test_current_task_state_defaults_to_not_ready tests/test_workbench_layout.py::test_task_command_bar_renders_document_strategy_and_ready_status -v`

Expected: PASS

### Task 3: Add strategy state + strategy card so the homepage promotes execution strategy instead of separate template/scene blocks

**Files:**
- Create: `src/ui/panels/workbench/strategy_card.py`
- Create: `src/ui/adapters/workbench_strategy_adapter.py`
- Modify: `src/ui/panels/workbench/state.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Create: `tests/test_workbench_strategy_card.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_strategy_card.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter
from src.ui.panels.workbench.state import StrategySummaryState
from src.ui.panels.workbench.strategy_card import StrategyCard


def _app():
    return QApplication.instance() or QApplication([])


def test_strategy_summary_state_exposes_homepage_safe_fields():
    state = StrategySummaryState()

    assert state.name == "未命名策略"
    assert state.source_type == "default"
    assert state.template_label == "未绑定模板"
    assert state.scene_label == "未绑定场景"


def test_strategy_card_renders_strategy_summary_labels():
    _app()
    card = StrategyCard()
    state = StrategySummaryState(
        name="论文标准",
        source_type="favorite",
        template_label="thesis.yaml",
        scene_label="结构优先",
        strict_mode=True,
        enabled_module_count=3,
    )

    card.set_state(state)

    assert card._name_value.text() == "论文标准"
    assert card._template_value.text() == "thesis.yaml"
    assert card._scene_value.text() == "结构优先"
    assert "3" in card._modules_value.text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_strategy_card.py -v`

Expected: FAIL because the strategy state, card, and adapter do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/state.py
@dataclass(slots=True)
class StrategySummaryState:
    name: str = "未命名策略"
    source_type: str = "default"
    template_label: str = "未绑定模板"
    scene_label: str = "未绑定场景"
    strict_mode: bool = True
    enabled_module_count: int = 0
```

```python
# src/ui/adapters/workbench_strategy_adapter.py
from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.ui.panels.workbench.state import StrategySummaryState


class WorkbenchStrategyAdapter:
    def build_summary(self, template: TemplateConfig | None, scene: SceneWorkspace | None) -> StrategySummaryState:
        if template is None or scene is None:
            return StrategySummaryState()
        enabled_count = sum(1 for enabled in scene.module_switches.values() if enabled)
        return StrategySummaryState(
            name=scene.name or "未命名策略",
            source_type="default",
            template_label=template.name or "未绑定模板",
            scene_label=scene.description or scene.category_label or "通用场景",
            strict_mode=scene.strict_mode,
            enabled_module_count=enabled_count,
        )
```

```python
# src/ui/panels/workbench/strategy_card.py
from __future__ import annotations

from src.qt_api import QLabel
from src.shared.ui.card import Card
from .state import StrategySummaryState


class StrategyCard(Card):
    def __init__(self, parent=None):
        super().__init__("执行策略", parent=parent)
        self._name_value = QLabel()
        self._template_value = QLabel()
        self._scene_value = QLabel()
        self._modules_value = QLabel()
        for widget in (self._name_value, self._template_value, self._scene_value, self._modules_value):
            self.add_widget(widget)
        self.set_state(StrategySummaryState())

    def set_state(self, state: StrategySummaryState) -> None:
        self._name_value.setText(state.name)
        self._template_value.setText(state.template_label)
        self._scene_value.setText(state.scene_label)
        self._modules_value.setText(f"启用模块: {state.enabled_module_count}")
```

```python
# src/ui/panels/workbench/panel.py
from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter
from .strategy_card import StrategyCard

self._strategy_adapter = WorkbenchStrategyAdapter()
self._strategy_card = StrategyCard(self)
self._root_layout.addWidget(self._strategy_card)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_strategy_card.py -v`

Expected: PASS

### Task 4: Add capability grid and replace the full homepage heading editor with a heading quick card + advanced entry

**Files:**
- Create: `src/ui/panels/workbench/capability_grid.py`
- Create: `src/ui/panels/workbench/heading_quick_card.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `src/ui/panels/heading_numbering_panel.py`
- Create: `tests/test_heading_quick_card.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_heading_quick_card.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.heading_quick_card import HeadingQuickCard
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_heading_quick_card_exposes_summary_and_advanced_button():
    _app()
    card = HeadingQuickCard(PanelBridge())

    assert hasattr(card, "_summary_label")
    assert hasattr(card, "_advanced_btn")


def test_workbench_uses_heading_quick_card_instead_of_inline_full_editor():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_heading_quick_card")
        assert panel.findChild(HeadingNumberingPanel) is None
    finally:
        panel.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_heading_quick_card.py -v`

Expected: FAIL because the homepage still depends on the full heading editor and no heading quick-card exists.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/capability_grid.py
from __future__ import annotations

from src.qt_api import QGridLayout, QWidget


class CapabilityGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    def add_card(self, widget: QWidget, row: int, column: int) -> None:
        self._layout.addWidget(widget, row, column)
```

```python
# src/ui/panels/workbench/heading_quick_card.py
from __future__ import annotations

from src.qt_api import QLabel, QPushButton, Signal
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card


class HeadingQuickCard(Card):
    advanced_requested = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__("标题编号", parent=parent)
        self._summary_label = QLabel("当前方案：未读取")
        self._advanced_btn = QPushButton("高级配置")
        apply_button_variant(self._advanced_btn, "secondary")
        self._advanced_btn.clicked.connect(self.advanced_requested.emit)
        self.add_widget(self._summary_label)
        self.add_widget(self._advanced_btn)
```

```python
# src/ui/panels/workbench/panel.py
from .capability_grid import CapabilityGrid
from .heading_quick_card import HeadingQuickCard

self._capability_grid = CapabilityGrid(self)
self._heading_quick_card = HeadingQuickCard(self.bridge, self)
self._capability_grid.add_card(self._heading_quick_card, 0, 0)
self._root_layout.addWidget(self._capability_grid)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_heading_quick_card.py -v`

Expected: PASS

### Task 5: Add quick-fill homepage placement so the command center is not single-capability

**Files:**
- Create: `src/ui/panels/workbench/quick_fill_card.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Create: `tests/test_quick_fill_card.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quick_fill_card.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.quick_fill_card import QuickFillCard
from src.ui.panels.workbench_panel import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_quick_fill_card_exposes_summary_and_actions():
    _app()
    card = QuickFillCard(PanelBridge())

    assert hasattr(card, "_source_summary")
    assert hasattr(card, "_quick_setup_btn")
    assert hasattr(card, "_advanced_mapping_btn")


def test_workbench_includes_quick_fill_as_default_homepage_card():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert hasattr(panel, "_quick_fill_card")
    finally:
        panel.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_quick_fill_card.py -v`

Expected: FAIL because quick fill has no homepage card yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/quick_fill_card.py
from __future__ import annotations

from src.qt_api import QLabel, QPushButton
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card


class QuickFillCard(Card):
    def __init__(self, bridge, parent=None):
        super().__init__("快捷填充", parent=parent)
        self._source_summary = QLabel("当前填充源：未连接")
        self._entity_summary = QLabel("实体/素材：未选择")
        self._quick_setup_btn = QPushButton("快速设置")
        self._advanced_mapping_btn = QPushButton("高级映射")
        apply_button_variant(self._quick_setup_btn, "secondary")
        apply_button_variant(self._advanced_mapping_btn, "ghost")
        self.add_widget(self._source_summary)
        self.add_widget(self._entity_summary)
        self.add_widget(self._quick_setup_btn)
        self.add_widget(self._advanced_mapping_btn)
```

```python
# src/ui/panels/workbench/panel.py
from .quick_fill_card import QuickFillCard

self._quick_fill_card = QuickFillCard(self.bridge, self)
self._capability_grid.add_card(self._quick_fill_card, 0, 1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_quick_fill_card.py -v`

Expected: PASS

### Task 6: Add fixed execution center + recent-run panel so the page reads like a command center

**Files:**
- Create: `src/ui/panels/workbench/execution_center.py`
- Create: `src/ui/panels/workbench/recent_run_panel.py`
- Create: `src/ui/adapters/workbench_execution_adapter.py`
- Modify: `src/ui/panels/workbench/state.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Create: `tests/test_workbench_execution_center.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_execution_center.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.panels.workbench.execution_center import ExecutionCenter
from src.ui.panels.workbench.state import ReadinessState


def _app():
    return QApplication.instance() or QApplication([])


def test_readiness_state_defaults_to_blocked():
    state = ReadinessState()

    assert state.ready is False
    assert state.label == "待执行"
    assert state.reasons == ["未选择文档", "未选择策略"]


def test_execution_center_renders_readiness_and_summary():
    _app()
    center = ExecutionCenter()
    state = ReadinessState(ready=True, label="Ready", reasons=[])

    center.set_readiness(state)
    center.set_summary("本次启用模块：3")

    assert center._ready_label.text() == "Ready"
    assert center._summary_box.toPlainText() == "本次启用模块：3"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_execution_center.py -v`

Expected: FAIL because the execution-center state, adapter, and panel do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/state.py
@dataclass(slots=True)
class ReadinessState:
    ready: bool = False
    label: str = "待执行"
    reasons: list[str] = field(default_factory=lambda: ["未选择文档", "未选择策略"])
```

```python
# src/ui/adapters/workbench_execution_adapter.py
from __future__ import annotations

from src.ui.panels.workbench.state import ReadinessState


class WorkbenchExecutionAdapter:
    def build_readiness(self, *, has_document: bool, has_strategy: bool) -> ReadinessState:
        reasons = []
        if not has_document:
            reasons.append("未选择文档")
        if not has_strategy:
            reasons.append("未选择策略")
        return ReadinessState(
            ready=not reasons,
            label="Ready" if not reasons else "待执行",
            reasons=reasons,
        )
```

```python
# src/ui/panels/workbench/execution_center.py
from __future__ import annotations

from src.qt_api import QLabel, QTextEdit, QVBoxLayout, QWidget
from .state import ReadinessState


class ExecutionCenter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._ready_label = QLabel("待执行")
        self._summary_box = QTextEdit()
        self._summary_box.setReadOnly(True)
        layout.addWidget(self._ready_label)
        layout.addWidget(self._summary_box)

    def set_readiness(self, state: ReadinessState) -> None:
        self._ready_label.setText(state.label)

    def set_summary(self, text: str) -> None:
        self._summary_box.setPlainText(text)
```

```python
# src/ui/panels/workbench/recent_run_panel.py
from __future__ import annotations

from src.qt_api import QLabel
from src.shared.ui.card import Card


class RecentRunPanel(Card):
    def __init__(self, parent=None):
        super().__init__("最近结果", parent=parent)
        self._summary = QLabel("暂无最近结果")
        self.add_widget(self._summary)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)
```

```python
# src/ui/panels/workbench/panel.py
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from .execution_center import ExecutionCenter
from .recent_run_panel import RecentRunPanel

self._execution_adapter = WorkbenchExecutionAdapter()
self._execution_center = ExecutionCenter(self)
self._recent_run_panel = RecentRunPanel(self)
self._root_layout.addWidget(self._execution_center)
self._root_layout.addWidget(self._recent_run_panel)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_execution_center.py -v`

Expected: PASS

### Task 7: Add Workbench styles and command-center naming so the page reads as a control surface instead of a form

**Files:**
- Create: `src/ui/panels/workbench/styles.py`
- Modify: `src/ui/panels/workbench/command_bar.py`
- Modify: `src/ui/panels/workbench/strategy_card.py`
- Modify: `src/ui/panels/workbench/execution_center.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_workbench_stylesheet_uses_command_center_naming_and_tokens():
    source = (ROOT / "src/ui/panels/workbench/styles.py").read_text(encoding="utf-8")

    assert "任务中控" in source or "执行策略" in source or "执行中心" in source
    assert "bg_card" in source
    assert "radius_md" in source
    assert "#FFFFFF" not in source


def test_workbench_panel_source_no_longer_embeds_old_mvp_labels():
    source = (ROOT / "src/ui/panels/workbench/panel.py").read_text(encoding="utf-8")

    assert "模板与场景" not in source
    assert "任务中控" in source or "执行策略" in source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_workbench_stylesheet_uses_command_center_naming_and_tokens tests/test_workbench_layout.py::test_workbench_panel_source_no_longer_embeds_old_mvp_labels -v`

Expected: FAIL because the command-center naming and shared styles do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/styles.py
from __future__ import annotations

from src.shared.ui.theme import AppTheme


def build_workbench_stylesheet(t: AppTheme) -> str:
    return f"""
    #WorkbenchPanel {{
        background: {t.bg_window};
    }}
    #wb_command_bar, #wb_strategy_card, #wb_execution_center, #wb_recent_run {{
        background: {t.bg_card};
        border: 1px solid {t.border};
        border-radius: {t.radius_md}px;
    }}
    #wb_ready_badge {{
        background: {t.bg_hover};
        color: {t.text_primary};
        border-radius: {t.radius_sm}px;
    }}
    """
```

```python
# src/ui/panels/workbench/panel.py
from .styles import build_workbench_stylesheet

self._header_title.setText("任务中控")
self._command_bar.setObjectName("wb_command_bar")
self.setStyleSheet(build_workbench_stylesheet(get_theme()))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_layout.py::test_workbench_stylesheet_uses_command_center_naming_and_tokens tests/test_workbench_layout.py::test_workbench_panel_source_no_longer_embeds_old_mvp_labels -v`

Expected: PASS

### Task 8: Run focused and full redesign verification

**Files:**
- Modify: `docs/superpowers/plans/2026-03-28-workbench-command-center-redesign.md`

- [ ] **Step 1: Run the focused Workbench redesign suite**

Run: `pytest tests/test_workbench_panel.py tests/test_workbench_layout.py tests/test_workbench_strategy_card.py tests/test_workbench_execution_center.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py -v`

Expected: PASS

- [ ] **Step 2: Run the affected heading-panel regressions**

Run: `pytest tests/test_heading_panel_level_slider.py tests/test_heading_panel_mode_controls.py tests/test_heading_numbering_logic.py -v`

Expected: PASS

- [ ] **Step 3: Run the full suite**

Run: `pytest tests -q`

Expected: PASS

- [ ] **Step 4: Manual smoke**

Run: `python main.py --gui`

Expected:
- top bar reads like a current-task control strip,
- the left column shows strategy + quick cards instead of a giant embedded editor,
- the right rail remains visually stable as execution center,
- the bottom area summarizes the latest run,
- the homepage feels like a command center rather than a configuration form.
