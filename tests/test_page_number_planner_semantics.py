import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.feature_configs import PageNumberPhaseConfig
from src.config.resolved import ResolvedConfig
from src.modules.basic.header_footer import HeaderFooterModule
from src.modules.basic.section_format import SectionFormatModule
from src.modules.structure.heading_recognition import DocSection, DocTree
from src.pipeline.context import PipelineContext
from src.pipeline.tracker import ChangeTracker
from src.shared.engine.field_builder import iter_field_instructions
from src.shared.engine.ooxml_ops import qn
from src.shared.engine.page_number_planner import (
    build_page_number_execution_plan,
    collect_static_page_number_diagnostics,
)


def _build_doc():
    doc = Document()
    doc.add_paragraph("封面")
    doc.add_paragraph("目录")
    doc.add_heading("第一章 绪论", level=1)
    doc.add_paragraph("正文内容 A")
    doc.add_heading("第二章 方法", level=1)
    doc.add_paragraph("正文内容 B")
    doc.add_paragraph("附录 A")
    doc.add_paragraph("附录内容")
    return doc


def _build_context():
    return PipelineContext(
        doc_tree=DocTree(
            sections=[
                DocSection("cover", 0, 1),
                DocSection("toc", 1, 2),
                DocSection("body", 2, 6),
                DocSection("appendix", 6, 8),
            ]
        ),
        heading_map={2: 1, 4: 1},
    )


def _build_config():
    config = ResolvedConfig()
    config.header_footer.page_number_plan.phases = [
        PageNumberPhaseConfig(
            phase_id="front",
            selectors=["front_matter"],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=["body"],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="appendix",
            selectors=["appendix"],
            visible=True,
            number_format="lowerRoman",
            start_mode="restart",
            start_value=1,
        ),
    ]
    return config


def _page_num_type(section):
    elem = section._sectPr.find(qn("w:pgNumType"))
    assert elem is not None
    return elem.get(qn("w:fmt")), elem.get(qn("w:start"))


def _field_instr_texts(para):
    return [" ".join((instr or "").split()) for _kind, _elem, instr in iter_field_instructions(para._element)]


def test_page_number_planner_marks_body_heading_and_phase_change_boundaries():
    plan = build_page_number_execution_plan(_build_doc(), _build_context(), _build_config().header_footer)

    assert [(item.start_index, item.section_type, item.phase_id) for item in plan.boundaries] == [
        (1, "toc", "front"),
        (2, "body", "body"),
        (4, "body", "body"),
        (6, "appendix", "appendix"),
    ]
    assert plan.boundaries[0].reasons == ("section_start", "phase_change")
    assert plan.boundaries[1].reasons == ("section_start", "phase_change")
    assert plan.boundaries[2].reasons == ("body_heading",)
    assert plan.boundaries[3].reasons == ("section_start", "phase_change")


def test_section_format_and_header_footer_share_phase_plan_without_restarting_same_body_phase():
    doc = _build_doc()
    context = _build_context()
    config = _build_config()

    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    cover, toc, body_first, body_second, appendix = list(doc.sections)

    assert _page_num_type(toc) == ("upperRoman", "1")
    assert _page_num_type(body_first) == ("decimal", "1")
    assert _page_num_type(body_second) == ("decimal", None)
    assert _page_num_type(appendix) == ("lowerRoman", "1")

    appendix_instrs = _field_instr_texts(appendix.footer.paragraphs[0])
    assert any("PAGE \\* roman" in instr for instr in appendix_instrs)


def test_pre_numbering_suppresses_statement_pages_before_front_matter():
    doc = Document()
    for text in ["封面", "原创性声明", "授权书", "摘要", "第一章 绪论"]:
        doc.add_paragraph(text)

    context = PipelineContext(
        doc_tree=DocTree(
            sections=[
                DocSection("cover", 0, 1),
                DocSection("statement", 1, 2),
                DocSection("authorization", 2, 3),
                DocSection("abstract_cn", 3, 4),
                DocSection("body", 4, 5),
            ]
        ),
        heading_map={4: 1},
    )
    config = ResolvedConfig()
    config.header_footer.suppress_header_footer_selectors = ["pre_numbering"]
    config.header_footer.page_number_plan.phases = [
        PageNumberPhaseConfig(
            phase_id="front",
            selectors=["front_matter"],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=["body"],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
    ]

    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    cover, statement, authorization, abstract, body = list(doc.sections)
    for suppressed_section in (cover, statement, authorization):
        assert not any("PAGE" in instr for instr in _field_instr_texts(suppressed_section.footer.paragraphs[0]))
        assert suppressed_section.header.paragraphs[0].text == ""

    assert _page_num_type(abstract) == ("upperRoman", "1")
    assert any("PAGE \\* ROMAN" in instr for instr in _field_instr_texts(abstract.footer.paragraphs[0]))
    assert _page_num_type(body) == ("decimal", "1")
    assert any("PAGE" in instr for instr in _field_instr_texts(body.footer.paragraphs[0]))


def test_header_footer_validate_warns_when_doc_tree_is_missing():
    issues = HeaderFooterModule().validate(Document(), ResolvedConfig(), PipelineContext())

    assert issues
    assert issues[0].level == "warning"
    assert "未识别到文档结构" in issues[0].message
    assert "处理：" in issues[0].message
    assert issues[0].location == "context.doc_tree"


def test_header_footer_validate_warns_for_cover_hide_even_when_page_numbers_are_off():
    config = ResolvedConfig()
    config.header_footer.page_number_enabled = False
    config.header_footer.hide_cover_header_footer = True

    issues = HeaderFooterModule().validate(Document(), config, PipelineContext())

    assert issues
    assert issues[0].level == "warning"
    assert "分区排除" in issues[0].message
    assert issues[0].location == "context.doc_tree"


def test_section_format_validate_rejects_overlapping_page_number_phases_in_strict_mode():
    config = _build_config()
    config.header_footer.page_number_plan.validation_mode = "strict"
    config.header_footer.page_number_plan.phases[1].selectors = ["body", "back_matter"]
    issues = SectionFormatModule().validate(_build_doc(), config, _build_context())

    assert any(issue.level == "error" for issue in issues)
    assert any("同时属于多个编号分组" in issue.message for issue in issues)
    assert any("处理：" in issue.message for issue in issues)


def test_header_footer_validate_downgrades_phase_overlap_to_warning_in_warn_mode():
    config = _build_config()
    config.header_footer.page_number_plan.validation_mode = "warn"
    config.header_footer.page_number_plan.phases[1].selectors = ["body", "back_matter"]
    issues = HeaderFooterModule().validate(_build_doc(), config, _build_context())

    assert any(issue.level == "error" for issue in issues)
    assert any("同时属于多个编号分组" in issue.message for issue in issues)


def test_empty_page_number_plan_defaults_to_continuous_decimal():
    doc = _build_doc()
    config = ResolvedConfig()
    config.header_footer.page_number_plan.phases = []
    context = _build_context()
    SectionFormatModule().apply(doc, config, ChangeTracker(), context)

    plan = build_page_number_execution_plan(doc, context, config.header_footer)

    assert collect_static_page_number_diagnostics(config.header_footer) == []
    assert [(section.phase_id, section.number_format, section.start_value) for section in plan.sections[:3]] == [
        (None, "decimal", None),
        ("main", "decimal", 1),
        ("main", "decimal", None),
    ]


def test_collect_static_page_number_diagnostics_flags_empty_selectors():
    config = _build_config()
    config.header_footer.page_number_plan.phases = []

    diagnostics = collect_static_page_number_diagnostics(config.header_footer)

    assert diagnostics == []

    config.header_footer.page_number_plan.phases = [
        PageNumberPhaseConfig(
            phase_id="broken",
            selectors=[],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
    ]

    diagnostics = collect_static_page_number_diagnostics(config.header_footer)

    assert len(diagnostics) == 1
    assert "尚未选择范围" in diagnostics[0].message
    assert "删除这个空分组" in diagnostics[0].suggestion


def test_collect_static_page_number_diagnostics_flags_duplicate_phase_ids():
    config = _build_config()
    config.header_footer.page_number_plan.phases[1].phase_id = "front"

    diagnostics = collect_static_page_number_diagnostics(config.header_footer)

    assert any(item.level == "error" for item in diagnostics)
    assert any("编号分组名称" in item.message and "重复" in item.message for item in diagnostics)


def test_collect_static_page_number_diagnostics_warns_when_hidden_range_masks_rule():
    config = _build_config()
    config.header_footer.suppress_header_footer_selectors = ["toc"]

    diagnostics = collect_static_page_number_diagnostics(config.header_footer)

    assert any(item.level == "warning" for item in diagnostics)
    assert any("包含已排除部分" in item.message for item in diagnostics)
