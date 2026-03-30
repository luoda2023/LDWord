"""
SceneWorkspace — 场景工作区

定义「做什么事」的功能开关、排版范围、模块开关、批量预设。
不包含排版参数（那些在 TemplateConfig 中）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.config.migration import (
    get_default_module_switches,
    normalize_module_name,
    normalize_module_switches,
)


@dataclass
class FormatScopeConfig:
    """排版作用域（决定处理文档的哪些部分）。"""
    mode: str = "auto"                      # "auto" | "manual"
    page_ranges_text: str = ""              # 手动模式: 页码范围
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
    """场景工作区 — 定义「做什么事」。

    包含：功能开关、排版范围、模块细项配置、批量预设。
    不包含排版参数（那些在 TemplateConfig 中定义）。
    """

    # ── 元信息 ─────────────────────────────────────
    name: str = ""
    description: str = ""
    category: str = "general"
    category_label: str = "通用文档"
    template_id: str = ""               # 绑定的模板 ID

    # ── 排版范围 ───────────────────────────────────
    format_scope: FormatScopeConfig = field(default_factory=FormatScopeConfig)
    available_sections: list[str] = field(default_factory=lambda: [
        "body", "references", "errata", "acknowledgment", "appendix",
        "resume", "abstract_cn", "abstract_en", "toc",
    ])

    # ── 模块开关 ───────────────────────────────────
    # 每个 key 对应 modules/base.py 中 ModuleMeta.name
    module_switches: dict[str, bool] = field(
        default_factory=lambda: dict(get_default_module_switches())
    )

    # ── 模块细项配置（仅需要细项的模块） ──────────────
    md_cleanup: MdCleanupOptions = field(default_factory=MdCleanupOptions)
    whitespace: WhitespaceOptions = field(default_factory=WhitespaceOptions)
    citation_link: CitationLinkOptions = field(default_factory=CitationLinkOptions)
    formula_convert: FormulaConvertOptions = field(default_factory=FormulaConvertOptions)
    chem_typography: ChemTypographyOptions = field(default_factory=ChemTypographyOptions)

    # ── 模板参数覆盖（场景级） ────────────────────────
    template_overrides: dict = field(default_factory=dict)

    # ── 批量预设 ───────────────────────────────────
    batch_preset: BatchPreset | None = None

    # ── 管线配置 ───────────────────────────────────
    strict_mode: bool = True

    def __post_init__(self) -> None:
        self.module_switches = normalize_module_switches(self.module_switches)

    def is_module_enabled(self, module_name: str) -> bool:
        """查询模块是否在本场景中启用。"""
        return self.module_switches.get(
            normalize_module_name(module_name),
            False,
        )
