from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget


class ModuleStatusList(QWidget):
    """Lightweight per-module status/progress list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._rows: dict[str, dict[str, object]] = {}
        self._current_key = ""

    @staticmethod
    def _build_row_text(label: str, status: str, progress: int) -> str:
        return f"{label} - {status} ({progress}%)"

    @staticmethod
    def _clamp_progress(progress: int) -> int:
        return max(0, min(100, int(progress)))

    def add_module(self, key: str, label: str, *, status: str = "queued", progress: int = 0) -> None:
        pct = self._clamp_progress(progress)
        row_label = QLabel(self._build_row_text(label, status, pct))
        self._layout.addWidget(row_label)
        self._rows[key] = {
            "label": label,
            "status": status,
            "progress": pct,
            "widget": row_label,
        }
        if not self._current_key:
            self._current_key = key

    def update_module_status(self, key: str, *, status: str | None = None, progress: int | None = None) -> None:
        row = self._rows.get(key)
        if row is None:
            return
        if status is not None:
            row["status"] = status
        if progress is not None:
            row["progress"] = self._clamp_progress(progress)
        label = row["label"]
        row_status = row["status"]
        row_progress = row["progress"]
        row["widget"].setText(self._build_row_text(label, row_status, row_progress))
        self._current_key = key

    def row_text(self, key: str) -> str:
        row = self._rows.get(key)
        if row is None:
            return ""
        return row["widget"].text()

    def current_module_text(self) -> str:
        if not self._current_key:
            return ""
        return self.row_text(self._current_key)
