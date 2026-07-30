"""
Dialog factory helpers.
"""

from __future__ import annotations

from typing import Optional

from src.qt_api import QDialog, QHBoxLayout, QLabel, QTextEdit, QWidget

from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.dialog_style import (
    build_dialog_detail_stylesheet,
    build_dialog_path_label_stylesheet,
)
from src.shared.ui.theme import get_theme
from src.shared.ui.icons.catalog import get_icon


OK_TEXT = "确定"
CONFIRM_TEXT = "确认"
CANCEL_TEXT = "取消"
LOG_PATH_PREFIX = "日志路径："


def _alert(
    kind: str,
    title: str,
    message: str,
    detail: str = '',
    ok_text: str = OK_TEXT,
    parent=None,
) -> None:
    dlg = BaseDialog(title=title, icon_style=kind, parent=parent)
    dlg.add_message(message)

    if detail:
        _add_detail_area(dlg, detail)

    btn = dlg.add_primary_button(ok_text)
    btn.clicked.connect(dlg.accept)
    dlg.exec()


def info(title: str, message: str, *, parent=None) -> None:
    _alert('info', title, message, parent=parent)


def success(title: str, message: str, *, parent=None) -> None:
    _alert('success', title, message, parent=parent)


def warning(title: str, message: str, *, parent=None) -> None:
    _alert('warning', title, message, parent=parent)


def error(
    title: str,
    message: str,
    detail: str = '',
    log_path: str = '',
    *,
    parent=None,
) -> None:
    dlg = BaseDialog(title=title, icon_style='error', parent=parent)
    dlg.add_message(message)

    if detail:
        _add_detail_area(dlg, detail, is_error=True)

    if log_path:
        dlg.content_layout.addWidget(_build_log_path_row(log_path))

    btn = dlg.add_primary_button(OK_TEXT)
    btn.clicked.connect(dlg.accept)
    dlg.exec()


def confirm(
    title: str,
    message: str,
    confirm_text: str = CONFIRM_TEXT,
    cancel_text: str = CANCEL_TEXT,
    *,
    destructive: bool = False,
    parent=None,
) -> bool:
    dlg = BaseDialog(
        title=title,
        icon_style='warning' if destructive else 'question',
        parent=parent,
    )
    dlg.add_message(message)

    cancel_btn = dlg.add_secondary_button(cancel_text)
    cancel_btn.clicked.connect(dlg.reject)

    ok_btn = dlg.add_primary_button(confirm_text, destructive=destructive)
    ok_btn.clicked.connect(dlg.accept)

    return dlg.exec() == QDialog.Accepted


def input_text(
    title: str,
    message: str,
    placeholder: str = '',
    default: str = '',
    ok_text: str = OK_TEXT,
    cancel_text: str = CANCEL_TEXT,
    *,
    parent=None,
) -> Optional[str]:
    dlg = BaseDialog(title=title, icon_style='input', parent=parent)
    dlg.add_message(message)

    line_edit = dlg.add_text_input(placeholder=placeholder, default=default)

    cancel_btn = dlg.add_secondary_button(cancel_text)
    cancel_btn.clicked.connect(dlg.reject)

    ok_btn = dlg.add_primary_button(ok_text)
    ok_btn.clicked.connect(dlg.accept)

    line_edit.returnPressed.connect(dlg.accept)

    if dlg.exec() == QDialog.Accepted:
        return line_edit.text()
    return None


def _build_log_path_row(log_path: str) -> QWidget:
    t = get_theme()
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 4, 0, 0)
    layout.setSpacing(6)

    file_icon = get_icon('file-text', size=14, color=t.text_hint)
    icon_label = QLabel()
    icon_label.setPixmap(file_icon.pixmap(14, 14))
    icon_label.setFixedSize(14, 14)
    layout.addWidget(icon_label)

    path_text = QLabel(f'{LOG_PATH_PREFIX}{log_path}')
    path_text.setWordWrap(True)
    path_text.setStyleSheet(build_dialog_path_label_stylesheet(t))
    layout.addWidget(path_text, 1)
    return row


def _add_detail_area(dlg: BaseDialog, text: str, *, is_error: bool = False):
    t = get_theme()
    txt = QTextEdit()
    txt.setPlainText(text)
    txt.setReadOnly(True)
    text_color = t.error if is_error else t.text_secondary
    txt.setStyleSheet(build_dialog_detail_stylesheet(t, text_color=text_color, border_color=t.border_light))
    txt.document().setTextWidth(400)
    doc_height = int(txt.document().size().height()) + t.spacing_md * 2 + 4
    txt.setFixedHeight(min(max(doc_height, t.dialog_detail_min_height), t.dialog_detail_max_height))
    dlg.content_layout.addWidget(txt)
