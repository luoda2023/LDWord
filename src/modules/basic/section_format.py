"""
section_format — 分节管理模块

管理文档分节属性：分节类型、分页符清理、分栏设置。
不处理段落格式（→ paragraph_style）、页面尺寸（→ page_setup）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.base import BaseModule, Issue, ModuleMeta
from src.shared.engine.ooxml_ops import clone_element, qn, find, find_or_create
from src.shared.engine.page_number_planner import (
    build_page_number_execution_plan,
    collect_page_number_diagnostics,
    format_page_number_diagnostic_text,
)

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


class SectionFormatModule(BaseModule):
    """分节管理模块。

    职责：
    - 统一分节类型（continuous / nextPage / evenPage / oddPage）
    - 清理多余的空白分节
    - 设置分栏属性
    - 清理题注与表格之间的多余分节符
    """

    meta = ModuleMeta(
        name="section_format",
        description="分节管理",
        category="basic",
        requires_config=("section",),
        soft_after=("heading_recognition",),
        soft_consumes=("doc_tree", "heading_map"),
        modifies_structure=True,
    )

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        issues: list[Issue] = []
        section_type = getattr(getattr(config, "section", None), "section_break_type", None)
        if section_type not in (None, "") and str(section_type) not in {"nextPage", "continuous", "evenPage", "oddPage"}:
            issues.append(
                Issue(
                    level="error",
                    module_name=self.meta.name,
                    message=f"unsupported section_break_type: {section_type}",
                    location="section.section_break_type",
                )
            )

        header_footer = getattr(config, "header_footer", None)
        if header_footer is not None:
            issues.extend(
                Issue(
                    level=item.level,
                    module_name=self.meta.name,
                    message=format_page_number_diagnostic_text(item),
                    location=item.location,
                )
                for item in collect_page_number_diagnostics(doc, context, header_footer)
                if item.level == "error"
            )
        return issues

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        count = 0
        count += _ensure_logical_section_breaks(doc, config, context)

        # 1. 清理题注-表格之间的多余分节符
        count += _remove_caption_table_section_breaks(doc)

        # 2. 统一分节类型
        section_type = config.section.section_break_type if config.section else None
        if section_type:
            count += _normalize_section_types(doc, section_type, tracker)

        # 3. 清理空白分节
        count += _remove_empty_sections(doc)

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 处分节属性",
                section="global",
                change_type="format",
                before="(mixed)",
                after="已清理/统一",
            )


# ── 分节类型统一 ─────────────────────────────────

def _normalize_section_types(
    doc: Document,
    target_type: str,
    tracker: ChangeTracker,
) -> int:
    """将所有分节符统一为指定类型。

    target_type: "nextPage" / "continuous" / "evenPage" / "oddPage"
    """
    count = 0
    for section in doc.sections:
        sect_pr = section._sectPr
        type_elem = find(sect_pr, "w:type")

        if type_elem is not None:
            old_type = type_elem.get(qn("w:val"), "")
            if old_type != target_type:
                type_elem.set(qn("w:val"), target_type)
                count += 1
        # 无 type 元素的默认是 nextPage，如果目标不同则添加
        elif target_type != "nextPage":
            type_elem = find_or_create(sect_pr, "w:type")
            type_elem.set(qn("w:val"), target_type)
            count += 1

    return count


# ── 空白分节清理 ─────────────────────────────────

def _remove_empty_sections(doc: Document) -> int:
    """清理连续多个空分节（两个 sectPr 之间无实际内容）。"""
    count = 0
    body = doc.element.body
    paragraphs = body.findall(qn("w:p"))

    # 找出含有 sectPr 的段落
    sect_paras = []
    for i, p in enumerate(paragraphs):
        sect_pr = p.find(qn("w:pPr"))
        if sect_pr is not None and sect_pr.find(qn("w:sectPr")) is not None:
            sect_paras.append((i, p))

    # 检查连续分节之间是否有内容
    for idx in range(len(sect_paras) - 1, 0, -1):
        curr_idx, curr_p = sect_paras[idx]
        prev_idx, _prev_p = sect_paras[idx - 1]

        if _get_para_text(curr_p).strip():
            continue

        # 只有当两个分节之间没有实际文本内容时才清理
        has_content = False
        for j in range(prev_idx + 1, curr_idx):
            p_text = _get_para_text(paragraphs[j])
            if p_text.strip():
                has_content = True
                break

        if not has_content:
            pPr = curr_p.find(qn("w:pPr"))
            if pPr is not None:
                sect_pr = pPr.find(qn("w:sectPr"))
                if sect_pr is not None:
                    pPr.remove(sect_pr)
                    count += 1

    return count


# ── 题注-表格分节清理 ────────────────────────────

def _remove_caption_table_section_breaks(doc: Document) -> int:
    """清理题注段落与紧随表格之间的多余 sectPr。

    Word 从网页粘贴时经常在题注和表格之间插入无意义的分节，
    导致后续表格排版异常。
    """
    count = 0
    body = doc.element.body
    children = list(body)

    for i, child in enumerate(children):
        if child.tag != qn("w:p"):
            continue

        # 找含有 sectPr 的段落
        pPr = child.find(qn("w:pPr"))
        if pPr is None:
            continue
        sect_pr = pPr.find(qn("w:sectPr"))
        if sect_pr is None:
            continue

        # 检查前一个元素是否是题注，后一个是否是表格
        text = _get_para_text(child).strip()
        if not text:
            # 空段落含分节 → 检查下一元素是否是表格
            if i + 1 < len(children) and children[i + 1].tag == qn("w:tbl"):
                pPr.remove(sect_pr)
                count += 1

    return count


def _ensure_logical_section_breaks(
    doc: Document,
    config: ResolvedConfig,
    context: PipelineContext,
) -> int:
    plan = build_page_number_execution_plan(doc, context, config.header_footer)
    if plan.missing_doc_tree:
        return 0

    count = 0
    for boundary in plan.boundaries:
        if not boundary.requires_section_break:
            continue
        if _ensure_section_break_before_paragraph(doc, boundary.start_index, "nextPage"):
            count += 1
    return count


def _ensure_section_break_before_paragraph(doc: Document, para_index: int, break_type: str) -> bool:
    if para_index <= 0 or para_index >= len(doc.paragraphs):
        return False
    if _has_table_between_paragraphs(doc, para_index - 1, para_index):
        return False

    prev_para = doc.paragraphs[para_index - 1]
    prev_ppr = find_or_create(prev_para._element, "w:pPr")
    sect_pr = prev_ppr.find(qn("w:sectPr"))
    if sect_pr is None:
        sect_pr = _build_section_break_sectpr(doc, break_type)
        prev_ppr.append(sect_pr)
        return True

    type_elem = find_or_create(sect_pr, "w:type")
    old_type = type_elem.get(qn("w:val"), "nextPage")
    if old_type == break_type:
        return False
    type_elem.set(qn("w:val"), break_type)
    return True


def _build_section_break_sectpr(doc: Document, break_type: str):
    body_sect_pr = doc.element.body.find(qn("w:sectPr"))
    if body_sect_pr is not None:
        sect_pr = clone_element(body_sect_pr)
        # Strip header/footer references to avoid sharing the same physical
        # header XML across sections (which causes overwriting).
        for ref_tag in ("w:headerReference", "w:footerReference"):
            for ref_el in list(sect_pr.findall(qn(ref_tag))):
                sect_pr.remove(ref_el)
    else:
        from lxml import etree

        sect_pr = etree.Element(qn("w:sectPr"))
    type_elem = find_or_create(sect_pr, "w:type")
    type_elem.set(qn("w:val"), break_type)
    return sect_pr


def _has_table_between_paragraphs(doc: Document, left_para_index: int, right_para_index: int) -> bool:
    if left_para_index < 0 or right_para_index >= len(doc.paragraphs) or left_para_index >= right_para_index:
        return False

    body_children = list(doc.element.body)
    left_el = doc.paragraphs[left_para_index]._element
    right_el = doc.paragraphs[right_para_index]._element
    left_body_index = None
    right_body_index = None
    for index, child in enumerate(body_children):
        if child is left_el:
            left_body_index = index
        if child is right_el:
            right_body_index = index
            break

    if left_body_index is None or right_body_index is None or right_body_index <= left_body_index + 1:
        return False

    for child in body_children[left_body_index + 1:right_body_index]:
        if child.tag == qn("w:tbl"):
            return True
    return False


def _get_para_text(p_elem) -> str:
    """从 XML 段落元素提取文本。"""
    texts = []
    for t in p_elem.iter(qn("w:t")):
        if t.text:
            texts.append(t.text)
    return "".join(texts)
