"""Compact style comparison strip for template/current/difference state."""

from __future__ import annotations

from src.qt_api import QLabel, QHBoxLayout, QSizePolicy, QWidget
from src.shared.ui.theme import bind_theme, get_theme


class StyleComparisonStrip(QWidget):
    """Show the template baseline, current section state, and difference summary."""

    _ORDER = (
        ("template", "模板基线"),
        ("current", "当前分区"),
        ("difference", "差异"),
    )

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_comparison",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_comparison").strip()
        self.setObjectName(prefix)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._labels: dict[str, QLabel] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for key, label in self._ORDER:
            widget = QLabel(f"{label}：-", self)
            widget.setObjectName(f"{prefix}_{key}")
            widget.setWordWrap(True)
            self._labels[key] = widget
            layout.addWidget(widget, 1)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def template_label(self) -> QLabel:
        return self._labels["template"]

    @property
    def current_label(self) -> QLabel:
        return self._labels["current"]

    @property
    def difference_label(self) -> QLabel:
        return self._labels["difference"]

    def apply_projection(self, projection) -> None:
        if projection is None:
            self.set_status(
                template="-",
                current="选择分区",
                difference="-",
                detail="",
            )
            self.setEnabled(False)
            return
        self.setEnabled(True)
        self.set_status(
            template=str(getattr(projection, "template_status", "") or "-"),
            current=str(getattr(projection, "current_status", "") or "-"),
            difference=str(getattr(projection, "difference_status", "") or "-"),
            detail=str(getattr(projection, "detail", "") or ""),
        )

    def set_status(
        self,
        *,
        template: str,
        current: str,
        difference: str,
        detail: str = "",
    ) -> None:
        values = {
            "template": str(template or "-").strip() or "-",
            "current": str(current or "-").strip() or "-",
            "difference": str(difference or "-").strip() or "-",
        }
        for key, title in self._ORDER:
            self._labels[key].setText(f"{title}：{values[key]}")
            self.setProperty(f"style_compare_{key}_status", values[key])
        self.setProperty("style_compare_detail", str(detail or ""))
        self.setToolTip(str(detail or ""))

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        style = (
            f"font-size: {theme.font_size_sm}px; "
            f"color: {theme.text_secondary}; "
            f"background: {theme.bg_card}; "
            f"border: 1px solid {theme.border_light}; "
            f"border-radius: {theme.radius_sm}px; "
            "padding: 5px 8px;"
        )
        for label in self._labels.values():
            label.setStyleSheet(style)


__all__ = ["StyleComparisonStrip"]
