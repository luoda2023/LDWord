# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.panels.workbench.recent_run_panel import RecentRunPanel
from src.ui.panels.workbench.state import RecentRunState


def _app():
    return QApplication.instance() or QApplication([])


def test_recent_run_panel_default_summary_text():
    _app()
    panel = RecentRunPanel()
    try:
        assert panel._summary.text() == "暂无最近结果"
    finally:
        panel.close()


def test_recent_run_panel_updates_summary_text():
    _app()
    panel = RecentRunPanel()
    try:
        panel.set_summary("已完成运行")
        assert panel._summary.text() == "已完成运行"
    finally:
        panel.close()


def test_recent_run_panel_wraps_long_summary():
    _app()
    panel = RecentRunPanel()
    try:
        long_text = "这是一段非常非常长的总结文本，应该在面板中正确换行显示而不会破坏布局。"
        panel.set_summary(long_text)
        assert panel._summary.text() == long_text
        assert panel._summary.wordWrap()
    finally:
        panel.close()


def test_recent_run_panel_accepts_recent_run_state_and_renders_summary():
    _app()
    panel = RecentRunPanel()
    try:
        panel.set_summary("旧的摘要")

        state = RecentRunState(
            status="success",
            title="最近结果",
            summary="本次执行已完成",
            output_label="out.docx",
            report_label="report.json",
            error_summary="",
        )
        panel.set_state(state)

        assert panel._summary.text() == "本次执行已完成"
    finally:
        panel.close()
