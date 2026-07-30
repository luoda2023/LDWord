from __future__ import annotations

from src.qt_api import QApplication
from src.config.entity import EntityArchive, EntityProfile
from src.config.material_batch import build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.config.material_preview_snapshot import (
    MaterialPreviewSnapshot,
    build_material_preview_snapshot,
)
from src.config.materials import AssetItem
from src.config.scene import SceneWorkspace
from src.shared.ui.card import Card
from src.ui.bridge import PanelBridge
from src.ui.panels.assets.material_preview_projection import (
    MaterialPreviewDraft,
    build_assets_material_preview_snapshot,
)
from src.ui.panels.assets_panel import AssetsPanel
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel
from src.ui.adapters.workbench_material_issues import (
    material_readiness_gate_decision,
    material_readiness_issue_groups,
)
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail
from src.ui.panels.workbench.quick_material_preview import QuickMaterialPreview
from src.ui.panels.workbench.quick_material_preview_presenter import (
    QuickMaterialPreviewItem,
    QuickMaterialPreviewProjection,
    build_quick_material_preview_projection,
)
from src.config.scene_presets import create_bidding_scene


def _app():
    return QApplication.instance() or QApplication([])


def _projection(scene, context):
    return build_quick_material_preview_projection(
        scene,
        context,
        gate_decision=material_readiness_gate_decision(scene, context),
        issue_groups=material_readiness_issue_groups(scene, context),
    )


def test_assets_preview_projection_owns_normalization_without_widget_state():
    snapshot = build_assets_material_preview_snapshot(
        MaterialPreviewDraft(
            mode_id="custom",
            archive_id="edited-package",
            archive_name="编辑中的资料包",
            entry_package_id="previous-package",
            entry_source_type="builtin",
            profile_id="profile-a",
            profile_name="主体资料",
            field_values={"company_name": "测试集团"},
            profile_field_scopes={"legacy": "removed"},
            official_fixed_keys=("company_name",),
            official_floating_keys=("project_name",),
            asset_items=(
                {"role": "logo", "path": "C:/assets/logo.png"},
                {"role": "seal", "path": ""},
            ),
            image_count=1,
            content_count=2,
            attachment_bindings={
                "appendix": {"items": ({"path": "a.docx"}, {"path": "b.docx"})},
                "license": {"source_path": "C:/assets/license.pdf"},
            },
            conflicts=("company_name",),
        )
    )

    assert snapshot.package_id == "edited-package"
    assert snapshot.package_source_type == "user"
    assert snapshot.scopes() == {
        "legacy": "removed",
        "company_name": "fixed",
        "project_name": "floating",
    }
    assert snapshot.asset_roles == ("logo",)
    assert snapshot.attachment_count == 3
    assert snapshot.valid is False
    assert snapshot.issues == ("company_name",)


def test_material_preview_keeps_a_stable_empty_card_without_materials():
    scene = SceneWorkspace(scene_id="custom", template_id="default")

    projection = _projection(scene, MaterialExecutionContext())

    assert projection.visible is True
    assert projection.items == ()
    assert projection.package_label == "未选择资料包"
    assert projection.summary_text == "暂无填充内容"
    assert projection.status_text == "未选择"


def test_material_preview_remains_an_independent_empty_card_for_exam_scene():
    from src.config.scene_presets import create_exam_scene

    projection = _projection(create_exam_scene(), MaterialExecutionContext())

    assert projection.visible is True
    assert projection.items == ()


def test_material_preview_shows_only_compact_execution_essentials():
    scene = create_bidding_scene()
    context = MaterialExecutionContext(
        archive_name="华东项目资料包",
        profile_name="投标人主体",
        entity_data={
            "company_name": "测试建设集团",
            "project_name": "产业园改造项目",
            "legal_person": "张三",
            "address": "这是一条可选资料，不应挤占三个必填字段",
        },
        asset_items=[
            AssetItem(role="logo", path="C:/materials/logo.png"),
            AssetItem(role="seal", path="C:/materials/seal.png"),
        ],
    )

    projection = _projection(scene, context)

    assert projection.visible is True
    assert projection.package_label == "华东项目资料包"
    assert projection.profile_label == "投标人主体"
    assert projection.status_text == "完整"
    assert projection.status_tone == "success"
    assert projection.summary_text == "投标人主体 · 已填 5/5 · 图片 2"
    assert [item.label for item in projection.compact_items] == [
        "公司名称",
        "项目名称",
        "法定代表人",
    ]
    assert projection.counter_text == "图片 2"
    assert projection.can_expand is True
    assert len(projection.items) <= 8


def test_material_preview_prioritizes_missing_required_values_without_a_new_cta():
    scene = create_bidding_scene()
    context = MaterialExecutionContext(
        archive_name="投标资料包",
        profile_name="第一份资料",
    )

    projection = _projection(scene, context)

    assert projection.status_text == "缺 5 项"
    assert projection.status_tone == "warning"
    assert all(item.missing for item in projection.compact_items)
    assert [item.value for item in projection.compact_items] == [
        "未填写",
        "未填写",
        "未填写",
    ]


def test_material_preview_excludes_official_floating_values_from_duplicate_preview():
    scene = create_bidding_scene()
    context = MaterialExecutionContext(
        archive_name="当前资料包",
        profile_name="投标人主体",
        entity_data={
            "company_name": "固定公司",
            "project_name": "本次项目",
            "legal_person": "李四",
        },
        field_scopes={
            "company_name": "fixed",
            "project_name": "floating",
            "legal_person": "floating",
        },
    )

    projection = _projection(scene, context)

    assert [item.key for item in projection.items] == [
        "logo",
        "seal",
        "company_name",
    ]
    assert all(item.key not in {"project_name", "legal_person"} for item in projection.items)


def test_material_preview_widget_has_explicit_clean_expand_interaction():
    _app()
    widget = QuickMaterialPreview()
    projection = QuickMaterialPreviewProjection(
        visible=True,
        package_label="资料包 A",
        profile_label="资料一",
        status_text="必填 4/4",
        status_tone="success",
        items=tuple(
            QuickMaterialPreviewItem(
                key=f"field_{index}",
                label=f"字段 {index}",
                value=f"内容 {index}",
            )
            for index in range(4)
        ),
        counters=("图片 2",),
    )
    try:
        widget.set_projection(projection)

        assert isinstance(widget, Card)
        assert widget.isHidden() is False
        assert widget._toggle_button.text() == "展开"
        assert widget._toggle_button.toolTip() == ""
        assert widget._package_label.toolTip() == ""
        assert widget._package_label.text() == "资料包 A"
        assert widget._summary_label.text() == "暂无填充内容"
        assert widget._status_badge.text() == "必填 4/4"
        assert widget._details.isHidden() is True
        assert widget._package_field.toolTip() == ""
        assert widget._content_field.toolTip() == ""

        widget._toggle_button.click()

        assert widget.is_expanded() is True
        assert widget._toggle_button.text() == "收起"
        assert widget._details.isHidden() is False
    finally:
        widget.close()


def test_quick_execution_inserts_material_preview_between_binding_and_output():
    _app()
    detail = QuickExecutionDetail()
    try:
        detail._apply_scene(create_bidding_scene())
        detail.set_material_context(
            MaterialExecutionContext(
                archive_name="投标资料包",
                profile_name="投标人主体",
                entity_data={
                    "company_name": "测试公司",
                    "project_name": "示例项目",
                    "legal_person": "张三",
                },
            )
        )

        assert detail._material_preview.isHidden() is False
        assert detail._layout.indexOf(detail._scene_card) < detail._layout.indexOf(
            detail._material_preview
        )
        assert detail._layout.indexOf(detail._material_preview) < detail._layout.indexOf(
            detail._output_card
        )
        assert detail._material_preview.projection().package_label == "投标资料包"
        assert (
            detail._material_preview.projection().profile_label
            == "投标人主体"
        )
    finally:
        detail.close()


def test_material_preview_never_uses_profile_name_as_package_name():
    projection = _projection(
        create_bidding_scene(),
        MaterialExecutionContext(
            archive_id="archive-a",
            profile_id="profile-a",
            profile_name="投标人主体",
        ),
    )

    assert projection.package_label == "未命名资料包"
    assert projection.profile_label == "投标人主体"


def test_material_preview_uses_unselected_fallback_without_package_identity():
    projection = _projection(
        create_bidding_scene(),
        MaterialExecutionContext(profile_name="仅有当前资料名称"),
    )

    assert projection.package_label == "未选择资料包"
    assert projection.profile_label == "仅有当前资料名称"


def test_material_preview_updates_package_and_profile_identity_independently():
    scene = create_bidding_scene()

    first = _projection(
        scene,
        MaterialExecutionContext(
            archive_name="资料包 A",
            profile_name="第一份",
        ),
    )
    same_package = _projection(
        scene,
        MaterialExecutionContext(
            archive_name="资料包 A",
            profile_name="第二份",
        ),
    )
    renamed_package = _projection(
        scene,
        MaterialExecutionContext(
            archive_name="资料包 B",
            profile_name="第二份",
        ),
    )

    assert (first.package_label, first.profile_label) == ("资料包 A", "第一份")
    assert (same_package.package_label, same_package.profile_label) == (
        "资料包 A",
        "第二份",
    )
    assert (renamed_package.package_label, renamed_package.profile_label) == (
        "资料包 B",
        "第二份",
    )


def test_live_preview_snapshot_supplies_package_source_and_clean_summary():
    projection = build_quick_material_preview_projection(
        create_bidding_scene(),
        MaterialExecutionContext(),
        preview_snapshot=build_material_preview_snapshot(
            mode_id="custom",
            package_id="package-a",
            archive_name="华东项目资料包",
            package_source_type="user",
            profile_id="profile-a",
            profile_name="投标人主体",
            field_values={
                "company_name": "测试集团",
                "project_name": "产业园改造",
                "legal_person": "张三",
            },
            asset_roles=("logo", "seal"),
            image_count=2,
        ),
    )

    assert projection.package_label == "华东项目资料包"
    assert projection.package_source_text == "自定"
    assert projection.summary_text == "投标人主体 · 已填 5/5 · 图片 2"
    assert projection.status_text == "完整"


def test_assets_bridge_workbench_live_preview_chain_does_not_publish_execution_context():
    app = _app()
    bridge = PanelBridge()
    workbench = WorkbenchPanel(bridge)
    assets = AssetsPanel(bridge)
    try:
        archive = EntityArchive(
            archive_id="package-a",
            archive_name="华东项目资料包",
            profiles=[
                EntityProfile(
                    profile_id="profile-a",
                    profile_name="投标人主体",
                    fields={"company_name": "测试集团"},
                ),
                EntityProfile(
                    profile_id="profile-b",
                    profile_name="联合体成员",
                    fields={"company_name": "协作公司"},
                ),
            ],
        )

        assert assets.set_archive(archive) is True
        app.processEvents()

        snapshot = bridge.current_material_preview_snapshot()
        projection = workbench._quick_execution_detail._material_preview.projection()
        assert snapshot.archive_name == "华东项目资料包"
        assert snapshot.profile_name == "投标人主体"
        assert snapshot.values()["company_name"] == "测试集团"
        assert projection.package_label == "华东项目资料包"
        assert "投标人主体" in projection.summary_text
        assert bridge.current_material_context().is_empty() is True

        assets._profile_list.setCurrentRow(1)
        app.processEvents()
        projection = workbench._quick_execution_detail._material_preview.projection()
        assert bridge.current_material_preview_snapshot().profile_name == "联合体成员"
        assert bridge.current_material_preview_snapshot().values()["company_name"] == "协作公司"
        assert "联合体成员" in projection.summary_text

        assets._fields_edit.set_text("company_name=协作公司（更新）")
        assets._refresh_field_only_projection()
        app.processEvents()
        assert (
            bridge.current_material_preview_snapshot().values()["company_name"]
            == "协作公司（更新）"
        )

        assets._archive_name_edit.setText("华东项目资料包（新）")
        app.processEvents()
        projection = workbench._quick_execution_detail._material_preview.projection()
        assert projection.package_label == "华东项目资料包（新）"
        assert bridge.current_material_context().is_empty() is True
    finally:
        assets.close()
        workbench.close()


def test_bridge_preview_snapshot_round_trip_and_mode_scope_reset():
    bridge = PanelBridge()
    snapshot = build_material_preview_snapshot(
        mode_id="custom",
        package_id="package-a",
        archive_name="资料包 A",
    )

    assert bridge.set_current_material_preview_snapshot(snapshot) is True
    assert bridge.current_material_preview_snapshot() == snapshot

    bridge.set_current_work_mode("official")

    assert bridge.current_material_preview_snapshot() == MaterialPreviewSnapshot()


def test_material_context_round_trip_preserves_archive_name():
    restored = MaterialExecutionContext.from_payload(
        {
            "package_id": "package-a",
            "archive_id": "archive-a",
            "archive_name": "华东项目资料包",
            "profile_id": "profile-a",
            "profile_name": "投标人主体",
        }
    )

    cloned = restored.clone()

    assert restored.archive_name == "华东项目资料包"
    assert cloned.archive_name == "华东项目资料包"
    assert MaterialExecutionContext(archive_name="资料包").is_empty() is False


def test_batch_items_snapshot_archive_name_for_every_profile(tmp_path):
    archive = EntityArchive(
        archive_id="archive-a",
        archive_name="批量投标资料包",
        package_id="package-a",
        profiles=[
            EntityProfile(profile_id="p1", profile_name="第一份"),
            EntityProfile(profile_id="p2", profile_name="第二份"),
        ],
    )

    items = build_material_batch_items(
        archive,
        base_output_dir=tmp_path,
    )

    assert [item.context.archive_name for item in items] == [
        "批量投标资料包",
        "批量投标资料包",
    ]
    assert [item.context.profile_name for item in items] == ["第一份", "第二份"]
