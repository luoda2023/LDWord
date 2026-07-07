"""Build report-ready style-source summaries from template and scene state."""

from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.config.style_difference_projection import (
    StyleDifferenceProjection,
    build_scene_style_difference_projections,
)
from src.config.template import TemplateConfig


def build_style_source_report_summary(
    scene: SceneWorkspace,
    template: TemplateConfig | None,
    *,
    template_label: str = "",
) -> dict[str, object]:
    """Return a JSON/Markdown friendly summary of effective style sources."""

    label = _template_label(scene, template, template_label=template_label)
    differences = build_scene_style_difference_projections(
        scene,
        template,
        overridden_only=True,
    )
    sections = [_difference_payload(item) for item in differences]
    independent_count = len(differences)
    changed_count = sum(1 for item in differences if item.has_changed_fields)
    summary = _summary_text(label, differences)
    section_status = (
        "无格式例外"
        if independent_count <= 0
        else f"{independent_count} 个格式例外"
    )
    return {
        "template_label": label,
        "summary": summary,
        "section_status": section_status,
        "independent_section_count": independent_count,
        "changed_section_count": changed_count,
        "sections": sections,
    }


def _difference_payload(item: StyleDifferenceProjection) -> dict[str, object]:
    return {
        "variant_key": item.variant_key,
        "label": item.scope_label,
        "status": item.status_label,
        "current_status": item.current_status,
        "difference_status": item.difference_status,
        "detail": item.detail,
        "detail_label": item.detail_label,
        "compact_label": item.compact_label,
        "changed_labels": list(item.changed_labels),
        "changed_count": item.changed_count,
        "follows_template": item.follows_template,
        "overridden": item.overridden,
    }


def _summary_text(
    template_label: str,
    differences: tuple[StyleDifferenceProjection, ...],
) -> str:
    base = f"本次按模板“{template_label}”处理"
    if not differences:
        return f"{base}；无格式例外。"
    labels = "、".join(item.source_line_label for item in differences[:3])
    suffix = "等" if len(differences) > 3 else ""
    return f"{base}；{labels}{suffix}使用场景格式例外。"


def _template_label(
    scene: SceneWorkspace,
    template: TemplateConfig | None,
    *,
    template_label: str = "",
) -> str:
    return (
        str(template_label or "").strip()
        or str(getattr(template, "name", "") or "").strip()
        or str(
            getattr(scene, "template_id", "")
            or getattr(scene, "default_template_id", "")
            or ""
        ).strip()
        or "当前模板"
    )


__all__ = ["build_style_source_report_summary"]
