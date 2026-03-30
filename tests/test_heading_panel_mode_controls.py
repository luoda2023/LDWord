import sys
from pathlib import Path

from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication, Qt
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(TemplateConfig())
    panel.show()
    app.processEvents()
    return app, panel


def test_heading_numbering_panel_uses_themed_radio_buttons_for_mode_switching():
    app, panel = _build_panel()
    radios = panel.findChildren(ThemedRadioButton)
    texts = {radio.text() for radio in radios}

    assert "快速应用" in texts
    assert "自定义多级列表" in texts
    assert len(radios) >= 2

    panel.close()
    app.processEvents()


def test_heading_numbering_panel_mode_radios_switch_stack_views():
    app, panel = _build_panel()
    radios = {radio.text(): radio for radio in panel.findChildren(ThemedRadioButton)}

    assert panel._stack.currentWidget() is panel._simple_widget

    QTest.mouseClick(radios["自定义多级列表"], Qt.LeftButton)
    app.processEvents()
    assert panel._stack.currentWidget() is panel._advanced_widget

    QTest.mouseClick(radios["快速应用"], Qt.LeftButton)
    app.processEvents()
    assert panel._stack.currentWidget() is panel._simple_widget

    panel.close()
    app.processEvents()
