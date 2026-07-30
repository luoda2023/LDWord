from pathlib import Path

from docx import Document

from src.config.attachment_materials import AttachmentProcessingMode
from src.services.material_attachments import (
    AttachmentRequirementAction,
    AttachmentRequirementKind,
    AttachmentRequirementState,
    build_directory_attachment_binding,
    project_attachment_token_requirements,
    scan_attachment_token_requirements,
)


def _save_docx(path: Path, *paragraphs: str) -> Path:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(path)
    return path


def test_attachment_requirement_scan_aggregates_strict_legacy_and_nested_tokens(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    _save_docx(
        package / "first.docx",
        "{{@text:project_name}} {{@img:LOGO1}} {{项目编号}}",
    )
    _save_docx(
        package / "second.docx",
        "{{@text:project_name}} {{@attach:nested}} {{bad token}}",
    )
    binding = build_directory_attachment_binding(
        role="iso_package",
        source_directory=package,
        accepted_types=("docx",),
        recursive=True,
        processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
        max_items=None,
    )

    report = scan_attachment_token_requirements(binding)

    assert report.docx_count == 2
    assert report.strict_count == 2
    assert report.legacy_count == 1
    requirements = {item.token: item for item in report.requirements}
    project = requirements["{{@text:project_name}}"]
    assert project.kind is AttachmentRequirementKind.FIELD
    assert project.occurrence_count == 2
    assert project.relative_paths == ("first.docx", "second.docx")
    assert requirements["{{项目编号}}"].suggested_token == "{{@text:项目编号}}"
    assert requirements["{{@attach:nested}}"].issue_code == (
        "attachment_nested_token_unsupported"
    )
    assert requirements["{{bad token}}"].issue_code == "invalid_material_token"


def test_attachment_requirement_projection_reuses_field_and_image_owners(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    _save_docx(
        package / "template.docx",
        "{{@text:项目名称}} {{@time:项目结束日期}} {{@img:LOGO1}}",
    )
    binding = build_directory_attachment_binding(
        role="iso_package",
        source_directory=package,
        accepted_types=("docx",),
        recursive=True,
        processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
        max_items=None,
    )

    rows = project_attachment_token_requirements(
        scan_attachment_token_requirements(binding),
        field_values={"project_name": "管道监测", "项目结束日期": "2026-07-26"},
        field_aliases={"项目名称": "project_name"},
        timeline_field_keys={"项目结束日期"},
        image_token_bindings={"{{@img:LOGO1}}": "logo"},
        image_values={"logo": "company-logo.png"},
        available_image_roles={"logo"},
    )
    by_token = {row.token: row for row in rows}

    assert by_token["{{@text:项目名称}}"].value == "管道监测"
    assert by_token["{{@text:项目名称}}"].status == "已对应"
    assert by_token["{{@text:项目名称}}"].state is AttachmentRequirementState.RESOLVED
    assert by_token["{{@time:项目结束日期}}"].source == "时间节点"
    assert by_token["{{@img:LOGO1}}"].value == "company-logo.png"
    assert by_token["{{@img:LOGO1}}"].status == "已对应"


def test_passthrough_projection_keeps_missing_state_visible(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    _save_docx(package / "template.docx", "{{@text:项目名称}}")
    binding = build_directory_attachment_binding(
        role="iso_package",
        source_directory=package,
        accepted_types=("docx",),
        recursive=True,
        max_items=None,
    )

    rows = project_attachment_token_requirements(
        scan_attachment_token_requirements(binding),
        processing_enabled=False,
    )

    assert rows[0].status == "未启用同步"
    assert rows[0].state is AttachmentRequirementState.DISABLED
    assert rows[0].action is AttachmentRequirementAction.ENABLE_SYNC


def test_requirement_scan_rejects_docx_changed_after_binding(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    source = _save_docx(package / "template.docx", "{{@text:project}}")
    binding = build_directory_attachment_binding(
        role="iso_package",
        source_directory=package,
        accepted_types=("docx",),
        recursive=True,
        max_items=None,
    )
    _save_docx(source, "{{@text:drifted}}")

    report = scan_attachment_token_requirements(binding)

    assert report.requirements == ()
    assert report.unreadable_paths == ("template.docx",)


def test_attachment_requirement_projection_has_one_state_and_one_next_action(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    _save_docx(
        package / "template.docx",
        "{{@text:已有空字段}} {{@text:尚未创建}} {{@time:时间节点1-1}}",
    )
    binding = build_directory_attachment_binding(
        role="iso_package",
        source_directory=package,
        accepted_types=("docx",),
        recursive=True,
        processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
        max_items=None,
    )

    rows = project_attachment_token_requirements(
        scan_attachment_token_requirements(binding),
        available_field_keys={"已有空字段"},
    )
    by_token = {row.token: row for row in rows}

    assert by_token["{{@text:已有空字段}}"].value == ""
    assert by_token["{{@text:已有空字段}}"].state is AttachmentRequirementState.EMPTY
    assert by_token["{{@text:已有空字段}}"].action is AttachmentRequirementAction.FILL_FIELD
    assert by_token["{{@text:尚未创建}}"].state is AttachmentRequirementState.MISSING
    assert by_token["{{@text:尚未创建}}"].action is AttachmentRequirementAction.CREATE_FIELD
    assert by_token["{{@time:时间节点1-1}}"].state is AttachmentRequirementState.UNCONFIGURED
    assert by_token["{{@time:时间节点1-1}}"].action is (
        AttachmentRequirementAction.CONFIGURE_TIMELINE
    )
