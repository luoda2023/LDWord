import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.change_tracker import ChangeTracker
from src.engine.pipeline import PipelineResult
from src.ui.main_window import (
    MainWindow,
    _format_execution_log_pipeline_controls,
    _format_execution_log_sections,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_execution_log_helpers_localize_sections_and_pipeline_steps():
    sections = _format_execution_log_sections(["body", "abstract_cn", "toc"])
    assert sections == "正文、中文摘要、目录"

    line = _format_execution_log_pipeline_controls(
        ["md_cleanup", "formula_convert", "citation_link"]
    )
    assert "Markdown 文本修复=开启" in line
    assert "公式编码统一=开启" in line
    assert "正文参考文献域关联=开启" in line
    assert "md_cleanup" not in line
    assert "formula_convert" not in line
    assert "citation_link" not in line


def test_execution_log_failure_line_uses_chinese_rule_and_target(monkeypatch):
    _app()
    monkeypatch.setattr(MainWindow, "_load_ui_state", lambda self: {})
    monkeypatch.setattr(MainWindow, "_save_ui_state", lambda self: None)

    window = MainWindow()
    logs: list[str] = []
    try:
        window._log = lambda msg: logs.append(str(msg))

        tracker = ChangeTracker()
        tracker.record(
            rule_name="formula_convert",
            target="range_scope",
            section="body",
            change_type="skip",
            before="",
            after="",
            paragraph_index=0,
            success=False,
            failure_reason="示例失败",
        )

        result = PipelineResult(
            success=True,
            status="partial_success",
            doc=object(),
            tracker=tracker,
            output_paths={},
            failed_items=[
                {
                    "rule_name": "formula_convert",
                    "target": "range_scope",
                    "change_type": "skip",
                    "reason": "示例失败",
                }
            ],
        )

        window._on_worker_finished(result)

        joined = "\n".join(logs)
        assert "[公式编码统一] 范围外内容: 示例失败" in joined
        assert "formula_convert" not in joined
        assert "range_scope" not in joined
    finally:
        window.close()
