import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.workbench import WorkbenchPanel
from src.config.loader import load_scene, load_template


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

        panel.capture_entry_snapshot()
        bridge.clear_template_dirty()
        app.processEvents()

        assert bridge.is_template_dirty() is False

        # Trigger a real edit through panel handler (which calls _mark_dirty)
        panel._levels_input.set_value(6, "")
        panel._on_levels_changed()
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


def test_workbench_panel_reflects_scene_dirty_state_in_config_management_card():
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        scene = load_scene(ROOT / "scenes" / "custom.json")
        bridge.set_current_scene(scene, config_id="custom", path=str(ROOT / "scenes" / "custom.json"), source="library")
        app.processEvents()

        bridge.mark_scene_dirty()
        app.processEvents()

        assert panel._scene_dirty is True
        assert panel._config_management_detail.is_scene_dirty() is True

        snapshot = panel._config_management_detail.navigation_snapshot()
        assert snapshot["badge_variant"] == "warning"
        assert "未保存" in snapshot["badge_text"]

        nav_card = panel._navigation_cards["config_management"]
        assert nav_card._badge.variant() == "warning"
        assert nav_card._badge.text()
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


def test_config_management_template_save_as_updates_current_template_id(tmp_path):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        template = TemplateConfig(name="Custom Saved Template")
        original_path = tmp_path / "default.json"
        bridge.set_current_template(
            template,
            config_id="default",
            path=str(original_path),
            source="library",
        )
        bridge.mark_template_dirty()
        app.processEvents()

        target = tmp_path / "custom_saved.json"
        saved = panel._config_management_detail.save_current_template_to_path(target)
        app.processEvents()

        assert saved == target
        assert bridge.current_template_id() == "custom_saved"
        assert panel._config_management_detail._template_export_section._template_id == "custom_saved"
        assert panel._quick_execution_detail.current_template_id() == "custom_saved"
        assert panel._quick_execution_detail.current_scene().template_id == "custom_saved"
    finally:
        panel.close()
        app.processEvents()


def test_config_management_detail_can_save_current_scene_and_clear_dirty(tmp_path):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        scene = load_scene(ROOT / "scenes" / "custom.json")
        bridge.set_current_scene(scene, config_id="custom", path=str(ROOT / "scenes" / "custom.json"), source="library")
        bridge.mark_scene_dirty()
        app.processEvents()

        target = tmp_path / "custom_scene.json"
        saved = panel._config_management_detail.save_current_scene_to_path(target)
        app.processEvents()

        assert saved == target
        assert target.exists()
        assert bridge.is_scene_dirty() is False
        assert panel._scene_dirty is False
        assert panel._config_management_detail.is_scene_dirty() is False
    finally:
        panel.close()
        app.processEvents()


def test_config_management_detail_logs_scene_id_sync_failures_after_save(monkeypatch, tmp_path, caplog):
    import src.ui.panels.workbench.config_management_detail as detail_module

    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        target = tmp_path / "exported_scene.json"

        class _SceneWithFailingId:
            def __init__(self) -> None:
                self.name = "Broken Scene"
                self._scene_id = "custom"

            @property
            def scene_id(self) -> str:
                return self._scene_id

            @scene_id.setter
            def scene_id(self, value: str) -> None:
                raise RuntimeError(f"cannot set scene id to {value}")

        scene = _SceneWithFailingId()
        bridge.set_current_scene(scene, config_id="custom", path="", source="builtin")
        bridge.mark_scene_dirty()
        panel._config_management_detail.set_current_scene(scene)
        app.processEvents()

        def _save_scene_stub(current_scene, path):
            Path(path).write_text("{}", encoding="utf-8")
            return Path(path)

        monkeypatch.setattr(detail_module, "save_scene", _save_scene_stub)

        with caplog.at_level(logging.WARNING):
            saved = panel._config_management_detail.save_current_scene_to_path(target)
            app.processEvents()

        assert saved == target
        assert target.exists()
        assert bridge.is_scene_dirty() is False
        assert bridge.current_scene() is scene
        assert bridge.current_scene_id() == "custom"
        assert any(
            "scene export section" in record.getMessage()
            and "scene_id assignment" in record.getMessage()
            for record in caplog.records
        )
    finally:
        panel.close()
        app.processEvents()
