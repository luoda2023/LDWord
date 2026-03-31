"""
Shared file drop zone primitive.
"""

from __future__ import annotations

from src.qt_api import QFileDialog, QComboBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget, Signal, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


class FileDropZone(QWidget):
    """File selection control with optional recent-file shortcuts."""

    file_selected = Signal(str)

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._file_path = ""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self._file_input = QLineEdit(self)
        self._file_input.setReadOnly(True)
        self._file_input.setPlaceholderText("No file selected")
        top_row.addWidget(self._file_input, 1)

        self._browse_button = QPushButton("Browse", self)
        self._browse_button.setCursor(Qt.PointingHandCursor)
        apply_button_variant(self._browse_button, "secondary")
        self._browse_button.clicked.connect(self._pick_file)
        top_row.addWidget(self._browse_button)

        self._layout.addLayout(top_row)

        self._recent_combo = QComboBox(self)
        self._recent_combo.setEditable(False)
        self._recent_combo.setPlaceholderText("Recent files")
        self._recent_combo.currentTextChanged.connect(self._on_recent_selected)
        self._layout.addWidget(self._recent_combo)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setSpacing(t.spacing_xs)
        self._file_input.setFixedHeight(t.control_height_md)
        self._browse_button.setFixedHeight(t.button_height_md)
        self._recent_combo.setFixedHeight(t.control_height_md)
        self._file_input.setStyleSheet(build_text_input_stylesheet(t))
        self._recent_combo.setStyleSheet(build_text_input_stylesheet(t, selector="QComboBox"))
        self._browse_button.setStyleSheet(build_button_stylesheet(t))

    def _pick_file(self) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "Select file",
            "",
            "Word Documents (*.docx);;All Files (*)",
        )
        file_path = str(file_path or "").strip()
        if not file_path:
            return
        self.set_file(file_path)

    def _on_recent_selected(self, value: str) -> None:
        file_path = str(value or "").strip()
        if not file_path:
            return
        self.set_file(file_path)

    def set_file(self, file_path: str) -> None:
        self._file_path = str(file_path or "")
        self._file_input.setText(self._file_path)
        self.file_selected.emit(self._file_path)

    def file_path(self) -> str:
        return self._file_path

    def set_recent_files(self, files: list[str]) -> None:
        self._recent_combo.blockSignals(True)
        self._recent_combo.clear()
        for file_path in files:
            candidate = str(file_path or "").strip()
            if candidate:
                self._recent_combo.addItem(candidate)
        self._recent_combo.blockSignals(False)
