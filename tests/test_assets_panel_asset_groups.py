from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtTest import QTest

from src.config.asset_resolution import refresh_asset_binding
from src.config.entity import AssetBinding, EntityArchive, EntityProfile
from src.config.scene import SceneWorkspace
from src.qt_api import QLabel, QPoint, QSizePolicy, Qt
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.assets import asset_file_operations_presenter
from src.ui.panels.assets_panel import AssetsPanel


def _bidding_panel() -> AssetsPanel:
    scene = SceneWorkspace()
    scene.input_source_profile.material_schema_id = "bid_materials_v1"
    bridge = PanelBridge()
    bridge.set_current_scene(scene, config_id="bidding", emit_signal=False)
    return AssetsPanel(bridge)


def _single_row_visual_signature(panel: AssetsPanel, role: str) -> tuple[object, ...]:
    thumbnail = panel._asset_slot_thumbnail_labels[role]
    index = panel._asset_slot_index_labels[role]
    path = panel._asset_slot_path_edits[role]
    return (
        thumbnail.styleSheet(),
        index.styleSheet(),
        path.displaySurface().styleSheet(),
        path.property("sizeClass"),
        thumbnail.size(),
        thumbnail.text(),
    )


def test_assets_panel_splits_single_slots_from_multi_image_folders(qapp):
    panel = _bidding_panel()

    single_roles = {spec.role for spec in panel._asset_slot_specs}
    group_roles = {spec.role for spec in panel._asset_group_specs}

    assert "logo" in single_roles
    assert "seal" in single_roles
    assert "qualification" not in single_roles
    assert group_roles == {"qualification"}
    assert panel._single_assets_title.text() == "单图"
    assert panel._asset_groups_title.text() == "多图文件夹"
    assert panel._asset_groups_count.text() == "1 项"
    assert "qualification" in panel._asset_group_rows
    assert panel._assets_picker.isHidden()
    assert panel._image_assets_status_label.isHidden()
    assert panel._add_single_asset_btn.text() == "＋ 新增单图"
    assert panel._add_asset_group_btn.text() == "＋ 新增多图文件夹"
    assert panel._asset_slot_index_labels["logo"].text() == "1"
    assert panel._asset_group_index_labels["qualification"].text() == "1"
    assert panel._asset_slot_target_edits["logo"].text() == "{{@img:LOGO1}}"
    assert panel._asset_slot_target_edits["seal"].text() == "{{@img:公章1}}"
    assert panel._asset_slot_rows["logo"].findChild(
        QLabel, "asset_slot_title"
    ) is None
    assert panel._asset_slot_name_edits["logo"].text() == "Logo"
    assert panel._asset_group_token_edits["qualification"].text() == "{{@img:资质证书1}}"
    assert panel._asset_group_name_edits["qualification"].text() == "资质证书"
    assert panel._asset_group_status_labels["qualification"].isHidden()

    panel.resize(1300, 900)
    panel.show()
    panel._on_section_selected("images")
    qapp.processEvents()

    expected_height = resolved_control_height(get_theme(), "md")
    assert panel._single_assets_title.parentWidget().height() == expected_height
    assert panel._add_single_asset_btn.height() == expected_height
    assert panel._timeline_card._header_widget.sizeHint().height() == expected_height
    strip = panel._asset_slot_action_strips["logo"]
    assert strip.width() == (
        get_theme().compact_action_size * 5
        + get_theme().compact_action_gap * 4
    )

    single_guide = panel._asset_slots_column_guide
    single_role = panel._asset_slot_specs[0].role
    assert single_guide.maximumHeight() == 32
    assert single_guide.name_label.text() == "名称"
    assert panel._asset_slot_target_edits[single_role].mapTo(panel, QPoint(0, 0)).x() == (
        single_guide.token_label.mapTo(panel, QPoint(0, 0)).x()
    )
    assert panel._asset_slot_name_edits[single_role].mapTo(panel, QPoint(0, 0)).x() == (
        single_guide.name_label.mapTo(panel, QPoint(0, 0)).x()
    )
    assert panel._asset_slot_path_widgets[single_role].mapTo(panel, QPoint(0, 0)).x() == (
        single_guide.source_label.mapTo(panel, QPoint(0, 0)).x()
    )
    assert panel._asset_slot_action_cells[single_role].mapTo(panel, QPoint(0, 0)).x() == (
        single_guide.actions_label.mapTo(panel, QPoint(0, 0)).x()
    )

    group_guide = panel._asset_groups_column_guide
    assert group_guide.maximumHeight() == 32
    assert panel._asset_group_token_edits["qualification"].mapTo(panel, QPoint(0, 0)).x() == (
        group_guide.token_label.mapTo(panel, QPoint(0, 0)).x()
    )
    assert panel._asset_group_name_edits["qualification"].mapTo(panel, QPoint(0, 0)).x() == (
        group_guide.name_label.mapTo(panel, QPoint(0, 0)).x()
    )
    assert panel._asset_group_path_widgets["qualification"].mapTo(panel, QPoint(0, 0)).x() == (
        group_guide.source_label.mapTo(panel, QPoint(0, 0)).x()
    )
    assert panel._asset_group_action_cells["qualification"].mapTo(panel, QPoint(0, 0)).x() == (
        group_guide.actions_label.mapTo(panel, QPoint(0, 0)).x()
    )


def test_single_image_picker_rejects_non_image_even_if_dialog_returns_it(
    tmp_path,
    qapp,
    monkeypatch,
):
    document = tmp_path / "pollution.docx"
    document.write_bytes(b"not-an-image")
    captured_filter: list[str] = []

    def fake_get_open_file_name(*args):
        captured_filter.append(str(args[3]))
        return str(document), ""

    monkeypatch.setattr(
        asset_file_operations_presenter.QFileDialog,
        "getOpenFileName",
        fake_get_open_file_name,
    )
    panel = _bidding_panel()
    try:
        panel._select_asset_file("logo")

        assert "logo" not in panel._asset_paths
        assert captured_filter
        assert "All Files" not in captured_filter[0]
    finally:
        panel.close()


def test_assets_panel_group_binding_drives_preview_profile_and_runtime(tmp_path, qapp):
    source = tmp_path / "qualification"
    (source / "A").mkdir(parents=True)
    (source / "A" / "10.jpg").write_bytes(b"ten")
    (source / "A" / "2.jpg").write_bytes(b"two")
    panel = _bidding_panel()
    binding, resolution = refresh_asset_binding(
        AssetBinding(
            role="qualification",
            cardinality="multiple",
            source_kind="directory",
            source_path=str(source),
            recursive=True,
            max_items=None,
        )
    )

    panel._asset_bindings["qualification"] = binding
    panel._refresh_asset_group_rows()
    assert panel._persist_current_profile_editor()
    context = panel.material_context()

    table = panel._asset_group_tables["qualification"]
    assert panel._asset_group_path_labels["qualification"].text() == str(source)
    assert table.rowCount() == 2
    assert [table.item(index, 1).text() for index in range(2)] == [
        "qualification_001.jpg",
        "qualification_002.jpg",
    ]
    assert [item.original_relative_path for item in resolution.items] == [
        "A/2.jpg",
        "A/10.jpg",
    ]
    profile = panel._selected_profile()
    assert profile.asset_bindings["qualification"].source_path == str(source)
    assert [item.sequence for item in context.asset_items if item.role == "qualification"] == [1, 2]
    rule = next(
        item
        for item in context.image_material_rules.values()
        if item.source_role == "qualification"
    )
    assert rule.cardinality.value == "multiple"
    assert profile.asset_bindings["qualification"].max_items is None
    assert context.image_rules == []


def test_assets_panel_archive_round_trip_keeps_group_binding(tmp_path, qapp):
    source = tmp_path / "case_images"
    source.mkdir()
    (source / "1.png").write_bytes(b"one")
    panel = _bidding_panel()
    binding, _resolution = refresh_asset_binding(
        AssetBinding(
            role="qualification",
            cardinality="multiple",
            source_kind="directory",
            source_path=str(source),
            recursive=True,
            max_items=None,
        )
    )
    panel._asset_bindings["qualification"] = binding
    archive = panel.current_archive()

    restored = _bidding_panel()
    restored.set_archive(archive)

    restored_binding = restored._selected_profile().asset_bindings["qualification"]
    assert Path(restored_binding.source_path) == source
    assert len(restored_binding.items) == 1
    assert restored._asset_group_tables["qualification"].rowCount() == 1


def test_bidding_archive_snapshot_inherits_primary_material_schema(qapp):
    panel = _bidding_panel()
    try:
        archive = panel.current_archive()

        assert archive.material_schema_ids == ["bid_materials_v1"]
        assert "official_document_v1" not in archive.material_schema_ids
    finally:
        panel.close()


def test_assets_panel_surfaces_group_source_conflicts(tmp_path, qapp):
    source = tmp_path / "qualification"
    source.mkdir()
    selected = source / "1.png"
    selected.write_bytes(b"selected")
    conflicting = tmp_path / "other.png"
    conflicting.write_bytes(b"other")
    panel = _bidding_panel()
    binding, _resolution = refresh_asset_binding(
        AssetBinding(
            role="qualification",
            cardinality="multiple",
            source_kind="directory",
            source_path=str(source),
            recursive=True,
            max_items=None,
        )
    )
    panel._asset_bindings["qualification"] = binding
    panel._asset_item_payloads = [
        {
            "item_id": "legacy",
            "role": "qualification",
            "path": str(conflicting),
        }
    ]

    panel._refresh_summary()

    assert "图片来源冲突" in panel._image_assets_status_label.text()
    assert "已隔离" in panel._image_assets_status_label.text()
    assert "qualification" in panel._image_assets_status_label.text()
    assert "图片来源冲突" in panel._asset_group_status_labels["qualification"].text()
    assert [
        item
        for item in panel._current_asset_items()
        if item.role == "qualification"
    ] == []


def test_assets_panel_group_rescan_and_clear_replace_stale_rows(tmp_path, qapp):
    source = tmp_path / "qualification"
    source.mkdir()
    (source / "1.png").write_bytes(b"one")
    panel = _bidding_panel()
    binding, _resolution = refresh_asset_binding(
        AssetBinding(
            role="qualification",
            cardinality="multiple",
            source_kind="directory",
            source_path=str(source),
            recursive=True,
            max_items=None,
        )
    )
    panel._asset_bindings["qualification"] = binding
    panel._refresh_asset_group_rows()
    assert panel._asset_group_tables["qualification"].rowCount() == 1

    (source / "2.png").write_bytes(b"two")
    panel._refresh_asset_group_binding("qualification")
    assert panel._asset_group_tables["qualification"].rowCount() == 2
    assert len(panel._asset_bindings["qualification"].items) == 2

    panel._clear_asset_group_binding("qualification")
    assert "qualification" not in panel._asset_bindings
    assert panel._asset_group_tables["qualification"].rowCount() == 0
    assert not [
        item
        for item in panel.material_context().asset_items
        if item.role == "qualification"
    ]


def test_assets_panel_image_page_has_compact_discoverable_empty_state(tmp_path, qapp):
    panel = _bidding_panel()
    panel._refresh_asset_slot_statuses([])

    logo_choose = panel._asset_slot_choose_buttons["logo"]
    logo_row = panel._asset_slot_rows["logo"]
    assert logo_choose.text() == ""
    assert logo_choose.toolTip() == "为Logo选择图片"
    assert not logo_choose.icon().isNull()
    assert logo_row.sizePolicy().verticalPolicy() == QSizePolicy.Maximum
    assert logo_row.maximumHeight() == 108
    assert not panel._asset_slot_path_edits["logo"].isHidden()
    assert panel._asset_slot_path_edits["logo"].placeholderText() == "尚未选择图片"
    assert "用于" not in panel._asset_slot_status_labels["logo"].text()
    logo_open_folder = panel._asset_slot_open_buttons["logo"]
    assert logo_open_folder.toolTip() == "打开Logo所在文件夹"
    assert logo_open_folder.property("pathAction") == "reveal_in_folder"
    assert not logo_open_folder.isEnabled()
    logo_clear = panel._asset_slot_clear_buttons["logo"]
    assert not logo_clear.isHidden()
    assert not logo_clear.isEnabled()
    logo_actions = panel._asset_slot_action_strips["logo"]
    assert tuple(logo_actions._buttons) == (
        "clear",
        "choose",
        "reveal",
        "add",
        "remove",
    )
    assert logo_actions.width() == (
        get_theme().compact_action_size * 5
        + get_theme().compact_action_gap * 4
    )
    assert logo_choose.property("pathAction") == "choose_image"

    group_choose = panel._asset_group_choose_buttons["qualification"]
    assert group_choose.text() == ""
    assert group_choose.toolTip() == "选择资质证书文件夹"
    assert group_choose.property("pathAction") == "choose_directory"
    assert (
        panel._asset_group_open_buttons["qualification"].property("pathAction")
        == "reveal_in_folder"
    )
    group_actions = group_choose.parentWidget()
    assert tuple(group_actions._buttons) == (
        "clear",
        "choose",
        "refresh",
        "open",
        "add",
        "remove",
    )
    assert all(
        not button.icon().isNull()
        for button in (
            group_choose,
            panel._asset_group_refresh_buttons["qualification"],
            panel._asset_group_open_buttons["qualification"],
            panel._asset_group_clear_buttons["qualification"],
        )
    )
    assert not panel._asset_group_path_labels["qualification"].isHidden()
    assert panel._asset_group_path_labels["qualification"].placeholderText() == "尚未选择文件夹"
    assert all(
        button.isHidden()
        for button in (
            panel._asset_group_refresh_buttons["qualification"],
            panel._asset_group_open_buttons["qualification"],
        )
    )
    group_clear = panel._asset_group_clear_buttons["qualification"]
    assert not group_clear.isHidden()
    assert not group_clear.isEnabled()
    assert group_clear.toolTip() == "清除资质证书文件夹"
    assert panel._asset_slot_add_buttons["logo"].property(
        "compactActionVariant"
    ) == "outlined-primary"
    assert panel._asset_slot_remove_buttons["logo"].property(
        "compactActionVariant"
    ) == "outlined-danger"
    assert panel._asset_group_add_buttons["qualification"].property(
        "compactActionVariant"
    ) == "outlined-primary"
    assert panel._asset_group_remove_buttons["qualification"].property(
        "compactActionVariant"
    ) == "outlined-danger"
    assert panel._single_assets_title.parentWidget().icon_label.isHidden()
    assert panel._asset_groups_title.parentWidget().icon_label.isHidden()
    assert panel._asset_group_section_gap.height() == 10
    assert not hasattr(panel, "_image_preview_header")
    assert not hasattr(panel, "_image_preview_label")
    assert not hasattr(panel, "_image_preview_actions_row")
    assert not hasattr(panel, "_full_image_preview_btn")

    preview = tmp_path / "preview.png"
    Image.new("RGB", (120, 80), color="blue").save(preview)
    panel.resize(1300, 900)
    panel.show()
    panel._on_section_selected("images")
    qapp.processEvents()
    empty_path_width = panel._asset_slot_path_edits["logo"].width()
    choose_x = panel._asset_slot_choose_buttons["logo"].geometry().x()
    opened: list[str] = []
    panel._open_current_image_preview_dialog = lambda: opened.append(
        panel._current_image_preview_path
    ) or True
    panel._asset_paths["logo"] = str(preview)
    panel._refresh_asset_slot_statuses([])
    qapp.processEvents()

    QTest.mouseClick(panel._asset_slot_thumbnail_labels["logo"], Qt.LeftButton)

    assert panel._current_image_preview_path == str(preview)
    assert opened == [str(preview)]
    assert panel._asset_slot_clear_buttons["logo"].isEnabled()
    assert panel._asset_slot_open_buttons["logo"].isEnabled()
    assert panel._asset_slot_path_edits["logo"].width() == empty_path_width
    assert panel._asset_slot_choose_buttons["logo"].geometry().x() == choose_x

    revealed: list[str] = []
    panel._open_file_path = revealed.append
    panel._asset_slot_open_buttons["logo"].click()
    assert revealed == [str(preview.parent)]

    group_source = tmp_path / "preview_group"
    group_source.mkdir()
    group_preview = group_source / "1.png"
    Image.new("RGB", (100, 100), color="green").save(group_preview)
    binding, _resolution = refresh_asset_binding(
        AssetBinding(
            role="qualification",
            cardinality="multiple",
            source_kind="directory",
            source_path=str(group_source),
            recursive=False,
        )
    )
    panel._asset_bindings["qualification"] = binding
    panel._refresh_asset_group_rows()
    panel._preview_asset_group_first_item("qualification")

    assert panel._current_image_preview_path == str(group_preview)
    assert panel._asset_group_thumbnail_labels["qualification"].pixmap() is not None
    QTest.mouseClick(
        panel._asset_group_thumbnail_labels["qualification"],
        Qt.LeftButton,
    )
    assert opened[-1] == str(group_preview)


def test_image_restore_preserves_row_identity_and_rethemes_recreated_empty_row(qapp):
    panel = _bidding_panel()
    panel._refresh_asset_slot_statuses([])
    initial_row = panel._asset_slot_rows["logo"]
    initial_signature = _single_row_visual_signature(panel, "logo")
    assert all(initial_signature[index] for index in range(4))

    panel._capture_material_persistence_snapshot(panel.current_archive())
    panel._commit_asset_slot_token("logo", "{{@img:品牌标志1}}")
    qapp.processEvents()

    assert panel._asset_slot_rows["logo"] is initial_row
    assert _single_row_visual_signature(panel, "logo") == initial_signature
    assert (
        panel._image_material_rules["image:logo"].anchor_token
        == "{{@img:品牌标志1}}"
    )

    panel._restore_material_section("images")
    qapp.processEvents()

    assert panel._asset_slot_rows["logo"] is initial_row
    assert panel._asset_slot_target_edits["logo"].text() == "{{@img:LOGO1}}"
    assert panel._image_material_rules["image:logo"].anchor_token == "{{@img:LOGO1}}"
    assert _single_row_visual_signature(panel, "logo") == initial_signature

    panel._capture_material_persistence_snapshot(panel.current_archive())
    panel._remove_asset_slot("logo")
    qapp.processEvents()
    assert "logo" not in panel._asset_slot_rows

    panel._restore_material_section("images")
    qapp.processEvents()

    assert panel._asset_slot_rows["logo"] is not initial_row
    assert _single_row_visual_signature(panel, "logo") == initial_signature


def test_unchanged_name_edit_dismisses_without_marking_images_dirty(qapp):
    panel = _bidding_panel()
    panel._capture_material_persistence_snapshot(panel.current_archive())
    actions = panel._material_persistence_actions["images"]
    name_edit = panel._asset_slot_name_edits["logo"]

    assert not actions.restore_button.isEnabled()
    assert not actions.save_button.isEnabled()

    QTest.mouseDClick(name_edit, Qt.LeftButton)
    assert name_edit.isInlineEditing()
    QTest.mouseClick(panel._single_assets_title, Qt.LeftButton)
    qapp.processEvents()

    assert name_edit.isReadOnly()
    assert not name_edit.isInlineEditing()
    assert name_edit.text() == "Logo"
    assert not actions.restore_button.isEnabled()
    assert not actions.save_button.isEnabled()


def test_single_asset_tokens_copy_rename_add_remove_and_round_trip(qapp):
    panel = _bidding_panel()

    logo_edit = panel._asset_slot_target_edits["logo"]
    logo_row = panel._asset_slot_rows["logo"]
    QTest.mouseClick(logo_edit, Qt.LeftButton)
    assert qapp.clipboard().text() == "{{@img:LOGO1}}"

    QTest.mouseDClick(logo_edit, Qt.LeftButton)
    assert logo_edit.isReadOnly() is False
    logo_edit.setFocus()
    logo_edit.setText("{{@img:品牌标志1}}")
    logo_edit.clearFocus()
    logo_edit.editingFinished.emit()
    qapp.processEvents()
    assert next(
        spec.target for spec in panel._asset_slot_specs if spec.role == "logo"
    ) == "{{@img:品牌标志1}}"
    assert panel._asset_slot_rows["logo"] is logo_row
    assert next(
        spec.label for spec in panel._asset_slot_specs if spec.role == "logo"
    ) == "Logo"

    name_edit = panel._asset_slot_name_edits["logo"]
    QTest.mouseClick(name_edit, Qt.LeftButton)
    assert qapp.clipboard().text() == "Logo"
    assert name_edit.isReadOnly()
    QTest.mouseDClick(name_edit, Qt.LeftButton)
    assert not name_edit.isReadOnly()
    name_edit.setText("企业品牌标志")
    QTest.mouseClick(panel._single_assets_title, Qt.LeftButton)
    qapp.processEvents()
    assert next(
        spec.label for spec in panel._asset_slot_specs if spec.role == "logo"
    ) == "企业品牌标志"

    panel._asset_slot_add_buttons["logo"].click()
    qapp.processEvents()
    added = next(
        spec for spec in panel._asset_slot_specs if spec.target == "{{@img:品牌标志2}}"
    )
    assert panel._asset_slot_remove_buttons[added.role].isHidden() is False
    assert panel._asset_slot_thumbnail_labels[added.role].styleSheet()
    assert panel._asset_slot_index_labels[added.role].styleSheet()
    assert panel._asset_slot_path_edits[added.role].displaySurface().styleSheet()
    assert panel._asset_slot_path_edits[added.role].property("sizeClass") == "md"

    panel._add_single_asset_btn.click()
    qapp.processEvents()
    assert any(spec.target == "{{@img:图片1}}" for spec in panel._asset_slot_specs)

    panel._asset_slot_remove_buttons[added.role].click()
    qapp.processEvents()
    assert all(spec.role != added.role for spec in panel._asset_slot_specs)

    panel._asset_slot_remove_buttons["seal"].click()
    qapp.processEvents()
    assert all(spec.role != "seal" for spec in panel._asset_slot_specs)

    archive = panel.current_archive()
    restored = _bidding_panel()
    restored.set_archive(archive)
    restored_targets = {spec.target for spec in restored._asset_slot_specs}
    assert "{{@img:品牌标志1}}" in restored_targets
    assert "{{@img:图片1}}" in restored_targets
    assert "{{@img:公章1}}" not in restored_targets
    assert next(
        spec.label for spec in restored._asset_slot_specs if spec.target == "{{@img:品牌标志1}}"
    ) == "企业品牌标志"


def test_multi_image_tokens_share_copy_rename_add_remove_and_round_trip(qapp):
    panel = _bidding_panel()

    token_edit = panel._asset_group_token_edits["qualification"]
    qualification_row = panel._asset_group_rows["qualification"]
    QTest.mouseClick(token_edit, Qt.LeftButton)
    assert qapp.clipboard().text() == "{{@img:资质证书1}}"

    QTest.mouseDClick(token_edit, Qt.LeftButton)
    token_edit.setFocus()
    token_edit.setText("{{@img:项目图片1}}")
    token_edit.clearFocus()
    token_edit.editingFinished.emit()
    qapp.processEvents()
    assert panel._asset_group_specs[0].target == "{{@img:项目图片1}}"
    assert panel._asset_group_rows["qualification"] is qualification_row
    assert panel._asset_group_specs[0].label == "资质证书"

    group_name = panel._asset_group_name_edits["qualification"]
    QTest.mouseClick(group_name, Qt.LeftButton)
    assert qapp.clipboard().text() == "资质证书"
    assert group_name.isReadOnly()
    QTest.mouseDClick(group_name, Qt.LeftButton)
    assert not group_name.isReadOnly()
    group_name.setText("ISO9001质量管理体系认证证书")
    QTest.mouseClick(panel._asset_groups_title, Qt.LeftButton)
    qapp.processEvents()
    assert panel._asset_group_specs[0].label == "ISO9001质量管理体系认证证书"

    panel._asset_group_add_buttons["qualification"].click()
    qapp.processEvents()
    added = next(
        spec for spec in panel._asset_group_specs if spec.target == "{{@img:项目图片2}}"
    )
    assert panel._asset_group_remove_buttons[added.role].isHidden() is False
    assert panel._asset_group_thumbnail_labels[added.role].styleSheet()
    assert panel._asset_group_index_labels[added.role].styleSheet()
    assert panel._asset_group_path_labels[added.role].displaySurface().styleSheet()
    assert panel._asset_group_path_labels[added.role].property("sizeClass") == "md"

    panel._add_asset_group_btn.click()
    qapp.processEvents()
    custom = next(
        spec for spec in panel._asset_group_specs if spec.target == "{{@img:图片组1}}"
    )
    panel._asset_group_remove_buttons[custom.role].click()
    qapp.processEvents()
    assert all(spec.role != custom.role for spec in panel._asset_group_specs)

    archive = panel.current_archive()
    restored = _bidding_panel()
    restored.set_archive(archive)
    restored_targets = {spec.target for spec in restored._asset_group_specs}
    assert restored_targets == {"{{@img:项目图片1}}", "{{@img:项目图片2}}"}
    assert next(
        spec.label
        for spec in restored._asset_group_specs
        if spec.target == "{{@img:项目图片1}}"
    ) == "ISO9001质量管理体系认证证书"
    assert all(
        spec.cardinality == "multiple"
        for spec in restored._selected_profile().asset_token_specs
        if spec.token in restored_targets
    )


def test_legacy_slot_metadata_is_read_then_migrated_on_first_inventory_change(qapp):
    panel = _bidding_panel()
    panel.set_archive(
        EntityArchive(
            profiles=[
                EntityProfile(
                    asset_metadata={
                        "logo": {
                            "slot_target": "{{@img:旧品牌标志1}}",
                            "slot_label": "旧品牌标志",
                            "slot_order": "10",
                        }
                    }
                )
            ]
        )
    )

    assert panel._selected_profile().asset_token_specs == []
    assert panel._asset_slot_specs[0].target == "{{@img:旧品牌标志1}}"

    panel._add_single_asset_btn.click()
    qapp.processEvents()

    assert panel._selected_profile().asset_token_specs
    assert panel._selected_profile().asset_token_specs[0].token == "{{@img:旧品牌标志1}}"
