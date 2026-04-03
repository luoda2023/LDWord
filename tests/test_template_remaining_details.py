import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_panel import TemplatePanel


def _app():
    return QApplication.instance() or QApplication([])


def test_formula_reference_and_other_details_reuse_shared_controls():
    formula_source = (ROOT / "src/ui/panels/template_formula_detail.py").read_text(encoding="utf-8")
    reference_source = (ROOT / "src/ui/panels/template_reference_detail.py").read_text(encoding="utf-8")
    other_source = (ROOT / "src/ui/panels/template_other_detail.py").read_text(encoding="utf-8")

    assert "FontCombo(" in formula_source
    assert "SizeCombo(" in formula_source
    assert "ToggleSwitch(" in formula_source
    assert "FontCombo(" in reference_source
    assert "SpacingInput(" in reference_source
    assert "ToggleSwitch(" in other_source


def test_template_panel_formula_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._formula_detail._unify_font.click()
        app.processEvents()

        assert panel._current_template.formula_style.unify_font is False
        assert "统一字号/统一间距" in panel._overview_detail._rows["formula"]._value.text()
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_reference_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._reference_detail._hanging_indent.set_value(1.2, "cm")
        app.processEvents()

        assert panel._current_template.reference_style.hanging_indent_cm == 1.2
        assert "1.2cm" in panel._overview_detail._rows["reference"]._value.text()
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_other_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._other_detail._watermark_toggle.click()
        app.processEvents()

        assert panel._current_template.watermark.enabled is True
        assert "水印" in panel._overview_detail._rows["other"]._value.text()
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()
