from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path

from docx import Document
from PIL import Image
import pytest

from src.config.attachment_materials import AttachmentProcessingMode
from src.config.entity import (
    EntityArchive,
    EntityProfile,
    load_entity_archive,
    save_entity_archive,
)
from src.config.material_batch import build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.qt_api import Qt
from src.services.material_attachments import (
    AttachmentRequirementOwner,
    AttachmentRequirementState,
    build_attachment_binding,
    build_attachment_preparation_report,
)
from src.services.material_attachments.timeline_preparation import (
    AttachmentTimelineConflict,
    apply_attachment_timeline_plan,
    attachment_timeline_plan_id,
    build_attachment_timeline_plan,
)
from src.shared.engine.material_timeline import default_timeline_plan
from src.ui.bridge import PanelBridge
from src.ui.panels.assets.attachment_preparation_dialog import (
    AttachmentPreparationDialog,
)
from src.ui.panels.assets.attachment_preparation_session import (
    AttachmentPreparationSession,
)
from src.ui.panels.assets_panel import AssetsPanel
import src.ui.panels.assets.attachment_preparation_presenter as preparation_presenter


def _binding(
    tmp_path: Path,
    text: str,
    *,
    name: str = "template.docx",
    role: str = "iso_package",
):
    path = tmp_path / name
    document = Document()
    document.add_paragraph(text)
    document.save(path)
    return build_attachment_binding(
        role=role,
        source_paths=(path,),
        accepted_types=("docx",),
        processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
    )


def _attachment_plan(*fields: str):
    denominator = max(1, len(fields) - 1)
    return build_attachment_timeline_plan(
        start_field="项目开始日期",
        end_field="项目结束日期",
        outputs=tuple(
            (field, Decimal(index) / Decimal(denominator))
            for index, field in enumerate(fields)
        ),
        date_format="yyyy-MM-dd",
    )


def test_profile_specific_aliases_edit_their_own_field_keys(tmp_path: Path):
    binding = _binding(tmp_path, "{{@text:项目名称}}")
    profiles = [
        EntityProfile(
            profile_id="a",
            profile_name="项目 A",
            declared_field_keys=["project_a"],
            field_aliases={"项目名称": "project_a"},
        ),
        EntityProfile(
            profile_id="b",
            profile_name="项目 B",
            declared_field_keys=["project_b"],
            field_aliases={"项目名称": "project_b"},
        ),
    ]
    session = AttachmentPreparationSession(
        role=binding.role,
        binding=binding,
        profiles=profiles,
    )

    requirement = session.report.requirements[0]
    assert requirement.resource_keys == ("project_a", "project_b")
    assert session.set_field_values(
        requirement.token,
        {0: "管道 A", 1: "管道 B"},
    )

    prepared = session.result_profiles()
    assert prepared[0].fields == {"project_a": "管道 A"}
    assert prepared[1].fields == {"project_b": "管道 B"}
    assert prepared[0].field_sources == {}
    assert prepared[1].field_sources == {}
    assert session.report.is_ready


def test_blank_declared_field_round_trips_without_fake_import_source(
    tmp_path: Path,
):
    path = tmp_path / "package.json"
    save_entity_archive(
        EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="one",
                    profile_name="项目一",
                    declared_field_keys=["发文机关3"],
                )
            ]
        ),
        path,
    )

    restored = load_entity_archive(path).profiles[0]

    assert restored.declared_field_keys == ["发文机关3"]
    assert restored.fields == {}
    assert restored.field_sources == {}


def test_owner_conflict_is_reported_instead_of_overwriting_a_resource_key(
    tmp_path: Path,
):
    binding = _binding(tmp_path, "{{@time:时间节点1-1}}")
    plan = _attachment_plan("时间节点1-1")
    profiles = [
        EntityProfile(
            profile_id="timeline",
            profile_name="方案计算",
            fields={"项目开始日期": "2026-01-01", "项目结束日期": "2026-01-11"},
            timeline_plans={"attachment": plan},
        ),
        EntityProfile(
            profile_id="direct",
            profile_name="直接填写",
            declared_field_keys=["时间节点1-1"],
        ),
    ]

    requirement = build_attachment_preparation_report(binding, profiles).requirements[0]

    assert requirement.owner is AttachmentRequirementOwner.CONFLICT
    assert requirement.state is AttachmentRequirementState.ERROR
    assert requirement.issue_code == "profile_requirement_owner_conflict"
    assert requirement.resource_keys == ("时间节点1-1", "时间节点1-1")


def test_time_namespace_does_not_make_every_missing_date_a_timeline_node(
    tmp_path: Path,
):
    binding = _binding(
        tmp_path,
        "{{@time:签署日期}} {{@time:时间节点1-1}}",
    )
    report = build_attachment_preparation_report(
        binding,
        [EntityProfile(profile_id="one", profile_name="项目一")],
    )
    by_token = {item.token: item for item in report.requirements}

    assert by_token["{{@time:签署日期}}"].owner is AttachmentRequirementOwner.FIELD
    assert by_token["{{@time:签署日期}}"].status == "字段未创建"
    assert by_token["{{@time:时间节点1-1}}"].owner is AttachmentRequirementOwner.TIMELINE
    assert by_token["{{@time:时间节点1-1}}"].status == "时间计划未就绪"


def test_image_readiness_is_projected_per_profile(tmp_path: Path):
    binding = _binding(tmp_path, "{{@img:LOGO1}}")
    logo_a = tmp_path / "logo-a.png"
    logo_b = tmp_path / "logo-b.png"
    Image.new("RGB", (8, 8), "red").save(logo_a)
    Image.new("RGB", (8, 8), "blue").save(logo_b)
    profiles = [
        EntityProfile(profile_id="a", profile_name="项目 A", asset_paths={"logo": str(logo_a)}),
        EntityProfile(profile_id="b", profile_name="项目 B"),
    ]

    partial = build_attachment_preparation_report(
        binding,
        profiles,
        image_token_bindings={"{{@img:LOGO1}}": "logo"},
    )
    assert partial.requirements[0].state is AttachmentRequirementState.PARTIAL
    assert tuple(item.state for item in partial.requirements[0].profiles) == (
        AttachmentRequirementState.RESOLVED,
        AttachmentRequirementState.EMPTY,
    )

    profiles[1].asset_paths["logo"] = str(logo_b)
    ready = build_attachment_preparation_report(
        binding,
        profiles,
        image_token_bindings={"{{@img:LOGO1}}": "logo"},
    )
    assert ready.is_ready


def test_attachment_timeline_apply_replaces_only_owned_plans():
    owned = _attachment_plan("时间节点1-1")
    profile = EntityProfile(
        profile_id="one",
        profile_name="项目一",
        timeline_plans={"old_a": owned, "old_b": copy.deepcopy(owned)},
    )

    plan_id = apply_attachment_timeline_plan(
        [profile],
        role="iso_package",
        plan=owned,
    )

    assert plan_id == attachment_timeline_plan_id("iso_package")
    assert list(profile.timeline_plans) == [plan_id]
    assert {"项目开始日期", "项目结束日期"}.issubset(
        profile.declared_field_keys
    )


def test_attachment_timeline_apply_rejects_a_main_timeline_owner():
    main_plan = default_timeline_plan()
    main_plan["nodes"] = [
        {
            "node_id": "node_1",
            "node_no": 1,
            "active": True,
            "label": "时间节点1-1",
            "rule": {"operation": "ratio", "value": "0.5"},
            "outputs": [{"field": "时间节点1-1", "format": "yyyy-MM-dd"}],
        }
    ]
    profile = EntityProfile(
        profile_id="one",
        profile_name="项目一",
        timeline_plans={"main": main_plan},
    )

    with pytest.raises(AttachmentTimelineConflict):
        apply_attachment_timeline_plan(
            [profile],
            role="iso_package",
            plan=_attachment_plan("时间节点1-1"),
        )

    assert list(profile.timeline_plans) == ["main"]


def test_main_timeline_editor_preserves_attachment_owned_plan(qapp):
    plan = _attachment_plan("时间节点1-1")
    original = copy.deepcopy(plan)
    panel = AssetsPanel(PanelBridge())
    try:
        panel.set_archive(
            EntityArchive(
                profiles=[
                    EntityProfile(
                        profile_id="one",
                        profile_name="项目一",
                        timeline_plans={"attachment": plan},
                    )
                ]
            )
        )

        assert panel._normalized_timeline_segments() == {}
        assert panel._selected_profile().timeline_plans == {"attachment": original}
    finally:
        panel.close()


def test_card_and_dialog_use_the_same_checked_generation_scope(qapp, tmp_path: Path):
    panel = AssetsPanel(PanelBridge())
    try:
        panel.set_archive(
            EntityArchive(
                profiles=[
                    EntityProfile(
                        profile_id="ready",
                        profile_name="已就绪",
                        fields={"项目名称": "管道项目"},
                    ),
                    EntityProfile(profile_id="missing", profile_name="未填写"),
                ]
            )
        )
        panel._add_independent_attachment_btn.click()
        role = panel._attachment_role_specs[-1].role
        binding = _binding(tmp_path, "{{@text:项目名称}}", role=role)
        panel._attachment_bindings[role] = binding
        panel._profile_list.item(1).setCheckState(Qt.Unchecked)
        panel._refresh_attachment_role_statuses()

        card_report = panel._attachment_preparation_summaries[role].report()
        scope = panel._attachment_preparation_scope_profiles()
        dialog = AttachmentPreparationDialog(
            role=role,
            binding=binding,
            profiles=scope,
            image_token_bindings=panel._attachment_image_token_bindings(),
        )
        try:
            assert card_report.profile_count == 1
            assert card_report.is_ready
            assert dialog._report.profile_count == card_report.profile_count
            assert dialog._report.is_ready == card_report.is_ready
            assert dialog._report.requirements == card_report.requirements
        finally:
            dialog._dirty = False
            dialog.close()
    finally:
        panel.close()


def test_workbench_commit_changes_only_checked_profiles(
    qapp,
    tmp_path: Path,
    monkeypatch,
):
    panel = AssetsPanel(PanelBridge())
    try:
        panel.set_archive(
            EntityArchive(
                profiles=[
                    EntityProfile(
                        profile_id="selected",
                        profile_name="本次生成",
                        fields={"项目名称": "修改前"},
                    ),
                    EntityProfile(
                        profile_id="unselected",
                        profile_name="不生成",
                        fields={"项目名称": "保持不变"},
                    ),
                ]
            )
        )
        panel._add_independent_attachment_btn.click()
        role = panel._attachment_role_specs[-1].role
        binding = _binding(tmp_path, "{{@text:项目名称}}", role=role)
        panel._attachment_bindings[role] = binding
        panel._profile_list.item(1).setCheckState(Qt.Unchecked)

        class FakeDialog:
            def __init__(self, *, profiles, **_kwargs):
                assert [profile.profile_id for profile in profiles] == ["selected"]
                self._profiles = profiles

            def exec(self):
                return 1

            def result_profiles(self):
                result = [copy.deepcopy(profile) for profile in self._profiles]
                result[0].fields["项目名称"] = "已在工作台修改"
                return result

            @staticmethod
            def profiles_replaced():
                return False

            @staticmethod
            def saved_complete():
                return False

        monkeypatch.setattr(
            preparation_presenter,
            "AttachmentPreparationDialog",
            FakeDialog,
        )

        panel._open_attachment_preparation(role)

        assert panel._profiles[0].fields["项目名称"] == "已在工作台修改"
        assert panel._profiles[1].fields["项目名称"] == "保持不变"
        assert panel._profile_list.item(0).checkState() == Qt.Checked
        assert panel._profile_list.item(1).checkState() == Qt.Unchecked
    finally:
        panel.close()


def test_import_inherits_only_attachment_dependencies(tmp_path: Path):
    binding = _binding(tmp_path, "{{@img:LOGO1}}")
    logo = tmp_path / "logo.png"
    seal = tmp_path / "seal.png"
    Image.new("RGB", (8, 8), "red").save(logo)
    Image.new("RGB", (8, 8), "black").save(seal)
    main_plan = default_timeline_plan()
    owned_plan = _attachment_plan("时间节点1-1")
    base = EntityProfile(
        profile_id="base",
        profile_name="基础数据",
        field_aliases={"项目名称": "project_name"},
        timeline_plans={"main": main_plan, "attachment": owned_plan},
        asset_paths={"logo": str(logo), "seal": str(seal)},
        attachment_bindings={binding.role: binding},
    )
    session = AttachmentPreparationSession(
        role=binding.role,
        binding=binding,
        profiles=[base],
        image_token_bindings={"{{@img:LOGO1}}": "logo"},
    )

    session.replace_profiles(
        [EntityProfile(profile_id="imported", profile_name="导入数据")],
        source_path=tmp_path / "batch.xlsx",
    )
    imported = session.result_profiles()[0]

    assert imported.field_aliases == {"项目名称": "project_name"}
    assert imported.asset_paths == {"logo": str(logo)}
    assert "seal" not in imported.asset_paths
    assert list(imported.timeline_plans) == ["attachment"]
    assert imported.attachment_bindings == {binding.role: binding}


def test_batch_wide_attachment_binding_overrides_stale_profile_binding(
    tmp_path: Path,
):
    old_binding = _binding(tmp_path, "old", name="old.docx", role="package")
    new_binding = _binding(tmp_path, "new", name="new.docx", role="package")
    profile = EntityProfile(
        profile_id="one",
        profile_name="项目一",
        attachment_bindings={"package": old_binding},
    )

    item = build_material_batch_items(
        EntityArchive(profiles=[profile]),
        base_context=MaterialExecutionContext(
            attachment_bindings={"package": new_binding}
        ),
    )[0]

    assert item.context.attachment_bindings["package"] == new_binding
