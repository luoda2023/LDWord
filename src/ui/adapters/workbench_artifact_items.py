from __future__ import annotations

from pathlib import Path

from src.config.delivery_preset_display import delivery_preset_display_name
from src.ui.panels.workbench.state import ArtifactItemState


def workbench_artifact_display_items(
    paths: dict[str, str],
    *,
    delivery_preset_labels: bool = False,
) -> list[tuple[str, str]]:
    """Return stable user-facing artifact labels without changing raw path keys."""

    if not isinstance(paths, dict):
        return []
    return [
        (
            _artifact_map_label(str(key), delivery_preset=delivery_preset_labels),
            str(path),
        )
        for key, path in paths.items()
    ]


def _artifact_label(
    paths: dict[str, str],
    fallback: str = "",
    *,
    delivery_preset_labels: bool = False,
) -> str:
    if paths:
        return ", ".join(
            f"{label}: {path}"
            for label, path in workbench_artifact_display_items(
                paths,
                delivery_preset_labels=delivery_preset_labels,
            )
        )
    return str(fallback or "")


def _build_artifact_items(
    *,
    output_path: str,
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    report_paths: list[str],
    intermediate_paths: dict[str, str],
    material_manifest_paths: dict[str, str],
    material_package_paths: dict[str, str],
    scene_sample_manifest_paths: dict[str, str],
    output_target_preflight: dict[str, object] | None,
    question_figure_repair_queue: dict[str, object] | None,
    official_document_assembly: dict[str, object] | None = None,
) -> list[ArtifactItemState]:
    preflight_by_label = _output_preflight_by_label(output_target_preflight)
    known_groups = _known_artifact_groups(
        output_paths,
        compare_paths,
        intermediate_paths,
        output_target_preflight,
    )
    items: list[ArtifactItemState] = []

    for label, path in output_paths.items():
        detail = preflight_by_label.get(label, "")
        items.append(
            ArtifactItemState(
                kind="output",
                label=_delivery_artifact_label(label),
                group_id=label,
                group_label=_delivery_artifact_label(label),
                path=path,
                status="warning" if detail else "available",
                detail=detail,
            )
        )
    if output_path and not output_paths:
        detail = preflight_by_label.get("final", "")
        items.append(
            ArtifactItemState(
                kind="output",
                label=_delivery_artifact_label("final"),
                group_id="final",
                group_label=_delivery_artifact_label("final"),
                path=output_path,
                status="warning" if detail else "available",
                detail=detail,
            )
        )
    _extend_official_review_pdf_status_item(
        items,
        official_document_assembly,
        output_paths=output_paths,
    )
    _extend_path_items(items, "compare", compare_paths, delivery_preset_labels=True)
    _extend_report_items(items, report_paths, known_groups=known_groups)
    _extend_question_figure_repair_queue_item(
        items,
        report_paths=report_paths,
        question_figure_repair_queue=question_figure_repair_queue,
    )
    _extend_path_items(
        items,
        "intermediate",
        intermediate_paths,
        delivery_preset_labels=True,
    )
    _extend_path_items(items, "material_manifest", material_manifest_paths)
    _extend_material_package_items(items, material_package_paths)
    _extend_path_items(
        items,
        "scene_sample_manifest",
        scene_sample_manifest_paths,
        group_id="scene_samples",
        group_label="样本库",
    )

    known_output_labels = {
        item.group_id for item in items if item.kind == "output" and item.group_id
    }
    for label, _display_label, detail, path in _planned_output_preflight_items(
        output_target_preflight
    ):
        if label in known_output_labels:
            continue
        items.append(
            ArtifactItemState(
                kind="planned_output",
                label=_delivery_artifact_label(label),
                group_id=label,
                group_label=_delivery_artifact_label(label),
                path=path,
                status="warning" if detail else "planned",
                detail=detail,
            )
        )
    return items


def _extend_official_review_pdf_status_item(
    items: list[ArtifactItemState],
    assembly: dict[str, object] | None,
    *,
    output_paths: dict[str, str],
) -> None:
    if not isinstance(assembly, dict):
        return
    status = str(assembly.get("review_pdf_status") or "not_requested").strip()
    if status in {"", "not_requested", "generated"}:
        return
    if output_paths.get("review_pdf"):
        return

    issue = str(assembly.get("review_pdf_issue") or "").strip()
    detail_by_status = {
        "renderer_unavailable": (
            "审阅 PDF 未生成：当前环境没有可用的 Word/LibreOffice PDF 渲染器；"
            "正式公文仍已生成。"
        ),
        "render_failed": "审阅 PDF 生成失败；正式公文仍已生成。",
        "output_missing": "PDF 渲染器未产生有效文件；正式公文仍已生成。",
        "assembly_blocked": "公文装配未完成，因此未生成审阅 PDF。",
    }
    detail = detail_by_status.get(status, f"审阅 PDF 未生成（{status}）。")
    if issue and status not in {"renderer_unavailable", "assembly_blocked"}:
        detail = f"{detail} 原因：{issue}"
    items.append(
        ArtifactItemState(
            kind="planned_output",
            label=_delivery_artifact_label("review_pdf"),
            group_id="review_pdf",
            group_label=_delivery_artifact_label("review_pdf"),
            status="warning",
            detail=detail,
        )
    )


def _extend_path_items(
    items: list[ArtifactItemState],
    kind: str,
    paths: dict[str, str],
    *,
    group_id: str = "",
    group_label: str = "",
    delivery_preset_labels: bool = False,
) -> None:
    for label, path in paths.items():
        resolved_group_id = group_id or label
        resolved_label = _artifact_map_label(
            label,
            delivery_preset=delivery_preset_labels,
        )
        resolved_group_label = group_label or _artifact_map_label(
            resolved_group_id,
            delivery_preset=delivery_preset_labels,
        )
        items.append(
            ArtifactItemState(
                kind=kind,
                label=resolved_label,
                group_id=resolved_group_id,
                group_label=resolved_group_label,
                path=path,
            )
        )


def _extend_material_package_items(
    items: list[ArtifactItemState],
    paths: dict[str, str],
) -> None:
    for label, path in paths.items():
        normalized_label = str(label or "").strip()
        if normalized_label == "report":
            items.append(
                ArtifactItemState(
                    kind="material_package_report",
                    label=normalized_label,
                    group_id=normalized_label,
                    group_label=_artifact_group_label(normalized_label),
                    path=path,
                    fragment="remote-asset-cache",
                    detail="Remote Asset Cache",
                )
            )
            continue
        items.append(
            ArtifactItemState(
                kind="material_package",
                label=normalized_label,
                group_id=normalized_label,
                group_label=_artifact_group_label(normalized_label),
                path=path,
            )
        )


def _extend_report_items(
    items: list[ArtifactItemState],
    report_paths: list[str],
    *,
    known_groups: list[str],
) -> None:
    for index, path in enumerate(report_paths, start=1):
        group_id = _infer_report_group(path, known_groups) or "reports"
        items.append(
            ArtifactItemState(
                kind="report",
                label=str(index),
                group_id=group_id,
                group_label=(
                    _delivery_artifact_label(group_id)
                    if group_id != "reports"
                    else _artifact_group_label(group_id)
                ),
                path=str(path),
            )
        )


def _extend_question_figure_repair_queue_item(
    items: list[ArtifactItemState],
    *,
    report_paths: list[str],
    question_figure_repair_queue: dict[str, object] | None,
) -> None:
    queue_payload = _dict_payload(question_figure_repair_queue)
    queue_count = _safe_int(queue_payload.get("queue_count"))
    if queue_count <= 0:
        return
    report_path = _question_figure_repair_queue_report_path(report_paths)
    plan_payload = _dict_payload(queue_payload.get("batch_confirmation_plan"))
    plan_detail = ""
    if plan_payload:
        plan_detail = (
            f"; batch_plan={_clean_text(plan_payload.get('status')) or 'empty'}"
            f"; eligible={_safe_int(plan_payload.get('eligible_count'))}"
            f"; blocked={_safe_int(plan_payload.get('blocked_count'))}"
            f"; conflicts={_safe_int(plan_payload.get('conflict_count'))}"
        )
    freeze_payload = _dict_payload(queue_payload.get("batch_confirmation_freeze"))
    freeze_detail = ""
    if freeze_payload:
        freeze_detail = (
            f"; freeze={_clean_text(freeze_payload.get('status')) or 'blocked'}"
            f"; frozen={_safe_int(freeze_payload.get('frozen_candidate_count'))}"
        )
    dry_run_payload = _dict_payload(queue_payload.get("batch_apply_dry_run"))
    dry_run_detail = ""
    if dry_run_payload:
        dry_run_detail = (
            f"; dry_run={_clean_text(dry_run_payload.get('status')) or 'blocked'}"
            f"; checked={_safe_int(dry_run_payload.get('checked_candidate_count'))}"
        )
    execution_plan_payload = _dict_payload(
        queue_payload.get("batch_apply_execution_plan")
    )
    execution_plan_detail = ""
    if execution_plan_payload:
        execution_plan_detail = (
            f"; exec_plan={_clean_text(execution_plan_payload.get('status')) or 'blocked'}"
            f"; planned={_safe_int(execution_plan_payload.get('planned_candidate_count'))}"
        )
    execution_result_payload = _dict_payload(
        queue_payload.get("batch_apply_execution_result")
    )
    execution_result_detail = ""
    if execution_result_payload:
        audit_text = (
            "written"
            if bool(execution_result_payload.get("audit_written"))
            else "not_written"
        )
        execution_result_detail = (
            f"; exec_result={_clean_text(execution_result_payload.get('status')) or 'blocked'}"
            f"; applied={_safe_int(execution_result_payload.get('applied_count'))}"
            f"; audit={audit_text}"
        )
    rollback_result_payload = _dict_payload(
        queue_payload.get("batch_apply_rollback_result")
    )
    rollback_result_detail = ""
    if rollback_result_payload:
        rollback_audit_text = (
            "written"
            if bool(rollback_result_payload.get("audit_written"))
            else "not_written"
        )
        rollback_result_detail = (
            f"; rollback={_clean_text(rollback_result_payload.get('status')) or 'blocked'}"
            f"; restored={_safe_int(rollback_result_payload.get('restored_count'))}"
            f"; rollback_audit={rollback_audit_text}"
        )
    transaction_manifest_payload = _dict_payload(
        queue_payload.get("batch_apply_transaction_manifest")
    )
    transaction_task_payload = _dict_payload(
        transaction_manifest_payload.get("task_summary")
    )
    transaction_manifest_detail = ""
    if transaction_manifest_payload:
        transaction_artifact_text = (
            "written"
            if bool(transaction_manifest_payload.get("artifact_written"))
            else "not_written"
        )
        transaction_report_text = (
            "written"
            if bool(transaction_manifest_payload.get("report_written"))
            else "not_written"
        )
        transaction_manifest_detail = (
            f"; transaction={_clean_text(transaction_manifest_payload.get('status')) or 'empty'}"
            f"; tx={_safe_int(transaction_manifest_payload.get('transaction_count'))}"
            f"; rolled_back={_safe_int(transaction_manifest_payload.get('rolled_back_count'))}"
            f"; tx_task={_clean_text(transaction_task_payload.get('status')) or 'empty'}"
            f"; rollback_available={_safe_int(transaction_task_payload.get('rollback_available_count'))}"
            f"; tx_artifact={transaction_artifact_text}"
            f"; tx_report={transaction_report_text}"
        )
    items.append(
        ArtifactItemState(
            kind="question_figure_repair_queue",
            label="candidates",
            group_id="reports",
            group_label=_artifact_group_label("reports"),
            path=report_path,
            fragment="question-figure-repair-queue" if report_path else "",
            status="warning",
            detail=(
                f"题图修复候选 {queue_count} 项，需要人工确认，自动应用关闭"
                f"{plan_detail}"
                f"{freeze_detail}"
                f"{dry_run_detail}"
                f"{execution_plan_detail}"
                f"{execution_result_detail}"
                f"{rollback_result_detail}"
                f"{transaction_manifest_detail}"
            ),
        )
    )
    transaction_manifest_path = _clean_text(
        transaction_manifest_payload.get("artifact_path")
    )
    if transaction_manifest_path:
        items.append(
            ArtifactItemState(
                kind="question_figure_batch_apply_transaction_manifest",
                label="transaction_manifest",
                group_id="reports",
                group_label=_artifact_group_label("reports"),
                path=transaction_manifest_path,
                fragment="question-figure-batch-apply-transaction-manifest",
                status=(
                    "success"
                    if _clean_text(transaction_manifest_payload.get("status"))
                    == "tracked"
                    else "warning"
                ),
                detail=(
                    f"题图批量应用事务台账 "
                    f"{_safe_int(transaction_manifest_payload.get('transaction_count'))} 项"
                    f"; rolled_back={_safe_int(transaction_manifest_payload.get('rolled_back_count'))}"
                ),
            )
        )
    transaction_report_path = _clean_text(
        transaction_manifest_payload.get("report_path")
    )
    if transaction_report_path:
        items.append(
            ArtifactItemState(
                kind="question_figure_batch_apply_transaction_report",
                label="transaction_report",
                group_id="reports",
                group_label=_artifact_group_label("reports"),
                path=transaction_report_path,
                fragment="question-figure-batch-apply-transaction-report",
                status=(
                    "success"
                    if bool(transaction_manifest_payload.get("report_written"))
                    else "warning"
                ),
                detail=(
                    f"题图批量应用事务报告 "
                    f"{_safe_int(transaction_manifest_payload.get('transaction_count'))} 项"
                    f"; rolled_back={_safe_int(transaction_manifest_payload.get('rolled_back_count'))}"
                ),
            )
        )
    transaction_task_path = _clean_text(
        transaction_task_payload.get("report_path")
    ) or transaction_report_path or transaction_manifest_path
    if transaction_task_payload and transaction_task_path:
        items.append(
            ArtifactItemState(
                kind="question_figure_batch_apply_transaction_task_summary",
                label="transaction_tasks",
                group_id="reports",
                group_label=_artifact_group_label("reports"),
                path=transaction_task_path,
                fragment="question-figure-batch-apply-transaction-task-summary",
                status=(
                    "success"
                    if _clean_text(transaction_task_payload.get("status"))
                    in {"active", "completed", "empty"}
                    else "warning"
                ),
                detail=(
                    f"题图批量应用事务任务 "
                    f"{_clean_text(transaction_task_payload.get('status')) or 'empty'}"
                    f"; active={_safe_int(transaction_task_payload.get('active_count'))}"
                    f"; rollback_available={_safe_int(transaction_task_payload.get('rollback_available_count'))}"
                ),
            )
        )


def _question_figure_repair_queue_report_path(report_paths: list[str]) -> str:
    normalized_paths = [str(path or "").strip() for path in list(report_paths or [])]
    for path in normalized_paths:
        lowered = path.lower()
        if lowered.endswith("_batch_report.md"):
            return path
    for path in normalized_paths:
        if path.lower().endswith(".md"):
            return path
    for path in normalized_paths:
        lowered = path.lower()
        if lowered.endswith("_batch_report.json"):
            return path
    for path in normalized_paths:
        if path.lower().endswith(".json"):
            return path
    return next((path for path in normalized_paths if path), "")


def _known_artifact_groups(
    output_paths: dict[str, str],
    compare_paths: dict[str, str],
    intermediate_paths: dict[str, str],
    output_target_preflight: dict[str, object] | None,
) -> list[str]:
    groups: list[str] = []
    for mapping in (output_paths, compare_paths, intermediate_paths):
        for key in mapping:
            normalized = str(key or "").strip()
            if normalized and normalized not in groups:
                groups.append(normalized)
    for label, _display_label, _detail, _path in _planned_output_preflight_items(
        output_target_preflight
    ):
        if label and label not in groups:
            groups.append(label)
    return groups


def _infer_report_group(path_text: str, known_groups: list[str]) -> str:
    if not known_groups:
        return ""
    path = Path(str(path_text or ""))
    haystack = " ".join([path.stem, *path.parts]).casefold()
    for group in known_groups:
        normalized = str(group or "").strip()
        if normalized and normalized.casefold() in haystack:
            return normalized
    return ""


def _artifact_group_label(group_id: str) -> str:
    normalized = str(group_id or "").strip()
    if not normalized:
        return "未分组"
    return "报告" if normalized == "reports" else normalized


def _artifact_map_label(label: str, *, delivery_preset: bool = False) -> str:
    normalized = str(label or "").strip()
    if not delivery_preset:
        return normalized
    return _delivery_artifact_label(normalized)


def _delivery_artifact_label(label: str) -> str:
    return delivery_preset_display_name(str(label or "").strip())


def _output_preflight_by_label(
    output_target_preflight: dict[str, object] | None,
) -> dict[str, str]:
    return {
        label: detail
        for label, _display_label, detail, _path in _planned_output_preflight_items(
            output_target_preflight
        )
        if detail
    }


def _planned_output_preflight_items(
    output_target_preflight: dict[str, object] | None,
) -> list[tuple[str, str, str, str]]:
    if not isinstance(output_target_preflight, dict):
        return []
    rows: list[tuple[str, str, str, str]] = []
    for item in list(output_target_preflight.get("items") or []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("preset_id") or item.get("label") or "output").strip()
        label = label or "output"
        display_label = _output_preflight_display_label(item, label)
        path = str(item.get("path") or "")
        issues = [
            _output_preflight_issue_detail(
                issue.get("message"),
                raw_label=label,
                display_label=display_label,
            )
            for issue in list(item.get("issues") or [])
            if isinstance(issue, dict) and str(issue.get("message") or "").strip()
        ]
        rows.append((label, display_label, "；".join(issues), path))
    return rows


def _output_preflight_display_label(item: dict[str, object], raw_label: str) -> str:
    explicit_label = _clean_text(item.get("display_label")) or _clean_text(
        item.get("label")
    )
    if explicit_label and explicit_label != raw_label:
        return delivery_preset_display_name(explicit_label)
    return _delivery_artifact_label(raw_label)


def _output_preflight_issue_detail(
    message: object,
    *,
    raw_label: str,
    display_label: str,
) -> str:
    value = _clean_text(message)
    for subject in (display_label, raw_label):
        stripped = _strip_output_preflight_subject(value, subject)
        if stripped != value:
            return stripped
    return value


def _strip_output_preflight_subject(value: str, subject: str) -> str:
    normalized = str(value or "").strip()
    prefix = str(subject or "").strip()
    if not normalized or not prefix or not normalized.startswith(prefix):
        return normalized
    suffix = normalized[len(prefix) :]
    if not suffix:
        return ""
    if suffix[0] in {" ", ":", "："}:
        return suffix.lstrip(" :：")
    return normalized


def _split_issue_detail_text(value: str) -> list[str]:
    return [
        text
        for text in (part.strip() for part in str(value or "").split("；"))
        if text
    ]


def _artifact_browser_label(items: list[ArtifactItemState], *, limit: int = 6) -> str:
    if not items:
        return ""
    parts: list[str] = []
    for item in items[:limit]:
        label = f"{_artifact_kind_label(item.kind)}[{item.label}]"
        status = "预警" if item.status == "warning" else "就绪"
        parts.append(f"{label}: {item.path} ({status})")
    suffix = "" if len(items) <= limit else f" 等 {len(items)} 项"
    return "；".join(parts) + suffix


def _artifact_kind_label(kind: str) -> str:
    return {
        "output": "输出",
        "planned_output": "计划输出",
        "compare": "对比",
        "report": "报告",
        "intermediate": "中间产物",
        "material_manifest": "资料清单",
        "material_package": "资料包",
        "material_package_report": "资料包报告",
        "question_figure_repair_queue": "题图修复候选",
        "question_figure_batch_apply_transaction_manifest": "题图事务台账",
        "question_figure_batch_apply_transaction_report": "题图事务报告",
        "question_figure_batch_apply_transaction_task_summary": "题图事务任务",
        "scene_sample_manifest": "样本清单",
    }.get(str(kind or ""), "产物")


def _dict_payload(value: dict[str, object] | None) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clean_text(value) -> str:
    return str(value or "").strip()
