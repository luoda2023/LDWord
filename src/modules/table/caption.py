"""
caption — 图表题注编号模块

自动识别图/表题注段落，统一编号格式。
支持按章编号（图 1.1 / 表 2.3）和全局编号（图 1 / 表 1）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 题注正则 ─────────────────────────────────────

_RE_FIG_CAPTION = re.compile(
    r"^(?P<prefix>图|Figure|Fig\.?)\s*"
    r"(?P<num>[一二三四五六七八九十\d]+(?:[.\-]\d+)*)"
    r"(?P<sep>\s+|[\s\u3000])"
    r"(?P<title>.*)",
    re.IGNORECASE,
)

_RE_TBL_CAPTION = re.compile(
    r"^(?P<prefix>表|Table|Tab\.?)\s*"
    r"(?P<num>[一二三四五六七八九十\d]+(?:[.\-]\d+)*)"
    r"(?P<sep>\s+|[\s\u3000])"
    r"(?P<title>.*)",
    re.IGNORECASE,
)

_RE_GENERIC_CAPTION = re.compile(
    r"^(?P<prefix>图|表|Figure|Table|Fig\.?|Tab\.?)\s*",
    re.IGNORECASE,
)


@dataclass
class CaptionInfo:
    """题注信息。"""
    para_index: int
    kind: str           # "figure" | "table"
    prefix: str         # "图" / "表" / "Figure" / "Table"
    old_number: str     # 原编号文本
    title: str          # 标题文本
    new_number: str = ""


class CaptionModule(BaseModule):
    """题注编号模块。

    职责：
    - 扫描识别图/表题注段落
    - 按章编号或全局编号重新编号
    - 统一题注格式（字体、居中）
    - 输出 caption_counters 到 context
    """

    meta = ModuleMeta(
        name="caption",
        description="题注编号",
        category="table",
        requires_config=("caption",),
        soft_after=("heading_recognition",),
        provides=("caption_counters",),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        caption_cfg = config.caption
        heading_map = context.heading_map or {}

        # 1. 扫描所有题注
        captions = _scan_captions(doc)
        if not captions:
            return

        # 2. 构建章号范围
        chapter_ranges = _build_chapter_ranges(heading_map, len(doc.paragraphs))

        # 3. 重新编号
        numbering_mode = caption_cfg.numbering_mode
        fig_counter = 0
        tbl_counter = 0
        chapter_fig_counters: dict[int, int] = {}
        chapter_tbl_counters: dict[int, int] = {}

        for cap in captions:
            chapter_num = _get_chapter_num(cap.para_index, chapter_ranges)

            if numbering_mode == "chapter" and chapter_num > 0:
                if cap.kind == "figure":
                    chapter_fig_counters[chapter_num] = chapter_fig_counters.get(chapter_num, 0) + 1
                    cap.new_number = f"{chapter_num}.{chapter_fig_counters[chapter_num]}"
                else:
                    chapter_tbl_counters[chapter_num] = chapter_tbl_counters.get(chapter_num, 0) + 1
                    cap.new_number = f"{chapter_num}.{chapter_tbl_counters[chapter_num]}"
            else:
                if cap.kind == "figure":
                    fig_counter += 1
                    cap.new_number = str(fig_counter)
                else:
                    tbl_counter += 1
                    cap.new_number = str(tbl_counter)

        # 4. 应用编号
        count = 0
        for cap in captions:
            para = doc.paragraphs[cap.para_index]
            new_text = f"{cap.prefix} {cap.new_number} {cap.title}"
            _replace_caption_text(para, new_text)

            # 居中
            para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

            count += 1

        # 5. 写入 context
        context.caption_counters = {
            "figure": fig_counter or sum(chapter_fig_counters.values()),
            "table": tbl_counter or sum(chapter_tbl_counters.values()),
        }

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个题注",
                section="global",
                change_type="format",
                before="(mixed)",
                after=f"mode={numbering_mode}",
            )


# ── 扫描题注 ─────────────────────────────────────

def _scan_captions(doc: Document) -> list[CaptionInfo]:
    """扫描文档中的图/表题注段落。"""
    captions = []
    for i, para in enumerate(doc.paragraphs):
        text = (para.text or "").strip()
        if not text:
            continue

        # 尝试匹配图题注
        m = _RE_FIG_CAPTION.match(text)
        if m:
            captions.append(CaptionInfo(
                para_index=i,
                kind="figure",
                prefix=m.group("prefix"),
                old_number=m.group("num"),
                title=m.group("title").strip(),
            ))
            continue

        # 尝试匹配表题注
        m = _RE_TBL_CAPTION.match(text)
        if m:
            captions.append(CaptionInfo(
                para_index=i,
                kind="table",
                prefix=m.group("prefix"),
                old_number=m.group("num"),
                title=m.group("title").strip(),
            ))

    return captions


# ── 章号范围 ─────────────────────────────────────

def _build_chapter_ranges(
    heading_map: dict[int, int],
    total_paragraphs: int,
) -> list[tuple[int, int, int]]:
    """从 heading_map 构建章号范围 [(start, end, chapter_num), ...]"""
    h1_indices = sorted(i for i, lvl in heading_map.items() if lvl == 1)
    if not h1_indices:
        return []

    ranges = []
    for idx, start in enumerate(h1_indices):
        end = h1_indices[idx + 1] - 1 if idx + 1 < len(h1_indices) else total_paragraphs - 1
        ranges.append((start, end, idx + 1))

    return ranges


def _get_chapter_num(para_index: int, chapter_ranges) -> int:
    """查询段落所属章号。"""
    for start, end, num in chapter_ranges:
        if start <= para_index <= end:
            return num
    return 0


# ── 文本替换 ─────────────────────────────────────

def _replace_caption_text(para: Paragraph, new_text: str) -> None:
    """替换题注段落文本（保留首个 Run 的格式）。"""
    if not para.runs:
        para.add_run(new_text)
        return

    # 保留第一个 run 的格式, 替换文本
    first_run = para.runs[0]
    first_run.text = new_text

    # 移除多余 runs
    for run in para.runs[1:]:
        run._element.getparent().remove(run._element)
