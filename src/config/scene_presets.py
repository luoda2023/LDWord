"""
Scene / Template presets — 方案与模板预设

连接 UI 层和真实配置模型 (config/scene.py + config/template.py)。

核心概念:
- UICapabilityGroup: 纯 UI 分组，将 module_switches 聚合为用户可理解的能力域开关
- SceneMeta: 场景元信息（UI 展示用），关联一个 SceneWorkspace 工厂
- TemplateMeta: 模板元信息（UI 展示用），关联一个 TemplateConfig 工厂
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module

from src.config.builtin_scenes import (
    create_builtin_scene,
    list_builtin_scene_resources,
)
from src.config.document_scope import (
    coerce_document_scope_policy,
    document_scope_role_label,
)
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


# ---------------------------------------------------------------------------
# UI Capability Group — 纯展示层分组
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class UICapabilityGroup:
    """将多个 module_switches 聚合为一个用户可见的能力开关。"""
    group_id: str
    label: str
    description: str
    module_names: tuple[str, ...]   # 对应 module_switches 中的 key


# 核心排版（始终 ON，不在 UI 显示开关）
CORE_MODULES: tuple[str, ...] = (
    "page_setup",
    "section_format",
    "paragraph_style",
    "heading_recognition",
    "heading_numbering",
)

# 用户可控的执行能力。能力组只决定运行时是否执行对应处理；
# 具体外观基线仍由当前模板负责。
UI_CAPABILITY_GROUPS: tuple[UICapabilityGroup, ...] = (
    UICapabilityGroup(
        group_id="table_chart",
        label="图表处理",
        description="表格处理·题注补齐·图表居中·续表，外观跟随模板",
        module_names=("table_format", "caption", "figure_table_center"),
    ),
    UICapabilityGroup(
        group_id="citation",
        label="引用处理",
        description="引用链接·参考条目编号·上标跟随，文献样式跟随模板",
        module_names=("reference_format", "citation_link"),
    ),
    UICapabilityGroup(
        group_id="content_fill",
        label="资料包填充",
        description="资料包输入·字段填入·占位符替换·图片插入·水印",
        module_names=(
            "entity_fill", "source_fill", "placeholder_replace",
            "image_insertion", "watermark",
        ),
    ),
)

UI_GROUP_MAP: dict[str, UICapabilityGroup] = {g.group_id: g for g in UI_CAPABILITY_GROUPS}

# Workbench cards are a product-navigation surface, not a mirror of every
# runtime capability group.  Material filling is configured by the canonical
# material-package panel and must never grow a second, partially functional
# Workbench destination merely because its execution modules are active.
_NON_WORKBENCH_CAPABILITY_GROUP_IDS = frozenset({"content_fill"})

CAPABILITY_FEATURE_CARD_ORDER: tuple[str, ...] = tuple(
    group.group_id
    for group in UI_CAPABILITY_GROUPS
    if group.group_id not in _NON_WORKBENCH_CAPABILITY_GROUP_IDS
)

CAPABILITY_FEATURE_CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    "table_chart": ("图表处理", "table"),
    "citation": ("引用处理", "book-open"),
}

LEGACY_FEATURE_GROUP_MAP: dict[str, str] = {
    "heading_numbering": "table_chart",
    "quick_fill": "content_fill",
}

LEGACY_FEATURE_CARD_ORDER: tuple[str, ...] = tuple(LEGACY_FEATURE_GROUP_MAP.keys())

LEGACY_FEATURE_CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    "heading_numbering": ("标题编号", "list-tree"),
    "quick_fill": ("内容填充", "database"),
}


def get_group_enabled(scene: SceneWorkspace, group: UICapabilityGroup) -> bool:
    """判断一个 UI 能力组在给定场景下是否启用（任一子模块 ON 即 ON）。"""
    return any(scene.module_switches.get(m, False) for m in group.module_names)


def set_group_enabled(scene: SceneWorkspace, group: UICapabilityGroup, enabled: bool) -> None:
    """批量设置一个 UI 能力组下所有模块的开关。"""
    for m in group.module_names:
        if m in scene.module_switches:
            scene.module_switches[m] = enabled


# ---------------------------------------------------------------------------
# Scene Meta — 场景元信息 + 工厂
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TemplateMeta:
    """模板在 UI 中的展示信息。"""
    template_id: str
    name: str
    mode_id: str = ""

    def create_template(self) -> TemplateConfig:
        """Materialize the full built-in TemplateConfig for this template id."""
        from src.config.builtin_templates import create_builtin_template

        return create_builtin_template(
            self.template_id,
            mode_id=self.mode_id or None,
        )


@dataclass(frozen=True, slots=True)
class SceneMeta:
    """场景在 UI 中的展示信息。"""
    scene_id: str
    name: str
    description: str
    template_id: str
    compatible_templates: tuple[TemplateMeta, ...]
    display_order: int = 0


# ---------------------------------------------------------------------------
# Canonical plan resources
# ---------------------------------------------------------------------------


def create_custom_scene() -> SceneWorkspace:
    return create_builtin_scene("custom", mode_id="custom")


def create_exam_scene() -> SceneWorkspace:
    return create_builtin_scene("exam", mode_id="exam")


def create_exam_quiz_scene() -> SceneWorkspace:
    return create_builtin_scene("exam_quiz", mode_id="exam")


def create_exam_term_scene() -> SceneWorkspace:
    return create_builtin_scene("exam_term", mode_id="exam")


def create_thesis_scene() -> SceneWorkspace:
    return create_builtin_scene("thesis", mode_id="thesis")


def create_bidding_scene() -> SceneWorkspace:
    return create_builtin_scene("bidding", mode_id="bidding")


def create_official_scene() -> SceneWorkspace:
    return create_builtin_scene("official", mode_id="official")


def create_technical_scene() -> SceneWorkspace:
    return create_builtin_scene("technical", mode_id="technical")


def create_report_scene() -> SceneWorkspace:
    return create_builtin_scene("report", mode_id="report")


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

def _canonical_scene_metas() -> tuple[SceneMeta, ...]:
    """Project UI metadata from the same canonical plan/template JSON bytes."""

    from src.config.builtin_templates import create_builtin_template

    template_names: dict[tuple[str, str], str] = {}
    metas: list[SceneMeta] = []
    for mode_id, scene_id, _path in list_builtin_scene_resources():
        scene = create_builtin_scene(scene_id, mode_id=mode_id)
        compatible_templates: list[TemplateMeta] = []
        for template_id in scene.compatible_template_ids:
            key = (mode_id, template_id)
            if key not in template_names:
                template_names[key] = create_builtin_template(
                    template_id,
                    mode_id=mode_id,
                ).name
            compatible_templates.append(
                TemplateMeta(
                    template_id=template_id,
                    name=template_names[key],
                    mode_id=mode_id,
                )
            )
        metas.append(
            SceneMeta(
                scene_id=scene.scene_id,
                name=scene.name,
                description=scene.description,
                template_id=scene.template_id,
                compatible_templates=tuple(compatible_templates),
                display_order=scene.display_order,
            )
        )
    return tuple(metas)


# Public UI projections.  No plan content or labels are duplicated here.
SCENE_METAS: tuple[SceneMeta, ...] = _canonical_scene_metas()

SCENE_META_MAP: dict[str, SceneMeta] = {s.scene_id: s for s in SCENE_METAS}

# 场景工厂表
SCENE_FACTORIES: dict[str, callable] = {
    "custom": create_custom_scene,
    "exam": create_exam_scene,
    "exam_quiz": create_exam_quiz_scene,
    "exam_term": create_exam_term_scene,
    "thesis": create_thesis_scene,
    "bidding": create_bidding_scene,
    "official": create_official_scene,
    "technical": create_technical_scene,
    "report": create_report_scene,
}


def create_scene(scene_id: str) -> SceneWorkspace:
    """根据方案 ID 创建真实 SceneWorkspace 实例。"""
    factory = SCENE_FACTORIES.get(scene_id)
    if factory is None:
        raise ValueError(f"未知方案 ID: {scene_id}")
    return factory()


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def build_scene_summary(scene: SceneWorkspace) -> str:
    """从真实 SceneWorkspace 构建一行摘要。"""
    strategy_text = "重建编号" if scene.strict_mode else "保留原编号"
    scope_text = _scene_document_scope_summary(scene)

    enabled_groups = []
    for group in UI_CAPABILITY_GROUPS:
        if get_group_enabled(scene, group):
            enabled_groups.append(group.label)

    cap_count = len(enabled_groups)
    features_text = "·".join(enabled_groups) if enabled_groups else "无"
    return (
        f"{strategy_text} · 处理范围：{scope_text} · "
        f"{cap_count}项功能（{features_text}） · {build_scene_profile_summary(scene)}"
    )


def _scene_document_scope_summary(scene: SceneWorkspace) -> str:
    labels = {
        "all": "全部内容",
        "body": "仅正文",
    }
    scope = coerce_document_scope_policy(scene.document_scope)
    if scope.mode != "selected":
        return labels.get(scope.mode, "全部内容")
    roles = "、".join(document_scope_role_label(role) for role in scope.selected_roles)
    return f"自选区域：{roles}" if roles else "自选区域"


def build_scene_profile_summary(scene: SceneWorkspace) -> str:
    """Build a compact profile summary shared by Workbench scene surfaces."""
    input_formats = _join_summary_values(scene.input_source_profile.accepted_formats)
    compliance = scene.compliance_profile.profile_id or "basic"
    default_delivery = str(scene.default_delivery_preset_id or "").strip() or "未设置"
    extra_deliveries = max(0, len(scene.delivery_presets) - 1)
    delivery = (
        f"{default_delivery}+{extra_deliveries}"
        if extra_deliveries
        else default_delivery
    )
    preflight = scene.compliance_profile.object_preflight
    protection = "严格保护" if preflight.preservation_mode == "strict" else "提示保护"
    if not preflight.enabled:
        protection = "未预检"
    return f"输入 {input_formats} · 合规 {compliance} · 交付 {delivery} · {protection}"


def _join_summary_values(values: Sequence[object]) -> str:
    normalized = [str(value or "").strip() for value in values if str(value or "").strip()]
    return "/".join(normalized) if normalized else "无"


_ENGINEERING_SUMMARY_EXPORTS = {
    "build_scene_control_contract_summary",
    "build_scene_parameter_ownership_summary",
    "build_scene_product_readiness_summary",
    "build_scene_request_cell_summary_text",
    "build_scene_sample_coverage_summary_text",
}


def __getattr__(name: str):
    if name not in _ENGINEERING_SUMMARY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module("src.config.scene_engineering_summary")
    value = getattr(module, name)
    globals()[name] = value
    return value
