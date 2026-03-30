# -*- coding: utf-8 -*-
from __future__ import annotations

from src.qt_api import QLabel
from src.shared.ui.card import Card

from .state import RecentRunState


class RecentRunPanel(Card):
    def __init__(self, parent=None):
        super().__init__("最近结果", parent=parent)
        self._summary = QLabel("暂无最近结果")
        self._summary.setWordWrap(True)
        self.add_widget(self._summary)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def set_state(self, state: RecentRunState) -> None:
        # Keep rendering minimal for now: Task 5 only needs single-run lifecycle sync.
        self.set_summary(state.summary)
