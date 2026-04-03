import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.workbench import WorkbenchPanel
from src.config.loader import load_template


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


def test_heading_numbering_panel_marks_bridge_dirty_after_user_edit():
    app = _app()
    bridge = PanelBridge()
    panel = HeadingNumberingPanel(bridge)
    try:
        panel.on_template_changed(TemplateConfig())
        _select_builtin_preset(panel)
        app.processEvents()

        assert bridge.is_template_dirty() is False

        panel._simple_rows[0]["checkbox"].click()
        app.processEvents()

        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_workbench_panel_reflects_template_dirty_state_in_config_management_card():
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        bridge.template_changed.emit(TemplateConfig(name="Thesis Template"))
        app.processEvents()

        bridge.mark_template_dirty()
        app.processEvents()

        assert panel._template_dirty is True
        assert panel._config_management_detail.is_template_dirty() is True

        snapshot = panel._config_management_detail.navigation_snapshot()
        assert snapshot["badge_variant"] == "warning"
        assert "Thesis Template" in snapshot["subtitle"]

        nav_card = panel._navigation_cards["config_management"]
        assert nav_card._badge.variant() == "warning"
        assert nav_card._badge.text()

        bridge.template_changed.emit(TemplateConfig(name="Fresh Template"))
        app.processEvents()

        assert bridge.is_template_dirty() is False
        assert panel._template_dirty is False
        assert panel._config_management_detail.is_template_dirty() is False
    finally:
        panel.close()
        app.processEvents()


def test_config_management_detail_can_save_current_template_and_clear_dirty(tmp_path):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        template = TemplateConfig(name="Thesis Template")
        bridge.template_changed.emit(template)
        bridge.mark_template_dirty()
        app.processEvents()

        target = tmp_path / "thesis_template.json"
        saved = panel._config_management_detail.save_current_template_to_path(target)
        app.processEvents()

        assert saved == target
        assert target.exists()
        assert bridge.is_template_dirty() is False
        assert panel._template_dirty is False
        assert panel._config_management_detail.is_template_dirty() is False
        assert "thesis_template.json" in panel._config_management_detail._template_export_status.text()

        reloaded = load_template(target)
        assert reloaded.name == "Thesis Template"
    finally:
        panel.close()
        app.processEvents()
