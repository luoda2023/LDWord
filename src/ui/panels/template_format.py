"""Compatibility helpers for template overview summaries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.config.template import TemplateConfig
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.ui.panels.template_summary_projection import (
    all_template_detail_summaries,
)


@dataclass(frozen=True, slots=True)
class TemplatePreviewGroup:
    group_id: str
    detail_card_id: str
    label: str
    icon_name: str
    summary: str
    field_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemplatePreviewGroupSpec:
    group_id: str
    detail_card_id: str
    label: str
    icon_name: str
    field_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemplatePreviewContext:
    """Shared user-facing context for scene-to-template preview entry."""

    title: str
    detail: str
    action: str
    coverage_labels: tuple[str, ...]
    detail_card_ids: tuple[str, ...]

    @property
    def detail_with_action(self) -> str:
        if self.detail and self.action:
            return f"{self.detail}；{self.action}"
        return self.detail or self.action


TEMPLATE_PREVIEW_SPECS: tuple[TemplatePreviewGroupSpec, ...] = (
    TemplatePreviewGroupSpec("page", "tpl_page", "页面", "ruler", ("page_setup", "section")),
    TemplatePreviewGroupSpec("style", "tpl_style", "排版", "type-outline", ("styles",)),
    TemplatePreviewGroupSpec("heading", "tpl_heading", "标题", "list-ordered", ("heading_numbering", "heading_model")),
    TemplatePreviewGroupSpec("table", "tpl_table", "表格", "table-2", ("table",)),
    TemplatePreviewGroupSpec("header_footer", "tpl_header_footer", "页眉与页脚", "panel-top", ("header_footer",)),
    TemplatePreviewGroupSpec("toc", "tpl_toc", "目录", "chart-no-axes-gantt", ("toc",)),
    TemplatePreviewGroupSpec("caption", "tpl_caption", "题注", "waves-arrow-down", ("caption", "styles")),
)

TEMPLATE_PREVIEW_ACTION_LABELS: dict[str, str] = {
    "page": "页面",
    "style": "正文",
    "heading": "标题",
    "table": "表格",
    "header_footer": "页眉页脚",
    "toc": "目录",
    "caption": "题注",
}


def _group_id(detail_card_id: str) -> str:
    return {
        "tpl_page": "page",
        "tpl_style": "style",
        "tpl_heading": "heading",
        "tpl_table": "table",
        "tpl_header_footer": "header_footer",
        "tpl_toc": "toc",
        "tpl_caption": "caption",
    }[detail_card_id]


def _cn_join(values: Sequence[str]) -> str:
    labels = [str(value or "").strip() for value in values if str(value or "").strip()]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return "、".join(labels[:-1]) + "和" + labels[-1]


def _preview_action_label(group_id: str, fallback: str) -> str:
    return TEMPLATE_PREVIEW_ACTION_LABELS.get(str(group_id or "").strip(), fallback)


def template_preview_coverage_labels(
    groups: Sequence[TemplatePreviewGroup | TemplatePreviewGroupSpec],
) -> tuple[str, ...]:
    return tuple(
        _preview_action_label(
            str(getattr(group, "group_id", "") or ""),
            str(getattr(group, "label", "") or ""),
        )
        for group in groups
        if str(getattr(group, "group_id", "") or "").strip()
    )


def build_template_preview_action_text(
    groups: Sequence[TemplatePreviewGroup | TemplatePreviewGroupSpec],
) -> str:
    coverage = template_preview_coverage_labels(groups)
    joined = _cn_join(coverage)
    return f"核对{joined}" if joined else "核对模板预览"


def build_template_preview_description(
    groups: Sequence[TemplatePreviewGroup | TemplatePreviewGroupSpec],
) -> str:
    coverage = template_preview_coverage_labels(groups)
    joined = _cn_join(coverage)
    return f"预览{joined}在同一页中的效果。" if joined else "预览模板样式效果。"


def build_template_preview_context(
    cfg: TemplateConfig,
    *,
    scene_label: str = "",
    template_label: str = "",
    detail: str = "",
    title: str = "来自场景：核对模板与样式",
) -> TemplatePreviewContext:
    groups = tuple(build_template_preview_groups(cfg))
    detail_parts = []
    explicit_detail = str(detail or "").strip()
    if explicit_detail:
        detail_text = explicit_detail
    else:
        detail_text = ""
    if not detail_text and str(scene_label or "").strip():
        detail_parts.append(f"场景：{str(scene_label).strip()}")
    if not detail_text and str(template_label or "").strip():
        detail_parts.append(f"模板：{str(template_label).strip()}")
    if not detail_text:
        detail_text = "；".join(detail_parts)
    return TemplatePreviewContext(
        title=title,
        detail=detail_text,
        action=build_template_preview_action_text(groups),
        coverage_labels=template_preview_coverage_labels(groups),
        detail_card_ids=tuple(group.detail_card_id for group in groups),
    )


def build_template_page_presentation_envelope(
    cfg: TemplateConfig,
) -> StylePresentationEnvelope:
    groups = tuple(build_template_preview_groups(cfg))
    template_label = str(getattr(cfg, "name", "") or "").strip() or "当前模板"
    return StylePresentationEnvelope.from_template_page(
        template_label=template_label,
        summary=build_template_preview_description(groups),
        action_label=build_template_preview_action_text(groups),
    )


def build_template_preview_groups(cfg: TemplateConfig) -> list[TemplatePreviewGroup]:
    return [
        TemplatePreviewGroup(
            group_id=_group_id(summary.detail_card_id),
            detail_card_id=summary.detail_card_id,
            label=summary.nav_label,
            icon_name=summary.icon_name,
            summary=summary.nav_summary,
            field_names=summary.field_names,
        )
        for summary in all_template_detail_summaries(cfg)
    ]


def build_template_summary_lines(cfg: TemplateConfig) -> list[tuple[str, str, str]]:
    return [
        (group.icon_name, group.label, group.summary)
        for group in build_template_preview_groups(cfg)
    ]


__all__ = [
    "TemplatePreviewGroup",
    "TemplatePreviewGroupSpec",
    "TemplatePreviewContext",
    "TEMPLATE_PREVIEW_SPECS",
    "build_template_page_presentation_envelope",
    "build_template_preview_action_text",
    "build_template_preview_context",
    "build_template_preview_description",
    "build_template_preview_groups",
    "build_template_summary_lines",
    "template_preview_coverage_labels",
]
