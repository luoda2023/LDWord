"""Deterministic Form document plan builder informed by natural-language routing."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.capability_registry import (
    classify_task_operation,
    resolve_assistant_capability,
)
from src.assistant.domain.exam_authoring_contract import (
    exam_delivery_contract_for_intent,
)
from src.assistant.contracts.document_plan import (
    DocumentPlan,
    OutputPolicy,
    PlanBlockingIssue,
)
from src.assistant.contracts.task_plan import (
    CAPABILITY_PLANNED,
    CAPABILITY_GATED,
    SOURCE_ROLE_REFERENCE_MATERIAL,
    SOURCE_ROLE_STANDARD_FORMAT_REFERENCE,
    SourceArtifactRef,
)
from src.assistant.domain.docx_format_evidence import (
    is_format_requirements_request,
)
from src.config.scene_natural_request_router import (
    get_natural_request_route,
    route_natural_scene_request,
)
from src.config.work_mode import get_work_mode


_DOCUMENT_OBJECT_HINTS = (
    "文档",
    "报告",
    "公文",
    "通知",
    "纪要",
    "方案",
    "简报",
    "论文",
    "标书",
    "申请书",
    "初稿",
    "word",
    "docx",
    "排版",
    "格式",
    "模板",
    "试卷",
    "题稿",
    "卷面",
)
_DOCUMENT_ACTION_HINTS = (
    "生成",
    "撰写",
    "起草",
    "写一份",
    "帮我写",
    "做一份",
    "新建",
    "创建",
    "创作",
    "排版",
    "格式化",
    "统一",
    "套用",
    "整理",
)


def requests_form_document_action(query: str) -> bool:
    """Whether a turn explicitly asks Form to create or transform a document."""

    normalized = " ".join(str(query or "").casefold().split())
    if is_format_requirements_request(normalized):
        # Format-reference inspection is read-only analysis.  It must not
        # create a production plan that would format the reference itself.
        return False
    operation = classify_task_operation(normalized)
    routed = route_natural_scene_request(query)
    has_routed_object = bool(routed.selected_route is not None or routed.matches)
    return bool(
        normalized
        and (
            (
                any(token in normalized for token in _DOCUMENT_ACTION_HINTS)
                and (
                    any(token in normalized for token in _DOCUMENT_OBJECT_HINTS)
                    or has_routed_object
                )
            )
            or operation in {"batch", "import", "author_master"}
        )
    )


class FormDocumentPlanBuilder:
    def build(
        self,
        *,
        query: str,
        workspace: WorkspaceSnapshot,
        turn_id: str,
        previous_plan: DocumentPlan | None = None,
        route_id_override: str = "",
    ) -> DocumentPlan:
        route = route_natural_scene_request(query)
        override = str(route_id_override or "").strip()
        selected_route = (
            get_natural_request_route(override)
            if override
            else route.selected_route
        )
        format_requirements_analysis = is_format_requirements_request(query)
        selected_route_id = (
            selected_route.route_id if selected_route is not None else ""
        )
        operation = classify_task_operation(query)
        capability = resolve_assistant_capability(
            route=selected_route,
            workspace_mode_id=workspace.mode_id,
            operation=operation,
        )
        mode_id = capability.mode_id
        mode = get_work_mode(mode_id) or get_work_mode("custom")
        if mode is None:  # pragma: no cover - guarded by Form registry tests.
            raise RuntimeError("Form default work mode is unavailable")
        keep_current = workspace.mode_id == mode.mode_id
        scene_id = (
            workspace.scene_id
            if keep_current and workspace.scene_id and selected_route is None
            else capability.scene_id
        )
        template_id = (
            workspace.template_id
            if keep_current and workspace.template_id and selected_route is None
            else capability.template_id
        )
        input_path = Path(workspace.input_path) if workspace.input_path else None
        output_root = (
            input_path.parent / "Alavette-Form-Outputs"
            if input_path is not None
            else Path.home() / "Documents" / "Alavette-Form-Outputs"
        )
        warnings: list[str] = []
        questions: list[str] = []
        blockers: list[PlanBlockingIssue] = []
        routing_ambiguous = route.status == "ambiguous" and not override
        capability_ref = capability.ref
        generation_contract = capability.generation
        if routing_ambiguous:
            questions.append(route.disambiguation_prompt or "请选择更符合需求的文档类型。")
            blockers.append(
                PlanBlockingIssue(
                    code="route_confirmation_required",
                    message=questions[-1],
                )
            )
            capability_ref = replace(
                capability_ref,
                status=CAPABILITY_PLANNED,
            )
            generation_contract = replace(generation_contract, required=False)
            warnings.append("assistant_route_ambiguous:explicit_confirmation_required")
        elif route.status == "unmatched" and not override:
            warnings.append("未命中专用场景，将使用当前或通用工作模式。")
        if format_requirements_analysis:
            capability_ref = replace(
                capability_ref,
                status=CAPABILITY_PLANNED,
            )
            generation_contract = replace(generation_contract, required=False)
            warnings.append(
                "assistant_analysis_only:format_requirements:no_document_production"
            )
        if not capability.executable:
            if capability.ref.status == CAPABILITY_GATED:
                questions.append(
                    "该需求需要经过专业能力或导入确认边界，当前不会回退到通用文档自动执行。"
                )
            else:
                questions.append(
                    "该场景尚未形成可验证的 Assistant 生产闭环，当前不会按通用文档降级执行。"
                )
            warnings.append(capability.blocking_reason)
            blockers.append(
                PlanBlockingIssue(
                    code="capability_not_executable",
                    message=questions[-1],
                )
            )
        generation_requested = (
            capability.executable
            and not routing_ambiguous
            and generation_contract.required
        )
        generation_mode = (
            "from_material"
            if generation_requested and input_path is not None and workspace.input_exists
            else ("from_prompt" if generation_requested else "existing_docx")
        )
        if (
            selected_route_id == "bidding_document_authoring"
            and generation_requested
        ):
            material_summary = dict(workspace.material_summary or {})
            missing_material_parts: list[str] = []
            if not str(material_summary.get("package_id") or "").strip():
                missing_material_parts.append("标书资料包")
            elif "material_schema_ids" in material_summary:
                schema_ids = {
                    str(value or "").strip()
                    for value in (
                        material_summary.get("material_schema_ids") or ()
                    )
                    if str(value or "").strip()
                }
                if "bid_materials_v1" not in schema_ids:
                    missing_material_parts.append("与标书正文匹配的资料包")
            if _summary_count(material_summary, "field_count") < 3:
                missing_material_parts.append("公司名称、项目名称、法定代表人")
            if _summary_count(material_summary, "asset_count") < 2:
                missing_material_parts.append("Logo、公章")
            if missing_material_parts:
                message = (
                    "生成最终标书前请补充："
                    + "；".join(missing_material_parts)
                    + "。"
                )
                questions.append(message)
                blockers.append(
                    PlanBlockingIssue(
                        code="bidding_materials_incomplete",
                        message=message,
                    )
                )
        production_contract = capability.production
        if mode.mode_id == "official":
            document_type_id = str(workspace.document_type_id or "").strip()
            if document_type_id:
                production_contract = replace(
                    production_contract,
                    document_type_id=document_type_id,
                )
            elif capability.executable:
                message = "请先确认本次公文文种，再进行公文母版装配。"
                questions.append(message)
                blockers.append(
                    PlanBlockingIssue(
                        code="official_document_type_required",
                        message=message,
                    )
                )
        if capability.executable and (input_path is None or not workspace.input_exists):
            if generation_mode == "from_prompt":
                warnings.append("将先生成并校验领域产物，再进入 Form 生产。")
            else:
                accepted = " / ".join(
                    suffix.lstrip(".").upper()
                    for suffix in capability.production.accepted_suffixes
                )
                message = f"请先选择要处理的输入文件（{accepted}）。"
                questions.append(message)
                blockers.append(
                    PlanBlockingIssue(
                        code="production_input_required",
                        message=message,
                    )
                )
        elif generation_mode == "from_material":
            warnings.append("已添加的 DOCX 将作为内容材料读取；不会覆盖原文件。")
        revision = 1 if previous_plan is None else previous_plan.revision + 1
        plan_id = previous_plan.plan_id if previous_plan is not None else uuid4().hex
        source_artifacts: tuple[SourceArtifactRef, ...] = ()
        if input_path is not None and workspace.input_exists:
            role = (
                SOURCE_ROLE_STANDARD_FORMAT_REFERENCE
                if format_requirements_analysis
                else (
                    SOURCE_ROLE_REFERENCE_MATERIAL
                    if generation_mode == "from_material"
                    else production_contract.input_role
                )
            )
            source_artifacts = (
                SourceArtifactRef(
                    role=role,
                    media_type=_source_media_type(input_path),
                    path=str(input_path),
                    name=input_path.name,
                    source_kind="file",
                ),
            )
        delivery_contract = capability.delivery
        if mode.mode_id == "exam":
            delivery_contract = exam_delivery_contract_for_intent(
                query,
                delivery_contract,
            )
        return DocumentPlan(
            plan_id=plan_id,
            revision=revision,
            intent=str(query).strip(),
            created_by_turn_id=turn_id,
            input_document_ref=(
                {"path": str(input_path), "name": input_path.name}
                if input_path is not None and generation_mode == "existing_docx"
                else {}
            ),
            work_mode_id=mode.mode_id,
            scene_ref={
                "id": scene_id,
                "route_id": selected_route_id,
                "family_id": capability.ref.family_id,
                "profile_id": capability.ref.profile_id,
                "route_type": capability.ref.route_type,
                "generation_mode": generation_mode,
            },
            template_ref={"id": template_id},
            material_refs=(
                ({"path": str(input_path), "name": input_path.name, "type": "file"},)
                if input_path is not None and generation_mode == "from_material"
                else ()
            ),
            operation=operation,
            capability_ref=capability_ref,
            source_artifacts=source_artifacts,
            generation_contract=generation_contract,
            production_contract=production_contract,
            delivery_contract=delivery_contract,
            output_policy=OutputPolicy(
                output_root=str(output_root),
                filename_suffix=("_draft" if generation_mode != "existing_docx" else "_formatted"),
                overwrite=False,
            ),
            warnings=tuple(warnings),
            unresolved_questions=tuple(dict.fromkeys(questions)),
            blocking_issues=tuple(
                {
                    issue.code: issue
                    for issue in blockers
                }.values()
            ),
        )


def _source_media_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".json": "application/json",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, "application/octet-stream")


def _summary_count(summary: dict[str, object], key: str) -> int:
    try:
        return max(0, int(summary.get(key) or 0))
    except (TypeError, ValueError):
        return 0


__all__ = ["FormDocumentPlanBuilder", "requests_form_document_action"]
