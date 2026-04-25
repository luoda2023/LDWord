"""
SceneWorkspace — 场景工作区

定义「做什么事」的功能开关、排版范围、模块开关、批量预设。
同时包含功能专属配置（开关 ON 时才生效的参数）。
基础排版参数在 TemplateConfig 中。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.config.migration import (
    get_default_module_switches,
    normalize_module_name,
    normalize_module_switches,
)
from src.config.feature_configs import (
    HeaderFooterConfig,
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


@dataclass
class FormatScopeConfig:
    """排版作用域（决定处理文档的哪些部分）。"""
    mode: str = "auto"
    page_ranges_text: str = ""
    body_start_index: int | None = None
    body_start_page: int | None = None
    body_start_keyword: str = ""
    sections: dict[str, bool] = field(default_factory=lambda: {
        "body": True,
        "references": True,
        "errata": True,
        "acknowledgment": True,
        "appendix": False,
        "abstract_cn": False,
        "abstract_en": False,
        "toc": False,
        "resume": False,
    })

    def is_section_enabled(self, section_type: str) -> bool:
        if str(section_type or "").strip().lower() == "cover":
            return False
        return self.sections.get(section_type, False)


@dataclass
class ModuleSwitch:
    """单个模块的开关+细项配置。"""
    enabled: bool = False
    options: dict = field(default_factory=dict)


@dataclass
class MdCleanupOptions:
    """格式清理模块的细项开关。"""
    preserve_existing_word_lists: bool = True
    formula_copy_noise_cleanup: bool = True
    suppress_formula_fake_lists: bool = True
    list_marker_separator: str = "tab"
    ordered_list_style: str = "mixed"
    unordered_list_style: str = "word_default"


@dataclass
class WhitespaceOptions:
    """空白规范模块的细项开关。"""
    normalize_space_variants: bool = True
    convert_tabs: bool = True
    remove_zero_width: bool = True
    collapse_multiple_spaces: bool = True
    trim_paragraph_edges: bool = True
    smart_full_half_convert: bool = True
    punctuation_by_context: bool = True
    bracket_by_inner_language: bool = True
    fullwidth_alnum_to_halfwidth: bool = True
    quote_by_context: bool = False
    protect_reference_numbering: bool = True
    context_min_confidence: int = 2


@dataclass
class CitationLinkOptions:
    """参考文献模块的细项开关。"""
    auto_number_reference_entries: bool = True
    superscript_outer_page_numbers: bool = False


@dataclass
class FormulaConvertOptions:
    """公式转换模块的细项开关。"""
    output_mode: str = "word_native"
    low_confidence_policy: str = "skip_and_mark"
    office_fallback_enabled: bool = False
    office_fallback_timeout_sec: int = 30


@dataclass
class ChemTypographyOptions:
    """化学式处理的细项开关。"""
    western_font: str = "Times New Roman"
    scopes: dict[str, bool] = field(default_factory=lambda: {
        "references": False, "body": False, "headings": False,
        "abstract_cn": False, "abstract_en": False,
        "captions": False, "tables": False,
    })
    allow_tokens: list[str] = field(default_factory=list)
    allow_patterns: list[str] = field(default_factory=list)
    ignore_tokens: list[str] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)
    manual_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class BatchPreset:
    """批量生成预设（陪标等场景）。"""
    entity_profile_ids: list[str] = field(default_factory=list)
    output_dir_template: str = "{entity_name}/"


@dataclass
class SceneWorkspace:
    """场景工作区 — 定义「做什么事」+「如何做这件事」。

    包含：功能开关、排版范围、模块细项配置、功能专属参数、批量预设。
    基础排版参数（页面、字体、标题编号）在 TemplateConfig 中。
    """

    # ── 元信息 ─────────────────────────────
    name: str = ""
    description: str = ""
    category: str = "general"
    category_label: str = "通用文档"
    scene_id: str = ""
    template_id: str = ""               # 绑定的模板 ID
    default_template_id: str = ""
    compatible_template_ids: list[str] = field(default_factory=list)

    # ── 排版范围 ───────────────────────────
    format_scope: FormatScopeConfig = field(default_factory=FormatScopeConfig)
    available_sections: list[str] = field(default_factory=lambda: [
        "body", "references", "errata", "acknowledgment", "appendix",
        "resume", "abstract_cn", "abstract_en", "toc",
    ])

    # ── 模块开关 ───────────────────────────
    module_switches: dict[str, bool] = field(
        default_factory=lambda: dict(get_default_module_switches())
    )

    # ── 模块细项配置（行为参数） ────────────────
    md_cleanup: MdCleanupOptions = field(default_factory=MdCleanupOptions)
    whitespace: WhitespaceOptions = field(default_factory=WhitespaceOptions)
    citation_link: CitationLinkOptions = field(default_factory=CitationLinkOptions)
    formula_convert: FormulaConvertOptions = field(default_factory=FormulaConvertOptions)
    chem_typography: ChemTypographyOptions = field(default_factory=ChemTypographyOptions)

    # ── 功能专属配置（开关 ON 时才生效的参数） ────
    table: TableConfig = field(default_factory=TableConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    toc: TocConfig = field(default_factory=TocConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    formula_table: FormulaTableConfig = field(default_factory=FormulaTableConfig)
    formula_style: FormulaStyleConfig = field(default_factory=FormulaStyleConfig)
    equation_numbering: EquationNumberingConfig = field(default_factory=EquationNumberingConfig)
    reference_style: ReferenceStyleConfig = field(default_factory=ReferenceStyleConfig)
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)

    # ── 分区样式变体（开启分区后的细项样式） ────
    # key = style_variant_semantics 中的 variant key，如 "references_body"
    # 值 = StyleConfig 对象。缺席表示“跟随正文”。
    section_styles: dict = field(default_factory=dict)

    # ── 输出配置 ─────────────────────
    output: OutputConfig = field(default_factory=OutputConfig)

    # ── 模板参数覆盖（场景级） ────────────────
    template_overrides: dict = field(default_factory=dict)

    # ── 批量预设 ───────────────────────────
    batch_preset: BatchPreset | None = None

    # ── 管线配置 ───────────────────────────
    strict_mode: bool = True

    def __post_init__(self) -> None:
        self.module_switches = normalize_module_switches(self.module_switches)
        self.scene_id = str(self.scene_id or "").strip()
        self.template_id = str(self.template_id or "").strip()
        self.default_template_id = str(self.default_template_id or "").strip()

        compatible_ids = [str(item or "").strip() for item in self.compatible_template_ids]
        self.compatible_template_ids = [item for item in compatible_ids if item]

        if not self.default_template_id and self.template_id:
            self.default_template_id = self.template_id
        if not self.template_id and self.default_template_id:
            self.template_id = self.default_template_id
        if not self.compatible_template_ids:
            seed = self.template_id or self.default_template_id
            self.compatible_template_ids = [seed] if seed else []
        elif self.template_id and self.template_id not in self.compatible_template_ids:
            self.compatible_template_ids.insert(0, self.template_id)
        elif not self.template_id and self.compatible_template_ids:
            self.template_id = self.compatible_template_ids[0]

    def is_module_enabled(self, module_name: str) -> bool:
        """查询模块是否在本场景中启用。"""
        return self.module_switches.get(
            normalize_module_name(module_name),
            False,
        )
