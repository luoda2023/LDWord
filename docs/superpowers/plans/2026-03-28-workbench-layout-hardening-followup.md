# Workbench Layout Hardening Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current vertically stacked Workbench into the intended command-center structure: top current-task bar, middle left/right dual-column layout, and bottom recent-result area, then place the execution center and recent-run surfaces into those correct regions.

**Architecture:** Keep the already-landed Workbench subcomponents, but stop stacking them directly in one `QVBoxLayout`. Introduce a fixed page skeleton in `src/ui/panels/workbench/panel.py` with a middle `QHBoxLayout` split into a left task-adjustment column and a right execution column, plus a bottom recent-run region. Only after that skeleton exists should the execution center and recent-run panel become real components in those slots.

**Tech Stack:** Python, PySide6, pytest, shared UI card/theme/button helpers, existing Workbench state/adapters

---

> Note: this workspace is **not** a git repository, so normal commit steps cannot be executed here. Keep each task isolated in the diff and verify before moving on.

## Why this follow-up exists

The current Workbench has the right functional pieces for Tasks 1?5, but the page is still laid out as a vertical stack:

- current-task bar
- strategy card
- capability grid

This is structurally wrong for the approved command-center design. If we keep adding features without hardening the layout now, the page will continue to feel like a stacked form rather than a control surface. So the next implementation work must prioritize **layout hardening first**, then fill the right rail and bottom area.

## File map

- Modify: `src/ui/panels/workbench/panel.py`
  - Replace the current flat vertical stacking with the approved top/middle/bottom page skeleton
- Create: `src/ui/panels/workbench/execution_center.py`
  - Right-rail execution surface
- Create: `src/ui/panels/workbench/recent_run_panel.py`
  - Bottom recent-run / report summary surface
- Create: `src/ui/adapters/workbench_execution_adapter.py`
  - Readiness + execution summary adapter for the right rail
- Modify: `src/ui/panels/workbench/state.py`
  - Add execution-state dataclasses used by the execution center and recent-run panel
- Create: `src/ui/panels/workbench/styles.py`
  - Workbench-specific layout/styling helpers for the hardened skeleton
- Modify: `src/ui/panels/workbench/command_bar.py`
  - Let the top strip style integrate with the final Workbench stylesheet rather than floating visually on its own
- Modify: `src/ui/panels/workbench/capability_grid.py`
  - Keep its API stable, but ensure it sits inside the left column rather than acting as a top-level page section
- Modify: `src/ui/panels/workbench/strategy_card.py`
  - Ensure it fits the left-column ?strategy-first? placement cleanly
- Modify: `src/ui/panels/workbench/heading_quick_card.py`
  - No new advanced behavior, but it may need visual hooks/object names for the left-column grid
- Modify: `src/ui/panels/workbench/quick_fill_card.py`
  - No new Task 6 behavior, but it may need visual hooks/object names for the left-column grid
- Create: `tests/test_workbench_execution_center.py`
  - Readiness, summary, and right-rail render tests
- Modify: `tests/test_workbench_layout.py`
  - Convert the layout assertions from ?stacked regions exist? to ?approved page skeleton exists?

## Layout constraints to lock down in this follow-up

These are non-negotiable acceptance rules for the next implementation slice:

1. `WorkbenchPanel._root_layout` must have exactly three conceptual regions in order:
   - top current-task bar
   - middle dual-column layout
   - bottom recent-run area
2. The middle layout must be a `QHBoxLayout`, not more vertical stacking.
3. The left column must contain:
   - strategy card first
   - capability grid second
4. The right column must contain only the execution center in this slice.
5. The bottom region must contain only the recent-run panel in this slice.
6. `HeadingNumberingPanel` must still not be embedded inline on the homepage.
7. No new capability cards should be added until this page skeleton is correct.

### Task 1: Harden the Workbench page skeleton before adding any more behavior

**Files:**
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py
from src.qt_api import QHBoxLayout, QVBoxLayout


def test_workbench_panel_uses_top_middle_bottom_page_skeleton():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert isinstance(panel.layout(), QVBoxLayout)
        assert panel.layout().count() == 3
        assert panel.layout().itemAt(0).widget() is panel._command_bar
        assert panel.layout().itemAt(2).widget() is panel._recent_run_panel
    finally:
        panel.close()


def test_workbench_panel_middle_region_is_left_right_split():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        middle = panel._middle_container
        assert middle is not None
        assert isinstance(middle.layout(), QHBoxLayout)
        assert panel._left_column is not None
        assert panel._right_column is not None
    finally:
        panel.close()


def test_workbench_panel_left_column_orders_strategy_before_capability_grid():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        left_layout = panel._left_column.layout()
        assert left_layout.itemAt(0).widget() is panel._strategy_card
        assert left_layout.itemAt(1).widget() is panel._capability_grid
    finally:
        panel.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_uses_top_middle_bottom_page_skeleton tests/test_workbench_layout.py::test_workbench_panel_middle_region_is_left_right_split tests/test_workbench_layout.py::test_workbench_panel_left_column_orders_strategy_before_capability_grid -v`

Expected: FAIL because the current panel still stacks command bar, strategy card, and capability grid directly in one vertical layout.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/panel.py
from src.qt_api import QHBoxLayout, QVBoxLayout, QWidget
```

```python
# inside WorkbenchPanel._setup_ui()
self.setObjectName("WorkbenchPanel")
self._root_layout = QVBoxLayout(self)

self._command_bar = TaskCommandBar(self)
self._root_layout.addWidget(self._command_bar)

self._middle_container = QWidget(self)
self._middle_layout = QHBoxLayout(self._middle_container)
self._left_column = QWidget(self._middle_container)
self._left_layout = QVBoxLayout(self._left_column)
self._right_column = QWidget(self._middle_container)
self._right_layout = QVBoxLayout(self._right_column)

self._strategy_adapter = WorkbenchStrategyAdapter()
self._strategy_card = StrategyCard(self._left_column)
self._capability_grid = CapabilityGrid(self._left_column)
self._heading_quick_card = HeadingQuickCard(self.bridge, self._capability_grid)
self._capability_grid.add_card(self._heading_quick_card, 0, 0)
self._quick_fill_card = QuickFillCard(self.bridge, self._capability_grid)
self._capability_grid.add_card(self._quick_fill_card, 0, 1)

self._left_layout.addWidget(self._strategy_card)
self._left_layout.addWidget(self._capability_grid)

self._execution_adapter = WorkbenchExecutionAdapter()
self._execution_center = ExecutionCenter(self._right_column)
self._right_layout.addWidget(self._execution_center)

self._middle_layout.addWidget(self._left_column, 7)
self._middle_layout.addWidget(self._right_column, 3)
self._root_layout.addWidget(self._middle_container)

self._recent_run_panel = RecentRunPanel(self)
self._root_layout.addWidget(self._recent_run_panel)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_uses_top_middle_bottom_page_skeleton tests/test_workbench_layout.py::test_workbench_panel_middle_region_is_left_right_split tests/test_workbench_layout.py::test_workbench_panel_left_column_orders_strategy_before_capability_grid -v`

Expected: PASS

### Task 2: Add the execution-center state surface and right-rail component

**Files:**
- Create: `src/ui/panels/workbench/execution_center.py`
- Create: `src/ui/adapters/workbench_execution_adapter.py`
- Modify: `src/ui/panels/workbench/state.py`
- Modify: `tests/test_workbench_execution_center.py`

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

Expected: FAIL because the execution-center state and widget do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/state.py
from dataclasses import dataclass, field


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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_execution_center.py -v`

Expected: PASS

### Task 3: Add the bottom recent-run panel so the page has a real third region

**Files:**
- Create: `src/ui/panels/workbench/recent_run_panel.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py

def test_workbench_panel_mounts_recent_run_panel_in_bottom_region():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._recent_run_panel is not None
        assert panel.layout().itemAt(2).widget() is panel._recent_run_panel
    finally:
        panel.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_mounts_recent_run_panel_in_bottom_region -v`

Expected: FAIL because `_recent_run_panel` is currently missing.

- [ ] **Step 3: Write the minimal implementation**

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

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_mounts_recent_run_panel_in_bottom_region -v`

Expected: PASS

### Task 4: Lock the right-rail and bottom-region placement with layout regression tests

**Files:**
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py

def test_workbench_panel_right_column_hosts_execution_center_only():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        right_layout = panel._right_column.layout()
        assert right_layout.itemAt(0).widget() is panel._execution_center
        assert right_layout.count() == 1
    finally:
        panel.close()


def test_workbench_panel_bottom_region_is_not_part_of_middle_columns():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._recent_run_panel.parent() is panel
        assert panel._recent_run_panel.parent() is not panel._left_column
        assert panel._recent_run_panel.parent() is not panel._right_column
    finally:
        panel.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_right_column_hosts_execution_center_only tests/test_workbench_layout.py::test_workbench_panel_bottom_region_is_not_part_of_middle_columns -v`

Expected: FAIL until the proper middle/right/bottom layout is in place.

- [ ] **Step 3: Run the tests to verify they pass after the layout hardening work**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_right_column_hosts_execution_center_only tests/test_workbench_layout.py::test_workbench_panel_bottom_region_is_not_part_of_middle_columns -v`

Expected: PASS

### Task 5: Focused layout-hardening verification

**Files:**
- Modify: `docs/superpowers/plans/2026-03-28-workbench-layout-hardening-followup.md`

- [ ] **Step 1: Run the focused Workbench layout + execution slice tests**

Run: `pytest tests/test_workbench_layout.py tests/test_workbench_execution_center.py tests/test_workbench_strategy_card.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py -v`

Expected: PASS

- [ ] **Step 2: Run the full suite once the focused slice is green**

Run: `pytest tests -q`

Expected: PASS

- [ ] **Step 3: Manual smoke**

Run: `python main.py --gui`

Expected:
- the page no longer feels like a vertical stack,
- the command bar sits on top,
- the middle region is visibly left/right split,
- the strategy card and capability grid live in the left column,
- the execution center lives in the right rail,
- the recent-run panel occupies a distinct bottom region.
