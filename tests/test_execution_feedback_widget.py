import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.execution_feedback_widget import ExecutionFeedbackWidget
from src.shared.ui.log_stream_widget import LogStreamWidget
from src.shared.ui.module_status_list import ModuleStatusList
from src.shared.ui.progress_indicator import DONE_STEP_TEXT


def _app():
    return QApplication.instance() or QApplication([])


def test_module_status_list_tracks_per_module_status_and_progress():
    _app()
    statuses = ModuleStatusList()

    statuses.add_module("ingest", "Ingest")
    statuses.update_status("ingest", status="running", progress=40)
    statuses.add_module("format", "Format")

    assert statuses.current_module_text() == "Ingest"


def test_module_status_list_emits_module_clicked():
    _app()
    statuses = ModuleStatusList()
    statuses.add_module("ingest", "Ingest")
    calls: list[str] = []
    statuses.module_clicked.connect(calls.append)

    statuses._rows["ingest"]["widget"].click()

    assert calls == ["ingest"]


def test_module_status_list_duplicate_module_id_updates_in_place():
    _app()
    statuses = ModuleStatusList()

    statuses.add_module("ingest", "Ingest")
    statuses.add_module("ingest", "Ingest Again")

    assert len(statuses._rows) == 1
    assert statuses.layout().count() == 1
    assert statuses.current_module_text() == "Ingest Again"


def test_log_stream_widget_appends_structured_log_lines():
    _app()
    logs = LogStreamWidget()

    logs.append_log("info", "started")
    logs.append_log("info", "parsed 3 headings")
    logs.append_log("debug", "queued")

    assert logs.log_text().splitlines() == [
        "[info] started",
        "[info] parsed 3 headings",
        "[debug] queued",
    ]


def test_log_stream_widget_append_keeps_cursor_at_end():
    _app()
    logs = LogStreamWidget()

    logs.append_log("info", "line one")
    logs.append_log("info", "line two")

    cursor = logs._view.textCursor()
    assert cursor.position() == len(logs._view.toPlainText())


def test_execution_feedback_widget_updates_progress_modules_and_logs():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        widget.add_module("ingest", "Ingest")
        widget.set_progress(1, 4, "Ingest")
        widget.update_module_status("ingest", "running", progress=25)
        widget.append_log("info", "processing")

        assert widget.current_module_text() == "Ingest"
        assert widget.log_text() == "[info] processing"
    finally:
        widget.close()


def test_execution_feedback_widget_set_completed_updates_summary():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        widget.set_completed(True, {"success_count": 3})
        assert "成功处理 3 项" in widget.summary_text()
    finally:
        widget.close()


def test_execution_feedback_widget_reset_clears_run_state():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        widget.add_module("ingest", "Ingest")
        widget.set_progress(1, 4, "Ingest")
        widget.append_log("info", "processing")
        widget.set_completed(True, {"success_count": 1})

        widget.reset()

        assert widget.current_module_text() == ""
        assert widget.log_text() == ""
        assert widget.summary_text() == ""
        assert widget._progress._pct_label.text() == "0%"
        assert widget._progress._cancel.isHidden() is False
    finally:
        widget.close()


def test_execution_feedback_widget_non_success_completion_keeps_non_done_progress_state():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        widget.set_progress(1, 4, "Ingest")

        widget.set_completed(False, {"success_count": 1})

        assert widget._progress._pct_label.text() != "100%"
        assert widget._progress._step_label.text() != DONE_STEP_TEXT
        assert widget._progress._cancel.isHidden() is False
    finally:
        widget.close()


def test_execution_feedback_widget_emits_cancel_clicked():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        calls: list[bool] = []
        widget.cancel_clicked.connect(lambda: calls.append(True))

        widget._progress._cancel.click()

        assert calls == [True]
    finally:
        widget.close()
