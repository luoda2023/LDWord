import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


_PRESET_KEY = "thesis_standard"


def _app():
    return QApplication.instance() or QApplication([])


def _select_builtin_preset(panel: HeadingNumberingPanel) -> None:
    for index in range(panel._preset_cb.count()):
        if panel._preset_cb.itemData(index) == _PRESET_KEY:
            panel._preset_cb.setCurrentIndex(index)
            return
    raise AssertionError("built-in preset not found")


def test_panel_bridge_tracks_template_dirty_state_without_duplicate_emits():
    bridge = PanelBridge()
    seen: list[bool] = []
    bridge.template_dirty_changed.connect(seen.append)

    assert bridge.is_template_dirty() is False

    bridge.mark_template_dirty()
    bridge.mark_template_dirty()
    assert bridge.is_template_dirty() is True
    assert seen == [True]

    bridge.clear_template_dirty()
    bridge.clear_template_dirty()
    assert bridge.is_template_dirty() is False
    assert seen == [True, False]


def test_heading_numbering_detail_emits_edit_without_owning_bridge_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = HeadingNumberingPanel(bridge)
    emitted = []
    panel.template_edited.connect(emitted.append)
    try:
        panel.on_template_changed(TemplateConfig())
        _select_builtin_preset(panel)
        app.processEvents()

        panel.capture_entry_snapshot()
        bridge.clear_template_dirty()
        app.processEvents()

        assert bridge.is_template_dirty() is False

        # Trigger a real edit through panel handler (which calls _mark_dirty)
        panel._levels_input.set_value(6, "")
        panel._on_levels_changed()
        app.processEvents()

        assert bridge.is_template_dirty() is False
        assert emitted
    finally:
        panel.close()
        app.processEvents()
