"""
Phase 3 冒烟测试 — 📊 表格与题注模块 (3 个)
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docx import Document
from docx.shared import Pt


def test_caption_module():
    """M08: caption 完整管线测试"""
    from src.modules.table.caption import CaptionModule, _scan_captions
    from src.modules.structure.heading_recognition import HeadingRecognitionModule
    from src.config.template import TemplateConfig
    from src.config.scene import SceneWorkspace
    from src.config.resolver import resolve_config
    from src.pipeline.runner import Pipeline

    doc = Document()
    doc.add_heading("第一章 绪论", level=1)
    doc.add_paragraph("正文内容。")
    doc.add_paragraph("图 1 实验装置图")
    doc.add_paragraph("正文内容。")
    doc.add_paragraph("表 1 实验数据")
    doc.add_heading("第二章 方法", level=1)
    doc.add_paragraph("图 2 流程图")
    doc.add_paragraph("表 2 结果统计")

    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp.close()
    doc.save(tmp.name)

    try:
        config = resolve_config(TemplateConfig(), SceneWorkspace())
        pipeline = Pipeline(
            modules=[HeadingRecognitionModule(), CaptionModule()],
            config=config,
        )
        result = pipeline.execute(tmp.name)

        assert result.success, f"执行失败: {result.error}"
        assert result.context.caption_counters is not None
        print(f"  ✅ M08 caption 通过 (counters={result.context.caption_counters})")
    finally:
        Path(tmp.name).unlink(missing_ok=True)
        out = result.output_paths.get("final", "")
        if out:
            Path(out).unlink(missing_ok=True)


def test_caption_scan_logic():
    """M08: 题注扫描逻辑测试"""
    from src.modules.table.caption import _scan_captions

    doc = Document()
    doc.add_paragraph("图 1.1 实验装置")
    doc.add_paragraph("正文段落")
    doc.add_paragraph("表 2.3 结果统计表")
    doc.add_paragraph("Figure 5 Overview")
    doc.add_paragraph("Table 3 Results")

    captions = _scan_captions(doc)
    assert len(captions) == 4
    assert captions[0].kind == "figure"
    assert captions[0].prefix == "图"
    assert captions[1].kind == "table"
    assert captions[2].kind == "figure"
    assert captions[3].kind == "table"
    print("  ✅ M08 题注扫描逻辑通过")


def test_caption_without_heading_recognition():
    """M08: 关闭 heading_recognition 时，caption 仍可回退到全局编号。"""
    from src.modules.table.caption import CaptionModule
    from src.config.template import TemplateConfig
    from src.config.scene import SceneWorkspace
    from src.config.resolver import resolve_config
    from src.pipeline.runner import Pipeline

    doc = Document()
    doc.add_paragraph("图 7 实验装置")
    doc.add_paragraph("正文段落")
    doc.add_paragraph("表 9 实验结果")

    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp.close()
    doc.save(tmp.name)

    try:
        scene = SceneWorkspace()
        scene.module_switches["heading_recognition"] = False
        config = resolve_config(TemplateConfig(), scene)

        pipeline = Pipeline(modules=[CaptionModule()], config=config)
        result = pipeline.execute(tmp.name)

        assert result.success, f"执行失败: {result.error}"
        assert result.doc.paragraphs[0].text.startswith("图 1 ")
        assert result.doc.paragraphs[2].text.startswith("表 1 ")
        print("  ✅ M08 caption 可在无 heading_map 时回退到全局编号")
    finally:
        Path(tmp.name).unlink(missing_ok=True)
        out = result.output_paths.get("final", "")
        if out:
            Path(out).unlink(missing_ok=True)


def test_table_format_import():
    """M09: table_format 导入"""
    from src.modules.table.table_format import TableFormatModule

    mod = TableFormatModule()
    assert mod.meta.name == "table_format"
    assert mod.meta.category == "table"
    print("  ✅ M09 table_format 导入正常")


def test_figure_table_center_import():
    """M10: figure_table_center 导入"""
    from src.modules.table.figure_table_center import FigureTableCenterModule

    mod = FigureTableCenterModule()
    assert mod.meta.name == "figure_table_center"
    assert "caption" in mod.meta.soft_after
    print("  ✅ M10 figure_table_center 导入正常")


def test_three_line_border_helper_uses_outer_outer_inner_semantics():
    """M09: helper 级三线表语义应为上=下粗，中间细。"""
    from src.shared.engine.table_builder import set_table_borders
    from src.shared.engine.ooxml_ops import qn

    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    set_table_borders(
        table,
        mode="three_line",
        width_pt=2.0,
        header_width_pt=1.0,
        bottom_width_pt=0.5,
    )

    tbl_borders = table._element.find(qn("w:tblPr")).find(qn("w:tblBorders"))
    top = tbl_borders.find(qn("w:top"))
    bottom = tbl_borders.find(qn("w:bottom"))
    inside_h = tbl_borders.find(qn("w:insideH"))
    inside_v = tbl_borders.find(qn("w:insideV"))
    header_cell_bottom = (
        table.rows[0].cells[0]._element
        .find(qn("w:tcPr"))
        .find(qn("w:tcBorders"))
        .find(qn("w:bottom"))
    )

    assert top is not None and top.get(qn("w:sz")) == "8"
    assert bottom is not None and bottom.get(qn("w:sz")) == "8"
    assert inside_h is not None and inside_h.get(qn("w:val")) == "none"
    assert inside_v is not None and inside_v.get(qn("w:val")) == "none"
    assert header_cell_bottom is not None and header_cell_bottom.get(qn("w:sz")) == "4"
    print("  ✅ M09 helper 级三线表语义正确")


def test_table_format_uses_outer_outer_inner_config_semantics():
    """M09: table_format 模块应复用 0.2.1 语义：outer 来自 three_line_header，inner 来自 three_line_bottom。"""
    from src.modules.table.table_format import _apply_three_line_borders
    from src.shared.engine.ooxml_ops import qn
    from src.config.template import TableConfig

    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    cfg = TableConfig(
        border_mode="three_line",
        border_width_pt=2.0,
        three_line_header_width_pt=1.0,
        three_line_bottom_width_pt=0.5,
    )

    _apply_three_line_borders(table._element, cfg)

    tbl_borders = table._element.find(qn("w:tblPr")).find(qn("w:tblBorders"))
    top = tbl_borders.find(qn("w:top"))
    bottom = tbl_borders.find(qn("w:bottom"))
    inside_h = tbl_borders.find(qn("w:insideH"))
    inside_v = tbl_borders.find(qn("w:insideV"))
    header_cell_bottom = (
        table.rows[0].cells[0]._element
        .find(qn("w:tcPr"))
        .find(qn("w:tcBorders"))
        .find(qn("w:bottom"))
    )

    assert top is not None and top.get(qn("w:sz")) == "8"
    assert bottom is not None and bottom.get(qn("w:sz")) == "8"
    assert inside_h is not None and inside_h.get(qn("w:val")) == "none"
    assert inside_v is not None and inside_v.get(qn("w:val")) == "none"
    assert header_cell_bottom is not None and header_cell_bottom.get(qn("w:sz")) == "4"
    print("  ✅ M09 table_format 三线表语义正确")


def test_all_table_meta():
    """验证 3 个模块 meta 完整性"""
    from src.modules.table.caption import CaptionModule
    from src.modules.table.table_format import TableFormatModule
    from src.modules.table.figure_table_center import FigureTableCenterModule

    modules = [CaptionModule(), TableFormatModule(), FigureTableCenterModule()]
    for mod in modules:
        assert mod.meta.name
        assert mod.meta.description
        assert mod.meta.category == "table"

    names = [m.meta.name for m in modules]
    assert len(names) == len(set(names))
    print(f"  ✅ 3 个模块 meta 验证通过: {names}")


if __name__ == "__main__":
    print("Phase 3 冒烟测试 — 📊 表格与题注")
    print("=" * 50)

    test_caption_module()
    test_caption_scan_logic()
    test_table_format_import()
    test_figure_table_center_import()
    test_all_table_meta()

    print("=" * 50)
    print("✅ 表格与题注 3 个模块全部通过！")
