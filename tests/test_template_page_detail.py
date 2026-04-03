import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_page_setup_detail_syncs_widget_values_from_template():
    _app()
    detail = PageSetupDetail()
    template = TemplateConfig()
    template.page_setup.paper_size = "A3"
    template.page_setup.margin.top_cm = 2.5
    template.page_setup.gutter_cm = 0.8
    template.page_setup.header_distance_cm = 1.6

    try:
        detail.set_template(template)

        assert detail._paper_combo.currentData() == "A3"
        assert detail._page_inputs["top_cm"].value() == 2.5
        assert detail._page_inputs["gutter_cm"].value() == 0.8
        assert detail._page_inputs["header_distance_cm"].value() == 1.6
    finally:
        detail.close()


def test_template_panel_page_setup_edit_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    emitted: list[TemplateConfig] = []
    bridge.template_changed.connect(emitted.append)

    try:
        panel._page_detail._page_inputs["top_cm"].set_value(4.5, "cm")
        app.processEvents()

        assert panel._current_template.page_setup.margin.top_cm == 4.5
        assert "4.5" in panel._overview_detail._rows["page"]._value.text()
        assert "4.5" in panel._nav_cards["tpl_page"]._full_subtitle
        assert bridge.is_template_dirty() is True
        assert emitted
        assert emitted[-1].page_setup.margin.top_cm == 4.5
    finally:
        panel.close()
        app.processEvents()


def test_page_setup_detail_reuses_shared_spacing_input_control():
    source = (ROOT / "src/ui/panels/template_page_detail.py").read_text(encoding="utf-8")

    assert "SpacingInput(" in source
    assert "QDoubleSpinBox(" not in source
