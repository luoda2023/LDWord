"""
Phase 2 冒烟测试 — 验证 12 个引擎共享工具
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_units():
    from src.shared.engine.units import (
        cm_to_pt, pt_to_cm, cm_to_emu, emu_to_cm,
        pt_to_twip, twip_to_pt, cn_size_to_pt, pt_to_cn_size,
        chars_to_pt, pt_to_chars,
    )
    # 双向转换精度
    assert abs(pt_to_cm(cm_to_pt(3.8)) - 3.8) < 0.001
    assert abs(twip_to_pt(pt_to_twip(12.0)) - 12.0) < 0.001
    # 中文字号
    assert cn_size_to_pt("小四") == 12.0
    assert pt_to_cn_size(12.0) == "小四"
    # chars
    assert chars_to_pt(2.0, 12.0) == 24.0
    assert pt_to_chars(24.0, 12.0) == 2.0
    print("  ✅ units 通过")


def test_patterns():
    from src.shared.engine.patterns import (
        PLACEHOLDER_DBL_BRACE, CJK_CHAR, HEADING_NUMBERING,
        CN_HEADING_NUMBERING, CITATION_BRACKET, AMOUNT_PATTERN,
    )
    assert PLACEHOLDER_DBL_BRACE.findall("{{公司名}}") == ["公司名"]
    assert CJK_CHAR.search("Hello中文") is not None
    assert HEADING_NUMBERING.match("1.1 标题") is not None
    assert CN_HEADING_NUMBERING.match("第一章 绪论") is not None
    assert CITATION_BRACKET.findall("参见[1,2]和[3-5]") == ["1,2", "3-5"]
    assert AMOUNT_PATTERN.search("总价100万元") is not None
    print("  ✅ patterns 通过")


def test_numbering():
    from src.shared.engine.numbering import format_number
    assert format_number(1, "arabic") == "1"
    assert format_number(3, "arabic_pad2") == "03"
    assert format_number(1, "cn_lower") == "一"
    assert format_number(11, "cn_lower") == "十一"
    assert format_number(21, "cn_lower") == "二十一"
    assert format_number(1, "cn_upper") == "壹"
    assert format_number(4, "roman_upper") == "IV"
    assert format_number(9, "roman_lower") == "ix"
    assert format_number(1, "alpha_upper") == "A"
    assert format_number(27, "alpha_lower") == "aa"
    assert format_number(1, "circled") == "①"
    assert format_number(5, "circled_paren") == "⑸"
    print("  ✅ numbering 通过")


def test_file_ops():
    import tempfile
    from src.shared.engine.file_ops import (
        ensure_dir, normalize_path, read_text_safe,
        write_text_safe, scan_files, file_size_human,
    )
    tmp = Path(tempfile.mkdtemp())
    sub = tmp / "a" / "b"
    ensure_dir(sub)
    assert sub.is_dir()
    # write + read
    write_text_safe(sub / "test.txt", "hello")
    assert read_text_safe(sub / "test.txt") == "hello"
    # scan
    write_text_safe(sub / "img.png", "fake")
    files = scan_files(sub, extensions={".txt"})
    assert len(files) == 1
    # human size
    assert file_size_human(1024) == "1.0 KB"
    print("  ✅ file_ops 通过")


def test_ooxml_ops():
    from src.shared.engine.ooxml_ops import (
        qn, create_element, element_to_string, find_or_create,
        set_val, get_val,
    )
    from lxml import etree
    # qn
    assert qn("w:pPr").endswith("}pPr")
    # create + set/get val
    parent = create_element("w:pPr")
    set_val(parent, "w:jc", "center")
    assert get_val(parent, "w:jc") == "center"
    print("  ✅ ooxml_ops 通过")


def test_font_resolver():
    from src.shared.engine.font_resolver import resolve_font
    # 直接匹配（简化实现总是返回 True）
    assert resolve_font("宋体") == "宋体"
    assert resolve_font("Times New Roman") == "Times New Roman"
    print("  ✅ font_resolver 通过")


def test_field_builder():
    from src.shared.engine.field_builder import (
        build_seq_field, build_ref_field, build_toc_field,
        build_complex_field,
    )
    from lxml import etree
    # SEQ
    seq = build_seq_field("图")
    xml = etree.tostring(seq, encoding="unicode")
    assert "SEQ" in xml and "图" in xml
    # REF
    ref = build_ref_field("_Ref123")
    xml = etree.tostring(ref, encoding="unicode")
    assert "REF" in xml
    # TOC
    toc = build_toc_field(max_level=3)
    xml = etree.tostring(toc, encoding="unicode")
    assert "TOC" in xml
    # Complex field
    parts = build_complex_field(" SEQ 表 \\* ARABIC ")
    assert len(parts) == 5
    print("  ✅ field_builder 通过")


def test_run_ops():
    """基本导入测试（完整测试需要真实 docx 环境）"""
    from src.shared.engine import run_ops
    assert hasattr(run_ops, "merge_runs")
    assert hasattr(run_ops, "replace_run_text")
    assert hasattr(run_ops, "get_full_text")
    print("  ✅ run_ops 导入正常")


def test_paragraph_iter():
    from src.shared.engine import paragraph_iter
    assert hasattr(paragraph_iter, "iter_paragraphs")
    assert hasattr(paragraph_iter, "iter_by_style")
    assert hasattr(paragraph_iter, "iter_tables")
    print("  ✅ paragraph_iter 导入正常")


def test_table_builder():
    from src.shared.engine import table_builder
    assert hasattr(table_builder, "create_table")
    assert hasattr(table_builder, "set_table_borders")
    assert hasattr(table_builder, "merge_cells")
    print("  ✅ table_builder 导入正常")


def test_style_resolver():
    from src.shared.engine import style_resolver
    assert hasattr(style_resolver, "resolve_paragraph_style")
    assert hasattr(style_resolver, "is_heading_paragraph")
    assert hasattr(style_resolver, "get_heading_level")
    print("  ✅ style_resolver 导入正常")


def test_image_ops():
    from src.shared.engine import image_ops
    assert hasattr(image_ops, "resize_image")
    assert hasattr(image_ops, "add_text_watermark")
    assert hasattr(image_ops, "get_image_size")
    print("  ✅ image_ops 导入正常")


if __name__ == "__main__":
    print("Phase 2 冒烟测试")
    print("=" * 50)

    test_units()
    test_patterns()
    test_numbering()
    test_file_ops()
    test_ooxml_ops()
    test_font_resolver()
    test_field_builder()
    test_run_ops()
    test_paragraph_iter()
    test_table_builder()
    test_style_resolver()
    test_image_ops()

    print("=" * 50)
    print("✅ 全部 12 项测试通过，Phase 2 引擎共享工具验证完成！")
