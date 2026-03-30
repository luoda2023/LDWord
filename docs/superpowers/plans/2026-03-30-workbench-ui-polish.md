# Workbench UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Workbench into a visually coherent command center with clear surface hierarchy, consistent Chinese operational copy, and stronger execution-first emphasis without changing the page architecture or execution behavior.

**Architecture:** Keep the current Workbench structure and execution lifecycle intact, and limit this pass to presentation-layer changes plus the smallest state/copy updates needed to support them. Centralize the hierarchy in `src/ui/panels/workbench/styles.py`, keep widgets focused on structure and object names, and lock the polish with UI-facing regression tests instead of manual visual judgment alone.

**Tech Stack:** Python, PySide6, pytest, shared theme/button/card helpers, existing Workbench panel/adapters/state

---

## File map

- Modify: `src/ui/panels/workbench/styles.py`
  - Encode role-based visual hierarchy for the task strip, execution center, strategy card, quick cards, and recent-run panel
- Modify: `src/ui/panels/workbench/command_bar.py`
  - Refine current-task strip density, copy, and semantic object names
- Modify: `src/ui/panels/workbench/execution_center.py`
  - Add stronger section structure and style hooks for the primary action surface
- Modify: `src/ui/panels/workbench/strategy_card.py`
  - Tighten summary presentation and add style hooks for the baseline surface
- Modify: `src/ui/panels/workbench/heading_quick_card.py`
  - Add quick-action-specific style hooks and concise summary copy
- Modify: `src/ui/panels/workbench/quick_fill_card.py`
  - Add quick-action-specific style hooks and concise summary copy
- Modify: `src/ui/panels/workbench/recent_run_panel.py`
  - Keep the bottom panel visually quieter while remaining informative
- Modify: `src/ui/panels/workbench/panel.py`
  - Apply the new stylesheet and stop emitting English `Ready` copy from the page-level ready path
- Modify: `src/ui/adapters/workbench_execution_adapter.py`
  - Normalize ready-state copy to Chinese operational language
- Modify: `tests/test_workbench_layout.py`
  - Lock page-level polish expectations and stylesheet hierarchy
- Modify: `tests/test_workbench_execution_center.py`
  - Lock Chinese copy and primary-surface rendering expectations

### Task 1: Lock Chinese operational copy and role hierarchy with failing tests

**Files:**
- Modify: `tests/test_workbench_layout.py`
- Modify: `tests/test_workbench_execution_center.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_workbench_ready_copy_uses_chinese_operational_language():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._command_bar._status_value.text() == "待执行"
        assert panel._execution_center._ready_label.text() == "待执行"
    finally:
        panel.close()


def test_workbench_stylesheet_encodes_surface_hierarchy():
    stylesheet = build_workbench_stylesheet(get_theme())

    assert "#wb_execution_center {" in stylesheet
    assert "border: 2px solid" in stylesheet
    assert "#wb_recent_run {" in stylesheet
    assert "#wb_heading_quick_card," in stylesheet
    assert "#wb_quick_fill_card {" in stylesheet


def test_execution_center_exposes_polish_section_labels():
    _app()
    center = ExecutionCenter()

    assert center._center_title.text() == "执行中心"
    assert center._summary_title.text() == "执行摘要"
    assert center._progress_title.text() == "执行进度"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_workbench_ready_copy_uses_chinese_operational_language tests/test_workbench_layout.py::test_workbench_stylesheet_encodes_surface_hierarchy tests/test_workbench_execution_center.py::test_execution_center_exposes_polish_section_labels -v`

Expected: FAIL because the current ready path still emits `Ready`, the stylesheet still treats all surfaces the same, and the execution center does not yet expose the new section labels.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/adapters/workbench_execution_adapter.py
return ReadinessState(
    ready=not reasons,
    label="待执行",
    reasons=reasons,
)
```

```python
# src/ui/panels/workbench/panel.py
self.set_current_task_state(
    CurrentTaskState(
        document_label=CurrentTaskState().document_label,
        strategy_label="默认策略",
        ready=True,
        status_text="待执行",
    )
)
```

```python
# src/ui/panels/workbench/execution_center.py
self._summary_title = QLabel("执行摘要")
self._progress_title = QLabel("执行进度")
```

```python
# src/ui/panels/workbench/styles.py
#wb_execution_center {
    border: 2px solid {t.border_focus};
}

#wb_heading_quick_card,
#wb_quick_fill_card {
    ...
}
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/test_workbench_layout.py::test_workbench_ready_copy_uses_chinese_operational_language tests/test_workbench_layout.py::test_workbench_stylesheet_encodes_surface_hierarchy tests/test_workbench_execution_center.py::test_execution_center_exposes_polish_section_labels -v`

Expected: PASS

### Task 2: Make the execution center the page's primary action surface

**Files:**
- Modify: `src/ui/panels/workbench/styles.py`
- Modify: `src/ui/panels/workbench/execution_center.py`
- Modify: `tests/test_workbench_execution_center.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_execution_center_primary_surface_uses_section_titles_and_running_status():
    _app()
    center = ExecutionCenter()
    center.set_readiness(ReadinessState(ready=True, label="待执行", reasons=[]))
    center.set_progress_state(
        ExecutionProgressState(stage_text="执行中", current_step=1, total_steps=2, percent=50)
    )

    assert center._progress_title.text() == "执行进度"
    assert center._summary_title.text() == "执行摘要"
    assert center._status_label.text() == "执行中"
    assert center._execute_button.isEnabled() is False
    assert center._cancel_button.isEnabled() is True


def test_workbench_stylesheet_marks_execution_center_as_primary_surface():
    stylesheet = build_workbench_stylesheet(get_theme())

    execution_start = stylesheet.index("#wb_execution_center {")
    execution_end = stylesheet.index("}", execution_start)
    block = stylesheet[execution_start:execution_end]

    assert "border: 2px solid" in block
    assert "background:" in block
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_center_primary_surface_uses_section_titles_and_running_status tests/test_workbench_execution_center.py::test_workbench_stylesheet_marks_execution_center_as_primary_surface -v`

Expected: FAIL until the execution center gains explicit internal sections and the stylesheet makes it visually stronger than the other surfaces.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/execution_center.py
self._center_title.setObjectName("wb_execution_title")
self._summary_title.setObjectName("wb_execution_section_title")
self._progress_title.setObjectName("wb_execution_section_title")
self._status_label.setObjectName("wb_execution_status")
self._summary_box.setObjectName("wb_execution_summary")
```

```python
# src/ui/panels/workbench/styles.py
#wb_execution_center {
    background: {t.bg_card};
    border: 2px solid {t.border_focus};
    border-radius: {t.radius_lg}px;
}

#wb_execution_section_title {
    color: {t.text_primary};
    font-size: {t.font_size_sm}px;
    font-weight: {t.font_weight_bold};
}

#wb_execution_summary {
    background: {t.bg_hover};
    border: 1px solid {t.border_light};
    border-radius: {t.radius_sm}px;
}
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_center_primary_surface_uses_section_titles_and_running_status tests/test_workbench_execution_center.py::test_workbench_stylesheet_marks_execution_center_as_primary_surface -v`

Expected: PASS

### Task 3: Refine the current-task strip and the secondary surfaces

**Files:**
- Modify: `src/ui/panels/workbench/command_bar.py`
- Modify: `src/ui/panels/workbench/strategy_card.py`
- Modify: `src/ui/panels/workbench/heading_quick_card.py`
- Modify: `src/ui/panels/workbench/quick_fill_card.py`
- Modify: `src/ui/panels/workbench/recent_run_panel.py`
- Modify: `src/ui/panels/workbench/styles.py`
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_workbench_panel_assigns_role_specific_object_names():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        assert panel._heading_quick_card.objectName() == "wb_heading_quick_card"
        assert panel._quick_fill_card.objectName() == "wb_quick_fill_card"
        assert panel._recent_run_panel.objectName() == "wb_recent_run"
        assert panel._strategy_card.objectName() == "wb_strategy_card"
    finally:
        panel.close()


def test_workbench_stylesheet_quiets_recent_run_and_secondary_cards():
    stylesheet = build_workbench_stylesheet(get_theme())

    recent_start = stylesheet.index("#wb_recent_run {")
    recent_end = stylesheet.index("}", recent_start)
    recent_block = stylesheet[recent_start:recent_end]

    assert "background:" in recent_block
    assert "border: 1px solid" in recent_block
    assert "#wb_heading_quick_card," in stylesheet
    assert "#wb_quick_fill_card {" in stylesheet
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_assigns_role_specific_object_names tests/test_workbench_layout.py::test_workbench_stylesheet_quiets_recent_run_and_secondary_cards -v`

Expected: FAIL because the quick cards do not yet expose role-specific object names and the stylesheet does not yet differentiate secondary vs muted surfaces.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/panel.py
self._heading_quick_card.setObjectName("wb_heading_quick_card")
self._quick_fill_card.setObjectName("wb_quick_fill_card")
```

```python
# src/ui/panels/workbench/styles.py
#wb_command_bar,
#wb_strategy_card {
    background: {t.bg_card};
    border: 1px solid {t.border};
}

#wb_heading_quick_card,
#wb_quick_fill_card {
    background: {t.bg_hover};
    border: 1px solid {t.border_light};
}

#wb_recent_run {
    background: {t.bg_sidebar};
    border: 1px solid {t.border_light};
}
```

```python
# src/ui/panels/workbench/command_bar.py
layout.setContentsMargins(16, 10, 16, 10)
layout.setSpacing(12)
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_assigns_role_specific_object_names tests/test_workbench_layout.py::test_workbench_stylesheet_quiets_recent_run_and_secondary_cards -v`

Expected: PASS

### Task 4: Run polish verification on the integrated page

**Files:**
- Modify: `tests/test_workbench_layout.py`
- Modify: `tests/test_workbench_execution_center.py`

- [ ] **Step 1: Run the focused polish suite**

Run: `pytest tests/test_workbench_layout.py tests/test_workbench_execution_center.py tests/test_heading_quick_card.py tests/test_quick_fill_card.py -v`

Expected: PASS

- [ ] **Step 2: Run the execution-related regression suite**

Run: `pytest tests/test_execution_worker.py tests/test_workbench_execution_center.py tests/test_recent_run_panel.py tests/test_workbench_layout.py tests/test_workbench_panel.py -q`

Expected: PASS

- [ ] **Step 3: Run the full suite**

Run: `pytest tests -q`

Expected: PASS

- [ ] **Step 4: Manual smoke**

Run: `python main.py --gui`

Expected:
- the execution center is visually stronger than the strategy card,
- the command bar reads like a compact task strip rather than a generic toolbar,
- quick cards feel lighter than the strategy card,
- the recent-run panel feels quieter than the execution center,
- the homepage no longer mixes English `Ready` into the visible Workbench status flow.
