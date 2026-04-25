"""Phase 2 shared-engine smoke tests."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_units():
    from src.shared.engine.units import (
        chars_to_pt,
        cm_to_pt,
        pt_to_cm,
        pt_to_twip,
        pt_to_chars,
        twip_to_pt,
    )

    assert abs(pt_to_cm(cm_to_pt(3.8)) - 3.8) < 0.001
    assert abs(twip_to_pt(pt_to_twip(12.0)) - 12.0) < 0.001
    assert chars_to_pt(2.0, 12.0) == 24.0
    assert pt_to_chars(24.0, 12.0) == 2.0


def test_patterns():
    from src.shared.engine.patterns import (
        CJK_CHAR,
        CITATION_BRACKET,
        HEADING_NUMBERING,
        PLACEHOLDER_DBL_BRACE,
    )

    assert PLACEHOLDER_DBL_BRACE.findall("{{company_name}}") == ["company_name"]
    assert CJK_CHAR.search("\u4e2d") is not None
    assert HEADING_NUMBERING.match("1.1 Title") is not None
    assert CITATION_BRACKET.findall("See [1,2] and [3]") == ["1,2", "3"]


def test_numbering():
    from src.shared.engine.numbering import format_number

    assert format_number(1, "arabic") == "1"
    assert format_number(3, "arabic_pad2") == "03"
    assert format_number(4, "roman_upper") == "IV"
    assert format_number(9, "roman_lower") == "ix"
    assert format_number(1, "alpha_upper") == "A"
    assert format_number(27, "alpha_lower") == "aa"


def test_file_ops():
    import tempfile

    from src.shared.engine.file_ops import (
        ensure_dir,
        file_size_human,
        read_text_safe,
        scan_files,
        write_text_safe,
    )

    tmp = Path(tempfile.mkdtemp())
    sub = tmp / "a" / "b"
    ensure_dir(sub)
    assert sub.is_dir()

    write_text_safe(sub / "test.txt", "hello")
    assert read_text_safe(sub / "test.txt") == "hello"

    write_text_safe(sub / "img.png", "fake")
    files = scan_files(sub, extensions={".txt"})
    assert len(files) == 1
    assert file_size_human(1024) == "1.0 KB"


def test_ooxml_ops():
    from src.shared.engine.ooxml_ops import create_element, get_val, qn, set_val

    assert qn("w:pPr").endswith("}pPr")
    parent = create_element("w:pPr")
    set_val(parent, "w:jc", "center")
    assert get_val(parent, "w:jc") == "center"


def test_font_resolver(monkeypatch):
    import src.shared.engine.font_resolver as font_resolver

    monkeypatch.setattr(font_resolver, "qt_font_families", lambda: ())
    monkeypatch.setattr(font_resolver, "list_system_fonts", lambda: {"SimSun", "Times New Roman"})

    # CN aliases should resolve to the actual available family when only the
    # system English family is present.
    assert font_resolver.resolve_font("\u5b8b\u4f53", lang="cn") == "SimSun"
    assert font_resolver.resolve_font("Times New Roman", lang="en") == "Times New Roman"


def test_field_builder():
    from lxml import etree

    from src.shared.engine.field_builder import (
        build_complex_field,
        build_ref_field,
        build_seq_field,
        build_toc_field,
    )

    seq = build_seq_field("Figure")
    xml = etree.tostring(seq, encoding="unicode")
    assert "SEQ" in xml and "Figure" in xml

    ref = build_ref_field("_Ref123")
    xml = etree.tostring(ref, encoding="unicode")
    assert "REF" in xml

    toc = build_toc_field(max_level=3)
    xml = etree.tostring(toc, encoding="unicode")
    assert "TOC" in xml

    parts = build_complex_field(" SEQ Table \\* ARABIC ")
    assert len(parts) == 5


def test_run_ops():
    from src.shared.engine import run_ops

    assert hasattr(run_ops, "merge_runs")
    assert hasattr(run_ops, "replace_run_text")
    assert hasattr(run_ops, "get_full_text")


def test_paragraph_iter():
    from src.shared.engine import paragraph_iter

    assert hasattr(paragraph_iter, "iter_paragraphs")
    assert hasattr(paragraph_iter, "iter_by_style")
    assert hasattr(paragraph_iter, "iter_tables")


def test_table_builder():
    from src.shared.engine import table_builder

    assert hasattr(table_builder, "create_table")
    assert hasattr(table_builder, "set_table_borders")
    assert hasattr(table_builder, "merge_cells")


def test_style_resolver():
    from src.shared.engine import style_resolver

    assert hasattr(style_resolver, "resolve_paragraph_style")
    assert hasattr(style_resolver, "is_heading_paragraph")
    assert hasattr(style_resolver, "get_heading_level")


def test_image_ops():
    from src.shared.engine import image_ops

    assert hasattr(image_ops, "resize_image")
    assert hasattr(image_ops, "add_text_watermark")
    assert hasattr(image_ops, "get_image_size")
