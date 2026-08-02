"""Runtime-only enablement projection for workbench execution resources."""

from __future__ import annotations

import copy

from src.config.migration import get_default_module_switches
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


DISABLED_SELECTOR_VALUE = "__disabled__"
DISABLED_SELECTOR_LABEL = "不启用"
DISABLED_SELECTOR_SOURCE_TYPE = "disabled"

_RUNTIME_PLAN_ENABLED_ATTRIBUTE = "_runtime_plan_enabled"

# These modules consume the selected template's appearance baseline.  Turning
# the template off must prevent the fallback TemplateConfig defaults from
# silently formatting the document.
TEMPLATE_CONTROLLED_MODULES = frozenset(
    {
        "page_setup",
        "section_format",
        "paragraph_style",
        "header_footer",
        "heading_numbering",
        "toc",
        "caption",
        "table_format",
        "figure_table_center",
        "watermark",
        "equation_table_format",
        "reference_format",
    }
)

MATERIAL_CONTROLLED_MODULES = frozenset(
    {
        "entity_fill",
        "source_fill",
        "placeholder_replace",
        "image_insertion",
    }
)


def execution_plan_is_enabled(scene: object | None) -> bool:
    """Return whether the runtime scene is allowed to execute plan behavior."""

    return bool(
        getattr(scene, _RUNTIME_PLAN_ENABLED_ATTRIBUTE, True)
    )


def project_execution_scene(
    scene: SceneWorkspace | None,
    *,
    plan_enabled: bool = True,
    template_enabled: bool = True,
    material_enabled: bool = True,
) -> SceneWorkspace:
    """Build an execution-only scene with independently disabled feature owners."""

    projected = copy.deepcopy(
        scene if isinstance(scene, SceneWorkspace) else SceneWorkspace()
    )
    setattr(
        projected,
        _RUNTIME_PLAN_ENABLED_ATTRIBUTE,
        bool(plan_enabled),
    )

    switches = dict(projected.module_switches or {})
    if not plan_enabled:
        neutral = SceneWorkspace()
        all_module_names = {
            *get_default_module_switches(),
            *switches,
        }
        switches = {name: False for name in all_module_names}
        projected.name = DISABLED_SELECTOR_LABEL
        projected.description = "运行时已关闭处理方案。"
        projected.document_scope = copy.deepcopy(neutral.document_scope)
        projected.input_source_profile = copy.deepcopy(
            neutral.input_source_profile
        )
        projected.compliance_profile = copy.deepcopy(
            neutral.compliance_profile
        )
        projected.default_delivery_preset_id = (
            neutral.default_delivery_preset_id
        )
        projected.delivery_presets = copy.deepcopy(
            neutral.delivery_presets
        )
        projected.exam_paper = copy.deepcopy(neutral.exam_paper)
        projected.template_overrides = {}
        projected.batch_preset = None
        projected.strict_mode = False
        projected.compliance_profile.enabled_checks = []
        projected.compliance_profile.object_preflight.enabled = False
    elif not template_enabled:
        for module_name in TEMPLATE_CONTROLLED_MODULES:
            switches[module_name] = False

    if not material_enabled:
        for module_name in MATERIAL_CONTROLLED_MODULES:
            switches[module_name] = False

    projected.module_switches = switches

    if not plan_enabled or not material_enabled:
        profile = projected.input_source_profile
        profile.require_material_package = False
        profile.material_schema_id = ""
        profile.material_schema_ids = []
        profile.required_material_fields = []
        profile.required_image_roles = []
        for preset in projected.delivery_presets:
            preset.content_visibility_rules = []

    if not plan_enabled or not template_enabled:
        projected.template_overrides = {}
        for preset in projected.delivery_presets:
            preset.target_template_id = ""

    return projected


def project_execution_template(
    template: TemplateConfig | None,
    *,
    enabled: bool = True,
) -> TemplateConfig:
    """Return the selected template or a neutral baseline for disabled execution."""

    if enabled and isinstance(template, TemplateConfig):
        return copy.deepcopy(template)
    if enabled:
        return TemplateConfig()
    return TemplateConfig(
        name=DISABLED_SELECTOR_LABEL,
        description="运行时已关闭模板排版。",
    )


__all__ = [
    "DISABLED_SELECTOR_LABEL",
    "DISABLED_SELECTOR_SOURCE_TYPE",
    "DISABLED_SELECTOR_VALUE",
    "MATERIAL_CONTROLLED_MODULES",
    "TEMPLATE_CONTROLLED_MODULES",
    "execution_plan_is_enabled",
    "project_execution_scene",
    "project_execution_template",
]
