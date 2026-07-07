"""
SceneWorkspace — 场景工作区

定义「做什么事」的功能开关、排版范围、模块开关、批量预设。
同时可携带场景级模块参数，用于在解析阶段覆盖 TemplateConfig 的模板基线。
"""

from __future__ import annotations

import copy
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
    """Legacy processing gate kept for old scene configs and runtime consumers."""
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


SCENE_APPLICATION_BOUNDARY_MODES = (
    "follow_template",
    "body_only",
    "full_document",
    "confirm_before_apply",
)


@dataclass
class SceneApplicationBoundaryConfig:
    """High-level task boundary; it filters template/runtime structure only."""

    mode: str = "follow_template"
    confirm_before_apply: bool = False

    def __post_init__(self) -> None:
        mode = str(self.mode or "").strip() or "follow_template"
        if mode not in SCENE_APPLICATION_BOUNDARY_MODES:
            mode = "follow_template"
        self.mode = mode
        self.confirm_before_apply = bool(
            self.confirm_before_apply or mode == "confirm_before_apply"
        )


def coerce_scene_application_boundary(
    boundary: SceneApplicationBoundaryConfig | dict | None,
) -> SceneApplicationBoundaryConfig:
    """Return a normalized copy of a scene application boundary."""

    if isinstance(boundary, SceneApplicationBoundaryConfig):
        result = copy.deepcopy(boundary)
        result.__post_init__()
        return result
    if isinstance(boundary, dict):
        return SceneApplicationBoundaryConfig(
            **{
                key: value
                for key, value in boundary.items()
                if key in {"mode", "confirm_before_apply"}
            }
        )
    return SceneApplicationBoundaryConfig()


def coerce_format_scope(scope: FormatScopeConfig | dict | None) -> FormatScopeConfig:
    """Return a normalized copy of the legacy runtime format scope."""

    if isinstance(scope, FormatScopeConfig):
        return copy.deepcopy(scope)
    if isinstance(scope, dict):
        payload = {
            key: value
            for key, value in scope.items()
            if key in {
                "mode",
                "page_ranges_text",
                "body_start_index",
                "body_start_page",
                "body_start_keyword",
                "sections",
            }
        }
        return FormatScopeConfig(**payload)
    return FormatScopeConfig()


def infer_application_boundary_from_format_scope(
    format_scope: FormatScopeConfig | dict | None,
) -> SceneApplicationBoundaryConfig:
    """Infer the high-level boundary from old section gates."""

    scope = coerce_format_scope(format_scope)
    raw_mode = str(scope.mode or "").strip()
    if raw_mode in SCENE_APPLICATION_BOUNDARY_MODES:
        return SceneApplicationBoundaryConfig(mode=raw_mode)
    if raw_mode in {"manual", "manual_review", "confirm"}:
        return SceneApplicationBoundaryConfig(mode="confirm_before_apply")

    sections = scope.sections or {}
    enabled = {str(key) for key, value in sections.items() if bool(value)}
    total = len(sections)
    if enabled == {"body"}:
        return SceneApplicationBoundaryConfig(mode="body_only")
    if total and len(enabled) == total:
        return SceneApplicationBoundaryConfig(mode="full_document")
    if total and len(enabled) >= max(3, total // 2):
        return SceneApplicationBoundaryConfig(mode="follow_template")
    return SceneApplicationBoundaryConfig(mode="confirm_before_apply")


def is_default_format_scope(scope: FormatScopeConfig | dict | None) -> bool:
    """Return True when the legacy scope is still at factory defaults."""

    current = coerce_format_scope(scope)
    default = FormatScopeConfig()
    return (
        current.mode == default.mode
        and current.page_ranges_text == default.page_ranges_text
        and current.body_start_index == default.body_start_index
        and current.body_start_page == default.body_start_page
        and current.body_start_keyword == default.body_start_keyword
        and current.sections == default.sections
    )


def scene_application_boundary_for_runtime(scene) -> SceneApplicationBoundaryConfig:
    """Resolve the scene's runtime boundary, preserving legacy-only configs."""

    boundary = coerce_scene_application_boundary(
        getattr(scene, "application_boundary", None)
    )
    if (
        boundary.mode == "follow_template"
        and not boundary.confirm_before_apply
        and not is_default_format_scope(getattr(scene, "format_scope", None))
    ):
        return infer_application_boundary_from_format_scope(
            getattr(scene, "format_scope", None)
        )
    return boundary


def format_scope_for_application_boundary(
    boundary: SceneApplicationBoundaryConfig | dict | None,
    legacy_scope: FormatScopeConfig | dict | None = None,
) -> FormatScopeConfig:
    """Project the high-level boundary into the legacy runtime scope."""

    resolved_boundary = coerce_scene_application_boundary(boundary)
    mode = resolved_boundary.mode
    if mode == "follow_template":
        return FormatScopeConfig()

    scope = coerce_format_scope(legacy_scope)
    default_sections = dict(FormatScopeConfig().sections)
    section_keys = tuple(dict.fromkeys([*default_sections, *(scope.sections or {})]))
    if mode == "body_only":
        scope.sections = {key: key == "body" for key in section_keys}
        scope.mode = "auto"
    elif mode == "full_document":
        scope.sections = {key: True for key in section_keys}
        scope.mode = "auto"
    elif mode == "confirm_before_apply":
        if not scope.sections:
            scope.sections = default_sections
        scope.mode = "manual_review"
    return scope


def format_scope_for_scene_runtime(scene) -> FormatScopeConfig:
    """Return the legacy scope that old runtime modules should consume."""

    return format_scope_for_application_boundary(
        scene_application_boundary_for_runtime(scene),
        getattr(scene, "format_scope", None),
    )


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
class InputSourceProfile:
    """Scene-level input contract, not the data values for one run."""

    accepted_formats: list[str] = field(default_factory=lambda: ["docx"])
    structured_formats: list[str] = field(default_factory=list)
    markdown_policy: str = "cleanup_only"
    latex_policy: str = "formula_fragments_only"
    require_material_package: bool = False
    material_schema_id: str = ""
    material_schema_ids: list[str] = field(default_factory=list)
    required_material_fields: list[str] = field(default_factory=list)
    required_image_roles: list[str] = field(default_factory=list)
    high_risk_imports: list[str] = field(default_factory=lambda: ["full_latex_project"])
    failure_policy: str = "warn"


@dataclass
class ObjectPreflightPolicy:
    """How a scene treats fragile Word objects before risky operations."""

    enabled: bool = True
    preservation_mode: str = "warn"
    scan_targets: list[str] = field(default_factory=lambda: [
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
        "macros",
        "tracked_changes",
        "comments",
        "hidden_text",
        "textboxes",
        "content_controls",
        "fields",
    ])
    block_on: list[str] = field(default_factory=lambda: ["macros"])
    skip_high_risk_modules: bool = True
    skip_modules_by_finding: dict[str, list[str]] = field(default_factory=lambda: {
        "ole_objects": ["section_format"],
        "embedded_workbooks": ["section_format"],
        "visio_drawings": ["section_format"],
        "macros": ["section_format"],
    })


@dataclass
class ComplianceProfile:
    """Scene-level compliance/checking profile."""

    profile_id: str = "basic"
    rule_family: str = "basic_format"
    count_profile_id: str = ""
    enabled_checks: list[str] = field(default_factory=lambda: [
        "validation",
        "object_preflight",
    ])
    check_scopes: list[str] = field(default_factory=lambda: [
        "body",
        "tables",
        "figures",
        "headers_footers",
    ])
    report_level: str = "summary"
    failure_policy: str = "warn"
    object_preflight: ObjectPreflightPolicy = field(default_factory=ObjectPreflightPolicy)


@dataclass
class ContentVisibilityRule:
    """Preset-level paragraph block visibility rule."""

    rule_id: str = ""
    label: str = ""
    selector_type: str = "marker_block"
    selector: str = ""
    action: str = "remove"


@dataclass
class DeliveryPreset:
    """One named output version generated from the same resolved source."""

    preset_id: str = "final"
    label: str = "Final DOCX"
    target_template_id: str = ""
    output_dir_template: str = "{document_dir}/output"
    filename_template: str = "{stem}_{preset_id}"
    artifacts: OutputConfig = field(default_factory=OutputConfig)
    content_visibility_rules: list[ContentVisibilityRule] = field(default_factory=list)
    include_structured_intermediate: bool = False
    report_level: str = "summary"


def default_delivery_presets() -> list[DeliveryPreset]:
    return [DeliveryPreset()]


@dataclass
class ExamBlankStyleConfig:
    """User-owned blank exam-paper style copied from a built-in style."""

    style_id: str = ""
    label: str = ""
    base_style_id: str = "default_exam"
    master_docx_path: str = ""

    def __post_init__(self) -> None:
        style_id = str(self.style_id or "").strip()
        self.style_id = style_id
        label = str(self.label or "").strip()
        self.label = label or style_id or "试卷样式副本"
        base_style = str(self.base_style_id or "").strip() or "default_exam"
        if base_style not in {"default_exam"}:
            base_style = "default_exam"
        self.base_style_id = base_style
        self.master_docx_path = str(self.master_docx_path or "").strip()


def _coerce_exam_blank_style_config(
    config: ExamBlankStyleConfig | dict | None,
) -> ExamBlankStyleConfig | None:
    if isinstance(config, ExamBlankStyleConfig):
        result = copy.deepcopy(config)
        result.__post_init__()
        return result if result.style_id else None
    if isinstance(config, dict):
        result = ExamBlankStyleConfig(
            **{
                key: value
                for key, value in config.items()
                if key in {"style_id", "label", "base_style_id", "master_docx_path"}
            }
        )
        return result if result.style_id else None
    return None


@dataclass
class ExamPaperConfig:
    """Scene-level assembly rules for exam paper scenarios.

    Runtime field values are intentionally not stored here.  This config only
    records which stable assembly decisions the workbench should follow.
    """

    blank_style_id: str = "default_exam"
    question_structure_mode: str = "markdown_headings"
    answer_policy: str = "student_plus_answer"
    custom_blank_styles: list[ExamBlankStyleConfig] = field(default_factory=list)
    runtime_fields: list[str] = field(
        default_factory=lambda: ["title", "subject", "grade", "duration", "total_score"]
    )

    def __post_init__(self) -> None:
        custom_styles: list[ExamBlankStyleConfig] = []
        seen_style_ids: set[str] = set()
        incoming_styles = (
            self.custom_blank_styles if isinstance(self.custom_blank_styles, list) else []
        )
        for item in incoming_styles:
            style = _coerce_exam_blank_style_config(item)
            if style is None or style.style_id in seen_style_ids:
                continue
            seen_style_ids.add(style.style_id)
            custom_styles.append(style)
        self.custom_blank_styles = custom_styles

        blank_style = str(self.blank_style_id or "").strip() or "default_exam"
        allowed_styles = {"default_exam", *seen_style_ids}
        if blank_style not in allowed_styles:
            blank_style = "default_exam"
        self.blank_style_id = blank_style

        structure_mode = str(self.question_structure_mode or "").strip() or "markdown_headings"
        if structure_mode not in {"markdown_headings", "numbered_questions"}:
            structure_mode = "markdown_headings"
        self.question_structure_mode = structure_mode

        answer_policy = str(self.answer_policy or "").strip() or "student_plus_answer"
        if answer_policy not in {"student_plus_answer", "student_only", "answer_only"}:
            answer_policy = "student_plus_answer"
        self.answer_policy = answer_policy

        default_fields = ["title", "subject", "grade", "duration", "total_score"]
        allowed_fields = [*default_fields, "class_name", "teacher", "exam_date"]
        incoming = self.runtime_fields if isinstance(self.runtime_fields, list) else []
        normalized = []
        for field_id in incoming:
            value = str(field_id or "").strip()
            if value in allowed_fields and value not in normalized:
                normalized.append(value)
        self.runtime_fields = normalized or default_fields


def coerce_exam_paper_config(
    config: ExamPaperConfig | dict | None,
) -> ExamPaperConfig:
    """Return a normalized exam paper config."""

    if isinstance(config, ExamPaperConfig):
        result = copy.deepcopy(config)
        result.__post_init__()
        return result
    if isinstance(config, dict):
        return ExamPaperConfig(
            **{
                key: value
                for key, value in config.items()
                if key in {
                    "blank_style_id",
                    "question_structure_mode",
                    "answer_policy",
                    "custom_blank_styles",
                    "runtime_fields",
                }
            }
        )
    return ExamPaperConfig()


@dataclass
class SceneWorkspace:
    """场景工作区 — 定义「做什么事」+「如何做这件事」。

    包含：功能开关、排版范围、模块细项配置、场景级模板覆盖、批量预设。
    TemplateConfig 提供排版基线；场景字段在 resolver 中作为覆盖层合并。
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

    # ── 处理范围 ───────────────────────────
    application_boundary: SceneApplicationBoundaryConfig = field(
        default_factory=SceneApplicationBoundaryConfig
    )

    # ── 兼容范围：旧场景和旧运行时仍会读取 ──────────────
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
    # High-level scene contracts.
    input_source_profile: InputSourceProfile = field(default_factory=InputSourceProfile)
    compliance_profile: ComplianceProfile = field(default_factory=ComplianceProfile)
    default_delivery_preset_id: str = "final"
    delivery_presets: list[DeliveryPreset] = field(default_factory=default_delivery_presets)
    exam_paper: ExamPaperConfig = field(default_factory=ExamPaperConfig)

    md_cleanup: MdCleanupOptions = field(default_factory=MdCleanupOptions)
    whitespace: WhitespaceOptions = field(default_factory=WhitespaceOptions)
    citation_link: CitationLinkOptions = field(default_factory=CitationLinkOptions)
    formula_convert: FormulaConvertOptions = field(default_factory=FormulaConvertOptions)
    chem_typography: ChemTypographyOptions = field(default_factory=ChemTypographyOptions)

    # ── 旧版场景内嵌模板字段（兼容保存 / 迁移读取） ────
    # 新路径不再通过这些同名字段自动覆盖模板外观；显式模板差异进入
    # template_overrides，运行时行为使用上方 scene-owned policy 字段。
    table: TableConfig = field(default_factory=TableConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    toc: TocConfig = field(default_factory=TocConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    formula_table: FormulaTableConfig = field(default_factory=FormulaTableConfig)
    formula_style: FormulaStyleConfig = field(default_factory=FormulaStyleConfig)
    equation_numbering: EquationNumberingConfig = field(default_factory=EquationNumberingConfig)
    reference_style: ReferenceStyleConfig = field(default_factory=ReferenceStyleConfig)
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)

    # ── 格式例外（绑定模板识别出的结构） ───────────────
    # key = style_variant_semantics 中的 variant key，如 "references_body"
    # 值 = StyleConfig 对象。缺席表示“跟随模板”。
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
        if isinstance(self.application_boundary, dict):
            self.application_boundary = SceneApplicationBoundaryConfig(
                **{
                    key: value
                    for key, value in self.application_boundary.items()
                    if key in {"mode", "confirm_before_apply"}
                }
            )
        elif self.application_boundary is None:
            self.application_boundary = SceneApplicationBoundaryConfig()
        elif isinstance(self.application_boundary, SceneApplicationBoundaryConfig):
            self.application_boundary.__post_init__()
        else:
            self.application_boundary = SceneApplicationBoundaryConfig()

        self.module_switches = normalize_module_switches(self.module_switches)
        self.scene_id = str(self.scene_id or "").strip()
        self.template_id = str(self.template_id or "").strip()
        self.default_template_id = str(self.default_template_id or "").strip()
        self.default_delivery_preset_id = str(
            self.default_delivery_preset_id or "final"
        ).strip() or "final"
        self.exam_paper = coerce_exam_paper_config(self.exam_paper)

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

        if not self.delivery_presets:
            self.delivery_presets = [
                DeliveryPreset(
                    preset_id=self.default_delivery_preset_id,
                    artifacts=copy.deepcopy(self.output),
                )
            ]
        preset_ids = {
            str(getattr(preset, "preset_id", "") or "").strip()
            for preset in self.delivery_presets
        }
        if self.default_delivery_preset_id not in preset_ids:
            first = self.delivery_presets[0]
            first_id = str(getattr(first, "preset_id", "") or "").strip()
            if first_id:
                self.default_delivery_preset_id = first_id

    def is_module_enabled(self, module_name: str) -> bool:
        """查询模块是否在本场景中启用。"""
        return self.module_switches.get(
            normalize_module_name(module_name),
            False,
        )
