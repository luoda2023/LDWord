import sys
import tempfile
import logging
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.library import (
    default_scene_entry,
    default_scene_descriptor,
    default_template_entry,
    ensure_config_library,
    get_scene_descriptor,
    list_scene_descriptors,
    load_scene_from_library,
)
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_config_library_seeds_default_scene_and_template_entries():
    ensure_config_library()

    template_entry = default_template_entry()
    scene_entry = default_scene_entry()

    assert template_entry is not None
    assert template_entry.path.exists()
    assert scene_entry is not None
    assert scene_entry.path.exists()

    scene = load_scene_from_library(scene_entry.config_id)
    assert scene.scene_id == scene_entry.config_id
    assert scene.template_id
    assert scene.template_id in scene.compatible_template_ids


def test_scene_descriptors_are_library_backed_and_keep_builtin_order():
    ensure_config_library()

    descriptors = list_scene_descriptors()

    assert [descriptor.config_id for descriptor in descriptors[:3]] == ["custom", "thesis", "bidding"]
    assert descriptors[0].scene_id == "custom"
    assert descriptors[0].path.exists()


def test_scene_descriptors_keep_broken_scene_visible_with_error(monkeypatch):
    import src.config.library as library

    root = Path(tempfile.mkdtemp())
    template_dir = root / "templates"
    scene_dir = root / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)

    ensure_config_library()
    broken_path = scene_dir / "broken_scene.json"
    broken_path.write_text("{not-valid-json", encoding="utf-8")

    descriptors = list_scene_descriptors()
    broken = next(descriptor for descriptor in descriptors if descriptor.config_id == "broken_scene")

    assert broken.is_available is False
    assert broken.load_error
    assert "Unavailable" in broken.display_name

    fetched = get_scene_descriptor("broken_scene")
    assert fetched is not None
    assert fetched.is_available is False

    default_descriptor = default_scene_descriptor()
    assert default_descriptor is not None
    assert default_descriptor.is_available is True


def test_load_scene_from_library_raises_for_broken_scene_file(monkeypatch):
    import pytest
    import src.config.library as library

    root = Path(tempfile.mkdtemp())
    template_dir = root / "templates"
    scene_dir = root / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)

    ensure_config_library()
    broken_path = scene_dir / "broken_scene.json"
    broken_path.write_text("{not-valid-json", encoding="utf-8")

    with pytest.raises(Exception):
        load_scene_from_library("broken_scene")


def test_panel_bridge_tracks_scene_and_template_context_metadata():
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom", template_id="default")
    template = TemplateConfig(name="Default Template")

    seen_scenes = []
    seen_templates = []
    bridge.scene_changed.connect(seen_scenes.append)
    bridge.template_changed.connect(seen_templates.append)

    bridge.set_current_scene(
        scene,
        config_id="custom",
        path="C:/configs/scenes/custom.json",
        source="library",
    )
    bridge.set_current_template(
        template,
        config_id="default",
        path="C:/configs/templates/default.json",
        source="library",
    )

    assert bridge.current_scene() is scene
    assert bridge.current_scene_id() == "custom"
    assert bridge.current_scene_path().endswith("custom.json")
    assert bridge.current_scene_source() == "library"
    assert bridge.current_template() is template
    assert bridge.current_template_id() == "default"
    assert bridge.current_template_path().endswith("default.json")
    assert bridge.current_template_source() == "library"
    assert seen_scenes == [scene]
    assert seen_templates == [template]


def test_workbench_bootstraps_and_updates_bridge_binding_from_quick_execution():
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        assert bridge.current_scene() is not None
        assert bridge.current_template() is not None
        assert bridge.current_scene_id() == panel._quick_execution_detail.current_scene_id()
        assert bridge.current_template_id() == panel._quick_execution_detail.current_template_id()

        panel._quick_execution_detail._scene_combo.setCurrentIndex(1)
        app.processEvents()

        assert bridge.current_scene_id() == "thesis"
        assert bridge.current_template_id() == "thesis_gbt"
    finally:
        panel.close()
        app.processEvents()


def test_workbench_logs_template_binding_load_failures_without_overwriting_bridge_template(
    monkeypatch,
    caplog,
):
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        import src.ui.panels.workbench.panel_v2 as panel_v2

        original_template = bridge.current_template()
        original_template_id = bridge.current_template_id()

        def _raise_template_load(_template_id: str):
            raise RuntimeError("broken template")

        monkeypatch.setattr(panel_v2, "load_template_from_library", _raise_template_load)

        with caplog.at_level(logging.WARNING):
            panel._on_quick_binding_changed(panel._current_scene, original_template_id)

        assert bridge.current_template() is original_template
        assert bridge.current_template_id() == original_template_id
        assert any(
            "quick binding ignored template load failure" in record.getMessage()
            for record in caplog.records
        )
    finally:
        panel.close()
        app.processEvents()
