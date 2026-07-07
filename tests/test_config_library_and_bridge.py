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
    list_template_entries,
    list_scene_descriptors,
    load_scene_from_library,
)
from src.config.builtin_templates import create_builtin_template
from src.config.loader import save_template
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


def test_config_library_seeds_only_default_and_thesis_templates(monkeypatch):
    import src.config.library as library

    root = Path(tempfile.mkdtemp())
    template_dir = root / "templates"
    scene_dir = root / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)

    template_dir.mkdir(parents=True)
    (template_dir / "bid_engineering.json").write_text("{}", encoding="utf-8")
    (template_dir / "my_custom_template.json").write_text("{}", encoding="utf-8")

    ensure_config_library()

    assert sorted(path.name for path in template_dir.glob("*.json")) == [
        "default.json",
        "my_custom_template.json",
        "thesis_gbt.json",
    ]


def test_template_entries_ignore_obsolete_templates_when_prune_is_blocked(monkeypatch):
    import src.config.library as library

    root = Path(tempfile.mkdtemp())
    template_dir = root / "templates"
    scene_dir = root / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)
    template_dir.mkdir(parents=True)
    save_template(
        create_builtin_template("bid_engineering"),
        template_dir / "bid_engineering.json",
    )

    original_unlink = Path.unlink

    def _locked_unlink(self, *args, **kwargs):
        if self.name == "bid_engineering.json":
            raise PermissionError("locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _locked_unlink)

    ensure_config_library()

    assert (template_dir / "bid_engineering.json").exists()
    assert {entry.config_id for entry in list_template_entries()} == {
        "default",
        "thesis_gbt",
    }


def test_scene_descriptors_are_library_backed_and_keep_builtin_order():
    ensure_config_library()

    descriptors = list_scene_descriptors()
    builtin_ids = {"custom", "exam", "thesis", "bidding", "official", "technical", "report"}
    builtin_descriptors = [
        descriptor for descriptor in descriptors if descriptor.config_id in builtin_ids
    ]

    assert [descriptor.config_id for descriptor in builtin_descriptors[:4]] == ["custom", "exam", "thesis", "bidding"]
    assert builtin_descriptors[0].scene_id == "custom"
    assert builtin_descriptors[0].display_name == "通用-默认"
    assert builtin_descriptors[0].path.exists()
    exam = next(descriptor for descriptor in descriptors if descriptor.config_id == "exam")
    assert exam.display_name == "试卷-默认"
    thesis = next(descriptor for descriptor in descriptors if descriptor.config_id == "thesis")
    assert thesis.description == "中文学位论文·课程论文·综述·开题"
    assert "期刊论文" not in thesis.description


def test_scene_descriptors_put_user_scenes_before_builtin_scenes(monkeypatch):
    import src.config.library as library

    root = Path(tempfile.mkdtemp())
    template_dir = root / "templates"
    scene_dir = root / "scenes"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_dir)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_dir)

    ensure_config_library()
    scene = SceneWorkspace(
        scene_id="exam_default_copy",
        name="试卷-期中",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    library.save_scene_to_library(scene, scene_id="exam_default_copy")

    descriptors = list_scene_descriptors()
    builtin_ids = {"custom", "exam", "thesis", "bidding", "official", "technical", "report"}

    assert descriptors[0].config_id == "exam_default_copy"
    assert descriptors[0].display_name == "试卷-期中"
    assert next(
        index for index, descriptor in enumerate(descriptors)
        if descriptor.config_id in builtin_ids
    ) > 0


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

        thesis_index = panel._quick_execution_detail._scene_combo.findData("thesis")
        assert thesis_index >= 0
        panel._quick_execution_detail._scene_combo.setCurrentIndex(thesis_index)
        app.processEvents()

        assert bridge.current_scene_id() == "thesis"
        assert bridge.current_template_id() == "thesis_gbt"
    finally:
        panel.close()
        app.processEvents()


def test_workbench_syncs_external_template_id_to_quick_execution():
    app = _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        template = TemplateConfig(name="Custom Saved Template")
        bridge.set_current_template(
            template,
            config_id="custom_saved",
            path="C:/tmp/custom_saved.json",
            source="file",
        )
        app.processEvents()

        detail = panel._quick_execution_detail

        assert bridge.current_template_id() == "custom_saved"
        assert detail.current_template_id() == "custom_saved"
        assert detail.current_scene().template_id == "custom_saved"
        assert "custom_saved" in detail.current_scene().compatible_template_ids
        assert any(
            detail._template_combo.itemText(index) == "Custom Saved Template"
            and detail._template_combo.itemData(index) == "custom_saved"
            for index in range(detail._template_combo.count())
        )
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
