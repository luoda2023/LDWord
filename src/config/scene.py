"""
SceneWorkspace — 场景工作区

定义「做什么事」的功能开关、排版范围、模块开关、批量预设。
同时可携带场景级模块参数，用于在解析阶段覆盖 TemplateConfig 的模板基线。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Literal

from src.config.migration import (
    get_default_module_switches,
    normalize_module_name,
    normalize_module_switches,
)
from src.config.feature_configs import (
    ReferenceStyleConfig,
    WatermarkConfig,
    OutputConfig,
)
from src.config.formula_policy import (
    THESIS_FORMULA_MODULE_NAMES,
    ThesisFormulaRules,
    is_thesis_formula_mode,
)
from src.config.document_scope import (
    DocumentScopePolicy,
    coerce_document_scope_policy,
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
class BatchPreset:
    """Recipe output preset; record selection remains run-owned."""

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
    failure_policy: Literal["warn", "block", "confirm"] = "warn"


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
    failure_policy: Literal["warn", "block", "confirm"] = "warn"
    object_preflight: ObjectPreflightPolicy = field(default_factory=ObjectPreflightPolicy)


@dataclass
class ContentVisibilityRule:
    """Preset-level paragraph block visibility rule."""

    rule_id: str = ""
    label: str = ""
    selector_type: Literal["marker_block"] = "marker_block"
    selector: str = ""
    action: Literal["remove"] = "remove"


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
        if base_style not in BUILTIN_EXAM_BLANK_STYLE_IDS:
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


BUILTIN_EXAM_BLANK_STYLE_IDS: tuple[str, ...] = (
    "default_exam",
)


def _normalized_user_exam_blank_style_id(
    builtin_style_id: str,
    reserved_ids: set[str],
) -> str:
    base_id = f"user_{str(builtin_style_id or '').strip()}_copy"
    candidate = base_id
    index = 2
    while candidate in reserved_ids:
        candidate = f"{base_id}{index}"
        index += 1
    return candidate


@dataclass
class ExamPaperConfig:
    """Scene-level assembly rules for exam paper scenarios.

    Runtime field values are intentionally not stored here.  This config only
    records which stable assembly decisions the workbench should follow.
    """

    question_structure_mode: str = "markdown_headings"
    answer_policy: str = "student_plus_answer"
    custom_blank_styles: list[ExamBlankStyleConfig] = field(default_factory=list)
    runtime_fields: list[str] = field(
        default_factory=lambda: ["title", "subject", "grade", "duration", "total_score"]
    )

    def __post_init__(self) -> None:
        coerced_styles: list[ExamBlankStyleConfig] = []
        seen_original_style_ids: set[str] = set()
        incoming_styles = (
            self.custom_blank_styles if isinstance(self.custom_blank_styles, list) else []
        )
        for item in incoming_styles:
            style = _coerce_exam_blank_style_config(item)
            if style is None or style.style_id in seen_original_style_ids:
                continue
            seen_original_style_ids.add(style.style_id)
            coerced_styles.append(style)

        reserved_style_ids = {
            *BUILTIN_EXAM_BLANK_STYLE_IDS,
            *(
                style.style_id
                for style in coerced_styles
                if style.style_id not in BUILTIN_EXAM_BLANK_STYLE_IDS
            ),
        }
        custom_styles: list[ExamBlankStyleConfig] = []
        for style in coerced_styles:
            original_style_id = style.style_id
            if original_style_id in BUILTIN_EXAM_BLANK_STYLE_IDS:
                style.style_id = _normalized_user_exam_blank_style_id(
                    original_style_id,
                    reserved_style_ids,
                )
                reserved_style_ids.add(style.style_id)
            custom_styles.append(style)
        self.custom_blank_styles = custom_styles

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
    mode_id: str = ""
    display_order: int = 0
    template_id: str = ""               # 唯一持久化模板 ID
    compatible_template_ids: list[str] = field(default_factory=list)
    master_id: str = ""                 # 唯一持久化母版 ID（无母版的方案留空）

    # ── 处理范围 ───────────────────────────
    document_scope: DocumentScopePolicy = field(
        default_factory=DocumentScopePolicy
    )

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
    # Formula conversion, equation-table layout/numbering and chemical
    # super/subscript recovery have one persisted owner.  Non-thesis plans use
    # ``None`` and are fail-closed by the resolver.
    thesis_formula_rules: ThesisFormulaRules | None = None
    reference_style: ReferenceStyleConfig = field(default_factory=ReferenceStyleConfig)
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)

    # ── 模板参数覆盖（场景级） ────────────────
    template_overrides: dict = field(default_factory=dict)

    # ── 批量预设 ───────────────────────────
    batch_preset: BatchPreset | None = None

    # ── 管线配置 ───────────────────────────
    strict_mode: bool = True

    def __post_init__(self) -> None:
        self.document_scope = coerce_document_scope_policy(self.document_scope)

        self.module_switches = normalize_module_switches(self.module_switches)
        # Formula enablement is persisted only inside ``thesis_formula_rules``.
        # The resolver recreates the runtime switches expected by the pipeline.
        for module_name in THESIS_FORMULA_MODULE_NAMES:
            self.module_switches.pop(module_name, None)
        self.scene_id = str(self.scene_id or "").strip()
        self.mode_id = str(self.mode_id or "").strip()
        if is_thesis_formula_mode(self.mode_id):
            if self.thesis_formula_rules is None:
                self.thesis_formula_rules = ThesisFormulaRules()
        else:
            # A formula policy attached to a non-thesis plan is stale/invalid
            # state.  Do not allow it to become executable merely because old
            # module switches were persisted as true.
            self.thesis_formula_rules = None
        if type(self.display_order) is not int:
            self.display_order = 0
        self.template_id = str(self.template_id or "").strip()
        self.master_id = str(self.master_id or "").strip()
        # Preserve an explicit empty/unknown ID.  Execution integrity is the
        # single owner that rejects it; construction must not silently select
        # a different delivery contract.
        self.default_delivery_preset_id = str(
            self.default_delivery_preset_id or ""
        ).strip()
        self.exam_paper = coerce_exam_paper_config(self.exam_paper)

        compatible_ids = [str(item or "").strip() for item in self.compatible_template_ids]
        self.compatible_template_ids = list(
            dict.fromkeys(item for item in compatible_ids if item)
        )

        if self.delivery_presets is None:
            self.delivery_presets = []

    def ensure_thesis_formula_rules(self) -> ThesisFormulaRules:
        """Return the thesis rule aggregate, rejecting cross-mode activation."""

        if not is_thesis_formula_mode(self.mode_id):
            raise RuntimeError(
                "thesis formula rules are unavailable outside thesis mode"
            )
        if self.thesis_formula_rules is None:
            self.thesis_formula_rules = ThesisFormulaRules()
        return self.thesis_formula_rules

    def is_module_enabled(self, module_name: str) -> bool:
        """查询模块是否在本场景中启用。"""
        normalized_name = normalize_module_name(module_name)
        rules = self.thesis_formula_rules
        if not is_thesis_formula_mode(self.mode_id) or rules is None:
            if normalized_name in THESIS_FORMULA_MODULE_NAMES:
                return False
        elif normalized_name == "formula_convert":
            return bool(rules.formula_enabled and rules.formula_convert.enabled)
        elif normalized_name == "chem_typography":
            return bool(
                rules.chem_typography.enabled
                and any(
                    bool(active)
                    for active in (rules.chem_typography.scopes or {}).values()
                )
            )
        elif normalized_name == "equation_table_format":
            return bool(
                rules.formula_enabled
                and (
                    rules.formula_to_table.enabled
                    or rules.equation_numbering.enabled
                    or rules.formula_style.enabled
                )
            )
        return self.module_switches.get(normalized_name, False)

    def default_delivery_preset(self) -> DeliveryPreset:
        """Return the canonical artifact owner selected for default delivery."""
        target_id = str(self.default_delivery_preset_id or "").strip()
        for preset in self.delivery_presets:
            if str(preset.preset_id or "").strip() == target_id:
                return preset
        raise RuntimeError(
            f"default delivery preset {target_id!r} is not present in the scene"
        )
