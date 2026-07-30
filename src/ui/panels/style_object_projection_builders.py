"""Style-object builders for template editing and execution receipts."""

from __future__ import annotations

from src.config.template import StyleConfig, TemplateConfig
from src.shared.ui.style_object_projection import StyleObjectProjection
from src.shared.ui.style_owner_state import template_body_style_owner_state
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.panels.template_summary_projection import (
    build_template_detail_summary_items,
)


def build_template_body_style_projection(
    template: TemplateConfig | None,
    style: StyleConfig | None,
    *,
    scene=None,
) -> StyleObjectProjection:
    del scene
    if template is None or style is None:
        summary_items = (
            SummaryGridItem(
                key="empty",
                label="当前状态",
                value="未选择模板。",
                detail="",
                column_span=12,
            ),
        )
    else:
        summary_items = build_template_detail_summary_items(template, "tpl_style")
    return StyleObjectProjection.from_owner_state(
        kind="template_body_style",
        object_label="正文排版",
        owner_state=template_body_style_owner_state(style),
        summary_items=summary_items,
    )


def build_execution_style_projection(
    *,
    style_source_envelope: StylePresentationEnvelope | object | None = None,
    style_source_summary: str = "",
) -> StyleObjectProjection:
    receipt = _effective_execution_receipt_envelope(
        style_source_envelope,
        style_source_summary,
    )
    return StyleObjectProjection(
        kind="execution_style",
        object_label="样式回执",
        source_label="本次使用",
        scope_label="执行结果",
        edit_state_label="只读",
        receipt=receipt if not receipt.is_empty() else None,
    )


def _effective_execution_receipt_envelope(
    envelope: StylePresentationEnvelope | object | None,
    summary: str,
) -> StylePresentationEnvelope:
    presentation = StylePresentationEnvelope.from_object(
        envelope,
        kind="execution_receipt",
    )
    if presentation.receipt_summary(title_fallback="样式来源"):
        return presentation
    return StylePresentationEnvelope.from_summary(
        summary,
        kind="execution_receipt",
        title="样式来源",
    )


__all__ = [
    "build_execution_style_projection",
    "build_template_body_style_projection",
]
