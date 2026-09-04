"""
field_builder — Word 域代码构建

构建 SEQ / REF / TOC / PAGEREF 等 Word 域代码的 XML。
"""

from __future__ import annotations

from typing import Iterator

from lxml import etree

from src.shared.engine.ooxml_ops import qn, create_element


def build_seq_field(
    seq_name: str,
    *,
    bookmark_prefix: str = "",
    level: int = 0,
) -> etree._Element:
    """构建 SEQ 域代码 XML。

    生成: <w:fldSimple w:instr=" SEQ {seq_name} \\* ARABIC ">

    Args:
        seq_name: 序列标识符 (e.g. "图", "表", "公式")
        bookmark_prefix: 书签前缀
        level: 章节级别 (>0 时添加 \\s 开关)
    """
    instr = f" SEQ {seq_name} \\* ARABIC "
    if level > 0:
        instr += f"\\s {level} "

    fld = create_element("w:fldSimple")
    fld.set(qn("w:instr"), instr)

    # 占位文本 Run
    r = etree.SubElement(fld, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = "0"

    return fld


def build_ref_field(bookmark_name: str) -> etree._Element:
    """构建 REF 域代码 XML。

    生成: <w:fldSimple w:instr=" REF {bookmark_name} \\h ">
    """
    instr = f" REF {bookmark_name} \\h "
    fld = create_element("w:fldSimple")
    fld.set(qn("w:instr"), instr)

    r = etree.SubElement(fld, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = "?"

    return fld


def build_toc_field(
    *,
    max_level: int = 3,
    heading_styles: str = "",
) -> etree._Element:
    """构建 TOC 域代码。

    生成: <w:fldSimple w:instr=' TOC \\o "1-{max_level}" \\h \\z \\u '>
    """
    instr = build_toc_instruction(
        max_level=max_level,
        heading_styles=heading_styles,
    )

    fld = create_element("w:fldSimple")
    fld.set(qn("w:instr"), instr)

    r = etree.SubElement(fld, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = "目录将在更新域后显示"

    return fld


def build_toc_instruction(
    *,
    max_level: int = 3,
    heading_styles: str = "",
) -> str:
    """构建 TOC 域代码指令文本。"""
    instr = f' TOC \\o "1-{max_level}" \\h \\z \\u '
    if heading_styles:
        instr += f'\\t "{heading_styles}" '
    return instr


def build_pageref_field(bookmark_name: str) -> etree._Element:
    """构建 PAGEREF 域代码。"""
    instr = f" PAGEREF {bookmark_name} \\h "
    fld = create_element("w:fldSimple")
    fld.set(qn("w:instr"), instr)

    r = etree.SubElement(fld, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = "0"

    return fld


def build_complex_field(
    instr: str,
    *,
    result_text: str = "?",
    mark_dirty: bool = False,
) -> list[etree._Element]:
    """构建复杂域代码（BEGIN + INSTR + SEPARATE + RESULT + END）。

    用于需要分段构建的域代码，返回元素列表。
    """
    elements = []

    # BEGIN
    r_begin = etree.Element(qn("w:r"))
    fld_char_begin = etree.SubElement(r_begin, qn("w:fldChar"))
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    if mark_dirty:
        fld_char_begin.set(qn("w:dirty"), "true")
    elements.append(r_begin)

    # INSTR
    r_instr = etree.Element(qn("w:r"))
    instr_text = etree.SubElement(r_instr, qn("w:instrText"))
    instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr_text.text = instr
    elements.append(r_instr)

    # SEPARATE
    r_sep = etree.Element(qn("w:r"))
    fld_char_sep = etree.SubElement(r_sep, qn("w:fldChar"))
    fld_char_sep.set(qn("w:fldCharType"), "separate")
    elements.append(r_sep)

    # RESULT (placeholder)
    r_result = etree.Element(qn("w:r"))
    t_result = etree.SubElement(r_result, qn("w:t"))
    t_result.text = result_text
    elements.append(r_result)

    # END
    r_end = etree.Element(qn("w:r"))
    fld_char_end = etree.SubElement(r_end, qn("w:fldChar"))
    fld_char_end.set(qn("w:fldCharType"), "end")
    elements.append(r_end)

    return elements


def iter_field_instructions(
    root: etree._Element,
) -> Iterator[tuple[str, etree._Element, str]]:
    """遍历简单域/复杂域的指令文本。

    Yields:
        ("simple" | "complex", 域元素, 指令文本)
    """
    for fld_simple in root.iter(qn("w:fldSimple")):
        yield ("simple", fld_simple, fld_simple.get(qn("w:instr"), ""))

    yield from _iter_complex_field_instructions(root)


def _iter_complex_field_instructions(
    root: etree._Element,
) -> Iterator[tuple[str, etree._Element, str]]:
    """遍历复杂域（BEGIN/INSTR/SEPARATE/END）的指令文本。"""
    stack: list[dict[str, object]] = []

    for elem in root.iter():
        if elem.tag == qn("w:fldChar"):
            fld_type = elem.get(qn("w:fldCharType"))

            if fld_type == "begin":
                stack.append({
                    "begin": elem,
                    "instr_parts": [],
                    "yielded": False,
                })
                continue

            if fld_type == "separate" and stack:
                current = stack[-1]
                if not current["yielded"]:
                    yield (
                        "complex",
                        current["begin"],
                        "".join(current["instr_parts"]),
                    )
                    current["yielded"] = True
                continue

            if fld_type == "end" and stack:
                current = stack.pop()
                if not current["yielded"]:
                    yield (
                        "complex",
                        current["begin"],
                        "".join(current["instr_parts"]),
                    )
                continue

        if elem.tag == qn("w:instrText") and stack:
            stack[-1]["instr_parts"].append(elem.text or "")
