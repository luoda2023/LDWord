"""Generate the synthetic public DOCX fixture tracked by the source release."""

from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "tests" / "TEST-1" / "中图分类号.docx"
BLUE = RGBColor(0x2E, 0x74, 0xB5)
DEEP_BLUE = RGBColor(0x1F, 0x4D, 0x78)
MUTED = RGBColor(0x63, 0x70, 0x83)
TABLE_FILL = "F4F6F9"
CONTENT_WIDTH_DXA = 9360


def _set_font(run, *, size: float, bold: bool = False, color=None) -> None:
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:ascii"), "Calibri")
    fonts.set(qn("w:hAnsi"), "Calibri")
    fonts.set(qn("w:eastAsia"), "Microsoft YaHei")


def _configure_styles(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.333
    for style_name, size, color, before, after in (
        ("Heading 1", 16, BLUE, 18, 10),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DEEP_BLUE, 8, 4),
    ):
        style = document.styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)


def _configure_section(section) -> None:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)


def _set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def _configure_table_geometry(table, widths: tuple[int, ...]) -> None:
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(width))
        grid.append(column)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            _set_cell_width(cell, widths[index])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            tc_pr = cell._tc.get_or_add_tcPr()
            margins = tc_pr.find(qn("w:tcMar"))
            if margins is None:
                margins = OxmlElement("w:tcMar")
                tc_pr.append(margins)
            for side, value in (
                ("top", 80),
                ("bottom", 80),
                ("start", 120),
                ("end", 120),
            ):
                element = margins.find(qn(f"w:{side}"))
                if element is None:
                    element = OxmlElement(f"w:{side}")
                    margins.append(element)
                element.set(qn("w:w"), str(value))
                element.set(qn("w:type"), "dxa")


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def _add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("第 ")
    _set_font(run, size=9, color=MUTED)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)
    suffix = paragraph.add_run(" 页")
    _set_font(suffix, size=9, color=MUTED)


def _add_running_furniture(section) -> None:
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.paragraph_format.space_after = Pt(0)
    run = header.add_run("合成学位论文版式测试样本")
    _set_font(run, size=9, color=MUTED)
    _add_page_number(section.footer.paragraphs[0])


def _add_cover(document: Document) -> None:
    for _ in range(4):
        document.add_paragraph()
    kicker = document.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kicker.paragraph_format.space_after = Pt(18)
    _set_font(
        kicker.add_run("公开测试夹具 · 全部内容为合成数据"),
        size=10.5,
        bold=True,
        color=BLUE,
    )
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(8)
    _set_font(
        title.add_run("合成学位论文版式测试样本"), size=28, bold=True, color=DEEP_BLUE
    )
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(32)
    _set_font(
        subtitle.add_run("Synthetic Thesis Layout Fixture for Formatting Regression"),
        size=14,
        color=MUTED,
    )
    metadata = document.add_table(rows=5, cols=2)
    metadata.style = "Table Grid"
    values = (
        ("中图分类号", "TP000（合成编号）"),
        ("公开级别", "公开测试数据"),
        ("作者", "示例作者"),
        ("单位", "示例大学文档工程学院"),
        ("日期", "2026 年 7 月"),
    )
    for row, (label, value) in zip(metadata.rows, values):
        row.cells[0].text = label
        row.cells[1].text = value
        _shade_cell(row.cells[0], TABLE_FILL)
        for index, cell in enumerate(row.cells):
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    _set_font(run, size=10.5, bold=index == 0)
    _configure_table_geometry(metadata, (2700, 6660))
    note = document.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.space_before = Pt(28)
    _set_font(
        note.add_run("本文件不含真实人员、机构、联系方式或研究成果。"),
        size=9.5,
        color=MUTED,
    )


def _add_body(document: Document) -> None:
    document.add_page_break()
    document.add_heading("摘要", level=1)
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.add_run(
        "本文档用于验证 DOCX 解析、标题识别、字体替换、表格宽度、分页和输出回执。"
        "所有名称、编号与论述均为专门生成的合成内容，不对应任何真实论文或个人。"
        "测试重点是文档结构和格式行为，而不是学术结论。"
    )
    keywords = document.add_paragraph()
    _set_font(keywords.add_run("关键词："), size=11, bold=True)
    _set_font(keywords.add_run("文档工程；格式回归；合成夹具；隐私安全"), size=11)

    document.add_heading("第一章 研究背景", level=1)
    document.add_heading("1.1 测试目标", level=2)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run(
        "发布级文档测试需要稳定、可重复且可公开的输入。合成夹具能够覆盖中文标题、"
        "英文副标题、多级标题和段落换行，同时避免把真实业务资料带入源码仓库。"
    )
    document.add_heading("1.2 结构范围", level=2)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run(
        "本样本包含封面元数据、摘要、关键词、多级标题、数据表和结论页。"
        "每个元素都采用确定的样式和页面几何，以便不同环境比较输出。"
    )

    document.add_heading("第二章 合成结果", level=1)
    document.add_heading("2.1 格式度量", level=2)
    table = document.add_table(rows=4, cols=3)
    table.style = "Table Grid"
    rows = (
        ("检查项", "合成值", "预期状态"),
        ("标题层级", "3 级", "可识别"),
        ("页面边距", "1 英寸", "一致"),
        ("表格宽度", "9360 DXA", "固定"),
    )
    for row_index, (row, values) in enumerate(zip(table.rows, rows)):
        for cell, value in zip(row.cells, values):
            cell.text = value
            if row_index == 0:
                _shade_cell(cell, TABLE_FILL)
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    _set_font(run, size=10, bold=row_index == 0)
    _configure_table_geometry(table, (3120, 3120, 3120))

    document.add_heading("2.2 解释", level=2)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run(
        "若处理流程保持标题、正文、表格和分页的语义一致，则该次回归可以判定为通过。"
        "任何真实姓名、联系方式、本机路径或外部文档内容都不应出现在测试产物中。"
    )

    document.add_page_break()
    document.add_heading("第三章 结论", level=1)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run(
        "本合成文件为公开源码提供最小但具有代表性的论文类 DOCX 输入。"
        "它可用于格式化、风险扫描和发布路径验证，并可由生成脚本重复创建。"
    )
    document.add_heading("数据声明", level=2)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run("全文均为合成测试数据。示例作者、示例大学和全部编号不指向现实主体。")


def build_fixture(output: Path) -> Path:
    document = Document()
    _configure_styles(document)
    for section in document.sections:
        _configure_section(section)
        _add_running_furniture(section)
    document.core_properties.title = "合成学位论文版式测试样本"
    document.core_properties.subject = "公开 DOCX 格式回归夹具"
    document.core_properties.author = "Alavette Form"
    document.core_properties.last_modified_by = "Alavette Form"
    document.core_properties.comments = "Synthetic public test fixture."
    _add_cover(document)
    _add_body(document)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(build_fixture(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
