"""
heading_recognition — 标题识别模块

扫描文档段落，识别各级标题并构建文档结构树 (doc_tree)。
依据样式名 + 编号模式 + 大纲级别进行多策略识别。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.style_resolver import get_heading_level, is_heading_paragraph

if TYPE_CHECKING:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 编号模式 ─────────────────────────────────────

_LEVEL_PATTERNS: list[tuple[str, re.Pattern]] = [
    # 阿拉伯数字层级
    ("heading4", re.compile(r"^\d+\.\d+\.\d+\.\d+[\s\u3000\t]")),
    ("heading3", re.compile(r"^\d+\.\d+\.\d+[\s\u3000\t]")),
    ("heading2", re.compile(r"^\d+\.\d+[\s\u3000\t]")),
    ("heading1", re.compile(r"^\d+[\s\u3000\t]")),
    # 中文
    ("heading1", re.compile(r"^第[一二三四五六七八九十百零]+[章篇][\s\u3000]")),
    ("heading1", re.compile(r"^第[一二三四五六七八九十百零]+[节条][\s\u3000]")),
    ("heading2", re.compile(r"^[一二三四五六七八九十百]+[、.][\s\u3000]?")),
    ("heading3", re.compile(r"^[（(][一二三四五六七八九十]+[）)]")),
    ("heading4", re.compile(r"^\d+[)）][\s\u3000\t]")),
    # 罗马数字
    ("heading1", re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ][、.\s\u3000]")),
    ("heading2", re.compile(r"^[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ][、.\s\u3000]")),
    # 字母
    ("heading3", re.compile(r"^[A-Z][、.)）][\s\u3000]?")),
    ("heading4", re.compile(r"^[a-z][、.)）][\s\u3000]?")),
]

_NARRATIVE_PUNCT = re.compile(r"[。；;？！?!]")
_TOC_STYLE_RE = re.compile(r"^(toc|目录)(\s*\d+|\s*heading)", re.IGNORECASE)

# 特殊节标题（一级标题但不编号）
_SPECIAL_SECTION_TITLES: dict[str, str] = {
    "参考文献": "references", "references": "references", "bibliography": "references",
    "摘要": "abstract_cn", "abstract": "abstract_en",
    "致谢": "acknowledgements", "acknowledgements": "acknowledgements",
    "附录": "appendix", "appendix": "appendix",
    "目录": "toc", "绪论": "body", "引言": "body",
    "勘误": "errata", "勘误页": "errata",
    "个人简历": "bio",
    "在学期间发表的学术论文与研究成果": "bio",
}


# ── 数据结构 ─────────────────────────────────────

@dataclass
class HeadingInfo:
    """标题识别结果。"""
    para_index: int
    level: int                  # 1-9
    text: str
    confidence: str = "high"    # "high" | "low"


@dataclass
class DocTree:
    """文档结构树。"""
    headings: list[HeadingInfo] = field(default_factory=list)
    heading_map: dict[int, int] = field(default_factory=dict)  # para_index → level
    section_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)  # section → (start, end)

    def get_heading_level(self, para_index: int) -> int | None:
        return self.heading_map.get(para_index)

    def get_section_for_paragraph(self, para_index: int) -> str:
        """获取段落所在的逻辑区域。"""
        for section_name, (start, end) in self.section_ranges.items():
            if start <= para_index < end:
                return section_name
        return "body"


class HeadingRecognitionModule(BaseModule):
    """标题识别模块。

    职责：
    - 扫描文档段落，依据样式名/编号模式/大纲级别识别标题
    - 构建 doc_tree 和 heading_map 写入 PipelineContext
    """

    meta = ModuleMeta(
        name="heading_recognition",
        description="标题识别",
        category="structure",
        requires_config=(),
        provides=("doc_tree", "heading_map"),
        enabled_by_default=True,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        headings: list[HeadingInfo] = []

        for i, para in enumerate(doc.paragraphs):
            text = (para.text or "").strip()
            if not text:
                continue

            level = _detect_heading(para, text)
            if level is not None:
                headings.append(HeadingInfo(
                    para_index=i,
                    level=level,
                    text=text[:80],
                ))

        # 构建 doc_tree
        heading_map = {h.para_index: h.level for h in headings}
        section_ranges = _build_section_ranges(headings, len(doc.paragraphs))
        doc_tree = DocTree(
            headings=headings,
            heading_map=heading_map,
            section_ranges=section_ranges,
        )

        # 写入 context
        context.doc_tree = doc_tree
        context.heading_map = heading_map

        if headings:
            level_counts = {}
            for h in headings:
                level_counts[h.level] = level_counts.get(h.level, 0) + 1

            tracker.record(
                rule_name=self.meta.name,
                target=f"{len(headings)} 个标题",
                section="global",
                change_type="detect",
                before="(未识别)",
                after=", ".join(f"H{k}={v}" for k, v in sorted(level_counts.items())),
            )


# ── 标题检测 ─────────────────────────────────────

def _detect_heading(para: Paragraph, text: str) -> int | None:
    """检测段落是否为标题，返回级别 (1-9) 或 None。"""
    # 排除：含叙事标点的长文本
    if len(text) > 80 and _NARRATIVE_PUNCT.search(text):
        return None

    # 排除：目录样式段落
    style_name = para.style.name if para.style else ""
    if _TOC_STYLE_RE.match(style_name.lower()):
        return None

    # 策略1: 通过 Word 样式名/大纲级别 (高置信度)
    level_from_style = get_heading_level(para)
    if level_from_style is not None:
        return level_from_style

    # 策略2: 通过编号模式匹配文本 (需要辅助视觉信号)
    # Normal 样式段落不能仅靠文本模式提升为标题 — 必须有标题视觉特征
    if len(text) <= 60 and _has_heading_visual_traits(para):
        level_from_pattern = _detect_by_pattern(text)
        if level_from_pattern is not None:
            return level_from_pattern

    return None


def _has_heading_visual_traits(para: Paragraph) -> bool:
    """判断段落是否具有标题视觉特征（加粗/大字号/短且独立）。

    用于辅助确认文本模式匹配的有效性：
    - 段落整体加粗
    - 首 run 字号 >= 12pt (小四)
    - 段落有 outlineLvl (即使 get_heading_level 没返回有效值)
    """
    from docx.shared import Pt
    from src.shared.engine.ooxml_ops import qn

    # 检查 outline level (即使超出 1-9, 也说明段落有结构意图)
    pPr = para._element.find(qn("w:pPr"))
    if pPr is not None and pPr.find(qn("w:outlineLvl")) is not None:
        return True

    # 检查加粗 — 段落级别或首 run 级别
    if para.runs:
        first_run = para.runs[0]
        if first_run.bold:
            return True
        # 检查字号 >= 三号 (16pt) — 明显大于正文的字号
        if first_run.font.size and first_run.font.size >= Pt(14):
            return True

    return False


def _detect_by_pattern(text: str) -> int | None:
    """通过编号模式匹配标题级别。"""
    for level_name, pattern in _LEVEL_PATTERNS:
        if pattern.match(text):
            return int(level_name[-1])
    return None


def _detect_special_section(text: str) -> str | None:
    """检测特殊节标题（参考文献/致谢/附录等）。"""
    normalized = text.strip().lower()
    for title, section in _SPECIAL_SECTION_TITLES.items():
        if title in normalized and len(text) < 30:
            return section
    return None


def _build_section_ranges(
    headings: list[HeadingInfo],
    total_paras: int,
) -> dict[str, tuple[int, int]]:
    """根据标题构建逻辑区域范围。"""
    ranges: dict[str, tuple[int, int]] = {}

    for i, h in enumerate(headings):
        section = _detect_special_section(h.text)
        if section:
            start = h.para_index
            end = headings[i + 1].para_index if i + 1 < len(headings) else total_paras
            ranges[section] = (start, end)

    return ranges
