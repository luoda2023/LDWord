from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget, Signal
from src.shared.ui.log_stream_widget import LogStreamWidget
from src.shared.ui.module_status_list import ModuleStatusList
from src.shared.ui.progress_indicator import ProgressIndicator


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

    def set_progress(self, current: int, total: int, step_name: str = "") -> None:
        self._progress.set_progress(current, total, step_name)

    def add_module(self, key: str, label: str, *, status: str = "queued", progress: int = 0) -> None:
        self._modules.add_module(key, label, status=status, progress=progress)

    def update_module_status(self, key: str, *, status: str | None = None, progress: int | None = None) -> None:
        self._modules.update_module_status(key, status=status, progress=progress)

    def append_log(self, module: str, message: str, *, level: str = "info") -> None:
        self._logs.append_log(module, message, level=level)

    def current_module_text(self) -> str:
        return self._modules.current_module_text()

    def log_text(self) -> str:
        return self._logs.log_text()

    def set_completed(self, status: str, *, completed: int, total: int) -> None:
        self._progress.set_done()
        self._summary.setText(f"Completed {completed}/{total} modules ({status}).")

    def summary_text(self) -> str:
        return self._summary.text()
