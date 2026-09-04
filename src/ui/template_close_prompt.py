"""Close-choice dialog for pending template drafts."""

from __future__ import annotations

from src.shared.ui.base_dialog import BaseDialog
from src.ui.template_close_transaction import (
    TEMPLATE_EDIT_CANCEL,
    TEMPLATE_EDIT_DISCARD,
    TEMPLATE_EDIT_SAVE,
)


class TemplateClosePrompt:
    """Own the close-dialog presentation without owning close state."""

    def __init__(self, parent) -> None:
        self._parent = parent

    @staticmethod
    def _accept(
        dialog,
        selected: dict[str, str],
        action: str,
    ) -> None:
        selected["action"] = action
        dialog.accept()

    def ask(self, count: int) -> str:
        dialog = BaseDialog(
            title="未保存的模板草稿",
            icon_style="warning",
            parent=self._parent,
        )
        dialog.add_message(
            f"当前会话暂存了 {count} 个未保存模板草稿。"
            "关闭程序前请选择保存全部、放弃全部或取消。"
        )
        selected = {"action": TEMPLATE_EDIT_CANCEL}

        cancel_btn = dialog.add_secondary_button("取消")
        cancel_btn.clicked.connect(dialog.reject)
        discard_btn = dialog.add_secondary_button("放弃全部")
        discard_btn.clicked.connect(
            lambda: self._accept(
                dialog,
                selected,
                TEMPLATE_EDIT_DISCARD,
            )
        )
        save_btn = dialog.add_primary_button("保存全部")
        save_btn.clicked.connect(
            lambda: self._accept(
                dialog,
                selected,
                TEMPLATE_EDIT_SAVE,
            )
        )
        dialog.exec()
        return str(selected["action"])
