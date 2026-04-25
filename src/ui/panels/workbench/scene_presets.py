"""
Scene / Template presets — 场景与模板预设

连接 UI 层和真实配置模型 (config/scene.py + config/template.py)。

核心概念:
- UICapabilityGroup: 纯 UI 分组，将 19 个 module_switches 聚合为 6 个用户可理解的开关
- SceneMeta: 场景元信息（UI 展示用），关联一个 SceneWorkspace 工厂
- TemplateMeta: 模板元信息（UI 展示用），关联一个 TemplateConfig 工厂
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.scene import FormatScopeConfig, SceneWorkspace
from src.config.template import TemplateConfig
from src.config.feature_configs import TableConfig, OutputConfig


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
    "figure_table_center",   # 图表居中，核心基础功能
)

# 用户可控的 6 个能力组
UI_CAPABILITY_GROUPS: tuple[UICapabilityGroup, ...] = (
    UICapabilityGroup(
        group_id="table_chart",
        label="表格与图表",
        description="表格格式·题注编号·序号域·续表",
        module_names=("table_format", "caption"),
    ),
    UICapabilityGroup(
        group_id="page_elements",
        label="页面元素",
        description="页眉·页脚·页码·目录·图表目录",
        module_names=("header_footer", "toc"),
    ),
    UICapabilityGroup(
        group_id="formula",
        label="公式规范",
        description="公式转换·表格排版·编号·格式统一",
        module_names=("equation_table_format", "chem_typography"),
    ),
    UICapabilityGroup(
        group_id="citation",
        label="参考文献",
        description="域关联·自动编号·上标跟随",
        module_names=("reference_format", "citation_link"),
    ),
    UICapabilityGroup(
        group_id="cleanup",
        label="校验与清理",
        description="Markdown修复·空白清洗·格式校验",
        module_names=("md_cleanup", "whitespace_normalize"),
    ),
    UICapabilityGroup(
        group_id="content_fill",
        label="内容与数据",
        description="实体档案填入·数据源填入·占位符替换·图片插入·水印",
        module_names=(
            "entity_fill", "source_fill", "placeholder_replace",
            "image_insertion", "watermark",
        ),
    ),
)

UI_GROUP_MAP: dict[str, UICapabilityGroup] = {g.group_id: g for g in UI_CAPABILITY_GROUPS}

CAPABILITY_FEATURE_CARD_ORDER: tuple[str, ...] = tuple(group.group_id for group in UI_CAPABILITY_GROUPS)

CAPABILITY_FEATURE_CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    "table_chart": ("表格与图表", "table"),
    "page_elements": ("页面元素", "layout"),
    "formula": ("公式规范", "sigma"),
    "citation": ("参考文献", "book-open"),
    "cleanup": ("校验与清理", "scan"),
    "content_fill": ("内容与数据", "pen-tool"),
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

    def create_template(self) -> TemplateConfig:
        """Materialize the full built-in TemplateConfig for this template id."""
        from src.config.builtin_templates import create_builtin_template

        return create_builtin_template(self.template_id)


@dataclass(frozen=True, slots=True)
class SceneMeta:
    """场景在 UI 中的展示信息。"""
    scene_id: str
    name: str
    description: str
    default_template_id: str
    compatible_templates: tuple[TemplateMeta, ...]


# ---------------------------------------------------------------------------
# Scene Factories — 生成真实 SceneWorkspace 实例
# ---------------------------------------------------------------------------

def _all_sections_on() -> dict[str, bool]:
    """所有文档分区默认全开。"""
    return {
        "body": True,
        "references": True,
        "errata": True,
        "acknowledgment": True,
        "appendix": True,
        "abstract_cn": True,
        "abstract_en": True,
        "toc": True,
        "resume": True,
    }


def _thesis_sections() -> dict[str, bool]:
    return {
        "body": True,
        "references": True,
        "acknowledgment": True,
        "abstract_cn": True,
        "abstract_en": True,
        "toc": True,
        "appendix": True,
        "errata": False,
        "resume": False,
    }


def _bidding_sections() -> dict[str, bool]:
    return {
        "body": True,
        "toc": True,
        "appendix": True,
        "references": False,
        "acknowledgment": False,
        "abstract_cn": False,
        "abstract_en": False,
        "errata": False,
        "resume": False,
    }


def _official_sections() -> dict[str, bool]:
    return {
        "body": True,
        "appendix": False,
        "references": False,
        "acknowledgment": False,
        "abstract_cn": False,
        "abstract_en": False,
        "toc": False,
        "errata": False,
        "resume": False,
    }


def _build_switches(
    *,
    table_chart: bool = True,
    page_elements: bool = True,
    formula: bool = False,
    citation: bool = False,
    cleanup: bool = True,
    content_fill: bool = False,
) -> dict[str, bool]:
    """从 6 个能力组开关生成完整的 module_switches 字典。"""
    switches: dict[str, bool] = {}

    # 核心模块始终 ON
    for m in CORE_MODULES:
        switches[m] = True

    # 按能力组展开
    group_mapping = {
        "table_chart": table_chart,
        "page_elements": page_elements,
        "formula": formula,
        "citation": citation,
        "cleanup": cleanup,
        "content_fill": content_fill,
    }
    for group in UI_CAPABILITY_GROUPS:
        enabled = group_mapping.get(group.group_id, False)
        for m in group.module_names:
            switches[m] = enabled

    return switches


def create_custom_scene() -> SceneWorkspace:
    """自定义场景：所有分区全开、能力组默认关闭，等待人工启用。"""
    return SceneWorkspace(
        scene_id="custom",
        name="自定义",
        description="手动控制所有功能开关与处理范围",
        category="general",
        category_label="通用文档",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
        strict_mode=True,
        format_scope=FormatScopeConfig(sections=_all_sections_on()),
        module_switches=_build_switches(
            table_chart=False,
            page_elements=False,
            formula=False,
            citation=False,
            cleanup=False,
            content_fill=False,
        ),
    )


def create_thesis_scene() -> SceneWorkspace:
    """论文排版场景。"""
    return SceneWorkspace(
        scene_id="thesis",
        name="论文排版",
        description="学位论文·期刊论文·学术报告",
        category="academic",
        category_label="学术文档",
        template_id="thesis_gbt",
        default_template_id="thesis_gbt",
        compatible_template_ids=["thesis_gbt", "thesis_custom"],
        strict_mode=True,
        format_scope=FormatScopeConfig(sections=_thesis_sections()),
        module_switches=_build_switches(
            table_chart=True,
            page_elements=True,
            formula=True,
            citation=True,
            cleanup=True,
            content_fill=False,
        ),
    )


def create_bidding_scene() -> SceneWorkspace:
    """标书排版场景。"""
    return SceneWorkspace(
        scene_id="bidding",
        name="标书排版",
        description="工程投标·政府采购·商务投标",
        category="business",
        category_label="商务文档",
        template_id="bid_engineering",
        default_template_id="bid_engineering",
        compatible_template_ids=["bid_engineering", "bid_procurement", "bid_custom"],
        strict_mode=True,
        format_scope=FormatScopeConfig(sections=_bidding_sections()),
        module_switches=_build_switches(
            table_chart=True,
            page_elements=True,
            formula=False,
            citation=False,
            cleanup=True,
            content_fill=True,
        ),
        table=TableConfig(border_mode="full_grid", layout_mode="full"),
    )


def create_official_scene() -> SceneWorkspace:
    """公文排版场景。"""
    return SceneWorkspace(
        scene_id="official",
        name="公文排版",
        description="政府公文·通知·批复·函",
        category="government",
        category_label="政府公文",
        template_id="official_gbt",
        default_template_id="official_gbt",
        compatible_template_ids=["official_gbt", "official_custom"],
        strict_mode=False,          # 公文保留原编号
        format_scope=FormatScopeConfig(sections=_official_sections()),
        module_switches=_build_switches(
            table_chart=True,
            page_elements=True,
            formula=False,
            citation=False,
            cleanup=True,
            content_fill=True,
        ),
    )


def create_technical_scene() -> SceneWorkspace:
    """技术文档场景。"""
    return SceneWorkspace(
        scene_id="technical",
        name="技术文档",
        description="技术规范·操作手册·设计文档",
        category="technical",
        category_label="技术文档",
        template_id="tech_standard",
        default_template_id="tech_standard",
        compatible_template_ids=["tech_standard", "tech_custom"],
        strict_mode=True,
        format_scope=FormatScopeConfig(sections={
            "body": True,
            "toc": True,
            "appendix": True,
            "references": False,
            "acknowledgment": False,
            "abstract_cn": False,
            "abstract_en": False,
            "errata": False,
            "resume": False,
        }),
        module_switches=_build_switches(
            table_chart=True,
            page_elements=True,
            formula=True,
            citation=False,
            cleanup=True,
            content_fill=True,
        ),
        table=TableConfig(border_mode="full_grid"),
    )


def create_report_scene() -> SceneWorkspace:
    """通用报告场景。"""
    return SceneWorkspace(
        scene_id="report",
        name="通用报告",
        description="汇报·总结·调研报告",
        category="general",
        category_label="通用文档",
        template_id="report_default",
        default_template_id="report_default",
        compatible_template_ids=["report_default", "report_custom"],
        strict_mode=True,
        format_scope=FormatScopeConfig(sections={
            "body": True,
            "toc": True,
            "appendix": False,
            "references": False,
            "acknowledgment": False,
            "abstract_cn": False,
            "abstract_en": False,
            "errata": False,
            "resume": False,
        }),
        module_switches=_build_switches(
            table_chart=True,
            page_elements=True,
            formula=False,
            citation=False,
            cleanup=True,
            content_fill=False,
        ),
    )


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

# 场景元信息表
SCENE_METAS: tuple[SceneMeta, ...] = (
    SceneMeta(
        scene_id="custom",
        name="自定义",
        description="手动控制所有功能开关与处理范围",
        default_template_id="default",
        compatible_templates=(
            TemplateMeta("default", "默认格式"),
        ),
    ),
    SceneMeta(
        scene_id="thesis",
        name="论文排版",
        description="学位论文·期刊论文·学术报告",
        default_template_id="thesis_gbt",
        compatible_templates=(
            TemplateMeta("thesis_gbt", "GB/T 7713 学位论文"),
            TemplateMeta("thesis_custom", "自定义论文模板"),
        ),
    ),
    SceneMeta(
        scene_id="bidding",
        name="标书排版",
        description="工程投标·政府采购·商务投标",
        default_template_id="bid_engineering",
        compatible_templates=(
            TemplateMeta("bid_engineering", "工程类投标文件"),
            TemplateMeta("bid_procurement", "政府采购投标"),
            TemplateMeta("bid_custom", "自定义标书模板"),
        ),
    ),
    SceneMeta(
        scene_id="official",
        name="公文排版",
        description="政府公文·通知·批复·函",
        default_template_id="official_gbt",
        compatible_templates=(
            TemplateMeta("official_gbt", "GB/T 9704 公文格式"),
            TemplateMeta("official_custom", "自定义公文模板"),
        ),
    ),
    SceneMeta(
        scene_id="technical",
        name="技术文档",
        description="技术规范·操作手册·设计文档",
        default_template_id="tech_standard",
        compatible_templates=(
            TemplateMeta("tech_standard", "通用技术文档"),
            TemplateMeta("tech_custom", "自定义技术模板"),
        ),
    ),
    SceneMeta(
        scene_id="report",
        name="通用报告",
        description="汇报·总结·调研报告",
        default_template_id="report_default",
        compatible_templates=(
            TemplateMeta("report_default", "通用报告格式"),
            TemplateMeta("report_custom", "自定义报告模板"),
        ),
    ),
)

SCENE_META_MAP: dict[str, SceneMeta] = {s.scene_id: s for s in SCENE_METAS}

# 场景工厂表
SCENE_FACTORIES: dict[str, callable] = {
    "custom": create_custom_scene,
    "thesis": create_thesis_scene,
    "bidding": create_bidding_scene,
    "official": create_official_scene,
    "technical": create_technical_scene,
    "report": create_report_scene,
}


def create_scene(scene_id: str) -> SceneWorkspace:
    """根据场景 ID 创建真实 SceneWorkspace 实例。"""
    factory = SCENE_FACTORIES.get(scene_id)
    if factory is None:
        raise ValueError(f"未知场景 ID: {scene_id}")
    return factory()


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def build_scene_summary(scene: SceneWorkspace) -> str:
    """从真实 SceneWorkspace 构建一行摘要。"""
    strategy_text = "重建编号" if scene.strict_mode else "保留原编号"
    zone_count = sum(1 for v in scene.format_scope.sections.values() if v)
    total_zones = len(scene.format_scope.sections)

    enabled_groups = []
    for group in UI_CAPABILITY_GROUPS:
        if get_group_enabled(scene, group):
            enabled_groups.append(group.label)

    cap_count = len(enabled_groups)
    features_text = "·".join(enabled_groups) if enabled_groups else "无"
    return f"{strategy_text} · {zone_count}/{total_zones}个分区 · {cap_count}项功能（{features_text}）"
