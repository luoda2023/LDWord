"""Semantic sample content shared by every lightweight template projection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplatePreviewSample:
    heading_titles: tuple[str, ...]
    body_text: str
    compact_body_text: str
    secondary_body_text: str
    compact_secondary_body_text: str
    non_numbered_title: str
    non_numbered_body: str
    table_rows: tuple[tuple[str, str, str], ...]
    figure_caption_title: str
    table_caption_title: str


DEFAULT_TEMPLATE_PREVIEW_SAMPLE = TemplatePreviewSample(
    heading_titles=(
        "绪论",
        "研究背景",
        "国内外研究现状",
        "研究方法",
        "实验设计",
        "结果分析",
        "讨论",
        "结论",
    ),
    body_text=(
        "本文示例用于预览正文样式，包括中文、English、数字 123 与括号"
        "（示例）等混排效果。"
    ),
    compact_body_text="正文示例：中文、English 与数字 123 混排。",
    secondary_body_text="此段用于观察标题后的段前、段后、行距与首行缩进。",
    compact_secondary_body_text="观察标题后的间距与缩进。",
    non_numbered_title="摘要",
    non_numbered_body="此处用于预览特殊标题样式；它不参与标题编号。",
    table_rows=(
        ("指标", "数值", "说明"),
        ("样本 A", "1.23", "有效"),
        ("样本 B", "2.35", "稳定"),
    ),
    figure_caption_title="研究框架示意",
    table_caption_title="实验指标统计",
)


__all__ = ["DEFAULT_TEMPLATE_PREVIEW_SAMPLE", "TemplatePreviewSample"]
