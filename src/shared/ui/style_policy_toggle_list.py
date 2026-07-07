"""Reusable toggle list for style policy controls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.qt_api import QLabel, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget, Signal, Qt
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch


@dataclass(frozen=True, slots=True)
class StylePolicyToggleOption:
    key: str
    label: str
    tooltip: str = ""


class StylePolicyToggleList(QWidget):
    """Small UI boundary for named style-policy toggles."""

    toggled = Signal(str, bool)
    activated = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        title: str = "策略",
        object_name_prefix: str = "style_policy_toggle_list",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_policy_toggle_list").strip()
        self.setObjectName(prefix)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName(f"{prefix}_title")
        self._prefix = prefix
        self._current_policy_key = ""
        self.setProperty("style_policy_current_key", "")
        self._toggles: dict[str, ToggleSwitch] = {}
        self._rows: dict[str, QWidget] = {}
        self._label_by_key: dict[str, QLabel] = {}
        self._status_by_key: dict[str, QLabel] = {}
        self._labels: list[QLabel] = []
        self._statuses: list[QLabel] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.addWidget(self._title_label)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def toggles(self) -> dict[str, ToggleSwitch]:
        return self._toggles

    @property
    def rows(self) -> dict[str, QWidget]:
        return self._rows

    @property
    def labels(self) -> tuple[QLabel, ...]:
        return tuple(self._labels)

    @property
    def status_labels(self) -> tuple[QLabel, ...]:
        return tuple(self._statuses)

    def set_options(self, options: Sequence[StylePolicyToggleOption]) -> None:
        if self._rows:
            raise RuntimeError("StylePolicyToggleList options are immutable after setup")

        for option in options:
            key = str(option.key or "").strip()
            if not key:
                continue
            row = QWidget(self)
            row.setObjectName(f"{self._prefix}_{_object_name_fragment(key)}_row")
            row.setCursor(Qt.PointingHandCursor)
            row.setProperty("style_policy_row_key", key)
            row.setProperty("style_policy_row_current", False)
            row.setProperty("style_policy_row_checked", False)
            row.mousePressEvent = (
                lambda _event, item_key=key: self.activate_policy(item_key)
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 5, 10, 5)
            row_layout.setSpacing(10)

            label = QLabel(option.label, row)
            label.setObjectName(f"{self._prefix}_{_object_name_fragment(key)}_label")
            label.setCursor(Qt.PointingHandCursor)
            label.setProperty("style_policy_row_key", key)
            label.setProperty("style_policy_row_current", False)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            label.mousePressEvent = (
                lambda _event, item_key=key: self.activate_policy(item_key)
            )
            row_layout.addWidget(label, 1)

            status = QLabel("跟随模板", row)
            status.setObjectName(f"{self._prefix}_{_object_name_fragment(key)}_status")
            status.setCursor(Qt.PointingHandCursor)
            status.setProperty("style_policy_row_key", key)
            status.setProperty("style_policy_row_checked", False)
            status.mousePressEvent = (
                lambda _event, item_key=key: self.activate_policy(item_key)
            )
            row_layout.addWidget(status, 0)

            toggle = ToggleSwitch(row, checked=False)
            tooltip = option.tooltip or f"为「{option.label}」启用策略"
            toggle.setToolTip(tooltip)
            toggle.toggled_signal.connect(
                lambda checked, item_key=key: self._on_toggle_changed(
                    item_key,
                    bool(checked),
                )
            )
            row_layout.addWidget(toggle)

            self._labels.append(label)
            self._statuses.append(status)
            self._label_by_key[key] = label
            self._status_by_key[key] = status
            self._toggles[key] = toggle
            self._rows[key] = row
            self._layout.addWidget(row)
        self._apply_theme()

    def set_checked(self, key: str, checked: bool) -> None:
        normalized_key = str(key or "").strip()
        toggle = self._toggles.get(normalized_key)
        if toggle is not None:
            toggle.set_checked(bool(checked), animate=False)
            self._sync_status_label(normalized_key)

    def set_row_visible(self, key: str, visible: bool) -> None:
        row = self._rows.get(str(key or "").strip())
        if row is not None:
            row.setVisible(bool(visible))

    def activate_policy(self, key: str) -> bool:
        policy_key = str(key or "").strip()
        if not policy_key or policy_key not in self._rows:
            return False
        self.activated.emit(policy_key)
        return True

    def current_policy_key(self) -> str:
        return self._current_policy_key

    def set_current_policy_key(self, key: str) -> bool:
        policy_key = str(key or "").strip()
        if policy_key and policy_key not in self._rows:
            return False
        self._current_policy_key = policy_key
        self.setProperty("style_policy_current_key", policy_key)
        self._sync_current_row_styles()
        return True

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._title_label.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.text_secondary};"
        )
        label_ss = f"font-size: {theme.font_size_sm}px; color: {theme.text_primary};"
        for label in self._labels:
            label.setStyleSheet(label_ss)
        for key in self._status_by_key:
            self._sync_status_label(key)
        self._sync_current_row_styles()

    def _on_toggle_changed(self, key: str, checked: bool) -> None:
        normalized_key = str(key or "").strip()
        self._sync_status_label(normalized_key)
        self.toggled.emit(normalized_key, bool(checked))

    def _sync_status_label(self, key: str) -> None:
        normalized_key = str(key or "").strip()
        status = self._status_by_key.get(normalized_key)
        toggle = self._toggles.get(normalized_key)
        row = self._rows.get(normalized_key)
        if status is None or toggle is None:
            return
        checked = bool(toggle.isChecked())
        if row is not None:
            row.setProperty("style_policy_row_checked", checked)
        status.setProperty("style_policy_row_checked", checked)
        status.setText("独立样式" if checked else "跟随模板")
        theme = get_theme()
        status.setStyleSheet(
            f"font-size: {theme.font_size_xs}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.primary if checked else theme.text_hint}; "
            f"background: {theme.primary_light if checked else theme.bg_hover}; "
            f"border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px; "
            f"padding: 2px 8px;"
        )

    def _sync_current_row_styles(self) -> None:
        theme = get_theme()
        for key, row in self._rows.items():
            current = bool(key and key == self._current_policy_key)
            checked = bool(self._toggles.get(key) and self._toggles[key].isChecked())
            row.setProperty("style_policy_row_current", current)
            row.setProperty("style_policy_row_checked", checked)
            row.setStyleSheet(
                f"QWidget#{row.objectName()} {{"
                f"background: {theme.bg_selected if current else 'transparent'};"
                f"border: 1px solid {theme.border_light if current else 'transparent'};"
                f"border-radius: {theme.radius_sm}px;"
                f"}}"
            )
            label = self._label_by_key.get(key)
            if label is not None:
                label.setProperty("style_policy_row_current", current)
                label.setStyleSheet(
                    f"font-size: {theme.font_size_sm}px; "
                    f"font-weight: {theme.font_weight_emphasis if current else theme.font_weight_normal}; "
                    f"color: {theme.primary if current else theme.text_primary};"
                )
            self._sync_status_label(key)


def _object_name_fragment(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value))


__all__ = ["StylePolicyToggleList", "StylePolicyToggleOption"]
