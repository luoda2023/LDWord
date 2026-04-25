import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.engine.document_structure_preview import StructurePreviewItem
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


def test_quick_execution_detail_writes_user_strategy_scope_and_feature_changes_back_to_scene():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._strategy_preserve.setChecked(True)
        detail._zones_clear_all()
        detail._on_feature_row_toggled("content_fill", True)

        assert detail.current_scene().strict_mode is False
        assert all(enabled is False for enabled in detail.current_scene().format_scope.sections.values())
        assert detail.current_scene().is_module_enabled("entity_fill") is True
    finally:
        detail.close()


def test_quick_execution_detail_builds_runtime_page_start_overrides():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._set_structure_items(
            [
                StructurePreviewItem("cover", "封面", 0, 1, "封面"),
                StructurePreviewItem("toc", "目录", 1, 2, "目录"),
                StructurePreviewItem("body", "正文", 2, 5, "第一章 绪论"),
            ],
            status="已识别 3 个内容块",
        )

        detail._page_start_combo.setCurrentIndex(1)
        assert detail.runtime_template_overrides() == {
            "header_footer.suppress_header_footer_selectors": []
        }
        assert detail._page_start_summary_text() == "页码从封面"

        detail._page_start_combo.setCurrentIndex(3)
        assert detail.runtime_template_overrides() == {
            "header_footer.suppress_header_footer_selectors": ["cover", "toc"]
        }
        assert detail._page_start_summary_text() == "页码从正文"
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


def test_shared_dashed_separator_is_exported_for_reuse():
    separator_path = ROOT / "src/shared/ui/dashed_separator.py"
    assert separator_path.exists()

    separator_source = separator_path.read_text(encoding="utf-8")
    export_source = (ROOT / "src/shared/ui/__init__.py").read_text(encoding="utf-8")

    assert "class DashedSeparator" in separator_source
    assert '"DashedSeparator": (".dashed_separator", "DashedSeparator")' in export_source


def test_quick_execution_detail_uses_shared_dashed_separator_instead_of_private_widgets():
    module_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert "from src.shared.ui import DashedSeparator" in module_source
    assert "class _DashedLine" not in module_source
    assert "class _DashedVLine" not in module_source
    assert "DashedSeparator(orientation=\"vertical\"" in module_source
    assert "DashedSeparator(orientation=\"horizontal\"" in module_source
