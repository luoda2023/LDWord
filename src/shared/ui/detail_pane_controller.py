from __future__ import annotations

from typing import TYPE_CHECKING

from src.qt_api import QObject
from src.shared.ui.detail_geometry import ScrollableDetailGeometrySync

if TYPE_CHECKING:
    from src.qt_api import QScrollArea, QVBoxLayout, QWidget


class DetailPaneController(QObject):
    """Own detail-pane registration and visible-pane switching."""

    def __init__(
        self,
        detail_container: "QWidget",
        detail_layout: "QVBoxLayout",
        detail_scroll: "QScrollArea",
    ) -> None:
        super().__init__(detail_container)
        self._detail_container = detail_container
        self._detail_layout = detail_layout
        self._detail_scroll = detail_scroll
        self._geometry = ScrollableDetailGeometrySync(
            detail_container,
            detail_layout,
            detail_scroll,
            parent=self,
        )
        self.detail_map: dict[str, QWidget] = {}
        self._current_detail: QWidget | None = None

    @property
    def current_detail(self) -> "QWidget | None":
        return self._current_detail

    def register_details(self, details: dict[str, "QWidget"]) -> None:
        if self._current_detail is not None:
            self._geometry.set_active_widget(None)
            self._detail_layout.removeWidget(self._current_detail)
            self._current_detail.hide()
            self._current_detail = None

        self.detail_map = {}
        for card_id, detail in details.items():
            detail.hide()
            detail.setParent(self._detail_container)
            self.detail_map[card_id] = detail

    def hide_all(self) -> None:
        """Hide every registered pane without discarding registrations."""
        if self._current_detail is not None:
            self._geometry.set_active_widget(None)
            self._detail_layout.removeWidget(self._current_detail)
            self._current_detail.hide()
            self._current_detail = None

        for detail in self.detail_map.values():
            detail.hide()
            if detail.parent() is not self._detail_container:
                detail.setParent(self._detail_container)

    def show_detail(self, card_id: str) -> "QWidget | None":
        detail = self.detail_map.get(card_id)
        if detail is None:
            return self._current_detail
        if detail is self._current_detail:
            self._geometry.sync_now(detail)
            return self._current_detail

        previous_detail = self._current_detail
        self._detail_scroll.setUpdatesEnabled(False)
        self._detail_container.setUpdatesEnabled(False)
        try:
            if previous_detail is not None:
                self._geometry.set_active_widget(None)
                self._detail_layout.removeWidget(previous_detail)
                previous_detail.hide()
            detail.setParent(self._detail_container)
            self._detail_layout.addWidget(detail)
            self._current_detail = detail
            self._geometry.set_active_widget(detail)
            detail.show()
            self._detail_layout.activate()
            self._geometry.sync_now(detail)
        finally:
            self._detail_scroll.verticalScrollBar().setValue(0)
            self._detail_container.setUpdatesEnabled(True)
            self._detail_scroll.setUpdatesEnabled(True)
        return detail


WorkbenchDetailController = DetailPaneController


__all__ = ["DetailPaneController", "WorkbenchDetailController"]
