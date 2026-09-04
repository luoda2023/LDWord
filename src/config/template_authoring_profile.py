"""Reusable contracts for AI-assisted template authoring.

This registry is the authoring boundary: it declares which top-level roots an AI template
workflow may change, which roots must remain frozen, and which document facts
belong to masters, scenes, or materials instead of a reusable format template.

Nothing in this module performs imports or mutates the template library.  It is
deliberately a small, dependency-light source of truth.  Work modes opt into
one profile by stable id; the product may add, remove, hide, or reorder modes
without changing the profile registry or any physical workspace path.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.work_mode import get_work_mode


TEMPLATE_AUTHORABLE_ROOTS: tuple[str, ...] = (
    "page_setup",
    "styles",
    "heading_numbering",
    "heading_model",
    "section",
    "table",
    "header_footer",
    "toc",
    "caption",
)

TEMPLATE_FROZEN_ROOTS: tuple[str, ...] = (
    "reference_style",
    "watermark",
)


@dataclass(frozen=True, slots=True)
class TemplateAuthoringProfile:
    """A reusable AI-template authoring contract.

    Work modes opt into a profile by stable ``profile_id``.  The profile has
    no storage identity of its own and may therefore be shared by future work
    modes with the same authoring boundary.
    """

    profile_id: str
    authorable_roots: tuple[str, ...]
    frozen_roots: tuple[str, ...]
    required_style_roles: tuple[str, ...]
    master_boundaries: tuple[str, ...]
    scene_boundaries: tuple[str, ...]
    material_boundaries: tuple[str, ...]
    version: int

_PROFILES: tuple[TemplateAuthoringProfile, ...] = (
    TemplateAuthoringProfile(
        profile_id="template_authoring.custom.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=("body", "heading"),
        master_boundaries=(
            "固定封面、占位符、浮动对象和精确页面骨架属于 general_master 母版，不写入排版模板。",
        ),
        scene_boundaries=(
            "处理范围、模块开关、清理策略、风险策略和交付行为属于通用方案。",
        ),
        material_boundaries=(
            "每份文档变化的正文、名称、日期、图片和附件属于运行资料，不固化到模板。",
        ),
        version=2,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.exam.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=("body", "heading"),
        master_boundaries=(
            "default_exam 母版拥有试卷标题区、考生信息栏、注意事项、题目区、答题区和固定占位符。",
            "学生卷、答案卷的固定页面结构不能用页眉、表格或正文样式模拟。",
        ),
        scene_boundaries=(
            "题目装配方式、答案策略、学生版/教师版交付以及执行模块属于试卷方案。",
        ),
        material_boundaries=(
            "exam_items_v1 的科目、年级、时长、总分、题目、答案和题图属于试卷资料。",
        ),
        version=2,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.thesis.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=(
            "body",
            "heading",
            "heading1",
            "heading2",
            "heading3",
            "abstract_body",
            "toc_title",
            "toc_level1",
            "toc_level2",
            "references_body",
            "caption",
        ),
        master_boundaries=(
            "论文封面表单、校徽、原创声明、授权页、签字区和固定分节骨架属于 thesis_master 母版。",
        ),
        scene_boundaries=(
            "章节处理范围、引用链接、公式编号策略、参考文献规则和交付版本属于论文方案。",
        ),
        material_boundaries=(
            "学校、院系、专业、学生、导师、日期、摘要正文和关键词等逐篇变化内容属于论文资料。",
        ),
        version=2,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.bidding.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=(
            "body",
            "heading",
            "heading1",
            "heading2",
            "heading3",
            "toc_title",
            "toc_level1",
            "toc_level2",
            "caption",
        ),
        master_boundaries=(
            "标书封面、资格审查固定表、签章位置、固定目录骨架和精确版面区域属于 bidding_master 母版。",
        ),
        scene_boundaries=(
            "工程标、采购标的装配范围、资料要求、批处理和交付策略属于标书方案。",
        ),
        material_boundaries=(
            "bid_materials_v1 的公司、项目、法人、日期、地址、Logo、印章和资质文件属于标书资料。",
        ),
        version=2,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.official.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=("body", "heading"),
        master_boundaries=(
            "official_gbt_standard、official_gbt_upward、official_gbt_letter、official_gbt_minutes 和 official_gbt_order 母版拥有红头、红线、版记、签发区及精确占位结构。",
            "通知、请示、报告、批复、函和纪要的固定结构差异由公文母版族表达。",
        ),
        scene_boundaries=(
            "公文文种路由、母版选择、处理能力、执行安全与正式/审阅交付属于公文方案。",
        ),
        material_boundaries=(
            "official_document_v1 与 administrative_meeting_fields_v1 的机构、文号、收文对象、签发人、日期、会议字段和印章属于公文资料。",
        ),
        version=2,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.technical.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=("body", "heading"),
        master_boundaries=(
            "技术文档封面、修订记录表、固定元数据区、图纸锚点和章节骨架属于 technical_master 母版。",
        ),
        scene_boundaries=(
            "索引与附录范围、复杂对象保护、处理模块、风险降级和交付策略属于技术文档方案。",
        ),
        material_boundaries=(
            "technical_document_v1 的标题、版本、负责人、源文件清单、技术图和普通插图属于技术资料。",
        ),
        version=2,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.engineering.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=("body", "heading"),
        master_boundaries=(
            "工程封面、固定表格骨架（如指标汇总表、工程量清单）、固定分节骨架与盖章区属于 engineering_master 母版。",
            "可研/施组/专项方案/交底/合同/结算/概算的行业章节骨架由各阶段大纲与母版表达，不写入排版模板。",
        ),
        scene_boundaries=(
            "决策/设计/交易/实施/竣工结算/贯穿造价分析六阶段切换、资料要求、批量与交付策略属于工程方案。",
        ),
        material_boundaries=(
            "engineering_document_v1 的项目名称、地点、规模、阶段、文种、投资估算、信息价与参考文件等逐项目变化内容属于工程资料。",
        ),
        version=1,
    ),
    TemplateAuthoringProfile(
        profile_id="template_authoring.report.v1",
        authorable_roots=TEMPLATE_AUTHORABLE_ROOTS,
        frozen_roots=TEMPLATE_FROZEN_ROOTS,
        required_style_roles=("body", "heading"),
        master_boundaries=(
            "报告封面、固定信息区、仪表板或固定表格骨架属于 report_master 母版。",
        ),
        scene_boundaries=(
            "报告处理范围、检查规则、交付版本和输出产物属于报告方案。",
        ),
        material_boundaries=(
            "报告标题、作者、日期、业务数据、图表数据和附件属于逐份报告资料。",
        ),
        version=2,
    ),
)

_PROFILE_BY_ID: dict[str, TemplateAuthoringProfile] = {
    profile.profile_id: profile for profile in _PROFILES
}


def list_template_authoring_profiles() -> tuple[TemplateAuthoringProfile, ...]:
    """Return reusable authoring profiles in registry order."""

    return _PROFILES


def get_template_authoring_profile_by_id(
    profile_id: str,
) -> TemplateAuthoringProfile | None:
    """Resolve a profile only by its stable contract identity."""

    return _PROFILE_BY_ID.get(str(profile_id or "").strip())


def get_template_authoring_profile(
    profile_or_mode_id: str,
) -> TemplateAuthoringProfile | None:
    """Resolve a profile by profile id or a work-mode id/label/alias."""

    key = str(profile_or_mode_id or "").strip()
    direct = get_template_authoring_profile_by_id(key)
    if direct is not None:
        return direct

    mode = get_work_mode(key)
    if mode is None:
        return None
    return get_template_authoring_profile_by_id(
        str(mode.template_authoring_profile_id or "")
    )


__all__ = [
    "TEMPLATE_AUTHORABLE_ROOTS",
    "TEMPLATE_FROZEN_ROOTS",
    "TemplateAuthoringProfile",
    "get_template_authoring_profile",
    "get_template_authoring_profile_by_id",
    "list_template_authoring_profiles",
]
