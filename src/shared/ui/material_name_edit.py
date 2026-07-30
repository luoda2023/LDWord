"""Reusable material display-name surface."""

from __future__ import annotations

from src.shared.ui.projected_text_edit import (
    EditActivation,
    ProjectedTextEdit,
    TextSurface,
)
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.text_projection import TextElideMode


class MaterialNameEdit(ProjectedTextEdit):
    """Material name with the shared copy/edit interaction contract."""

    def __init__(self, text: object = "", parent=None) -> None:
        super().__init__(
            text,
            parent,
            editable=True,
            activation=EditActivation.COPY_DOUBLE_EDIT,
            surface=TextSurface.FRAMED,
            elide_mode=TextElideMode.RIGHT,
            show_full_text_tooltip=True,
            expand_editor_on_overflow=True,
        )
        self.setClearButtonEnabled(False)
        self.setAccessibleName("材料名称；单击复制，双击修改")
        apply_size_class(self, "md")

    def _expanded_editor_title(self) -> str:
        return "编辑材料名称"


__all__ = ["MaterialNameEdit"]
