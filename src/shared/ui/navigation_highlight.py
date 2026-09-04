"""Shared navigation-field highlight state for template and scene detail panes."""

from __future__ import annotations

from src.qt_api import QWidget
from src.shared.ui.theme import get_theme


class NavigationHighlighter:
    """Highlight one widget at a time and restore the previous widget style."""

    def __init__(self, *, tooltip_prefix: str = "当前执行问题定位") -> None:
        self._widget: QWidget | None = None
        self._base_style = ""
        self._base_tooltip = ""
        self._tooltip_prefix = tooltip_prefix

    @property
    def current_widget(self) -> QWidget | None:
        return self._widget

    def clear(self) -> None:
        if self._widget is None:
            return
        self._widget.setProperty("navigation_field_highlight", False)
        self._widget.setProperty("navigation_field_display_label", "")
        self._widget.setProperty("navigation_field_raw_label", "")
        self._widget.setProperty("navigation_field_diagnostic_label", "")
        self._widget.setToolTip(self._base_tooltip)
        self._widget.setStyleSheet(self._base_style)
        self._widget = None
        self._base_style = ""
        self._base_tooltip = ""

    def highlight(
        self,
        widget: QWidget,
        label: str,
        *,
        display_label: str = "",
    ) -> None:
        self.clear()
        self._widget = widget
        self._base_style = widget.styleSheet()
        self._base_tooltip = widget.toolTip()
        t = get_theme()
        raw_label = str(label or "").strip()
        visible_label = str(display_label or "").strip() or raw_label
        diagnostic_label = raw_label if raw_label and raw_label != visible_label else ""
        widget.setProperty("navigation_field_highlight", True)
        widget.setProperty("navigation_field_display_label", visible_label)
        widget.setProperty("navigation_field_raw_label", raw_label)
        widget.setProperty("navigation_field_diagnostic_label", diagnostic_label)
        widget.setToolTip(f"{self._tooltip_prefix}：{visible_label}")
        widget.setStyleSheet(
            self._base_style
            + f"; border: 2px solid {t.primary}; border-radius: {t.radius_sm}px;"
        )
        widget.setFocus()


__all__ = ["NavigationHighlighter"]
