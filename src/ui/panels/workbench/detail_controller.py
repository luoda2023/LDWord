from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.qt_api import QScrollArea, QVBoxLayout, QWidget


class WorkbenchDetailController:
    """Own detail-pane registration and visible-pane switching.

    Registration is also the ownership boundary for detail panes: every pane is
    reparented into the shared detail container and hidden until explicitly
    shown. That prevents placeholder/details widgets from lingering at the
    panel root origin before the first selection.
    """

    def __init__(
        self,
        detail_container: "QWidget",
        detail_layout: "QVBoxLayout",
        detail_scroll: "QScrollArea",
    ) -> None:
        self._detail_container = detail_container
        self._detail_layout = detail_layout
        self._detail_scroll = detail_scroll
        self.detail_map: dict[str, QWidget] = {}
        self._current_detail: QWidget | None = None

    @property
    def current_detail(self) -> "QWidget | None":
        return self._current_detail

    def register_details(self, details: dict[str, "QWidget"]) -> None:
        if self._current_detail is not None:
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
            self._detail_layout.removeWidget(self._current_detail)
            self._current_detail.hide()
            self._current_detail = None

        for detail in self.detail_map.values():
            detail.hide()
            if detail.parent() is not self._detail_container:
                detail.setParent(self._detail_container)

    def show_detail(self, card_id: str) -> "QWidget | None":
        detail = self.detail_map.get(card_id)
        if detail is None or detail is self._current_detail:
            return self._current_detail

        if self._current_detail is not None:
            self._detail_layout.removeWidget(self._current_detail)
            self._current_detail.hide()

        detail.setParent(self._detail_container)
        self._detail_layout.addWidget(detail)
        detail.show()
        self._current_detail = detail
        self._detail_scroll.verticalScrollBar().setValue(0)
        return detail


__all__ = ["WorkbenchDetailController"]
