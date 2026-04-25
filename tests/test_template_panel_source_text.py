import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_template_panel_source_text_avoids_middle_dot_separator_for_file_backed_templates():
    _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel._current_template_source = "library"
        panel._current_template_path = str(ROOT / "templates" / "thesis_gbt.json")
        assert panel._template_source_text() == "来源: 模板库（thesis_gbt.json）"

        panel._current_template_source = "file"
        assert panel._template_source_text() == "来源: 文件（thesis_gbt.json）"
    finally:
        panel.close()


def test_template_panel_module_source_has_no_middle_dot_template_origin_labels():
    source = (ROOT / "src/ui/panels/template_panel.py").read_text(encoding="utf-8")

    assert "模板库 ·" not in source
    assert "文件 ·" not in source
    assert "导入文件 ·" not in source
