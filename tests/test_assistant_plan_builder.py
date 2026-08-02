from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.assistant.adapters.production_adapter import AssistantProductionAdapter
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.plan_builder import (
    FormDocumentPlanBuilder,
    requests_form_document_action,
)
from src.assistant.application.plan_presentation import (
    generated_draft_display_name,
    present_document_plan,
)
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


def _workspace_with_docx(path: Path) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
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


def test_explicit_writing_intent_uses_prompt_generation_mode():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份项目报告",
        workspace=_empty_workspace(),
        turn_id="turn-1",
    )

    assert plan.scene_ref["generation_mode"] == "from_prompt"
    assert not any("选择" in item and "DOCX" in item for item in plan.unresolved_questions)


def test_semantic_revision_uses_docx_as_material_and_requires_new_draft(tmp_path):
    source = tmp_path / "report.docx"
    source.write_bytes(b"test boundary only")

    plan = FormDocumentPlanBuilder().build(
        query="帮我把报告改专业一点",
        workspace=_workspace_with_docx(source),
        turn_id="turn-semantic-revision",
    )

    assert plan.generation_required is True
    assert plan.scene_ref["generation_mode"] == "from_material"
    assert plan.material_refs[0]["path"] == str(source)
    assert plan.production_input_artifact is None


def test_exam_layout_transform_accepts_docx_instead_of_markdown(tmp_path):
    source = tmp_path / "exam.docx"
    source.write_bytes(b"test boundary only")

    plan = FormDocumentPlanBuilder().build(
        query="重新排版这份试卷并统一页边距",
        workspace=_workspace_with_docx(source),
        turn_id="turn-exam-layout",
    )

    assert plan.work_mode_id == "exam"
    assert plan.generation_required is False
    assert plan.production_contract.accepted_suffixes == (".docx",)
    assert plan.production_contract.terminal_assembler == "generic"
    assert plan.production_input_artifact is not None
    assert plan.production_input_artifact.path == str(source)


def test_exam_semantic_revision_generates_validated_markdown_from_docx_material(
    tmp_path,
):
    source = tmp_path / "exam.docx"
    source.write_bytes(b"test boundary only")

    plan = FormDocumentPlanBuilder().build(
        query="修改这份试卷的第 3 题并调整题量",
        workspace=_workspace_with_docx(source),
        turn_id="turn-exam-revision",
    )

    assert plan.work_mode_id == "exam"
    assert plan.generation_required is True
    assert plan.scene_ref["generation_mode"] == "from_material"
    assert plan.production_contract.accepted_suffixes == (".md", ".markdown")
    assert plan.production_input_artifact is None


def test_exam_authoring_plan_resolves_scale_specific_scene_and_targets():
    standard = FormDocumentPlanBuilder().build(
        query="生成一份高一信息技术 Python 基础试卷",
        workspace=_empty_workspace(),
        turn_id="turn-exam-standard",
    )
    quiz = FormDocumentPlanBuilder().build(
        query="生成一份高一信息技术随堂测验试卷",
        workspace=_empty_workspace(),
        turn_id="turn-exam-quiz",
    )
    term = FormDocumentPlanBuilder().build(
        query="生成一份高一信息技术期末试卷",
        workspace=_empty_workspace(),
        turn_id="turn-exam-term",
    )

    assert standard.scene_ref["id"] == "exam"
    assert standard.scene_ref["scale_profile_id"] == "standard"
    assert standard.scene_ref["target_question_count"] == 18
    assert standard.scene_ref["target_student_page_range"] == [4, 8]
    assert quiz.scene_ref["id"] == "exam_quiz"
    assert quiz.scene_ref["scale_profile_id"] == "quiz"
    assert term.scene_ref["id"] == "exam_term"
    assert term.scene_ref["scale_profile_id"] == "term"


def test_exam_make_request_builds_generated_term_plan_without_input_file():
    plan = FormDocumentPlanBuilder().build(
        query="我需要制作一份初中六年级语文期中考试试卷",
        workspace=WorkspaceSnapshot(
            mode_id="exam",
            mode_label="试卷",
            scene_id="exam",
            scene_source_type="builtin",
            template_id="default",
            template_source_type="builtin",
            input_path="",
            input_name="",
            input_exists=False,
            material_summary={},
        ),
        turn_id="turn-exam-make",
    )

    assert plan.operation == "author"
    assert plan.scene_ref["route_id"] == "exam_teaching_versions"
    assert plan.scene_ref["generation_mode"] == "from_prompt"
    assert plan.scene_ref["id"] == "exam_term"
    assert plan.scene_ref["scale_profile_id"] == "term"
    assert plan.generation_required is True
    assert plan.unresolved_questions == ()


def test_exam_plan_card_is_user_facing_and_exposes_a_revision_action():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份小学六年级英语期中考试试卷",
        workspace=WorkspaceSnapshot(
            mode_id="exam",
            mode_label="试卷",
            scene_id="exam",
            scene_source_type="builtin",
            template_id="default",
            template_source_type="builtin",
            input_path="",
            input_name="",
            input_exists=False,
            material_summary={},
        ),
        turn_id="turn-exam-card",
    )
    plan = replace(
        plan,
        material_snapshot_ref={
            "package_id": "pkg_internal_should_not_leak",
            "field_count": 0,
            "asset_count": 0,
            "content_count": 0,
        },
    )

    presentation = present_document_plan(plan)
    facts = dict(presentation.facts)

    assert presentation.title == "小学六年级英语期中考试"
    assert list(facts) == [
        "年级",
        "学科",
        "考试类型",
        "题量",
        "考试时长",
        "满分",
        "交付",
        "参考资料",
        "卷面模板",
        "输出位置",
    ]
    assert facts["参考资料"] == "未添加"
    assert facts["卷面模板"] == "A4 标准卷面"
    assert facts["输出位置"] == plan.output_policy.output_root
    assert Path(facts["输出位置"]).is_absolute()
    assert "pkg_internal_should_not_leak" not in str(presentation)
    assert presentation.notices == ()
    assert generated_draft_display_name(
        plan,
        "3fc8e0ed872e4633a3f156afced8c7ba.exam.md",
    ) == "小学六年级英语期中考试-内容草稿.md"
    assert presentation.actions[-1] == {
        "id": "edit_exam_plan_requirements",
        "label": "修改要求",
        "variant": "secondary",
    }


def test_exam_authoring_preserves_user_scene_and_template_across_scale_routing():
    workspace = WorkspaceSnapshot(
        mode_id="exam",
        mode_label="试卷",
        scene_id="my_school_exam",
        scene_source_type="user",
        template_id="my_school_template",
        template_source_type="user",
        input_path="",
        input_name="",
        input_exists=False,
        material_summary={},
    )

    standard = FormDocumentPlanBuilder().build(
        query="生成一份高一信息技术 Python 基础试卷",
        workspace=workspace,
        turn_id="turn-user-exam-standard",
    )
    quiz = FormDocumentPlanBuilder().build(
        query="生成一份高一信息技术随堂测验试卷",
        workspace=workspace,
        turn_id="turn-user-exam-quiz",
    )
    term = FormDocumentPlanBuilder().build(
        query="生成一份高一信息技术期末试卷",
        workspace=workspace,
        turn_id="turn-user-exam-term",
    )

    for plan in (standard, quiz, term):
        assert plan.work_mode_id == "exam"
        assert plan.scene_ref["route_id"]
        assert plan.scene_ref["id"] == "my_school_exam"
        assert plan.template_ref["id"] == "my_school_template"

    assert standard.scene_ref["scale_profile_id"] == "standard"
    assert standard.scene_ref["target_question_count"] == 18
    assert standard.scene_ref["target_student_page_range"] == [4, 8]
    assert quiz.scene_ref["scale_profile_id"] == "quiz"
    assert quiz.scene_ref["target_question_count"] == 8
    assert quiz.scene_ref["target_student_page_range"] == [2, 4]
    assert term.scene_ref["scale_profile_id"] == "term"
    assert term.scene_ref["target_question_count"] == 24
    assert term.scene_ref["target_student_page_range"] == [6, 10]


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
    assert plan.blocking_issues == ()
    assert present_document_plan(plan).actions == (
        {"id": "generate_content_draft", "label": "生成并校验内容"},
    )
    preflight = AssistantProductionAdapter().build_preflight(plan)
    assert preflight.ready is False
    assert "input_document_missing" in preflight.issues


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

    assert any("不是标书资料包" in item for item in plan.unresolved_questions)
    assert [item.code for item in plan.blocking_issues] == [
        "bidding_material_package_incompatible"
    ]
