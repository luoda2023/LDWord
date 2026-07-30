"""
style_resolver — 段落有效样式解析

解析 Word 文档中段落的有效样式（直接格式 → 段落样式 → 默认样式继承链）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.shared.engine.ooxml_ops import qn

if TYPE_CHECKING:
    from docx.text.paragraph import Paragraph


@dataclass
class EffectiveStyle:
    """段落的有效样式。"""
    style_name: str | None = None           # Word 内置样式名
    font_cn: str | None = None
    font_en: str | None = None
    size_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    alignment: str | None = None
    outline_level: int | None = None        # 大纲级别 (0-8, None=正文)
    is_heading: bool = False


def resolve_paragraph_style(para: Paragraph) -> EffectiveStyle:
    """解析段落的有效样式。

    优先级: 直接格式 > 段落样式 > 默认样式
    """
    result = EffectiveStyle()

    # 段落样式
    style = para.style
    if style:
        result.style_name = style.name
        # 检查大纲级别
        pPr = para._element.find(qn("w:pPr"))
        if pPr is not None:
            outline_lvl = pPr.find(qn("w:outlineLvl"))
            if outline_lvl is not None:
                val = outline_lvl.get(qn("w:val"))
                if val is not None:
                    try:
                        result.outline_level = int(val)
                        result.is_heading = result.outline_level <= 8
                    except ValueError:
                        pass

        # 从样式中获取默认值
        if style.font:
            result.font_en = style.font.name
            result.size_pt = style.font.size.pt if style.font.size else None

    # 直接格式覆盖
    if para.runs:
        first_run = para.runs[0]
        font = first_run.font
        if font.name:
            result.font_en = font.name
        if font.size:
            result.size_pt = font.size.pt
        if font.bold is not None:
            result.bold = font.bold
        if font.italic is not None:
            result.italic = font.italic

    # 段落对齐
    if para.alignment is not None:
        result.alignment = str(para.alignment)

    # 是否为标题（通过样式名或大纲级别判断）
    if not result.is_heading and result.style_name:
        name_lower = result.style_name.lower()
        if name_lower.startswith("heading") or "标题" in result.style_name:
            result.is_heading = True

    return result


def is_heading_paragraph(para: Paragraph) -> bool:
    """快速判断段落是否为标题。"""
    style = para.style
    if style:
        name = style.name or ""
        if name.lower().startswith("heading") or "标题" in name:
            return True

    # 检查大纲级别
    pPr = para._element.find(qn("w:pPr"))
    if pPr is not None:
        outline_lvl = pPr.find(qn("w:outlineLvl"))
        if outline_lvl is not None:
            val = outline_lvl.get(qn("w:val"))
            if val is not None:
                try:
                    return int(val) <= 8
                except ValueError:
                    pass
    return False


def get_heading_level(para: Paragraph) -> int | None:
    """获取标题级别 (1-9), 非标题返回 None。"""
    style = para.style
    if style and style.name:
        name = style.name.lower()
        # "Heading 1" ~ "Heading 9"
        if name.startswith("heading "):
            try:
                return int(name.split()[-1])
            except ValueError:
                pass

    # 大纲级别
    pPr = para._element.find(qn("w:pPr"))
    if pPr is not None:
        outline_lvl = pPr.find(qn("w:outlineLvl"))
        if outline_lvl is not None:
            val = outline_lvl.get(qn("w:val"))
            if val is not None:
                try:
                    level = int(val) + 1  # outlineLvl 从 0 开始
                    return level if 1 <= level <= 9 else None
                except ValueError:
                    pass
    return None
