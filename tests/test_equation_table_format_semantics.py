import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from lxml import etree


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.resolved import ResolvedConfig
from src.modules.special.equation_table_format import EquationTableFormatModule
from src.pipeline.context import PipelineContext
from src.pipeline.tracker import ChangeTracker
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.line_spacing_ops import apply_line_spacing, sync_spacing_ooxml
from src.shared.engine.ooxml_ops import qn


def test_equation_table_format_applies_formula_and_unified_number_typography():
    doc, table, formula_para, number_para = _build_equation_table_doc()

    config = ResolvedConfig()
    config.formula_table.block_alignment = "left"
    config.formula_table.formula_font_name = "Cambria Math"
    config.formula_table.formula_font_size_pt = 16.0
    config.formula_table.formula_line_spacing = 1.75
    config.formula_table.formula_space_before_pt = 9.0
    config.formula_table.formula_space_after_pt = 11.0
    config.formula_style.unify_font = True
    config.formula_style.unify_size = True
    config.formula_style.unify_spacing = True

    EquationTableFormatModule().apply(doc, config, ChangeTracker(), PipelineContext())

    tbl_jc = table._element.find(qn("w:tblPr")).find(qn("w:jc"))
    assert tbl_jc is not None
    assert tbl_jc.get(qn("w:val")) == "left"

    assert formula_para.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.LEFT
    assert number_para.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.RIGHT

    formula_spacing = _spacing(formula_para)
    assert formula_spacing.get(qn("w:before")) == "180"
    assert formula_spacing.get(qn("w:after")) == "220"
    assert formula_spacing.get(qn("w:line")) == "420"
    assert formula_spacing.get(qn("w:lineRule")) == "auto"

    number_spacing = _spacing(number_para)
    assert number_spacing.get(qn("w:before")) == "180"
    assert number_spacing.get(qn("w:after")) == "220"
    assert number_spacing.get(qn("w:line")) == "420"
    assert number_spacing.get(qn("w:lineRule")) == "auto"

    resolved_formula_font = resolve_font("Cambria Math", lang="en")
    math_r_pr = _first_math_word_rpr(formula_para)
    assert math_r_pr.find(qn("w:rFonts")).get(qn("w:ascii")) == resolved_formula_font
    assert math_r_pr.find(qn("w:rFonts")).get(qn("w:hAnsi")) == resolved_formula_font
    assert math_r_pr.find(qn("w:rFonts")).get(qn("w:cs")) == resolved_formula_font
    assert math_r_pr.find(qn("w:sz")).get(qn("w:val")) == "32"
    assert math_r_pr.find(qn("w:szCs")).get(qn("w:val")) == "32"

    number_r_pr = _word_rpr(number_para.runs[0])
    assert number_r_pr.find(qn("w:rFonts")).get(qn("w:ascii")) == resolved_formula_font
    assert number_r_pr.find(qn("w:rFonts")).get(qn("w:hAnsi")) == resolved_formula_font
    assert number_r_pr.find(qn("w:rFonts")).get(qn("w:cs")) == resolved_formula_font
    assert number_r_pr.find(qn("w:sz")).get(qn("w:val")) == "32"
    assert number_r_pr.find(qn("w:szCs")).get(qn("w:val")) == "32"


def test_equation_table_format_applies_formula_spacing_units():
    doc, _table, formula_para, number_para = _build_equation_table_doc()

    config = ResolvedConfig()
    config.formula_table.formula_line_spacing = 1.5
    config.formula_table.formula_space_before_pt = 2.0
    config.formula_table.formula_space_before_unit = "lines"
    config.formula_table.formula_space_after_pt = 0.0
    config.formula_table.formula_space_after_unit = "auto"
    config.formula_style.unify_spacing = True

    EquationTableFormatModule().apply(doc, config, ChangeTracker(), PipelineContext())

    for paragraph in (formula_para, number_para):
        spacing = _spacing(paragraph)
        assert spacing.get(qn("w:before")) is None
        assert spacing.get(qn("w:beforeLines")) == "200"
        assert spacing.get(qn("w:after")) is None
        assert spacing.get(qn("w:afterAutospacing")) == "1"


def test_equation_table_format_uses_number_specific_font_size_and_preserves_spacing_when_not_unified():
    doc, _table, formula_para, number_para = _build_equation_table_doc()

    config = ResolvedConfig()
    config.formula_table.formula_font_name = "Times New Roman"
    config.formula_table.formula_font_size_pt = 15.0
    config.formula_table.formula_line_spacing = 2.0
    config.formula_table.formula_space_before_pt = 8.0
    config.formula_table.formula_space_after_pt = 6.0
    config.formula_table.number_font_name = "Courier New"
    config.formula_table.number_font_size_pt = 10.0
    config.formula_style.unify_font = False
    config.formula_style.unify_size = False
    config.formula_style.unify_spacing = False

    EquationTableFormatModule().apply(doc, config, ChangeTracker(), PipelineContext())

    formula_spacing = _spacing(formula_para)
    assert formula_spacing.get(qn("w:before")) == "160"
    assert formula_spacing.get(qn("w:after")) == "120"
    assert formula_spacing.get(qn("w:line")) == "480"
    assert formula_spacing.get(qn("w:lineRule")) == "auto"

    number_spacing = _spacing(number_para)
    assert number_spacing.get(qn("w:before")) == "60"
    assert number_spacing.get(qn("w:after")) == "80"
    assert number_spacing.get(qn("w:line")) == "360"
    assert number_spacing.get(qn("w:lineRule")) == "auto"

    resolved_formula_font = resolve_font("Times New Roman", lang="en")
    math_r_pr = _first_math_word_rpr(formula_para)
    assert math_r_pr.find(qn("w:rFonts")).get(qn("w:ascii")) == resolved_formula_font
    assert math_r_pr.find(qn("w:sz")).get(qn("w:val")) == "30"
    assert math_r_pr.find(qn("w:szCs")).get(qn("w:val")) == "30"

    resolved_number_font = resolve_font("Courier New", lang="en")
    number_r_pr = _word_rpr(number_para.runs[0])
    assert number_r_pr.find(qn("w:rFonts")).get(qn("w:ascii")) == resolved_number_font
    assert number_r_pr.find(qn("w:rFonts")).get(qn("w:hAnsi")) == resolved_number_font
    assert number_r_pr.find(qn("w:rFonts")).get(qn("w:cs")) == resolved_number_font
    assert number_r_pr.find(qn("w:sz")).get(qn("w:val")) == "20"
    assert number_r_pr.find(qn("w:szCs")).get(qn("w:val")) == "20"


def test_equation_table_format_normalizes_existing_numbering_by_chapter():
    doc = Document()
    doc.add_heading("第一章 绪论", level=1)
    table_1 = _add_equation_table(doc, ["(9-9)", "(9-10)"])
    doc.add_heading("第二章 方法", level=1)
    table_2 = _add_equation_table(doc, ["（99）"])

    config = ResolvedConfig()
    config.equation_numbering.numbering_format = "chapter.seq"
    context = PipelineContext(heading_map={0: 1, 1: 1})

    EquationTableFormatModule().apply(doc, config, ChangeTracker(), context)

    assert table_1.cell(0, 1).text == "(1.1)"
    assert table_1.cell(1, 1).text == "(1.2)"
    assert table_2.cell(0, 1).text == "（2.1）"


def test_equation_table_format_normalizes_existing_numbering_globally_without_wrappers():
    doc = Document()
    doc.add_heading("第一章 绪论", level=1)
    table_1 = _add_equation_table(doc, ["9-9"])
    doc.add_heading("第二章 方法", level=1)
    table_2 = _add_equation_table(doc, ["(8-8)"])

    config = ResolvedConfig()
    config.equation_numbering.numbering_format = "global"
    context = PipelineContext(heading_map={0: 1, 1: 1})

    EquationTableFormatModule().apply(doc, config, ChangeTracker(), context)

    assert table_1.cell(0, 1).text == "1"
    assert table_2.cell(0, 1).text == "(2)"


def test_equation_table_format_skips_chapter_numbering_without_heading_context():
    doc = Document()
    table = _add_equation_table(doc, ["(9-9)"])

    config = ResolvedConfig()
    config.equation_numbering.numbering_format = "chapter.seq"
    tracker = ChangeTracker()

    EquationTableFormatModule().apply(doc, config, tracker, PipelineContext())

    assert table.cell(0, 1).text == "(9-9)"
    records = tracker.get_by_module("equation_table_format")
    assert any(record.change_type == "skip" for record in records)


def _build_equation_table_doc():
    doc = Document()
    table = doc.add_table(rows=1, cols=2)

    formula_para = table.cell(0, 0).paragraphs[0]
    _append_math_formula(
        formula_para,
        [
            ("x", "Arial", "20"),
            ("=", "Arial", "20"),
            ("1", "Arial", "20"),
        ],
    )
    formula_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _seed_spacing(formula_para, before_pt=2.0, after_pt=3.0, line_spacing=1.0)

    number_para = table.cell(0, 1).paragraphs[0]
    number_run = number_para.add_run("(1-1)")
    number_run.font.name = "Arial"
    number_run.font.size = Pt(9.0)
    _seed_word_run_rpr(number_run, font_name="Arial", half_points="18")
    number_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _seed_spacing(number_para, before_pt=3.0, after_pt=4.0, line_spacing=1.5)

    return doc, table, formula_para, number_para


def _add_equation_table(doc: Document, numbers: list[str]):
    table = doc.add_table(rows=len(numbers), cols=2)
    for row_index, text in enumerate(numbers):
        formula_para = table.cell(row_index, 0).paragraphs[0]
        _append_math_formula(formula_para, [("x", "Arial", "20")])
        number_para = table.cell(row_index, 1).paragraphs[0]
        number_run = number_para.add_run(text)
        _seed_word_run_rpr(number_run, font_name="Arial", half_points="18")
    return table


def _append_math_formula(paragraph, fragments: list[tuple[str, str, str]]) -> None:
    math_para = etree.SubElement(paragraph._element, qn("m:oMathPara"))
    math = etree.SubElement(math_para, qn("m:oMath"))

    for text, font_name, half_points in fragments:
        math_run = etree.SubElement(math, qn("m:r"))
        math_r_pr = etree.SubElement(math_run, qn("m:rPr"))
        etree.SubElement(math_r_pr, qn("m:nor"))
        style = etree.SubElement(math_r_pr, qn("m:sty"))
        style.set(qn("m:val"), "p")

        word_r_pr = etree.SubElement(math_run, qn("w:rPr"))
        r_fonts = etree.SubElement(word_r_pr, qn("w:rFonts"))
        r_fonts.set(qn("w:ascii"), font_name)
        r_fonts.set(qn("w:hAnsi"), font_name)
        r_fonts.set(qn("w:cs"), font_name)
        sz = etree.SubElement(word_r_pr, qn("w:sz"))
        sz.set(qn("w:val"), half_points)
        sz_cs = etree.SubElement(word_r_pr, qn("w:szCs"))
        sz_cs.set(qn("w:val"), half_points)

        text_node = etree.SubElement(math_run, qn("m:t"))
        text_node.text = text


def _seed_word_run_rpr(run, *, font_name: str, half_points: str) -> None:
    r_pr = run._element.find(qn("w:rPr"))
    if r_pr is None:
        r_pr = etree.Element(qn("w:rPr"))
        run._element.insert(0, r_pr)

    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = etree.SubElement(r_pr, qn("w:rFonts"))
    r_fonts.set(qn("w:ascii"), font_name)
    r_fonts.set(qn("w:hAnsi"), font_name)
    r_fonts.set(qn("w:cs"), font_name)

    sz = r_pr.find(qn("w:sz"))
    if sz is None:
        sz = etree.SubElement(r_pr, qn("w:sz"))
    sz.set(qn("w:val"), half_points)

    sz_cs = r_pr.find(qn("w:szCs"))
    if sz_cs is None:
        sz_cs = etree.SubElement(r_pr, qn("w:szCs"))
    sz_cs.set(qn("w:val"), half_points)


def _seed_spacing(paragraph, *, before_pt: float, after_pt: float, line_spacing: float) -> None:
    apply_line_spacing(paragraph.paragraph_format, "multiple", line_spacing)
    paragraph.paragraph_format.space_before = Pt(before_pt)
    paragraph.paragraph_format.space_after = Pt(after_pt)
    sync_spacing_ooxml(
        paragraph._element,
        space_before_pt=before_pt,
        space_after_pt=after_pt,
        line_spacing_type="multiple",
        line_spacing_value=line_spacing,
    )


def _spacing(paragraph):
    spacing = paragraph._element.find(qn("w:pPr")).find(qn("w:spacing"))
    assert spacing is not None
    return spacing


def _first_math_word_rpr(paragraph):
    math_run = paragraph._element.find(f".//{qn('m:r')}")
    assert math_run is not None
    word_r_pr = math_run.find(qn("w:rPr"))
    assert word_r_pr is not None
    return word_r_pr


def _word_rpr(run):
    r_pr = run._element.find(qn("w:rPr"))
    assert r_pr is not None
    return r_pr
