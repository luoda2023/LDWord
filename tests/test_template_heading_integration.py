import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_heading_detail_updates_heading_preview_summary_when_levels_change():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        before = panel._nav_cards["tpl_heading"]._full_subtitle

        panel._heading_detail._levels_slider.setValue(3)
        app.processEvents()

        after = panel._nav_cards["tpl_heading"]._full_subtitle

        assert panel._current_template.heading_model.max_heading_levels == 3
        assert before != after
        assert "3" in after
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()
