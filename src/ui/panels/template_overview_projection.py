"""Single pure projection consumed by the template overview surface."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.config.resolved import ResolvedConfig
from src.pipeline.module_selection import ModuleSelectionPlan
from src.ui.panels.template_feature_specs import TEMPLATE_FEATURE_SPECS
from src.ui.panels.template_preview.model import (
    PreviewBlockKind,
    PreviewTextStyle,
    TemplatePreviewMode,
    TemplatePreviewBlock,
    TemplatePreviewProjection,
)
from src.ui.panels.template_preview.projector import (
    build_template_preview_projection,
)
from src.ui.panels.template_summary_projection import (
    all_template_detail_summaries,
)


@dataclass(frozen=True, slots=True)
class TemplateFeatureSummaryProjection:
    feature_id: str
    card_id: str
    nav_label: str
    icon_name: str
    summary: str
    field_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemplateOverviewProjection:
    features: tuple[TemplateFeatureSummaryProjection, ...]
    preview: TemplatePreviewProjection
    coverage_labels: tuple[str, ...]


def build_template_overview_projection(
    summary_config: ResolvedConfig,
    selection: ModuleSelectionPlan | None = None,
    *,
    mode: TemplatePreviewMode,
    preview_config: ResolvedConfig | None = None,
) -> TemplateOverviewProjection:
    preview = build_template_preview_projection(
        preview_config or summary_config,
        selection,
        mode=mode,
    )
    summary_by_card = {
        summary.detail_card_id: summary
        for summary in all_template_detail_summaries(summary_config)
    }
    expected_cards = {feature.card_id for feature in TEMPLATE_FEATURE_SPECS}
    if set(summary_by_card) != expected_cards:
        missing = sorted(expected_cards - set(summary_by_card))
        extra = sorted(set(summary_by_card) - expected_cards)
        raise ValueError(
            f"Template summary registry mismatch; missing={missing}, extra={extra}"
        )

    features = tuple(
        TemplateFeatureSummaryProjection(
            feature_id=feature.feature_id,
            card_id=feature.card_id,
            nav_label=feature.nav_label,
            icon_name=feature.icon_name,
            summary=summary_by_card[feature.card_id].nav_summary,
            field_names=feature.config_sections,
        )
        for feature in TEMPLATE_FEATURE_SPECS
    )
    return TemplateOverviewProjection(
        features=features,
        preview=preview,
        coverage_labels=tuple(feature.action_label for feature in TEMPLATE_FEATURE_SPECS),
    )


def build_template_overview_failure_projection(
    summary_config: ResolvedConfig,
    selection: ModuleSelectionPlan | None = None,
    *,
    mode: TemplatePreviewMode,
) -> TemplateOverviewProjection:
    """Build a visible safe state when the coordinator cannot resolve config."""
    base_preview = build_template_preview_projection(
        ResolvedConfig(),
        selection,
        mode=mode,
    )
    preview = replace(
        base_preview,
        page_geometry=replace(
            base_preview.page_geometry,
            paper_label="",
            neutral=True,
        ),
        show_page_guides=False,
        show_header_distance_guide=False,
        show_footer_distance_guide=False,
        blocks=(
            TemplatePreviewBlock(
                kind=PreviewBlockKind.EMPTY_STATE,
                text="预览暂不可用，请检查当前模板或方案配置",
                style=PreviewTextStyle(size_pt=10.5, alignment="center"),
                alignment="center",
            ),
        ),
        status_text="预览暂不可用；模板参数仍可编辑",
        accessible_description="模板样式预览暂不可用；模板参数仍可编辑",
    )
    summary_by_card = {
        summary.detail_card_id: summary
        for summary in all_template_detail_summaries(summary_config)
    }
    features = tuple(
        TemplateFeatureSummaryProjection(
            feature_id=feature.feature_id,
            card_id=feature.card_id,
            nav_label=feature.nav_label,
            icon_name=feature.icon_name,
            summary=summary_by_card[feature.card_id].nav_summary,
            field_names=feature.config_sections,
        )
        for feature in TEMPLATE_FEATURE_SPECS
    )
    return TemplateOverviewProjection(
        features=features,
        preview=preview,
        coverage_labels=tuple(
            feature.action_label for feature in TEMPLATE_FEATURE_SPECS
        ),
    )


__all__ = [
    "TemplateFeatureSummaryProjection",
    "TemplateOverviewProjection",
    "build_template_overview_failure_projection",
    "build_template_overview_projection",
]
