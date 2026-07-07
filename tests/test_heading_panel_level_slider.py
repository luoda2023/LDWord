import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(TemplateConfig())
    panel.show()
    app.processEvents()
    return app, panel


def test_heading_numbering_panel_uses_spacing_input_for_max_levels_control():
    app, panel = _build_panel()

    try:
        assert isinstance(panel._levels_input, SpacingInput)
        assert isinstance(panel._levels_slider, StyledSpinBox)
        assert panel._levels_slider.minimum() == 1
        assert panel._levels_slider.maximum() == 8
        assert panel._levels_slider.value() == 4
        assert panel._levels_input.value() == 4
        assert panel.panel_icon == "list-ordered"
        assert panel._summary_card.header._icon_name == "list-ordered"
        summary_items = panel._summary_grid.items()
        assert panel._summary_grid._tile_style == "module"
        assert summary_items[0].icon_name == "settings"
        assert summary_items[1].icon_name == "sliders-horizontal"
        assert {item.icon_name for item in summary_items[2:]} == {"list-ordered"}
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_panel_level_slider_updates_adapter_and_preview_rows():
    app, panel = _build_panel()

    try:
        panel._levels_input.set_value(6, "")
        panel._on_levels_changed()
        app.processEvents()

        assert panel._adapter.max_levels == 6
        assert panel._adv_list.count() == 6
        assert panel._levels_input.value() == 6
    finally:
        panel.close()
        app.processEvents()
