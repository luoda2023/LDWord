"""Domain registry for template-management features.

This registry owns template navigation and module-control identity.  It must
never import or describe preview/view-model types: styles and execution policy
are the source of truth, while preview is only one consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ModuleControlSpec:
    module_name: str
    label: str
    status_label: str
    linked_module_names: tuple[str, ...] = ()

    @property
    def module_names(self) -> tuple[str, ...]:
        """Return every backend module governed by this visible control."""

        return (self.module_name, *self.linked_module_names)


@dataclass(frozen=True, slots=True)
class TemplateFeatureSpec:
    feature_id: str
    card_id: str
    title: str
    nav_label: str
    icon_name: str
    config_sections: tuple[str, ...]
    module_controls: tuple[ModuleControlSpec, ...]
    action_label: str
    show_execution_badge: bool = True


TEMPLATE_FEATURE_SPECS: tuple[TemplateFeatureSpec, ...] = (
    TemplateFeatureSpec(
        "page",
        "tpl_page",
        "页面设置",
        "页面",
        "ruler",
        ("page_setup", "section"),
        (
            ModuleControlSpec(
                "page_setup",
                "应用页面设置",
                "页面设置",
                ("section_format",),
            ),
        ),
        "页面",
    ),
    TemplateFeatureSpec(
        "style",
        "tpl_style",
        "正文排版",
        "排版",
        "type-outline",
        ("styles",),
        (ModuleControlSpec("paragraph_style", "应用正文与标题样式", "正文排版"),),
        "正文",
    ),
    TemplateFeatureSpec(
        "heading",
        "tpl_heading",
        "标题编号",
        "标题",
        "list-ordered",
        ("heading_numbering", "heading_model"),
        (ModuleControlSpec("heading_numbering", "应用标题编号", "标题编号"),),
        "标题",
    ),
    TemplateFeatureSpec(
        "table",
        "tpl_table",
        "表格",
        "表格",
        "table-2",
        ("table",),
        (ModuleControlSpec("table_format", "应用表格格式", "表格"),),
        "表格",
    ),
    TemplateFeatureSpec(
        "header_footer",
        "tpl_header_footer",
        "页眉与页脚",
        "页眉与页脚",
        "panel-top",
        ("header_footer",),
        (ModuleControlSpec("header_footer", "应用页眉与页脚", "页眉页脚"),),
        "页眉页脚",
    ),
    TemplateFeatureSpec(
        "toc",
        "tpl_toc",
        "目录",
        "目录",
        "chart-no-axes-gantt",
        ("toc",),
        (ModuleControlSpec("toc", "生成或更新目录", "目录"),),
        "目录",
    ),
    TemplateFeatureSpec(
        "caption",
        "tpl_caption",
        "题注",
        "题注",
        "waves-arrow-down",
        ("caption", "styles"),
        (ModuleControlSpec("caption", "应用图表题注", "题注"),),
        "题注",
    ),
)

TEMPLATE_FEATURE_BY_ID = {
    spec.feature_id: spec for spec in TEMPLATE_FEATURE_SPECS
}
TEMPLATE_FEATURE_BY_CARD_ID = {
    spec.card_id: spec for spec in TEMPLATE_FEATURE_SPECS
}
TEMPLATE_CARD_ORDER = (
    "tpl_overview",
    *(spec.card_id for spec in TEMPLATE_FEATURE_SPECS),
)
TEMPLATE_DETAIL_CARD_IDS = tuple(
    spec.card_id for spec in TEMPLATE_FEATURE_SPECS
)

TEMPLATE_CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    "tpl_overview": ("模板概览", "scan-text"),
    **{
        spec.card_id: (spec.title, spec.icon_name)
        for spec in TEMPLATE_FEATURE_SPECS
    },
}


def module_control_spec(module_name: str) -> ModuleControlSpec | None:
    target = str(module_name or "")
    for feature in TEMPLATE_FEATURE_SPECS:
        for control in feature.module_controls:
            if target in control.module_names:
                return control
    return None


def feature_module_names(feature: TemplateFeatureSpec) -> tuple[str, ...]:
    """Flatten the backend modules owned by a feature in stable order."""

    return tuple(
        dict.fromkeys(
            module_name
            for control in feature.module_controls
            for module_name in control.module_names
        )
    )


def module_control_switch_updates(
    module_name: str,
    enabled: bool,
) -> dict[str, bool]:
    """Build the atomic switch update represented by one visible control."""

    control = module_control_spec(module_name)
    governed_names = control.module_names if control is not None else (str(module_name),)
    return {name: bool(enabled) for name in governed_names if name}


__all__ = [
    "ModuleControlSpec",
    "TEMPLATE_CARD_DEFINITIONS",
    "TEMPLATE_CARD_ORDER",
    "TEMPLATE_DETAIL_CARD_IDS",
    "TEMPLATE_FEATURE_BY_CARD_ID",
    "TEMPLATE_FEATURE_BY_ID",
    "TEMPLATE_FEATURE_SPECS",
    "TemplateFeatureSpec",
    "feature_module_names",
    "module_control_switch_updates",
    "module_control_spec",
]
