"""
run_ops — Run 级别原子操作

对 python-docx 的 Run 对象执行合并、拆分、替换等操作。
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run

from lxml import etree


def merge_runs(paragraph: Paragraph) -> None:
    """合并段落中格式完全相同的相邻 Run。"""
    runs = paragraph.runs
    if len(runs) <= 1:
        return

    i = 0
    while i < len(runs) - 1:
        r1 = runs[i]
        r2 = runs[i + 1]
        if _runs_same_format(r1, r2):
            r1.text = (r1.text or "") + (r2.text or "")
            r2._element.getparent().remove(r2._element)
            runs = paragraph.runs  # refresh
        else:
            i += 1


def split_run_at(run: Run, offset: int) -> Run | None:
    """在指定偏移处拆分 Run, 返回新 Run (后半部分)。"""
    text = run.text or ""
    if offset <= 0 or offset >= len(text):
        return None

    new_elem = deepcopy(run._element)
    run.text = text[:offset]
    new_elem.text = text[offset:]
    run._element.addnext(new_elem)

    from docx.text.run import Run as RunClass
    return RunClass(new_elem, run._element.getparent())


def replace_run_text(
    paragraph: Paragraph,
    old: str,
    new: str,
    *,
    max_replacements: int = -1,
) -> int:
    """在段落中替换跨 Run 的文本。

    先合并 Run, 再查找替换, 返回替换次数。
    """
    merge_runs(paragraph)
    count = 0
    for run in paragraph.runs:
        text = run.text or ""
        if old not in text:
            continue
        if max_replacements > 0:
            run.text = text.replace(old, new, max_replacements - count)
            count += text.count(old)
            if count >= max_replacements:
                break
        else:
            n = text.count(old)
            run.text = text.replace(old, new)
            count += n
    return count


def clear_paragraph_runs(paragraph: Paragraph) -> None:
    """清空段落的所有 Run (保留段落属性)。"""
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)


def get_full_text(paragraph: Paragraph) -> str:
    """获取段落完整文本（合并所有 Run）。"""
    return "".join(r.text or "" for r in paragraph.runs)


def copy_run_format(source: Run, target: Run) -> None:
    """复制 Run 的格式（字体、大小、粗体等）到目标 Run。"""
    rPr = source._element.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr"
    )
    if rPr is not None:
        new_rPr = deepcopy(rPr)
        old_rPr = target._element.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr"
        )
        if old_rPr is not None:
            target._element.remove(old_rPr)
        target._element.insert(0, new_rPr)


# ── 内部工具 ─────────────────────────────────────

def _runs_same_format(r1: Run, r2: Run) -> bool:
    """比较两个 Run 的格式属性是否完全一致。"""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    rPr1 = r1._element.find(f"{ns}rPr")
    rPr2 = r2._element.find(f"{ns}rPr")

    if rPr1 is None and rPr2 is None:
        return True
    if rPr1 is None or rPr2 is None:
        return False

    return etree.tostring(rPr1) == etree.tostring(rPr2)


# ── 字体操作 ─────────────────────────────────────

def set_run_east_asian_font(run: Run, font_name: str) -> None:
    """设置 Run 的东亚字体（中文字体）。

    Args:
        run: python-docx Run 对象
        font_name: 字体名（会通过 resolve_font 解析）
    """
    from src.shared.engine.ooxml_ops import qn, find_or_create
    from src.shared.engine.font_resolver import resolve_font

    resolved = resolve_font(font_name, lang="cn")
    rPr = find_or_create(run._element, "w:rPr")
    rFonts = find_or_create(rPr, "w:rFonts")
    rFonts.set(qn("w:eastAsia"), resolved)


def set_run_fonts(
    run: Run,
    *,
    font_cn: str | None = None,
    font_en: str | None = None,
    size_pt: float | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> None:
    """统一设置 Run 的字体属性。

    Args:
        run: python-docx Run 对象
        font_cn: 中文字体名（可选）
        font_en: 英文字体名（可选）
        size_pt: 字号磅值（可选）
        bold: 加粗（可选）
        italic: 斜体（可选）
    """
    from docx.shared import Pt
    from src.shared.engine.font_resolver import resolve_font

    if font_en:
        run.font.name = resolve_font(font_en, lang="en")
    if font_cn:
        set_run_east_asian_font(run, font_cn)
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
