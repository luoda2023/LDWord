"""Cardless style-difference summary slot for template/current comparisons."""

from __future__ import annotations

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget
from src.shared.ui.style_comparison_strip import StyleComparisonStrip


class StyleDifferenceSummarySlot(QWidget):
    """A lightweight slot that gives comparison strips an explicit difference role."""

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_difference",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_difference").strip()
        self.setObjectName(f"{prefix}_difference_slot")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._comparison_strip = StyleComparisonStrip(
            self,
            object_name_prefix=f"{prefix}_comparison",
        )
        layout.addWidget(self._comparison_strip)
        self._sync_properties()

    @property
    def comparison_strip(self) -> StyleComparisonStrip:
        return self._comparison_strip

    def apply_projection(self, projection) -> None:
        self._comparison_strip.apply_projection(projection)
        has_projection = projection is not None
        self.setProperty("style_difference_has_projection", has_projection)
        self.setProperty(
            "style_difference_template_status",
            self._comparison_strip.property("style_compare_template_status") or "",
        )
        self.setProperty(
            "style_difference_current_status",
            self._comparison_strip.property("style_compare_current_status") or "",
        )
        self.setProperty(
            "style_difference_status",
            self._comparison_strip.property("style_compare_difference_status") or "",
        )
        self.setProperty(
            "style_difference_detail",
            self._comparison_strip.property("style_compare_detail") or "",
        )

    def apply_theme(self) -> None:
        self._comparison_strip.apply_theme()

    def _sync_properties(self) -> None:
        self.setProperty("style_difference_content_plan", "difference")
        self.setProperty("style_difference_slot_surface", "embedded")
        self.setProperty("style_difference_has_projection", False)
        self.setProperty("style_difference_template_status", "")
        self.setProperty("style_difference_current_status", "")
        self.setProperty("style_difference_status", "")
        self.setProperty("style_difference_detail", "")


__all__ = ["StyleDifferenceSummarySlot"]
