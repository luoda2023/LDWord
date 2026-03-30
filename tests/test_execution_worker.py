import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline.result import PipelineResult
from src.qt_api import QApplication
from src.ui.panels.workbench.execution_worker import ExecutionWorker


def _app():
    return QApplication.instance() or QApplication([])


class _StubRunner:
    def __init__(self):
        self.cancelled = False

    def run(self, progress_cb, cancel_check):
        progress_cb(1, 3, "prepare")
        if cancel_check():
            self.cancelled = True
            return {"status": "cancelled"}
        progress_cb(2, 3, "process")
        progress_cb(3, 3, "complete")
        return {"status": "success", "output_path": "out.docx", "report_paths": []}


def test_execution_worker_emits_progress_and_success_signals():
    _app()
    worker = ExecutionWorker(_StubRunner())
    progress = []
    success = []
    partial = []
    failed = []
    cancelled = []
    finished = []
    worker.progress_changed.connect(lambda cur, total, stage: progress.append((cur, total, stage)))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert progress == [(1, 3, "prepare"), (2, 3, "process"), (3, 3, "complete")]
    assert success == [
        {
            "status": "success",
            "output_path": "out.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
        }
    ]
    assert partial == []
    assert failed == []
    assert cancelled == []
    assert finished == [True]


def test_execution_worker_honors_cancel_flag():
    _app()
    worker = ExecutionWorker(_StubRunner())
    cancelled = []
    finished = []
    success = []
    partial = []
    failed = []
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_finished.connect(lambda: finished.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.request_cancel()

    worker.run()

    assert cancelled == [True]
    assert finished == [True]
    assert success == []
    assert partial == []
    assert failed == []


def test_execution_worker_resets_cancel_flag_after_run_finishes():
    _app()

    class _ReusableRunner:
        def __init__(self):
            self.calls = 0

        def run(self, progress_cb, cancel_check):
            self.calls += 1
            if cancel_check():
                return {"status": "cancelled"}
            progress_cb(1, 1, f"run-{self.calls}")
            return {"status": "success", "output_path": f"out-{self.calls}.docx", "report_paths": []}

    runner = _ReusableRunner()
    worker = ExecutionWorker(runner)
    cancelled = []
    success = []
    partial = []
    failed = []
    finished = []
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.request_cancel()
    worker.run()
    worker.run()

    assert cancelled == [True]
    assert success == [
        {
            "status": "success",
            "output_path": "out-2.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
        }
    ]
    assert partial == []
    assert failed == []
    assert finished == [True, True]


def test_execution_worker_supports_pipeline_result_objects():
    _app()

    class _PipelineResultRunner:
        def run(self, progress_cb, cancel_check):
            progress_cb(1, 1, "done")
            assert cancel_check() is False
            return PipelineResult(
                success=True,
                status="partial_success",
                output_paths={"final": "out.docx"},
                failed_items=[{"rule_name": "heading"}],
                error="1 module operation(s) failed.",
            )

    worker = ExecutionWorker(_PipelineResultRunner())
    started = []
    success = []
    partial = []
    failed = []
    cancelled = []
    finished = []
    worker.execution_started.connect(lambda: started.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert started == [True]
    assert success == []
    assert partial == [
        {
            "status": "partial_success",
            "output_path": "out.docx",
            "report_paths": [],
            "failed_count": 1,
            "error_text": "1 module operation(s) failed.",
        }
    ]
    assert failed == []
    assert cancelled == []
    assert finished == [True]


def test_execution_worker_treats_unknown_status_as_failure():
    _app()

    class _UnknownStatusRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {"status": "paused"}

    worker = ExecutionWorker(_UnknownStatusRunner())
    success = []
    partial = []
    failures = []
    cancelled = []
    finished = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failures.append(payload))
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert success == []
    assert partial == []
    assert failures == [
        {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "Unknown execution status: 'paused'",
        }
    ]
    assert cancelled == []
    assert finished == [True]


def test_execution_worker_normalizes_report_paths_to_strings():
    _app()

    class _PathResultRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_path": Path("out.docx"),
                "report_paths": [Path("logs/report.json"), Path("logs/report.md")],
            }

    worker = ExecutionWorker(_PathResultRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success == [
        {
            "status": "success",
            "output_path": "out.docx",
            "report_paths": [str(Path("logs/report.json")), str(Path("logs/report.md"))],
            "failed_count": 0,
            "error_text": "",
        }
    ]
