"""
TemplateConfig — 核心排版参数定义

定义可复用的文档外观与排版策略：页面、字体、标题编号、表格、
页眉页脚、目录、题注、参考文献等。
部分功能配置的数据类集中在 feature_configs.py 中，TemplateConfig 提供模板基线，
SceneWorkspace 可在解析阶段覆盖对应字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── 页面设置 ────────────────────────────────────────

@dataclass
class MarginConfig:
    top_cm: float = 3.8
    bottom_cm: float = 3.8
    left_cm: float = 3.2
    right_cm: float = 3.2


@dataclass
class PageSetupConfig:
    paper_size: str = "A4"
    orientation: str = "portrait"           # "portrait" | "landscape"
    margin: MarginConfig = field(default_factory=MarginConfig)
    gutter_cm: float = 0
    header_distance_cm: float = 3.0
    footer_distance_cm: float = 3.0


# ── 段落样式 ────────────────────────────────────────

@dataclass
class StyleConfig:
    """段落/字符样式定义（用于正文、标题各级、题注等）。"""
    font_cn: str = "宋体"
    font_en: str = "Times New Roman"
    size_pt: float = 12
    size_display: str = ""              # UI 显示用, e.g. "小四"
    bold: bool = False
    italic: bool = False
    alignment: str = "justify"
    first_line_indent_chars: float = 0
    first_line_indent_unit: str = "chars"
    left_indent_chars: float = 0
    left_indent_unit: str = "chars"
    right_indent_chars: float = 0
    right_indent_unit: str = "chars"
    hanging_indent_chars: float = 0
    hanging_indent_unit: str = "chars"
    special_indent_mode: str = "none"
    special_indent_value: float = 0
    special_indent_unit: str = "chars"
    line_spacing_type: str = "exact"    # "exact" | "multiple"
    line_spacing_pt: float = 20         # exact=pt, multiple=倍数
    space_before_pt: float = 0
    space_before_unit: str = "pt"
    space_after_pt: float = 0
    space_after_unit: str = "pt"


# ── 标题编号 ────────────────────────────────────────

@dataclass
class NumberShellConfig:
    label: str = "{}"
    prefix: str = ""
    suffix: str = ""


@dataclass
class NumberCoreStyleConfig:
    label: str = ""
    sample: str = ""


@dataclass
class NumberChainSegmentConfig:
    type: str = "value"     # "value" | "literal"
    source: str = "current"
    text: str = ""


@dataclass
class NumberChainConfig:
    label: str = ""
    segments: list[NumberChainSegmentConfig] = field(default_factory=list)


@dataclass
class NumberPresetConfig:
    label: str = ""
    display_shell: str = "plain"
    display_core_style: str = "arabic"
    reference_core_style: str = ""
    chain: str = "current_only"


@dataclass
class HeadingLevelBindingConfig:
    enabled: bool = False
    display_shell: str = "plain"
    display_core_style: str = "arabic"
    reference_core_style: str = "arabic"
    chain: str = "current_only"
    title_separator: str = "\u3000"
    ooxml_separator_mode: str = "inline"
    ooxml_suff: str | None = "nothing"
    ooxml_lvl_ind: dict[str, str] = field(default_factory=dict)
    start_at: int = 1
    restart_on: str | None = None
    include_in_toc: bool = True
    # 模板化编号字段
    display_template_mode: str = "structured"  # "structured"=字段生成, "custom"=手写编号模板
    display_template: str = ""          # 例: "第{cn}章", "({cn})", "{nn})" — 空=用 display_core_style 自动展开
    chain_separator: str = "."          # 多级 chain 连接符: "." → 3.1, "-" → 3-1
    chain_number_style: str = "arabic"  # 多级 chain 默认数字格式


@dataclass
class HeadingNumberingConfig:
    """标题编号模板参数。"""
    shell_catalog: dict[str, NumberShellConfig] = field(default_factory=dict)
    core_style_catalog: dict[str, NumberCoreStyleConfig] = field(default_factory=dict)
    chain_catalog: dict[str, NumberChainConfig] = field(default_factory=dict)
    preset_catalog: dict[str, NumberPresetConfig] = field(default_factory=dict)
    level_bindings: dict[str, HeadingLevelBindingConfig] = field(default_factory=dict)


# ── 标题模型 ────────────────────────────────────────

@dataclass
class HeadingModelConfig:
    """标题语义模型（层级映射、分区标题样式）。"""
    level_to_word_style: dict[str, str] = field(default_factory=lambda: {
        f"heading{i}": f"Heading {i}" for i in range(1, 9)
    })
    style_alias_to_level: dict[str, str] = field(default_factory=lambda: {
        "一级标题": "heading1", "二级标题": "heading2",
        "三级标题": "heading3", "四级标题": "heading4",
        "五级标题": "heading5", "六级标题": "heading6",
        "七级标题": "heading7", "八级标题": "heading8",
        "章标题": "heading1", "节标题": "heading2",
        "标题 1": "heading1", "标题 2": "heading2",
        "标题 3": "heading3", "标题 4": "heading4",
    })
    max_heading_levels: int = 4
    non_numbered_title_texts: list[str] = field(default_factory=lambda: [
        "参考文献", "勘误页", "勘误", "致谢",
        "个人简历", "在学期间发表的学术论文与研究成果",
        "摘要", "Abstract", "目录",
    ])
    non_numbered_prefixes: list[str] = field(default_factory=lambda: [
        "附录", "附件", "Appendix",
    ])
    non_numbered_heading_style_name: str = "Heading 1 Unnumbered"
    non_numbered_heading_style_mode: str = "inherit_heading1"


# ── 分节 ────────────────────────────────────────────

@dataclass
class SectionConfig:
    section_break_type: str | None = None   # "nextPage" | "continuous" | None(不修改)


# ── 功能专属配置的向后兼容 re-export ─────────────────
# 这些类型已移到 feature_configs.py，由 TemplateConfig 和 SceneWorkspace 共享。
# 此处 re-export 以保持下游 import 不中断。
from src.config.feature_configs import (  # noqa: E402, F401
    HeaderFooterConfig,
    HeaderFooterTypographyConfig,
    HeaderFooterBorderConfig,
    HeaderFooterBehaviorConfig,
    HeaderFooterContentConfig,
    HeaderFooterVariantConfig,
    HeaderFooterVariantsConfig,
    HeaderConfig,
    FooterConfig,
    PageNumberPhaseConfig,
    PageNumberPlanConfig,
    TocConfig,
    CaptionConfig,
    FormulaTableConfig,
    FormulaStyleConfig,
    EquationNumberingConfig,
    ReferenceStyleConfig,
    WatermarkConfig,
    TableConfig,
    OutputConfig,
)


# ── 顶层聚合 ────────────────────────────────────────

@dataclass
class TemplateConfig:
    """基础模板配置 — 定义文档的核心外观。

    模板提供可复用的排版基线；场景只通过显式 template_overrides
    或执行前 session overrides 覆盖模板字段。
    """
    name: str = ""
    description: str = ""

    page_setup: PageSetupConfig = field(default_factory=PageSetupConfig)
    styles: dict[str, StyleConfig] = field(default_factory=dict)
    heading_numbering: HeadingNumberingConfig = field(default_factory=HeadingNumberingConfig)
    heading_model: HeadingModelConfig = field(default_factory=HeadingModelConfig)
    section: SectionConfig = field(default_factory=SectionConfig)
    table: TableConfig = field(default_factory=TableConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    toc: TocConfig = field(default_factory=TocConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    formula_table: FormulaTableConfig = field(default_factory=FormulaTableConfig)
    formula_style: FormulaStyleConfig = field(default_factory=FormulaStyleConfig)
    equation_numbering: EquationNumberingConfig = field(default_factory=EquationNumberingConfig)
    reference_style: ReferenceStyleConfig = field(default_factory=ReferenceStyleConfig)
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
