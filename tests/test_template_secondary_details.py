import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_table_and_elements_details_reuse_shared_controls():
    table_source = (ROOT / "src/ui/panels/template_table_detail.py").read_text(encoding="utf-8")
    elements_source = (ROOT / "src/ui/panels/template_elements_detail.py").read_text(encoding="utf-8")

    assert "StyledComboBox(" in table_source
    assert "ToggleSwitch(" in table_source
    assert "StyledComboBox(" in elements_source
    assert "ToggleSwitch(" in elements_source


def test_template_panel_table_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._table_detail._border_combo.setCurrentIndex(1)
        app.processEvents()

        assert panel._current_template.table.border_mode == "full_grid"
        assert "全框线" in panel._overview_detail._rows["table"]._value.text()
        assert "全框线" in panel._nav_cards["tpl_table"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_elements_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._elements_detail._toc_enabled_toggle.click()
        app.processEvents()

        assert panel._current_template.toc.enabled is False
        assert "目录关闭" in panel._overview_detail._rows["elements"]._value.text()
        assert "目录关闭" in panel._nav_cards["tpl_elements"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()
