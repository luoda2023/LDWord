"""Capability-driven Assistant planning without UI-owned mode branches."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    ARTIFACT_KIND_EXISTING_DOCUMENT,
    ARTIFACT_KIND_NARRATIVE,
    CAPABILITY_EXECUTABLE,
    CAPABILITY_GATED,
    CAPABILITY_PLANNED,
    DeliveryContract,
    GenerationContract,
    ProductionContract,
    SOURCE_ROLE_PRODUCTION_INPUT,
    SOURCE_ROLE_STRUCTURED_SOURCE,
    TASK_OPERATION_AUTHOR,
    TASK_OPERATION_AUTHOR_MASTER,
    TASK_OPERATION_BATCH,
    TASK_OPERATION_IMPORT,
    TASK_OPERATION_REVIEW,
    TASK_OPERATION_TRANSFORM,
    TaskCapabilityRef,
)
from src.assistant.domain.docx_format_evidence import (
    is_format_requirements_request,
)
from src.config.scene_natural_request_router import (
    NaturalRequestRoute,
    list_natural_request_routes,
)
from src.config.library import load_scene_from_library
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.config.work_mode import WorkModeSpec, get_work_mode
from src.shared.engine.exam_paper_style import EXAM_MARKDOWN_AUTHORING_PROMPT


NARRATIVE_PROMPT_PROFILE_ID = "assistant.narrative-markdown.v1"
EXAM_PROMPT_PROFILE_ID = "assistant.exam-paper-markdown.v1"
BIDDING_PROMPT_PROFILE_ID = "assistant.bidding-markdown.v1"

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
    }
)

_AUTHORING_MODE_IDS = frozenset(
    {"custom", "exam", "thesis", "technical", "report", "bidding"}
)
_EXAM_DELIVERY = DeliveryContract(
    default_preset_id="student",
    preset_ids=("student", "answer"),
    required_artifact_keys=("student", "answer_key"),
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
    if any(token in normalized for token in ("pdf转", "ocr", "扫描件", "latex转", "导入")):
        return TASK_OPERATION_IMPORT
    if any(token in normalized for token in ("母版", "卷面")) and any(
        token in normalized for token in ("生成", "创建", "改造", "制作")
    ):
        return TASK_OPERATION_AUTHOR_MASTER
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
    if any(
        token in normalized
        for token in (
            "生成",
            "撰写",
            "起草",
            "写一份",
            "帮我写",
            "做一份",
            "新建",
            "创建",
            "创作",
            "命题",
        )
    ):
        return TASK_OPERATION_AUTHOR
    return TASK_OPERATION_TRANSFORM


def resolve_assistant_capability(
    *,
    route: NaturalRequestRoute | None,
    workspace_mode_id: str,
    operation: str,
) -> ResolvedAssistantCapability:
    route_id = route.route_id if route is not None else ""
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
    )
    production = _production_contract(mode)
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
        blocking_reason = (
            f"assistant_capability_gate_required:{gate_id or route_type}"
        )
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
) -> GenerationContract:
    if operation != TASK_OPERATION_AUTHOR or mode_id not in _AUTHORING_MODE_IDS:
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
    return GenerationContract(
        required=True,
        artifact_kind=ARTIFACT_KIND_NARRATIVE,
        prompt_profile_id=NARRATIVE_PROMPT_PROFILE_ID,
        validator_id="content-ir-v2",
    )


def _production_contract(mode: WorkModeSpec) -> ProductionContract:
    if mode.mode_id == "exam":
        return ProductionContract(
            input_role=SOURCE_ROLE_STRUCTURED_SOURCE,
            artifact_kind=ARTIFACT_KIND_EXAM,
            validator_id="exam_items_v1",
            terminal_assembler="exam",
            master_id=mode.default_master_id,
            accepted_suffixes=(".md", ".markdown"),
        )
    terminal_owner = "official" if mode.mode_id == "official" else "generic"
    return ProductionContract(
        input_role=SOURCE_ROLE_PRODUCTION_INPUT,
        artifact_kind=ARTIFACT_KIND_EXISTING_DOCUMENT,
        validator_id=(
            "official_document_v1" if mode.mode_id == "official" else "docx_preflight"
        ),
        terminal_assembler=terminal_owner,
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
            str(route.delivery_preset_id or "").strip()
            if route is not None
            else ""
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
    "EXAM_PROMPT_PROFILE_ID",
    "NARRATIVE_PROMPT_PROFILE_ID",
    "ResolvedAssistantCapability",
    "capability_route_coverage",
    "classify_task_operation",
    "resolve_assistant_capability",
    "system_prompt_for_profile",
]
