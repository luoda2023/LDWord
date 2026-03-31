# -*- coding: utf-8 -*-
from __future__ import annotations

from src.qt_api import QLabel
from src.shared.ui.card import Card

from .state import RecentRunState


class RecentRunPanel(Card):
    _STATUS_LABELS = {
        "idle": "未执行",
        "success": "已完成",
        "partial_success": "部分完成",
        "failed": "执行失败",
        "cancelled": "已取消",
    }

    def __init__(self, parent=None):
        super().__init__("最近结果", parent=parent)
        self._status_label = QLabel(self._STATUS_LABELS["idle"])
        self._status_label.setObjectName("wb_recent_run_status")
        self._summary = QLabel("暂无最近结果")
        self._summary.setWordWrap(True)
        self._meta_label = QLabel("")
        self._meta_label.setObjectName("wb_recent_run_meta")
        self._meta_label.setWordWrap(True)
        self.add_widget(self._status_label)
        self.add_widget(self._summary)
        self.add_widget(self._meta_label)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def set_state(self, state: RecentRunState) -> None:
        self._status_label.setText(self._STATUS_LABELS.get(state.status, self._STATUS_LABELS["idle"]))
        self.set_summary(state.summary)
        meta_parts = []
        if state.output_label:
            meta_parts.append(f"输出: {state.output_label}")
        if state.report_label:
            meta_parts.append(f"报告: {state.report_label}")
        if state.error_summary:
            meta_parts.append(f"错误: {state.error_summary}")
        self._meta_label.setText(" | ".join(meta_parts))
