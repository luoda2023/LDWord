import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_template_panel_source_text_uses_file_status_language():
    _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._current_template_source = "library"
        panel._current_template_path = str(ROOT / "templates" / "thesis_gbt.json")
        assert panel._template_source_text() == "模板文件：thesis_gbt.json"
        assert panel._template_overview_status_text() == "模板文件"
        assert panel._template_path_status_text() == f"保存位置：{ROOT / 'templates'}"
        assert panel._template_path_tooltip() == str(ROOT / "templates" / "thesis_gbt.json")

        panel._current_template_source = "file"
        assert panel._template_source_text() == "本地文件：thesis_gbt.json"
        assert panel._template_overview_status_text() == "本地文件"

        panel._current_template_source = "builtin"
        panel._current_template_path = ""
        assert panel._template_source_text() == "模板类型：内置模板"
        assert panel._template_overview_status_text() == "内置模板"

        panel._current_template_source = ""
        assert panel._template_source_text() == "未保存到模板文件"
        assert panel._template_overview_status_text() == "未保存"
        assert panel._template_path_status_text() == "保存位置：未保存到文件"
        assert panel._template_path_tooltip() == "当前模板还没有保存到文件"
    finally:
        panel.close()


def test_template_panel_module_source_has_no_middle_dot_template_origin_labels():
    source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")

    assert "模板库 ·" not in source
    assert "文件 ·" not in source
    assert "导入文件 ·" not in source
    assert "来源:" not in source
    assert "导入或另存模板配置。" not in source


def test_template_panel_syncs_file_status_to_overview():
    _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._current_template_source = "file"
        panel._current_template_path = str(ROOT / "templates" / "custom_style.json")
        panel._sync_template_file_status()

        assert panel._overview_detail._status_chip.text() == "本地文件"
        assert panel._overview_detail._status_chip.objectName() == "tpl_overview_status_chip"
        assert panel._template_source_text() == "本地文件：custom_style.json"
        assert panel._template_path_status_text() == f"保存位置：{ROOT / 'templates'}"
        assert panel._template_path_tooltip() == str(ROOT / "templates" / "custom_style.json")

        panel._current_template_source = ""
        panel._current_template_path = ""
        panel._sync_template_file_status()

        assert panel._overview_detail._status_chip.text() == "未保存"
        assert panel._template_source_text() == "未保存到模板文件"
        assert panel._template_path_status_text() == "保存位置：未保存到文件"
        assert panel._template_path_tooltip() == "当前模板还没有保存到文件"
    finally:
        panel.close()


def test_template_panel_dirty_status_distinguishes_preview_from_execution():
    _app()
    panel = TemplatePanel(PanelBridge())
    try:
        panel._current_template.name = "Draft only"
        panel._on_template_edited(panel._current_template)

        status = panel._template_overview_status_text()
        assert "草稿预览" in status
        assert "执行仍使用已保存版本" in status
    finally:
        panel.close()


def test_template_panel_tracks_save_status_without_import_export_detail():
    _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        assert not hasattr(panel, "_io_detail")
        assert bridge.is_template_dirty() is False

        bridge.mark_template_dirty()

        assert bridge.is_template_dirty() is True

        bridge.clear_template_dirty()

        assert bridge.is_template_dirty() is False
    finally:
        panel.close()
