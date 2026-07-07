"""Shared owner toolbar for paragraph-style surfaces."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.qt_api import QLabel, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class StyleOwnerOption:
    key: str
    label: str


class StyleControlOwnerToolbar(QWidget):
    """Shared toolbar for selecting a style owner and exposing owner actions."""

    current_key_changed = Signal(str)
    action_requested = Signal()

    def __init__(
        self,
        parent=None,
        *,
        title: str = "编辑样式",
        selector_label: str = "编辑分区",
        action_label: str = "恢复模板",
        object_name_prefix: str = "style_owner",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_owner").strip()

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName(f"{prefix}_title")

        self._selector = StyledComboBox(self)
        self._selector.setObjectName(f"{prefix}_selector")
        self._selector.setSizeAdjustPolicy(
            self._selector.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self._selector.currentIndexChanged.connect(self._emit_current_key_changed)

        self._action_button = QPushButton(action_label, self)
        self._action_button.setObjectName(f"{prefix}_action")
        self._action_button.clicked.connect(self.action_requested.emit)

        tools = QWidget(self)
        tools_layout = QHBoxLayout(tools)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(8)
        tools_layout.addWidget(self._selector, 1)
        tools_layout.addWidget(self._action_button)

        self._hint_label = QLabel("", self)
        self._hint_label.setObjectName(f"{prefix}_hint")
        self._hint_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title_label)
        layout.addWidget(template_form_row(selector_label, tools, parent=self))
        layout.addWidget(self._hint_label)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def selector(self) -> StyledComboBox:
        return self._selector

    @property
    def action_button(self) -> QPushButton:
        return self._action_button

    @property
    def hint_label(self) -> QLabel:
        return self._hint_label

    def set_options(self, options: Sequence[StyleOwnerOption]) -> None:
        current = self.current_key()
        blocked = self._selector.blockSignals(True)
        try:
            self._selector.clear()
            for option in options:
                self._selector.addItem(option.label, option.key)
        finally:
            self._selector.blockSignals(blocked)
        if current:
            self.set_current_key(current)

    def current_key(self) -> str:
        return str(self._selector.currentData() or "")

    def set_current_key(self, key: str) -> bool:
        target = str(key or "").strip()
        for index in range(self._selector.count()):
            if str(self._selector.itemData(index) or "") == target:
                blocked = self._selector.blockSignals(True)
                try:
                    self._selector.setCurrentIndex(index)
                finally:
                    self._selector.blockSignals(blocked)
                return True
        return False

    def set_action_enabled(self, enabled: bool) -> None:
        self._action_button.setEnabled(bool(enabled))

    def set_hint(self, text: str) -> None:
        self._hint_label.setText(str(text or ""))

    def apply_theme(self) -> None:
        self._apply_theme()

    def _emit_current_key_changed(self, *_args) -> None:
        self.current_key_changed.emit(self.current_key())

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(build_button_stylesheet(theme))
        self._title_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.text_secondary};"
        )
        self._hint_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        )
        apply_button_variant(self._action_button, "secondary")


__all__ = ["StyleControlOwnerToolbar", "StyleOwnerOption"]
