"""
TemplateConfig — 纯排版参数定义

只定义「文档长什么样」的排版参数。
不包含功能开关、管线配置、元信息。
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
    line_spacing_type: str = "exact"    # "exact" | "multiple"
    line_spacing_pt: float = 20         # exact=pt, multiple=倍数
    space_before_pt: float = 0
    space_after_pt: float = 0


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


# ── 题注 ────────────────────────────────────────────

@dataclass
class CaptionConfig:
    figure_prefix: str = "图"
    table_prefix: str = "表"
    separator: str = "\u3000"
    placeholder: str = "[待补充]"
    numbering_format: str = "chapter.seq"
    numbering_mode: str = "chapter"     # "chapter" | "global"


# ── 表格 ────────────────────────────────────────────

@dataclass
class TableConfig:
    layout_mode: str = "smart"          # "compact" | "full" | "smart"
    smart_levels: int = 4
    border_mode: str = "three_line"     # "full_grid" | "three_line" | "keep"
    border_width_pt: float = 0.5        # 全框线模式线宽
    three_line_header_width_pt: float = 1.0   # 三线表外边线（上/下共用）
    three_line_bottom_width_pt: float = 0.5   # 三线表中间线（表头下分隔线）
    line_spacing_mode: str = "single"   # "single" | "one_half" | "double"
    repeat_header: bool = False
    row_height_pt: float | None = None
    font_cn: str | None = None
    font_en: str | None = None
    size_pt: float | None = None
    cell_alignment: str | None = None


# ── 页眉页脚 ────────────────────────────────────────

@dataclass
class HeaderFooterConfig:
    header_mode: str = "styleref"       # "styleref" | "fixed" | "none"
    header_text: str = ""               # fixed 模式的文本
    header_border: bool = True          # 页眉横线
    page_number_enabled: bool = True    # 页脚页码
    styleref_level: int = 1             # STYLEREF 跟随的标题级别
    font_cn: str | None = None          # 页眉页脚中文字体
    font_en: str | None = None          # 页眉页脚英文字体
    size_pt: float | None = None        # 页眉页脚字号


# ── 公式 ────────────────────────────────────────────

@dataclass
class FormulaTableConfig:
    """公式表格视觉参数。"""
    formula_font_name: str = "Times New Roman"
    formula_font_size_pt: float = 12.0
    formula_font_size_display: str = "12"
    formula_line_spacing: float = 1.0
    formula_space_before_pt: float = 6.0
    formula_space_after_pt: float = 6.0
    block_alignment: str = "center"
    table_alignment: str = "center"
    formula_cell_alignment: str = "center"
    number_alignment: str = "right"
    number_font_name: str = "Times New Roman"
    number_font_size_pt: float = 12.0
    number_font_size_display: str = "12"
    auto_shrink_number_column: bool = True


@dataclass
class FormulaStyleConfig:
    """公式样式参数。"""
    unify_font: bool = True
    unify_size: bool = True
    unify_spacing: bool = True


@dataclass
class EquationNumberingConfig:
    """公式编号参数。"""
    numbering_format: str = "chapter.seq"


# ── 目录 ────────────────────────────────────────────

@dataclass
class TocConfig:
    mode: str = "word_native"   # "word_native" | "plain"
    enabled: bool = True
    max_level: int = 3
    insert_position: str = "auto"   # "auto" | "after_cover" | 段落索引数字


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
    # 标题级数上限: 超出此级别的标题不编号、不设样式
    max_heading_levels: int = 4
    # 精确匹配词典: 标题文本必须完全一致才跳过编号
    non_numbered_title_texts: list[str] = field(default_factory=lambda: [
        "参考文献", "勘误页", "勘误", "致谢",
        "个人简历", "在学期间发表的学术论文与研究成果",
        "摘要", "Abstract", "目录",
    ])
    # 前缀匹配词典: 标题文本以此开头即跳过编号
    non_numbered_prefixes: list[str] = field(default_factory=lambda: [
        "附录", "附件", "Appendix",
    ])
    non_numbered_heading_style_name: str = "Heading 1 Unnumbered"


# ── 分节 ────────────────────────────────────────────

@dataclass
class SectionConfig:
    section_break_type: str | None = None   # "nextPage" | "continuous" | None(不修改)


# ── 水印 ────────────────────────────────────────────

@dataclass
class WatermarkConfig:
    """水印模块配置。"""
    enabled: bool = False
    text: str = ""
    color: str = "#C0C0C0"
    rotation: int = -45
    font_size: int = 48


# ── 参考文献样式 ────────────────────────────────────

@dataclass
class ReferenceStyleConfig:
    """参考文献排版配置。"""
    hanging_indent_cm: float = 0.74
    space_after_pt: float = 0
    font_cn: str | None = None
    font_en: str | None = None
    size_pt: float | None = None


# ── 输出 ────────────────────────────────────────────

@dataclass
class OutputConfig:
    final_docx: bool = True
    compare_docx: bool = True
    compare_text: bool = True
    compare_formatting: bool = True
    report_json: bool = True
    report_markdown: bool = True


# ── 顶层聚合 ────────────────────────────────────────

@dataclass
class TemplateConfig:
    """基础模板配置 — 定义文档「长什么样」。

    只包含排版参数，不包含功能开关和管线配置。
    跨文档不变的参数放在这里。
    """
    name: str = ""
    description: str = ""

    page_setup: PageSetupConfig = field(default_factory=PageSetupConfig)
    styles: dict[str, StyleConfig] = field(default_factory=dict)
    heading_numbering: HeadingNumberingConfig = field(default_factory=HeadingNumberingConfig)
    heading_model: HeadingModelConfig = field(default_factory=HeadingModelConfig)
    toc: TocConfig = field(default_factory=TocConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    table: TableConfig = field(default_factory=TableConfig)
    section: SectionConfig = field(default_factory=SectionConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)
    reference_style: ReferenceStyleConfig = field(default_factory=ReferenceStyleConfig)
    formula_table: FormulaTableConfig = field(default_factory=FormulaTableConfig)
    formula_style: FormulaStyleConfig = field(default_factory=FormulaStyleConfig)
    equation_numbering: EquationNumberingConfig = field(default_factory=EquationNumberingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
