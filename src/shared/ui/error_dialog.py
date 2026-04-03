"""
Legacy-compatible error dialog built on BaseDialog.
"""

from __future__ import annotations

from src.app_meta import APP_DISPLAY_NAME
from src.qt_api import QHBoxLayout, QLabel, QTextEdit, QWidget

from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.dialog_style import (
    build_dialog_detail_stylesheet,
    build_dialog_path_label_stylesheet,
)
from src.shared.ui.dialogs import LOG_PATH_PREFIX, OK_TEXT
from src.shared.ui.theme import get_theme
from src.ui.icons.catalog import get_icon


class ErrorDialog(BaseDialog):
    """Error dialog with traceback and optional log path."""

    def __init__(
        self,
        error_message: str,
        traceback_text: str = "",
        log_path: str = "",
        parent=None,
    ):
        super().__init__(title=f"{APP_DISPLAY_NAME} - 错误", icon_style="error", parent=parent)
        self.setMinimumWidth(520)
        self.setMaximumWidth(700)

        self.add_message("处理过程中发生错误，请查看以下详情。")
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlainText(traceback_text or str(error_message))
        self._apply_detail_style()
        self.content_layout.addWidget(self._detail)

        if log_path:
            self.content_layout.addWidget(self._build_path_row(log_path))

        self._ok_btn = self.add_primary_button(OK_TEXT)
        self._ok_btn.clicked.connect(self.accept)

    def _apply_detail_style(self) -> None:
        t = get_theme()
        self._detail.setMinimumHeight(t.dialog_detail_min_height)
        self._detail.setMaximumHeight(t.dialog_detail_max_height)
        self._detail.setStyleSheet(
            build_dialog_detail_stylesheet(
                t,
                text_color=t.error,
                border_color=t.border,
                padding=t.spacing_sm,
                radius=t.radius_sm,
            )
        )

    def _build_path_row(self, log_path: str) -> QWidget:
        t = get_theme()
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.spacing_xs)

        icon_label = QLabel()
        file_icon = get_icon('file-text', size=14, color=t.text_hint)
        icon_label.setPixmap(file_icon.pixmap(14, 14))
        icon_label.setFixedWidth(t.dialog_path_icon_width)
        layout.addWidget(icon_label)

        path_label = QLabel(f"{LOG_PATH_PREFIX}{log_path}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet(build_dialog_path_label_stylesheet(t))
        layout.addWidget(path_label, 1)
        return row
