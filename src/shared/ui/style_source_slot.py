"""Stable source slot for style-management blocks."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later
from src.shared.ui.style_source_compact_row import StyleSourceCompactRow


class StyleSourceSlot(QWidget):
    """Named source/scope slot that owns a style-source renderer."""

    navigate_requested = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_source",
        source_row: StyleSourceCompactRow | None = None,
        context_widgets: Sequence[QWidget] = (),
        row_object_name_prefix: str | None = None,
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_source").strip()
        row_prefix = str(row_object_name_prefix or f"{prefix}_row").strip()
        self.setObjectName(f"{prefix}_slot")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for widget in context_widgets:
            self.add_context_widget(widget)

        self._source_row = source_row or StyleSourceCompactRow(
            self,
            object_name_prefix=row_prefix,
        )
        self._source_row.navigate_requested.connect(self.navigate_requested.emit)
        layout.addWidget(self._source_row)

        self.setProperty("style_source_slot_has_projection", False)

    @property
    def source_row(self) -> StyleSourceCompactRow:
        return self._source_row

    def add_context_widget(self, widget: QWidget) -> None:
        layout = self.layout()
        if layout is None:
            return
        widget.setParent(self)
        insert_at = max(0, layout.count() - 1)
        layout.insertWidget(insert_at, widget)

    def apply_projection(self, projection) -> None:
        self._source_row.apply_projection(projection)
        view_mode = str(getattr(projection, "view_mode", "") or "").strip()
        status_label = str(getattr(projection, "status_label", "") or "").strip()
        self.setProperty("style_source_slot_has_projection", projection is not None)
        self.setProperty("style_source_slot_view_mode", view_mode)
        self.setProperty("style_source_slot_status_label", status_label)
        refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def summary_text(self) -> str:
        return self._source_row.summary_text()


__all__ = ["StyleSourceSlot"]
