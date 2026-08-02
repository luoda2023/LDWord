from __future__ import annotations

from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.exam_plan_editing import (
    ExamPlanEditValues,
    compose_exam_plan_intent,
    resolve_exam_master_binding,
)
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.domain.exam_authoring_contract import (
    parse_exam_authoring_requirements,
    resolve_exam_blueprint,
)
from src.assistant.ui.exam_plan_editor import ExamPlanEditor
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.ui.adapters.config_selector_models import SelectorOption


def _workspace() -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
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
    )


def test_edit_projection_round_trips_a_term_plan_without_duplicate_paper_suffix():
    plan = FormDocumentPlanBuilder().build(
        query=(
            "生成一份小学六年级英语期末考试试卷，共 24 道题，"
            "考试时间 90 分钟，满分 100 分，人教版上册，范围 Unit 1-4，"
            "生成学生卷和答案卷"
        ),
        workspace=_workspace(),
        turn_id="turn-exam-edit-values",
    )

    values = ExamPlanEditValues.from_plan(plan)
    intent = compose_exam_plan_intent(values)
    requirements = parse_exam_authoring_requirements(intent)
    blueprint = resolve_exam_blueprint(intent)

    assert values.exam_period == "期末考试"
    assert values.master_id == "default_exam"
    assert "试卷试卷" not in intent
    assert requirements.subject == "英语"
    assert requirements.grade == "六年级"
    assert requirements.question_count == 24
    assert blueprint.section_blueprints


def test_exam_plan_editor_uses_shared_controls_and_emits_selected_master(qapp):
    initial = ExamPlanEditValues(
        school_stage="小学",
        grade="六年级",
        subject="英语",
        exam_period="期中考试",
        question_count=24,
        duration_minutes=90,
        total_score=100,
        include_student=True,
        include_answer=True,
    )
    editor = ExamPlanEditor(
        initial,
        master_options=(
            SelectorOption(
                value="default_exam",
                label="A4 标准卷面",
                source_type="builtin",
            ),
            SelectorOption(
                value="school_exam",
                label="学校统一卷面",
                source_type="user",
            ),
        ),
    )
    emitted: list[ExamPlanEditValues] = []
    editor.save_requested.connect(emitted.append)
    try:
        assert isinstance(editor.stage, StyledComboBox)
        assert isinstance(editor.master, StyledComboBox)
        assert isinstance(editor.total_score, StyledSpinBox)
        assert isinstance(editor.output_root, FolderPicker)
        assert editor.cancel_button.property("variant") == "secondary"
        assert editor.save_button.property("variant") == "primary"
        assert editor.cancel_button.styleSheet()
        assert editor.save_button.styleSheet()

        editor.student_copy.setChecked(False)
        editor.answer_copy.setChecked(False)
        editor._submit()
        assert emitted == []
        assert not editor._error.isHidden()

        editor.answer_copy.setChecked(True)
        editor.total_score.setValue(120)
        editor.master.setCurrentIndex(editor.master.findData("school_exam"))
        editor._submit()
        qapp.processEvents()

        assert len(emitted) == 1
        assert emitted[0].include_student is False
        assert emitted[0].include_answer is True
        assert emitted[0].total_score == 120
        assert emitted[0].master_id == "school_exam"
    finally:
        editor.close()


def test_incomplete_plan_can_still_open_as_an_editable_projection():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份数学试卷",
        workspace=_workspace(),
        turn_id="turn-incomplete-exam-edit",
    )

    values = ExamPlanEditValues.from_plan(plan)

    assert values.grade == ""
    assert values.subject == "数学"


def test_exam_master_binding_uses_real_master_and_compatible_template():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份小学六年级数学期中考试试卷",
        workspace=_workspace(),
        turn_id="turn-exam-master-binding",
    )

    binding = resolve_exam_master_binding(plan, "default_exam")

    assert binding.master.master_id == "default_exam"
    assert binding.master.docx_path.is_file()
    assert binding.template_id == "default"


def test_exam_master_binding_rejects_a_missing_master():
    plan = FormDocumentPlanBuilder().build(
        query="生成一份小学六年级数学期中考试试卷",
        workspace=_workspace(),
        turn_id="turn-missing-exam-master",
    )

    try:
        resolve_exam_master_binding(plan, "missing_exam_master")
    except ValueError as exc:
        assert str(exc) == "exam_master_unavailable"
    else:
        raise AssertionError("missing master must not be accepted")
