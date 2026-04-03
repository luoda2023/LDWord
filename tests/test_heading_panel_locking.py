import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication, QCheckBox
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


_PRESET_KEY = "thesis_standard"


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(TemplateConfig())
    panel.show()
    app.processEvents()
    return app, panel


def _select_builtin_preset(panel: HeadingNumberingPanel) -> None:
    for index in range(panel._preset_cb.count()):
        data = panel._preset_cb.itemData(index)
        if data == _PRESET_KEY:
            panel._preset_cb.setCurrentIndex(index)
            return
    raise AssertionError("built-in preset not found")


def _select_custom_mode(panel: HeadingNumberingPanel) -> None:
    for index in range(panel._preset_cb.count()):
        if panel._preset_cb.itemData(index) == "__custom__":
            panel._preset_cb.setCurrentIndex(index)
            return
    raise AssertionError("custom preset entry not found")


def _first_advanced_level_toggle(panel: HeadingNumberingPanel) -> QCheckBox:
    panel._switch_mode(1)
    item = panel._adv_list.item(0)
    widget = panel._adv_list.itemWidget(item)
    if widget is None:
        raise AssertionError("advanced row widget missing")
    for checkbox in widget.findChildren(QCheckBox):
        if checkbox.property("heading_level_toggle"):
            return checkbox
    raise AssertionError("heading level toggle not found")


def test_heading_numbering_adapter_detects_preset_mismatch_for_enabled_and_toc_flags():
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())

    adapter.apply_preset(_PRESET_KEY)
    assert adapter.detect_active_preset() == _PRESET_KEY

    adapter.set_binding_field(1, "enabled", False)
    assert adapter.detect_active_preset() is None

    adapter.apply_preset(_PRESET_KEY)
    assert adapter.detect_active_preset() == _PRESET_KEY

    adapter.set_binding_field(1, "include_in_toc", False)
    assert adapter.detect_active_preset() is None


def test_heading_numbering_adapter_detects_preset_mismatch_when_visible_levels_expand_beyond_preset():
    adapter = HeadingNumberingAdapter()
    adapter.set_template(TemplateConfig())

    adapter.apply_preset(_PRESET_KEY)
    assert adapter.detect_active_preset() == _PRESET_KEY

    adapter.set_max_levels(6)
    assert adapter.detect_active_preset() is None


def test_heading_numbering_panel_locks_advanced_level_toggles_until_custom_mode():
    app, panel = _build_panel()

    _select_builtin_preset(panel)
    app.processEvents()

    toggle = _first_advanced_level_toggle(panel)
    assert toggle.isEnabled() is False
    before = panel._adapter.get_binding(1).enabled
    toggle.click()
    app.processEvents()
    assert panel._adapter.get_binding(1).enabled is before

    _select_custom_mode(panel)
    app.processEvents()

    toggle = _first_advanced_level_toggle(panel)
    assert toggle.isEnabled() is True

    panel.close()
    app.processEvents()


def test_heading_numbering_panel_switches_to_custom_mode_after_toc_edit_from_preset():
    app, panel = _build_panel()

    _select_builtin_preset(panel)
    app.processEvents()

    assert panel._is_custom_mode is False
    assert panel._prefix_edit.isEnabled() is False

    toc_checkbox = panel._simple_rows[0]["checkbox"]
    toc_checkbox.click()
    app.processEvents()

    assert panel._is_custom_mode is True
    assert panel._preset_cb.currentData() == "__custom__"
    assert panel._prefix_edit.isEnabled() is True

    panel.close()
    app.processEvents()


def test_heading_numbering_panel_switches_to_custom_mode_after_level_count_edit():
    app, panel = _build_panel()

    _select_builtin_preset(panel)
    app.processEvents()

    panel._levels_slider.setValue(6)
    app.processEvents()

    assert panel._is_custom_mode is True
    assert panel._preset_cb.currentData() == "__custom__"
    assert panel._prefix_edit.isEnabled() is True

    panel.close()
    app.processEvents()
