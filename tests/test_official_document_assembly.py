import json
from dataclasses import replace

from docx import Document

from src.config import master_library
from src.shared.engine.official_document_assembly import (
    _placeholder_replacements,
    assemble_official_document_docx,
)
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)
from src.config.master_library import default_master
from src.shared.engine import official_document_assembly


def _all_docx_text(path):
    doc = Document(path)
    parts = [paragraph.text for paragraph in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def test_official_replacements_support_numbered_and_custom_placeholders():
    contract = get_official_document_assembly_contract("notice")

    replacements = _placeholder_replacements(
        contract,
        {
            "organization": "示例市档案局",
            "发文机关2": "示例市财政局",
            "自定义字段1": "自定义内容",
        },
    )

    assert replacements["{{@text:发文机关1}}"] == "示例市档案局"
    assert replacements["{{@text:发文机关2}}"] == "示例市财政局"
    assert replacements["{{@text:自定义字段1}}"] == "自定义内容"

    renamed = _placeholder_replacements(
        contract,
        {
            "organization": "示例市档案局",
            "发文机关3": "示例市财政局",
        },
        field_aliases={"发文机关2": "organization"},
    )
    assert renamed["{{@text:发文机关2}}"] == "示例市档案局"
    assert renamed["{{@text:发文机关3}}"] == "示例市财政局"


def test_execution_frozen_master_never_falls_back_to_live_contract_master(
    tmp_path,
    monkeypatch,
):
    standard = default_master("official")
    assert standard is not None
    frozen_standard = replace(standard, execution_frozen=True)
    monkeypatch.setattr(
        master_library,
        "get_master",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("frozen execution master fell back to live library")
        ),
    )
    monkeypatch.setattr(
        master_library,
        "default_master",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("frozen execution master fell back to live default")
        ),
    )

    result = assemble_official_document_docx(
        "letter",
        {},
        tmp_path,
        master=frozen_standard,
    )

    assert result.status == "master_incompatible"
    assert result.master_id == "official_gbt_standard"


def test_official_assembly_applies_renamed_alias_and_added_series_to_user_master(
    tmp_path,
):
    builtin_master = default_master("official")
    assert builtin_master is not None
    master_path = tmp_path / "renamed-series-master.docx"
    document = Document(builtin_master.docx_path)
    document.add_paragraph("别名一：{{@text:发文机关2}}；新增项：{{@text:发文机关3}}")
    document.save(master_path)
    user_master = replace(
        builtin_master,
        docx_path=master_path,
        source_type="user",
        readonly=False,
        manifest_path=None,
    )

    result = assemble_official_document_docx(
        "notice",
        {
            "title": "别名链路验证通知",
            "body": "验证公文正式件装配链路。",
            "organization": "第一机关",
            "发文机关3": "第二机关",
            "document_no": "测发〔2026〕1号",
            "issue_date": "2026年7月12日",
        },
        tmp_path,
        field_aliases={"发文机关2": "organization"},
        filename="renamed-series-output.docx",
        master=user_master,
    )

    assert result.ok is True
    text = _all_docx_text(result.docx_path)
    assert "别名一：第一机关；新增项：第二机关" in text
    assert "{{@text:发文机关2}}" not in text
    assert "{{@text:发文机关3}}" not in text


def test_assemble_official_notice_docx_replaces_master_placeholders(tmp_path):
    result = assemble_official_document_docx(
        "notice",
        {
            "title": "关于开展档案检查的通知",
            "body": "请各部门按要求完成自查并提交材料。",
            "organization": "示例市档案局",
            "document_no": "示档发〔2026〕3号",
            "issue_date": "2026年7月9日",
            "issuer": "示例市档案局",
            "recipient": "各部门",
            "copy_scope": "办公室",
            "printing_org": "示例市档案局办公室",
            "printing_date": "2026年7月9日",
        },
        tmp_path,
    )

    assert result.ok is True
    assert result.docx_path is not None
    assert result.docx_path.is_file()
    assert result.profile_id == "notice"
    assert result.master_id == "official_gbt_standard"
    assert result.material_schema_ids == ("official_document_v1",)
    assert "official_title" in result.replaced_placeholders
    assert "official_body" in result.replaced_placeholders
    assert result.unresolved_placeholders == ()
    assert result.internal_review_docx_path is not None
    assert result.internal_review_docx_path.is_file()
    assert result.archive_manifest_path is not None
    assert result.archive_manifest_path.is_file()
    assert result.archive_manifest_markdown_path is not None
    assert result.archive_manifest_markdown_path.is_file()
    assert result.output_paths == {
        "official_docx": str(result.docx_path),
        "internal_review_docx": str(result.internal_review_docx_path),
        "archive_manifest": str(result.archive_manifest_path),
        "archive_manifest_md": str(result.archive_manifest_markdown_path),
    }

    text = _all_docx_text(result.docx_path)
    formal_document = Document(result.docx_path)
    review_text = _all_docx_text(result.internal_review_docx_path)
    archive_manifest = json.loads(
        result.archive_manifest_path.read_text(encoding="utf-8")
    )
    assert "关于开展档案检查的通知" in text
    assert "请各部门按要求完成自查并提交材料。" in text
    assert "{{@text:official_title}}" not in text
    assert "{{@text:official_body}}" not in text
    assert "\u5185\u90e8\u5ba1\u9605\u7a3f" not in text
    assert "\u5185\u90e8\u5ba1\u9605\u7a3f" in review_text
    assert archive_manifest["status"] == "ok"
    assert archive_manifest["profile_id"] == "notice"
    assert archive_manifest["archive_fields"]["title"]
    assert archive_manifest["output_paths"] == result.output_paths
    assert "official_docx" in archive_manifest["delivery_versions"]
    assert "internal_review_docx" in archive_manifest["delivery_versions"]
    assert "archive_manifest" in archive_manifest["delivery_versions"]
    assert (
        "material bindings are applied by the official document runtime assembly"
        in archive_manifest["boundaries"]
    )
    assert not any(
        "does not execute runtime assembly yet" in boundary
        for boundary in archive_manifest["boundaries"]
    )
    assert "版式占位符说明" not in text
    assert "母版占位符说明" not in text
    assert len(formal_document.sections) == 1
    assert not any(
        paragraph._p.xpath(".//w:sectPr")
        for paragraph in formal_document.paragraphs
    )


def test_assemble_official_minutes_uses_meeting_schema_bindings(tmp_path):
    result = assemble_official_document_docx(
        "minutes",
        {
            "title": "专题协调会议纪要",
            "body": "会议研究了近期材料归档和流程优化事项。",
            "organization": "示例市办公室",
            "document_no": "会议纪要〔2026〕8号",
            "issue_date": "2026年7月9日",
            "meeting_date": "2026年7月9日上午",
            "participants": "张三、李四、王五",
        },
        tmp_path,
        filename="minutes.docx",
    )

    assert result.ok is True
    assert result.material_schema_ids == (
        "official_document_v1",
        "administrative_meeting_fields_v1",
    )
    assert "official_meeting_time" in result.replaced_placeholders
    assert "official_meeting_attendees" in result.replaced_placeholders
    assert result.unresolved_placeholders == ()
    assert result.docx_path is not None
    document = Document(result.docx_path)
    text = _all_docx_text(result.docx_path)
    assert "会议时间：2026年7月9日上午" in text
    assert "出席：张三、李四、王五" in text
    assert result.master_id == "official_gbt_minutes"
    assert "2026年7月9日" in text
    assert "印发机关" not in text


def test_assemble_official_document_omits_empty_optional_paragraphs(tmp_path):
    result = assemble_official_document_docx(
        "notice",
        {
            "title": "无附件通知",
            "body": "本通知没有主送、附件说明或署名机关。",
            "organization": "示例单位",
            "document_no": "示发〔2026〕9号",
            "issue_date": "2026年7月10日",
        },
        tmp_path,
        filename="without_optional_paragraphs.docx",
    )

    assert result.ok is True
    assert result.docx_path is not None
    document = Document(result.docx_path)
    paragraph_texts = [paragraph.text.strip() for paragraph in document.paragraphs]
    assert "附件：" not in paragraph_texts
    assert "：" not in paragraph_texts
    assert "official_attachment_note" not in result.replaced_placeholders
    assert "official_recipient" not in result.replaced_placeholders
    assert "official_issuer" not in result.replaced_placeholders


def test_assemble_official_document_honors_removed_builtin_fields(tmp_path):
    result = assemble_official_document_docx(
        "notice",
        {
            "body": "正文保留，标题由资料包明确删除。",
            "organization": "示例单位",
            "document_no": "示发〔2026〕11号",
            "issue_date": "2026年7月11日",
        },
        tmp_path,
        filename="removed-title.docx",
        removed_field_keys={"title"},
    )

    assert result.ok is True
    assert result.missing_required_fields == ()
    assert result.docx_path is not None
    assert "{{@text:official_title}}" not in _all_docx_text(result.docx_path)


def test_assemble_official_document_generates_optional_review_pdf(tmp_path):
    rendered_sources = []

    def fake_renderer(source_path, target_path):
        rendered_sources.append(source_path)
        assert "内部审阅稿" in _all_docx_text(source_path)
        target_path.write_bytes(b"%PDF-1.4\n% review\n")

    result = assemble_official_document_docx(
        "notice",
        {
            "title": "带审阅 PDF 的通知",
            "body": "用于验证审阅 PDF 可选交付。",
            "organization": "示例单位",
            "document_no": "示发〔2026〕10号",
            "issue_date": "2026年7月10日",
        },
        tmp_path,
        filename="review_pdf.docx",
        generate_review_pdf=True,
        review_pdf_renderer_resolver=lambda: ("fake_pdf", fake_renderer),
    )

    assert result.ok is True
    assert result.review_pdf_status == "generated"
    assert result.review_pdf_renderer == "fake_pdf"
    assert result.review_pdf_issue == ""
    assert result.review_pdf_path == tmp_path / "review_pdf_review.pdf"
    assert result.review_pdf_path.is_file()
    assert len(rendered_sources) == 1
    assert rendered_sources[0].name == result.internal_review_docx_path.name
    assert rendered_sources[0] != result.internal_review_docx_path
    assert result.output_paths["review_pdf"] == str(result.review_pdf_path)
    archive_manifest = json.loads(result.archive_manifest_path.read_text(encoding="utf-8"))
    assert archive_manifest["review_pdf"] == {
        "status": "generated",
        "path": str(result.review_pdf_path),
        "renderer": "fake_pdf",
        "issue": "",
    }
    assert archive_manifest["output_paths"]["review_pdf"] == str(result.review_pdf_path)


def test_assemble_official_document_degrades_when_review_pdf_renderer_unavailable(tmp_path):
    result = assemble_official_document_docx(
        "notice",
        {
            "title": "无 PDF 渲染器通知",
            "body": "DOCX 交付仍应成功。",
            "organization": "示例单位",
            "document_no": "示发〔2026〕11号",
            "issue_date": "2026年7月10日",
        },
        tmp_path,
        filename="renderer_unavailable.docx",
        generate_review_pdf=True,
        review_pdf_renderer_resolver=lambda: None,
    )

    assert result.ok is True
    assert result.review_pdf_status == "renderer_unavailable"
    assert result.review_pdf_path is None
    assert result.review_pdf_renderer == ""
    assert result.review_pdf_issue == "docx_to_pdf_renderer_unavailable"
    assert "review_pdf" not in result.output_paths
    archive_manifest = json.loads(result.archive_manifest_path.read_text(encoding="utf-8"))
    assert archive_manifest["review_pdf"]["status"] == "renderer_unavailable"
    assert archive_manifest["review_pdf"]["path"] == ""
    assert "review_pdf" not in archive_manifest["output_paths"]


def test_assemble_official_document_degrades_and_removes_failed_review_pdf(tmp_path):
    def broken_renderer(_source_path, target_path):
        target_path.write_bytes(b"partial")
        raise RuntimeError("renderer crashed")

    result = assemble_official_document_docx(
        "notice",
        {
            "title": "PDF 失败通知",
            "body": "PDF 失败不能破坏 DOCX 交付。",
            "organization": "示例单位",
            "document_no": "示发〔2026〕12号",
            "issue_date": "2026年7月10日",
        },
        tmp_path,
        filename="renderer_failed.docx",
        generate_review_pdf=True,
        review_pdf_renderer_resolver=lambda: ("broken_pdf", broken_renderer),
    )

    assert result.ok is True
    assert result.review_pdf_status == "render_failed"
    assert result.review_pdf_path is None
    assert result.review_pdf_renderer == "broken_pdf"
    assert "renderer crashed" in result.review_pdf_issue
    assert "review_pdf" not in result.output_paths
    assert not (tmp_path / "renderer_failed_review.pdf").exists()


def test_assemble_official_document_blocks_missing_required_fields(tmp_path):
    result = assemble_official_document_docx(
        "notice",
        {
            "title": "缺正文的通知",
            "organization": "示例单位",
            "document_no": "示发〔2026〕1号",
            "issue_date": "2026年7月9日",
        },
        tmp_path,
    )

    assert result.status == "missing_required_fields"
    assert result.docx_path is None
    assert result.output_paths == {}
    assert result.missing_required_fields == ("body",)


def test_assemble_official_document_blocks_unknown_profile(tmp_path):
    result = assemble_official_document_docx(
        "unknown_official_type",
        {
            "title": "未知文种",
            "body": "正文",
        },
        tmp_path,
    )

    assert result.status == "unknown_profile"
    assert result.docx_path is None
    assert result.output_paths == {}


def test_assemble_official_document_auto_routes_stale_builtin_master(tmp_path):
    common = default_master("official")
    assert common is not None

    result = assemble_official_document_docx(
        "letter",
        {
            "title": "测试函",
            "body": "函件正文。",
            "organization": "测试单位",
            "document_no": "测函〔2026〕1号",
            "issue_date": "2026年7月11日",
        },
        tmp_path,
        master=common,
    )

    assert result.ok is True
    assert result.master_id == "official_gbt_letter"


def test_assemble_official_document_blocks_incompatible_user_layout(tmp_path):
    common = default_master("official")
    assert common is not None
    user_common = replace(common, source_type="user", readonly=False)

    result = assemble_official_document_docx(
        "minutes",
        {
            "title": "会议纪要",
            "body": "会议正文。",
            "organization": "测试单位",
            "document_no": "第1期",
            "issue_date": "2026年7月11日",
        },
        tmp_path,
        master=user_common,
    )

    assert result.status == "master_incompatible"
