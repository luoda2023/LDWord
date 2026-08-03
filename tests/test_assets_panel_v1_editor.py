from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.application.materials import (
    MaterialPackageService,
    default_material_contract_id,
    get_package_material_contract,
    project_material_preview,
)
from src.config import material_package_library
from src.config.material_schema_registry import MaterialAssetRoleSpec
from src.domain.materials import (
    MaterialDerivationSpec,
    MaterialPackage,
    MaterialRecord,
    MaterialScope,
    MaterialTimelineSpec,
    generate_package_id,
    generate_record_id,
)
from src.qt_api import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QInputDialog,
    QLineEdit,
    Qt,
    QWidget,
)
from src.shared.ui.master_detail_shell import MasterDetailShell
from src.shared.ui.persistence_actions import PersistenceActions
from src.ui.bridge import PanelBridge
from src.ui.panels.assets_panel import AssetsPanel
from src.ui.panels.material_legacy_rows import (
    LegacyContentTokenRow,
    LegacyFieldTokenRow,
    LegacyImageGroupTokenRow,
    LegacySingleImageTokenRow,
)
from src.ui.workspace_preferences import WorkspacePreferenceStore


def _create_user_package(
    name: str,
    *,
    with_test_fields: bool = True,
    shared_fields: dict[str, str] | None = None,
) -> MaterialPackage:
    metadata = {}
    if with_test_fields:
        metadata = {
            "material_contract_extensions": {
                "fields": [
                    {
                        "key": key,
                        "label": key,
                        "required": False,
                        "allowed_scopes": ["shared", "group", "record", "run"],
                    }
                    for key in ("title", "body")
                ],
                "resource_roles": [],
                "image_policy": {},
            }
        }
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name=name,
        work_mode_id="custom",
        material_contract_id=default_material_contract_id("custom"),
        shared_scope=MaterialScope(fields=dict(shared_fields or {})),
        records=(
            MaterialRecord(
                record_id=generate_record_id(),
                display_name="记录 1",
                lifecycle="active",
            ),
        ),
        metadata=metadata,
    )
    material_package_library.material_package_repository().create_user(package)
    return package


def _panel_for(package: MaterialPackage) -> AssetsPanel:
    panel = AssetsPanel(PanelBridge())
    panel._reload_library(package.package_id)
    assert panel._package is not None
    assert panel._package.package_id == package.package_id
    return panel


def test_assets_panel_preserves_scope_after_a_field_edit(qapp):
    package = _create_user_package("作用域测试")
    panel = _panel_for(package)
    shared_index = panel._scope.findData(("shared", ""))
    panel._scope.setCurrentIndex(shared_index)
    field = get_package_material_contract(package).fields[0]

    result = panel._service().set_field(
        panel._package,
        owner_scope="shared",
        owner_id="",
        key=field.key,
        value="共享值",
        provenance="test",
    )

    assert panel._apply_result(result)
    assert panel._scope.currentData() == ("shared", "")
    assert panel._package.shared_scope.fields[field.key] == "共享值"


def test_assets_panel_cancelled_package_switch_keeps_dirty_draft(qapp, monkeypatch):
    first = _create_user_package("资料包 A")
    second = _create_user_package("资料包 B")
    panel = _panel_for(first)
    field = get_package_material_contract(first).fields[0]
    record_id = panel._current_record_id
    assert panel._apply_result(
        panel._service().set_field(
            panel._package,
            owner_scope="record",
            owner_id=record_id,
            key=field.key,
            value="不能丢",
        )
    )
    monkeypatch.setattr(
        panel,
        "_prompt_pending_material_action",
        lambda _reason: "cancel",
    )

    panel._package_combo.setCurrentIndex(
        panel._package_combo.findData(second.package_id)
    )

    assert panel._package.package_id == first.package_id
    assert panel._package_combo.currentData() == first.package_id
    assert panel.has_pending_material_changes() is True
    assert panel._package.get_record(record_id).scope.fields[field.key] == "不能丢"


def test_deleting_current_package_does_not_fall_back_to_default(
    qapp,
    tmp_path,
    monkeypatch,
):
    package = _create_user_package("待删除资料包")
    store = WorkspacePreferenceStore(tmp_path / "workspace-preferences.json")
    panel = AssetsPanel(PanelBridge(workspace_preference_store=store))
    panel._reload_library(package.package_id)
    monkeypatch.setattr(
        "src.ui.panels.assets_panel.confirm",
        lambda *_args, **_kwargs: True,
    )

    panel._delete_package()

    preference = store.load().for_mode("custom")
    assert panel._package_combo.currentData() == ""
    assert panel._package is None
    assert preference is not None
    assert preference.material_enabled is False
    assert preference.material_package_id == ""


def test_assets_panel_exposes_v1_material_domains(qapp):
    package = _create_user_package("分区测试")
    panel = _panel_for(package)

    assert isinstance(panel._shell, MasterDetailShell)
    assert tuple(panel._section_nav_cards) == (
        "generate",
        "fields",
        "content",
        "timeline",
        "images",
        "attachments",
    )
    assert panel._section_nav_cards["generate"]._title.text() == "资料包概览"
    assert panel._section_nav_cards["fields"]._title.text() == "字段资料"
    assert panel._section_nav_cards["content"]._title.text() == "文件资料"
    assert panel._detail_stack.currentWidget() is panel._section_pages["generate"]
    assert set(panel._resource_tables) == {"content", "image", "attachment"}
    assert panel._overview_preview_table.columnCount() == 3
    assert panel._overview_preview_table.rowCount() >= 1
    assert panel._overview_preview_table.item(0, 0).text().startswith("{{@text:")
    assert panel._image_rules_card.parent() is panel._section_pages["images"]
    assert panel._image_card.parent() is panel._section_pages["images"]
    assert not panel._image_card.isAncestorOf(panel._image_rules_table)
    assert panel._content_rules_card.parent() is panel._section_pages["content"]
    assert panel._content_card.parent() is panel._section_pages["content"]
    assert panel._attachment_card.parent() is panel._section_pages["attachments"]
    assert "可编辑" in panel._source_banner.text()


def test_overview_keeps_management_compact_and_restores_header_persistence(qapp):
    package = _create_user_package("总览层级")
    panel = _panel_for(package)

    assert panel._archive_card._description_label is None
    assert panel._mode_label.isHidden()
    assert panel._status.isHidden()
    assert panel._source_banner.isHidden()
    assert panel._overview_summary.isHidden()
    assert panel._new_package_button.text() == "新建"
    assert panel._duplicate_button.text() == "复制"
    assert panel._rename_package_button.text() == "重命名"
    assert panel._open_package_folder_button.text() == "打开文件夹"
    assert panel._delete_button.text() == "删除"
    assert not panel._archive_card.isAncestorOf(panel._save_button)
    assert set(panel._persistence_actions) == {
        "fields",
        "content",
        "timeline",
        "images",
        "attachments",
    }
    for actions in panel._persistence_actions.values():
        assert isinstance(actions, PersistenceActions)
        assert actions.restore_button.text() == "恢复"
        assert actions.save_button.text() == "保存"
    image_actions = panel._persistence_actions["images"]
    assert panel._image_rules_card.isAncestorOf(image_actions)
    assert not panel._image_card.isAncestorOf(image_actions)
    content_actions = panel._persistence_actions["content"]
    assert panel._content_rules_card.isAncestorOf(content_actions)
    assert not panel._content_card.isAncestorOf(content_actions)


def test_section_restore_keeps_other_v1_draft_sections(qapp):
    package = _create_user_package("分区恢复")
    panel = _panel_for(package)
    record_id = panel._current_record_id
    field = get_package_material_contract(package).fields[0]

    assert panel._apply_result(
        panel._service().set_field(
            panel._package,
            owner_scope="record",
            owner_id=record_id,
            key=field.key,
            value="保留字段草稿",
        )
    )
    assert panel._apply_result(
        panel._service().set_image_policy(
            panel._package,
            adaptive=True,
            watermark_enabled=False,
            watermark_source="fixed",
            watermark_text="",
            show_single_image_name=True,
            show_multi_image_name=False,
        )
    )
    assert panel._persistence_actions["fields"].restore_button.isEnabled()
    assert panel._persistence_actions["images"].restore_button.isEnabled()

    assert panel._restore_section_draft("images")
    assert panel._package.get_record(record_id).scope.fields[field.key] == "保留字段草稿"
    assert not panel._persistence_actions["images"].restore_button.isEnabled()
    assert panel._persistence_actions["fields"].restore_button.isEnabled()
    assert panel.has_pending_material_changes()

    assert panel._restore_section_draft("fields")
    assert panel._package == panel._snapshot.package
    assert not panel.has_pending_material_changes()


def test_single_and_multi_image_name_switches_update_independently(qapp):
    package = _create_user_package("图片名称开关")
    panel = _panel_for(package)

    policy_layout = panel._image_rule_adaptive_check.parentWidget().layout()
    strategy_layout = policy_layout.itemAt(0).layout()
    assert all(
        strategy_layout.indexOf(control) >= 0
        for control in (
            panel._image_rule_adaptive_check,
            panel._image_rule_page_break_after_check,
            panel._image_rule_single_name_check,
            panel._image_rule_multi_name_check,
        )
    )
    assert panel._image_rule_single_name_check.isChecked() is False
    assert panel._image_rule_multi_name_check.isChecked() is False
    assert panel._image_rule_page_break_after_check.isChecked() is False

    panel._image_rule_multi_name_check.setChecked(True)
    panel._image_rule_page_break_after_check.setChecked(True)

    policy = panel._package.metadata["material_contract_extensions"][
        "image_policy"
    ]
    assert policy["show_single_image_name"] is False
    assert policy["show_multi_image_name"] is True
    assert policy["page_break_after_images"] is True
    assert panel.has_pending_material_changes() is True


def test_file_rules_card_persists_plain_text_policy_and_restores_as_one_section(
    qapp,
):
    package = _create_user_package("文件规则")
    panel = _panel_for(package)

    assert panel._content_rule_target_radio.isChecked()
    assert not panel._content_rule_plain_radio.isChecked()
    assert not panel._content_rule_source_radio.isEnabled()
    assert panel._content_rule_source_radio.isHidden()
    assert not hasattr(panel, "_content_rule_description")
    policy_layout = panel._content_rule_target_radio.parentWidget().layout()
    format_layout = policy_layout.itemAt(0).layout()
    assert format_layout.indexOf(panel._content_rule_source_radio) == -1
    behavior_layout = policy_layout.itemAt(1).layout()
    assert behavior_layout.count() == 2
    assert behavior_layout.itemAt(0).widget() is panel._content_rule_page_break_check
    assert behavior_layout.itemAt(1).spacerItem() is not None
    assert panel._content_rules_card.isAncestorOf(
        panel._persistence_actions["content"]
    )

    panel._content_rule_plain_radio.setChecked(True)

    policy = panel._package.metadata["material_contract_extensions"][
        "content_policy"
    ]
    assert policy == {
        "format_mode": "plain_text",
        "page_break_policy": "drop",
    }
    assert panel._persistence_actions["content"].restore_button.isEnabled()

    assert panel._restore_section_draft("content")
    assert panel._content_rule_target_radio.isChecked()
    assert not panel._persistence_actions["content"].restore_button.isEnabled()


def test_image_watermark_font_defaults_to_simsun_and_updates_policy(qapp):
    package = _create_user_package("图片水印字体")
    panel = _panel_for(package)

    policy_layout = panel._image_rule_adaptive_check.parentWidget().layout()
    watermark_layout = policy_layout.itemAt(1).layout()
    watermark_font_layout = policy_layout.itemAt(2).layout()
    assert watermark_layout.indexOf(panel._image_rule_watermark_edit) >= 0
    assert watermark_layout.indexOf(panel._image_rule_watermark_font_label) < 0
    assert watermark_layout.indexOf(panel._image_rule_watermark_font) < 0
    assert watermark_font_layout.indexOf(panel._image_rule_watermark_font_label) >= 0
    assert watermark_font_layout.indexOf(panel._image_rule_watermark_font) >= 0
    assert panel._image_rule_watermark_font.selected_font() == "宋体"
    assert panel._image_rule_watermark_font.isEnabled() is False

    panel._image_rule_watermark_check.setChecked(True)
    panel._image_rule_watermark_font.set_font_name("黑体")

    policy = panel._package.metadata["material_contract_extensions"][
        "image_policy"
    ]
    assert panel._image_rule_watermark_font.isEnabled() is True
    assert policy["watermark_font"] == "黑体"


def test_image_folder_import_freezes_natural_number_order(qapp, tmp_path):
    package = _create_user_package("图片自然排序")
    panel = _panel_for(package)
    initial_preview_height = panel._overview_preview_table.height()
    role = "现场照片"
    assert panel._apply_result(
        panel._service().add_resource_role_definition(
            panel._package,
            role=role,
            label="现场照片",
            domain="image",
            max_items=None,
            source_kind="directory",
            recursive=True,
        )
    )
    folder = tmp_path / "images"
    folder.mkdir()
    for name, color in (
        ("photo10.png", "navy"),
        ("photo2.png", "teal"),
        ("photo1.png", "purple"),
    ):
        Image.new("RGB", (32, 32), color).save(folder / name)

    panel._bind_resource_paths(
        "image",
        role,
        (str(folder),),
        source_kind="directory",
    )

    owner_scope, owner_id = panel._selected_scope()
    binding = panel._scope_object(owner_scope, owner_id).resources[role]
    assert [item.original_name for item in binding.items] == [
        "photo1.png",
        "photo2.png",
        "photo10.png",
    ]
    preview_rows = {
        panel._overview_preview_table.item(row, 0).text(): row
        for row in range(panel._overview_preview_table.rowCount())
    }
    image_row = preview_rows["{{@img:现场照片}}"]
    image_preview = panel._overview_preview_table.item(image_row, 1)
    assert image_preview.text() == (
        "3 张图片 · photo1.png、photo2.png、photo10.png"
    )
    assert image_preview.toolTip().splitlines() == [
        "photo1.png",
        "photo2.png",
        "photo10.png",
    ]
    assert panel._overview_preview_table.item(image_row, 2).text() == "已绑定"
    assert panel._overview_preview_table.height() > initial_preview_height
    assert (
        panel._overview_preview_table.verticalScrollBarPolicy()
        == Qt.ScrollBarAlwaysOff
    )
    assert (
        panel._overview_preview_table.minimumHeight()
        == panel._overview_preview_table.maximumHeight()
    )


def test_overview_generation_check_stays_detached_and_hidden(qapp):
    package = _create_user_package("隐藏生成检查")
    panel = _panel_for(package)

    assert panel._section_layouts["generate"].indexOf(panel._preview_card) == -1
    assert panel._preview_card.isHidden()

    panel._refresh_scope_views()

    assert panel._section_layouts["generate"].indexOf(panel._preview_card) == -1
    assert panel._preview_card.isHidden()


def test_assets_panel_restores_legacy_token_row_views_on_v1(qapp):
    package = _create_user_package("旧版三级界面")
    panel = _panel_for(package)

    assert panel._apply_result(
        panel._service().add_field_definition(
            panel._package,
            key="客户名称",
            label="客户名称",
        )
    )
    assert panel._apply_result(
        panel._service().add_resource_role_definition(
            panel._package,
            role="文件1",
            label="文件1",
            domain="content",
        )
    )
    assert panel._apply_result(
        panel._service().add_resource_role_definition(
            panel._package,
            role="单图1",
            label="单图1",
            domain="image",
            max_items=1,
            source_kind="file",
        )
    )
    assert panel._apply_result(
        panel._service().add_resource_role_definition(
            panel._package,
            role="多图文件夹1",
            label="多图文件夹1",
            domain="image",
            max_items=None,
            source_kind="directory",
            recursive=True,
        )
    )

    assert isinstance(panel._legacy_field_rows["客户名称"], LegacyFieldTokenRow)
    assert isinstance(
        panel._legacy_resource_rows["content"]["文件1"],
        LegacyContentTokenRow,
    )
    assert isinstance(
        panel._legacy_resource_rows["image"]["多图文件夹1"],
        LegacyImageGroupTokenRow,
    )
    assert isinstance(
        panel._legacy_resource_rows["image"]["单图1"],
        LegacySingleImageTokenRow,
    )
    assert panel._fields.isHidden()
    assert panel._resource_tables["content"].isHidden()
    assert panel._resource_section_headers[
        ("image", "folder")
    ].title_label.text() == "多图文件夹"
    assert panel._resource_section_headers[
        ("image", "folder")
    ].count_label.text() == "1 项"
    folder_row = panel._legacy_resource_rows["image"]["多图文件夹1"]
    assert folder_row.refresh_button is not None
    assert folder_row.actions.button("refresh") is folder_row.refresh_button
    assert folder_row.preview_label.size().width() == 52
    assert folder_row.preview_label.size().height() == 52
    single_rows = tuple(
        row
        for row in panel._legacy_resource_rows["image"].values()
        if row.property("materialSection") == "single"
    )
    folder_rows = tuple(
        row
        for row in panel._legacy_resource_rows["image"].values()
        if row.property("materialSection") == "folder"
    )
    assert [row.index_label.text() for row in single_rows] == [
        str(index) for index in range(1, len(single_rows) + 1)
    ]
    assert [row.index_label.text() for row in folder_rows] == ["1"]
    assert panel._resource_column_guides[
        ("image", "folder")
    ]._action_count == 6


def test_custom_field_editor_starts_empty_and_adds_inline_like_file_materials(
    qapp,
    monkeypatch,
):
    package = _create_user_package("空白字段资料", with_test_fields=False)
    panel = _panel_for(package)

    def unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("inline field add must not open an input dialog")

    monkeypatch.setattr(QInputDialog, "getText", unexpected_dialog)
    assert get_package_material_contract(panel._package).fields == ()
    assert panel._legacy_field_rows == {}
    assert not panel._add_material_field_button.isHidden()
    assert panel._fixed_field_header.title_label.text() == "固定字段"
    assert panel._floating_field_header.title_label.text() == "自由字段"
    assert panel._add_material_field_button.text() == "＋ 新增固定字段"
    assert (
        panel._add_floating_material_field_button.text()
        == "＋ 新增自由字段"
    )
    assert panel._profile_card.isAncestorOf(panel._add_material_field_button)

    panel._request_add_field_definition()

    assert tuple(panel._legacy_field_rows) == ("固定字段1",)
    first = panel._legacy_field_rows["固定字段1"]
    assert first.token_edit.isTokenEditable()
    assert first.add_button.isEnabled()
    assert not first.remove_button.isHidden()

    first.add_requested.emit(first.key)

    assert tuple(panel._legacy_field_rows) == ("固定字段1", "固定字段2")
    assert panel.has_pending_material_changes()


def test_free_field_group_is_runtime_owned_and_projected_to_workbench(qapp):
    package = _create_user_package("自由字段资料", with_test_fields=False)
    panel = _panel_for(package)

    panel._request_add_field_definition("floating")

    assert tuple(panel._legacy_field_rows) == ("自由字段1",)
    row = panel._legacy_field_rows["自由字段1"]
    assert panel._legacy_field_scopes["自由字段1"] == "floating"
    assert row.value_edit.isReadOnly()
    assert row.value_edit.placeholderText() == "在工作台填写"
    assert row.token_edit.isTokenEditable()
    definition = panel._package.metadata["material_contract_extensions"][
        "fields"
    ][0]
    assert definition["value_source"] == "floating"
    assert definition["allowed_scopes"] == ["run"]

    preview = project_material_preview(
        panel._package,
        revision="draft",
        source_type="user",
        contract=get_package_material_contract(panel._package),
        current_record_id=panel._current_record_id,
    )
    assert [item.key for item in preview.runtime_fields] == ["自由字段1"]


def test_custom_field_editor_preserves_used_legacy_generic_fields(qapp):
    package = _create_user_package(
        "旧字段兼容",
        with_test_fields=False,
        shared_fields={"title": "旧资料仍保留"},
    )
    panel = _panel_for(package)

    assert [
        field.key for field in get_package_material_contract(panel._package).fields
    ] == ["title"]
    assert panel._legacy_field_rows["title"].value_edit.text() == "旧资料仍保留"

    panel._clear_legacy_field_value("title")

    assert get_package_material_contract(panel._package).fields == ()
    assert panel._legacy_field_rows == {}


def test_inline_image_add_does_not_open_input_dialogs(qapp, monkeypatch):
    package = _create_user_package("图片新增不弹窗")
    panel = _panel_for(package)

    def unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("inline image add must not open an input dialog")

    monkeypatch.setattr(QInputDialog, "getText", unexpected_dialog)
    monkeypatch.setattr(QInputDialog, "getItem", unexpected_dialog)
    before = len(panel._legacy_resource_rows["image"])
    before_roles = set(panel._legacy_resource_rows["image"])

    panel._request_add_resource_role("image", "file")

    assert len(panel._legacy_resource_rows["image"]) == before + 1
    assert panel._creating_resource_role is False
    created_role = (
        set(panel._legacy_resource_rows["image"]) - before_roles
    ).pop()
    created_row = panel._legacy_resource_rows["image"][created_role]
    assert created_row.token_edit._expanded_popup is None
    assert created_row.name_edit._expanded_popup is None
    assert not any(
        widget.objectName() in {"asset_slot_row", "asset_group_row"}
        for widget in QApplication.topLevelWidgets()
    )


def test_attachment_rebuild_never_promotes_rows_to_pythonw_windows(qapp):
    package = _create_user_package("附件新增不产生空白窗口")
    panel = _panel_for(package)
    panel.resize(1200, 820)
    panel._on_section_selected("attachments")
    panel.show()
    qapp.processEvents()
    before = len(panel._legacy_resource_rows["attachment"])

    panel._request_add_resource_role("attachment", "file")
    panel._request_add_resource_role("attachment", "directory")

    assert len(panel._legacy_resource_rows["attachment"]) == before + 2
    assert not any(
        widget.objectName()
        in {
            "asset_slot_row",
            "asset_group_row",
            "material_v1_field_token_row",
            "timeline_segment_row",
        }
        for widget in QApplication.topLevelWidgets()
    )


def test_classic_image_rows_keep_file_and_folder_drag_drop(qapp, tmp_path):
    package = _create_user_package("图片拖放")
    panel = _panel_for(package)
    owner_scope, owner_id = panel._selected_scope()

    before_roles = set(panel._legacy_resource_rows["image"])
    panel._request_add_resource_role("image", "file")
    single_role = (
        set(panel._legacy_resource_rows["image"]) - before_roles
    ).pop()
    single_row = panel._legacy_resource_rows["image"][single_role]
    image_path = tmp_path / "证书.png"
    image_path.write_bytes(b"not-a-rendered-image")
    assert single_row._material_path_drop_controller.accepts_path(
        str(image_path)
    )
    single_row._material_path_drop_controller.paths_dropped.emit(
        (str(image_path),)
    )

    single_binding = panel._scope_object(owner_scope, owner_id).resources[single_role]
    assert single_binding.items[0].original_name == "证书.png"
    assert panel._legacy_resource_rows["image"][
        single_role
    ].path_edit.text() == str(image_path)

    before_roles = set(panel._legacy_resource_rows["image"])
    panel._request_add_resource_role("image", "directory")
    folder_role = (
        set(panel._legacy_resource_rows["image"]) - before_roles
    ).pop()
    folder_row = panel._legacy_resource_rows["image"][folder_role]
    image_directory = tmp_path / "多图来源"
    image_directory.mkdir()
    (image_directory / "第一页.png").write_bytes(b"first")
    (image_directory / "第二页.jpg").write_bytes(b"second")
    assert folder_row._material_path_drop_controller.accepts_path(
        str(image_directory)
    )
    folder_row._material_path_drop_controller.paths_dropped.emit(
        (str(image_directory),)
    )

    folder_binding = panel._scope_object(owner_scope, owner_id).resources[folder_role]
    assert [item.original_name for item in folder_binding.items] == [
        "第一页.png",
        "第二页.jpg",
    ]
    assert panel._package.metadata["material_resource_authoring_sources"][
        folder_role
    ][f"{owner_scope}:{owner_id}"] == str(image_directory)


def test_derivation_add_uses_one_editor_instead_of_dialog_chain(
    qapp,
    monkeypatch,
):
    from src.ui.panels import assets_panel as assets_panel_module

    package = _create_user_package("计算字段单窗口")
    panel = _panel_for(package)
    contract = get_package_material_contract(panel._package)
    output = contract.fields[0].key
    source = contract.fields[-1].key
    instances: list[object] = []

    class FakeDerivationEditor:
        def __init__(self, keys, parent):
            assert tuple(keys)
            assert parent is panel
            instances.append(self)

        def exec(self):
            return QDialog.Accepted

        def output_field(self):
            return output

        def specification(self):
            return MaterialDerivationSpec(
                output_field=output,
                preset_id="copy",
                preset_version=1,
                input_fields=(source,),
            )

    def unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("derivation add must not open chained input dialogs")

    monkeypatch.setattr(
        assets_panel_module,
        "_DerivationEditorDialog",
        FakeDerivationEditor,
    )
    monkeypatch.setattr(QInputDialog, "getText", unexpected_dialog)
    monkeypatch.setattr(QInputDialog, "getItem", unexpected_dialog)

    panel._add_derivation()

    owner_scope, owner_id = panel._selected_scope()
    assert len(instances) == 1
    assert output in panel._scope_object(owner_scope, owner_id).derivations


def test_classic_field_page_hides_record_administration_but_keeps_field_add(qapp):
    package = _create_user_package("旧版字段页")
    panel = _panel_for(package)

    assert panel._profile_list_card.isHidden()
    assert panel._record_card.isHidden()
    assert panel._profile_form.parent() is panel._profile_card
    assert panel._profile_name_row.parent() is panel._profile_form
    assert panel._profile_form.isHidden()
    assert panel._field_mapping_example.isHidden()
    assert not panel._add_material_field_button.isHidden()
    assert not panel._add_floating_material_field_button.isHidden()
    assert panel._profile_card.isAncestorOf(panel._add_material_field_button)


def test_classic_timeline_shows_record_plan_independent_of_hidden_v1_scope(qapp):
    package = _create_user_package("旧版时间计划")
    panel = _panel_for(package)
    contract = get_package_material_contract(package)
    output = contract.fields[0].key
    anchor = contract.fields[-1].key
    record_id = panel._current_record_id
    assert panel._apply_result(
        panel._service().set_timeline(
            panel._package,
            owner_scope="record",
            owner_id=record_id,
            key=output,
            specification=MaterialTimelineSpec(
                output_field=output,
                preset_id="date_offset_days",
                preset_version=1,
                anchor_field=anchor,
                parameters={"days": "5"},
            ),
        )
    )

    panel._scope.setCurrentIndex(
        panel._scope.findData(("shared", ""))
    )

    assert len(panel._timeline_segment_rows) == 1
    assert panel._timeline_empty_label.isHidden()
    assert next(iter(panel._timeline_segment_rows)).endswith(f":{output}")
    timeline_row = next(iter(panel._timeline_segment_rows.values()))
    assert timeline_row.property("tokenRowHover") is False
    assert timeline_row.findChild(QFrame, "timeline_segment_header") is not None


def test_classic_timeline_add_edit_and_remove_compile_to_v1(qapp):
    package = _create_user_package("旧版时间段编辑")
    panel = _panel_for(package)

    panel._add_timeline()

    owner_scope, owner_id = panel._selected_scope()
    scope = panel._scope_object(owner_scope, owner_id)
    assert len(scope.timelines) == 2
    assert tuple(scope.timelines) == ("时间节点1-1", "时间节点1-2")
    projection = panel._visible_timeline_segments()[0]
    assert projection.ratio_based
    assert projection.start_field == "时间段1_开始"
    assert projection.end_field == "时间段1_结束"
    assert len(panel._timeline_segment_rows) == 1
    timeline_row = next(iter(panel._timeline_segment_rows.values()))
    assert timeline_row.property("tokenRowHover") is False
    assert timeline_row.findChild(QFrame, "timeline_segment_header") is not None
    assert len(
        [
            row
            for row in timeline_row.findChildren(type(timeline_row))
            if row.objectName() == "timeline_node_row"
        ]
    ) == 2

    panel._commit_ratio_timeline_dates(
        projection,
        "2026-08-01",
        "2026-08-10",
    )

    scope = panel._scope_object(owner_scope, owner_id)
    assert scope.fields["时间段1_开始"] == "2026-08-01"
    assert scope.fields["时间段1_结束"] == "2026-08-10"
    resolution = panel._resolved_record(panel._current_record_id)
    assert resolution.record is not None
    assert resolution.record.field_values["时间节点1-1"] == "2026-08-01"
    assert resolution.record.field_values["时间节点1-2"] == "2026-08-10"

    panel._resize_ratio_timeline_segment(projection, 4)
    projection = panel._visible_timeline_segments()[0]
    assert len(projection.nodes) == 4
    timeline_row = next(iter(panel._timeline_segment_rows.values()))
    position_values = [
        node_row.findChild(QLineEdit, "timeline_node_position").text()
        for node_row in timeline_row.findChildren(QFrame)
        if node_row.objectName() == "timeline_node_row"
    ]
    assert position_values == ["0", "33.3", "66.7", "100"]
    panel._commit_ratio_timeline_position(
        projection,
        "时间节点1-2",
        "25",
    )
    projection = panel._visible_timeline_segments()[0]
    assert projection.nodes[1][1].parameters["ratio"] == "0.25"
    panel._update_ratio_timeline_settings(
        projection,
        weekend_adjust="forward",
        output_format="yyyy年MM月dd日",
    )
    projection = panel._visible_timeline_segments()[0]
    assert all(
        specification.parameters["weekend_adjust"] == "forward"
        and specification.parameters["output_format"] == "yyyy年MM月dd日"
        for _key, specification in projection.nodes
    )
    panel._update_ratio_timeline_settings(
        projection,
        input_scope="floating",
    )
    projection = panel._visible_timeline_segments()[0]
    scope = panel._scope_object(owner_scope, owner_id)
    assert "时间段1_开始" not in scope.fields
    assert "时间段1_结束" not in scope.fields
    assert all(
        specification.parameters["input_scope"] == "floating"
        for _key, specification in projection.nodes
    )

    panel._remove_ratio_timeline_segment(projection)
    contract = get_package_material_contract(panel._package)
    assert contract.get_field("时间段1_开始") is None
    assert contract.get_field("时间段1_结束") is None
    assert contract.get_field("时间节点1-4") is None
    assert panel._scope_object(owner_scope, owner_id).timelines == {}


def test_timeline_date_range_waits_for_both_inputs_before_committing(qapp):
    package = _create_user_package("时间段支持分步填写")
    panel = _panel_for(package)
    panel._add_timeline()

    timeline_row = next(iter(panel._timeline_segment_rows.values()))
    start_edit = timeline_row.findChild(
        QLineEdit,
        "timeline_segment_start_date",
    )
    end_edit = timeline_row.findChild(
        QLineEdit,
        "timeline_segment_end_date",
    )
    assert start_edit is not None
    assert end_edit is not None

    start_edit.setText("2026-08-01")
    start_edit.editingFinished.emit()

    assert start_edit.text() == "2026-08-01"
    assert end_edit.text() == ""
    assert next(iter(panel._timeline_segment_rows.values())) is timeline_row

    end_edit.setText("2026-08-10")
    end_edit.editingFinished.emit()

    owner_scope, owner_id = panel._selected_scope()
    scope = panel._scope_object(owner_scope, owner_id)
    assert scope.fields["时间段1_开始"] == "2026-08-01"
    assert scope.fields["时间段1_结束"] == "2026-08-10"


def test_timeline_refresh_is_atomic_and_preserves_expansion_state(
    qapp,
    monkeypatch,
):
    package = _create_user_package("时间段刷新不闪烁")
    panel = _panel_for(package)
    panel._add_timeline()
    panel._on_section_selected("timeline")

    timeline_row = next(iter(panel._timeline_segment_rows.values()))
    body = timeline_row.findChild(QWidget, "timeline_segment_body")
    assert body is not None
    body.hide()

    update_states: list[tuple[bool, bool]] = []
    original_rebuild = panel._rebuild_calculations

    def observe_atomic_rebuild(expanded_state):
        update_states.append(
            (
                panel._timeline_segments_container.updatesEnabled(),
                panel._detail_scroll.viewport().updatesEnabled(),
            )
        )
        original_rebuild(expanded_state)

    monkeypatch.setattr(panel, "_rebuild_calculations", observe_atomic_rebuild)
    panel._refresh_calculations()

    refreshed_row = next(iter(panel._timeline_segment_rows.values()))
    refreshed_body = refreshed_row.findChild(QWidget, "timeline_segment_body")
    assert update_states == [(False, False)]
    assert refreshed_body is not None
    assert refreshed_body.isHidden()
    assert panel._timeline_segments_container.updatesEnabled()
    assert panel._detail_scroll.viewport().updatesEnabled()


def test_legacy_folder_row_imports_files_into_v1_object_store(
    qapp,
    tmp_path,
    monkeypatch,
):
    package = _create_user_package("文件夹资料")
    panel = _panel_for(package)
    assert panel._apply_result(
        panel._service().add_resource_role_definition(
            panel._package,
            role="附件文件夹1",
            label="附件文件夹1",
            domain="attachment",
            max_items=None,
            source_kind="directory",
            recursive=True,
        )
    )
    folder = tmp_path / "delivery"
    folder.mkdir()
    (folder / "a.pdf").write_bytes(b"a")
    nested = folder / "nested"
    nested.mkdir()
    (nested / "b.txt").write_bytes(b"b")
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(folder),
    )

    panel._bind_resource_role("attachment", "附件文件夹1")

    owner_scope, owner_id = panel._selected_scope()
    binding = panel._scope_object(owner_scope, owner_id).resources[
        "附件文件夹1"
    ]
    assert {item.original_name for item in binding.items} == {"a.pdf", "b.txt"}
    row = panel._legacy_resource_rows["attachment"]["附件文件夹1"]
    assert not row.items_table.isHidden()
    assert row.items_table.rowCount() == 2
    assert {
        row.items_table.item(index, 1).text()
        for index in range(row.items_table.rowCount())
    } == {"a.pdf", "b.txt"}

    (nested / "c.csv").write_bytes(b"c")
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("refresh must reuse the selected source directory")
        ),
    )
    row.refresh_requested.emit("附件文件夹1")

    refreshed = panel._scope_object(owner_scope, owner_id).resources[
        "附件文件夹1"
    ]
    assert {item.original_name for item in refreshed.items} == {
        "a.pdf",
        "b.txt",
        "c.csv",
    }
    refreshed_row = panel._legacy_resource_rows["attachment"]["附件文件夹1"]
    assert refreshed_row.items_table.rowCount() == 3


def test_legacy_assets_ui_reference_remains_complete():
    root = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "ui_reference"
        / "assets_legacy_ui"
    )
    sources = tuple(root.glob("*.py"))

    assert len(sources) == 53
    assert (root / "README.md").is_file()
    assert (root / "section_shell_presenter.py").is_file()
    assert (root / "theme_presenter.py").is_file()
    assert (root / "content_materials_presenter.py").is_file()
    assert (root / "timeline_presenter.py").is_file()
    assert (root / "image_inventory_presenter.py").is_file()
    assert (root / "attachment_inventory_presenter.py").is_file()


def test_classic_image_page_binds_resource_through_v1_service(
    qapp,
    tmp_path,
    monkeypatch,
):
    package = _create_user_package("图片绑定测试")
    panel = _panel_for(package)
    image = tmp_path / "logo.png"
    image.write_bytes(b"not-a-decoded-image-but-a-valid-package-object")
    table = panel._resource_tables["image"]
    assert table.rowCount() >= 1
    table.selectRow(0)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(image), ""),
    )

    panel._bind_resource("image")

    owner_scope, owner_id = panel._selected_scope()
    scope = panel._scope_object(owner_scope, owner_id)
    assert "logo" in scope.resources
    assert scope.resources["logo"].items[0].original_name == "logo.png"
    assert panel.has_pending_material_changes() is True


def test_material_service_can_remove_derivation_and_timeline():
    package = _create_user_package("计算测试")
    repository = material_package_library.material_package_repository()
    service = MaterialPackageService(repository)
    record_id = package.records[0].record_id
    contract = get_package_material_contract(package)
    output = contract.fields[0].key
    source = contract.fields[-1].key
    derived = service.set_derivation(
        package,
        owner_scope="record",
        owner_id=record_id,
        key=output,
        specification=MaterialDerivationSpec(
            output_field=output,
            preset_id="copy",
            preset_version=1,
            input_fields=(source,),
        ),
    ).package
    assert derived is not None
    timed = service.set_timeline(
        derived,
        owner_scope="record",
        owner_id=record_id,
        key=source,
        specification=MaterialTimelineSpec(
            output_field=source,
            preset_id="date_offset_days",
            preset_version=1,
            anchor_field=output,
            parameters={"days": "3"},
        ),
    ).package
    assert timed is not None

    without_derivation = service.remove_derivation(
        timed,
        owner_scope="record",
        owner_id=record_id,
        key=output,
    ).package
    assert without_derivation is not None
    without_timeline = service.remove_timeline(
        without_derivation,
        owner_scope="record",
        owner_id=record_id,
        key=source,
    ).package

    assert without_timeline is not None
    scope = without_timeline.get_record(record_id).scope
    assert output not in scope.derivations
    assert source not in scope.timelines


def test_schema_registry_accepts_content_resource_domain():
    role = MaterialAssetRoleSpec(
        role="source_document",
        label="内容来源文件",
        required=False,
        accepted_types=("text/plain",),
        material_domain="content",
    )

    assert role.material_domain == "content"
