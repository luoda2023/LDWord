"""
paragraph_style — 段落样式模块

设置正文/标题/题注等段落的字体、字号、行距、缩进、对齐。
不处理分节（→ section_format）、标题编号（→ heading_numbering）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.font_resolver import resolve_font
from src.shared.engine.style_ops import apply_style_text_format
from src.shared.engine.units import cn_size_to_pt
from src.shared.engine.run_ops import set_run_east_asian_font

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 对齐映射 ─────────────────────────────────────

ALIGNMENT_MAP: dict[str, int] = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "distribute": WD_ALIGN_PARAGRAPH.DISTRIBUTE,
}


class ParagraphStyleModule(BaseModule):
    """段落样式模块。

    按 ResolvedConfig 中的 styles 配置，对各类段落设置：
    - 字体（中/英文分别设置）
    - 字号
    - 行距（固定值/多倍）
    - 缩进（首行/左/右）
    - 段前段后间距
    - 对齐方式
    """

    meta = ModuleMeta(
        name="paragraph_style",
        description="段落样式",
        category="basic",
        requires_config=("styles",),
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
        styles_cfg = config.styles
        max_levels = config.heading_model.max_heading_levels
        style_definition_count = _sync_heading_style_definitions(doc, config)
        count = 0

        for i, para in enumerate(doc.paragraphs):
            text = (para.text or "").strip()
            if not text:
                continue

            # 确定段落类型 → 选择样式配置
            style_key = _resolve_style_key(para, context)
            # 超出级数上限的标题 → 降级为 normal
            if style_key.startswith("heading") and style_key != "heading":
                lvl_num = int(style_key.replace("heading", "") or "0")
                if lvl_num > max_levels:
                    style_key = "normal"
            sc = styles_cfg.get(style_key)
            # 分级 heading 回退: heading2 → heading → normal
            if not sc and style_key.startswith("heading") and style_key != "heading":
                sc = styles_cfg.get("heading")
            if not sc:
                sc = styles_cfg.get("normal")
            if not sc:
                continue

            applied = _apply_style_to_paragraph(para, sc)
            if applied:
                count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个段落",
                section="global",
                change_type="format",
                before="(mixed)",
                after="已统一样式",
            )
        if style_definition_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{style_definition_count} 个 Word 标题样式定义",
                section="global",
                change_type="format",
                before="字号未同步",
                after="已同步到样式定义",
            )


def _resolve_style_key(
    para: Paragraph,
    context: PipelineContext,
) -> str:
    """根据段落属性确定应使用的样式配置 key。"""
    style = para.style
    style_name = style.name if style else ""
    style_lower = style_name.lower()

    # 标题 → 分级查找 heading1/heading2/..., fallback heading
    if style_lower.startswith("heading") or "标题" in style_name:
        # 提取级别数字: "Heading 2" → 2, "heading 1 Unnumbered" → 1
        import re
        m = re.search(r"(\d+)", style_name)
        if m:
            return f"heading{m.group(1)}"
        return "heading"

    # 题注
    if "caption" in style_lower or "题注" in style_name:
        return "caption"

    # 目录
    if style_lower.startswith("toc") or "目录" in style_name:
        return "toc"

    # 页眉 → 由 header_footer 处理
    if "header" in style_lower or "页眉" in style_name:
        return "header"

    # 页脚
    if "footer" in style_lower or "页脚" in style_name:
        return "footer"

    # 利用 doc_tree 判断所在区域
    doc_tree = context.doc_tree
    if doc_tree is not None:
        sec_type = doc_tree.get_section_for_paragraph(
            _get_para_index(para)
        )
        if sec_type == "references":
            return "references_body"
        if sec_type in ("abstract_cn", "abstract_en"):
            return "abstract_body"
        if sec_type == "appendix":
            return "appendix_body"

    return "normal"


def _get_para_index(para: Paragraph) -> int:
    """获取段落在文档中的索引。"""
    body = para._element.getparent()
    if body is None:
        return -1
    for i, child in enumerate(body):
        if child is para._element:
            return i
    return -1


def _apply_style_to_paragraph(para: Paragraph, sc) -> bool:
    """应用样式配置到段落。

    sc 是 StyleConfig (或 dict-like)，字段定义参见 config/template.py。
    """
    size_pt = _resolve_size_pt(sc)
    changed = False
    changed |= _apply_font(para, sc, size_pt)
    changed |= _apply_alignment(para, sc)
    changed |= _apply_spacing(para, sc)
    changed |= _apply_indent(para, sc, size_pt)
    return changed


def _sync_heading_style_definitions(doc: Document, config: ResolvedConfig) -> int:
    """同步 Heading 1..8 的 Word 样式定义文本属性。"""
    styles_cfg = config.styles
    style_name_map = config.heading_model.level_to_word_style or {}
    count = 0

    for level in range(1, 9):
        style_key = f"heading{level}"
        sc = styles_cfg.get(style_key) or styles_cfg.get("heading")
        if sc is None:
            continue

        size_pt = _resolve_size_pt(sc)
        if size_pt is None:
            continue

        word_style_name = str(
            style_name_map.get(style_key) or f"Heading {level}"
        )
        try:
            style = doc.styles[word_style_name]
        except KeyError:
            continue

        if apply_style_text_format(
            style,
            font_cn=sc.font_cn,
            font_en=sc.font_en,
            size_pt=size_pt,
        ):
            count += 1

    return count


def _resolve_size_pt(sc) -> float | None:
    """从 size_pt 或 size_display 解析字号 (pt)。"""
    size_pt = sc.size_pt
    if size_pt is None:
        cn_size = sc.size_display
        if cn_size:
            size_pt = cn_size_to_pt(cn_size)
    return size_pt


def _apply_font(para: Paragraph, sc, size_pt: float | None) -> bool:
    """字体、字号、粗体、斜体。"""
    font_cn = sc.font_cn
    font_en = sc.font_en
    bold = sc.bold
    italic = sc.italic

    if not (font_cn or font_en or size_pt is not None or bold is not None or italic is not None):
        return False

    for run in para.runs:
        if font_en:
            run.font.name = resolve_font(font_en, lang="en")
        if font_cn:
            set_run_east_asian_font(run, font_cn)
        if size_pt:
            run.font.size = Pt(size_pt)
        if bold is not None:
            run.font.bold = bold
        if italic is not None:
            run.font.italic = italic
    return True


def _apply_alignment(para: Paragraph, sc) -> bool:
    """段落对齐。"""
    alignment = sc.alignment
    if alignment and alignment in ALIGNMENT_MAP:
        para.paragraph_format.alignment = ALIGNMENT_MAP[alignment]
        return True
    return False


def _apply_spacing(para: Paragraph, sc) -> bool:
    """段前段后、行距。"""
    changed = False
    pf = para.paragraph_format

    space_before = sc.space_before_pt
    if space_before is not None:
        pf.space_before = Pt(space_before)
        changed = True

    space_after = sc.space_after_pt
    if space_after is not None:
        pf.space_after = Pt(space_after)
        changed = True

    ls_type = sc.line_spacing_type
    ls_val = sc.line_spacing_pt
    if ls_val is not None:
        if ls_type == "exact" or ls_type == "fixed":
            pf.line_spacing = Pt(ls_val)
        else:
            pf.line_spacing = ls_val  # 倍数
        changed = True

    return changed


def _apply_indent(para: Paragraph, sc, size_pt: float | None) -> bool:
    """首行、左、右、悬挂缩进。"""
    changed = False
    pf = para.paragraph_format
    effective_pt = size_pt or 12

    # 首行缩进
    first_indent = sc.first_line_indent_chars
    first_indent_unit = sc.first_line_indent_unit
    if first_indent is not None:
        if first_indent == 0:
            pf.first_line_indent = Pt(0)
        elif first_indent_unit == "cm":
            pf.first_line_indent = Cm(first_indent)
        else:
            pf.first_line_indent = Pt(first_indent * effective_pt)
        changed = True

    # 左缩进
    left_indent = sc.left_indent_chars
    left_indent_unit = sc.left_indent_unit
    if left_indent is not None and left_indent > 0:
        if left_indent_unit == "cm":
            pf.left_indent = Cm(left_indent)
        else:
            pf.left_indent = Pt(left_indent * effective_pt)
        changed = True

    # 右缩进
    right_indent = sc.right_indent_chars
    right_indent_unit = sc.right_indent_unit
    if right_indent is not None and right_indent > 0:
        if right_indent_unit == "cm":
            pf.right_indent = Cm(right_indent)
        else:
            pf.right_indent = Pt(right_indent * effective_pt)
        changed = True

    # 悬挂缩进
    hanging = sc.hanging_indent_chars
    hanging_unit = sc.hanging_indent_unit
    if hanging is not None and hanging > 0:
        if hanging_unit == "cm":
            pf.left_indent = Cm(hanging)
            pf.first_line_indent = Cm(-hanging)
        else:
            pf.left_indent = Pt(hanging * effective_pt)
            pf.first_line_indent = Pt(-hanging * effective_pt)
        changed = True

    return changed


