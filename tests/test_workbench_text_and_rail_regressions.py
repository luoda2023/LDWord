import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.dynamic_navigation_rail import DynamicNavigationRail


def _app():
    return QApplication.instance() or QApplication([])


def test_dynamic_navigation_rail_can_remove_section_header_without_stale_deleted_labels():
    _app()
    rail = DynamicNavigationRail()
    try:
        header = rail.add_section_header("高级功能")
        rail.remove_section_header(header)
        rail._apply_theme()

        assert rail._section_labels == []
    finally:
        rail.close()


def test_workbench_navigation_and_execution_controller_sources_keep_readable_copy():
    navigation_source = (ROOT / "src/ui/panels/workbench/navigation_controller.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "src/ui/panels/workbench/execution_controller.py").read_text(encoding="utf-8")
    feedback_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_feedback_mixin.py"
    ).read_text(encoding="utf-8")
    result_presenter_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_result_presenter.py"
    ).read_text(encoding="utf-8")

    assert "??" not in navigation_source
    assert "??" not in execution_source
    assert "高级功能" in navigation_source
    assert "execution_history" not in navigation_source
    assert "execution_history" not in execution_source
    assert "build_execution_result_presentation" in feedback_source
    assert "✓ 本次生成完成" in result_presenter_source
