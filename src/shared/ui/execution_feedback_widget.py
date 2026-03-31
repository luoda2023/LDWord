from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Signal
from src.shared.ui.log_stream_widget import LogStreamWidget
from src.shared.ui.module_status_list import ModuleStatusList
from src.shared.ui.progress_indicator import DEFAULT_STEP_TEXT, ProgressIndicator


class ExecutionFeedbackWidget(QWidget):
    """Composite widget for execution progress, per-module status, and logs."""

    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._progress = ProgressIndicator()
        self._progress.cancel_clicked.connect(self.cancel_clicked.emit)
        layout.addWidget(self._progress)

        self._modules = ModuleStatusList()
        layout.addWidget(self._modules)

        self._logs = LogStreamWidget()
        layout.addWidget(self._logs)

        self._summary = QLabel("")
        layout.addWidget(self._summary)

    def set_progress(self, current: int, total: int, module_title: str) -> None:
        self._progress.set_progress(current, total, module_title)

    def add_module(self, module_id: str, title: str) -> None:
        self._modules.add_module(module_id, title)

    def update_module_status(self, module_id: str, status: str, progress: int = 0) -> None:
        self._modules.update_status(module_id, status, progress)

    def append_log(self, level: str, message: str) -> None:
        self._logs.append_log(level, message)

    def current_module_text(self) -> str:
        return self._modules.current_module_text()

    def log_text(self) -> str:
        return self._logs.log_text()

    def set_completed(self, success: bool, summary: dict) -> None:
        if success:
            self._progress.set_done()
        else:
            self._progress._cancel.show()
        success_count = int(summary.get("success_count", 0))
        text = f"成功处理 {success_count} 项"
        if not success:
            text = f"{text}（部分未完成）"
        self._summary.setText(text)

    def summary_text(self) -> str:
        return self._summary.text()

    def reset(self) -> None:
        self._modules.clear()
        self._logs.clear()
        self._summary.clear()
        self._progress.set_progress(0, 0, DEFAULT_STEP_TEXT)
        self._progress._cancel.show()
