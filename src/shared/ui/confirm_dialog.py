"""
Shared confirm dialog built on top of BaseDialog.
"""

from __future__ import annotations

from src.shared.ui.base_dialog import BaseDialog


DEFAULT_CONFIRM_DIALOG_TITLE = "请确认"
DEFAULT_CONFIRM_BUTTON_TEXT = "确认"
DEFAULT_CANCEL_BUTTON_TEXT = "取消"


class ConfirmDialog(BaseDialog):
    """Standard confirmation dialog."""

    def __init__(
        self,
        title: str = DEFAULT_CONFIRM_DIALOG_TITLE,
        message: str = "",
        confirm_text: str = DEFAULT_CONFIRM_BUTTON_TEXT,
        cancel_text: str = DEFAULT_CANCEL_BUTTON_TEXT,
        *,
        destructive: bool = False,
        parent=None,
    ):
        super().__init__(
            title=title,
            icon_style="warning" if destructive else "question",
            parent=parent,
        )
        self.setMinimumWidth(380)
        self._add_optional_message(message)
        self._cancel_btn = self._build_cancel_button(cancel_text)
        self._confirm_btn = self._build_confirm_button(confirm_text, destructive=destructive)
    def _add_optional_message(self, message: str) -> None:
        if message:
            self.add_message(message)

    def _build_cancel_button(self, cancel_text: str):
        button = self.add_secondary_button(cancel_text)
        button.clicked.connect(self.reject)
        return button

    def _build_confirm_button(self, confirm_text: str, *, destructive: bool):
        button = self.add_primary_button(confirm_text, destructive=destructive)
        button.clicked.connect(self.accept)
        return button
