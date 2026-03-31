import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.execution_feedback_widget import ExecutionFeedbackWidget
from src.shared.ui.log_stream_widget import LogStreamWidget
from src.shared.ui.module_status_list import ModuleStatusList


def _app():
    return QApplication.instance() or QApplication([])


def test_module_status_list_tracks_per_module_status_and_progress():
    _app()
    statuses = ModuleStatusList()

    statuses.add_module("ingest", "Ingest", status="queued", progress=0)
    statuses.update_module_status("ingest", status="running", progress=40)
    statuses.add_module("format", "Format", status="queued", progress=0)

    assert statuses.current_module_text() == "Ingest - running (40%)"
    assert statuses.row_text("ingest") == "Ingest - running (40%)"
    assert statuses.row_text("format") == "Format - queued (0%)"


def test_log_stream_widget_appends_structured_log_lines():
    _app()
    logs = LogStreamWidget()

    logs.append_log("ingest", "started")
    logs.append_log("ingest", "parsed 3 headings")
    logs.append_log("format", "queued", level="debug")

    assert logs.log_text().splitlines() == [
        "[info] ingest: started",
        "[info] ingest: parsed 3 headings",
        "[debug] format: queued",
    ]


def test_execution_feedback_widget_updates_progress_modules_and_logs():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        widget.add_module("ingest", "Ingest")
        widget.set_progress(1, 4, "Ingest")
        widget.update_module_status("ingest", status="running", progress=25)
        widget.append_log("ingest", "processing")

        assert widget.current_module_text() == "Ingest - running (25%)"
        assert widget.log_text() == "[info] ingest: processing"
    finally:
        widget.close()


def test_execution_feedback_widget_set_completed_updates_summary():
    _app()
    widget = ExecutionFeedbackWidget()
    try:
        widget.set_completed("success", completed=4, total=4)
        assert widget.summary_text() == "Completed 4/4 modules (success)."
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
