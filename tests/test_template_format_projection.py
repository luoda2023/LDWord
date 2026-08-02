from __future__ import annotations

from src.config.builtin_templates import create_builtin_template
from src.config.resolver import resolve_template_baseline
from src.modules.registry import create_all_modules
from src.pipeline.module_selection import build_module_selection_plan
from src.shared.ui.icons.catalog import get_icon_names
from src.ui.panels.template_feature_specs import (
    TEMPLATE_CARD_DEFINITIONS,
    TEMPLATE_DETAIL_CARD_IDS,
    TEMPLATE_FEATURE_SPECS,
    feature_module_names,
)
from src.ui.panels.template_navigation_context import (
    build_template_navigation_context,
)
from src.ui.panels.template_overview_projection import (
    build_template_overview_projection,
)
from src.ui.panels.template_preview.model import TemplatePreviewMode


def _baseline_projection(template_id: str = "thesis_gbt"):
    template = create_builtin_template(template_id)
    resolved = resolve_template_baseline(template)
    modules = create_all_modules()
    selection = build_module_selection_plan(
        modules,
        is_requested=lambda name: next(
            module.meta.enabled_by_default
            for module in modules
            if module.meta.name == name
        ),
    )
    return build_template_overview_projection(
        resolved,
        selection,
        mode=TemplatePreviewMode.TEMPLATE_BASELINE,
    )


def test_feature_registry_covers_template_preview_identity_once():
    assert {section for spec in TEMPLATE_FEATURE_SPECS for section in spec.config_sections} == {
        "page_setup",
        "section",
        "styles",
        "heading_numbering",
        "heading_model",
        "table",
        "header_footer",
        "toc",
        "caption",
    }
    assert tuple(spec.card_id for spec in TEMPLATE_FEATURE_SPECS) == TEMPLATE_DETAIL_CARD_IDS
    assert len({spec.feature_id for spec in TEMPLATE_FEATURE_SPECS}) == len(TEMPLATE_FEATURE_SPECS)
    assert len(
        {
            module_name
            for spec in TEMPLATE_FEATURE_SPECS
            for module_name in feature_module_names(spec)
        }
    ) == 8


def test_overview_projection_exposes_registry_order_and_real_summaries():
    projection = _baseline_projection()
    summaries = {feature.feature_id: feature.summary for feature in projection.features}

    assert tuple(feature.card_id for feature in projection.features) == TEMPLATE_DETAIL_CARD_IDS
    assert "3.8" in summaries["page"]
    assert "宋体" in summaries["style"]
    assert "页码" in summaries["header_footer"]
    assert "目录" in summaries["toc"]
    assert "智能布局" in summaries["table"]
    assert "章节编号" in summaries["caption"]


def test_navigation_context_uses_registry_coverage_and_card_ids():
    context = build_template_navigation_context(
        scene_label="论文排版",
        template_label="GB/T 7713 学位论文 (thesis_gbt)",
    )

    assert context.coverage_labels == tuple(
        spec.action_label for spec in TEMPLATE_FEATURE_SPECS
    )
    assert context.detail_card_ids == TEMPLATE_DETAIL_CARD_IDS
    assert context.action == "核对页面、正文、标题、表格、页眉页脚、目录和题注"
    assert context.detail == "方案：论文排版；模板：GB/T 7713 学位论文 (thesis_gbt)"


def test_template_registry_icons_are_registered():
    registered = set(get_icon_names())
    assert all(icon in registered for _title, icon in TEMPLATE_CARD_DEFINITIONS.values())
