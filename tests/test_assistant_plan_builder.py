from __future__ import annotations

from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.adapters.production_adapter import AssistantProductionAdapter
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.application.plan_builder import requests_form_document_action
from src.assistant.application.plan_presentation import present_document_plan
from src.assistant.contracts.task_plan import (
    CAPABILITY_PLANNED,
    SOURCE_ROLE_STANDARD_FORMAT_REFERENCE,
    TASK_OPERATION_REVIEW,
)
from src.config.scene_natural_request_router import route_natural_scene_request


def _empty_workspace() -> WorkspaceSnapshot:
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


def test_explicit_writing_intent_uses_prompt_generation_mode():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份项目报告",
        workspace=_empty_workspace(),
        turn_id="turn-1",
    )

    assert plan.scene_ref["generation_mode"] == "from_prompt"
    assert not any("选择" in item and "DOCX" in item for item in plan.unresolved_questions)


def test_formatting_noun_without_input_does_not_silently_generate_content():
    plan = FormDocumentPlanBuilder().build(
        query="检查项目报告的排版问题",
        workspace=_empty_workspace(),
        turn_id="turn-1",
    )

    assert plan.scene_ref["generation_mode"] == "existing_docx"
    assert any("DOCX" in item for item in plan.unresolved_questions)


def test_standard_reference_format_request_is_read_only_and_not_a_production_plan(
    tmp_path,
):
    path = tmp_path / "standard-plan.docx"
    path.write_bytes(b"placeholder")
    workspace = WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path=str(path),
        input_name=path.name,
        input_exists=True,
        material_summary={},
    )
    query = "这个是标准的规划文件，帮我看看确定对应的格式要求"

    route = route_natural_scene_request(query)
    plan = FormDocumentPlanBuilder().build(
        query=query,
        workspace=workspace,
        turn_id="turn-format-reference",
    )

    assert route.status == "matched"
    assert route.selected_route_id == "quick_formatting_general"
    assert requests_form_document_action(query) is False
    assert plan.operation == TASK_OPERATION_REVIEW
    assert plan.capability_ref.status == CAPABILITY_PLANNED
    assert plan.source_artifacts[0].role == SOURCE_ROLE_STANDARD_FORMAT_REFERENCE
    assert any(
        warning.startswith("assistant_analysis_only:format_requirements")
        for warning in plan.warnings
    )
    preflight = AssistantProductionAdapter().build_preflight(plan)
    assert preflight.ready is False
    assert "assistant_capability_not_executable" in preflight.issues


def test_explicit_writing_with_docx_treats_it_as_material_not_mutation_input(tmp_path):
    path = tmp_path / "brief.docx"
    path.write_bytes(b"placeholder")
    workspace = WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path=str(path),
        input_name=path.name,
        input_exists=True,
        material_summary={},
    )

    plan = FormDocumentPlanBuilder().build(
        query="根据材料生成一份项目报告",
        workspace=workspace,
        turn_id="turn-material",
    )

    assert plan.scene_ref["generation_mode"] == "from_material"
    assert not plan.input_document_ref
    assert plan.material_refs[0]["path"] == str(path)
    assert plan.output_policy.filename_suffix == "_draft"
    assert any("不会覆盖原文件" in item for item in plan.warnings)


def test_bidding_authoring_and_qualification_archive_are_distinct_plans(tmp_path):
    source = tmp_path / "qualification-index.docx"
    source.write_bytes(b"placeholder")
    ready_material = {
        "package_id": "bidder-main",
        "profile_id": "company-a",
        "material_schema_ids": ["bid_materials_v1"],
        "field_count": 3,
        "asset_count": 2,
    }
    workspace = WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path="",
        input_name="",
        input_exists=False,
        material_summary=ready_material,
    )

    authoring = FormDocumentPlanBuilder().build(
        query="生成一份投标标书正文",
        workspace=workspace,
        turn_id="turn-bid-author",
    )
    archive = FormDocumentPlanBuilder().build(
        query="整理投标资质证书材料",
        workspace=WorkspaceSnapshot(
            mode_id="custom",
            mode_label="通用版",
            scene_id="custom",
            scene_source_type="builtin",
            template_id="default",
            template_source_type="builtin",
            input_path=str(source),
            input_name=source.name,
            input_exists=True,
            material_summary=ready_material,
        ),
        turn_id="turn-bid-archive",
    )

    assert authoring.scene_ref["route_id"] == "bidding_document_authoring"
    assert authoring.scene_ref["family_id"] == ""
    assert authoring.generation_contract.required is True
    assert authoring.generation_contract.prompt_profile_id == (
        "assistant.bidding-markdown.v1"
    )
    assert authoring.delivery_contract.default_preset_id == "original"
    assert authoring.delivery_contract.required_artifact_keys == ("final_docx",)
    assert authoring.unresolved_questions == ()

    assert archive.scene_ref["route_id"] == "bidding_qualification_archive"
    assert archive.scene_ref["family_id"] == "qualification_archive_packages"
    assert archive.generation_contract.required is False
    assert archive.delivery_contract.default_preset_id == "attachment_package"
    assert archive.delivery_contract.preset_ids == (
        "attachment_package",
        "missing_items_report",
        "archive_manifest",
    )
    assert archive.delivery_contract.required_artifact_keys == (
        "material_manifest",
        "material_package",
    )


def test_bidding_authoring_plan_names_missing_materials_before_final_assembly():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份投标标书正文",
        workspace=_empty_workspace(),
        turn_id="turn-bid-missing",
    )

    assert plan.generation_contract.required is True
    assert any("标书资料包" in item for item in plan.unresolved_questions)
    assert any("Logo、公章" in item for item in plan.unresolved_questions)
    assert [item.code for item in plan.blocking_issues] == [
        "bidding_materials_incomplete"
    ]
    assert present_document_plan(plan).actions == (
        {"id": "open_workbench", "label": "补充所需材料"},
    )
    preflight = AssistantProductionAdapter().build_preflight(plan)
    assert preflight.ready is False
    assert "plan_blocked:bidding_materials_incomplete" in preflight.issues


def test_bidding_authoring_rejects_a_qualification_archive_package():
    workspace = WorkspaceSnapshot(
        mode_id="custom",
        mode_label="通用版",
        scene_id="custom",
        scene_source_type="builtin",
        template_id="default",
        template_source_type="builtin",
        input_path="",
        input_name="",
        input_exists=False,
        material_summary={
            "package_id": "qualification-main",
            "profile_id": "company-a",
            "material_schema_ids": ["qualification_archive_assets_v1"],
            "field_count": 3,
            "asset_count": 2,
        },
    )

    plan = FormDocumentPlanBuilder().build(
        query="生成一份投标标书正文",
        workspace=workspace,
        turn_id="turn-bid-wrong-package",
    )

    assert any(
        "与标书正文匹配的资料包" in item
        for item in plan.unresolved_questions
    )
