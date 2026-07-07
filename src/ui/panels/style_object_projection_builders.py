"""Builders for unified style-object projections used by panel surfaces."""

from __future__ import annotations

from collections.abc import Sequence

from src.config.style_variant_semantics import STYLE_VARIANTS
from src.config.template import StyleConfig, TemplateConfig
from src.config.style_difference_projection import (
    build_style_difference_summary_projection,
)
from src.shared.ui.style_object_projection import StyleObjectProjection
from src.shared.ui.style_owner_state import (
    scene_section_style_owner_state,
    template_body_style_owner_state,
)
from src.shared.ui.style_policy_control_deck import (
    StylePolicyActionProjection,
    StylePolicyProjection,
    StylePolicyToggleProjection,
)
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.panels.scene_style_override_service import (
    scene_section_effective_style,
    scene_section_style_comparison_projection,
    scene_section_style_override_projection,
    scene_section_style_preview_projection,
    scene_style_variants_for_scene,
)
from src.ui.panels.scene_summary_projection import build_scene_style_override_summary_items
from src.ui.panels.style_source_projection import build_style_source_projection
from src.ui.panels.template_summary_projection import build_template_detail_summary_items


def build_template_body_style_projection(
    template: TemplateConfig | None,
    style: StyleConfig | None,
    *,
    scene=None,
) -> StyleObjectProjection:
    """Build the shared style-object projection for template body editing."""

    if template is None or style is None:
        summary_items = (
            SummaryGridItem(
                key="empty",
                label="当前状态",
                value="未选择模板。",
                detail="选择模板后，这里会汇总字体、缩进和行距等正文排版信息。",
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


def build_scene_section_style_projection(
    scene,
    template: TemplateConfig | None,
    variant_key: str,
    *,
    empty_preview_text: str = "选择分区后预览样式",
    summary_variants: Sequence | None = None,
    restore_all_labels: Sequence[str] | None = None,
    undo_restore_all_labels: Sequence[str] = (),
) -> StyleObjectProjection:
    """Build the shared style-object projection for one scene section style."""

    key = str(variant_key or "").strip()
    if scene is None or not key:
        return StyleObjectProjection.from_owner_state(
            kind="scene_section_style",
            object_label="",
            owner_state=scene_section_style_owner_state(
                style=None,
                variant_label="",
                section_enabled=False,
                overridden=False,
            ),
            summary_items=build_scene_style_override_summary_items(
                scene,
                None,
                variants=summary_variants,
            ),
            policy=build_scene_section_style_policy_projection(
                scene,
                template,
                key,
                variants=summary_variants,
                restore_all_labels=restore_all_labels,
                undo_restore_all_labels=undo_restore_all_labels,
            ),
            empty_preview_text=empty_preview_text,
        )

    override_projection = scene_section_style_override_projection(scene, template, key)
    preview_projection = scene_section_style_preview_projection(scene, template, key)
    comparison_projection = scene_section_style_comparison_projection(
        scene,
        template,
        key,
    )
    effective_style = scene_section_effective_style(scene, template, key)
    variant_label = _variant_label(key, fallback=getattr(override_projection, "label", ""))
    owner_state = scene_section_style_owner_state(
        style=effective_style,
        projection=override_projection,
        variant_label=variant_label,
        section_enabled=bool(getattr(override_projection, "section_enabled", False)),
        overridden=bool(getattr(override_projection, "overridden", False)),
    )

    return StyleObjectProjection.from_owner_state(
        kind="scene_section_style",
        object_label=variant_label,
        owner_state=owner_state,
        summary_items=build_scene_style_override_summary_items(
            scene,
            override_projection,
            variants=summary_variants,
        ),
        preview_projection=preview_projection,
        difference=comparison_projection,
        policy=build_scene_section_style_policy_projection(
            scene,
            template,
            key,
            variants=summary_variants,
            restore_all_labels=restore_all_labels,
            undo_restore_all_labels=undo_restore_all_labels,
        ),
        empty_preview_text=empty_preview_text,
    )


def build_scene_section_style_policy_projection(
    scene,
    template: TemplateConfig | None,
    variant_key: str,
    *,
    variants: Sequence | None = None,
    restore_all_labels: Sequence[str] | None = None,
    undo_restore_all_labels: Sequence[str] = (),
) -> StylePolicyProjection:
    """Build the rule-control policy used by scene section style surfaces."""

    selected_key = str(variant_key or "").strip()
    toggles: list[StylePolicyToggleProjection] = []
    overridden_labels: list[str] = []
    style_variants = (
        tuple(variants)
        if variants is not None
        else scene_style_variants_for_scene(scene, template)
    )

    for variant in style_variants:
        override = (
            scene_section_style_override_projection(scene, template, variant.key)
            if scene is not None
            else None
        )
        section_enabled = True
        overridden = bool(getattr(override, "overridden", False))
        if overridden:
            overridden_labels.append(variant.label)
        toggles.append(
            StylePolicyToggleProjection(
                key=variant.key,
                label=variant.label,
                checked=overridden,
                visible=True,
                tooltip=_scene_policy_toggle_tooltip(
                    variant.label,
                    section_enabled=section_enabled,
                    overridden=overridden,
                ),
            )
        )

    restore_labels = (
        tuple(overridden_labels)
        if restore_all_labels is None
        else _clean_names(restore_all_labels)
    )
    undo_labels = _clean_names(undo_restore_all_labels)
    difference = (
        scene_section_style_comparison_projection(scene, template, selected_key)
        if scene is not None and selected_key
        else None
    )
    return StylePolicyProjection(
        kind="scene_section_style",
        title="分区",
        toggles=tuple(toggles),
        difference=difference,
        restore_all=StylePolicyActionProjection(
            label="全部跟随模板",
            enabled=bool(restore_labels),
            labels=restore_labels,
        ),
        undo_restore_all=StylePolicyActionProjection(
            label="撤销恢复",
            enabled=bool(undo_labels),
            labels=undo_labels,
        ),
    )


def build_execution_style_projection(
    *,
    style_source_envelope: StylePresentationEnvelope | object | None = None,
    style_source_summary: str = "",
    difference=None,
) -> StyleObjectProjection:
    """Build the shared style-object projection for execution style receipts."""

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
        difference=difference,
        receipt=receipt if not receipt.is_empty() else None,
    )


def build_execution_prereview_style_projection(
    scene,
    template: TemplateConfig | None,
    *,
    template_label: str = "",
) -> StyleObjectProjection:
    """Build the style projection used by execution prereview surfaces."""

    source_projection = build_style_source_projection(
        scene,
        template=template,
        template_label=template_label,
        view_mode="execution_review",
    )
    difference = build_style_difference_summary_projection(
        tuple(getattr(source_projection, "section_differences", ()) or ())
    )
    return StyleObjectProjection(
        kind="execution_prereview_style",
        object_label="执行前复核",
        source_label=source_projection.status_label,
        scope_label=source_projection.section_status_label,
        edit_state_label="只读",
        source=source_projection,
        difference=difference,
    )


def _effective_execution_receipt_envelope(
    envelope: StylePresentationEnvelope | object | None,
    summary: str = "",
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


def _variant_label(variant_key: str, *, fallback: str = "") -> str:
    key = str(variant_key or "").strip()
    for variant in STYLE_VARIANTS:
        if variant.key == key:
            return variant.label
    return str(fallback or key).strip()


def _scene_policy_toggle_tooltip(
    label: str,
    *,
    section_enabled: bool,
    overridden: bool,
) -> str:
    clean_label = str(label or "例外").strip()
    if overridden:
        return f"已为「{clean_label}」添加格式例外。"
    return f"默认跟随模板；需要局部不同时再添加「{clean_label}」例外。"


def _clean_names(labels: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        str(label or "").strip() for label in labels if str(label or "").strip()
    )


__all__ = [
    "build_execution_prereview_style_projection",
    "build_execution_style_projection",
    "build_scene_section_style_policy_projection",
    "build_scene_section_style_projection",
    "build_template_body_style_projection",
]
