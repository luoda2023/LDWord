"""Capability-driven Assistant planning without UI-owned mode branches."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass

from src.assistant.application.request_semantics import (
    is_semantic_revision_request,
)
from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    ARTIFACT_KIND_EXISTING_DOCUMENT,
    ARTIFACT_KIND_NARRATIVE,
    ARTIFACT_KIND_OFFICIAL,
    CAPABILITY_EXECUTABLE,
    CAPABILITY_GATED,
    CAPABILITY_PLANNED,
    SOURCE_ROLE_PRODUCTION_INPUT,
    SOURCE_ROLE_STRUCTURED_SOURCE,
    TASK_OPERATION_AUTHOR,
    TASK_OPERATION_AUTHOR_MASTER,
    TASK_OPERATION_BATCH,
    TASK_OPERATION_IMPORT,
    TASK_OPERATION_REVIEW,
    TASK_OPERATION_TRANSFORM,
    DeliveryContract,
    GenerationContract,
    ProductionContract,
    TaskCapabilityRef,
)
from src.assistant.domain.docx_format_evidence import (
    is_format_requirements_request,
)
from src.config.library import load_scene_from_library
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.config.scene_natural_request_router import (
    NaturalRequestRoute,
    list_natural_request_routes,
)
from src.config.work_mode import WorkModeSpec, get_work_mode
from src.shared.engine.exam_paper_style import EXAM_MARKDOWN_AUTHORING_PROMPT

NARRATIVE_PROMPT_PROFILE_ID = "assistant.narrative-markdown.v1"
EXAM_PROMPT_PROFILE_ID = "assistant.exam-paper-markdown.v1"
BIDDING_PROMPT_PROFILE_ID = "assistant.bidding-markdown.v1"
OFFICIAL_PROMPT_PROFILE_ID = "assistant.official-document-json.v1"
ENGINEERING_PROMPT_PROFILE_ID = "assistant.engineering-document-markdown.v1"

_NARRATIVE_SYSTEM_PROMPT = (
    "你是文档内容起草助手。输出 UTF-8 Markdown 正文，不要输出解释、代码围栏、"
    "OOXML、DOCX 或 base64。使用清晰标题、段落、列表和简单表格；不要虚构引用。"
)
_BIDDING_SYSTEM_PROMPT = (
    "你是投标文件正文起草助手。仅根据用户明确提供的项目与企业资料生成 UTF-8 "
    "Markdown 正文，不要输出解释、代码围栏、OOXML、DOCX 或 base64。使用清晰的"
    "一级、二级标题组织封面信息、项目理解、响应内容、实施方案和承诺事项；不得虚构"
    "资质、业绩、报价、证书编号或法律结论，缺失事实必须用“待补充”明确标记。"
    "企业名称、项目名称、法定代表人必须分别保留为 {{@text:company_name}}、"
    "{{@text:project_name}}、{{@text:legal_person}}。不要输出 @img Token 或 Markdown "
    "图片；企业标志和公章槽位由 Form 在内容编译完成后从资料包本地确定性装配。"
)
_ENGINEERING_SYSTEM_PROMPT = (
    "你是工程文档写作专家。按用户给定的项目阶段与文档类型，仅根据用户明确提供的项目资料生成 UTF-8 Markdown 正文，"
    "不要输出解释、代码围栏、OOXML、DOCX 或 base64。严格按照工程行业章节习惯组织内容："
    "决策立项阶段用项目建议书/可行性研究报告/投资估算结构；设计报批阶段用初步设计说明/设计概算/施工图说明；"
    "招投标与合同阶段用招标/投标/合同示范文本结构；施工实施阶段用施工组织设计/专项施工方案/技术交底/工艺标准结构；"
    "竣工结算阶段用工程结算书/结算审计/签证索赔结构；贯穿阶段用造价分析/目标成本测算结构。"
    "章节编号遵循行业惯例（章用第X章或第一部分，节用 x.x，条目用 1）2）等）。"
    "项目名称、地点、规模、投资额、建设单位、设计单位等必须以 {{@text:project_name}}、{{@text:project_location}}、"
    "{{@text:project_scale}}、{{@text:invest_estimate}}、{{@text:owner_org}}、{{@text:design_org}} 等占位形式保留待填槽位，"
    "不得虚构具体数值、图纸编号、审批文号、价格、资质或法律结论；缺失事实用“待补充”明确标记。"
    "不得输出 @img Token 或 Markdown 图片，图表由 Form 从资料包本地装配。"
    "若用户未说明工程阶段或文档类型，先输出最合适的默认大纲并提示确认，不要臆造项目事实。"
)
_OFFICIAL_SYSTEM_PROMPT = (
    "你是公文内容起草与材料抽取助手。只输出一个 UTF-8 JSON 对象，不要输出解释、"
    "Markdown 代码围栏、OOXML、DOCX 或 base64。JSON 顶层必须包含 fields 对象；"
    "fields 可使用 title、body、organization、document_no、issue_date、recipient、"
    "issuer、signer、attachment_note、copy_scope、printing_org、printing_date、"
    "meeting_date、participants。严格优先使用用户请求和已授权材料中的事实。"
    "title 和 body 可以依据材料拟写；未明确的发文机关、文号、签发人等正式事实必须"
    "填 null，不得猜测或编造。正文应完整、可审阅，使用纯文本换行，不要嵌套对象。"
)

# These routes have a real first-level work mode and a production runtime today.
# All other route definitions remain visible as planned/gated capabilities instead
# of silently falling back to the generic document workflow.
_ROUTE_MODE_IDS: dict[str, str] = {
    "quick_formatting_general": "custom",
    "quick_bilingual_formatting": "custom",
    "personal_career_formatting": "custom",
    "chinese_academic_thesis": "thesis",
    "english_journal_submission": "thesis",
    "exam_teaching_versions": "exam",
    "bidding_document_authoring": "bidding",
    "bidding_qualification_archive": "bidding",
    "official_policy_documents": "official",
    "technical_long_document": "technical",
    "engineering_document_authoring": "engineering",
    "project_application_package": "report",
}
_CLOSED_ROUTE_IDS = frozenset(
    {
        "quick_formatting_general",
        "quick_bilingual_formatting",
        "personal_career_formatting",
        "chinese_academic_thesis",
        "exam_teaching_versions",
        "bidding_document_authoring",
        "bidding_qualification_archive",
        "official_policy_documents",
        "technical_long_document",
        "engineering_document_authoring",
    }
)

_AUTHORING_MODE_IDS = frozenset(
    {"custom", "exam", "thesis", "technical", "report", "bidding", "official", "engineering"}
)
_EXAM_DELIVERY = DeliveryContract(
    default_preset_id="student",
    preset_ids=("student", "answer"),
    required_artifact_keys=("student", "answer_key"),
)

AUTHORING_ACTION_HINTS = (
    "生成",
    "撰写",
    "起草",
    "写一个",
    "写一份",
    "写一篇",
    "写篇",
    "写个",
    "写份",
    "写封",
    "写张",
    "写套",
    "帮我写",
    "给我写",
    "替我写",
    "做一份",
    "做份",
    "做张",
    "做套",
    "做个",
    "制作",
    "新建",
    "创建",
    "创作",
    "命题",
    "出题",
    "出一份",
    "出一套",
    "出份",
    "出套",
    "出张",
    "组一份",
    "组一套",
    "组份",
    "组套",
    "编写",
    "编制",
    "设计一份",
    "准备一份",
    "拟一份",
    "拟一个",
    "拟个",
    "来一份",
    "来一个",
    "来个",
    "来份",
    "来套",
    "来张",
    "整一份",
    "整份",
    "整一个",
    "整套",
    "弄一份",
    "弄份",
    "弄一个",
    "弄一套",
    "弄套",
    "重新做一版",
    "重做一版",
    "给我一份",
    "我想要一份",
    "我要一份",
)
_OFFICIAL_AUTHORING_ACTION_HINTS = (
    "发一个",
    "发一份",
    "发个",
    "发份",
    "发布",
    "下发",
    "印发",
    "出一个",
    "出一份",
    "出个",
    "做个",
)
_OFFICIAL_DOCUMENT_OBJECT_HINTS = (
    "公文",
    "决议",
    "决定",
    "命令",
    "公报",
    "公告",
    "通告",
    "意见",
    "通知",
    "通报",
    "请示",
    "报告",
    "函",
    "批复",
    "议案",
    "纪要",
)
_TRANSFER_TO_ASSISTANT_HINTS = (
    "发给你",
    "发送给你",
    "传给你",
    "给你",
    "上传",
)
_TRANSFER_REVIEW_HINTS = (
    "看看",
    "分析",
    "检查",
    "审阅",
    "审校",
    "评估",
    "修改",
    "润色",
    "完善",
)
_AUTHORING_NEGATION_PREFIXES = (
    "不要",
    "不用",
    "无需",
    "不需要",
    "别",
    "不想",
    "不打算",
    "没必要",
    "没有必要",
    "没说",
    "没有说",
)
_AUTHORING_ADVISORY_HINTS = (
    "有没有必要",
    "是否需要",
    "需不需要",
    "要不要",
    "假设",
    "想了解",
    "需要准备什么",
)
_CLAUSE_SPLIT_RE = re.compile(r"[\s,，。；;！!？?\n]+")
_CONTEXTUAL_AUTHORING_PATTERNS = (
    re.compile(r"(?:^|我|我们|咱们|本人).{0,12}(?:想|要|需要|准备|打算)写"),
    re.compile(r"(?:有|有个|有份|有一份|有一个).{0,12}要写"),
    re.compile(r"^(?:请)?(?:想|要|需要|准备|打算)写"),
)


@dataclass(frozen=True, slots=True)
class ResolvedAssistantCapability:
    ref: TaskCapabilityRef
    mode_id: str
    scene_id: str
    template_id: str
    operation: str
    generation: GenerationContract
    production: ProductionContract
    delivery: DeliveryContract
    executable: bool
    blocking_reason: str = ""


def classify_task_operation(query: str) -> str:
    normalized = " ".join(str(query or "").casefold().split())
    if is_format_requirements_request(normalized):
        return TASK_OPERATION_REVIEW
    if any(token in normalized for token in ("批量", "每一份", "每个人", "每条记录")):
        return TASK_OPERATION_BATCH
    if any(
        token in normalized for token in ("pdf转", "ocr", "扫描件", "latex转", "导入")
    ):
        return TASK_OPERATION_IMPORT
    if any(token in normalized for token in ("母版", "卷面")) and any(
        token in normalized for token in ("生成", "创建", "改造", "制作")
    ):
        return TASK_OPERATION_AUTHOR_MASTER
    if _requests_authoring(normalized):
        return TASK_OPERATION_AUTHOR
    if any(
        token in normalized
        for token in (
            "检查",
            "审阅",
            "审校",
            "合规",
            "诊断",
            "分析",
            "评估",
        )
    ):
        return TASK_OPERATION_REVIEW
    return TASK_OPERATION_TRANSFORM


def _requests_authoring(normalized: str) -> bool:
    """Resolve authoring per clause so one negation cannot poison another task."""

    for clause in _CLAUSE_SPLIT_RE.split(normalized):
        if not clause:
            continue
        if any(marker in clause for marker in _AUTHORING_ADVISORY_HINTS):
            continue
        if any(
            pattern.search(clause) for pattern in _CONTEXTUAL_AUTHORING_PATTERNS
        ) and not _whole_clause_negates_authoring(clause):
            return True
        official_object = any(
            token in clause for token in _OFFICIAL_DOCUMENT_OBJECT_HINTS
        )
        for token in AUTHORING_ACTION_HINTS:
            start = clause.find(token)
            while start >= 0:
                if not _authoring_action_is_negated(
                    clause, start
                ) and not _is_attachment_transfer_action(clause, token):
                    return True
                start = clause.find(token, start + 1)
        if not official_object:
            continue
        for token in _OFFICIAL_AUTHORING_ACTION_HINTS:
            start = clause.find(token)
            while start >= 0:
                if not _authoring_action_is_negated(
                    clause, start
                ) and not _is_attachment_transfer_action(clause, token):
                    return True
                start = clause.find(token, start + 1)
    return False


def _whole_clause_negates_authoring(clause: str) -> bool:
    action_index = min(
        (
            index
            for marker in ("写", "生成", "制作", "创建", "起草")
            if (index := clause.find(marker)) >= 0
        ),
        default=len(clause),
    )
    return _authoring_action_is_negated(clause, action_index)


def _authoring_action_is_negated(clause: str, start: int) -> bool:
    prefix = clause[max(0, start - 10) : start]
    if prefix.endswith(_AUTHORING_NEGATION_PREFIXES):
        return True
    # ``要写`` used to match the tail of ``必要写``.  Keep that advisory
    # construction out of the authoring path without rejecting ``我要写``.
    return bool(start > 0 and clause[start - 1] == "必")


def _is_attachment_transfer_action(clause: str, token: str) -> bool:
    if not token.startswith("发"):
        return False
    return bool(
        any(marker in clause for marker in _TRANSFER_TO_ASSISTANT_HINTS)
        and any(marker in clause for marker in _TRANSFER_REVIEW_HINTS)
    )


def resolve_assistant_capability(
    *,
    route: NaturalRequestRoute | None,
    workspace_mode_id: str,
    operation: str,
    query: str = "",
) -> ResolvedAssistantCapability:
    route_id = route.route_id if route is not None else ""
    if (
        route_id == "bidding_qualification_archive"
        and operation == TASK_OPERATION_AUTHOR
    ):
        # “生成归档清单/ZIP” describes archive delivery, not AI-authored
        # document content. Keep this closed route on the deterministic
        # transform pipeline even when the request contains “生成”.
        operation = TASK_OPERATION_TRANSFORM
    configured_mode_id = _ROUTE_MODE_IDS.get(route_id, "")
    mode_id = configured_mode_id or str(workspace_mode_id or "custom")
    mode = get_work_mode(mode_id) or get_work_mode("custom")
    if mode is None:  # pragma: no cover - protected by work-mode registry tests.
        raise RuntimeError("assistant_default_work_mode_unavailable")

    route_type = route.route_type if route is not None else "workspace"
    family_id = route.family_id if route is not None else ""
    profile_id = route.profile_id if route is not None else ""
    gate_id = route.plugin_gate_id if route is not None else ""
    status = _capability_status(route, configured_mode_id)
    capability_id = _capability_id(route_id, mode.mode_id, operation)
    generation = _generation_contract(
        mode.mode_id,
        operation,
        route_id=route_id,
        semantic_revision=is_semantic_revision_request(query),
    )
    production = _production_contract(
        mode,
        operation,
        generation_required=generation.required,
    )
    delivery = _delivery_contract(mode, route=route)

    blocking_reason = ""
    executable = status == CAPABILITY_EXECUTABLE
    if executable and operation == TASK_OPERATION_AUTHOR and not generation.required:
        executable = False
        status = CAPABILITY_PLANNED
        blocking_reason = (
            f"assistant_authoring_not_closed:{mode.mode_id}:"
            "structured_generation_adapter_required"
        )
    elif executable and operation in {
        TASK_OPERATION_BATCH,
        TASK_OPERATION_IMPORT,
        TASK_OPERATION_AUTHOR_MASTER,
    }:
        executable = False
        status = CAPABILITY_PLANNED
        blocking_reason = f"assistant_operation_not_closed:{operation}"
    elif status == CAPABILITY_GATED:
        blocking_reason = f"assistant_capability_gate_required:{gate_id or route_type}"
    elif status == CAPABILITY_PLANNED:
        blocking_reason = f"assistant_capability_not_executable:{route_id or family_id}"
    if not executable:
        generation = GenerationContract()

    return ResolvedAssistantCapability(
        ref=TaskCapabilityRef(
            capability_id=capability_id,
            route_id=route_id,
            family_id=family_id,
            profile_id=profile_id,
            route_type=route_type,
            status=status,
            gate_id=gate_id,
        ),
        mode_id=mode.mode_id,
        scene_id=mode.default_scene_id,
        template_id=mode.default_template_id,
        operation=operation,
        generation=generation,
        production=production,
        delivery=delivery,
        executable=executable,
        blocking_reason=blocking_reason,
    )


def system_prompt_for_profile(profile_id: str) -> str:
    target = str(profile_id or "").strip()
    if target == EXAM_PROMPT_PROFILE_ID:
        return EXAM_MARKDOWN_AUTHORING_PROMPT
    if target == BIDDING_PROMPT_PROFILE_ID:
        return _BIDDING_SYSTEM_PROMPT
    if target == OFFICIAL_PROMPT_PROFILE_ID:
        return _OFFICIAL_SYSTEM_PROMPT
    if target == ENGINEERING_PROMPT_PROFILE_ID:
        return _ENGINEERING_SYSTEM_PROMPT
    if target in {"", NARRATIVE_PROMPT_PROFILE_ID}:
        return _NARRATIVE_SYSTEM_PROMPT
    raise ValueError(f"assistant_prompt_profile_unknown:{target}")


def capability_route_coverage() -> dict[str, str]:
    """Return every registered route with its non-silent capability status."""

    coverage: dict[str, str] = {}
    for route in list_natural_request_routes():
        resolution = resolve_assistant_capability(
            route=route,
            workspace_mode_id="custom",
            operation=TASK_OPERATION_TRANSFORM,
        )
        coverage[route.route_id] = resolution.ref.status
    return coverage


def _capability_status(
    route: NaturalRequestRoute | None,
    configured_mode_id: str,
) -> str:
    if route is None:
        return CAPABILITY_EXECUTABLE
    if configured_mode_id and route.route_id in _CLOSED_ROUTE_IDS:
        return CAPABILITY_EXECUTABLE
    if route.route_type in {
        "professional_boundary",
        "plugin_manual_boundary",
        "import_boundary",
    }:
        return CAPABILITY_GATED
    return CAPABILITY_PLANNED


def _capability_id(route_id: str, mode_id: str, operation: str) -> str:
    owner = route_id or f"mode-{mode_id}"
    return f"assistant.{owner}.{operation}.v1"


def _generation_contract(
    mode_id: str,
    operation: str,
    *,
    route_id: str = "",
    semantic_revision: bool = False,
) -> GenerationContract:
    if mode_id not in _AUTHORING_MODE_IDS or (
        operation != TASK_OPERATION_AUTHOR
        and not (operation == TASK_OPERATION_TRANSFORM and semantic_revision)
    ):
        return GenerationContract()
    if mode_id == "exam":
        return GenerationContract(
            required=True,
            artifact_kind=ARTIFACT_KIND_EXAM,
            prompt_profile_id=EXAM_PROMPT_PROFILE_ID,
            validator_id="exam_items_v1",
        )
    if mode_id == "bidding":
        if route_id != "bidding_document_authoring":
            return GenerationContract()
        return GenerationContract(
            required=True,
            artifact_kind=ARTIFACT_KIND_NARRATIVE,
            prompt_profile_id=BIDDING_PROMPT_PROFILE_ID,
            validator_id="content-ir-v2",
        )
    if mode_id == "official":
        return GenerationContract(
            required=True,
            artifact_kind=ARTIFACT_KIND_OFFICIAL,
            prompt_profile_id=OFFICIAL_PROMPT_PROFILE_ID,
            validator_id="official_document_draft_v1",
        )
    if mode_id == "engineering":
        return GenerationContract(
            required=True,
            artifact_kind=ARTIFACT_KIND_NARRATIVE,
            prompt_profile_id=ENGINEERING_PROMPT_PROFILE_ID,
            validator_id="content-ir-v2",
        )
    return GenerationContract(
        required=True,
        artifact_kind=ARTIFACT_KIND_NARRATIVE,
        prompt_profile_id=NARRATIVE_PROMPT_PROFILE_ID,
        validator_id="content-ir-v2",
    )


def _production_contract(
    mode: WorkModeSpec,
    operation: str,
    *,
    generation_required: bool,
) -> ProductionContract:
    if mode.mode_id == "exam" and generation_required:
        return ProductionContract(
            input_role=SOURCE_ROLE_STRUCTURED_SOURCE,
            artifact_kind=ARTIFACT_KIND_EXAM,
            validator_id="exam_items_v1",
            terminal_assembler="exam",
            master_id=mode.default_master_id,
            accepted_suffixes=(".md", ".markdown"),
        )
    if mode.mode_id == "official" and generation_required:
        return ProductionContract(
            input_role=SOURCE_ROLE_STRUCTURED_SOURCE,
            artifact_kind=ARTIFACT_KIND_OFFICIAL,
            validator_id="official_document_draft_v1",
            terminal_assembler="official",
            master_id=mode.default_master_id,
            accepted_suffixes=(".json",),
        )
    return ProductionContract(
        input_role=SOURCE_ROLE_PRODUCTION_INPUT,
        artifact_kind=ARTIFACT_KIND_EXISTING_DOCUMENT,
        validator_id="docx_preflight",
        terminal_assembler="generic",
        master_id=mode.default_master_id,
        accepted_suffixes=(".docx",),
    )


def _delivery_contract(
    mode: WorkModeSpec,
    *,
    route: NaturalRequestRoute | None = None,
) -> DeliveryContract:
    if mode.mode_id == "exam":
        return _EXAM_DELIVERY
    try:
        scene = deepcopy(
            load_scene_from_library(
                mode.default_scene_id,
                mode_id=mode.mode_id,
            )
        )
        if route is not None and route.family_id:
            application = apply_planned_scene_family_defaults(
                scene,
                family_id=route.family_id,
            )
            if not application.applied:
                raise ValueError(
                    f"assistant_scene_family_not_applicable:{route.family_id}"
                )
        route_preset_id = (
            str(route.delivery_preset_id or "").strip() if route is not None else ""
        )
        if route_preset_id:
            available_preset_ids = {
                str(getattr(item, "preset_id", "") or "").strip()
                for item in tuple(getattr(scene, "delivery_presets", ()) or ())
            }
            if route_preset_id not in available_preset_ids:
                raise ValueError(
                    f"assistant_delivery_preset_unavailable:{route_preset_id}"
                )
            scene.default_delivery_preset_id = route_preset_id
        presets = tuple(
            str(getattr(item, "preset_id", "") or "").strip()
            for item in tuple(getattr(scene, "delivery_presets", ()) or ())
            if str(getattr(item, "preset_id", "") or "").strip()
        )
        default_preset_id = str(
            getattr(scene, "default_delivery_preset_id", "") or ""
        ).strip()
        default_preset = next(
            (
                item
                for item in tuple(getattr(scene, "delivery_presets", ()) or ())
                if str(getattr(item, "preset_id", "") or "").strip()
                == default_preset_id
            ),
            None,
        )
        artifacts = getattr(default_preset, "artifacts", None)
        required = tuple(
            key
            for key, enabled in (
                ("final_docx", bool(getattr(artifacts, "final_docx", False))),
                (
                    "material_manifest",
                    bool(getattr(artifacts, "material_manifest", False)),
                ),
                (
                    "material_package",
                    bool(getattr(artifacts, "material_package", False)),
                ),
            )
            if enabled
        )
        return DeliveryContract(
            default_preset_id=default_preset_id,
            preset_ids=presets,
            required_artifact_keys=required,
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return DeliveryContract(
            default_preset_id="final",
            preset_ids=("final",),
            required_artifact_keys=("final_docx",),
        )


__all__ = [
    "BIDDING_PROMPT_PROFILE_ID",
    "ENGINEERING_PROMPT_PROFILE_ID",
    "EXAM_PROMPT_PROFILE_ID",
    "NARRATIVE_PROMPT_PROFILE_ID",
    "OFFICIAL_PROMPT_PROFILE_ID",
    "ResolvedAssistantCapability",
    "capability_route_coverage",
    "classify_task_operation",
    "resolve_assistant_capability",
    "system_prompt_for_profile",
]
