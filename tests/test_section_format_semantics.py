import sys
from pathlib import Path
from types import SimpleNamespace

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.resolved import ResolvedConfig
from src.modules.basic.section_format import SectionFormatModule
from src.modules.structure.heading_recognition import DocSection
from src.pipeline.context import PipelineContext
from src.pipeline.tracker import ChangeTracker
from src.shared.engine.ooxml_ops import qn


def _fake_doc_tree(sections):
    return SimpleNamespace(
        sections=sections,
        get_section=lambda name: next((section for section in sections if section.section_type == name), None),
    )


def _section_break_type(para):
    ppr = para._element.find(qn("w:pPr"))
    if ppr is None:
        return None
    sect_pr = ppr.find(qn("w:sectPr"))
    if sect_pr is None:
        return None
    type_elem = sect_pr.find(qn("w:type"))
    if type_elem is None:
        return "nextPage"
    return type_elem.get(qn("w:val"))


def test_section_format_inserts_next_page_breaks_for_body_chapters_and_back_matter():
    doc = Document()
    doc.add_paragraph("Cover")
    doc.add_heading("Chapter 1 Intro", level=1)
    doc.add_paragraph("Body paragraph")
    doc.add_heading("Chapter 2 Method", level=1)
    doc.add_paragraph("More body")
    doc.add_paragraph("References")
    doc.add_paragraph("[1] Ref entry")

    sections = [
        DocSection("cover", 0, 1, confidence=10.0),
        DocSection("body", 1, 5, confidence=10.0),
        DocSection("references", 5, 7, confidence=10.0),
    ]
    context = PipelineContext(
        doc_tree=_fake_doc_tree(sections),
        heading_map={1: 1, 3: 1},
    )

    SectionFormatModule().apply(doc, ResolvedConfig(), ChangeTracker(), context)

    assert _section_break_type(doc.paragraphs[0]) == "nextPage"
    assert _section_break_type(doc.paragraphs[2]) == "nextPage"
    assert _section_break_type(doc.paragraphs[4]) == "nextPage"


def test_section_format_skips_break_insertion_when_table_sits_between_paragraphs():
    doc = Document()
    doc.add_paragraph("Cover")
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "value"
    doc.add_paragraph("Chapter 1 Intro")

    sections = [
        DocSection("cover", 0, 1, confidence=10.0),
        DocSection("body", 1, 2, confidence=10.0),
    ]
    context = PipelineContext(
        doc_tree=_fake_doc_tree(sections),
        heading_map={1: 1},
    )

    SectionFormatModule().apply(doc, ResolvedConfig(), ChangeTracker(), context)

    assert _section_break_type(doc.paragraphs[0]) is None
