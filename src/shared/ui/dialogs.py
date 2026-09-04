"""
Dialog factory helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from src.qt_api import QDialog, QHBoxLayout, QLabel, QTextEdit, QWidget

from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.dialog_style import (
    build_dialog_detail_stylesheet,
    build_dialog_path_label_stylesheet,
)
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import get_theme


OK_TEXT = "确定"
CONFIRM_TEXT = "确认"
CANCEL_TEXT = "取消"
LOG_PATH_PREFIX = "日志路径："


DialogActionVariant = Literal["primary", "secondary", "danger"]


@dataclass(frozen=True, slots=True)
class DialogAction:
    """One explicit action in a themed decision dialog."""

    action_id: str
    text: str
    variant: DialogActionVariant = "secondary"
    default: bool = False
    escape: bool = False

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("dialog action_id must not be empty")
        if not self.text.strip():
            raise ValueError("dialog action text must not be empty")
        if self.variant not in {"primary", "secondary", "danger"}:
            raise ValueError(f"unsupported dialog action variant: {self.variant}")


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
    default_confirm: bool | None = None,
    parent=None,
) -> bool:
    confirm_is_default = (
        not destructive if default_confirm is None else bool(default_confirm)
    )
    return decision(
        title,
        message,
        actions=(
            DialogAction(
                "cancel",
                cancel_text,
                default=not confirm_is_default,
                escape=True,
            ),
            DialogAction(
                "confirm",
                confirm_text,
                variant="danger" if destructive else "primary",
                default=confirm_is_default,
            ),
        ),
        icon_style="warning" if destructive else "question",
        parent=parent,
    ) == "confirm"


def decision(
    title: str,
    message: str,
    actions: Sequence[DialogAction],
    *,
    icon_style: str = "question",
    parent=None,
) -> str:
    """Show a themed multi-action dialog and return the selected action ID.

    Window close and Escape resolve to the action marked ``escape``.  Defaults
    are explicit so button behaviour does not change with the host platform.
    """

    normalized = tuple(actions)
    if not normalized:
        raise ValueError("decision dialog requires at least one action")
    action_ids = [action.action_id for action in normalized]
    if len(set(action_ids)) != len(action_ids):
        raise ValueError("decision dialog action IDs must be unique")
    if sum(action.default for action in normalized) > 1:
        raise ValueError("decision dialog can only have one default action")
    escape_actions = tuple(action for action in normalized if action.escape)
    if len(escape_actions) > 1:
        raise ValueError("decision dialog can only have one escape action")

    dlg = BaseDialog(title=title, icon_style=icon_style, parent=parent)
    if message:
        dlg.add_message(message)
    selected = {
        "action": escape_actions[0].action_id if escape_actions else ""
    }

    def choose(action_id: str) -> None:
        selected["action"] = action_id
        dlg.accept()

    for action in normalized:
        if action.variant == "secondary":
            button = dlg.add_secondary_button(
                action.text,
                default=action.default,
            )
        else:
            button = dlg.add_primary_button(
                action.text,
                destructive=action.variant == "danger",
                default=action.default,
            )
        button.clicked.connect(
            lambda _checked=False, action_id=action.action_id: choose(action_id)
        )

    dlg.exec()
    return selected["action"]


def input_text(
    title: str,
    message: str,
    placeholder: str = '',
    default: str = '',
    ok_text: str = OK_TEXT,
    cancel_text: str = CANCEL_TEXT,
    *,
    parent=None,
) -> str | None:
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
