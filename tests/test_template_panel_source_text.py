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


def test_template_panel_syncs_file_status_to_import_export_detail():
    _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._current_template_source = "file"
        panel._current_template_path = str(ROOT / "templates" / "custom_style.json")
        panel._sync_template_file_status()

        assert panel._overview_detail._status_chip.text() == "本地文件"
        assert panel._overview_detail._status_chip.objectName() == "tpl_overview_status_chip"
        assert panel._io_detail._file_state.text() == "本地文件：custom_style.json"
        assert panel._io_detail._path_state.text() == f"保存位置：{ROOT / 'templates'}"
        assert panel._io_detail._path_state.toolTip() == str(ROOT / "templates" / "custom_style.json")
        assert panel._io_detail._path_state.objectName() == "tpl_io_path_state"

        panel._current_template_source = ""
        panel._current_template_path = ""
        panel._sync_template_file_status()

        assert panel._overview_detail._status_chip.text() == "未保存"
        assert panel._io_detail._file_state.text() == "未保存到模板文件"
        assert panel._io_detail._path_state.text() == "保存位置：未保存到文件"
        assert panel._io_detail._path_state.toolTip() == "当前模板还没有保存到文件"
    finally:
        panel.close()


def test_template_panel_import_export_detail_shows_save_status():
    _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        assert panel._io_detail._save_state.text() == "保存状态：已保存"

        bridge.mark_template_dirty()

        assert panel._io_detail._save_state.text() == "保存状态：有未保存更改"

        bridge.clear_template_dirty()

        assert panel._io_detail._save_state.text() == "保存状态：已保存"
    finally:
        panel.close()
