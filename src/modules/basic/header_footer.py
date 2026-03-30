"""
header_footer — 页眉页脚模块

设置页眉内容（STYLEREF 跟随章节标题）、页码格式（阿拉伯/罗马）、
页眉横线、页眉页脚字体样式。
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn, find_or_create
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.run_ops import set_run_east_asian_font
from src.shared.engine.field_builder import build_complex_field, iter_field_instructions

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class HeaderFooterModule(BaseModule):
    """页眉页脚模块。

    职责：
    - 页眉：STYLEREF 域自动跟随章节标题 / 固定文本
    - 页眉横线：开启/关闭
    - 页码：阿拉伯/罗马、起始页码
    - 页眉页脚字体样式统一
    - 封面不显示页眉页脚
    """

    meta = ModuleMeta(
        name="header_footer",
        description="页眉页脚",
        category="basic",
        requires_config=("header_footer",),
        soft_after=("heading_recognition",),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        hf_cfg = config.header_footer
        count = 0

        header_mode = hf_cfg.header_mode
        header_border = hf_cfg.header_border
        page_number_enabled = hf_cfg.page_number_enabled

        for idx, section in enumerate(doc.sections):
            # 1. 页眉内容
            if header_mode == "styleref":
                _set_styleref_header(section, hf_cfg)
                count += 1
            elif header_mode == "fixed":
                _set_fixed_header(section, hf_cfg)
                count += 1
            elif header_mode not in ("none",):
                # 非法值回退到 styleref；正常情况下 migration 已保证只剩 canonical 值
                _set_styleref_header(section, hf_cfg)
                count += 1

            # 2. 页眉横线
            _set_header_border(section, header_border)

            # 3. 页眉字体
            _format_header_footer_font(section, hf_cfg)

            # 4. 页脚页码
            if page_number_enabled:
                _set_page_number(section, hf_cfg)
                count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{len(list(doc.sections))} 个节",
                section="global",
                change_type="format",
                before="(mixed)",
                after=(
                    f"header={header_mode or 'styleref'}, "
                    f"border={header_border}, "
                    f"page_num={page_number_enabled}"
                ),
            )


# ── STYLEREF 页眉 ────────────────────────────────

def _set_styleref_header(section, hf_cfg) -> None:
    """设置 STYLEREF 域代码页眉（自动跟随章节标题）。"""
    header = section.header
    header.is_linked_to_previous = False

    # 清空现有内容
    for para in header.paragraphs:
        for run in list(para.runs):
            run._element.getparent().remove(run._element)

    if header.paragraphs:
        para = header.paragraphs[0]
    else:
        para = header.add_paragraph()

    # 添加 STYLEREF 域
    level = hf_cfg.styleref_level
    _add_field_to_paragraph(
        para,
        f' STYLEREF "Heading {level}" \\n ',
    )


def _set_fixed_header(section, hf_cfg) -> None:
    """设置固定文本页眉。"""
    header = section.header
    header.is_linked_to_previous = False

    for para in header.paragraphs:
        for run in list(para.runs):
            run._element.getparent().remove(run._element)

    if header.paragraphs:
        para = header.paragraphs[0]
    else:
        para = header.add_paragraph()

    text = hf_cfg.header_text
    if text:
        para.add_run(text)


# ── 页眉横线 ─────────────────────────────────────

def _set_header_border(section, enable: bool) -> None:
    """设置或移除页眉段落底部横线。"""
    header = section.header
    if not header.paragraphs:
        return

    para = header.paragraphs[0]
    pPr = find_or_create(para._element, "w:pPr")
    pBdr = find_or_create(pPr, "w:pBdr")
    bottom = find_or_create(pBdr, "w:bottom")

    if enable:
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "auto")
    else:
        bottom.set(qn("w:val"), "none")
        bottom.set(qn("w:sz"), "0")


# ── 页码 ─────────────────────────────────────────

def _set_page_number(section, hf_cfg) -> None:
    """在页脚中设置页码域代码。"""
    footer = section.footer
    footer.is_linked_to_previous = False

    # 检查是否已有 PAGE 域
    for para in footer.paragraphs:
        if _paragraph_has_field(para, "PAGE"):
            return  # 已有页码，不重复添加

    if footer.paragraphs:
        para = footer.paragraphs[0]
    else:
        para = footer.add_paragraph()

    # 居中对齐
    pPr = find_or_create(para._element, "w:pPr")
    jc = find_or_create(pPr, "w:jc")
    jc.set(qn("w:val"), "center")

    _add_field_to_paragraph(para, " PAGE ")


# ── 字体格式 ─────────────────────────────────────

def _format_header_footer_font(section, hf_cfg) -> None:
    """统一页眉页脚的字体样式。"""
    font_cn = hf_cfg.font_cn
    font_en = hf_cfg.font_en
    size_pt = hf_cfg.size_pt

    if not any((font_cn, font_en, size_pt)):
        return

    from docx.shared import Pt

    for part in (section.header, section.footer):
        for para in part.paragraphs:
            for run in para.runs:
                if font_en:
                    run.font.name = resolve_font(font_en, lang="en")
                if font_cn:
                    set_run_east_asian_font(run, font_cn)
                if size_pt:
                    run.font.size = Pt(size_pt)


# ── 域代码插入工具 ───────────────────────────────

def _add_field_to_paragraph(para, instr: str) -> None:
    """向段落添加复杂域代码。"""
    for elem in build_complex_field(instr, result_text=" "):
        para._element.append(elem)


def _paragraph_has_field(para, field_keyword: str) -> bool:
    """判断段落是否已包含指定域代码。"""
    keyword = field_keyword.strip().upper()
    for _kind, _elem, instr in iter_field_instructions(para._element):
        normalized = " ".join((instr or "").upper().split())
        if normalized.startswith(keyword):
            return True
    return False
