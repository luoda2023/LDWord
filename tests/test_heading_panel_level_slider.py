import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.shared.ui.themed_slider import ThemedSlider
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(TemplateConfig())
    panel.show()
    app.processEvents()
    return app, panel


def test_heading_numbering_panel_uses_themed_slider_for_max_levels_control():
    app, panel = _build_panel()

    assert isinstance(panel._levels_slider, ThemedSlider)
    assert panel._levels_slider.minimum() == 1
    assert panel._levels_slider.maximum() == 8
    assert panel._levels_slider.value() == 4
    assert panel._levels_value_label.text() == "4 级"

    panel.close()
    app.processEvents()


def test_heading_numbering_panel_level_slider_updates_adapter_and_preview_rows():
    app, panel = _build_panel()

    panel._levels_slider.setValue(6)
    app.processEvents()

    assert panel._adapter.max_levels == 6
    assert len(panel._simple_rows) == 6
    assert panel._levels_value_label.text() == "6 级"

    panel.close()
    app.processEvents()
