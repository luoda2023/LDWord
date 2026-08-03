from __future__ import annotations

import json

import pytest

from src.application.materials import default_material_contract_id
from src.config import library as config_library
from src.config.builtin_templates import create_builtin_template
from src.config.execution_feature_state import DISABLED_SELECTOR_VALUE
from src.config.material_package_library import material_package_repository
from src.domain.materials import (
    MaterialPackage,
    MaterialRecord,
    generate_package_id,
    generate_record_id,
)
from src.ui.main_window import MainWindow
from src.ui.workspace_preferences import (
    WorkspacePreferenceStore,
    WorkspacePreferences,
)


@pytest.fixture
def isolated_config_library(tmp_path, monkeypatch):
    root = tmp_path / "config-library"
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", root / "plans")
    monkeypatch.setattr(config_library, "TEMPLATE_LIBRARY_DIR", root / "templates")
    config_library.ensure_config_library()
    return root


def test_workspace_preference_store_round_trips_versioned_mode_state(tmp_path):
    path = tmp_path / "workspace-preferences.json"
    store = WorkspacePreferenceStore(path)

    store.update_mode(
        "thesis",
        scene_id="thesis",
        template_id="thesis_custom",
        execution_template_id="thesis_gbt",
        plan_enabled=False,
        template_enabled=False,
        material_enabled=True,
        material_package_id="package-1",
        official_document_type_id="report",
        output_mode="custom",
        custom_output_dir="C:/Deliveries",
    )
    store.update_active_mode("thesis")

    restored = WorkspacePreferenceStore(path).load()
    preference = restored.for_mode("thesis")

    assert restored.active_mode_id == "thesis"
    assert preference is not None
    assert preference.scene_id == "thesis"
    assert preference.template_id == "thesis_custom"
    assert preference.execution_template_id == "thesis_gbt"
    assert preference.plan_enabled is False
    assert preference.template_enabled is False
    assert preference.material_selection_configured is True
    assert preference.material_enabled is True
    assert preference.material_package_id == "package-1"
    assert preference.output_mode == "custom"
    assert preference.custom_output_dir == "C:/Deliveries"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == (
        "workspace-preferences-v1"
    )


def test_unrelated_mode_preferences_do_not_disable_default_material_selection(
    tmp_path,
):
    store = WorkspacePreferenceStore(tmp_path / "workspace-preferences.json")

    preference = store.update_mode("official", scene_id="official").for_mode(
        "official"
    )

    assert preference is not None
    assert preference.material_selection_configured is False


def test_workspace_preference_store_ignores_corrupt_or_unknown_state(tmp_path):
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    assert WorkspacePreferenceStore(corrupt).load() == WorkspacePreferences()

    unknown = tmp_path / "unknown.json"
    unknown.write_text(
        json.dumps({"schema_version": "workspace-preferences-v999"}),
        encoding="utf-8",
    )
    assert WorkspacePreferenceStore(unknown).load() == WorkspacePreferences()


def test_restart_restores_saved_template_and_durable_execution_choices(
    qapp,
    tmp_path,
    isolated_config_library,
):
    state_path = tmp_path / "workspace-preferences.json"
    first = MainWindow(
        enable_background_services=False,
        workspace_preference_store=WorkspacePreferenceStore(state_path),
    )
    workbench = first._loaded_panel_for_id("workbench")
    quick = workbench._quick_execution_detail

    user_template = create_builtin_template("default", mode_id="custom")
    user_template.name = "Restart retained template"
    entry = config_library.save_template_to_library(
        user_template,
        template_id="restart_retained_template",
        mode_id="custom",
    )
    first.bridge.set_current_template(
        user_template,
        config_id=entry.config_id,
        path=str(entry.path),
        source="library",
        source_type="user",
    )

    package_combo = quick._material_preview._package_field
    package_index = next(
        index
        for index in range(package_combo.count())
        if str(package_combo.itemData(index) or "").strip()
        not in {"", DISABLED_SELECTOR_VALUE}
    )
    package_combo.setCurrentIndex(package_index)
    package_id = str(package_combo.currentData())

    quick._scene_combo.setCurrentIndex(
        quick._scene_combo.findData(DISABLED_SELECTOR_VALUE)
    )
    quick._template_combo.setCurrentIndex(
        quick._template_combo.findData(DISABLED_SELECTOR_VALUE)
    )
    custom_output = tmp_path / "deliveries"
    workbench._document_execution_detail._output_card.set_output_dir(str(custom_output))
    first.bridge.set_current_document_path(str(tmp_path / "one-off.docx"))
    qapp.processEvents()

    assert first.close()
    qapp.processEvents()

    second = MainWindow(
        enable_background_services=False,
        workspace_preference_store=WorkspacePreferenceStore(state_path),
    )
    restored_workbench = second._loaded_panel_for_id("workbench")
    restored_quick = restored_workbench._quick_execution_detail
    restored_selection = second.bridge.current_material_run_selection()
    try:
        template_index = next(
            index
            for index, spec in enumerate(second._panel_specs)
            if spec.id == "template"
        )
        template_panel = second._show_panel(template_index, allow_async=False)

        assert second.bridge.current_work_mode_id() == "custom"
        assert second.bridge.current_template_id() == entry.config_id
        assert second.bridge.current_template().name == user_template.name
        assert template_panel._current_template_id == entry.config_id
        assert template_panel._current_template.name == user_template.name
        assert restored_quick.plan_enabled() is False
        assert restored_quick.template_enabled() is False
        assert restored_quick.material_package_enabled() is True
        assert restored_selection is not None
        assert restored_selection.package_ref.package_id == package_id
        assert restored_quick.execution_scene().is_module_enabled("entity_fill")
        assert "content_fill" not in restored_quick.enabled_features()
        assert "content_fill" not in restored_workbench._navigation_cards
        assert "content_fill" not in restored_workbench._detail_map
        assert not hasattr(restored_workbench, "_content_fill_detail")
        assert restored_workbench._document_execution_detail.output_dir() == str(
            custom_output
        )

        assets_index = next(
            index
            for index, spec in enumerate(second._panel_specs)
            if spec.id == "assets"
        )
        assets_panel = second._show_panel(assets_index, allow_async=False)
        assert assets_panel._package_combo.currentData() == package_id
        assert second.bridge.current_material_run_selection().package_ref.package_id == (
            package_id
        )

        # Inputs and execution feedback are task state, not durable preferences.
        assert second.bridge.current_document_path() == ""
        assert (
            restored_workbench._document_execution_detail._execution_state.status
            == "idle"
        )
    finally:
        second.close()
        qapp.processEvents()


def test_restart_falls_back_only_when_persisted_resources_are_unavailable(
    qapp,
    tmp_path,
    isolated_config_library,
):
    state_path = tmp_path / "workspace-preferences.json"
    store = WorkspacePreferenceStore(state_path)
    store.update_mode(
        "custom",
        scene_id="deleted-plan",
        template_id="deleted-template",
        execution_template_id="deleted-template",
        material_enabled=True,
        material_package_id="deleted-package",
        output_mode="custom",
        custom_output_dir=str(tmp_path / "still-retained-output"),
    )

    window = MainWindow(
        enable_background_services=False,
        workspace_preference_store=WorkspacePreferenceStore(state_path),
    )
    workbench = window._loaded_panel_for_id("workbench")
    quick = workbench._quick_execution_detail
    try:
        assert window.bridge.current_scene_id() == "custom"
        assert window.bridge.current_template_id() == "default"
        assert quick.selected_template_id() == "default"
        assert workbench._document_execution_detail.output_dir() == str(
            tmp_path / "still-retained-output"
        )
        package_combo = quick._material_preview._package_field
        assert quick.material_package_enabled() is True
        assert quick.selected_material_package_id() == "deleted-package"
        assert package_combo.currentData() == "deleted-package"
        assert package_combo.currentText() == "原资料包（不可用）"
        assert any(
            issue.code == "material.selection.package_unavailable"
            for issue in window.bridge.current_material_issues()
        )

        assets_index = next(
            index
            for index, spec in enumerate(window._panel_specs)
            if spec.id == "assets"
        )
        assets_panel = window._show_panel(assets_index, allow_async=False)
        assert assets_panel._package_combo.currentData() == "deleted-package"
        assert "不可用" in assets_panel._package_combo.currentText()
        assert assets_panel._package is None
        assert assets_panel._duplicate_button.isEnabled() is False

        # Saving an unrelated choice must not silently erase the unresolved ID.
        workbench._persist_workspace_preferences()
        retained = WorkspacePreferenceStore(state_path).load().for_mode("custom")
        assert retained is not None
        assert retained.material_enabled is True
        assert retained.material_package_id == "deleted-package"

        # Only an explicit user choice to disable the package clears it.
        package_combo.setCurrentIndex(
            package_combo.findData(DISABLED_SELECTOR_VALUE)
        )
        qapp.processEvents()
        cleared = WorkspacePreferenceStore(state_path).load().for_mode("custom")
        assert cleared is not None
        assert cleared.material_enabled is False
        assert cleared.material_package_id == ""
    finally:
        window.close()
        qapp.processEvents()


def test_assets_page_selection_survives_restart_without_falling_back(
    qapp,
    tmp_path,
):
    state_path = tmp_path / "workspace-preferences.json"
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="资料页保留选择",
        work_mode_id="custom",
        material_contract_id=default_material_contract_id("custom"),
        records=(
            MaterialRecord(
                record_id=generate_record_id(),
                display_name="记录 1",
                lifecycle="active",
            ),
        ),
    )
    material_package_repository().create_user(package)

    first = MainWindow(
        enable_background_services=False,
        workspace_preference_store=WorkspacePreferenceStore(state_path),
    )
    assets_index = next(
        index
        for index, spec in enumerate(first._panel_specs)
        if spec.id == "assets"
    )
    first_assets = first._show_panel(assets_index, allow_async=False)
    first_assets._package_combo.setCurrentIndex(
        first_assets._package_combo.findData(package.package_id)
    )
    qapp.processEvents()
    assert first.close()
    qapp.processEvents()

    second = MainWindow(
        enable_background_services=False,
        workspace_preference_store=WorkspacePreferenceStore(state_path),
    )
    second.show()
    qapp.processEvents()
    try:
        restored_workbench = second._loaded_panel_for_id("workbench")
        restored_selection = second.bridge.current_material_run_selection()
        assert restored_selection is not None
        assert restored_selection.package_ref.package_id == package.package_id

        second_assets = second._show_panel(assets_index, allow_async=False)
        assert second_assets._package_combo.currentData() == package.package_id
        assert second_assets._package is not None
        assert second_assets._package.package_id == package.package_id
        assert (
            restored_workbench._quick_execution_detail.selected_material_package_id()
            == package.package_id
        )

        # Re-entering the already-loaded Assets page follows a later Workbench
        # choice, while the package editor is clean.
        second._show_panel(0, allow_async=False)
        quick = restored_workbench._quick_execution_detail
        package_combo = quick._material_preview._package_field
        replacement_index = next(
            index
            for index in range(package_combo.count())
            if str(package_combo.itemData(index) or "").strip()
            not in {"", DISABLED_SELECTOR_VALUE, package.package_id}
            and package_combo.model().item(index).isEnabled()
        )
        replacement_id = str(package_combo.itemData(replacement_index))
        package_combo.setCurrentIndex(replacement_index)
        qapp.processEvents()

        second._show_panel(assets_index, allow_async=False)
        qapp.processEvents()
        assert second_assets._package_combo.currentData() == replacement_id
    finally:
        second.close()
        qapp.processEvents()


def test_startup_restores_active_mode_and_selected_plan(
    qapp,
    tmp_path,
    isolated_config_library,
):
    state_path = tmp_path / "workspace-preferences.json"
    store = WorkspacePreferenceStore(state_path)
    store.update_mode(
        "exam",
        scene_id="exam_quiz",
        template_id="default",
        execution_template_id="default",
    )
    store.update_active_mode("exam")

    window = MainWindow(
        enable_background_services=False,
        workspace_preference_store=WorkspacePreferenceStore(state_path),
    )
    workbench = window._loaded_panel_for_id("workbench")
    try:
        assert window.bridge.current_work_mode_id() == "exam"
        assert window.bridge.current_scene_id() == "exam_quiz"
        assert window.bridge.current_template_id() == "default"
        assert workbench._quick_execution_detail.current_scene_id() == "exam_quiz"
        assert workbench._quick_execution_detail.selected_template_id() == "default"
    finally:
        window.close()
        qapp.processEvents()
