"""Navigation copy derived from the single template feature registry."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.ui.panels.template_feature_specs import TEMPLATE_FEATURE_SPECS


@dataclass(frozen=True, slots=True)
class TemplateNavigationContext:
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


def _cn_join(values: Sequence[str]) -> str:
    labels = tuple(str(value or "").strip() for value in values if str(value or "").strip())
    if len(labels) < 2:
        return labels[0] if labels else ""
    return "、".join(labels[:-1]) + "和" + labels[-1]


def build_template_navigation_context(
    *,
    scene_label: str = "",
    template_label: str = "",
    detail: str = "",
    title: str = "来自方案：核对模板与样式",
) -> TemplateNavigationContext:
    coverage = tuple(feature.action_label for feature in TEMPLATE_FEATURE_SPECS)
    explicit_detail = str(detail or "").strip()
    if explicit_detail:
        detail_text = explicit_detail
    else:
        parts = []
        if str(scene_label or "").strip():
            parts.append(f"方案：{str(scene_label).strip()}")
        if str(template_label or "").strip():
            parts.append(f"模板：{str(template_label).strip()}")
        detail_text = "；".join(parts)
    joined = _cn_join(coverage)
    return TemplateNavigationContext(
        title=title,
        detail=detail_text,
        action=f"核对{joined}" if joined else "核对模板预览",
        coverage_labels=coverage,
        detail_card_ids=tuple(feature.card_id for feature in TEMPLATE_FEATURE_SPECS),
    )


__all__ = ["TemplateNavigationContext", "build_template_navigation_context"]
