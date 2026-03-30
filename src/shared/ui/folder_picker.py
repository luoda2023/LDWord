"""
Folder picker with shared input/button styling.
"""

from __future__ import annotations

from src.qt_api import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget, Signal, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


DEFAULT_FOLDER_PLACEHOLDER = "请选择文件夹"
BROWSE_BUTTON_TEXT = "浏览"
FOLDER_DIALOG_TITLE = "选择文件夹"


class FolderPicker(QWidget):
    """Select a folder and display its path."""

    folder_changed = Signal(str)

    def __init__(self, *, placeholder: str = DEFAULT_FOLDER_PLACEHOLDER, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().spacing_xs)

        self._path = self._build_path_input(placeholder)
        layout.addWidget(self._path, 1)

        self._btn = self._build_browse_button()
        layout.addWidget(self._btn)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @staticmethod
    def _build_path_input(placeholder: str) -> QLineEdit:
        path_input = QLineEdit()
        path_input.setPlaceholderText(placeholder)
        path_input.setReadOnly(True)
        path_input.setStyleSheet(build_text_input_stylesheet(get_theme()))
        return path_input

    def _build_browse_button(self) -> QPushButton:
        button = QPushButton(BROWSE_BUTTON_TEXT)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(build_button_stylesheet(get_theme()))
        apply_button_variant(button, "secondary")
        button.clicked.connect(self._browse)
        return button

    def _apply_theme(self) -> None:
        t = get_theme()
        self.layout().setSpacing(t.spacing_xs)
        self._path.setFixedHeight(t.control_height_md)
        self._path.setStyleSheet(build_text_input_stylesheet(t))
        self._btn.setFixedHeight(t.button_height_md)
        self._btn.setMinimumWidth(t.button_height_md * 2)
        self._btn.setStyleSheet(build_button_stylesheet(t))
        self.setFixedHeight(max(t.control_height_md, t.button_height_md))

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, FOLDER_DIALOG_TITLE)
        if path:
            self._path.setText(path)
            self.folder_changed.emit(path)

    def path(self) -> str:
        return self._path.text()

    def set_path(self, path: str):
        self._path.setText(path)
