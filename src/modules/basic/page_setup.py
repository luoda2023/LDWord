"""
page_setup — 页面设置模块

设置纸张大小、页边距、装订线、页眉页脚距离。
不处理页眉页脚内容格式（那属于 header_footer 模块）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docx.shared import Cm

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn, find

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 纸张尺寸 (cm) ────────────────────────────────

PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "LETTER": (21.59, 27.94),
    "LEGAL": (21.59, 35.56),
    "16K": (18.4, 26.0),
}


def _section_has_explicit_orientation(section) -> bool:
    """Check whether a section's XML has an explicit w:orient attribute."""
    sect_pr = section._sectPr
    pg_sz = find(sect_pr, "w:pgSz")
    if pg_sz is None:
        return False
    return pg_sz.get(qn("w:orient")) is not None


class PageSetupModule(BaseModule):
    """页面设置模块。

    职责：纸张大小 + 页边距 + 装订线 + 页眉页脚距离
    不职责：页眉页脚内容格式（→ header_footer 模块）
    """

    meta = ModuleMeta(
        name="page_setup",
        description="页面设置",
        category="basic",
        requires_config=("page_setup",),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        ps = config.page_setup

        # 解析纸张尺寸
        paper_key = ps.paper_size.strip().upper()
        if paper_key not in PAPER_SIZES:
            paper_key = "A4"
        paper_w, paper_h = PAPER_SIZES[paper_key]

        # 模板默认方向
        template_landscape = getattr(ps, "orientation", "portrait") == "landscape"

        for idx, section in enumerate(doc.sections):
            old_width = section.page_width
            old_top = section.top_margin

            # 判断该节方向：有显式 orient 属性 → 保留；否则 → 用模板默认
            if _section_has_explicit_orientation(section):
                is_landscape = (
                    section.page_width is not None
                    and section.page_height is not None
                    and section.page_width > section.page_height
                )
            else:
                is_landscape = template_landscape

            # 设置纸张大小（按方向交换宽高）
            if is_landscape:
                section.page_width = Cm(paper_h)
                section.page_height = Cm(paper_w)
            else:
                section.page_width = Cm(paper_w)
                section.page_height = Cm(paper_h)

            # 设置页边距
            section.top_margin = Cm(ps.margin.top_cm)
            section.bottom_margin = Cm(ps.margin.bottom_cm)
            section.left_margin = Cm(ps.margin.left_cm)
            section.right_margin = Cm(ps.margin.right_cm)

            # 装订线
            section.gutter = Cm(ps.gutter_cm)

            # 页眉页脚距离
            section.header_distance = Cm(ps.header_distance_cm)
            section.footer_distance = Cm(ps.footer_distance_cm)

            tracker.record(
                rule_name=self.meta.name,
                target=f"Section {idx + 1}",
                section="global",
                change_type="format",
                before=f"width={old_width}, top={old_top}",
                after=(
                    f"paper={paper_key}, "
                    f"orient={'landscape' if is_landscape else 'portrait'}, "
                    f"margin=({ps.margin.top_cm}/{ps.margin.bottom_cm}/"
                    f"{ps.margin.left_cm}/{ps.margin.right_cm})cm"
                ),
            )

