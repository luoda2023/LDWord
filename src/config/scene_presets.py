"""
Scene / Template presets — 场景与模板预设

连接 UI 层和真实配置模型 (config/scene.py + config/template.py)。

核心概念:
- UICapabilityGroup: 纯 UI 分组，将 module_switches 聚合为用户可理解的能力域开关
- SceneMeta: 场景元信息（UI 展示用），关联一个 SceneWorkspace 工厂
- TemplateMeta: 模板元信息（UI 展示用），关联一个 TemplateConfig 工厂
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from src.config.control_contract_registry import (
    ALLOWED_CONTROL_OWNER_LAYERS,
    ControlContractAuditResult,
    audit_control_contract_registry,
    list_control_contracts,
)
from src.config.scene import (
    ComplianceProfile,
    ContentVisibilityRule,
    ExamPaperConfig,
    FormatScopeConfig,
    InputSourceProfile,
    ObjectPreflightPolicy,
    DeliveryPreset,
    SceneWorkspace,
    scene_application_boundary_for_runtime,
)
from src.config.template import TemplateConfig
from src.config.feature_configs import TableConfig, OutputConfig
from src.config.scene_parameter_ownership import (
    ALLOWED_PARAMETER_OWNER_LAYERS,
    ParameterOwnershipAuditResult,
    audit_scene_parameter_ownership,
    scene_parameter_ownership_specs,
)
from src.config.scene_product_readiness import (
    SceneProductReadinessSpec,
    product_readiness_for,
)
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
from src.config.scene_sample_fixture_registry import (
    build_scene_sample_coverage_summary,
)
from src.config.scene_request_cell_fixture_registry import (
    build_scene_request_cell_fixture_summary,
)


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
        group_id="formula",
        label="公式处理",
        description="公式转换·低置信度处理·化学式修正，外观跟随模板",
        module_names=("equation_table_format", "chem_typography"),
    ),
    UICapabilityGroup(
        group_id="citation",
        label="引用处理",
        description="引用链接·参考条目编号·上标跟随，文献样式跟随模板",
        module_names=("reference_format", "citation_link"),
    ),
    UICapabilityGroup(
        group_id="cleanup",
        label="风险检查",
        description="Markdown残留·空白清理·对象风险·结构校验",
        module_names=("md_cleanup", "whitespace_normalize", "validation"),
    ),
    UICapabilityGroup(
        group_id="content_fill",
        label="资料包与填充",
        description="资料包输入·字段填入·占位符替换·图片插入·水印",
        module_names=(
            "entity_fill", "source_fill", "placeholder_replace",
            "image_insertion", "watermark",
        ),
    ),
)

UI_GROUP_MAP: dict[str, UICapabilityGroup] = {g.group_id: g for g in UI_CAPABILITY_GROUPS}

CAPABILITY_FEATURE_CARD_ORDER: tuple[str, ...] = tuple(group.group_id for group in UI_CAPABILITY_GROUPS)

CAPABILITY_FEATURE_CARD_DEFINITIONS: dict[str, tuple[str, str]] = {
    "table_chart": ("图表处理", "table"),
    "formula": ("公式处理", "sigma"),
    "citation": ("引用处理", "book-open"),
    "cleanup": ("风险检查", "scan"),
    "content_fill": ("资料包与填充", "pen-tool"),
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


def _input_profile(
    *,
    accepted_formats: tuple[str, ...] = ("docx",),
    structured_formats: tuple[str, ...] = (),
    markdown_policy: str = "cleanup_only",
    latex_policy: str = "formula_fragments_only",
    require_material_package: bool = False,
    material_schema_id: str = "",
    material_schema_ids: tuple[str, ...] = (),
    required_material_fields: tuple[str, ...] = (),
    required_image_roles: tuple[str, ...] = (),
    failure_policy: str = "warn",
) -> InputSourceProfile:
    return InputSourceProfile(
        accepted_formats=list(accepted_formats),
        structured_formats=list(structured_formats),
        markdown_policy=markdown_policy,
        latex_policy=latex_policy,
        require_material_package=require_material_package,
        material_schema_id=material_schema_id,
        material_schema_ids=list(material_schema_ids),
        required_material_fields=list(required_material_fields),
        required_image_roles=list(required_image_roles),
        failure_policy=failure_policy,
    )


def _compliance_profile(
    profile_id: str,
    *,
    rule_family: str,
    count_profile_id: str = "",
    check_scopes: tuple[str, ...] = ("body", "tables", "figures", "headers_footers"),
    report_level: str = "summary",
    failure_policy: str = "warn",
    preservation_mode: str = "warn",
    block_on: tuple[str, ...] = ("macros",),
) -> ComplianceProfile:
    return ComplianceProfile(
        profile_id=profile_id,
        rule_family=rule_family,
        count_profile_id=count_profile_id,
        check_scopes=list(check_scopes),
        report_level=report_level,
        failure_policy=failure_policy,
        object_preflight=ObjectPreflightPolicy(
            preservation_mode=preservation_mode,
            block_on=list(block_on),
        ),
    )


def _delivery_preset(
    preset_id: str,
    label: str,
    *,
    template_id: str = "",
    final_docx: bool = True,
    compare_docx: bool = False,
    report_json: bool = True,
    report_markdown: bool = True,
    material_manifest: bool = False,
    material_package: bool = False,
    structured: bool = False,
    report_level: str = "summary",
    output_dir_template: str = "{document_dir}/output",
) -> DeliveryPreset:
    return DeliveryPreset(
        preset_id=preset_id,
        label=label,
        target_template_id=template_id,
        output_dir_template=output_dir_template,
        filename_template="{stem}_{preset_id}",
        artifacts=OutputConfig(
            final_docx=final_docx,
            compare_docx=compare_docx,
            compare_text=compare_docx,
            compare_formatting=compare_docx,
            report_json=report_json,
            report_markdown=report_markdown,
            material_manifest=material_manifest,
            material_package=material_package,
        ),
        include_structured_intermediate=structured,
        report_level=report_level,
    )


def _build_switches(
    *,
    table_chart: bool = True,
    page_elements: bool = True,
    formula: bool = False,
    citation: bool = False,
    cleanup: bool = True,
    content_fill: bool = False,
) -> dict[str, bool]:
    """从能力域开关生成完整的 module_switches 字典。"""
    switches: dict[str, bool] = {}

    # 核心模块始终 ON
    for m in CORE_MODULES:
        switches[m] = True

    # 页眉页脚与目录规则由模板负责；旧预设参数只保留内部开关兼容。
    switches["header_footer"] = bool(page_elements)
    switches["toc"] = bool(page_elements)

    # 按能力组展开
    group_mapping = {
        "table_chart": table_chart,
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
        input_source_profile=_input_profile(
            accepted_formats=("docx", "markdown"),
            structured_formats=("json",),
            latex_policy="disabled",
        ),
        compliance_profile=_compliance_profile(
            "custom_basic",
            rule_family="manual",
            check_scopes=("body", "references", "tables", "figures"),
        ),
        delivery_presets=[
            _delivery_preset("final", "Final DOCX", template_id="default"),
        ],
        module_switches=_build_switches(
            table_chart=False,
            page_elements=False,
            formula=False,
            citation=False,
            cleanup=False,
            content_fill=False,
        ),
    )


def create_exam_scene() -> SceneWorkspace:
    """试卷场景：把题目内容装配到可交付的试卷样式中。"""
    student_preset = _delivery_preset("student", "学生卷", template_id="default")
    student_preset.content_visibility_rules = [
        ContentVisibilityRule(
            rule_id="hide_answers",
            label="隐藏答案与解析",
            selector_type="semantic_block",
            selector="answer",
            action="remove",
        ),
        ContentVisibilityRule(
            rule_id="hide_explanations",
            label="隐藏解析",
            selector_type="semantic_block",
            selector="explanation",
            action="remove",
        ),
    ]
    answer_preset = _delivery_preset("answer", "答案版", template_id="default")
    return SceneWorkspace(
        scene_id="exam",
        name="试卷",
        description="把 Markdown 或 Word 题目内容装配成完整试卷",
        category="exam_paper",
        category_label="试卷",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
        strict_mode=False,
        format_scope=FormatScopeConfig(sections={
            "body": True,
            "toc": False,
            "references": False,
            "appendix": False,
            "acknowledgment": False,
            "abstract_cn": False,
            "abstract_en": False,
            "errata": False,
            "resume": False,
        }),
        input_source_profile=_input_profile(
            accepted_formats=("markdown", "docx"),
            structured_formats=("json",),
            markdown_policy="preview_and_cleanup",
            latex_policy="formula_fragments_only",
        ),
        compliance_profile=_compliance_profile(
            "exam_paper",
            rule_family="exam_paper",
            check_scopes=("body", "tables", "figures"),
            preservation_mode="warn",
            block_on=("macros", "ole_objects"),
        ),
        default_delivery_preset_id="student",
        delivery_presets=[student_preset, answer_preset],
        exam_paper=ExamPaperConfig(
            blank_style_id="default_exam",
            question_structure_mode="markdown_headings",
            answer_policy="student_plus_answer",
            runtime_fields=["title", "subject", "grade", "duration", "total_score"],
        ),
        module_switches=_build_switches(
            table_chart=True,
            page_elements=True,
            formula=True,
            citation=False,
            cleanup=True,
            content_fill=False,
        ),
        table=TableConfig(border_mode="full_grid"),
    )


def create_thesis_scene() -> SceneWorkspace:
    """论文排版场景。"""
    return SceneWorkspace(
        scene_id="thesis",
        name="论文排版",
        description="中文学位论文·课程论文·综述·开题",
        category="academic",
        category_label="学术文档",
        template_id="thesis_gbt",
        default_template_id="thesis_gbt",
        compatible_template_ids=["thesis_gbt"],
        strict_mode=True,
        format_scope=FormatScopeConfig(sections=_thesis_sections()),
        input_source_profile=_input_profile(
            accepted_formats=("docx", "markdown"),
            structured_formats=("json",),
            markdown_policy="preview_and_cleanup",
            latex_policy="formula_fragments_only",
            material_schema_id="thesis_school_rule_context_v1",
            material_schema_ids=("thesis_school_rule_context_v1",),
        ),
        compliance_profile=_compliance_profile(
            "thesis_cn",
            rule_family="academic_thesis",
            count_profile_id="school_thesis",
            check_scopes=(
                "abstract_cn", "abstract_en", "body", "references",
                "tables", "figures", "appendix",
            ),
            report_level="detailed",
        ),
        delivery_presets=[
            _delivery_preset("final", "Final manuscript", template_id="thesis_gbt"),
            _delivery_preset(
                "review",
                "Review copy",
                template_id="thesis_gbt",
                compare_docx=True,
                structured=True,
                report_level="detailed",
            ),
            _delivery_preset(
                "compliance_report",
                "Compliance report",
                template_id="thesis_gbt",
                final_docx=False,
                report_level="detailed",
            ),
        ],
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
        input_source_profile=_input_profile(
            accepted_formats=("docx", "xlsx"),
            structured_formats=("json", "xlsx"),
            markdown_policy="disabled",
            latex_policy="disabled",
            require_material_package=True,
            material_schema_id="bid_materials_v1",
            required_material_fields=("company_name", "project_name", "legal_person"),
            required_image_roles=("logo", "seal"),
            failure_policy="block",
        ),
        compliance_profile=_compliance_profile(
            "bid_package",
            rule_family="bidding_materials",
            check_scopes=("body", "toc", "tables", "figures", "attachments"),
            report_level="detailed",
            failure_policy="block",
            preservation_mode="strict",
            block_on=("macros", "ole_objects"),
        ),
        delivery_presets=[
            _delivery_preset("original", "Original copy", template_id="bid_engineering"),
            _delivery_preset("copy", "Duplicate copy", template_id="bid_engineering"),
            _delivery_preset(
                "package_report",
                "Package report",
                template_id="bid_engineering",
                final_docx=False,
                material_manifest=True,
                material_package=True,
                report_level="detailed",
            ),
        ],
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
        input_source_profile=_input_profile(
            accepted_formats=("docx",),
            structured_formats=("json",),
            markdown_policy="disabled",
            latex_policy="disabled",
            require_material_package=True,
            material_schema_id="official_document_v1",
            required_material_fields=("organization", "document_no", "issue_date"),
            failure_policy="warn",
        ),
        compliance_profile=_compliance_profile(
            "official_document",
            rule_family="official_document",
            check_scopes=("body", "headers_footers", "metadata"),
            failure_policy="warn",
            preservation_mode="warn",
        ),
        delivery_presets=[
            _delivery_preset("formal", "Formal copy", template_id="official_gbt"),
            _delivery_preset(
                "internal_review",
                "Internal review",
                template_id="official_gbt",
                compare_docx=True,
            ),
        ],
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
        input_source_profile=_input_profile(
            accepted_formats=("docx", "markdown"),
            structured_formats=("json",),
            markdown_policy="preview_and_cleanup",
            latex_policy="formula_fragments_only",
            material_schema_id="technical_document_v1",
            required_image_roles=("diagram", "figure"),
        ),
        compliance_profile=_compliance_profile(
            "long_document_publishing",
            rule_family="long_document_structure",
            check_scopes=("body", "toc", "tables", "figures", "appendix"),
            report_level="detailed",
            preservation_mode="strict",
            block_on=("macros", "ole_objects", "embedded_workbooks"),
        ),
        default_delivery_preset_id="final_docx",
        delivery_presets=[
            _delivery_preset(
                "review_copy",
                "Review copy",
                template_id="tech_standard",
                compare_docx=True,
                structured=True,
                output_dir_template="technical/{preset_id}",
            ),
            _delivery_preset(
                "proof_copy",
                "Proof copy",
                template_id="tech_standard",
                compare_docx=True,
                structured=True,
                report_level="detailed",
                output_dir_template="technical/{preset_id}",
            ),
            _delivery_preset(
                "final_docx",
                "Final DOCX",
                template_id="tech_standard",
                output_dir_template="technical/{preset_id}",
            ),
            _delivery_preset(
                "archive_package",
                "Archive package",
                template_id="tech_standard",
                final_docx=False,
                material_manifest=True,
                material_package=True,
                structured=True,
                report_level="detailed",
                output_dir_template="technical/{preset_id}",
            ),
        ],
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
        input_source_profile=_input_profile(
            accepted_formats=("docx", "markdown"),
            structured_formats=("json",),
            markdown_policy="preview_and_cleanup",
            latex_policy="disabled",
        ),
        compliance_profile=_compliance_profile(
            "general_report",
            rule_family="basic_report",
            check_scopes=("body", "toc", "tables", "figures"),
            preservation_mode="warn",
        ),
        delivery_presets=[
            _delivery_preset("final", "Final report", template_id="report_default"),
            _delivery_preset(
                "review",
                "Review copy",
                template_id="report_default",
                compare_docx=True,
            ),
        ],
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
        scene_id="exam",
        name="试卷",
        description="Markdown 或 Word 题目装配成完整试卷",
        default_template_id="default",
        compatible_templates=(
            TemplateMeta("default", "默认格式"),
        ),
    ),
    SceneMeta(
        scene_id="thesis",
        name="论文排版",
        description="中文学位论文·课程论文·综述·开题",
        default_template_id="thesis_gbt",
        compatible_templates=(
            TemplateMeta("thesis_gbt", "GB/T 7713 学位论文"),
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
    "exam": create_exam_scene,
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
    boundary_text = _scene_application_boundary_summary(scene)

    enabled_groups = []
    for group in UI_CAPABILITY_GROUPS:
        if get_group_enabled(scene, group):
            enabled_groups.append(group.label)

    cap_count = len(enabled_groups)
    features_text = "·".join(enabled_groups) if enabled_groups else "无"
    return (
        f"{strategy_text} · 处理范围：{boundary_text} · "
        f"{cap_count}项功能（{features_text}） · {build_scene_profile_summary(scene)} · "
        f"{build_scene_parameter_ownership_summary(scene)} · "
        f"{build_scene_control_contract_summary()} · "
        f"{build_scene_product_readiness_summary(scene)} · "
        f"{build_scene_sample_coverage_summary_text(scene)} · "
        f"{build_scene_request_cell_summary_text(scene)}"
    )


def _scene_application_boundary_summary(scene: SceneWorkspace) -> str:
    labels = {
        "follow_template": "按模板默认",
        "body_only": "只处理正文",
        "full_document": "处理全文",
        "confirm_before_apply": "每次执行前选择",
    }
    boundary = scene_application_boundary_for_runtime(scene)
    return labels.get(boundary.mode, "按模板默认")


def build_scene_profile_summary(scene: SceneWorkspace) -> str:
    """Build a compact profile summary shared by Workbench scene surfaces."""
    input_formats = _join_summary_values(scene.input_source_profile.accepted_formats)
    compliance = scene.compliance_profile.profile_id or "basic"
    default_delivery = scene.default_delivery_preset_id or (
        scene.delivery_presets[0].preset_id if scene.delivery_presets else "final"
    )
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


def build_scene_parameter_ownership_summary(scene: SceneWorkspace) -> str:
    """Build a compact parameter ownership summary for Workbench surfaces."""
    audit = audit_scene_parameter_ownership(scene.__class__)
    status = "已守门" if audit.is_clean else f"{_ownership_issue_count(audit)}个缺口"
    layers = _ownership_layer_compact_text()
    return f"参数归属{status}（{layers}）"


def build_scene_control_contract_summary() -> str:
    """Build a compact control-contract summary for Workbench surfaces."""

    audit = audit_control_contract_registry()
    status = "已守门" if audit.is_clean else f"{_control_contract_issue_count(audit)}个缺口"
    return f"控件契约{status}（{_control_contract_layer_compact_text()}）"


def build_scene_sample_coverage_summary_text(scene: SceneWorkspace) -> str:
    """Build a compact DOCX sample coverage summary for Workbench surfaces."""

    packs = _coverage_packs_for_scene_context(scene)
    if not packs:
        return "样本覆盖未归属"
    summary = build_scene_sample_coverage_summary([pack.pack_id for pack in packs])
    issue_count = len(summary.missing_pack_ids) + len(summary.audit_issues)
    status = "已守门" if summary.is_clean else f"{issue_count}个缺口"
    manual = (
        f"/{len(summary.manual_gate_ids)}人工确认"
        if summary.manual_gate_ids
        else ""
    )
    return (
        f"样本覆盖{status}（"
        f"{len(summary.fixture_ids)}样本/"
        f"{len(summary.docx_surfaces)}类OOXML{manual}"
        "）"
    )


def build_scene_request_cell_summary_text(scene: SceneWorkspace) -> str:
    """Build a compact request-cell fixture summary for Workbench surfaces."""

    packs = _coverage_packs_for_scene_context(scene)
    if not packs:
        return "常见说法未归属"
    summary = build_scene_request_cell_fixture_summary(
        [pack.pack_id for pack in packs]
    )
    issue_count = len(summary.audit_issues)
    release_clean = (
        summary.is_clean
        and summary.family_proxy_count == 0
        and (
            summary.fixture_cell_count + summary.negative_control_count
            == summary.cell_count
        )
    )
    status = "已守门" if release_clean else f"{issue_count}个缺口"
    boundary = ""
    if summary.manual_boundary_count or summary.ambiguous_count:
        boundary = (
            f"/{summary.manual_boundary_count}人工确认"
            f"/{summary.ambiguous_count}容易误解"
        )
    return (
        f"常见说法{status}（"
        f"{summary.cell_count}请求/"
        f"{summary.fixture_cell_count}证据/"
        f"{summary.family_proxy_count}借用{boundary}"
        "）"
    )


def build_scene_product_readiness_summary(scene: SceneWorkspace) -> str:
    """Build a compact product-readiness summary for Workbench surfaces."""

    specs = _product_readiness_specs_for_scene_context(scene)
    if not specs:
        return "产品成熟度未登记"
    levels = _unique_summary_values(
        [spec.product_readiness_level for spec in specs if spec.product_readiness_level]
    )
    level_text = "/".join(_product_readiness_label(level) for level in levels)
    static_closed = sum(1 for spec in specs if spec.static_closure_level == "closed")
    non_green = sum(1 for spec in specs if not spec.is_green)
    gap_count = sum(len(spec.remaining_product_gaps) for spec in specs)
    return (
        f"产品成熟度{level_text}"
        f"（static闭合{static_closed}/非Green{non_green}/缺口{gap_count}）"
    )


def _control_contract_layer_compact_text() -> str:
    counts = Counter(contract.owner_layer for contract in list_control_contracts())
    layers = [
        layer
        for layer in ALLOWED_CONTROL_OWNER_LAYERS
        if counts.get(layer, 0)
    ]
    return "/".join(layers) if layers else "未登记"


def _control_contract_issue_count(audit: ControlContractAuditResult) -> int:
    return (
        len(audit.missing_required_contracts)
        + len(audit.invalid_owner_layers)
        + len(audit.missing_paired_contracts)
        + len(audit.missing_evidence_files)
        + len(audit.missing_evidence_markers)
    )


def _ownership_layer_compact_text() -> str:
    counts = Counter(
        spec.owner_layer for spec in scene_parameter_ownership_specs().values()
    )
    layers = [
        layer
        for layer in ALLOWED_PARAMETER_OWNER_LAYERS
        if counts.get(layer, 0)
    ]
    return "/".join(layers) if layers else "未登记"


def _ownership_issue_count(audit: ParameterOwnershipAuditResult) -> int:
    return (
        len(audit.missing_top_level_paths)
        + len(audit.missing_required_paths)
        + len(audit.unknown_spec_paths)
        + len(audit.invalid_owner_layers)
    )


def _coverage_packs_for_scene_context(
    scene: SceneWorkspace,
) -> tuple[SceneCoveragePack, ...]:
    return coverage_packs_for_config(scene)


def _product_readiness_specs_for_scene_context(
    scene: SceneWorkspace,
) -> tuple[SceneProductReadinessSpec, ...]:
    specs: list[SceneProductReadinessSpec] = []
    seen: set[tuple[str, str]] = set()
    for pack in _coverage_packs_for_scene_context(scene):
        _append_product_readiness_spec(specs, seen, "pack", pack.pack_id)
    for candidate in coverage_candidate_keys_for_config(scene):
        _append_product_readiness_spec(specs, seen, "family", candidate)
    return tuple(specs)


def _append_product_readiness_spec(
    specs: list[SceneProductReadinessSpec],
    seen: set[tuple[str, str]],
    subject_type: str,
    subject_id: str,
) -> None:
    normalized = str(subject_id or "").strip()
    if not normalized:
        return
    key = (subject_type, normalized)
    if key in seen:
        return
    try:
        spec = product_readiness_for(normalized, subject_type=subject_type)
    except KeyError:
        return
    specs.append(spec)
    seen.add(key)


def _product_readiness_label(level: str) -> str:
    return {
        "gray_l1": "Gray/L1",
        "blue_boundary": "Blue/Boundary",
        "yellow_l3": "Yellow/L3",
        "orange_l4": "Orange/L4",
        "green_l5": "Green/L5",
    }.get(str(level or "").strip(), str(level or "").strip() or "未登记")


def _unique_summary_values(values: Sequence[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def _join_summary_values(values: Sequence[object]) -> str:
    normalized = [str(value or "").strip() for value in values if str(value or "").strip()]
    return "/".join(normalized) if normalized else "无"
