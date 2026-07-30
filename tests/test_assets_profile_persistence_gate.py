from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import material_package_library as material_package_library
from src.config.attachment_materials import AttachmentRoleSpec
from src.config.content_artifacts import ContentArtifactRef, ContentMaterialBinding
from src.config.content_materials import ContentInsertionRule, content_anchor_token
from src.config.entity import AssetBinding, EntityArchive, EntityProfile
from src.config.material_batch import MaterialBatchSelection
from src.config.material_mappings import MaterialMappingPayload
from src.config.material_package_library import MaterialPackageLibraryEntry
from src.config.materials import AssetItem
from src.qt_api import QApplication, Qt
from src.services.material_assets import (
    asset_item_payload,
    question_figure_library_metadata_history_record,
)
from src.services.material_attachments import build_attachment_binding
from src.ui.bridge import PanelBridge
from src.ui.panels.assets.archive_presenter import ProfileEditorPersistenceRejected
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)
from src.ui.panels.assets.specs import AssetGroupSpec, AssetSlotSpec
from src.ui.panels.assets_panel import AssetsPanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _panel_with_profile(*, profile_id: str = "profile-1") -> AssetsPanel:
    panel = AssetsPanel(PanelBridge())
    panel.set_archive(
        EntityArchive(
            archive_id="package-1",
            profiles=[EntityProfile(profile_id=profile_id, profile_name="Profile 1")],
        )
    )
    return panel


def _question_payload(path: str, *, source: str = "local") -> dict[str, object]:
    return asset_item_payload(
        AssetItem(
            item_id="question-1",
            label="Question 1",
            role="question_figure",
            path=path,
            metadata={
                "question_index": "1",
                "source": source,
                "asset_id": "asset-1",
                "alt_text": "original alt",
            },
        )
    )


def test_assets_presenters_do_not_discard_profile_persistence_results() -> None:
    ignored: list[str] = []
    paths = [
        *Path("src/ui/panels/assets").glob("*.py"),
        Path("src/ui/panels/assets_panel.py"),
    ]
    for path in paths:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            function = node.value.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "_persist_current_profile_editor"
            ):
                ignored.append(f"{path}:{node.lineno}")

    assert ignored == []


def test_assets_presenters_do_not_discard_material_batch_publish_results() -> None:
    ignored: list[str] = []
    paths = [
        *Path("src/ui/panels/assets").glob("*.py"),
        Path("src/ui/panels/assets_panel.py"),
    ]
    for path in paths:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            function = node.value.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "_sync_material_batch_selection"
            ):
                ignored.append(f"{path}:{node.lineno}")

    assert ignored == []


def test_archive_replace_and_profile_remove_keep_checked_transaction_gates() -> None:
    cases = (
        (
            Path("src/ui/panels/assets/archive_presenter.py"),
            "set_archive",
            "_apply_archive_editor_state",
        ),
        (
            Path("src/ui/panels/assets/profile_presenter.py"),
            "_remove_current_profile",
            None,
        ),
    )
    for path, function_name, mutation_call_name in cases:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        function = next(
            node
            for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(function):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

        def calls_named(name: str) -> list[ast.Call]:
            return [
                node
                for node in calls
                if isinstance(node.func, ast.Attribute) and node.func.attr == name
            ]

        persist_calls = calls_named("_persist_current_profile_editor")
        capture_calls = calls_named("_capture_archive_editor_transaction_snapshot")
        sync_calls = calls_named("_sync_material_batch_selection")
        restore_calls = calls_named("_restore_archive_editor_transaction_snapshot")
        assert len(persist_calls) == 1
        assert len(capture_calls) == 1
        assert len(sync_calls) == 1
        assert len(restore_calls) == 1
        assert not isinstance(parents[sync_calls[0]], ast.Expr)
        if mutation_call_name is not None:
            mutation_calls = calls_named(mutation_call_name)
            assert mutation_calls
            first_mutation_line = min(node.lineno for node in mutation_calls)
        else:
            mutation_lines = [
                node.lineno
                for node in ast.walk(function)
                if (
                    isinstance(node, (ast.Assign, ast.AnnAssign))
                    and any(
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and target.attr == "_profiles"
                        for target in (
                            node.targets
                            if isinstance(node, ast.Assign)
                            else [node.target]
                        )
                    )
                )
            ]
            mutation_lines.extend(
                node.lineno
                for node in calls
                if isinstance(node.func, ast.Attribute)
                and node.func.attr == "pop"
                and isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "self"
                and node.func.value.attr == "_profiles"
            )
            assert mutation_lines
            first_mutation_line = min(mutation_lines)
        assert persist_calls[0].lineno < capture_calls[0].lineno < first_mutation_line


@pytest.mark.parametrize("failure_mode", ["false", "exception"])
def test_set_archive_publish_failure_restores_full_editor_and_bridge(
    failure_mode: str,
    monkeypatch,
) -> None:
    _app()
    panel = AssetsPanel(PanelBridge())
    panel._material_persistence.replace_identity(None, "")
    old_archive = EntityArchive(
        archive_id="package-a",
        archive_name="Package A",
        profiles=[
            EntityProfile(profile_id="p1", profile_name="Profile 1"),
            EntityProfile(profile_id="p2", profile_name="Profile 2"),
        ],
    )
    assert panel.set_archive(old_archive, select_index=1) is True
    first_item = panel._profile_list.item(0)
    assert first_item is not None
    first_item.setCheckState(Qt.Unchecked)
    published = panel.bridge.current_material_batch_selection()
    panel._profile_name_edit.setText("Unsaved profile 2")
    panel._task_field_values = {"runtime": "keep"}
    panel._last_received_material_context = {"context": "keep"}
    expected_profiles = copy.deepcopy(panel._profiles)
    expected_profiles[1].profile_name = "Unsaved profile 2"
    expected_checks = [
        panel._profile_list.item(index).checkState()
        for index in range(panel._profile_list.count())
    ]

    def reject_publish() -> bool:
        if failure_mode == "exception":
            drift = published.clone()
            drift.package_id = "drift-package"
            drift.profile_ids = []
            panel.bridge.set_current_material_batch_selection(
                drift,
                emit_signal=False,
            )
            raise RuntimeError("publish failed after bridge mutation")
        return False

    try:
        monkeypatch.setattr(panel, "_sync_material_batch_selection", reject_publish)

        assert panel.set_archive(
            EntityArchive(
                archive_id="package-b",
                archive_name="Package B",
                profiles=[EntityProfile(profile_id="new", profile_name="New")],
            )
        ) is False

        assert panel._profiles == expected_profiles
        assert panel._current_profile_index == 1
        assert panel._profile_list.currentRow() == 1
        assert panel._profile_name_edit.text() == "Unsaved profile 2"
        assert panel._archive_id_edit.text() == "package-a"
        assert panel._archive_name_edit.text() == "Package A"
        assert panel._task_field_values == {"runtime": "keep"}
        assert panel._last_received_material_context == {"context": "keep"}
        assert [
            panel._profile_list.item(index).checkState()
            for index in range(panel._profile_list.count())
        ] == expected_checks
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def _scene_and_secondary_mutation_state(panel: AssetsPanel) -> dict[str, object]:
    state = _material_mutation_local_state(panel)
    state.update(
        copy.deepcopy(
            {
                "asset_slot_specs": panel._asset_slot_specs,
                "asset_group_specs": panel._asset_group_specs,
                "asset_metadata": panel._asset_metadata,
                "asset_item_payloads": panel._asset_item_payloads,
                "image_material_rules": panel._image_material_rules,
            }
        )
    )
    return state


@pytest.mark.parametrize("failure_mode", ["false", "changed_then_exception"])
def test_scene_spec_and_secondary_mutations_rollback_after_checked_publish_failure(
    failure_mode: str,
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    original_sync = panel._sync_material_batch_selection
    slot_role = "slot"
    group_role = "group"
    attachment_role = "attachment"
    content_id = "content1"
    slot_spec = AssetSlotSpec(
        role=slot_role,
        label="Slot",
        target="{{@img:slot}}",
    )
    group_spec = AssetGroupSpec(
        role=group_role,
        label="Group",
        target="{{@img:group}}",
        recursive=True,
        max_items=None,
    )
    attachment_spec = AttachmentRoleSpec(
        role=attachment_role,
        label="Attachment",
        accepted_types=("pdf",),
        origin="profile",
    )
    scene_slot_spec = AssetSlotSpec(
        role="scene-slot",
        label="Scene Slot",
        target="{{@img:scene_slot}}",
    )
    scene_group_spec = AssetGroupSpec(
        role="scene-group",
        label="Scene Group",
        target="{{@img:scene_group}}",
        max_items=None,
    )
    scene_attachment_spec = AttachmentRoleSpec(
        role="scene-attachment",
        label="Scene Attachment",
        accepted_types=("pdf",),
    )
    old_image = tmp_path / "old.png"
    old_image.write_bytes(b"image")
    group_dir = tmp_path / "group"
    group_dir.mkdir()
    old_group_binding = AssetBinding(
        role=group_role,
        cardinality="multiple",
        source_kind="directory",
        source_path=str(group_dir),
        recursive=True,
        max_items=None,
    )
    old_pdf = tmp_path / "old.pdf"
    old_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    old_attachment_binding = build_attachment_binding(
        role=attachment_role,
        source_paths=(old_pdf,),
        accepted_types=("pdf",),
        cardinality="single",
        source_kind="single_file",
        label=attachment_spec.label,
    )
    content_rule = ContentInsertionRule(
        rule_id=f"content:{content_id}",
        content_id=content_id,
        anchor_token=content_anchor_token(content_id),
    )
    content_binding = ContentMaterialBinding(
        content_id=content_id,
        label=content_id,
        artifact_ref=ContentArtifactRef("e" * 64, "f" * 64),
    )

    monkeypatch.setattr(
        panel,
        "_asset_slots_from_scene",
        lambda _scene: (scene_slot_spec,),
    )
    monkeypatch.setattr(
        panel,
        "_asset_groups_from_scene",
        lambda _scene: (scene_group_spec,),
    )
    monkeypatch.setattr(
        panel,
        "_attachment_roles_from_scene",
        lambda _scene: (scene_attachment_spec,),
    )
    monkeypatch.setattr(
        "src.ui.panels.assets.scene_spec_presenter.confirm",
        lambda *_args, **_kwargs: True,
    )

    events: list[str] = []
    monkeypatch.setattr(
        panel,
        "_sync_asset_slot_rows",
        lambda: events.append("slot_rows"),
    )
    monkeypatch.setattr(
        panel,
        "_sync_asset_group_rows",
        lambda: events.append("group_rows"),
    )
    monkeypatch.setattr(
        panel,
        "_sync_attachment_role_rows",
        lambda: events.append("attachment_rows"),
    )
    monkeypatch.setattr(
        panel,
        "_refresh_asset_group_row",
        lambda _role: events.append("group_row"),
    )
    monkeypatch.setattr(
        panel,
        "_sync_content_material_rows",
        lambda: events.append("content_rows"),
    )
    monkeypatch.setattr(panel, "_apply_theme", lambda: events.append("theme"))
    monkeypatch.setattr(
        panel,
        "_refresh_summary",
        lambda: events.append("summary"),
    )

    restore_scene_selection = panel._restore_scene_spec_mutation_selection
    restore_group_selection = panel._restore_asset_group_mutation_selection
    restore_content_selection = panel._restore_content_material_mutation_selection

    def restore_scene(selection) -> None:
        events.append("bridge")
        restore_scene_selection(selection)

    def restore_group(selection) -> None:
        events.append("bridge")
        restore_group_selection(selection)

    def restore_content(selection) -> None:
        events.append("bridge")
        restore_content_selection(selection)

    monkeypatch.setattr(panel, "_restore_scene_spec_mutation_selection", restore_scene)
    monkeypatch.setattr(panel, "_restore_asset_group_mutation_selection", restore_group)
    monkeypatch.setattr(
        panel,
        "_restore_content_material_mutation_selection",
        restore_content,
    )

    active_cluster = {"name": ""}
    expected_state: dict[str, dict[str, object] | None] = {"value": None}
    state_was_mutated: list[bool] = []
    publish_count = 0

    def reject_publish() -> bool:
        nonlocal publish_count
        publish_count += 1
        state_was_mutated.append(
            _scene_and_secondary_mutation_state(panel) != expected_state["value"]
        )
        assert panel._persist_current_profile_editor() is True
        if active_cluster["name"] == "scene_spec":
            panel._current_image_preview_path = "publish-drift.png"
            panel._current_image_preview_display_name = "publish drift"
            panel._current_image_preview_compare_reference = "drift-reference"
            panel._current_image_preview_compare_source = "drift-source"
            panel._current_image_preview_compare_display_name = "drift compare"
            panel._current_image_preview_compare_options = [
                {"reference": "drift-reference"}
            ]
            panel._current_image_preview_question_figure_row = 88
            panel._image_assets_status_label.setText("publish drift")
        if failure_mode == "changed_then_exception":
            drift = panel.bridge.current_material_batch_selection()
            drift.package_id = "bridge-drift"
            drift.profile_ids = []
            panel.bridge.set_current_material_batch_selection(
                drift,
                emit_signal=False,
            )
            raise RuntimeError("publish failed after changing Bridge")
        return False

    monkeypatch.setattr(panel, "_sync_material_batch_selection", reject_publish)

    operations = (
        (
            "scene_switch",
            "scene_spec",
            [
                "slot_rows",
                "group_rows",
                "attachment_rows",
                "theme",
                "summary",
                "bridge",
            ],
            lambda: panel._on_scene_changed(object()),
        ),
        (
            "slot_insert",
            "scene_spec",
            ["slot_rows", "summary", "bridge"],
            lambda: panel._insert_asset_slot(
                1,
                target="{{@img:new_slot}}",
                role_prefix=slot_role,
            ),
        ),
        (
            "slot_token",
            "scene_spec",
            ["slot_rows", "summary", "bridge"],
            lambda: panel._commit_asset_slot_token(
                slot_role,
                "{{@img:renamed_slot}}",
            ),
        ),
        (
            "slot_label",
            "scene_spec",
            ["slot_rows", "summary", "bridge"],
            lambda: panel._commit_asset_slot_label(slot_role, "Renamed Slot"),
        ),
        (
            "slot_remove",
            "scene_spec",
            ["slot_rows", "summary", "bridge"],
            lambda: panel._remove_asset_slot(slot_role),
        ),
        (
            "group_insert",
            "scene_spec",
            ["group_rows", "summary", "bridge"],
            lambda: panel._insert_asset_group(
                1,
                target="{{@img:new_group}}",
                role_prefix=group_role,
            ),
        ),
        (
            "group_token",
            "scene_spec",
            ["group_rows", "summary", "bridge"],
            lambda: panel._commit_asset_group_token(
                group_role,
                "{{@img:renamed_group}}",
            ),
        ),
        (
            "group_label",
            "scene_spec",
            ["group_rows", "summary", "bridge"],
            lambda: panel._commit_asset_group_label(group_role, "Renamed Group"),
        ),
        (
            "group_remove",
            "scene_spec",
            ["group_rows", "summary", "bridge"],
            lambda: panel._remove_asset_group(group_role),
        ),
        (
            "attachment_request",
            "scene_spec",
            ["attachment_rows", "summary", "bridge"],
            lambda: panel._request_attachment_role(source_kind="single_file"),
        ),
        (
            "attachment_series",
            "scene_spec",
            ["attachment_rows", "summary", "bridge"],
            lambda: panel._add_attachment_role_series(attachment_role),
        ),
        (
            "attachment_remove",
            "scene_spec",
            ["attachment_rows", "summary", "bridge"],
            lambda: panel._remove_attachment_role(attachment_role),
        ),
        (
            "attachment_token",
            "scene_spec",
            ["attachment_rows", "summary", "bridge"],
            lambda: panel._commit_attachment_role_token(
                attachment_role,
                "{{@attach:renamed_attachment}}",
            ),
        ),
        (
            "attachment_label",
            "scene_spec",
            ["attachment_rows", "summary", "bridge"],
            lambda: panel._commit_attachment_role_label(
                attachment_role,
                "Renamed Attachment",
            ),
        ),
        (
            "group_refresh",
            "asset_group",
            ["group_row", "summary", "bridge"],
            lambda: panel._refresh_asset_group_binding(group_role),
        ),
        (
            "content_insert",
            "content",
            ["content_rows", "summary", "bridge"],
            lambda: panel._insert_content_material(1, "content2"),
        ),
        (
            "content_token",
            "content",
            ["content_rows", "summary", "bridge"],
            lambda: panel._commit_content_material_token(
                content_id,
                "{{@file:content2}}",
            ),
        ),
    )

    try:
        for operation_name, cluster, expected_events, invoke in operations:
            panel._asset_slot_specs = (slot_spec,)
            panel._asset_group_specs = (group_spec,)
            panel._attachment_role_specs = (attachment_spec,)
            panel._asset_paths = {slot_role: str(old_image)}
            panel._asset_bindings = {group_role: old_group_binding}
            panel._asset_metadata = {
                slot_role: {"alt_text": "old alt"},
                attachment_role: {"alt_text": "attachment metadata"},
            }
            panel._asset_item_payloads = [
                asset_item_payload(
                    AssetItem(
                        item_id="slot-item",
                        label="Slot item",
                        role=slot_role,
                        path=str(old_image),
                    )
                )
            ]
            panel._image_material_rules = {}
            panel._attachment_bindings = {
                attachment_role: old_attachment_binding
            }
            panel._attachment_legacy_errors = {
                attachment_role: "legacy error"
            }
            panel._content_rules = [content_rule]
            panel._content_bindings = {content_id: content_binding}
            panel._current_image_preview_path = str(old_image)
            panel._current_image_preview_display_name = operation_name
            panel._current_image_preview_compare_reference = "old-reference"
            panel._current_image_preview_compare_source = "old-source"
            panel._current_image_preview_compare_display_name = "old compare"
            panel._current_image_preview_compare_options = [
                {"reference": "old-reference", "label": operation_name}
            ]
            panel._current_image_preview_question_figure_row = 6
            panel._image_assets_status_label.setText(
                f"preview baseline: {operation_name}"
            )
            panel._store_asset_token_inventory()
            panel._store_attachment_role_inventory()
            assert panel._persist_current_profile_editor() is True
            assert original_sync() is True

            expected_state["value"] = _scene_and_secondary_mutation_state(panel)
            expected_profile = copy.deepcopy(panel._selected_profile())
            expected_selection = panel.bridge.current_material_batch_selection()
            active_cluster["name"] = cluster
            events.clear()
            before_publish_count = publish_count

            assert invoke() is False, operation_name
            assert publish_count == before_publish_count + 1, operation_name
            assert state_was_mutated[-1] is True, operation_name
            assert (
                _scene_and_secondary_mutation_state(panel)
                == expected_state["value"]
            ), operation_name
            assert panel._selected_profile() == expected_profile, operation_name
            assert (
                panel.bridge.current_material_batch_selection() == expected_selection
            ), operation_name
            assert events == expected_events, operation_name
            assert events[-1] == "bridge", operation_name

        assert publish_count == len(operations)
    finally:
        panel.close()


def test_set_archive_persistence_rejection_happens_before_mutation(monkeypatch) -> None:
    _app()
    panel = _panel_with_profile()
    profiles = copy.deepcopy(panel._profiles)
    archive_id = panel._archive_id_edit.text()
    published = panel.bridge.current_material_batch_selection()
    try:
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)
        monkeypatch.setattr(
            panel,
            "_sync_material_batch_selection",
            lambda: (_ for _ in ()).throw(
                AssertionError("publish ran after rejected harvest")
            ),
        )

        assert panel.set_archive(
            EntityArchive(
                archive_id="rejected",
                profiles=[EntityProfile(profile_id="rejected")],
            )
        ) is False
        assert panel._profiles == profiles
        assert panel._archive_id_edit.text() == archive_id
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def test_archive_activation_rejection_restores_entry_path_and_selector(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    panel = AssetsPanel(PanelBridge())
    path_a = tmp_path / "a" / "package.json"
    path_b = tmp_path / "b" / "package.json"
    entry_a = MaterialPackageLibraryEntry(
        package_id="package-a",
        name="Package A",
        path=path_a,
        mode_id="",
        source_type="user",
    )
    entry_b = MaterialPackageLibraryEntry(
        package_id="package-b",
        name="Package B",
        path=path_b,
        mode_id="",
        source_type="user",
    )
    panel._material_persistence.replace_identity(None, "")
    assert panel.set_archive(
        EntityArchive(
            archive_id="package-a",
            archive_name="Package A",
            profiles=[EntityProfile(profile_id="p1", profile_name="Old")],
        )
    ) is True
    panel._material_persistence.replace_identity(entry_a, str(path_a))
    panel._capture_material_persistence_snapshot()
    baseline = copy.deepcopy(panel._persisted_archive_snapshot)
    published = panel.bridge.current_material_batch_selection()
    signals_blocked = panel._archive_combo.blockSignals(True)
    try:
        panel._archive_combo.clear()
        panel._archive_combo.addItem("Package A", str(path_a))
        panel._archive_combo.addItem("Package B", str(path_b))
        panel._archive_combo.setCurrentIndex(1)
    finally:
        panel._archive_combo.blockSignals(signals_blocked)
    try:
        monkeypatch.setattr(
            "src.ui.panels.assets.archive_presenter.load_material_package_entry",
            lambda _entry: EntityArchive(
                archive_id="package-b",
                archive_name="Package B",
                profiles=[EntityProfile(profile_id="new", profile_name="New")],
            ),
        )
        monkeypatch.setattr(panel, "_sync_material_batch_selection", lambda: False)

        assert panel._activate_archive_entry(entry_b) is False

        assert panel._current_archive_entry == entry_a
        assert panel._current_archive_path == str(path_a)
        assert panel._archive_combo.currentData() == str(path_a)
        assert panel._profiles[0].profile_id == "p1"
        assert panel._profile_name_edit.text() == "Old"
        assert panel._persisted_archive_snapshot == baseline
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


@pytest.mark.parametrize("profile_count", [1, 2])
@pytest.mark.parametrize("failure_mode", ["false", "exception"])
def test_profile_remove_publish_failure_restores_both_branches(
    profile_count: int,
    failure_mode: str,
    monkeypatch,
) -> None:
    _app()
    panel = AssetsPanel(PanelBridge())
    panel._material_persistence.replace_identity(None, "")
    profiles = [
        EntityProfile(profile_id=f"p{index + 1}", profile_name=f"Profile {index + 1}")
        for index in range(profile_count)
    ]
    selected_index = profile_count - 1
    assert panel.set_archive(
        EntityArchive(
            archive_id="package-a",
            archive_name="Package A",
            profiles=profiles,
        ),
        select_index=selected_index,
    ) is True
    if profile_count > 1:
        first_item = panel._profile_list.item(0)
        assert first_item is not None
        first_item.setCheckState(Qt.Unchecked)
    published = panel.bridge.current_material_batch_selection()
    panel._profile_name_edit.setText("Unsaved selected profile")
    panel._task_field_values = {"runtime": "keep"}
    panel._last_removed_official_field = {
        "key": "restorable",
        "scope": "fixed",
        "profile_index": selected_index,
    }
    expected_profiles = copy.deepcopy(panel._profiles)
    expected_profiles[selected_index].profile_name = "Unsaved selected profile"
    expected_checks = [
        panel._profile_list.item(index).checkState()
        for index in range(panel._profile_list.count())
    ]

    def reject_publish() -> bool:
        if failure_mode == "exception":
            drift = published.clone()
            drift.package_id = "drift-package"
            drift.profile_ids = []
            panel.bridge.set_current_material_batch_selection(
                drift,
                emit_signal=False,
            )
            raise RuntimeError("publish failed after bridge mutation")
        return False

    try:
        monkeypatch.setattr(panel, "_sync_material_batch_selection", reject_publish)

        assert panel._remove_current_profile() is False

        assert panel._profiles == expected_profiles
        assert panel._current_profile_index == selected_index
        assert panel._profile_list.currentRow() == selected_index
        assert panel._profile_name_edit.text() == "Unsaved selected profile"
        assert panel._archive_id_edit.text() == "package-a"
        assert panel._archive_name_edit.text() == "Package A"
        assert panel._task_field_values == {"runtime": "keep"}
        assert panel._last_removed_official_field == {
            "key": "restorable",
            "scope": "fixed",
            "profile_index": selected_index,
        }
        assert [
            panel._profile_list.item(index).checkState()
            for index in range(panel._profile_list.count())
        ] == expected_checks
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def test_profile_remove_persistence_rejection_happens_before_mutation(
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    profiles = copy.deepcopy(panel._profiles)
    published = panel.bridge.current_material_batch_selection()
    try:
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)
        monkeypatch.setattr(
            panel,
            "_sync_material_batch_selection",
            lambda: (_ for _ in ()).throw(
                AssertionError("publish ran after rejected harvest")
            ),
        )

        assert panel._remove_current_profile() is False
        assert panel._profiles == profiles
        assert panel._profile_list.count() == len(profiles)
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def test_archive_projection_duplicate_and_rename_abort_on_persistence_rejection(
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    original_profiles = copy.deepcopy(panel._profiles)
    prompt_calls: list[bool] = []
    try:
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)
        monkeypatch.setattr(
            "src.ui.panels.assets.archive_presenter.input_text",
            lambda *args, **kwargs: prompt_calls.append(True),
        )

        with pytest.raises(
            ProfileEditorPersistenceRejected,
            match="material_profile_editor_persistence_rejected",
        ):
            panel.current_archive()
        panel._duplicate_archive()
        panel._rename_archive()

        assert panel._profiles == original_profiles
        assert prompt_calls == []
    finally:
        panel.close()


def test_batch_projection_is_pure_and_import_preview_abort_without_publishing(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile(profile_id="existing")
    source = tmp_path / "profiles.json"
    source.write_text(
        '{"profiles":[{"profile_id":"imported","profile_name":"Imported"}]}',
        encoding="utf-8",
    )
    original_profiles = copy.deepcopy(panel._profiles)
    published = panel.bridge.current_material_batch_selection()
    try:
        monkeypatch.setattr(
            panel,
            "_persist_current_profile_editor",
            lambda: (_ for _ in ()).throw(AssertionError("pure projection persisted")),
        )
        assert panel.selected_batch_profile_ids() == ["existing"]

        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)
        monkeypatch.setattr(
            "src.ui.panels.assets.batch_output_presenter.build_material_batch_items",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("rejected preview was built")
            ),
        )

        assert panel.batch_output_preview() == []
        assert panel.load_batch_profiles_from_path(source) == []
        assert panel._sync_material_batch_selection() is False
        assert panel._profiles == original_profiles
        assert panel._profile_list.count() == 1
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def test_profile_checkbox_rejection_restores_last_published_selection(
    monkeypatch,
) -> None:
    app = _app()
    panel = _panel_with_profile()
    published = panel.bridge.current_material_batch_selection()
    item = panel._profile_list.item(0)
    assert item is not None
    assert item.checkState() == Qt.Checked
    try:
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)

        item.setCheckState(Qt.Unchecked)
        app.processEvents()

        assert item.checkState() == Qt.Checked
        assert panel.selected_batch_profile_ids() == published.profile_ids
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def test_batch_naming_rejection_restores_template_combo_and_bridge(
    monkeypatch,
) -> None:
    app = _app()
    panel = _panel_with_profile()
    published = panel.bridge.current_material_batch_selection()
    original_index = panel._batch_output_naming_combo.currentIndex()
    try:
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)

        panel._batch_output_template_edit.setText("DRIFT-{profile_id}")
        app.processEvents()

        assert (
            panel._batch_output_template_edit.text()
            == published.output_dir_template
        )
        assert panel._batch_output_template() == published.output_dir_template
        assert panel.bridge.current_material_batch_selection() == published

        target_index = next(
            index
            for index in range(panel._batch_output_naming_combo.count())
            if index != original_index
        )
        panel._batch_output_naming_combo.setCurrentIndex(target_index)
        app.processEvents()

        assert panel._batch_output_naming_combo.currentIndex() == original_index
        assert (
            panel._batch_output_template_edit.text()
            == published.output_dir_template
        )
        assert panel.bridge.current_material_batch_selection() == published
    finally:
        panel.close()


def _prepare_user_material_save(
    panel: AssetsPanel,
    target: Path,
) -> tuple[MaterialPackageLibraryEntry, object, object]:
    entry = MaterialPackageLibraryEntry(
        package_id="package-1",
        name="Package 1",
        path=target,
        mode_id=str(panel.bridge.current_work_mode_id() or ""),
        source_type="user",
    )
    panel._material_persistence.replace_identity(entry, str(target))
    panel._capture_material_persistence_snapshot()
    baseline = copy.deepcopy(panel._persisted_archive_snapshot)
    panel._profile_name_edit.setText("Unsaved profile name")
    expected_editor = copy.deepcopy(panel.current_archive())
    assert panel.prepare_pending_material_changes("save") is True
    return entry, baseline, expected_editor


def test_prepared_material_save_restores_disk_after_post_write_exception(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    root = tmp_path / "material_packages"
    monkeypatch.setattr(material_package_library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    target = root / "custom" / "user" / "package-1" / "package.json"
    target.parent.mkdir(parents=True)
    old_bytes = b'{"version":"old"}'
    new_bytes = b'{"version":"new"}'
    target.write_bytes(old_bytes)
    panel = _panel_with_profile()
    try:
        entry, baseline, expected_editor = _prepare_user_material_save(
            panel,
            target,
        )
        state = panel._prepared_material_changes

        def publish_to_real_disk(archive, current_entry):
            assert current_entry == entry
            target.write_bytes(new_bytes)
            return current_entry

        monkeypatch.setattr(
            "src.ui.panels.assets.persistence_presenter.save_material_package_entry",
            publish_to_real_disk,
        )
        monkeypatch.setattr(
            panel,
            "_capture_material_persistence_snapshot",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("post-write adoption failed")
            ),
        )

        assert panel.commit_prepared_material_changes() is False

        assert target.read_bytes() == old_bytes
        assert panel._current_archive_entry == entry
        assert panel._current_archive_path == str(target)
        assert panel.current_archive() == expected_editor
        assert panel._persisted_archive_snapshot == baseline
        assert panel._prepared_material_changes is None
        assert state["publication_attempted"] is True
        assert state["publication_confirmed"] is True
        assert state["adopted"] is False
        assert state["committed"] is False
    finally:
        panel.close()


def test_prepared_material_save_restores_disk_when_writer_reports_false(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    root = tmp_path / "material_packages"
    monkeypatch.setattr(material_package_library, "MATERIAL_PACKAGE_LIBRARY_DIR", root)
    target = root / "custom" / "user" / "package-1" / "package.json"
    target.parent.mkdir(parents=True)
    old_bytes = b"old bytes"
    target.write_bytes(old_bytes)
    panel = _panel_with_profile()
    try:
        entry, baseline, expected_editor = _prepare_user_material_save(
            panel,
            target,
        )
        state = panel._prepared_material_changes

        def publish_then_report_false() -> bool:
            target.write_bytes(b"new bytes")
            panel._material_change_transaction.record_publication(entry)
            return False

        monkeypatch.setattr(
            panel,
            "save_pending_material_changes",
            publish_then_report_false,
        )

        assert panel.commit_prepared_material_changes() is False

        assert target.read_bytes() == old_bytes
        assert panel._current_archive_entry == entry
        assert panel.current_archive() == expected_editor
        assert panel._persisted_archive_snapshot == baseline
        assert panel._prepared_material_changes is None
        assert state["publication_attempted"] is True
        assert state["publication_confirmed"] is True
        assert state["adopted"] is False
        assert state["committed"] is False
    finally:
        panel.close()


def test_prepared_new_material_save_does_not_delete_unidentified_paths_when_writer_raises(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    user_dir = tmp_path / "user"
    unidentified_target = user_dir / "unidentified-package" / "package.json"
    concurrent_target = user_dir / "concurrent-package" / "package.json"
    panel = _panel_with_profile()
    try:
        panel._material_persistence.replace_identity(None, "")
        panel._capture_material_persistence_snapshot()
        baseline = copy.deepcopy(panel._persisted_archive_snapshot)
        panel._profile_name_edit.setText("Unsaved new package")
        expected_editor = copy.deepcopy(panel.current_archive())
        assert panel.prepare_pending_material_changes("save") is True
        state = panel._prepared_material_changes

        def publish_then_raise(*_args, **_kwargs):
            unidentified_target.parent.mkdir(parents=True)
            unidentified_target.write_bytes(b"published without an identity")
            concurrent_target.parent.mkdir(parents=True)
            concurrent_target.write_bytes(b"concurrent publication")
            raise RuntimeError("writer failed after replace")

        monkeypatch.setattr(
            "src.config.material_package_library."
            "create_material_package_in_library_with_receipt",
            publish_then_raise,
        )

        assert panel.commit_prepared_material_changes() is False

        # Without a returned publication identity the UI cannot distinguish
        # the failed writer's path from a concurrent publisher.  Both must be
        # preserved; the production creator owns cleanup of its exact mkdir.
        assert unidentified_target.read_bytes() == b"published without an identity"
        assert concurrent_target.read_bytes() == b"concurrent publication"
        assert panel._current_archive_entry is None
        assert panel._current_archive_path == ""
        assert panel.current_archive() == expected_editor
        assert panel._persisted_archive_snapshot == baseline
        assert panel._prepared_material_changes is None
        assert state["publication_attempted"] is True
        assert state["publication_confirmed"] is False
        assert state["adopted"] is False
        assert state["committed"] is False
    finally:
        panel.close()


def test_prepared_new_material_save_removes_known_publication_only(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    root = tmp_path / "config_library" / "material_packages"
    monkeypatch.setattr(
        material_package_library,
        "MATERIAL_PACKAGE_LIBRARY_DIR",
        root,
    )
    panel = _panel_with_profile()
    try:
        panel._material_persistence.replace_identity(None, "")
        panel._capture_material_persistence_snapshot()
        panel._profile_name_edit.setText("Unsaved new package")
        expected_editor = copy.deepcopy(panel.current_archive())
        assert panel.prepare_pending_material_changes("save") is True
        state = panel._prepared_material_changes

        mode_id = str(panel.bridge.current_work_mode_id() or "")
        user_dir = material_package_library.material_package_user_dir(mode_id)
        published_target = user_dir / "known-package" / "package.json"
        concurrent_target = user_dir / "concurrent-package" / "package.json"
        published_entry = MaterialPackageLibraryEntry(
            package_id="known-package",
            name="Known package",
            path=published_target,
            mode_id=mode_id,
            source_type="user",
        )

        def publish_known_then_report_false() -> bool:
            published_target.parent.mkdir(parents=True)
            published_target.write_bytes(b"owned publication")
            concurrent_target.parent.mkdir(parents=True)
            concurrent_target.write_bytes(b"concurrent publication")
            panel._material_change_transaction.record_publication(published_entry)
            return False

        monkeypatch.setattr(
            panel,
            "save_pending_material_changes",
            publish_known_then_report_false,
        )

        assert panel.commit_prepared_material_changes() is False

        assert not published_target.parent.exists()
        assert concurrent_target.read_bytes() == b"concurrent publication"
        assert panel._current_archive_entry is None
        assert panel._current_archive_path == ""
        assert panel.current_archive() == expected_editor
        assert panel._prepared_material_changes is None
        assert state["publication_attempted"] is True
        assert state["publication_confirmed"] is True
    finally:
        panel.close()


def test_scene_projection_does_not_replace_rows_after_persistence_rejection(
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    old_slots = panel._asset_slot_specs
    old_groups = panel._asset_group_specs
    old_attachments = panel._attachment_role_specs
    side_effects: list[str] = []
    try:
        monkeypatch.setattr(panel, "_asset_slots_from_scene", lambda _scene: ("new-slot",))
        monkeypatch.setattr(panel, "_asset_groups_from_scene", lambda _scene: ("new-group",))
        monkeypatch.setattr(
            panel,
            "_attachment_roles_from_scene",
            lambda _scene: ("new-attachment",),
        )
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)
        monkeypatch.setattr(
            panel,
            "_sync_asset_slot_rows",
            lambda: side_effects.append("slots"),
        )
        monkeypatch.setattr(
            panel,
            "_sync_asset_group_rows",
            lambda: side_effects.append("groups"),
        )
        monkeypatch.setattr(
            panel,
            "_sync_attachment_role_rows",
            lambda: side_effects.append("attachments"),
        )
        monkeypatch.setattr(panel, "_apply_theme", lambda: side_effects.append("theme"))
        monkeypatch.setattr(
            panel,
            "_refresh_summary",
            lambda: side_effects.append("summary"),
        )
        monkeypatch.setattr(
            panel,
            "_sync_material_batch_selection",
            lambda: side_effects.append("batch"),
        )

        assert panel._on_scene_changed(object()) is False
        assert panel._asset_slot_specs == old_slots
        assert panel._asset_group_specs == old_groups
        assert panel._attachment_role_specs == old_attachments
        assert side_effects == []
    finally:
        panel.close()


def test_mapping_import_restores_profile_and_editor_when_final_commit_fails(
    monkeypatch,
) -> None:
    _app()
    panel = AssetsPanel(PanelBridge())
    panel.set_archive(
        EntityArchive(
            archive_id="package-1",
            profiles=[
                EntityProfile(
                    profile_id="profile-1",
                    fields={"existing": "old value"},
                    field_scopes={"existing": "floating"},
                    declared_field_keys=["existing"],
                )
            ],
        )
    )
    results = [True, False]
    try:
        monkeypatch.setattr(
            panel,
            "_persist_current_profile_editor",
            lambda: results.pop(0) if results else True,
        )

        assert (
            panel._apply_mapping_payload(
                MaterialMappingPayload(entity_data={"imported": "new value"})
            )
            is False
        )
        assert panel._selected_profile().fields == {"existing": "old value"}
        assert panel._editor_fields() == {"existing": "old value"}
        assert panel._manual_field_keys == ["existing"]
    finally:
        panel.close()


def test_image_policy_rejection_restores_rules_and_control_projection(monkeypatch) -> None:
    _app()
    panel = _panel_with_profile()
    panel.current_archive()
    original_rules = copy.deepcopy(panel._image_material_rules)
    original_adaptive = panel._image_rule_adaptive_check.isChecked()
    try:
        blocked = panel._image_rule_adaptive_check.blockSignals(True)
        try:
            panel._image_rule_adaptive_check.setChecked(not original_adaptive)
        finally:
            panel._image_rule_adaptive_check.blockSignals(blocked)
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)

        assert panel._commit_global_image_policy() is False
        assert panel._image_material_rules == original_rules
        assert panel._image_rule_adaptive_check.isChecked() is original_adaptive
    finally:
        panel.close()


def test_question_figure_mutations_roll_back_when_persistence_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    old_path = tmp_path / "old.png"
    new_path = tmp_path / "new.png"
    old_path.write_bytes(b"old")
    new_path.write_bytes(b"new")
    panel = _panel_with_profile()
    panel._asset_item_payloads = [_question_payload(str(old_path))]
    original_payloads = copy.deepcopy(panel._asset_item_payloads)
    try:
        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)

        assert panel._replace_question_figure_item_path(0, str(new_path)) is False
        assert panel._asset_item_payloads == original_payloads

        panel._current_image_preview_question_figure_row = 0
        panel._current_image_preview_compare_options = [
            {
                "reference": str(new_path),
                "display_name": "expected.png",
                "kind_label": "comparison",
            }
        ]
        assert panel._mark_current_full_image_preview_compare_issue() is False
        assert panel._asset_item_payloads == original_payloads
    finally:
        panel.close()


def test_question_library_save_and_history_rollback_are_atomic_on_rejection(
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"image")
    panel = _panel_with_profile()
    current = AssetItem(
        item_id="question-1",
        label="Question 1",
        role="question_figure",
        path=str(image_path),
        metadata={
            "question_index": "1",
            "source": "remote",
            "asset_id": "new-id",
            "alt_text": "new alt",
        },
    )
    history = question_figure_library_metadata_history_record(
        current,
        {
            "question_index": "1",
            "source": "local",
            "asset_id": "old-id",
            "alt_text": "old alt",
        },
        dict(current.metadata),
    )
    assert history is not None
    panel._asset_item_payloads = [asset_item_payload(current)]
    panel._selected_profile().asset_item_history = [history]
    panel._refresh_summary()
    app.processEvents()
    original_payloads = copy.deepcopy(panel._asset_item_payloads)
    original_history = copy.deepcopy(panel._selected_profile().asset_item_history)
    try:
        library_table = panel._question_figure_library_table
        assert library_table.rowCount() == 1
        library_table.setCurrentCell(0, 0)
        panel._select_question_figure_library_row(0)
        panel._question_figure_library_source_edit.setText("edited")
        panel._question_figure_library_alt_text_edit.setText("edited alt")

        monkeypatch.setattr(panel, "_persist_current_profile_editor", lambda: False)

        assert panel._save_question_figure_library_metadata() is False
        assert panel._asset_item_payloads == original_payloads
        assert panel._selected_profile().asset_item_history == original_history

        history_table = panel._question_figure_library_version_history_table
        assert history_table.rowCount() == 1
        assert (
            panel._rollback_question_figure_library_version_history_row(
                0,
                confirmed=True,
            )
            is False
        )
        assert panel._asset_item_payloads == original_payloads
        assert panel._selected_profile().asset_item_history == original_history
    finally:
        panel.close()
        app.processEvents()


def _install_material_batch_publish_failure(
    panel: AssetsPanel,
    monkeypatch,
    failure_mode: str,
) -> list[str]:
    calls: list[str] = []

    def fail_publish() -> bool:
        calls.append("publish")
        if failure_mode == "changed_then_exception":
            panel.bridge.set_current_material_batch_selection(
                MaterialBatchSelection(package_id="drifted")
            )
            raise RuntimeError("injected material batch publish failure")
        return False

    monkeypatch.setattr(panel, "_sync_material_batch_selection", fail_publish)
    return calls


@pytest.mark.parametrize("failure_mode", ["false", "changed_then_exception"])
def test_apply_current_profile_keeps_context_batch_and_navigation_atomic(
    failure_mode: str,
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    panel._profile_name_edit.setText("Unsaved draft")
    original_context = panel.bridge.current_material_context()
    original_selection = panel.bridge.current_material_batch_selection()
    navigation: list[int] = []
    observed_selections: list[MaterialBatchSelection] = []
    panel.bridge.navigate_to_panel.connect(navigation.append)
    panel.bridge.material_batch_selection_changed.connect(observed_selections.append)
    calls = _install_material_batch_publish_failure(
        panel,
        monkeypatch,
        failure_mode,
    )
    try:
        assert panel._open_batch_generation() is False
        assert calls == ["publish"]
        assert panel.bridge.current_material_context() == original_context
        assert panel.bridge.current_material_batch_selection() == original_selection
        assert panel._selected_profile().profile_name == "Unsaved draft"
        assert navigation == []
        if failure_mode == "changed_then_exception":
            assert observed_selections[-2].package_id == "drifted"
            assert observed_selections[-1] == original_selection
        else:
            assert observed_selections == []
    finally:
        panel.close()


def test_apply_current_profile_rebroadcasts_context_and_batch_recovery(
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    panel._profile_name_edit.setText("Changed profile")
    original_context = panel.bridge.current_material_context()
    original_selection = panel.bridge.current_material_batch_selection()
    observed_contexts = []
    observed_selections: list[MaterialBatchSelection] = []
    panel.bridge.material_context_changed.connect(observed_contexts.append)
    panel.bridge.material_batch_selection_changed.connect(observed_selections.append)
    real_set_context = panel.bridge.set_current_material_context
    calls = 0

    def set_context_then_raise(context, **kwargs):
        nonlocal calls
        calls += 1
        result = real_set_context(context, **kwargs)
        if calls == 1:
            raise RuntimeError("injected context publish failure")
        return result

    monkeypatch.setattr(
        panel.bridge,
        "set_current_material_context",
        set_context_then_raise,
    )
    try:
        assert panel._apply_current_profile() is False
        assert calls == 2
        assert panel.bridge.current_material_context() == original_context
        assert panel.bridge.current_material_batch_selection() == original_selection
        assert observed_contexts[0] != original_context
        assert observed_contexts[-1] == original_context
        assert observed_selections[-1] == original_selection
    finally:
        panel.close()


@pytest.mark.parametrize("failure_mode", ["false", "changed_then_exception"])
@pytest.mark.parametrize(
    "operation",
    ["add", "copy", "batch_import", "attachment_preparation"],
)
def test_profile_structure_entrypoints_restore_model_list_and_batch_on_publish_failure(
    operation: str,
    failure_mode: str,
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    role = "attachment1"
    if operation == "attachment_preparation":
        source = tmp_path / "attachment.pdf"
        source.write_bytes(b"%PDF-1.4\n%%EOF")
        panel._attachment_bindings[role] = build_attachment_binding(
            role=role,
            source_paths=(source,),
            accepted_types=("pdf",),
            cardinality="single",
            source_kind="single_file",
            label=role,
        )
        assert panel._persist_current_profile_editor() is True

        class FakeDialog:
            def __init__(self, *, profiles, **_kwargs):
                self._profiles = profiles

            @staticmethod
            def exec():
                return 1

            def result_profiles(self):
                result = copy.deepcopy(self._profiles)
                result[0].profile_name = "Prepared mutation"
                return result

            @staticmethod
            def profiles_replaced():
                return False

        monkeypatch.setattr(
            "src.ui.panels.assets.attachment_preparation_presenter."
            "AttachmentPreparationDialog",
            FakeDialog,
        )
    elif operation == "batch_import":
        monkeypatch.setattr(
            "src.ui.panels.assets.batch_output_presenter."
            "_load_batch_profiles_from_path",
            lambda _path: [
                EntityProfile(profile_id="imported", profile_name="Imported")
            ],
        )

    original_profiles = copy.deepcopy(panel._profiles)
    original_index = panel._current_profile_index
    original_selection = panel.bridge.current_material_batch_selection()
    original_checks = [
        panel._profile_list.item(index).checkState()
        for index in range(panel._profile_list.count())
    ]
    calls = _install_material_batch_publish_failure(
        panel,
        monkeypatch,
        failure_mode,
    )
    try:
        if operation == "add":
            result = panel._add_profile()
        elif operation == "copy":
            result = panel._copy_current_profile()
        elif operation == "batch_import":
            result = panel.load_batch_profiles_from_path(tmp_path / "unused.json")
        else:
            result = panel._open_attachment_preparation(role)

        assert result is False or result == []
        assert calls == ["publish"]
        assert panel._profiles == original_profiles
        assert panel._current_profile_index == original_index
        assert panel._profile_list.count() == len(original_profiles)
        assert [
            panel._profile_list.item(index).checkState()
            for index in range(panel._profile_list.count())
        ] == original_checks
        assert panel.bridge.current_material_batch_selection() == original_selection
    finally:
        panel.close()


@pytest.mark.parametrize("failure_mode", ["false", "changed_then_exception"])
@pytest.mark.parametrize("operation", ["mapping", "image_policy"])
def test_mapping_and_image_policy_restore_editor_profile_and_batch_on_publish_failure(
    operation: str,
    failure_mode: str,
    monkeypatch,
) -> None:
    _app()
    panel = AssetsPanel(PanelBridge())
    panel.set_archive(
        EntityArchive(
            archive_id="package-1",
            profiles=[
                EntityProfile(
                    profile_id="profile-1",
                    fields={"existing": "old value"},
                    field_scopes={"existing": "floating"},
                    declared_field_keys=["existing"],
                )
            ],
        )
    )
    if operation == "image_policy":
        panel._asset_slot_specs = (
            AssetSlotSpec(
                role="logo",
                label="Logo",
                target="{{@img:logo}}",
            ),
        )
        panel._sync_image_material_rule_rows()
        assert panel._persist_current_profile_editor() is True
        blocked = panel._image_rule_adaptive_check.blockSignals(True)
        try:
            panel._image_rule_adaptive_check.setChecked(
                not panel._image_rule_adaptive_check.isChecked()
            )
        finally:
            panel._image_rule_adaptive_check.blockSignals(blocked)

    original_profile = copy.deepcopy(panel._selected_profile())
    original_fields = panel._editor_fields()
    original_manual_keys = list(panel._manual_field_keys)
    original_rules = copy.deepcopy(panel._image_material_rules)
    original_selection = panel.bridge.current_material_batch_selection()
    original_adaptive = (
        panel._strategy_from_material_rules(panel._image_rule_specs())
        == panel._ADAPTIVE_STRATEGY
    )
    calls = _install_material_batch_publish_failure(
        panel,
        monkeypatch,
        failure_mode,
    )
    try:
        if operation == "mapping":
            result = panel._apply_mapping_payload(
                MaterialMappingPayload(entity_data={"imported": "new value"})
            )
        else:
            result = panel._commit_global_image_policy()

        assert result is False
        assert calls == ["publish"]
        assert panel._selected_profile() == original_profile
        assert panel.bridge.current_material_batch_selection() == original_selection
        if operation == "mapping":
            assert panel._editor_fields() == original_fields
            assert panel._manual_field_keys == original_manual_keys
        else:
            assert panel._image_material_rules == original_rules
            assert panel._image_rule_adaptive_check.isChecked() is original_adaptive
    finally:
        panel.close()


@pytest.mark.parametrize("failure_mode", ["false", "changed_then_exception"])
@pytest.mark.parametrize("operation", ["replace", "save", "history"])
def test_question_figure_entrypoints_restore_payload_history_draft_and_batch_on_publish_failure(
    operation: str,
    failure_mode: str,
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    old_path = tmp_path / "old.png"
    new_path = tmp_path / "new.png"
    old_path.write_bytes(b"old")
    new_path.write_bytes(b"new")
    panel = _panel_with_profile()
    current = AssetItem(
        item_id="question-1",
        label="Question 1",
        role="question_figure",
        path=str(old_path),
        metadata={
            "question_index": "1",
            "source": "remote",
            "asset_id": "new-id",
            "alt_text": "new alt",
        },
    )
    history = question_figure_library_metadata_history_record(
        current,
        {
            "question_index": "1",
            "source": "local",
            "asset_id": "old-id",
            "alt_text": "old alt",
        },
        dict(current.metadata),
    )
    assert history is not None
    panel._asset_item_payloads = [asset_item_payload(current)]
    panel._selected_profile().asset_item_history = [history]
    panel._refresh_summary()
    app.processEvents()
    library_table = panel._question_figure_library_table
    library_table.setCurrentCell(0, 0)
    panel._select_question_figure_library_row(0)
    if operation == "save":
        panel._question_figure_library_source_edit.setText("draft source")
        panel._question_figure_library_asset_id_edit.setText("draft id")
        panel._question_figure_library_alt_text_edit.setText("draft alt")
    elif operation == "history":
        panel._question_figure_library_version_history_table.setCurrentCell(0, 0)

    original_payloads = copy.deepcopy(panel._asset_item_payloads)
    original_history = copy.deepcopy(panel._selected_profile().asset_item_history)
    original_selection = panel.bridge.current_material_batch_selection()
    original_library_status = panel._question_figure_library_status_label.text()
    original_draft = (
        panel._question_figure_library_source_edit.text(),
        panel._question_figure_library_asset_id_edit.text(),
        panel._question_figure_library_alt_text_edit.text(),
    )
    calls = _install_material_batch_publish_failure(
        panel,
        monkeypatch,
        failure_mode,
    )
    try:
        if operation == "replace":
            result = panel._replace_question_figure_item_path(0, str(new_path))
        elif operation == "save":
            result = panel._save_question_figure_library_metadata()
        else:
            result = panel._rollback_question_figure_library_version_history_row(
                0,
                confirmed=True,
            )

        assert result is False
        assert calls == ["publish"]
        assert panel._asset_item_payloads == original_payloads
        assert panel._selected_profile().asset_item_history == original_history
        assert panel.bridge.current_material_batch_selection() == original_selection
        assert panel._question_figure_library_status_label.text() == original_library_status
        assert (
            panel._question_figure_library_source_edit.text(),
            panel._question_figure_library_asset_id_edit.text(),
            panel._question_figure_library_alt_text_edit.text(),
        ) == original_draft
    finally:
        panel.close()
        app.processEvents()


def test_question_repair_audit_write_failure_keeps_visible_in_memory_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    old_path = tmp_path / "old.png"
    new_path = tmp_path / "new.png"
    old_path.write_bytes(b"old")
    new_path.write_bytes(b"new")
    history_path = tmp_path / "question_figure_repair_audit.json"
    corrupt_history = b'{"schema_version":1,"records":['
    history_path.write_bytes(corrupt_history)
    panel = _panel_with_profile()
    panel._asset_item_payloads = [_question_payload(str(old_path))]
    warnings: list[str] = []
    monkeypatch.setattr(
        "src.ui.panels.assets.question_figure_repair_actions_presenter."
        "Toast.show_warning",
        warnings.append,
    )
    candidate = {
        "confirmation_status": "ready",
        "confirmation_apply_supported": True,
        "replacement_source_path": str(new_path),
        "replacement_source_kind": "local_file",
        "repair_target_key": json.dumps(
            {
                "role": "question_figure",
                "item_id": "question-1",
                "question_index": "1",
                "path": str(old_path),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    try:
        assert (
            panel.apply_question_figure_repair_candidate(
                candidate,
                confirmed=True,
            )
            is True
        )
        applied_record = panel.current_question_figure_repair_audit_records()[0]
        assert applied_record["action"] == "frontstage_question_figure_repair_apply"
        assert applied_record["artifact_path"] == ""
        assert applied_record["audit_persistence_status"] == "failed"
        assert panel._asset_item_payloads[0]["path"] == str(new_path)
        assert (
            panel.bridge.current_material_batch_selection()
            .archive.profiles[0]
            .asset_items[0]["path"]
            == str(new_path)
        )

        assert (
            panel.revert_question_figure_repair_audit_record(
                applied_record,
                confirmed=True,
            )
            is True
        )
        records = panel.current_question_figure_repair_audit_records()
        assert records[-1]["action"] == "frontstage_question_figure_repair_rollback"
        assert records[-1]["artifact_path"] == ""
        assert records[-1]["audit_persistence_status"] == "failed"
        assert panel._asset_item_payloads[0]["path"] == str(old_path)
        assert (
            panel.bridge.current_material_batch_selection()
            .archive.profiles[0]
            .asset_items[0]["path"]
            == str(old_path)
        )
        assert len(warnings) == 2
        assert all("当前会话" in message for message in warnings)
        assert history_path.read_bytes() == corrupt_history
    finally:
        panel.close()


def test_question_library_save_and_history_rollback_publish_success_once_each(
    tmp_path,
) -> None:
    app = _app()
    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"image")
    panel = _panel_with_profile()
    current = AssetItem(
        item_id="question-1",
        label="Question 1",
        role="question_figure",
        path=str(image_path),
        metadata={
            "question_index": "1",
            "source": "remote",
            "asset_id": "asset-1",
            "alt_text": "old alt",
        },
    )
    panel._asset_item_payloads = [asset_item_payload(current)]
    panel._refresh_summary()
    app.processEvents()
    published: list[MaterialBatchSelection] = []
    panel.bridge.material_batch_selection_changed.connect(published.append)
    try:
        table = panel._question_figure_library_table
        table.setCurrentCell(0, 0)
        panel._select_question_figure_library_row(0)
        panel._question_figure_library_source_edit.setText("edited")
        panel._question_figure_library_alt_text_edit.setText("edited alt")

        assert panel._save_question_figure_library_metadata() is True
        assert len(published) == 1
        assert panel._asset_item_payloads[0]["metadata"]["source"] == "edited"
        assert panel._asset_item_payloads[0]["metadata"]["alt_text"] == "edited alt"

        history_table = panel._question_figure_library_version_history_table
        assert history_table.rowCount() == 1
        assert (
            panel._rollback_question_figure_library_version_history_row(
                0,
                confirmed=True,
            )
            is True
        )
        assert len(published) == 2
        assert panel._asset_item_payloads[0]["metadata"]["source"] == "remote"
        assert panel._asset_item_payloads[0]["metadata"]["alt_text"] == "old alt"
        bridge_payload = (
            panel.bridge.current_material_batch_selection()
            .archive.profiles[0]
            .asset_items[0]
        )
        assert bridge_payload["metadata"]["source"] == "remote"
        assert bridge_payload["metadata"]["alt_text"] == "old alt"
    finally:
        panel.close()
        app.processEvents()


def test_material_mutation_transaction_success_publishes_exactly_once() -> None:
    calls: list[str] = []
    snapshot = capture_material_mutation_snapshot(
        local_state={"value": "old"},
        profile_state=EntityProfile(profile_id="profile-1"),
        profile_index=0,
        batch_selection=MaterialBatchSelection(package_id="package-1"),
    )

    assert publish_or_rollback_material_mutation(
        snapshot,
        publish=lambda: calls.append("publish") or True,
        restore_selection=lambda _selection: calls.append("selection"),
        restore_profile=lambda _index, _profile: calls.append("profile"),
        restore_local=lambda _state: calls.append("local"),
        refresh=lambda: calls.append("refresh"),
    ) is True
    assert calls == ["publish"]


def test_material_mutation_transaction_restores_internal_state_before_bridge(
    caplog,
) -> None:
    calls: list[str] = []
    snapshot = capture_material_mutation_snapshot(
        local_state={"value": "old"},
        profile_state=EntityProfile(profile_id="profile-1"),
        profile_index=0,
        batch_selection=MaterialBatchSelection(package_id="package-1"),
    )

    def publish_then_raise() -> bool:
        calls.append("publish")
        raise RuntimeError("Bridge changed before failure")

    with caplog.at_level("WARNING"):
        assert publish_or_rollback_material_mutation(
            snapshot,
            publish=publish_then_raise,
            restore_selection=lambda _selection: calls.append("selection"),
            restore_profile=lambda _index, _profile: calls.append("profile"),
            restore_local=lambda _state: calls.append("local"),
            refresh=lambda: calls.append("refresh"),
        ) is False

    assert calls == ["publish", "profile", "local", "refresh", "selection"]
    assert "Bridge changed before failure" in caplog.text


def test_material_mutation_entrypoints_keep_one_checked_publish_gate() -> None:
    targets = {
        Path("src/ui/panels/assets/asset_file_operations_presenter.py"): {
            "_apply_attachment_paths": {
                "_attachment_role_specs",
                "_attachment_bindings",
                "_asset_paths",
                "_attachment_legacy_errors",
            },
            "_apply_asset_slot_path": {"_asset_paths"},
            "_clear_asset_file": {"_asset_paths"},
            "_clear_attachment_file": {
                "_attachment_bindings",
                "_asset_paths",
                "_attachment_legacy_errors",
            },
        },
        Path("src/ui/panels/assets/asset_group_rows_presenter.py"): {
            "_apply_asset_group_directory": {"_asset_bindings"},
            "_refresh_asset_group_binding": {"_asset_bindings"},
            "_clear_asset_group_binding": {"_asset_bindings"},
        },
        Path("src/ui/panels/assets/content_materials_presenter.py"): {
            "_insert_content_material": {"_content_rules"},
            "_commit_content_material_token": {
                "_content_bindings",
                "_content_rules",
            },
            "_bind_content_material_path": {"_content_bindings"},
            "_clear_content_material_file": {"_content_bindings"},
            "_remove_content_material": {
                "_content_bindings",
                "_content_rules",
            },
        },
    }

    for path, functions in targets.items():
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for function_name, owned_attributes in functions.items():
            function = next(
                node
                for node in ast.walk(module)
                if isinstance(node, ast.FunctionDef) and node.name == function_name
            )
            calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
            publish_gates = [
                node
                for node in calls
                if isinstance(node.func, ast.Name)
                and node.func.id == "publish_or_rollback_material_mutation"
            ]
            capture_calls = [
                node
                for node in calls
                if isinstance(node.func, ast.Attribute)
                and node.func.attr.startswith("_capture_")
                and node.func.attr.endswith("_mutation_snapshot")
            ]
            direct_sync_calls = [
                node
                for node in calls
                if isinstance(node.func, ast.Attribute)
                and node.func.attr == "_sync_material_batch_selection"
            ]
            assert len(publish_gates) == 1, (path, function_name)
            assert len(capture_calls) == 1, (path, function_name)
            assert direct_sync_calls == [], (path, function_name)
            publish_keyword = next(
                keyword
                for keyword in publish_gates[0].keywords
                if keyword.arg == "publish"
            )
            assert isinstance(publish_keyword.value, ast.Attribute)
            assert publish_keyword.value.attr == "_sync_material_batch_selection"

            mutation_lines: list[int] = []
            for node in ast.walk(function):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets_to_check = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    if any(
                        isinstance(descendant, ast.Attribute)
                        and descendant.attr in owned_attributes
                        for target in targets_to_check
                        for descendant in ast.walk(target)
                    ):
                        mutation_lines.append(node.lineno)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr
                    in {"pop", "insert", "append", "clear", "update"}
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr in owned_attributes
                ):
                    mutation_lines.append(node.lineno)
            assert mutation_lines, (path, function_name)
            assert (
                capture_calls[0].lineno
                < min(mutation_lines)
                < publish_gates[0].lineno
            ), (path, function_name)


def test_scene_spec_mutations_use_one_explicit_transaction_gate() -> None:
    path = Path("src/ui/panels/assets/scene_spec_presenter.py")
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets = {
        "_on_scene_changed": {
            "_asset_slot_specs",
            "_asset_group_specs",
            "_attachment_role_specs",
        },
        "_insert_asset_slot": {"_asset_slot_specs"},
        "_commit_asset_slot_token": {"_asset_slot_specs"},
        "_commit_asset_slot_label": {"_asset_slot_specs"},
        "_remove_asset_slot": {
            "_asset_paths",
            "_asset_bindings",
            "_image_material_rules",
            "_asset_item_payloads",
            "_asset_slot_specs",
        },
        "_insert_asset_group": {"_asset_group_specs"},
        "_commit_asset_group_token": {"_asset_group_specs"},
        "_commit_asset_group_label": {"_asset_group_specs"},
        "_remove_asset_group": {
            "_asset_bindings",
            "_image_material_rules",
            "_asset_paths",
            "_asset_item_payloads",
            "_asset_group_specs",
        },
        "_request_attachment_role": {"_attachment_role_specs"},
        "_add_attachment_role_series": {"_attachment_role_specs"},
        "_remove_attachment_role": {
            "_attachment_bindings",
            "_attachment_legacy_errors",
            "_asset_metadata",
            "_attachment_role_specs",
        },
        "_commit_attachment_role_token": {
            "_attachment_bindings",
            "_attachment_legacy_errors",
            "_attachment_role_specs",
        },
        "_commit_attachment_role_label": {
            "_attachment_bindings",
            "_attachment_role_specs",
        },
    }

    functions = {
        node.name: node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
    }
    for function_name, owned_attributes in targets.items():
        function = functions[function_name]
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        capture_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "_capture_scene_spec_mutation_snapshot"
        ]
        publish_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "_publish_scene_spec_mutation"
        ]
        success_refresh_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "_refresh_scene_spec_mutation_ui"
        ]
        ignored_sync_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "_sync_material_batch_selection"
        ]
        assert len(capture_calls) == 1, function_name
        assert len(publish_calls) == 1, function_name
        assert len(success_refresh_calls) == 1, function_name
        assert ignored_sync_calls == [], function_name

        mutation_lines: list[int] = []
        for node in ast.walk(function):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets_to_check = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if any(
                    isinstance(descendant, ast.Attribute)
                    and descendant.attr in owned_attributes
                    for target in targets_to_check
                    for descendant in ast.walk(target)
                ):
                    mutation_lines.append(node.lineno)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr
                in {"pop", "insert", "append", "clear", "update"}
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr in owned_attributes
            ):
                mutation_lines.append(node.lineno)
        assert mutation_lines, function_name
        assert (
            capture_calls[0].lineno
            < min(mutation_lines)
            < publish_calls[0].lineno
            < success_refresh_calls[0].lineno
        ), function_name

    wrapper = functions["_publish_scene_spec_mutation"]
    wrapper_gates = [
        node
        for node in ast.walk(wrapper)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "publish_or_rollback_material_mutation"
    ]
    assert len(wrapper_gates) == 1
    publish_keyword = next(
        item for item in wrapper_gates[0].keywords if item.arg == "publish"
    )
    assert isinstance(publish_keyword.value, ast.Attribute)
    assert publish_keyword.value.attr == "_sync_material_batch_selection"


def _material_mutation_local_state(panel: AssetsPanel) -> dict[str, object]:
    return copy.deepcopy(
        {
            "asset_paths": panel._asset_paths,
            "attachment_bindings": panel._attachment_bindings,
            "attachment_legacy_errors": panel._attachment_legacy_errors,
            "attachment_role_specs": panel._attachment_role_specs,
            "asset_bindings": panel._asset_bindings,
            "content_bindings": panel._content_bindings,
            "content_rules": panel._content_rules,
            "preview": (
                panel._current_image_preview_path,
                panel._current_image_preview_display_name,
                panel._current_image_preview_compare_reference,
                panel._current_image_preview_compare_source,
                panel._current_image_preview_compare_display_name,
                panel._current_image_preview_compare_options,
                panel._current_image_preview_question_figure_row,
            ),
            "preview_status": panel._image_assets_status_label.text(),
        }
    )


@pytest.mark.parametrize("failure_mode", ["false", "changed_then_exception"])
def test_all_remaining_material_mutations_restore_every_boundary_on_publish_failure(
    failure_mode: str,
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    panel = _panel_with_profile()
    original_sync = panel._sync_material_batch_selection
    role = "attachment1"
    content_id = "content1"
    attachment_spec = AttachmentRoleSpec(
        role=role,
        label=role,
        accepted_types=("pdf",),
        origin="profile",
    )
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "renamed.pdf"
    old_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    new_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    old_attachment = build_attachment_binding(
        role=role,
        source_paths=(old_pdf,),
        accepted_types=("pdf",),
        cardinality="single",
        source_kind="single_file",
        label=role,
    )
    old_image = tmp_path / "old.png"
    new_image = tmp_path / "new.png"
    old_image.write_bytes(b"old")
    new_image.write_bytes(b"new")
    old_group_dir = tmp_path / "old-group"
    new_group_dir = tmp_path / "new-group"
    old_group_dir.mkdir()
    new_group_dir.mkdir()
    old_group = AssetBinding(
        role="qualification",
        cardinality="multiple",
        source_kind="directory",
        source_path=str(old_group_dir),
        recursive=True,
        max_items=None,
    )
    rule = ContentInsertionRule(
        rule_id=f"content:{content_id}",
        content_id=content_id,
        anchor_token=content_anchor_token(content_id),
    )
    old_content = ContentMaterialBinding(
        content_id=content_id,
        label="Old content",
        artifact_ref=ContentArtifactRef("a" * 64, "b" * 64),
    )
    new_content_ref = ContentArtifactRef("c" * 64, "d" * 64)
    monkeypatch.setattr(
        "src.ui.panels.assets.content_materials_presenter.compile_content_material",
        lambda _path, _repository: SimpleNamespace(
            blocked=False,
            artifact_ref=new_content_ref,
            findings=(),
        ),
    )
    monkeypatch.setattr(
        "src.ui.panels.assets.content_materials_presenter.confirm",
        lambda *_args, **_kwargs: True,
    )

    row_calls: list[tuple[str, str]] = []
    summary_calls: list[str] = []
    monkeypatch.setattr(
        panel,
        "_sync_attachment_role_rows",
        lambda: row_calls.append(("asset_file", "")),
    )
    monkeypatch.setattr(
        panel,
        "_refresh_asset_group_row",
        lambda selected_role: row_calls.append(("asset_group", selected_role)),
    )
    monkeypatch.setattr(
        panel,
        "_sync_content_material_rows",
        lambda: row_calls.append(("content", "")),
    )
    monkeypatch.setattr(
        panel,
        "_refresh_summary",
        lambda: summary_calls.append("summary"),
    )

    active_cluster = {"name": ""}
    expected_profile: dict[str, EntityProfile | None] = {"value": None}
    publish_count = 0
    profile_was_mutated: list[bool] = []

    def reject_publish() -> bool:
        nonlocal publish_count
        publish_count += 1
        assert panel._persist_current_profile_editor() is True
        profile_was_mutated.append(
            panel._selected_profile() != expected_profile["value"]
        )
        if active_cluster["name"] == "asset_file":
            panel._current_image_preview_path = "publish-drift.png"
            panel._current_image_preview_display_name = "publish drift"
            panel._current_image_preview_compare_reference = "drift-reference"
            panel._current_image_preview_compare_source = "drift-source"
            panel._current_image_preview_compare_display_name = "drift compare"
            panel._current_image_preview_compare_options = [
                {"reference": "drift-reference"}
            ]
            panel._current_image_preview_question_figure_row = 99
            panel._image_assets_status_label.setText("publish drift")
        if failure_mode == "changed_then_exception":
            drift = panel.bridge.current_material_batch_selection()
            drift.package_id = "bridge-drift"
            drift.profile_ids = []
            panel.bridge.set_current_material_batch_selection(
                drift,
                emit_signal=False,
            )
            raise RuntimeError("publish failed after changing Bridge")
        return False

    monkeypatch.setattr(panel, "_sync_material_batch_selection", reject_publish)

    operations = (
        (
            "attachment_apply",
            "asset_file",
            lambda: panel._apply_attachment_paths(role, (str(new_pdf),)),
        ),
        (
            "single_image_apply",
            "asset_file",
            lambda: panel._apply_asset_slot_path("logo", str(new_image)),
        ),
        ("image_clear", "asset_file", lambda: panel._clear_asset_file("logo")),
        (
            "attachment_clear",
            "asset_file",
            lambda: panel._clear_attachment_file(role),
        ),
        (
            "directory_apply",
            "asset_group",
            lambda: panel._apply_asset_group_directory(
                "qualification",
                str(new_group_dir),
            ),
        ),
        (
            "directory_clear",
            "asset_group",
            lambda: panel._clear_asset_group_binding("qualification"),
        ),
        (
            "content_bind",
            "content",
            lambda: panel._bind_content_material_path(content_id, "source.md"),
        ),
        (
            "content_clear",
            "content",
            lambda: panel._clear_content_material_file(content_id),
        ),
        (
            "content_remove",
            "content",
            lambda: panel._remove_content_material(content_id),
        ),
    )

    try:
        for operation_name, cluster, invoke in operations:
            panel._asset_paths = {
                "logo": str(old_image),
                role: "legacy-attachment-path",
            }
            panel._attachment_bindings = {role: old_attachment}
            panel._attachment_legacy_errors = {role: "legacy error"}
            panel._attachment_role_specs = (attachment_spec,)
            panel._asset_bindings = {"qualification": old_group}
            panel._content_bindings = {content_id: old_content}
            panel._content_rules = [rule]
            panel._current_image_preview_path = str(old_image)
            panel._current_image_preview_display_name = operation_name
            panel._current_image_preview_compare_reference = "old-reference"
            panel._current_image_preview_compare_source = "old-source"
            panel._current_image_preview_compare_display_name = "old compare"
            panel._current_image_preview_compare_options = [
                {"reference": "old-reference", "label": operation_name}
            ]
            panel._current_image_preview_question_figure_row = 7
            panel._image_assets_status_label.setText(
                f"preview baseline: {operation_name}"
            )
            panel._store_attachment_role_inventory()
            assert panel._persist_current_profile_editor() is True
            assert original_sync() is True

            expected_local = _material_mutation_local_state(panel)
            expected_profile["value"] = copy.deepcopy(panel._selected_profile())
            expected_selection = panel.bridge.current_material_batch_selection()
            active_cluster["name"] = cluster
            row_calls.clear()
            summary_calls.clear()
            before_publish_count = publish_count

            assert invoke() is False, operation_name
            assert publish_count == before_publish_count + 1, operation_name
            assert profile_was_mutated[-1] is True, operation_name
            assert _material_mutation_local_state(panel) == expected_local, operation_name
            assert panel._selected_profile() == expected_profile["value"], operation_name
            assert (
                panel.bridge.current_material_batch_selection() == expected_selection
            ), operation_name
            assert summary_calls == ["summary"], operation_name
            assert row_calls == [
                (
                    cluster,
                    "qualification" if cluster == "asset_group" else "",
                )
            ], operation_name

        assert publish_count == len(operations)
    finally:
        panel.close()
