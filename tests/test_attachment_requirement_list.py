from src.services.material_attachments import (
    AttachmentPreparationReport,
    AttachmentPreparationRequirement,
    AttachmentProfileRequirement,
    AttachmentRequirementKind,
    AttachmentRequirementOwner,
    AttachmentRequirementState,
)
from src.ui.panels.assets.attachment_preparation_summary import (
    AttachmentPreparationSummary,
)


def _report(*, state=AttachmentRequirementState.MISSING, unreadable=()):
    profile = AttachmentProfileRequirement(
        profile_id="one",
        profile_name="项目一",
        resource_key="项目名称",
        owner=AttachmentRequirementOwner.FIELD,
        value="项目甲" if state is AttachmentRequirementState.RESOLVED else "",
        state=state,
        declared=state is not AttachmentRequirementState.MISSING,
    )
    requirement = AttachmentPreparationRequirement(
        token="{{@text:项目名称}}",
        kind=AttachmentRequirementKind.FIELD,
        namespace="text",
        identifier="项目名称",
        owner=AttachmentRequirementOwner.FIELD,
        state=state,
        source="直接字段",
        status="已就绪" if state is AttachmentRequirementState.RESOLVED else "字段未创建",
        occurrence_count=12,
        relative_paths=("a.docx", "b.docx"),
        profiles=(profile,),
    )
    return AttachmentPreparationReport(
        binding_revision="revision",
        docx_count=2,
        profile_count=1,
        requirements=(requirement,),
        source_file_count=2,
        unreadable_paths=tuple(unreadable),
    )


def test_attachment_preparation_summary_opens_one_workbench(qapp):
    view = AttachmentPreparationSummary()
    requested: list[bool] = []
    view.prepare_requested.connect(lambda: requested.append(True))
    view.set_report(_report())

    assert view.summary_text() == "2 个文件 · 1 项待补充"
    assert view.status_text() == "2 个文件 · 1 项待补充"
    assert view.prepare_button.text() == "去准备"

    view.prepare_button.click()
    assert requested == [True]
    view.close()


def test_attachment_preparation_summary_has_one_derived_ready_state(qapp):
    view = AttachmentPreparationSummary()
    view.set_report(_report(state=AttachmentRequirementState.RESOLVED))

    assert view.summary_text() == "2 个文件 · 已准备完成"
    assert view.status_text() == "2 个文件 · 已准备完成"
    assert view.prepare_button.text() == "查看资料"
    view.close()


def test_attachment_preparation_summary_keeps_unreadable_package_actionable(qapp):
    view = AttachmentPreparationSummary()
    report = AttachmentPreparationReport(
        binding_revision="revision",
        docx_count=1,
        profile_count=1,
        requirements=(),
        source_file_count=1,
        unreadable_paths=("broken.docx",),
    )
    view.set_report(report)

    assert view.isVisible()
    assert view.summary_text() == "1 个文件无法读取"
    assert view.status_text() == "1 个文件无法读取"
    assert view.prepare_button.text() == "查看问题"
    view.close()


def test_attachment_preparation_summary_requires_a_checked_scope(qapp):
    view = AttachmentPreparationSummary()
    report = _report()
    view.set_report(
        AttachmentPreparationReport(
            binding_revision=report.binding_revision,
            docx_count=report.docx_count,
            profile_count=0,
            requirements=report.requirements,
            source_file_count=report.source_file_count,
        )
    )

    assert view.summary_text() == "请先选择本次要生成的数据"
    assert view.status_text() == "请先选择本次要生成的数据"
    assert view.prepare_button.text() == "去准备"
    view.close()
