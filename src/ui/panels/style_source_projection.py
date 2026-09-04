"""Template-only style-source projections."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


@dataclass(frozen=True)
class StyleSourceActionSpec:
    label: str
    target_card_id: str


@dataclass(frozen=True)
class StyleSourceProjection:
    template_label: str
    status_label: str
    summary: str
    primary_action: StyleSourceActionSpec
    template_action_summary: str = ""


def build_style_source_projection(
    scene: SceneWorkspace,
    *,
    template: TemplateConfig | None = None,
    template_label: str = "",
    template_preview_action: str = "",
    template_target_card_id: str = "tpl_overview",
) -> StyleSourceProjection:
    label = _display_text(_template_label(scene, template, template_label))
    action = _display_text(template_preview_action)
    return StyleSourceProjection(
        template_label=label,
        template_action_summary=action,
        status_label="模板",
        summary=f"模板：{label}",
        primary_action=StyleSourceActionSpec("看模板", template_target_card_id),
    )


def build_template_style_source_projection(
    template: TemplateConfig,
    *,
    template_label: str = "",
    target_card_id: str = "tpl_style",
) -> StyleSourceProjection:
    label = (
        _clean(template_label)
        or _clean(getattr(template, "name", ""))
        or "当前模板"
    )
    return StyleSourceProjection(
        template_label=label,
        template_action_summary="样式基线",
        status_label="模板基线",
        summary=f"模板：{label}",
        primary_action=StyleSourceActionSpec("编辑正文", target_card_id),
    )


def _template_label(
    scene: SceneWorkspace,
    template: TemplateConfig | None,
    explicit: str,
) -> str:
    return (
        _clean(explicit)
        or _clean(getattr(template, "name", ""))
        or _clean(getattr(scene, "template_id", ""))
        or "当前模板"
    )


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _display_text(value: object) -> str:
    text = _clean(value).replace(" / ", "、")
    for source, target in (
        ("preset_final_schema", "最终资料规则"),
        ("OOXML 对象", "Word 对象"),
        ("OOXML", "Word 对象"),
    ):
        text = text.replace(source, target)
    return text.replace("_", " ")


__all__ = [
    "StyleSourceActionSpec",
    "StyleSourceProjection",
    "build_style_source_projection",
    "build_template_style_source_projection",
]
