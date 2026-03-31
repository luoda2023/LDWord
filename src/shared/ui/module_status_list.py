from __future__ import annotations

from src.qt_api import QPushButton, QVBoxLayout, QWidget, Signal


class ModuleStatusList(QWidget):
    """Lightweight per-module status/progress list."""

    module_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._rows: dict[str, dict[str, object]] = {}
        self._current_module_id = ""

    @staticmethod
    def _build_row_text(title: str, status: str, progress: int) -> str:
        return f"{title} - {status} ({progress}%)"

    @staticmethod
    def _clamp_progress(progress: int) -> int:
        return max(0, min(100, int(progress)))

    def add_module(self, module_id: str, title: str) -> None:
        existing = self._rows.get(module_id)
        if existing is not None:
            existing["title"] = title
            existing["status"] = "queued"
            existing["progress"] = 0
            existing["widget"].setText(self._build_row_text(title, "queued", 0))
            self._current_module_id = module_id
            return

        row_button = QPushButton(self._build_row_text(title, "queued", 0))
        row_button.setFlat(True)
        row_button.clicked.connect(lambda: self._on_row_clicked(module_id))
        self._layout.addWidget(row_button)
        self._rows[module_id] = {
            "title": title,
            "status": "queued",
            "progress": 0,
            "widget": row_button,
        }
        if not self._current_module_id:
            self._current_module_id = module_id

    def _on_row_clicked(self, module_id: str) -> None:
        self._current_module_id = module_id
        self.module_clicked.emit(module_id)

    def update_status(self, module_id: str, status: str, progress: int = 0) -> None:
        row = self._rows.get(module_id)
        if row is None:
            return
        row["status"] = status
        row["progress"] = self._clamp_progress(progress)
        row["widget"].setText(self._build_row_text(row["title"], row["status"], row["progress"]))
        self._current_module_id = module_id

    def current_module_text(self) -> str:
        if not self._current_module_id:
            return ""
        row = self._rows.get(self._current_module_id)
        if row is None:
            return ""
        return str(row["title"])

    def clear(self) -> None:
        for row in self._rows.values():
            widget = row["widget"]
            self._layout.removeWidget(widget)
            widget.deleteLater()
        self._rows.clear()
        self._current_module_id = ""
