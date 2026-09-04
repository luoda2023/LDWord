from __future__ import annotations

from src.qt_api import QVBoxLayout, QWidget, Signal

from src.shared.ui.execution_feedback_widget import ExecutionFeedbackWidget


class ExecutionProgressWidget(QWidget):
    """Compatibility wrapper for the V2 quick-execution detail page."""

    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._known_modules: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._feedback = ExecutionFeedbackWidget(self)
        self._feedback.cancel_clicked.connect(self.cancel_clicked.emit)
        layout.addWidget(self._feedback)

    def set_progress(self, current: int, total: int, module: str) -> None:
        module_id = str(module or "").strip() or "current"
        if module_id not in self._known_modules:
            self._known_modules.add(module_id)
            self._feedback.add_module(module_id, module_id)
        self._feedback.set_progress(current, total, module_id)

    def update_module_status(self, module: str, status: str, progress: int = 0) -> None:
        module_id = str(module or "").strip() or "current"
        if module_id not in self._known_modules:
            self._known_modules.add(module_id)
            self._feedback.add_module(module_id, module_id)
        self._feedback.update_module_status(module_id, status, progress)

    def append_log(self, level: str, message: str) -> None:
        self._feedback.append_log(level, message)

    def set_completed(self, success: bool, summary: dict) -> None:
        self._feedback.set_completed(success, summary)

    def reset(self) -> None:
        self._known_modules.clear()
        self._feedback.reset()
