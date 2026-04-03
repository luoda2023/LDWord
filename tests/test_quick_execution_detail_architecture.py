import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.panels.workbench.quick_execution_drop_area import QuickExecutionDropArea
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail
from src.ui.panels.workbench.scene_presets import LEGACY_FEATURE_GROUP_MAP


def _app():
    return QApplication.instance() or QApplication([])


def test_quick_execution_detail_uses_presenter_module_for_snapshot_and_status_logic():
    detail_source = inspect.getsource(QuickExecutionDetail)
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert "from .quick_execution_presenter import" in module_source
    assert "from .quick_execution_drop_area import QuickExecutionDropArea" in module_source
    assert "build_navigation_snapshot(" in detail_source
    assert "build_feature_navigation_snapshot(" in detail_source
    assert "build_ready_status(" in detail_source
    assert "build_running_status(" in detail_source


def test_quick_execution_detail_uses_dedicated_drop_area_widget():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert isinstance(detail._drop_area, QuickExecutionDropArea)
        assert detail.document_path() == ""
    finally:
        detail.close()


def test_quick_execution_detail_reports_presenter_derived_status_and_snapshot():
    _app()
    detail = QuickExecutionDetail()
    try:
        assert detail._status_label.text() == "请先选择输入文档"
        assert detail.navigation_snapshot() == {
            "subtitle": "未选择文档 · 默认流程",
            "badge_text": "待补充",
            "badge_variant": "warning",
        }

        detail.set_document_path("C:/docs/report.docx")
        detail.set_strategy_context(template_name="汇报演示", strict_mode=False)
        detail.set_feature_enabled("content_fill", True)

        assert detail._status_label.text() == "就绪：report.docx · 汇报演示 · 标准模式"
        assert detail.navigation_snapshot() == {
            "subtitle": "report.docx · 汇报演示",
            "badge_text": "1 项增强",
            "badge_variant": "success",
        }
        assert detail.feature_navigation_snapshot("content_fill") == {
            "subtitle": "Excel / 5 个映射字段",
            "badge_text": "数据就绪",
            "badge_variant": "neutral",
        }
    finally:
        detail.close()


def test_quick_execution_detail_uses_shared_legacy_feature_group_map():
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert LEGACY_FEATURE_GROUP_MAP == {
        "heading_numbering": "table_chart",
        "quick_fill": "content_fill",
    }
    assert "LEGACY_FEATURE_GROUP_MAP" in module_source
    assert "FEATURE_ID_ALIASES = {" not in module_source
