from __future__ import annotations

from dataclasses import replace

import pytest

from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.official_plan_editing import (
    OfficialPlanEditValues,
    compose_official_plan_intent,
    official_plan_field_values,
    official_plan_missing_user_fields,
    validate_official_plan_edit_values,
)
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.application.plan_presentation import present_document_plan
from src.assistant.ui.official_plan_editor import OfficialPlanEditor
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.form_row import FormRow
from src.shared.ui.styled_combo_box import StyledComboBox
from src.ui.adapters.config_selector_models import (
    master_selector_options,
    template_selector_options,
)


def _workspace() -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path="",
        input_name="",
        input_exists=False,
        material_summary={},
    )


def _notice_plan():
    return FormDocumentPlanBuilder().build(
        query="起草一份关于开展档案检查的通知",
        workspace=_workspace(),
        turn_id="turn-official-plan-edit",
    )


def test_official_authoring_plan_requires_user_owned_fields_before_generation():
    plan = _notice_plan()

    assert official_plan_missing_user_fields(plan) == (
        "organization",
        "content_requirements",
    )
    assert present_document_plan(plan).actions == (
        {
            "id": "edit_official_plan_requirements",
            "label": "填写公文信息",
            "variant": "primary",
        },
    )


def test_official_plan_values_become_authoritative_generation_fields():
    plan = _notice_plan()
    values = OfficialPlanEditValues(
        document_type_id="notice",
        organization="示例市综合办公室",
        content_requirements="通知各部门于8月20日前完成第三季度档案自查。",
        recipient="各有关部门",
        signer="不应进入通知",
        document_no="示办发〔2026〕8号",
    )
    revised = replace(
        plan,
        scene_ref={
            **dict(plan.scene_ref),
            "official_field_values": values.authoritative_fields(),
            "official_content_requirements": values.content_requirements,
        },
    )

    assert official_plan_missing_user_fields(revised) == ()
    assert official_plan_field_values(revised) == {
        "document_type": "notice",
        "organization": "示例市综合办公室",
        "recipient": "各有关部门",
        "document_no": "示办发〔2026〕8号",
        "issuer": "示例市综合办公室",
    }
    assert "签发人" not in compose_official_plan_intent(values)
    presentation = present_document_plan(revised)
    assert presentation.actions[0]["id"] == "generate_content_draft"
    assert presentation.body == ""
    assert ("格式模板", "GB/T 9704 公文格式") in presentation.facts
    assert any(label == "公文版式" for label, _value in presentation.facts)
    assert ("交付方式", "正式版 Word") in presentation.facts


def test_upward_official_type_collects_routing_and_signer_before_drafting():
    values = OfficialPlanEditValues(
        document_type_id="report",
        organization="示例市综合办公室",
        content_requirements="报告年度档案管理工作情况。",
    )

    with pytest.raises(ValueError, match="official_plan_recipient_required"):
        validate_official_plan_edit_values(values)
    with pytest.raises(ValueError, match="official_plan_signer_required"):
        validate_official_plan_edit_values(
            replace(values, recipient="示例市人民政府")
        )
    values = replace(
        values,
        recipient="示例市人民政府",
        signer="主任 张明",
    )
    validate_official_plan_edit_values(values)

    base = _notice_plan()
    plan = replace(
        base,
        production_contract=replace(
            base.production_contract,
            document_type_id="report",
        ),
        scene_ref={
            **dict(base.scene_ref),
            "official_field_values": values.authoritative_fields(),
            "official_content_requirements": values.content_requirements,
        },
    )
    assert official_plan_missing_user_fields(plan) == ()


def test_official_plan_editor_uses_shared_controls_and_validates_required_fields(
    qapp,
):
    editor = OfficialPlanEditor(OfficialPlanEditValues(document_type_id="notice"))
    emitted: list[OfficialPlanEditValues] = []
    editor.save_requested.connect(emitted.append)
    try:
        assert isinstance(editor.document_type, StyledComboBox)
        assert isinstance(editor.template, StyledComboBox)
        assert isinstance(editor.master, StyledComboBox)
        assert isinstance(editor.delivery_profile, StyledComboBox)
        assert isinstance(editor.output_root, FolderPicker)
        assert editor.cancel_button.property("variant") == "secondary"
        assert editor.save_button.property("variant") == "primary"
        assert editor._official_field_rows["signer"].isHidden()
        assert editor._meeting_section.isHidden()

        editor._submit()
        assert emitted == []
        assert not editor._error.isHidden()

        editor.organization.setText("示例市综合办公室")
        editor.content_requirements.setPlainText("通知各部门按时完成档案检查。")
        editor._submit()
        qapp.processEvents()

        assert len(emitted) == 1
        assert emitted[0].organization == "示例市综合办公室"
        assert emitted[0].content_requirements.startswith("通知各部门")
    finally:
        editor.close()


def test_official_plan_editor_preserves_multiline_requirements_geometry(qapp):
    editor = OfficialPlanEditor(
        OfficialPlanEditValues(
            document_type_id="notice",
            organization="示例市综合办公室",
            content_requirements="通知各部门按时完成档案检查。",
        )
    )
    try:
        editor.resize(900, 840)
        editor.show()
        qapp.processEvents()
        qapp.processEvents()

        requirements_row = next(
            row
            for row in editor.findChildren(FormRow)
            if row.widget is editor.content_requirements
        )

        assert editor.content_requirements.height() == 104
        assert requirements_row.height() - editor.content_requirements.height() <= 8
        assert not editor.content_requirements.verticalScrollBar().isVisible()
    finally:
        editor.close()


def test_official_editor_keeps_document_type_master_and_delivery_in_sync(qapp):
    editor = OfficialPlanEditor(
        OfficialPlanEditValues(
            document_type_id="letter",
            master_id="official_gbt_letter",
            template_id="official_gbt",
            delivery_profile="formal",
        ),
        master_options=master_selector_options("official"),
        template_options=template_selector_options("official"),
    )
    try:
        assert not editor._official_field_rows["recipient"].isHidden()
        assert editor._official_field_rows["signer"].isHidden()
        editor.document_type.setCurrentIndex(
            editor.document_type.findData("report")
        )
        qapp.processEvents()
        assert editor.master.currentData() == "official_gbt_upward"
        assert not editor._official_field_rows["recipient"].isHidden()
        assert not editor._official_field_rows["signer"].isHidden()
        assert editor.recipient.placeholderText().startswith("必填")
        assert editor.signer.placeholderText().startswith("必填")

        editor.document_type.setCurrentIndex(
            editor.document_type.findData("minutes")
        )
        qapp.processEvents()
        assert editor.master.currentData() == "official_gbt_minutes"
        assert editor.delivery_profile.currentData() == "meeting_archive"
        assert editor._official_field_rows["recipient"].isHidden()
        assert editor._official_field_rows["signer"].isHidden()
        assert not editor._meeting_section.isHidden()
    finally:
        editor.close()
