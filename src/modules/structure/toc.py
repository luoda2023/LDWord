"""
toc — 目录生成模块

在指定位置插入或更新 TOC（Table of Contents）域代码。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn
from src.shared.engine.field_builder import (
    build_complex_field,
    build_toc_instruction,
    iter_field_instructions,
)
from src.shared.engine.field_refresh import (
    document_has_toc,
    ensure_update_fields_on_open,
)

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class TocModule(BaseModule):
    """目录生成模块。

    职责：
    - 在文档指定位置插入 TOC 域代码
    - 更新已有 TOC 域
    - 移除旧的手动目录
    """

    meta = ModuleMeta(
        name="toc",
        description="目录生成",
        category="structure",
        requires_config=("toc",),
        depends_on=("heading_numbering",),
        consumes=("heading_map",),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        toc_cfg = config.toc

        if not toc_cfg.enabled:
            return

        max_level = toc_cfg.max_level
        insert_position = toc_cfg.insert_position

        # 检查是否已有 TOC
        has_existing_toc = _has_existing_toc(doc)

        if has_existing_toc:
            # 更新 TOC 标记（Word 打开时会自动更新域）
            _mark_toc_for_update(doc)
            ensure_update_fields_on_open(doc)
            tracker.record(
                rule_name=self.meta.name,
                target="已有目录",
                section="global",
                change_type="format",
                before="目录未更新",
                after="已标记更新",
            )
        else:
            # 插入新 TOC
            insert_idx = _find_insert_position(doc, insert_position, context)
            if insert_idx is not None:
                _insert_toc(doc, insert_idx, max_level)
                ensure_update_fields_on_open(doc)
                tracker.record(
                    rule_name=self.meta.name,
                    target=f"段落 {insert_idx}",
                    section="global",
                    change_type="insert",
                    before="无目录",
                    after=f"已插入 TOC (1-{max_level} 级)",
                )


def _has_existing_toc(doc: Document) -> bool:
    """检查文档是否已有 TOC 域代码。"""
    return document_has_toc(doc)


def _mark_toc_for_update(doc: Document) -> None:
    """标记目录域需要更新（设置 dirty flag）。"""
    body = doc.element.body
    for _kind, elem, instr in iter_field_instructions(body):
        if _is_toc_instruction(instr):
            elem.set(qn("w:dirty"), "true")


def _find_insert_position(
    doc: Document,
    mode: str,
    context: PipelineContext,
) -> int | None:
    """确定 TOC 插入位置。

    mode:
    - "auto": 在第一个 heading 之前插入
    - "after_cover": 在封面后插入
    - 数字字符串: 指定段落索引
    """
    if mode == "auto":
        # 在第一个标题前插入
        heading_map = context.heading_map
        if heading_map:
            first_heading_idx = min(heading_map.keys())
            return max(0, first_heading_idx)
        return 0

    if mode == "after_cover":
        # 简化：在第 2 段后插入
        return min(2, len(doc.paragraphs))

    # 数字索引
    try:
        return int(mode)
    except ValueError:
        return 0


def _insert_toc(doc: Document, position: int, max_level: int) -> None:
    """在指定位置插入 TOC 段落。"""
    body = doc.element.body
    paragraphs = body.findall(qn("w:p"))

    # 创建 TOC 段落
    toc_para = etree.Element(qn("w:p"))

    # 段落属性：居中
    pPr = etree.SubElement(toc_para, qn("w:pPr"))
    jc = etree.SubElement(pPr, qn("w:jc"))
    jc.set(qn("w:val"), "left")

    # "目录"标题 Run
    r_title = etree.SubElement(toc_para, qn("w:r"))
    rPr = etree.SubElement(r_title, qn("w:rPr"))
    b = etree.SubElement(rPr, qn("w:b"))
    sz = etree.SubElement(rPr, qn("w:sz"))
    sz.set(qn("w:val"), "32")  # 16 pt
    t = etree.SubElement(r_title, qn("w:t"))
    t.text = "目 录"

    # TOC 域代码段落
    toc_field_para = etree.Element(qn("w:p"))
    instr = build_toc_instruction(max_level=max_level)
    for elem in build_complex_field(
        instr,
        result_text="请更新域以显示目录",
        mark_dirty=True,
    ):
        toc_field_para.append(elem)

    # 插入到 body
    if position < len(paragraphs):
        ref = paragraphs[position]
        ref.addprevious(toc_para)
        ref.addprevious(toc_field_para)
    else:
        body.append(toc_para)
        body.append(toc_field_para)


def _is_toc_instruction(instr: str) -> bool:
    """判断域代码指令是否为 TOC。"""
    normalized = " ".join((instr or "").upper().split())
    return normalized.startswith("TOC ")
