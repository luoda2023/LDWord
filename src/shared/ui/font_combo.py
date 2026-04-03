"""Editable system-font combo."""

from __future__ import annotations

from functools import lru_cache

from src.qt_api import QComboBox, Signal
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox

_CN_FONTS = ("宋体", "黑体", "仿宋", "楷体", "微软雅黑", "华文中宋", "华文楷体")
_EN_FONTS = ("Times New Roman", "Arial", "Calibri", "Courier New", "Cambria")


@lru_cache(maxsize=1)
def installed_font_families() -> tuple[str, ...]:
    try:
        from PySide6.QtGui import QFontDatabase
    except Exception:
        return ()

    try:
        names = sorted(
            {str(name).strip() for name in QFontDatabase.families() if str(name).strip()},
            key=lambda item: item.casefold(),
        )
    except Exception:
        return ()
    return tuple(names)


def ordered_font_families(lang: str) -> tuple[str, ...]:
    preferred = _CN_FONTS if lang == "cn" else _EN_FONTS
    installed = installed_font_families()
    ordered: list[str] = []
    seen: set[str] = set()

    def push(name: str) -> None:
        normalized = str(name or "").strip()
        if not normalized:
            return
        key = normalized.casefold()
        if key in seen:
            return
        seen.add(key)
        ordered.append(normalized)

    for name in preferred:
        if not installed or any(name.casefold() == item.casefold() for item in installed):
            push(name)
    for name in installed:
        push(name)
    if not ordered:
        for name in preferred:
            push(name)
    return tuple(ordered)


class FontCombo(StyledComboBox):
    """Editable font selector backed by installed system families."""

    font_changed = Signal(str)

    def __init__(self, *, lang: str = "cn", parent=None):
        super().__init__(parent)
        self._lang = lang
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMinimumWidth(160)
        self.setMaxVisibleItems(16)
        apply_size_class(self, "md")
        self._populate()
        self.currentTextChanged.connect(self._on_text_changed)
        self.setToolTip("下拉显示本机已安装字体，也支持直接输入字体名。")

        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("输入字体名或下拉选择")
            line_edit.setToolTip("例如宋体、黑体、Times New Roman，未收录字体名也会保留。")

    def _populate(self) -> None:
        self.addItems(list(ordered_font_families(self._lang)))

    def _on_text_changed(self, text: str) -> None:
        self.font_changed.emit(str(text or "").strip())

    def selected_font(self) -> str:
        return str(self.currentText() or "").strip()

    def set_font_name(self, name: str) -> None:
        normalized = str(name or "").strip()
        if not normalized:
            self.setCurrentIndex(-1)
            self.setEditText("")
            return

        index = self.findText(normalized)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        self.setEditText(normalized)
