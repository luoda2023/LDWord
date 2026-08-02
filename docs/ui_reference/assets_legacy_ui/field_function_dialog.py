"""Realtime function picker for official-document material fields."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.qt_api import QDialog, Qt
from src.shared.engine.material_field_function import normalize_field_functions
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.styled_combo_box import StyledComboBox


_FUNCTION_OPTIONS = (
    ("实时日期", "realtime_date"),
    ("实时时间", "realtime_time"),
    ("实时日期时间", "realtime_datetime"),
)


def choose_official_field_function(
    *,
    parent,
    target_key: str,
    fields: Sequence[tuple[str, str]],
    values: Mapping[str, object],
    field_functions: Mapping[str, object],
) -> tuple[str, dict[str, str] | None]:
    """Return ("apply" | "clear" | "cancel", function spec)."""

    dialog = _OfficialFieldFunctionDialog(
        parent=parent,
        target_key=target_key,
        fields=fields,
        values=values,
        field_functions=field_functions,
    )
    if dialog.exec() != QDialog.Accepted:
        return "cancel", None
    if dialog.cleared:
        return "clear", None
    return "apply", dialog.selected_function()


class _OfficialFieldFunctionDialog(BaseDialog):
    def __init__(
        self,
        *,
        parent,
        target_key: str,
        fields: Sequence[tuple[str, str]],
        values: Mapping[str, object],
        field_functions: Mapping[str, object],
    ) -> None:
        super().__init__(title="插入字段函数", icon_style="input", parent=parent)
        self.setMinimumWidth(420)
        # The shared combo popup is intentionally window-bound.  Keep enough
        # room below this lone selector for all three realtime functions so
        # the popup does not flip upward or introduce a scrollbar.
        self.setMinimumHeight(264)
        self._target_key = str(target_key)
        self._field_functions = normalize_field_functions(field_functions)
        self.cleared = False
        current_spec = self._field_functions.get(self._target_key, {})

        self._function_combo = StyledComboBox(self)
        self._function_combo.set_full_width_mode()
        self._function_combo.setAccessibleName("字段函数")
        for label, function_name in _FUNCTION_OPTIONS:
            self._function_combo.addItem(label, function_name)
        self.content_layout.addWidget(self._function_combo)
        self.content_layout.setAlignment(Qt.AlignTop)

        if current_spec:
            index = self._function_combo.findData(current_spec.get("function"))
            if index >= 0:
                self._function_combo.setCurrentIndex(index)

        cancel = self.add_secondary_button("取消")
        cancel.clicked.connect(self.reject)
        if current_spec:
            clear = self.add_secondary_button("移除函数")
            clear.clicked.connect(self._clear_and_accept)
        apply = self.add_primary_button("插入函数")
        apply.clicked.connect(self.accept)

    def selected_function(self) -> dict[str, str]:
        return {
            "function": str(
                self._function_combo.currentData() or "realtime_date"
            )
        }

    def _clear_and_accept(self) -> None:
        self.cleared = True
        self.accept()


__all__ = ["choose_official_field_function"]
