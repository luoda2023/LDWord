import json

import pytest

from src.config import library as config_library
from src.config import material_package_library

from src.shared.ui.styled_combo_box import StyledComboBox
from src.qt_api import QMainWindow
from src.ui.bridge import PanelBridge
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow as _ProductMainWindow
from src.ui.panel_registry import PANEL_SPECS
from src.ui.panels import scene_session_coordinator as scene_session_module
from src.ui.panels.template_panel import TemplatePanel
from src.ui.title_bar import TitleBar


class MainWindow(_ProductMainWindow):
    """Exercise source-only optional panels in the legacy integration suite."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("include_optional_panels", True)
        super().__init__(*args, **kwargs)


@pytest.fixture(autouse=True)
def _isolate_title_bar_config_library(tmp_path, monkeypatch):
    root = tmp_path / "config_library"
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", root / "plans")
    monkeypatch.setattr(config_library, "TEMPLATE_LIBRARY_DIR", root / "templates")
    config_library.ensure_config_library()


def _load_assets_panel(window):
    assets_index = next(
        index
        for index, spec in enumerate(window._panel_specs)
        if spec.id == "assets"
    )
    return window._show_panel(assets_index, allow_async=False)


def _edit_material_field(panel, value: str = "Acme") -> None:
    archive = panel.current_archive()
    archive.profiles[0].fields["company_name"] = value
    panel.set_archive(archive)
    assert panel.has_pending_material_changes() is True


def _saved_material_packages(tmp_path):
    del tmp_path
    root = material_package_library.MATERIAL_PACKAGE_LIBRARY_DIR
    return sorted(root.glob("*/user/*/package.json")) if root.exists() else []


def _prepare_builtin_scene_save_as(window, monkeypatch, name: str):
    panel = window._ensure_panel_loaded_for_id("scene")
    monkeypatch.setattr(panel, "_prompt_scene_save_as_name", lambda _reason="": name)
    return panel


def _close_test_window(window, qapp) -> None:
    """End mode tests without opening the production pending-edit dialogs."""

    window.bridge.clear_scene_dirty()
    assets = window._loaded_panel_for_id("assets")
    if assets is not None and assets.has_pending_material_changes():
        assets._capture_material_persistence_snapshot()
    window.close()
    qapp.processEvents()


def test_title_bar_projects_bridge_work_mode(qapp):
    window = QMainWindow()
    bridge = PanelBridge()
    title_bar = TitleBar(window, bridge=bridge)
    combo = title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")

    assert combo is not None
    assert combo.property("titlebarMode") == "true"
    assert combo.minimumSize().width() == 128
    assert combo.maximumSize().height() == 28
    assert combo.currentData() == "custom"
    assert combo.currentText() == "通用版"

    bridge.set_current_work_mode("exam")

    assert combo.currentData() == "exam"
    assert combo.currentText() == "试卷版"


def test_title_bar_work_mode_combo_updates_bridge_without_scene_switch(qapp):
    window = QMainWindow()
    bridge = PanelBridge()
    title_bar = TitleBar(window, bridge=bridge)
    combo = title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
    seen_modes = []
    seen_scenes = []
    seen_templates = []
    bridge.work_mode_changed.connect(seen_modes.append)
    bridge.scene_changed.connect(seen_scenes.append)
    bridge.template_changed.connect(seen_templates.append)

    combo.setCurrentIndex(combo.findData("official"))
    qapp.processEvents()

    assert bridge.current_work_mode_id() == "official"
    assert [mode.mode_id for mode in seen_modes] == ["official"]
    assert seen_scenes == []
    assert seen_templates == []


def test_main_window_work_mode_switch_loads_mode_default_scene_and_template(qapp):
    window = MainWindow()
    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        seen_scenes = []
        seen_templates = []
        window.bridge.scene_changed.connect(seen_scenes.append)
        window.bridge.template_changed.connect(seen_templates.append)

        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "official"
        assert window.bridge.current_scene_id() == "official"
        assert window.bridge.current_template_id() == "official_gbt"
        assert window.bridge.current_scene_source() == "library"
        assert window.bridge.current_scene_source_type() == "builtin"
        assert window.bridge.current_template_source() == "library"
        assert window.bridge.current_template_source_type() == "builtin"
        assert "config_library" in window.bridge.current_template_path()
        assert "official" in window.bridge.current_template_path()
        assert window.bridge.current_scene().template_id == "official_gbt"
        assert "official_gbt" in window.bridge.current_scene().compatible_template_ids
        assert [getattr(scene, "scene_id", "") for scene in seen_scenes] == ["official"]
        assert len(seen_templates) == 1
    finally:
        _close_test_window(window, qapp)


def test_main_window_rejects_same_id_user_plan_and_keeps_builtin_origin(
    qapp,
    tmp_path,
    monkeypatch,
):
    import src.config.library as library
    from src.config.scene import SceneWorkspace

    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", tmp_path / "plans")
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", tmp_path / "templates")
    library.ensure_config_library()
    with pytest.raises(library.ConfigReferenceResolutionError, match="plan_id_shadowed"):
        library.save_scene_to_library(
            SceneWorkspace(
                scene_id="exam",
                name="School Midterm",
                mode_id="exam",
                template_id="default",
                compatible_template_ids=["default"],
            ),
            scene_id="exam",
            mode_id="exam",
        )

    window = MainWindow()
    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        combo.setCurrentIndex(combo.findData("exam"))
        qapp.processEvents()

        assert window.bridge.current_scene_id() == "exam"
        assert window.bridge.current_scene_source() == "library"
        assert window.bridge.current_scene_source_type() == "builtin"
        assert "/builtin/" in window.bridge.current_scene_path().replace("\\", "/")
    finally:
        _close_test_window(window, qapp)


def test_main_window_work_mode_switch_cancel_keeps_dirty_config(qapp, monkeypatch):
    window = MainWindow()
    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        original_mode_id = window.bridge.current_work_mode_id()
        original_scene_id = window.bridge.current_scene_id()
        original_template_id = window.bridge.current_template_id()
        seen_scenes = []
        seen_templates = []
        window.bridge.scene_changed.connect(seen_scenes.append)
        window.bridge.template_changed.connect(seen_templates.append)
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda mode: main_window_module.WORK_MODE_DIRTY_CANCEL,
        )

        window.bridge.set_scene_dirty(True)
        combo.setCurrentIndex(combo.findData("exam"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == original_mode_id
        assert combo.currentData() == original_mode_id
        assert window.bridge.current_scene_id() == original_scene_id
        assert window.bridge.current_template_id() == original_template_id
        assert window.bridge.is_scene_dirty() is True
        assert seen_scenes == []
        assert seen_templates == []
    finally:
        _close_test_window(window, qapp)


def test_main_window_work_mode_switch_discards_dirty_config(qapp, monkeypatch):
    window = MainWindow()
    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda mode: main_window_module.WORK_MODE_DIRTY_DISCARD,
        )

        window.bridge.set_scene_dirty(True)
        combo.setCurrentIndex(combo.findData("exam"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "exam"
        assert combo.currentData() == "exam"
        assert window.bridge.current_scene_id() == "exam"
        assert window.bridge.current_template_id() == "default"
        assert window.bridge.is_scene_dirty() is False
        assert window.bridge.is_template_dirty() is False
    finally:
        _close_test_window(window, qapp)


def test_work_mode_switch_caches_template_draft_without_prompt_or_publish(
    qapp,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        template_index = next(
            index for index, spec in enumerate(PANEL_SPECS) if spec.id == "template"
        )
        panel = window._show_panel(template_index, allow_async=False)
        assert isinstance(panel, TemplatePanel)

        committed_margin = window.bridge.current_template().page_setup.margin.top_cm
        panel._current_template.page_setup.margin.top_cm = committed_margin + 1.75
        panel._on_template_edited(panel._current_template)
        assert window.bridge.is_template_dirty() is True
        assert window.bridge.current_template().page_setup.margin.top_cm == committed_margin

        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: (_ for _ in ()).throw(
                AssertionError("template drafts must not block work-mode switching")
            ),
        )
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        combo.setCurrentIndex(combo.findData("exam"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "exam"
        assert window.bridge.is_template_dirty() is False

        combo.setCurrentIndex(combo.findData("custom"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert panel._current_template.page_setup.margin.top_cm == committed_margin + 1.75
        assert window.bridge.current_template().page_setup.margin.top_cm == committed_margin
        assert window.bridge.is_template_dirty() is True
    finally:
        panel = window._loaded_panel_for_id("template")
        if isinstance(panel, TemplatePanel):
            panel._discard_all_pending_template_edits()
        _close_test_window(window, qapp)


def test_main_window_work_mode_switch_saves_dirty_scene_before_switch(
    qapp,
    monkeypatch,
    tmp_path,
):
    window = MainWindow()

    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        _prepare_builtin_scene_save_as(window, monkeypatch, "custom saved")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda mode: main_window_module.WORK_MODE_DIRTY_SAVE,
        )

        window.bridge.set_scene_dirty(True)
        window.bridge.set_template_dirty(True)
        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        saved_path = config_library.scene_user_target_path(
            "custom saved", mode_id="custom"
        )
        assert saved_path.is_file()
        assert config_library.load_scene_from_library(
            "custom saved", mode_id="custom"
        ).scene_id == "custom saved"
        assert window.bridge.current_work_mode_id() == "official"
        assert combo.currentData() == "official"
        assert window.bridge.current_scene_id() == "official"
        assert window.bridge.current_template_id() == "official_gbt"
        assert window.bridge.is_scene_dirty() is False
        assert window.bridge.is_template_dirty() is False
    finally:
        _close_test_window(window, qapp)


def test_main_window_work_mode_switch_saves_dirty_scene_with_previous_mode(
    qapp,
    monkeypatch,
    tmp_path,
):
    window = MainWindow()

    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        combo.setCurrentIndex(combo.findData("exam"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "exam"
        assert window.bridge.current_scene_id() == "exam"
        assert window.bridge.current_template_id() == "default"

        _prepare_builtin_scene_save_as(window, monkeypatch, "exam saved")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda mode: main_window_module.WORK_MODE_DIRTY_SAVE,
        )

        window.bridge.set_scene_dirty(True)
        window.bridge.set_template_dirty(True)
        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        saved_path = config_library.scene_user_target_path(
            "exam saved", mode_id="exam"
        )
        assert saved_path.is_file()
        assert config_library.load_scene_from_library(
            "exam saved", mode_id="exam"
        ).scene_id == "exam saved"
        assert window.bridge.current_work_mode_id() == "official"
        assert combo.currentData() == "official"
        assert window.bridge.current_scene_id() == "official"
        assert window.bridge.current_template_id() == "official_gbt"
        assert window.bridge.is_scene_dirty() is False
        assert window.bridge.is_template_dirty() is False
    finally:
        _close_test_window(window, qapp)


def test_main_window_work_mode_switch_restores_when_dirty_save_fails(
    qapp,
    monkeypatch,
):
    window = MainWindow()

    def fail_save_scene(scene, scene_id=None, **_kwargs):
        raise RuntimeError("cannot save scene")

    try:
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")
        original_mode_id = window.bridge.current_work_mode_id()
        original_scene_id = window.bridge.current_scene_id()
        _prepare_builtin_scene_save_as(window, monkeypatch, "failed saved")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda mode: main_window_module.WORK_MODE_DIRTY_SAVE,
        )
        monkeypatch.setattr(
            scene_session_module, "save_scene_to_library", fail_save_scene
        )

        window.bridge.set_scene_dirty(True)
        combo.setCurrentIndex(combo.findData("exam"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == original_mode_id
        assert combo.currentData() == original_mode_id
        assert window.bridge.current_scene_id() == original_scene_id
        assert window.bridge.is_scene_dirty() is True
    finally:
        _close_test_window(window, qapp)


def test_clean_work_mode_switches_do_not_create_material_packages(qapp, tmp_path):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        assert panel.has_pending_material_changes() is False
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")

        for mode_id in ("official", "custom") * 10:
            combo.setCurrentIndex(combo.findData(mode_id))
            qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert _saved_material_packages(tmp_path) == []
    finally:
        _close_test_window(window, qapp)


def test_dirty_material_cancel_keeps_mode_editor_and_disk_unchanged(
    qapp,
    tmp_path,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Cancel Corp")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: main_window_module.WORK_MODE_DIRTY_CANCEL,
        )
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")

        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert combo.currentData() == "custom"
        assert panel.current_archive().profiles[0].fields["company_name"] == "Cancel Corp"
        assert panel.has_pending_material_changes() is True
        assert _saved_material_packages(tmp_path) == []
    finally:
        _close_test_window(window, qapp)


def test_dirty_material_discard_switches_without_writing(qapp, tmp_path, monkeypatch):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Discard Corp")
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: main_window_module.WORK_MODE_DIRTY_DISCARD,
        )
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")

        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "official"
        assert combo.currentData() == "official"
        assert panel.has_pending_material_changes() is False
        assert "company_name" not in panel.current_archive().profiles[0].fields
        assert _saved_material_packages(tmp_path) == []
    finally:
        _close_test_window(window, qapp)


def test_dirty_material_save_writes_once_to_previous_mode_before_switch(
    qapp,
    tmp_path,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    prompted = []

    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Saved Corp")
        _prepare_builtin_scene_save_as(window, monkeypatch, "material scene saved")
        window.bridge.set_scene_dirty(True)
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda mode: prompted.append(mode.mode_id)
            or main_window_module.WORK_MODE_DIRTY_SAVE,
        )
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")

        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        saved = _saved_material_packages(tmp_path)
        assert len(saved) == 1
        assert "/custom/user/" in saved[0].as_posix()
        payload = json.loads(saved[0].read_text(encoding="utf-8"))
        assert payload["mode_id"] == "custom"
        assert payload["profiles"][0]["fields"]["company_name"] == "Saved Corp"
        assert prompted == ["official"]
        assert config_library.scene_user_target_path(
            "material scene saved", mode_id="custom"
        ).is_file()
        assert window.bridge.current_work_mode_id() == "official"
        assert combo.currentData() == "official"
    finally:
        _close_test_window(window, qapp)


def test_dirty_material_save_failure_never_changes_mode_or_writes(
    qapp,
    tmp_path,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Failed Corp")
        _prepare_builtin_scene_save_as(window, monkeypatch, "must not be saved")
        window.bridge.set_scene_dirty(True)
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: main_window_module.WORK_MODE_DIRTY_SAVE,
        )
        monkeypatch.setattr(panel, "save_pending_material_changes", lambda: False)
        combo = window.title_bar.findChild(StyledComboBox, "titlebar_work_mode_combo")

        combo.setCurrentIndex(combo.findData("official"))
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert combo.currentData() == "custom"
        assert panel.current_archive().profiles[0].fields["company_name"] == "Failed Corp"
        assert panel.has_pending_material_changes() is True
        assert window.bridge.is_scene_dirty() is True
        assert not config_library.scene_user_target_path(
            "must not be saved", mode_id="custom"
        ).exists()
        assert _saved_material_packages(tmp_path) == []
    finally:
        _close_test_window(window, qapp)


def test_programmatic_work_mode_switch_never_implicitly_saves_materials(
    qapp,
    tmp_path,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Internal Corp")

        window.bridge.set_current_work_mode("official")
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "official"
        assert panel.has_pending_material_changes() is False
        assert _saved_material_packages(tmp_path) == []
    finally:
        _close_test_window(window, qapp)


def test_failed_mode_default_load_restores_complete_material_scope(qapp, monkeypatch):
    from src.config.material_batch import MaterialBatchSelection
    from src.config.material_context import MaterialExecutionContext

    window = MainWindow(enable_background_services=False)
    try:
        window._ensure_panel_loaded_for_id("scene")
        context = MaterialExecutionContext(
            mode_id="custom",
            scene_id="custom",
            entity_data={"sentinel": "kept"},
        )
        selection = MaterialBatchSelection(
            mode_id="custom",
            scene_id="custom",
            package_id="package-one",
            profile_ids=["profile-one"],
        )
        window.bridge.set_current_material_context(context, emit_signal=False)
        window.bridge.set_current_material_batch_selection(selection, emit_signal=False)
        original_scene_id = window.bridge.current_scene_id()
        original_template_id = window.bridge.current_template_id()

        def fail_defaults(_mode):
            raise RuntimeError("forced mode-default failure")

        monkeypatch.setattr(window, "_load_work_mode_defaults", fail_defaults)

        assert window._request_work_mode_change("official") is False
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert window.bridge.current_scene_id() == original_scene_id
        assert window.bridge.current_template_id() == original_template_id
        assert window.bridge.current_material_context() == context
        assert window.bridge.current_material_batch_selection() == selection
        assert window.bridge.suspended_material_states() == ()
    finally:
        _close_test_window(window, qapp)


def test_failed_mode_activation_rolls_back_prepared_material_discard(
    qapp,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "UNSAVED MATERIAL")
        assert panel.has_pending_material_changes() is True
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: main_window_module.WORK_MODE_DIRTY_DISCARD,
        )

        def fail_defaults(_mode):
            raise RuntimeError("forced mode-default failure after discard")

        monkeypatch.setattr(window, "_load_work_mode_defaults", fail_defaults)

        assert window._request_work_mode_change("official") is False
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert panel.current_archive().profiles[0].fields["company_name"] == (
            "UNSAVED MATERIAL"
        )
        assert panel.has_pending_material_changes() is True
    finally:
        _close_test_window(window, qapp)


def test_warm_scene_panel_mode_switch_publishes_each_default_once(qapp):
    window = MainWindow(enable_background_services=False)
    try:
        window._ensure_panel_loaded_for_id("scene")
        seen_scenes = []
        seen_templates = []
        window.bridge.scene_changed.connect(seen_scenes.append)
        window.bridge.template_changed.connect(seen_templates.append)

        assert window._request_work_mode_change("official") is True
        qapp.processEvents()

        assert [scene.scene_id for scene in seen_scenes] == ["official"]
        assert len(seen_templates) == 1
        assert window.bridge.current_template_id() == "official_gbt"
        assert window.bridge.is_scene_dirty() is False
    finally:
        _close_test_window(window, qapp)


def test_scene_save_failure_rolls_back_material_save_before_mode_switch(
    qapp,
    tmp_path,
    monkeypatch,
):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Rollback Corp")
        _prepare_builtin_scene_save_as(window, monkeypatch, "rollback scene")
        window.bridge.set_scene_dirty(True)
        monkeypatch.setattr(
            window,
            "_prompt_work_mode_dirty_switch_action",
            lambda _mode: main_window_module.WORK_MODE_DIRTY_SAVE,
        )

        def fail_scene_save(*_args, **_kwargs):
            raise RuntimeError("scene disk unavailable")

        monkeypatch.setattr(
            scene_session_module,
            "save_scene_to_library",
            fail_scene_save,
        )

        assert window._request_work_mode_change("official") is False
        qapp.processEvents()

        assert window.bridge.current_work_mode_id() == "custom"
        assert window.bridge.is_scene_dirty() is True
        assert panel.has_pending_material_changes() is True
        assert panel.current_archive().profiles[0].fields["company_name"] == "Rollback Corp"
        assert _saved_material_packages(tmp_path) == []
    finally:
        _close_test_window(window, qapp)


def test_material_close_discard_can_be_rolled_back(qapp, monkeypatch):
    window = MainWindow(enable_background_services=False)
    try:
        panel = _load_assets_panel(window)
        _edit_material_field(panel, "Close Rollback Corp")
        monkeypatch.setattr(
            panel,
            "_prompt_pending_material_action",
            lambda _reason: "discard",
        )

        assert panel.prepare_close_pending_changes() is True
        assert panel.commit_close_pending_changes() is True
        assert panel.has_pending_material_changes() is False

        assert panel.rollback_close_pending_changes() is True
        assert panel.has_pending_material_changes() is True
        assert (
            panel.current_archive().profiles[0].fields["company_name"]
            == "Close Rollback Corp"
        )
    finally:
        _close_test_window(window, qapp)


def test_edit_transaction_cleanup_continues_after_individual_failures(caplog):
    calls: list[str] = []

    class Panel:
        def __init__(self, name: str, outcome: str = "ok") -> None:
            self.name = name
            self.outcome = outcome

        def cleanup(self):
            calls.append(self.name)
            if self.outcome == "raise":
                raise RuntimeError(f"{self.name} cleanup failed")
            if self.outcome == "false":
                return False
            return True

    transactions = [
        (Panel("first"), "", "cleanup", "cleanup", "cleanup"),
        (Panel("second", "raise"), "", "cleanup", "cleanup", "cleanup"),
        (Panel("third", "false"), "", "cleanup", "cleanup", "cleanup"),
    ]

    MainWindow._rollback_edit_transactions(transactions)
    assert calls == ["third", "second", "first"]

    calls.clear()
    MainWindow._cancel_prepared_edit_transactions(transactions)
    assert calls == ["first", "second", "third"]

    calls.clear()
    assert MainWindow._finalize_edit_transactions(transactions) is False
    assert calls == ["third"]
    assert "returned False" in caplog.text


def test_edit_transaction_finalize_succeeds_in_reverse_commit_order():
    calls: list[str] = []

    class Panel:
        def __init__(self, name: str) -> None:
            self.name = name

        def finalize(self):
            calls.append(self.name)
            return True

    transactions = [
        (Panel("first"), "", "", "finalize", ""),
        (Panel("second"), "", "", "finalize", ""),
        (Panel("third"), "", "", "finalize", ""),
    ]

    assert MainWindow._finalize_edit_transactions(transactions) is True
    assert calls == ["third", "second", "first"]


def test_strict_finalize_retains_scene_evidence_until_all_participants_succeed():
    calls: list[object] = []

    class ScenePanelLike:
        def finalize(self, *, retain_rollback: bool = False):
            calls.append(("scene.finalize", retain_rollback))
            return True

        def release_finalized_edit_transaction(self):
            calls.append("scene.release")
            return True

    class MaterialPanelLike:
        def __init__(self, succeeds: bool) -> None:
            self.succeeds = succeeds

        def finalize(self):
            calls.append("material.finalize")
            return self.succeeds

    scene = ScenePanelLike()
    material = MaterialPanelLike(False)
    transactions = [
        (material, "", "", "finalize", ""),
        (scene, "", "", "finalize", ""),
    ]

    assert MainWindow._finalize_edit_transactions(
        transactions,
        retain_rollback=True,
    ) is False
    assert calls == [("scene.finalize", True), "material.finalize"]

    calls.clear()
    material.succeeds = True
    assert MainWindow._finalize_edit_transactions(
        transactions,
        retain_rollback=True,
    ) is True
    assert calls == [
        ("scene.finalize", True),
        "material.finalize",
        "scene.release",
    ]
