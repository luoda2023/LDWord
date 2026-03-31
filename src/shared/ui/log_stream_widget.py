from __future__ import annotations

from src.qt_api import QTextEdit, QVBoxLayout, QWidget


class LogStreamWidget(QWidget):
    """Append-only structured log stream."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._view = QTextEdit()
        self._view.setReadOnly(True)
        layout.addWidget(self._view)
        self._lines: list[str] = []

    def append_log(self, level: str, message: str) -> None:
        line = f"[{level}] {message}"
        self._lines.append(line)
        self._view.setPlainText(self.log_text())

    def log_text(self) -> str:
        return "\n".join(self._lines)
