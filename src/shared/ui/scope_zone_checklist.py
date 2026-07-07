"""Reusable checklist for scene processing zones."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.qt_api import QCheckBox, QSizePolicy, QWidget, Signal
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class ScopeZoneOption:
    key: str
    label: str


class ScopeZoneChecklist(QWidget):
    """Small UI boundary for processing-scope zone checkboxes."""

    checked_changed = Signal(str, bool)

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "scope_zone_checklist",
        h_spacing: int = 16,
        v_spacing: int = 4,
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "scope_zone_checklist").strip()
        self.setObjectName(prefix)
        self._checks: dict[str, QCheckBox] = {}
        self._flow = FlowLayout(self, h_spacing=h_spacing, v_spacing=v_spacing)
        self._flow.setContentsMargins(0, 6, 0, 0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def checks(self) -> dict[str, QCheckBox]:
        return self._checks

    @property
    def flow(self) -> FlowLayout:
        return self._flow

    def set_options(self, options: Sequence[ScopeZoneOption]) -> None:
        if self._checks:
            raise RuntimeError("ScopeZoneChecklist options are immutable after setup")

        for option in options:
            key = str(option.key or "").strip()
            if not key:
                continue
            checkbox = QCheckBox(option.label, self)
            checkbox.toggled.connect(
                lambda checked, item_key=key: self.checked_changed.emit(
                    item_key,
                    bool(checked),
                )
            )
            self._checks[key] = checkbox
            self._flow.addWidget(checkbox)
        self._apply_theme()

    def set_checked(self, key: str, checked: bool) -> None:
        checkbox = self._checks.get(str(key or "").strip())
        if checkbox is not None:
            checkbox.setChecked(bool(checked))

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        stylesheet = build_checkbox_stylesheet(get_theme())
        for checkbox in self._checks.values():
            checkbox.setStyleSheet(stylesheet)


__all__ = ["ScopeZoneChecklist", "ScopeZoneOption"]
