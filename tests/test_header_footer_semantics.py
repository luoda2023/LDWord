import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.feature_configs import PageNumberPhaseConfig
from src.config.resolved import ResolvedConfig
from src.modules.basic.header_footer import (
    HeaderFooterModule,
    _paragraph_has_field,
    _set_header_border,
    _set_page_number,
)
from src.modules.basic.section_format import _ensure_section_break_before_paragraph
from src.modules.structure.heading_recognition import DocSection, DocTree
from src.pipeline.context import PipelineContext
from src.pipeline.tracker import ChangeTracker
from src.shared.engine.field_builder import iter_field_instructions
from src.shared.engine.ooxml_ops import qn


def test_header_footer_none_clears_existing_header_and_border():
    doc = Document()
    section = doc.sections[0]
    section.header.paragraphs[0].add_run("Legacy Header")
    _set_header_border(section, True)

    config = ResolvedConfig()
    config.header_footer.header_mode = "none"
    config.header_footer.header_border = True

    HeaderFooterModule().apply(doc, config, ChangeTracker(), PipelineContext())

    para = section.header.paragraphs[0]
    bottom = para._element.find(qn("w:pPr")).find(qn("w:pBdr")).find(qn("w:bottom"))

    assert para.text == ""
    assert bottom is not None
    assert bottom.get(qn("w:val")) == "none"


def test_header_footer_page_number_disabled_removes_existing_page_field():
    doc = Document()
    section = doc.sections[0]

    config = ResolvedConfig()
    _set_page_number(section, config.header_footer)
    assert _paragraph_has_field(section.footer.paragraphs[0], "PAGE") is True

    config.header_footer.page_number_enabled = False
    HeaderFooterModule().apply(doc, config, ChangeTracker(), PipelineContext())

    assert _paragraph_has_field(section.footer.paragraphs[0], "PAGE") is False
    assert section.footer.paragraphs[0].text == ""


def _build_sectioned_doc():
    doc = Document()
    doc.add_paragraph("封面")
    doc.add_paragraph("目录")
    doc.add_paragraph("第一章 绪论")
    doc.add_paragraph("正文内容")
    doc.add_paragraph("参考文献")

    _ensure_section_break_before_paragraph(doc, 1, "nextPage")
    _ensure_section_break_before_paragraph(doc, 2, "nextPage")
    _ensure_section_break_before_paragraph(doc, 4, "nextPage")
    return doc


def _build_doc_tree():
    return DocTree(
        sections=[
            DocSection("cover", 0, 1),
            DocSection("toc", 1, 2),
            DocSection("body", 2, 4),
            DocSection("references", 4, 5),
        ]
    )


def _apply_thesis_page_plan(config):
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
            selectors=["body", "back_matter"],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
    ]


def _page_num_type(section):
    elem = section._sectPr.find(qn("w:pgNumType"))
    assert elem is not None
    return elem.get(qn("w:fmt")), elem.get(qn("w:start"))


def _field_instr_texts(para):
    return [" ".join((instr or "").split()) for _kind, _elem, instr in iter_field_instructions(para._element)]


def test_header_footer_doc_tree_strategy_hides_cover_and_restarts_front_and_body_numbering():
    doc = _build_sectioned_doc()
    config = ResolvedConfig()
    _apply_thesis_page_plan(config)
    context = PipelineContext(doc_tree=_build_doc_tree())

    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    cover, toc, body, references = list(doc.sections)

    assert cover.header.paragraphs[0].text == ""
    assert cover.footer.paragraphs[0].text == ""

    assert _paragraph_has_field(toc.footer.paragraphs[0], "PAGE") is True
    assert _page_num_type(toc) == ("upperRoman", "1")

    assert _paragraph_has_field(body.footer.paragraphs[0], "PAGE") is True
    assert _page_num_type(body) == ("decimal", "1")

    assert _paragraph_has_field(references.footer.paragraphs[0], "PAGE") is True
    assert _page_num_type(references) == ("decimal", None)

    ref_instrs = _field_instr_texts(references.header.paragraphs[0])
    assert any('STYLEREF "Heading 1 Unnumbered"' in instr for instr in ref_instrs)
    assert all("\\n" not in instr for instr in ref_instrs)


def test_header_footer_page_number_strategy_supports_lower_roman_front_matter_and_optional_body_restart():
    doc = _build_sectioned_doc()
    config = ResolvedConfig()
    config.header_footer.front_matter_page_number_format = "lowerRoman"
    config.header_footer.restart_body_page_number = False
    context = PipelineContext(doc_tree=_build_doc_tree())

    HeaderFooterModule().apply(doc, config, ChangeTracker(), context)

    _cover, toc, body, references = list(doc.sections)

    assert _page_num_type(toc) == ("lowerRoman", "1")
    assert _page_num_type(body) == ("decimal", None)
    assert _page_num_type(references) == ("decimal", None)
