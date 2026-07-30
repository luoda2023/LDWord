from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

from src.services.execution_result_contract import (
    normalize_path_list,
    normalize_path_map,
    normalize_terminal_payload,
    plain_payload,
)
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope

from src.ui.panels.workbench.state import (
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)
from src.ui.panels.workbench.execution_flow_projection import normalize_workbench_stage_text
from src.ui.adapters.workbench_artifact_items import (
    _artifact_browser_label,
    _artifact_label,
    _build_artifact_items,
    _planned_output_preflight_items,
    _split_issue_detail_text,
)
from src.ui.adapters.workbench_issue_models import (
    WorkbenchIssueItem,
)



class WorkbenchExecutionAdapter:
    def build_readiness(
        self,
        *,
        has_document: bool,
        has_strategy: bool,
        material_schema_reasons: list[str] | None = None,
    ) -> ReadinessState:
        reasons: list[str] = []
        if not has_document:
            reasons.append("未选择文档")
        if not has_strategy:
            reasons.append("未选择策略")
        reasons.extend(_clean_reason_list(material_schema_reasons))
        return ReadinessState(
            ready=not reasons,
            label="待执行",
            reasons=reasons,
        )

    def build_progress_state(
        self,
        *,
        stage_text: str,
        current_step: int,
        total_steps: int,
    ) -> ExecutionProgressState:
        sanitized_total_steps = max(total_steps, 0)
        if sanitized_total_steps <= 0:
            sanitized_current_step = 0
        else:
            sanitized_current_step = min(max(current_step, 0), sanitized_total_steps)
        percent = 0
        if sanitized_total_steps > 0:
            percent = int(sanitized_current_step / sanitized_total_steps * 100)
        return ExecutionProgressState(
            stage_text=normalize_workbench_stage_text(stage_text),
            current_step=sanitized_current_step,
            total_steps=sanitized_total_steps,
            percent=percent,
        )

    def build_result_state(
        self,
        *,
        terminal_payload: Mapping[str, object],
    ) -> ExecutionResultState:
        """Project one canonical terminal payload into immutable UI state."""

        return _execution_result_state_from_terminal(
            _copy_terminal_payload(terminal_payload)
        )

    def build_recent_run_state(
        self,
        result_state: ExecutionResultState,
    ) -> RecentRunState:
        terminal_payload = _copy_terminal_payload(
            result_state.terminal_payload
        )
        output_path = str(terminal_payload.get("output_path") or "")
        output_paths = _terminal_dict_projection(
            terminal_payload,
            "output_paths",
        )
        compare_paths = _terminal_dict_projection(
            terminal_payload,
            "compare_paths",
        )
        report_paths = _terminal_string_list(terminal_payload, "report_paths")
        intermediate_paths = _terminal_dict_projection(
            terminal_payload,
            "intermediate_paths",
        )
        material_manifest_paths = _terminal_dict_projection(
            terminal_payload,
            "material_manifest_paths",
        )
        material_package_paths = _terminal_dict_projection(
            terminal_payload,
            "material_package_paths",
        )
        scene_sample_manifest_paths = _terminal_dict_projection(
            terminal_payload,
            "scene_sample_manifest_paths",
        )
        execution_session = _terminal_dict_projection(
            terminal_payload,
            "execution_session",
        )
        attachment_bundles = _terminal_dict_projection(
            terminal_payload,
            "attachment_bundles",
        )
        material_dependency_usage = _terminal_dict_projection(
            terminal_payload,
            "material_dependency_usage",
        )
        style_source = _terminal_dict_projection(
            terminal_payload,
            "style_source",
        )
        object_preflight = _terminal_dict_projection(
            terminal_payload,
            "object_preflight",
        )
        material_field_consistency = _terminal_dict_projection(
            terminal_payload,
            "material_field_consistency",
        )
        batch_isolation = _terminal_dict_projection(
            terminal_payload,
            "batch_isolation",
        )
        question_figure_repair_queue = _terminal_dict_projection(
            terminal_payload,
            "question_figure_repair_queue",
        )
        style_source_envelope = _style_source_receipt_envelope(style_source)
        artifact_items = _build_artifact_items(
            output_path=output_path,
            output_paths=_string_path_map(output_paths),
            compare_paths=_string_path_map(compare_paths),
            report_paths=report_paths,
            intermediate_paths=_string_path_map(intermediate_paths),
            material_manifest_paths=_string_path_map(material_manifest_paths),
            material_package_paths=_string_path_map(material_package_paths),
            scene_sample_manifest_paths=_string_path_map(
                scene_sample_manifest_paths
            ),
            output_target_preflight=_terminal_dict_projection(
                terminal_payload,
                "output_target_preflight",
            ),
            question_figure_repair_queue=question_figure_repair_queue,
            official_document_assembly=_terminal_dict_projection(
                terminal_payload,
                "official_document_assembly",
            ),
        )
        report_label = ", ".join(report_paths)
        return RecentRunState(
            status=str(terminal_payload.get("status") or result_state.status),
            title="最近结果",
            summary=result_state.summary,
            terminal_payload=terminal_payload,
            execution_session=execution_session,
            output_label=_artifact_label(
                output_paths,
                output_path,
                delivery_preset_labels=True,
            ),
            compare_label=_artifact_label(
                compare_paths,
                delivery_preset_labels=True,
            ),
            report_label=report_label,
            intermediate_label=_artifact_label(
                intermediate_paths,
                delivery_preset_labels=True,
            ),
            material_manifest_label=_artifact_label(material_manifest_paths),
            material_package_label=_artifact_label(material_package_paths),
            attachment_bundles=attachment_bundles,
            attachment_bundle_summary=_attachment_bundle_summary(
                attachment_bundles
            ),
            material_dependency_usage=material_dependency_usage,
            material_dependency_summary=_material_dependency_summary(
                material_dependency_usage
            ),
            scene_sample_manifest_label=_artifact_label(
                scene_sample_manifest_paths
            ),
            artifact_label=_artifact_browser_label(artifact_items),
            artifact_items=artifact_items,
            error_summary=str(terminal_payload.get("error_text") or ""),
            diagnostics_count=max(
                0,
                _safe_int(terminal_payload.get("diagnostics_count")),
            ),
            diagnostics_summary=str(
                terminal_payload.get("diagnostics_summary") or ""
            ),
            style_source=style_source,
            style_source_summary=style_source_envelope.receipt_summary(
                title_fallback="鏍峰紡鏉ユ簮"
            ),
            style_source_envelope=style_source_envelope,
            object_preflight=object_preflight,
            object_preflight_summary=_object_preflight_summary(
                object_preflight
            ),
            object_preflight_details=_object_preflight_detail_lines(
                object_preflight
            ),
            material_field_consistency=material_field_consistency,
            material_field_consistency_summary=(
                _material_field_consistency_summary(
                    material_field_consistency
                )
            ),
            batch_isolation=batch_isolation,
            batch_isolation_summary=_batch_isolation_summary(batch_isolation),
            batch_isolation_details=_batch_isolation_detail_lines(
                batch_isolation
            ),
            question_figure_repair_queue=question_figure_repair_queue,
        )


def _batch_issue_parameter_paths(payload: dict[str, object]) -> tuple[str, ...]:
    paths: list[str] = []
    for key in (
        "repair_target_key",
        "field_id",
        "parameter_path",
        "parameter_field",
    ):
        value = _clean_text(payload.get(key))
        if value:
            paths.append(value)
    for key in ("parameter_paths", "declared_paths", "runtime_paths"):
        paths.extend(_clean_list(payload.get(key)))

    unique: list[str] = []
    for path in paths:
        if path and path not in unique:
            unique.append(path)
    return tuple(unique)


def _infer_scene_field_repair_target(
    parameter_paths: tuple[str, ...],
    *,
    fallback_key: str = "",
) -> tuple[str, str]:
    candidates = [path for path in parameter_paths if path]
    if fallback_key and fallback_key not in candidates:
        candidates.insert(0, fallback_key)

    for path in candidates:
        target = _normalize_scene_document_scope_field_path(path)
        if target:
            return ("scene_document_scope_field", target)

    return ("", "")


def _normalize_scene_document_scope_field_path(path: str) -> str:
    target = _clean_text(path)
    if target in {
        "scene.document_scope.mode",
        "scene.document_scope.selected_roles",
    }:
        return target
    return ""


def output_target_preflight_issue_items(
    output_target_preflight: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return structured Workbench issue items for planned output risks."""

    items: list[WorkbenchIssueItem] = []
    for (
        label,
        display_label,
        detail,
        path,
    ) in _planned_output_preflight_items(output_target_preflight):
        if not detail:
            continue
        item_label = str(label or "output").strip() or "output"
        source_notes = []
        if display_label != item_label:
            source_notes.append("交付版本 ID：" + item_label)
        if str(path or "").strip():
            source_notes.append("输出路径：" + str(path))
        items.append(
            WorkbenchIssueItem(
                issue_id=f"output_target.{item_label}.warning",
                category="output_target",
                severity="warning",
                title="输出目标预检",
                summary=f"{display_label}：{detail}",
                details=tuple(_split_issue_detail_text(detail)),
                source_notes=tuple(source_notes),
                repair_target_type="output_target",
                repair_target_key=item_label,
                blocking=False,
            )
        )
    return items


def execution_diagnostic_issue_items(
    diagnostics_items: list[dict] | tuple[dict, ...] | None,
) -> list[WorkbenchIssueItem]:
    """Return actionable Workbench issues for routable execution diagnostics."""

    items: list[WorkbenchIssueItem] = []
    for index, payload in enumerate(list(diagnostics_items or []), start=1):
        if not isinstance(payload, dict):
            continue

        parameter_paths = _batch_issue_parameter_paths(payload)
        explicit_target_type = _clean_text(payload.get("repair_target_type"))
        explicit_target_key = _clean_text(payload.get("repair_target_key"))
        repair_target_type, repair_target_key = _infer_scene_field_repair_target(
            parameter_paths,
            fallback_key=explicit_target_key,
        )
        if not repair_target_type and explicit_target_type:
            repair_target_type = explicit_target_type
            repair_target_key = explicit_target_key

        if repair_target_type != "scene_document_scope_field":
            continue

        rule_name = _clean_text(payload.get("rule_name")) or "diagnostic"
        change_type = _clean_text(payload.get("change_type")) or "diagnostic"
        target = _clean_text(payload.get("target"))
        section = _clean_text(payload.get("section"))
        reason = _clean_text(payload.get("reason")) or change_type
        severity = _clean_text(payload.get("severity") or payload.get("level"))
        if not severity:
            severity = "error" if payload.get("success") is False else "warning"
        category = "scene_document_scope"
        title = "方案处理范围需要确认"
        details = [
            f"规则：{rule_name}" if rule_name else "",
            f"类型：{change_type}" if change_type else "",
            f"对象：{target}" if target else "",
            f"结构：{section}" if section else "",
            "参数路径：" + ", ".join(parameter_paths[:3]) if parameter_paths else "",
        ]
        items.append(
            WorkbenchIssueItem(
                issue_id=(
                    _clean_text(payload.get("issue_id"))
                    or "diagnostic."
                    f"{_issue_token(repair_target_type)}."
                    f"{_issue_token(repair_target_key)}.{index}"
                ),
                category=category,
                severity=severity,
                title=title,
                summary=reason,
                details=tuple(line for line in details if line),
                source_notes=("diagnostics_items",),
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
                blocking=severity == "error",
                status="open",
                owner="scene",
            )
        )
    return items


def batch_execution_issue_items(
    batch_issue_items: list[dict] | tuple[dict, ...] | None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issue items for per-record batch execution payloads."""

    items: list[WorkbenchIssueItem] = []
    for index, payload in enumerate(list(batch_issue_items or []), start=1):
        if not isinstance(payload, dict):
            continue
        profile_id = _clean_text(payload.get("profile_id"))
        profile_name = _clean_text(payload.get("profile_name"))
        kind = _clean_text(payload.get("kind")) or "batch_issue"
        summary = _clean_text(payload.get("summary")) or kind
        severity = _clean_text(payload.get("severity")) or "warning"
        status = _clean_text(payload.get("status")) or "open"
        repair_target_type = _clean_text(payload.get("repair_target_type"))
        repair_target_key = _clean_text(payload.get("repair_target_key"))
        parameter_paths = _batch_issue_parameter_paths(payload)
        if not repair_target_type:
            inferred_type, inferred_key = _infer_scene_field_repair_target(
                parameter_paths,
                fallback_key=repair_target_key,
            )
            repair_target_type = inferred_type
            repair_target_key = repair_target_key or inferred_key
        missing_fields = _clean_list(payload.get("missing_field_keys"))
        missing_assets = _clean_list(payload.get("missing_asset_roles"))
        suspicious_assets = [
            dict(item)
            for item in _list_values(payload.get("suspicious_asset_items"))
            if isinstance(item, dict)
        ]
        comparison_assets = [
            dict(item)
            for item in _list_values(payload.get("comparison_issue_items"))
            if isinstance(item, dict)
        ]
        details = _batch_issue_detail_lines(
            profile_id=profile_id,
            profile_name=profile_name,
            status=status,
            parameter_paths=parameter_paths,
            missing_fields=missing_fields,
            missing_assets=missing_assets,
            suspicious_assets=suspicious_assets,
            comparison_assets=comparison_assets,
        )
        source_notes = tuple(
            note
            for note in (
                "batch_issue_items",
                f"profile_id:{profile_id}" if profile_id else "",
                f"profile_name:{profile_name}" if profile_name else "",
            )
            if note
        )
        issue_id = (
            _clean_text(payload.get("issue_id"))
            or f"batch.{_issue_token(profile_id or profile_name or str(index))}.{_issue_token(kind)}.{index}"
        )
        items.append(
            WorkbenchIssueItem(
                issue_id=issue_id,
                category="batch_issue",
                severity=severity,
                title="批量记录问题",
                summary=summary,
                details=tuple(details),
                source_notes=source_notes,
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
                repair_context=tuple(
                    pair
                    for pair in (
                        ("profile_id", profile_id),
                        ("profile_name", profile_name),
                    )
                    if pair[1]
                ),
                blocking=severity == "error",
                status="open",
                owner="workbench",
            )
        )
    return items


def question_figure_repair_queue_issue_items(
    question_figure_repair_queue: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return actionable Workbench issues for question-figure repair candidates."""

    queue_payload = _dict_payload(question_figure_repair_queue)
    entries = [
        dict(entry)
        for entry in _list_values(queue_payload.get("entries"))
        if isinstance(entry, dict)
    ]
    items: list[WorkbenchIssueItem] = []
    for index, entry in enumerate(entries, start=1):
        repair_target_type = _clean_text(entry.get("repair_target_type"))
        repair_target_key = _clean_text(entry.get("repair_target_key"))
        if not repair_target_type or not repair_target_key:
            continue
        profile_id = _clean_text(entry.get("profile_id"))
        profile_name = _clean_text(entry.get("profile_name"))
        question_index = _clean_text(entry.get("question_index"))
        reference = (
            _clean_text(entry.get("comparison_display_name"))
            or _clean_text(entry.get("comparison_reference"))
        )
        issue_summary = (
            _clean_text(entry.get("issue_summary"))
            or _clean_text(entry.get("issue_kind"))
            or "题图对比修复候选"
        )
        queue_id = _clean_text(entry.get("queue_id"))
        status = _clean_text(entry.get("status")) or "candidate"
        region_summary = _clean_text(entry.get("region_summary"))
        confirmation_status = _clean_text(entry.get("confirmation_status"))
        replacement_source_path = _clean_text(entry.get("replacement_source_path"))
        apply_blockers = _clean_list(entry.get("apply_blockers"))
        conflict_group_id = _clean_text(entry.get("conflict_group_id"))
        conflict_resolution_action = _clean_text(
            entry.get("conflict_resolution_action")
        )
        conflict_resolution_status = _clean_text(
            entry.get("conflict_resolution_status")
        )
        conflict_resolution_note = _clean_text(entry.get("conflict_resolution_note"))
        conflict_candidate_queue_ids = _clean_list(
            entry.get("conflict_candidate_queue_ids")
        )
        details = [
            f"题号：{question_index}" if question_index else "",
            f"候选状态：{status}",
            f"对比对象：{reference}" if reference else "",
            f"差异区域：{region_summary}" if region_summary else "",
            (
                "确认替换：可用"
                if bool(entry.get("confirmation_apply_supported"))
                else "确认替换：不可用"
            ),
            f"替换来源：{replacement_source_path}" if replacement_source_path else "",
            "阻断原因：" + ", ".join(apply_blockers) if apply_blockers else "",
            f"确认状态：{confirmation_status}" if confirmation_status else "",
            f"冲突组：{conflict_group_id}" if conflict_group_id else "",
            (
                f"冲突动作：{conflict_resolution_action}"
                if conflict_resolution_action
                else ""
            ),
            (
                "冲突裁决：可选择此候选"
                if bool(entry.get("conflict_resolution_select_supported"))
                else ""
            ),
            (
                f"冲突裁决：{conflict_resolution_status}"
                if conflict_resolution_status
                else ""
            ),
            (
                f"裁决说明：{conflict_resolution_note}"
                if conflict_resolution_note
                else ""
            ),
            (
                "同组候选：" + ", ".join(conflict_candidate_queue_ids)
                if conflict_candidate_queue_ids
                else ""
            ),
            "需要人工确认"
            if bool(entry.get("requires_user_confirmation", True))
            else "",
            "自动应用关闭"
            if not bool(entry.get("auto_apply_supported", False))
            else "",
            f"来源 issue：{_clean_text(entry.get('source_issue_id'))}"
            if _clean_text(entry.get("source_issue_id"))
            else "",
        ]
        issue_id = (
            queue_id
            or "question_figure_repair_queue."
            f"{_issue_token(profile_id or profile_name or str(index))}."
            f"{_issue_token(question_index or str(index))}.{index}"
        )
        items.append(
            WorkbenchIssueItem(
                issue_id=issue_id,
                category="question_figure_repair_queue",
                severity="warning",
                title="题图修复候选",
                summary=issue_summary,
                details=tuple(detail for detail in details if detail),
                source_notes=("question_figure_repair_queue",),
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
                repair_context=tuple(
                    pair
                    for pair in (
                        ("profile_id", profile_id),
                        ("profile_name", profile_name),
                        (
                            "repair_candidate_json",
                            json.dumps(
                                entry,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                    if pair[1]
                ),
                blocking=False,
                status="open",
                owner="workbench",
            )
        )
    return items


def question_figure_transaction_task_issue_items(
    question_figure_repair_queue: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return actionable issues for active question-figure transaction tasks."""

    queue_payload = _dict_payload(question_figure_repair_queue)
    manifest_payload = _dict_payload(
        queue_payload.get("batch_apply_transaction_manifest")
    )
    task_payload = _dict_payload(manifest_payload.get("task_summary"))
    status = _clean_text(task_payload.get("status"))
    if status not in {"active", "blocked", "orphaned"}:
        return []

    next_action = _clean_text(task_payload.get("next_action"))
    artifact_path = _clean_text(manifest_payload.get("artifact_path"))
    report_path = (
        _clean_text(task_payload.get("report_path"))
        or _clean_text(manifest_payload.get("report_path"))
        or artifact_path
    )
    blockers = _clean_list(task_payload.get("blockers")) or _clean_list(
        manifest_payload.get("blockers")
    )
    active_ids = _clean_list(task_payload.get("active_transaction_ids"))
    rolled_back_ids = _clean_list(task_payload.get("rolled_back_transaction_ids"))
    rollback_available_ids = _clean_list(
        task_payload.get("rollback_available_transaction_ids")
    )
    latest_transaction_id = _clean_text(task_payload.get("latest_transaction_id"))
    latest_transaction_status = _clean_text(
        task_payload.get("latest_transaction_status")
    )
    latest_apply_audit_id = _clean_text(task_payload.get("latest_apply_audit_id"))
    latest_rollback_audit_id = _clean_text(
        task_payload.get("latest_rollback_audit_id")
    )
    transaction_count = _safe_int(task_payload.get("transaction_count"))
    active_count = _safe_int(task_payload.get("active_count"))
    rolled_back_count = _safe_int(task_payload.get("rolled_back_count"))
    rollback_available_count = _safe_int(
        task_payload.get("rollback_available_count")
    )
    orphan_rollback_count = _safe_int(task_payload.get("orphan_rollback_count"))
    action_payload = {
        "status": status,
        "next_action": next_action,
        "report_path": report_path,
        "artifact_path": artifact_path,
        "fragment": "question-figure-batch-apply-transaction-task-summary",
        "transaction_count": transaction_count,
        "active_count": active_count,
        "rolled_back_count": rolled_back_count,
        "rollback_available_count": rollback_available_count,
        "orphan_rollback_count": orphan_rollback_count,
        "latest_transaction_id": latest_transaction_id,
        "latest_transaction_status": latest_transaction_status,
        "latest_apply_audit_id": latest_apply_audit_id,
        "latest_rollback_audit_id": latest_rollback_audit_id,
    }
    details = [
        f"事务状态：{status}",
        f"下一步：{next_action}" if next_action else "",
        f"事务总数：{transaction_count}",
        f"活动事务：{active_count}",
        f"可回滚事务：{rollback_available_count}",
        f"已回滚事务：{rolled_back_count}",
        f"孤立回滚：{orphan_rollback_count}",
        (
            f"最近事务：{latest_transaction_id}"
            + (f" ({latest_transaction_status})" if latest_transaction_status else "")
            if latest_transaction_id
            else ""
        ),
        f"最近 apply audit：{latest_apply_audit_id}" if latest_apply_audit_id else "",
        (
            f"最近 rollback audit：{latest_rollback_audit_id}"
            if latest_rollback_audit_id
            else ""
        ),
        "活动事务 ID：" + ", ".join(active_ids) if active_ids else "",
        (
            "可回滚事务 ID：" + ", ".join(rollback_available_ids)
            if rollback_available_ids
            else ""
        ),
        "已回滚事务 ID：" + ", ".join(rolled_back_ids) if rolled_back_ids else "",
        "阻断原因：" + ", ".join(blockers) if blockers else "",
        f"报告：{report_path}" if report_path else "",
        f"台账：{artifact_path}" if artifact_path else "",
    ]
    issue_suffix = (
        latest_transaction_id
        or latest_apply_audit_id
        or latest_rollback_audit_id
        or next_action
        or status
    )
    severity = "error" if status == "blocked" else "warning"
    return [
        WorkbenchIssueItem(
            issue_id=(
                "question_figure_batch_apply_transaction_task."
                f"{_issue_token(status)}.{_issue_token(issue_suffix)}"
            ),
            category="question_figure_batch_apply_transaction_task",
            severity=severity,
            title="题图批量应用事务任务",
            summary=(
                f"{status}; next={next_action or '-'}; "
                f"rollback_available={rollback_available_count}"
            ),
            details=tuple(detail for detail in details if detail),
            source_notes=(
                "batch_apply_transaction_manifest",
                "transaction_task_summary",
            ),
            repair_target_type="question_figure_batch_apply_transaction_task_summary",
            repair_target_key=json.dumps(
                action_payload, ensure_ascii=False, separators=(",", ":")
            ),
            repair_context=tuple(
                pair
                for pair in (
                    ("task_status", status),
                    ("next_action", next_action),
                    ("report_path", report_path),
                    ("artifact_path", artifact_path),
                    (
                        "fragment",
                        "question-figure-batch-apply-transaction-task-summary",
                    ),
                )
                if pair[1]
            ),
            blocking=status == "blocked",
            status="open",
            owner="pipeline",
        )
    ]


def _execution_result_state_from_terminal(
    payload: dict[str, object],
) -> ExecutionResultState:
    status, summary, failed_count, artifact_failure_count = (
        _terminal_result_summary(payload)
    )
    paths = _terminal_result_paths(payload)
    domains = _terminal_result_domains(payload)
    diagnostics_items = _terminal_mapping_list(payload, "diagnostics_items")
    batch_issue_items = _terminal_mapping_list(payload, "batch_issue_items")
    style_source = domains["style_source"]
    style_source_envelope = _style_source_receipt_envelope(style_source, fallback="")
    question_queue = domains["question_figure_repair_queue"]
    object_preflight = domains["object_preflight"]
    field_consistency = domains["material_field_consistency"]
    batch_isolation = domains["batch_isolation"]
    return ExecutionResultState(
        status=status,
        summary=summary,
        error_text=str(payload.get("error_text") or ""),
        terminal_payload=payload,
        execution_session=domains["execution_session"],
        style_source=style_source,
        style_source_summary=style_source_envelope.receipt_summary(
            title_fallback="样式来源"
        ),
        style_source_envelope=style_source_envelope,
        output_path=paths["output_path"],
        output_paths=paths["output_paths"],
        compare_paths=paths["compare_paths"],
        report_paths=paths["report_paths"],
        intermediate_paths=paths["intermediate_paths"],
        material_manifest_paths=paths["material_manifest_paths"],
        material_package_paths=paths["material_package_paths"],
        material_package_receipt=domains["material_package_receipt"],
        material_package_receipts=domains["material_package_receipts"],
        attachment_bundles=domains["attachment_bundles"],
        attachment_bundle_summary=_attachment_bundle_summary(
            domains["attachment_bundles"]
        ),
        material_dependency_usage=domains["material_dependency_usage"],
        material_dependency_summary=_material_dependency_summary(
            domains["material_dependency_usage"]
        ),
        scene_sample_manifest_paths=paths["scene_sample_manifest_paths"],
        failed_count=failed_count,
        artifact_failure_count=artifact_failure_count,
        diagnostics_count=max(0, _safe_int(payload.get("diagnostics_count"))),
        diagnostics_summary=str(payload.get("diagnostics_summary") or ""),
        object_preflight=object_preflight,
        object_preflight_summary=_object_preflight_summary(object_preflight),
        object_preflight_details=_object_preflight_detail_lines(object_preflight),
        material_field_consistency=field_consistency,
        material_field_consistency_summary=_material_field_consistency_summary(
            field_consistency
        ),
        batch_isolation=batch_isolation,
        batch_isolation_summary=_batch_isolation_summary(batch_isolation),
        batch_isolation_details=_batch_isolation_detail_lines(batch_isolation),
        question_figure_repair_queue=question_queue,
        artifact_items=_build_artifact_items(
            output_path=paths["output_path"],
            output_paths=paths["output_paths"],
            compare_paths=paths["compare_paths"],
            report_paths=paths["report_paths"],
            intermediate_paths=paths["intermediate_paths"],
            material_manifest_paths=paths["material_manifest_paths"],
            material_package_paths=paths["material_package_paths"],
            scene_sample_manifest_paths=paths["scene_sample_manifest_paths"],
            output_target_preflight=domains["output_target_preflight"],
            question_figure_repair_queue=question_queue,
            official_document_assembly=domains["official_document_assembly"],
        ),
        issue_items=[
            *output_target_preflight_issue_items(domains["output_target_preflight"]),
            *execution_diagnostic_issue_items(diagnostics_items),
            *batch_execution_issue_items(batch_issue_items),
            *question_figure_repair_queue_issue_items(question_queue),
            *question_figure_transaction_task_issue_items(question_queue),
        ],
    )


def _terminal_result_summary(
    payload: Mapping[str, object],
) -> tuple[str, str, int, int]:
    status = str(payload.get("status") or "")
    failed_count = max(0, _safe_int(payload.get("failed_count")))
    artifact_failure_count = max(
        0,
        _safe_int(payload.get("artifact_failure_count")),
    )
    if artifact_failure_count and failed_count:
        partial_summary = (
            f"执行完成，但有 {failed_count} 个业务项未成功，"
            f"另有 {artifact_failure_count} 个辅助产物失败"
        )
    elif artifact_failure_count:
        partial_summary = (
            f"核心执行已完成，但有 {artifact_failure_count} 个辅助产物失败"
        )
    else:
        partial_summary = f"执行完成，但有 {failed_count} 个模块未成功"
    summaries = {
        "success": "本次执行已完成",
        "partial_success": partial_summary,
        "failed": "执行失败",
        "cancelled": "已取消",
    }
    if status not in summaries:
        raise ValueError(f"Unknown execution status: {status!r}")
    return status, summaries[status], failed_count, artifact_failure_count


def _terminal_result_paths(
    payload: Mapping[str, object],
) -> dict[str, object]:
    return {
        "output_path": str(payload.get("output_path") or ""),
        "output_paths": _string_path_map(
            _terminal_dict_projection(payload, "output_paths")
        ),
        "compare_paths": _string_path_map(
            _terminal_dict_projection(payload, "compare_paths")
        ),
        "report_paths": _terminal_string_list(payload, "report_paths"),
        "intermediate_paths": _string_path_map(
            _terminal_dict_projection(payload, "intermediate_paths")
        ),
        "material_manifest_paths": _string_path_map(
            _terminal_dict_projection(payload, "material_manifest_paths")
        ),
        "material_package_paths": _string_path_map(
            _terminal_dict_projection(payload, "material_package_paths")
        ),
        "scene_sample_manifest_paths": _string_path_map(
            _terminal_dict_projection(payload, "scene_sample_manifest_paths")
        ),
    }


def _terminal_result_domains(
    payload: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    fields = (
        "output_target_preflight",
        "official_document_assembly",
        "object_preflight",
        "style_source",
        "material_field_consistency",
        "batch_isolation",
        "question_figure_repair_queue",
        "attachment_bundles",
        "material_dependency_usage",
        "execution_session",
        "material_package_receipt",
        "material_package_receipts",
    )
    return {
        field_name: _terminal_dict_projection(payload, field_name)
        for field_name in fields
    }


def _clean_reason_list(reasons: list[str] | None) -> list[str]:
    return [
        text
        for text in (str(item or "").strip() for item in list(reasons or []))
        if text
    ]


def _dict_payload(value: dict[str, object] | None) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _copy_terminal_payload(
    value: Mapping[str, object],
) -> dict[str, object]:
    return normalize_terminal_payload(value)


def _terminal_dict_projection(
    payload: Mapping[str, object],
    field_name: str,
) -> dict[str, object]:
    if field_name not in payload or payload.get(field_name) is None:
        return {}
    value = payload.get(field_name)
    if not isinstance(value, Mapping):
        raise TypeError(
            f"Terminal payload field {field_name!r} must be a mapping or null"
        )
    if field_name in {
        "output_paths",
        "compare_paths",
        "intermediate_paths",
        "material_manifest_paths",
        "material_package_paths",
        "scene_sample_manifest_paths",
    }:
        return normalize_path_map(value, field_name=field_name)
    projected = plain_payload(value)
    return projected if isinstance(projected, dict) else {}


def _terminal_mapping_list(
    payload: Mapping[str, object],
    field_name: str,
) -> list[dict[str, object]]:
    if field_name not in payload or payload.get(field_name) is None:
        return []
    value = payload.get(field_name)
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            f"Terminal payload field {field_name!r} must be a list, tuple, or null"
        )
    projected = plain_payload(value)
    if not isinstance(projected, list):
        raise TypeError(
            f"Terminal payload field {field_name!r} did not normalize to a list"
        )
    items: list[dict[str, object]] = []
    for index, item in enumerate(projected):
        if not isinstance(item, dict):
            raise TypeError(
                f"Terminal payload field {field_name!r} item {index} "
                "must be a mapping"
            )
        items.append(item)
    return items


def _terminal_string_list(
    payload: Mapping[str, object],
    field_name: str,
) -> list[str]:
    if field_name not in payload or payload.get(field_name) is None:
        return []
    return normalize_path_list(payload.get(field_name), field_name=field_name)


def _string_path_map(value: dict[str, str] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(path)
        for key, path in value.items()
        if str(key or "").strip() and str(path or "").strip()
    }


def _style_source_receipt_envelope(
    value: dict[str, object],
    *,
    fallback: str = "",
) -> StylePresentationEnvelope:
    return StylePresentationEnvelope.from_execution_result(
        value,
        fallback=fallback,
    )


def _object_preflight_summary(value: dict[str, object]) -> str:
    if not value or value.get("enabled") is False:
        return ""
    findings_count = _safe_int(value.get("findings_count"))
    module_skips_count = _safe_int(value.get("module_skips_count"))
    scan_targets = [
        str(item or "").strip()
        for item in list(value.get("scan_targets") or [])
        if str(item or "").strip()
    ]
    if findings_count > 0:
        summary = f"对象预检：{findings_count} 项风险"
        if module_skips_count > 0:
            summary = f"{summary} · 跳过 {module_skips_count} 个模块"
        return summary
    if module_skips_count > 0:
        return f"对象预检：跳过 {module_skips_count} 个模块"
    if scan_targets:
        return "对象预检：未发现风险"
    return ""


def _object_preflight_detail_lines(
    value: dict[str, object],
    *,
    limit: int = 8,
) -> list[str]:
    if not value or value.get("enabled") is False or limit <= 0:
        return []

    entries: list[tuple[str, dict[str, object]]] = []
    for finding in list(value.get("findings") or []):
        if isinstance(finding, dict):
            entries.append(("finding", finding))
    for module_skip in list(value.get("module_skips") or []):
        if isinstance(module_skip, dict):
            entries.append(("skip", module_skip))

    lines: list[str] = []
    for kind, payload in entries[:limit]:
        if kind == "finding":
            line = _object_preflight_finding_line(payload)
        else:
            line = _object_preflight_skip_line(payload)
        if line:
            lines.append(line)
    remaining = len(entries) - len(lines)
    if remaining > 0:
        lines.append(f"... 还有 {remaining} 条对象预检明细")
    return lines


def _object_preflight_finding_line(finding: dict[str, object]) -> str:
    kind = _clean_text(finding.get("kind"))
    severity = _clean_text(finding.get("severity")) or "warning"
    location = _clean_text(finding.get("location"))
    message = _clean_text(finding.get("message"))

    head = f"风险[{severity}]"
    if kind:
        head = f"{head} {kind}"
    if location:
        head = f"{head} @ {location}"
    if message:
        return f"{head}: {message}"
    return head if kind or location else ""


def _object_preflight_skip_line(module_skip: dict[str, object]) -> str:
    module_name = _clean_text(module_skip.get("module_name"))
    reason = _clean_text(module_skip.get("reason"))
    finding_kinds = [
        cleaned
        for cleaned in (_clean_text(item) for item in _list_values(module_skip.get("finding_kinds")))
        if cleaned
    ]
    if not module_name and not finding_kinds and not reason:
        return ""

    head = "跳过模块"
    if module_name:
        head = f"{head} {module_name}"
    if finding_kinds:
        head = f"{head} <- {'/'.join(finding_kinds)}"
    if reason:
        return f"{head}: {reason}"
    return head


def _issue_token(value: str) -> str:
    token = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(value or "").strip().lower()
    ).strip("_")
    return token or "item"


def _material_field_consistency_summary(value: dict[str, object]) -> str:
    if not value:
        return ""
    schema_id = str(value.get("schema_id") or "").strip()
    status = str(value.get("status") or "").strip()
    issue_count = _safe_int(value.get("issue_count"))
    field_count = _safe_int(value.get("field_count"))
    if not schema_id and not status and field_count <= 0:
        return ""
    if status == "not_applicable" and field_count <= 0:
        return ""
    label = schema_id or "material fields"
    if issue_count > 0:
        return f"字段一致性：{label} · {issue_count} 项风险"
    if status in {"ok", "not_applicable"} or field_count > 0:
        return f"字段一致性：{label} · 通过"
    return f"字段一致性：{label} · {status}"


def _material_dependency_summary(value: dict[str, object]) -> str:
    if not value or not str(value.get("index_id") or ""):
        return ""
    fields = len(list(value.get("fields") or []))
    images = len(list(value.get("images") or []))
    consumers = len(list(value.get("consumers") or []))
    occurrences = _safe_int(value.get("occurrence_count"))
    return (
        f"资料联动：字段 {fields} · 图片 {images} · "
        f"消费文件 {consumers} · 出现 {occurrences} 次"
    )


def _attachment_bundle_summary(value: dict[str, object]) -> str:
    if not value or str(value.get("status") or "not_run") == "not_run":
        return ""
    status = str(value.get("status") or "unknown")
    succeeded = _safe_int(value.get("succeeded_binding_count"))
    failed = _safe_int(value.get("failed_binding_count"))
    files = _safe_int(value.get("file_count"))
    fields = _safe_int(value.get("field_replacement_count"))
    images = _safe_int(value.get("image_job_count"))
    return (
        f"附件包：{status} · 成功 {succeeded} · 失败 {failed} · "
        f"文件 {files} · 字段替换 {fields} · 图片 {images}"
    )


def _batch_isolation_summary(value: dict[str, object]) -> str:
    if not value:
        return ""
    total = _safe_int(value.get("total_count"))
    success = _safe_int(value.get("success_count"))
    warning = _safe_int(value.get("warning_count"))
    failed = _safe_int(value.get("failed_count"))
    if total <= 0 and success <= 0 and warning <= 0 and failed <= 0:
        return ""
    return (
        "Batch isolation: "
        f"total={total}; success={success}; warning={warning}; failed={failed}"
    )


def _batch_isolation_detail_lines(value: dict[str, object]) -> list[str]:
    if not value:
        return []
    lines: list[str] = []
    for profile in list(value.get("profiles") or []):
        if not isinstance(profile, dict):
            continue
        status = _clean_text(profile.get("status"))
        if status == "success":
            continue
        label = (
            _clean_text(profile.get("profile_name"))
            or _clean_text(profile.get("profile_id"))
            or "profile"
        )
        summary = _clean_text(profile.get("summary"))
        missing_fields = _clean_list(profile.get("missing_field_keys"))
        missing_assets = _clean_list(profile.get("missing_asset_roles"))
        detail = f"{label}: {status or 'failed'}"
        if missing_fields:
            detail += " | missing fields=" + ",".join(missing_fields)
        if missing_assets:
            detail += " | missing assets=" + ",".join(missing_assets)
        if summary:
            detail += " | " + summary
        lines.append(detail)
    return lines


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_bool(value, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enabled", "启用", "是"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disabled", "停用", "否"}:
        return False
    return bool(default)


def _clean_text(value) -> str:
    return " ".join(str(value or "").strip().split())


def _clean_list(value) -> tuple[str, ...]:
    return tuple(
        cleaned
        for cleaned in (_clean_text(item) for item in _list_values(value))
        if cleaned
    )


def _list_values(value) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _batch_issue_detail_lines(
    *,
    profile_id: str,
    profile_name: str,
    status: str,
    parameter_paths: tuple[str, ...],
    missing_fields: tuple[str, ...],
    missing_assets: tuple[str, ...],
    suspicious_assets: list[dict[str, object]],
    comparison_assets: list[dict[str, object]],
) -> list[str]:
    lines: list[str] = []
    if profile_id:
        lines.append("记录 ID：" + profile_id)
    if profile_name:
        lines.append("记录名称：" + profile_name)
    if status:
        lines.append("执行状态：" + status)
    if parameter_paths:
        lines.append("参数路径：" + ", ".join(parameter_paths[:3]))
    if missing_fields:
        lines.append("缺字段：" + ", ".join(missing_fields))
    if missing_assets:
        lines.append("缺素材：" + ", ".join(missing_assets))
    for item in suspicious_assets[:3]:
        target = _clean_text(item.get("question_index"))
        detected = _clean_text(item.get("detected_question_index"))
        path = _clean_text(item.get("path"))
        filename = Path(path).name if path else ""
        pieces = [
            f"目标题号 {target}" if target else "",
            f"文件名题号 {detected}" if detected else "",
            filename,
        ]
        lines.append("疑似错图：" + " / ".join(piece for piece in pieces if piece))
    for item in comparison_assets[:3]:
        target = _clean_text(item.get("question_index"))
        issue_kind = _clean_text(item.get("comparison_issue_kind")) or "题图对比"
        display = (
            _clean_text(item.get("comparison_issue_display_name"))
            or _clean_text(item.get("comparison_issue_reference"))
            or _clean_text(item.get("path"))
        )
        marked_at = _clean_text(item.get("comparison_issue_marked_at"))
        region_summary = _clean_text(item.get("comparison_issue_region_summary"))
        pieces = [
            f"题号 {target}" if target else "",
            issue_kind,
            display,
            f"标注时间 {marked_at}" if marked_at else "",
            f"区域 {region_summary}" if region_summary else "",
        ]
        lines.append("人工对比问题：" + " / ".join(piece for piece in pieces if piece))
    return lines
