import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.feature_configs import PageNumberPhaseConfig
from src.config.header_footer_presets import toc_roman_body_decimal_phases
from src.config.resolved import ResolvedConfig
from src.config.special_title_rules import special_title_selector
from src.modules.basic.header_footer import HeaderFooterModule, _paragraph_has_field
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


def test_page_number_planner_marks_semantic_and_phase_change_boundaries():
    plan = build_page_number_execution_plan(_build_doc(), _build_context(), _build_config().header_footer)

    assert [(item.start_index, item.section_type, item.phase_id) for item in plan.boundaries] == [
        (1, "toc", "front"),
        (2, "body", "body"),
        (6, "appendix", "appendix"),
    ]
    assert plan.boundaries[0].reasons == ("section_start", "phase_change")
    assert plan.boundaries[1].reasons == ("section_start", "phase_change")
    assert plan.boundaries[2].reasons == ("section_start", "phase_change")


def test_section_format_and_header_footer_share_phase_plan_without_restarting_same_body_phase():
    doc = _build_doc()
    context = _build_context()
    config = _build_config()

    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    cover, toc, body, appendix = list(doc.sections)

    assert _page_num_type(toc) == ("upperRoman", "1")
    assert _page_num_type(body) == ("decimal", "1")
    assert _page_num_type(appendix) == ("lowerRoman", "1")

    appendix_instrs = _field_instr_texts(appendix.footer.paragraphs[0])
    assert any("PAGE \\* roman" in instr for instr in appendix_instrs)
    for section in doc.sections:
        child_tags = [child.tag for child in section._sectPr]
        if qn("w:type") in child_tags:
            assert child_tags.index(qn("w:type")) < child_tags.index(qn("w:pgSz"))
        if qn("w:pgNumType") in child_tags:
            assert child_tags.index(qn("w:pgNumType")) < child_tags.index(qn("w:cols"))


def test_pre_numbering_selector_suppresses_only_cover():
    doc = Document()
    for text in ["封面", "原创性声明", "授权书", "摘要", "第一章 绪论"]:
        doc.add_paragraph(text)

    context = PipelineContext(
        doc_tree=DocTree(
            sections=[
                DocSection("cover", 0, 1),
                DocSection("body", 1, 3),
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

    cover, unclassified_body, abstract, body = list(doc.sections)
    assert not any("PAGE" in instr for instr in _field_instr_texts(cover.footer.paragraphs[0]))
    assert cover.header.paragraphs[0].text == ""
    assert any("PAGE" in instr for instr in _field_instr_texts(unclassified_body.footer.paragraphs[0]))

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
    assert "页眉和页脚文字范围" in issues[0].message
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
        ("pre_numbering", "decimal", 1),
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


def test_header_hidden_range_does_not_override_page_number_rule():
    config = _build_config()
    config.header_footer.header.hidden_selectors = ["toc"]

    diagnostics = collect_static_page_number_diagnostics(config.header_footer)

    assert diagnostics == []
    doc = _build_doc()
    context = _build_context()
    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    plan = build_page_number_execution_plan(doc, context, config.header_footer)
    toc = next(section for section in plan.sections if section.section_type == "toc")
    assert toc.header_visible is False
    assert toc.footer_text_visible is True
    assert toc.page_number_visible is True


def test_hidden_abstract_pages_count_into_roman_toc_then_body_restarts_decimal():
    doc = Document()
    for text in ["封面", "摘要", "Abstract", "目录", "第一章 绪论"]:
        doc.add_paragraph(text)
    context = PipelineContext(
        doc_tree=DocTree(
            sections=[
                DocSection("cover", 0, 1),
                DocSection("abstract_cn", 1, 2),
                DocSection("abstract_en", 2, 3),
                DocSection("toc", 3, 4),
                DocSection("body", 4, 5),
            ]
        ),
        heading_map={4: 1},
    )
    config = ResolvedConfig()
    phases = toc_roman_body_decimal_phases()
    phases[2].start_mode = "continue"
    config.header_footer.page_number_plan.phases = phases

    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    cover, abstract_cn, abstract_en, toc, body = list(doc.sections)
    assert not _paragraph_has_field(cover.footer.paragraphs[0], "PAGE")
    assert not _paragraph_has_field(abstract_cn.footer.paragraphs[0], "PAGE")
    assert not _paragraph_has_field(abstract_en.footer.paragraphs[0], "PAGE")
    assert _page_num_type(abstract_cn) == ("upperRoman", "1")
    assert _page_num_type(abstract_en) == ("upperRoman", None)
    assert _page_num_type(toc) == ("upperRoman", None)
    assert _paragraph_has_field(toc.footer.paragraphs[0], "PAGE")
    assert _page_num_type(body) == ("decimal", "1")
    assert _paragraph_has_field(body.footer.paragraphs[0], "PAGE")


def test_toc_only_roman_preset_restarts_toc_at_i():
    phases = toc_roman_body_decimal_phases()

    assert phases[1].phase_id == "front_hidden"
    assert phases[1].visible is False
    assert phases[2].phase_id == "toc"
    assert phases[2].number_format == "upperRoman"
    assert phases[2].start_mode == "restart"
    assert phases[2].start_value == 1
    assert phases[3].phase_id == "body"
    assert phases[3].number_format == "decimal"
    assert phases[3].start_mode == "restart"
    assert phases[3].start_value == 1


def test_header_footer_text_and_page_number_visibility_are_three_channels():
    doc = _build_doc()
    context = _build_context()
    config = _build_config()
    config.header_footer.header.hidden_selectors = ["toc"]
    config.header_footer.footer.hidden_selectors = ["appendix"]
    config.header_footer.footer.content_mode = "fixed"
    config.header_footer.footer_text = "内部资料"

    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    _cover, toc, body, appendix = list(doc.sections)
    assert toc.header.paragraphs[0].text == ""
    assert "内部资料" in toc.footer.paragraphs[0].text
    assert _paragraph_has_field(toc.footer.paragraphs[0], "PAGE")
    assert appendix.header.paragraphs[0].text != ""
    assert "内部资料" not in appendix.footer.paragraphs[0].text
    assert _paragraph_has_field(appendix.footer.paragraphs[0], "PAGE")


def test_literal_special_title_scope_has_its_own_boundaries_and_phase_priority():
    doc = Document()
    for text in ["第一章 绪论", "摘要", "摘要正文", "第二章 方法", "方法正文"]:
        doc.add_paragraph(text)
    selector = special_title_selector("exact", "摘要")
    context = PipelineContext(
        doc_tree=DocTree(
            sections=[DocSection("body", 0, 5)],
            special_title_matches={1: selector},
            special_title_ranges=[DocSection(selector, 1, 3)],
        ),
        heading_map={0: 1, 1: 1, 3: 1},
    )
    config = ResolvedConfig()
    config.header_footer.header.hidden_selectors = [selector]
    config.header_footer.footer.hidden_selectors = ["body"]
    config.header_footer.page_number_plan.phases = [
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=["body"],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="summary",
            selectors=[selector],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
    ]

    before_breaks = build_page_number_execution_plan(
        doc,
        context,
        config.header_footer,
    )
    assert [
        (item.start_index, item.reasons)
        for item in before_breaks.boundaries
    ] == [
        (1, ("special_title_start", "phase_change")),
        (3, ("special_title_end", "phase_change")),
    ]

    SectionFormatModule().apply(doc, config, ChangeTracker(), context)
    plan = build_page_number_execution_plan(doc, context, config.header_footer)

    assert [item.start_index for item in plan.sections] == [0, 1, 3]
    assert plan.sections[1].phase_id == "summary"
    assert plan.sections[1].number_format == "upperRoman"
    assert plan.sections[1].header_visible is False
    assert plan.sections[1].footer_text_visible is True
    assert plan.sections[2].phase_id == "body"
    assert plan.sections[2].header_visible is True
    assert plan.sections[2].footer_text_visible is False
