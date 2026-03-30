# Execution Center Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current right-side execution center into a real execution-control surface with background execution, live progress, cancel support, final result states, and synchronized recent-run summaries.

**Architecture:** Keep `WorkbenchPanel` as the page-level coordinator, keep `ExecutionCenter` as a UI-only control surface, and introduce a background `ExecutionWorker` running inside `QThread`. Expand `WorkbenchExecutionAdapter` and `state.py` so the execution center and recent-run panel receive structured progress/result state instead of ad-hoc strings.

**Tech Stack:** Python, PySide6, pytest, existing pipeline/loader/resolver/report infrastructure, Qt signal-slot threading

---

> Note: this workspace is **not** a git repository, so normal commit steps cannot be executed here. Keep each task isolated in the diff and verify before moving on.

## File map

- Create: `src/ui/panels/workbench/execution_worker.py`
  - Background pipeline runner + Qt signals for start/progress/success/failure/cancelled/finished
- Modify: `src/ui/panels/workbench/state.py`
  - Add progress/result/recent-run dataclasses used by the execution center and recent-run panel
- Modify: `src/ui/adapters/workbench_execution_adapter.py`
  - Expand from readiness-only adapter into execution summary/progress/result/recent-run adapter
- Modify: `src/ui/panels/workbench/execution_center.py`
  - Add start/cancel signals, progress UI, stage text, final-state rendering, and state reset behavior
- Modify: `src/ui/panels/workbench/recent_run_panel.py`
  - Accept and render structured recent-run state
- Modify: `src/ui/panels/workbench/panel.py`
  - Create/manage worker + thread, wire execution-center signals, sync result state to bottom panel, lock/unlock controls
- Modify: `tests/test_workbench_execution_center.py`
  - Expand beyond readiness into start/cancel/progress/final-state behavior
- Modify: `tests/test_workbench_layout.py`
  - Add panel-level execution lifecycle/regression coverage
- Create: `tests/test_execution_worker.py`
  - Worker signal and cancellation behavior tests (using lightweight stubs where needed)

## Task boundaries

This plan intentionally stays focused on the **single-run execution lifecycle**.

It does **not** cover:
- multi-run history lists,
- batch queues,
- retry logic,
- or deep report-viewer UI.

### Task 1: Extend state models for execution progress, execution result, and recent-run summary

**Files:**
- Modify: `src/ui/panels/workbench/state.py`
- Create: `tests/test_workbench_execution_center.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_execution_center.py
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState, RecentRunState


def test_execution_progress_state_defaults_are_safe():
    state = ExecutionProgressState()

    assert state.stage_text == "????"
    assert state.current_step == 0
    assert state.total_steps == 0
    assert state.percent == 0


def test_execution_result_state_defaults_are_safe():
    state = ExecutionResultState()

    assert state.status == "idle"
    assert state.summary == "????"
    assert state.output_path == ""
    assert state.report_paths == []
    assert state.failed_count == 0


def test_recent_run_state_defaults_are_safe():
    state = RecentRunState()

    assert state.status == "idle"
    assert state.title == "????"
    assert state.summary == "??????"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_progress_state_defaults_are_safe tests/test_workbench_execution_center.py::test_execution_result_state_defaults_are_safe tests/test_workbench_execution_center.py::test_recent_run_state_defaults_are_safe -v`

Expected: FAIL because the new state dataclasses do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/state.py
@dataclass(slots=True)
class ExecutionProgressState:
    stage_text: str = "????"
    current_step: int = 0
    total_steps: int = 0
    percent: int = 0


@dataclass(slots=True)
class ExecutionResultState:
    status: str = "idle"
    summary: str = "????"
    error_text: str = ""
    output_path: str = ""
    report_paths: list[str] = field(default_factory=list)
    failed_count: int = 0


@dataclass(slots=True)
class RecentRunState:
    status: str = "idle"
    title: str = "????"
    summary: str = "??????"
    output_label: str = ""
    report_label: str = ""
    error_summary: str = ""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_progress_state_defaults_are_safe tests/test_workbench_execution_center.py::test_execution_result_state_defaults_are_safe tests/test_workbench_execution_center.py::test_recent_run_state_defaults_are_safe -v`

Expected: PASS

### Task 2: Expand WorkbenchExecutionAdapter into a real execution-state adapter

**Files:**
- Modify: `src/ui/adapters/workbench_execution_adapter.py`
- Modify: `tests/test_workbench_execution_center.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_execution_center.py
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState, RecentRunState


def test_execution_adapter_builds_progress_state_from_step_counts():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_progress_state(
        stage_text="??????",
        current_step=2,
        total_steps=5,
    )

    assert isinstance(state, ExecutionProgressState)
    assert state.stage_text == "??????"
    assert state.current_step == 2
    assert state.total_steps == 5
    assert state.percent == 40


def test_execution_adapter_builds_success_result_state():
    adapter = WorkbenchExecutionAdapter()

    state = adapter.build_result_state(
        status="success",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json", "C:/tmp/report.md"],
        failed_count=0,
        error_text="",
    )

    assert isinstance(state, ExecutionResultState)
    assert state.status == "success"
    assert state.output_path.endswith("out.docx")
    assert len(state.report_paths) == 2
    assert state.failed_count == 0


def test_execution_adapter_builds_recent_run_state_from_result():
    adapter = WorkbenchExecutionAdapter()
    result_state = adapter.build_result_state(
        status="partial_success",
        output_path="C:/tmp/out.docx",
        report_paths=["C:/tmp/report.json"],
        failed_count=2,
        error_text="",
    )

    recent = adapter.build_recent_run_state(result_state)

    assert isinstance(recent, RecentRunState)
    assert recent.status == "partial_success"
    assert "2" in recent.summary
    assert recent.output_label.endswith("out.docx")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_adapter_builds_progress_state_from_step_counts tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state tests/test_workbench_execution_center.py::test_execution_adapter_builds_recent_run_state_from_result -v`

Expected: FAIL because the adapter only builds readiness today.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/adapters/workbench_execution_adapter.py
from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)


class WorkbenchExecutionAdapter:
    ...

    def build_progress_state(self, *, stage_text: str, current_step: int, total_steps: int) -> ExecutionProgressState:
        percent = 0 if total_steps <= 0 else int(current_step / total_steps * 100)
        return ExecutionProgressState(
            stage_text=stage_text,
            current_step=current_step,
            total_steps=total_steps,
            percent=percent,
        )

    def build_result_state(self, *, status: str, output_path: str, report_paths: list[str], failed_count: int, error_text: str) -> ExecutionResultState:
        summary_map = {
            "success": "???????",
            "partial_success": f"??????? {failed_count} ??????",
            "failed": "????",
            "cancelled": "???",
        }
        return ExecutionResultState(
            status=status,
            summary=summary_map.get(status, "????"),
            error_text=error_text,
            output_path=output_path,
            report_paths=list(report_paths),
            failed_count=failed_count,
        )

    def build_recent_run_state(self, result_state: ExecutionResultState) -> RecentRunState:
        report_label = ", ".join(result_state.report_paths)
        return RecentRunState(
            status=result_state.status,
            title="????",
            summary=result_state.summary,
            output_label=result_state.output_path,
            report_label=report_label,
            error_summary=result_state.error_text,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_adapter_builds_progress_state_from_step_counts tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state tests/test_workbench_execution_center.py::test_execution_adapter_builds_recent_run_state_from_result -v`

Expected: PASS

### Task 3: Introduce a background execution worker with progress/cancel/final-state signals

**Files:**
- Create: `src/ui/panels/workbench/execution_worker.py`
- Create: `tests/test_execution_worker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_execution_worker.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.panels.workbench.execution_worker import ExecutionWorker


def _app():
    return QApplication.instance() or QApplication([])


class _StubRunner:
    def __init__(self):
        self.cancelled = False

    def run(self, progress_cb, cancel_check):
        progress_cb(1, 3, "????")
        if cancel_check():
            self.cancelled = True
            return {"status": "cancelled"}
        progress_cb(2, 3, "??????")
        progress_cb(3, 3, "????")
        return {"status": "success", "output_path": "out.docx", "report_paths": []}


def test_execution_worker_emits_progress_and_success_signals():
    _app()
    worker = ExecutionWorker(_StubRunner())
    progress = []
    success = []
    worker.progress_changed.connect(lambda cur, total, stage: progress.append((cur, total, stage)))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert progress == [(1, 3, "????"), (2, 3, "??????"), (3, 3, "????")]
    assert success and success[0]["status"] == "success"


def test_execution_worker_honors_cancel_flag():
    _app()
    worker = ExecutionWorker(_StubRunner())
    cancelled = []
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.request_cancel()

    worker.run()

    assert cancelled == [True]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_execution_worker.py -v`

Expected: FAIL because `ExecutionWorker` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/execution_worker.py
from __future__ import annotations

from src.qt_api import QObject, Signal


class ExecutionWorker(QObject):
    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal()
    execution_finished = Signal()

    def __init__(self, runner, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:
        self.execution_started.emit()
        try:
            result = self._runner.run(self.progress_changed.emit, self._is_cancelled)
            status = result.get("status")
            if status == "cancelled":
                self.execution_cancelled.emit()
            elif status == "partial_success":
                self.execution_partial.emit(result)
            elif status == "failed":
                self.execution_failed.emit(result)
            else:
                self.execution_succeeded.emit(result)
        except Exception as exc:
            self.execution_failed.emit({"status": "failed", "error_text": str(exc)})
        finally:
            self.execution_finished.emit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_execution_worker.py -v`

Expected: PASS

### Task 4: Expand ExecutionCenter to expose start/cancel controls, stage text, progress, and final-state rendering

**Files:**
- Modify: `src/ui/panels/workbench/execution_center.py`
- Modify: `tests/test_workbench_execution_center.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_execution_center.py
from src.ui.panels.workbench.state import ExecutionProgressState, ExecutionResultState


def test_execution_center_exposes_execute_and_cancel_signals():
    _app()
    center = ExecutionCenter()
    execute_calls = []
    cancel_calls = []
    center.execute_requested.connect(lambda: execute_calls.append(True))
    center.cancel_requested.connect(lambda: cancel_calls.append(True))

    center._execute_button.click()
    center._cancel_button.click()

    assert execute_calls == [True]
    assert cancel_calls == [True]


def test_execution_center_renders_progress_state():
    _app()
    center = ExecutionCenter()
    state = ExecutionProgressState(stage_text="??????", current_step=2, total_steps=5, percent=40)

    center.set_progress_state(state)

    assert center._stage_label.text() == "??????"
    assert center._progress_label.text() == "2 / 5"
    assert center._progress_bar.value() == 40


def test_execution_center_renders_result_state():
    _app()
    center = ExecutionCenter()
    state = ExecutionResultState(status="success", summary="???????", output_path="out.docx")

    center.set_result_state(state)

    assert center._ready_label.text() == "???"
    assert center._summary_box.toPlainText() == "???????"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_center_exposes_execute_and_cancel_signals tests/test_workbench_execution_center.py::test_execution_center_renders_progress_state tests/test_workbench_execution_center.py::test_execution_center_renders_result_state -v`

Expected: FAIL because the execution center does not expose these controls/state setters yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/execution_center.py
from src.qt_api import QLabel, QTextEdit, QVBoxLayout, QWidget, QPushButton, QProgressBar, Signal
from .state import ExecutionProgressState, ExecutionResultState, ReadinessState


class ExecutionCenter(QWidget):
    execute_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None):
        ...
        self._stage_label = QLabel("????")
        self._progress_label = QLabel("0 / 0")
        self._progress_bar = QProgressBar()
        self._execute_button = QPushButton("????")
        self._cancel_button = QPushButton("??")
        self._cancel_button.setEnabled(False)
        self._execute_button.clicked.connect(self.execute_requested.emit)
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        ...

    def set_progress_state(self, state: ExecutionProgressState) -> None:
        self._stage_label.setText(state.stage_text)
        self._progress_label.setText(f"{state.current_step} / {state.total_steps}")
        self._progress_bar.setValue(state.percent)

    def set_result_state(self, state: ExecutionResultState) -> None:
        status_map = {
            "success": "???",
            "partial_success": "????",
            "failed": "????",
            "cancelled": "???",
        }
        self._ready_label.setText(status_map.get(state.status, "???"))
        self._summary_box.setPlainText(state.summary)
        self._execute_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_execution_center.py::test_execution_center_exposes_execute_and_cancel_signals tests/test_workbench_execution_center.py::test_execution_center_renders_progress_state tests/test_workbench_execution_center.py::test_execution_center_renders_result_state -v`

Expected: PASS

### Task 5: Wire the execution lifecycle into WorkbenchPanel and sync the recent-run panel

**Files:**
- Modify: `src/ui/panels/workbench/panel.py`
- Modify: `src/ui/panels/workbench/recent_run_panel.py`
- Modify: `tests/test_workbench_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workbench_layout.py
from src.ui.panels.workbench.state import ExecutionResultState


def test_workbench_panel_updates_recent_run_panel_after_success_result():
    _app()
    panel = WorkbenchPanel(PanelBridge())
    try:
        result = ExecutionResultState(
            status="success",
            summary="???????",
            output_path="out.docx",
            report_paths=["report.json"],
        )

        panel._on_execution_succeeded(result)

        assert panel._recent_run_panel._summary.text() == "???????"
    finally:
        panel.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_updates_recent_run_panel_after_success_result -v`

Expected: FAIL because the panel does not yet handle execution result callbacks.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/ui/panels/workbench/recent_run_panel.py
from .state import RecentRunState

    def set_state(self, state: RecentRunState) -> None:
        self._summary.setText(state.summary)
```

```python
# src/ui/panels/workbench/panel.py
from src.qt_api import QThread
from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter
from .execution_worker import ExecutionWorker

    def _connect_signals(self) -> None:
        ...
        self._execution_center.execute_requested.connect(self._start_execution)
        self._execution_center.cancel_requested.connect(self._cancel_execution)

    def _start_execution(self) -> None:
        # minimal runner stub / adapter-backed runner wiring for this slice
        ...

    def _on_execution_succeeded(self, result_payload) -> None:
        result_state = self._execution_adapter.build_result_state(...)
        recent_state = self._execution_adapter.build_recent_run_state(result_state)
        self._execution_center.set_result_state(result_state)
        self._recent_run_panel.set_state(recent_state)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_workbench_layout.py::test_workbench_panel_updates_recent_run_panel_after_success_result -v`

Expected: PASS

### Task 6: Focused and full execution-center enhancement verification

**Files:**
- Modify: `docs/superpowers/plans/2026-03-30-execution-center-enhancement.md`

- [ ] **Step 1: Run the focused execution-enhancement suite**

Run: `pytest tests/test_workbench_execution_center.py tests/test_execution_worker.py tests/test_workbench_layout.py -v`

Expected: PASS

- [ ] **Step 2: Run the full suite**

Run: `pytest tests -q`

Expected: PASS

- [ ] **Step 3: Manual smoke**

Run: `python main.py --gui`

Expected:
- starting execution moves the center into running state,
- cancelling a run updates the center to cancelled,
- success / partial / failed states render in the execution center,
- the recent-run panel updates after completion,
- the page now feels operational, not just structural.
