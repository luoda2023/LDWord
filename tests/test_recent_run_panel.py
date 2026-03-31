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


def test_recent_run_panel_renders_quiet_status_and_meta_lines():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="partial_success",
            title="最近结果",
            summary="执行完成，但有 2 个模块未成功",
            output_label="out.docx",
            report_label="report.json",
            error_summary="",
        )

        panel.set_state(state)

        assert panel._status_label.objectName() == "wb_recent_run_status"
        assert panel._status_label.text() == "部分完成"
        assert panel._meta_label.objectName() == "wb_recent_run_meta"
        assert panel._meta_label.text() == "输出: out.docx | 报告: report.json"
    finally:
        panel.close()


def test_recent_run_panel_wraps_meta_line_for_long_paths():
    _app()
    panel = RecentRunPanel()
    try:
        state = RecentRunState(
            status="failed",
            title="最近结果",
            summary="执行失败",
            output_label="C:/very/long/path/output/document.docx",
            report_label="C:/very/long/path/report/details.json",
            error_summary="",
        )

        panel.set_state(state)

        assert panel._meta_label.wordWrap() is True
        assert "输出:" in panel._meta_label.text()
        assert "报告:" in panel._meta_label.text()
    finally:
        panel.close()
