"""Batch execution payload aggregation and atomic report publication."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.config.atomic_io import atomic_write_text
from src.services.artifact_failure import (
    apply_artifact_failures,
    capture_artifact_write,
)
from src.shared.io.artifact_publication import StagedArtifact, publish_staged_artifacts
from src.shared.engine.official_document_batch_history import (
    persist_official_document_batch_history,
)

from .material_artifacts import (
    material_artifact_path_map,
    unique_manifest_values,
)
from .question_figure_repair_runtime import (
    build_batch_question_figure_comparison_matrix,
    build_batch_question_figure_repair_queue,
)


def attach_batch_reports(
    payload: dict[str, object],
    base_output_dir: str | Path,
    input_path: Path,
) -> None:
    """Publish batch reports and attach artifact-failure evidence to payload."""

    artifact_failures: list[dict[str, str]] = []
    capture_artifact_write(
        artifact_failures,
        "batch_reports",
        lambda: _write_batch_reports(
            payload,
            base_output_dir,
            input_path,
        ),
        None,
    )
    apply_artifact_failures(payload, artifact_failures)


def _write_batch_reports(
    payload: dict[str, object],
    base_output_dir: str | Path,
    input_path: Path,
) -> None:
    output_dir = Path(base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{input_path.stem}_batch_report.json"
    md_path = output_dir / f"{input_path.stem}_batch_report.md"

    batch_issue_items = payload.get("batch_issue_items", [])
    comparison_matrix = build_batch_question_figure_comparison_matrix(
        batch_issue_items
    )
    repair_queue = build_batch_question_figure_repair_queue(batch_issue_items)
    report_batch_isolation = dict(payload.get("batch_isolation", {}) or {})
    for history_key in (
        "history_run_id",
        "history_path",
        "history_index_path",
    ):
        report_batch_isolation.pop(history_key, None)
    report_payload = {
        "status": payload.get("status", "failed"),
        "input_path": str(input_path),
        "batch_source_kind": str(payload.get("batch_source_kind") or ""),
        "batch_source_path": str(payload.get("batch_source_path") or ""),
        "items": payload.get("items", []),
        "pending_profile_ids": _batch_profile_ids_from_payload(payload),
        "output_paths": payload.get("output_paths", []),
        "material_manifest_paths": payload.get("material_manifest_paths", {}),
        "material_package_paths": payload.get("material_package_paths", {}),
        "material_package_receipt": payload.get("material_package_receipt", {}),
        "material_package_receipts": payload.get("material_package_receipts", {}),
        "material_diagnostics": payload.get("material_diagnostics", []),
        "batch_issue_items": batch_issue_items,
        "question_figure_comparison_matrix": comparison_matrix,
        "question_figure_repair_queue": repair_queue,
        "failed_count": int(payload.get("failed_count") or 0),
        "artifact_failure_count": max(
            int(payload.get("artifact_failure_count") or 0),
            len(list(payload.get("artifact_failures") or [])),
        ),
        "error_text": str(payload.get("error_text") or ""),
        "diagnostics_count": int(payload.get("diagnostics_count") or 0),
        "diagnostics_summary": str(payload.get("diagnostics_summary") or ""),
        "batch_isolation": report_batch_isolation,
        "batch_retry_of_run_id": str(payload.get("batch_retry_of_run_id") or ""),
        "batch_attempt_number": max(
            1,
            int(payload.get("batch_attempt_number") or 1),
        ),
    }

    batch_report_paths = [str(json_path), str(md_path)]

    def _publish_main_reports(_history_record=None) -> None:
        _publish_batch_report_files(
            report_payload,
            json_path=json_path,
            markdown_path=md_path,
            output_dir=output_dir,
        )
        payload["batch_report_paths"] = batch_report_paths
        payload["question_figure_comparison_matrix"] = comparison_matrix
        payload["question_figure_repair_queue"] = repair_queue
        existing_report_paths = [
            str(path) for path in payload.get("report_paths", []) or []
        ]
        payload["report_paths"] = [*existing_report_paths, *batch_report_paths]

    if report_payload["batch_source_kind"] == "official_document_table":
        history_record = persist_official_document_batch_history(
            output_dir,
            report_payload,
            retry_of_run_id=report_payload["batch_retry_of_run_id"],
            attempt_number=report_payload["batch_attempt_number"],
            before_commit=_publish_main_reports,
        )
        history_isolation = dict(payload.get("batch_isolation", {}) or {})
        history_isolation.update(
            {
                "history_run_id": history_record.run_id,
                "history_path": str(history_record.history_path),
                "history_index_path": str(
                    history_record.history_path.parent
                    / "batch_history_index.json"
                ),
                "retry_of_run_id": history_record.retry_of_run_id,
                "attempt_number": history_record.attempt_number,
                "retry_eligible_profile_ids": list(
                    history_record.failed_profile_ids
                ),
            }
        )
        payload["batch_run_id"] = history_record.run_id
        payload["batch_history_path"] = str(history_record.history_path)
        payload["batch_history_index_path"] = str(
            history_record.history_path.parent / "batch_history_index.json"
        )
        payload["batch_isolation"] = history_isolation
        payload["report_paths"].append(str(history_record.history_path))
    else:
        _publish_main_reports()


def _publish_batch_report_files(
    report_payload: dict[str, object],
    *,
    json_path: Path,
    markdown_path: Path,
    output_dir: Path,
) -> None:
    with TemporaryDirectory(prefix=".batch-report-", dir=str(output_dir)) as temp_dir:
        staging_dir = Path(temp_dir)
        staged_json = staging_dir / json_path.name
        staged_markdown = staging_dir / markdown_path.name
        atomic_write_text(
            staged_json,
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        atomic_write_text(
            staged_markdown,
            _render_batch_markdown_report(report_payload),
            encoding="utf-8",
        )
        publish_staged_artifacts(
            (
                StagedArtifact("batch_report_json", staged_json, json_path),
                StagedArtifact(
                    "batch_report_markdown",
                    staged_markdown,
                    markdown_path,
                ),
            ),
            execution_id=f"batch-report-{uuid4().hex}",
            work_root=output_dir,
        )


def _render_batch_markdown_report(report_payload: dict[str, object]) -> str:
    lines = _batch_report_header_lines(report_payload)
    _append_batch_issue_center(lines, report_payload)
    _append_question_figure_comparison(lines, report_payload)
    _append_question_figure_repair_queue(lines, report_payload)
    _append_batch_isolation(lines, report_payload)
    _append_batch_items(lines, report_payload)
    return "\n".join(lines)


def _batch_report_header_lines(report_payload: Mapping[str, object]) -> list[str]:
    lines = [
        "# Batch Material Execution Report",
        "",
        f"- Status: {report_payload.get('status', 'failed')}",
        f"- Input: {report_payload.get('input_path', '')}",
        f"- Failed count: {report_payload.get('failed_count', 0)}",
        (
            "- Artifact failure count: "
            f"{report_payload.get('artifact_failure_count', 0)}"
        ),
    ]
    source_kind = str(report_payload.get("batch_source_kind") or "").strip()
    if source_kind:
        lines.append(f"- Batch source kind: {source_kind}")
    history = report_payload.get("batch_history", {})
    if isinstance(history, dict) and history.get("run_id"):
        lines.append(f"- Batch run id: {history.get('run_id')}")
        lines.append(f"- Attempt: {history.get('attempt_number', 1)}")
        if history.get("retry_of_run_id"):
            lines.append(f"- Retry of: {history.get('retry_of_run_id')}")
    error_text = str(report_payload.get("error_text") or "")
    if error_text:
        lines.append(f"- Error: {error_text}")
    return lines


def _append_batch_issue_center(
    lines: list[str],
    report_payload: Mapping[str, object],
) -> None:
    issue_items = [
        item
        for item in list(report_payload.get("batch_issue_items", []) or [])
        if isinstance(item, dict)
    ]
    if issue_items:
        lines.extend(["", "## Batch Issue Center"])
        for issue in issue_items[:50]:
            profile = issue.get("profile_name") or issue.get("profile_id") or "profile"
            lines.append(
                f"- {profile}: {issue.get('kind', 'issue')} -> "
                f"{issue.get('summary', '')}"
            )


def _append_question_figure_comparison(
    lines: list[str],
    report_payload: Mapping[str, object],
) -> None:
    comparison_matrix = report_payload.get("question_figure_comparison_matrix", {})
    if (
        isinstance(comparison_matrix, dict)
        and int(comparison_matrix.get("total_issue_count") or 0)
    ):
        lines.extend(["", "## Question Figure Comparison Matrix"])
        lines.append(
            "- Total issues: {issues}; profiles: {profiles}; questions: {questions}".format(
                issues=comparison_matrix.get("total_issue_count", 0),
                profiles=comparison_matrix.get("profile_count", 0),
                questions=comparison_matrix.get("question_count", 0),
            )
        )
        for profile in list(comparison_matrix.get("profiles", []) or [])[:30]:
            if not isinstance(profile, dict):
                continue
            profile_label = (
                profile.get("profile_name")
                or profile.get("profile_id")
                or "profile"
            )
            for question in list(profile.get("questions", []) or [])[:50]:
                if not isinstance(question, dict):
                    continue
                question_index = question.get("question_index") or "-"
                item_labels = [
                    str(
                        item.get("display_name")
                        or item.get("reference")
                        or item.get("path")
                        or item.get("item_id")
                        or "issue"
                    )
                    for item in list(question.get("items", []) or [])[:5]
                    if isinstance(item, dict)
                ]
                label_text = ", ".join(item_labels) if item_labels else "issue"
                region_text = ""
                first_item = next(
                    (
                        item
                        for item in list(question.get("items", []) or [])
                        if isinstance(item, dict)
                        and str(item.get("region_summary") or "").strip()
                    ),
                    None,
                )
                if isinstance(first_item, dict):
                    region_text = f" 路 {first_item.get('region_summary')}"
                lines.append(
                    f"- {profile_label} / Q{question_index}: "
                    f"{question.get('issue_count', 0)} issue(s) -> "
                    f"{label_text}{region_text}"
                )


def _append_question_figure_repair_queue(
    lines: list[str],
    report_payload: Mapping[str, object],
) -> None:
    repair_queue = report_payload.get("question_figure_repair_queue", {})
    if not isinstance(repair_queue, dict) or not int(
        repair_queue.get("queue_count") or 0
    ):
        return
    lines.extend(["", "## Question Figure Repair Queue"])
    conflict_count = int(repair_queue.get("conflict_count") or 0)
    conflict_text = f"; conflicts: {conflict_count}" if conflict_count else ""
    lines.append(
        "- Candidate count: {count}; confirmation: required; "
        "auto apply: disabled{conflicts}".format(
            count=repair_queue.get("queue_count", 0),
            conflicts=conflict_text,
        )
    )
    _append_repair_confirmation_evidence(lines, repair_queue)
    _append_repair_execution_evidence(lines, repair_queue)
    _append_repair_transaction_manifest(lines, repair_queue)
    _append_repair_entries(lines, repair_queue)


def _append_repair_confirmation_evidence(
    lines: list[str],
    repair_queue: Mapping[str, object],
) -> None:
    plan = repair_queue.get("batch_confirmation_plan", {})
    if isinstance(plan, dict):
        lines.append(
            "- Batch confirmation plan: status={status}; eligible={eligible}; "
            "blocked={blocked}; conflicts={conflicts}; batch_apply=false".format(
                status=_clean_text(plan.get("status")) or "empty",
                eligible=plan.get("eligible_count", 0),
                blocked=plan.get("blocked_count", 0),
                conflicts=plan.get("conflict_count", 0),
            )
        )
        blocked_ids = [
            _clean_text(queue_id)
            for queue_id in list(plan.get("blocked_queue_ids") or [])[:20]
            if _clean_text(queue_id)
        ]
        if blocked_ids:
            lines.append("- Batch blocked queue ids: " + ", ".join(blocked_ids))
    freeze = repair_queue.get("batch_confirmation_freeze", {})
    if isinstance(freeze, dict) and freeze:
        lines.append(
            "- Batch confirmation freeze: status={status}; frozen={frozen}; "
            "blocked={blocked}; fingerprint={fingerprint}; batch_apply=false".format(
                status=_clean_text(freeze.get("status")) or "blocked",
                frozen=freeze.get("frozen_candidate_count", 0),
                blocked=freeze.get("blocked_count", 0),
                fingerprint=_clean_text(freeze.get("plan_fingerprint")),
            )
        )
    dry_run = repair_queue.get("batch_apply_dry_run", {})
    if isinstance(dry_run, dict) and dry_run:
        lines.append(
            "- Batch apply dry-run: status={status}; checked={checked}; "
            "blocked={blocked}; guard_passed={guard}; batch_apply=false".format(
                status=_clean_text(dry_run.get("status")) or "blocked",
                checked=dry_run.get("checked_candidate_count", 0),
                blocked=len(list(dry_run.get("blocked_queue_ids") or [])),
                guard=str(bool(dry_run.get("execution_guard_passed"))).lower(),
            )
        )


def _append_repair_execution_evidence(
    lines: list[str],
    repair_queue: Mapping[str, object],
) -> None:
    execution_plan = repair_queue.get("batch_apply_execution_plan", {})
    if isinstance(execution_plan, dict) and execution_plan:
        final_confirmation = (
            "provided"
            if bool(execution_plan.get("final_confirmation_provided"))
            else "required"
        )
        lines.append(
            "- Batch apply execution plan: status={status}; planned={planned}; "
            "final_confirmation={confirmation}; batch_apply=false".format(
                status=_clean_text(execution_plan.get("status")) or "blocked",
                planned=execution_plan.get("planned_candidate_count", 0),
                confirmation=final_confirmation,
            )
        )
    execution_result = repair_queue.get("batch_apply_execution_result", {})
    if isinstance(execution_result, dict) and execution_result:
        lines.append(
            "- Batch apply execution result: status={status}; applied={applied}; "
            "output={output}; word_write={word_write}; audit={audit}".format(
                status=_clean_text(execution_result.get("status")) or "blocked",
                applied=execution_result.get("applied_count", 0),
                output=_clean_text(execution_result.get("output_path")),
                word_write=str(
                    bool(execution_result.get("word_write_enabled"))
                ).lower(),
                audit=(
                    "written"
                    if bool(execution_result.get("audit_written"))
                    else "not_written"
                ),
            )
        )
    rollback_result = repair_queue.get("batch_apply_rollback_result", {})
    if isinstance(rollback_result, dict) and rollback_result:
        lines.append(
            "- Batch apply rollback result: status={status}; restored={restored}; "
            "output={output}; word_write={word_write}; audit={audit}".format(
                status=_clean_text(rollback_result.get("status")) or "blocked",
                restored=rollback_result.get("restored_count", 0),
                output=_clean_text(rollback_result.get("output_path")),
                word_write=str(
                    bool(rollback_result.get("word_write_enabled"))
                ).lower(),
                audit=(
                    "written"
                    if bool(rollback_result.get("audit_written"))
                    else "not_written"
                ),
            )
        )


def _append_repair_transaction_manifest(
    lines: list[str],
    repair_queue: Mapping[str, object],
) -> None:
    transaction_manifest = repair_queue.get(
        "batch_apply_transaction_manifest",
        {},
    )
    if not isinstance(transaction_manifest, dict) or not transaction_manifest:
        return
    transaction_artifact = (
        "written"
        if bool(transaction_manifest.get("artifact_written"))
        else "not_written"
    )
    transaction_report = (
        "written"
        if bool(transaction_manifest.get("report_written"))
        else "not_written"
    )
    task_summary = transaction_manifest.get("task_summary")
    task_status = (
        _clean_text(task_summary.get("status"))
        if isinstance(task_summary, Mapping)
        else ""
    ) or "empty"
    rollback_available = (
        task_summary.get("rollback_available_count", 0)
        if isinstance(task_summary, Mapping)
        else 0
    )
    lines.append(
        "- Batch apply transaction manifest: status={status}; "
        "transactions={transactions}; active={active}; rolled_back={rolled}; "
        "orphan_rollback={orphan}; task={task}; "
        "rollback_available={rollback_available}; artifact={artifact}; "
        "report={report}".format(
            status=_clean_text(transaction_manifest.get("status")) or "empty",
            transactions=transaction_manifest.get("transaction_count", 0),
            active=transaction_manifest.get("active_count", 0),
            rolled=transaction_manifest.get("rolled_back_count", 0),
            orphan=transaction_manifest.get("orphan_rollback_count", 0),
            task=task_status,
            rollback_available=rollback_available,
            artifact=transaction_artifact,
            report=transaction_report,
        )
    )


def _append_repair_entries(
    lines: list[str],
    repair_queue: Mapping[str, object],
) -> None:
    for entry in list(repair_queue.get("entries", []) or [])[:50]:
        if not isinstance(entry, dict):
            continue
        profile_label = (
            entry.get("profile_name") or entry.get("profile_id") or "profile"
        )
        question_index = entry.get("question_index") or "-"
        target = (
            entry.get("repair_target_key")
            or entry.get("item_id")
            or entry.get("current_path")
            or "question_figure"
        )
        reference = (
            entry.get("comparison_display_name")
            or entry.get("comparison_reference")
            or "manual comparison"
        )
        region_summary = _clean_text(entry.get("region_summary"))
        region_text = f"; region={region_summary}" if region_summary else ""
        confirm_status = _clean_text(entry.get("confirmation_status")) or "blocked"
        lines.append(
            f"- {profile_label} / Q{question_index}: "
            f"{entry.get('action', 'review_question_figure_replacement')} -> "
            f"{target}; reference={reference}; confirmation=required; "
            f"auto_apply=false; confirm={confirm_status}{region_text}"
        )


def _append_batch_isolation(
    lines: list[str],
    report_payload: Mapping[str, object],
) -> None:
    isolation = report_payload.get("batch_isolation", {})
    if not isinstance(isolation, dict) or not isolation:
        return
    lines.extend(["", "## Batch Isolation"])
    lines.append(
        "- Total: {total}; success: {success}; warning: {warning}; "
        "failed: {failed}".format(
            total=isolation.get("total_count", 0),
            success=isolation.get("success_count", 0),
            warning=isolation.get("warning_count", 0),
            failed=isolation.get("failed_count", 0),
        )
    )
    for profile in list(isolation.get("profiles", []) or []):
        if not isinstance(profile, dict) or profile.get("status") == "success":
            continue
        label = profile.get("profile_name") or profile.get("profile_id") or "profile"
        lines.append(
            f"- {label}: {profile.get('status', 'failed')} -> "
            f"{profile.get('summary', '')}"
        )


def _append_batch_items(
    lines: list[str],
    report_payload: Mapping[str, object],
) -> None:
    lines.extend(["", "## Items"])
    for item in report_payload.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        label = item.get("profile_name") or item.get("profile_id") or "profile"
        lines.append(
            f"- {label}: {item.get('status', 'failed')} -> "
            f"{item.get('output_path', '')}"
        )
        for diagnostic in item.get("material_diagnostics", []) or []:
            if not isinstance(diagnostic, dict):
                continue
            reason = str(diagnostic.get("reason") or "").strip()
            if reason:
                lines.append(f"  - material: {reason}")


def _clean_text(value) -> str:
    return str(value or "").strip()


def build_batch_payload(
    status: str,
    results: list[dict[str, object]],
    *,
    error_text: str,
) -> dict[str, object]:
    """Aggregate item results into the canonical batch execution payload."""

    report_paths: list[str] = []
    failed_count = 0
    diagnostics_count = 0
    diagnostics_summary_parts: list[str] = []
    material_diagnostics: list[dict] = []
    batch_issue_items: list[dict] = []
    output_paths: dict[str, str] = {}
    material_manifest_paths: dict[str, str] = {}
    material_package_paths: dict[str, str] = {}
    material_package_receipts: dict[str, dict[str, object]] = {}
    artifact_failures: list[dict[str, object]] = []
    for item_index, item in enumerate(results, start=1):
        profile_key = str(
            item.get("profile_id")
            or item.get("profile_name")
            or item_index
        )
        report_paths.extend(str(path) for path in item.get("report_paths", []) or [])
        failed_count += int(item.get("failed_count") or 0)
        diagnostics_count += int(item.get("diagnostics_count") or 0)
        material_diagnostics.extend(
            dict(diagnostic)
            for diagnostic in item.get("material_diagnostics", []) or []
            if isinstance(diagnostic, dict)
        )
        summary = str(item.get("diagnostics_summary") or "")
        if summary:
            diagnostics_summary_parts.append(summary)
        batch_issue_items.extend(build_batch_issue_items_for_result(item))
        item_output_paths = material_artifact_path_map(item.get("output_paths"))
        if item_output_paths:
            for output_key, output_path in item_output_paths.items():
                output_paths[f"{profile_key}:{output_key}"] = output_path
        else:
            output_path = str(item.get("output_path") or "").strip()
            if output_path:
                output_paths[f"{profile_key}:final"] = output_path
        for manifest_key, manifest_path in material_artifact_path_map(
            item.get("material_manifest_paths")
        ).items():
            material_manifest_paths[f"{profile_key}:{manifest_key}"] = manifest_path
        for package_key, package_path in material_artifact_path_map(
            item.get("material_package_paths")
        ).items():
            material_package_paths[f"{profile_key}:{package_key}"] = package_path
        package_receipt = item.get("material_package_receipt")
        if isinstance(package_receipt, Mapping) and package_receipt:
            material_package_receipts[profile_key] = dict(package_receipt)

        child_failures = [
            dict(failure)
            for failure in list(item.get("artifact_failures") or [])
            if isinstance(failure, Mapping)
        ]
        child_failure_count = max(
            int(item.get("artifact_failure_count") or 0),
            len(child_failures),
        )
        for failure in child_failures:
            failure.setdefault("profile_id", str(item.get("profile_id") or ""))
            failure.setdefault("profile_name", str(item.get("profile_name") or ""))
            failure.setdefault("kind", "batch_item_artifact")
            failure.setdefault("error", "unreported auxiliary artifact failure")
            artifact_failures.append(failure)
        for _ in range(child_failure_count - len(child_failures)):
            artifact_failures.append(
                {
                    "kind": "batch_item_artifact",
                    "path": "",
                    "error_type": "ArtifactError",
                    "error": str(item.get("error_text") or "").strip()
                    or "unreported auxiliary artifact failure",
                    "profile_id": str(item.get("profile_id") or ""),
                    "profile_name": str(item.get("profile_name") or ""),
                }
            )

    payload = {
        "status": str(status),
        "items": results,
        "output_paths": output_paths,
        "report_paths": report_paths,
        "material_manifest_paths": material_manifest_paths,
        "material_package_paths": material_package_paths,
        "material_package_receipts": material_package_receipts,
        "material_diagnostics": material_diagnostics,
        "batch_issue_items": batch_issue_items,
        "failed_count": failed_count,
        "artifact_failure_count": 0,
        "artifact_failures": [],
        "error_text": error_text,
        "diagnostics_count": diagnostics_count,
        "diagnostics_summary": "\n".join(diagnostics_summary_parts),
    }
    apply_artifact_failures(payload, artifact_failures)
    payload["batch_isolation"] = _batch_isolation_payload(
        str(payload["status"]),
        results,
        batch_issue_items=batch_issue_items,
        error_text=str(payload["error_text"]),
    )
    return payload


def batch_profile_ids(items) -> list[str]:
    """Return stable non-empty profile ids for pending-batch receipts."""

    return [
        profile_id
        for item in items
        if (profile_id := str(getattr(item, "profile_id", "") or "").strip())
    ]


def _batch_profile_ids_from_payload(payload: Mapping[str, object]) -> list[str]:
    values = payload.get("pending_profile_ids")
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        return []
    return [
        profile_id
        for value in values
        if (profile_id := str(value or "").strip())
    ]


def _batch_isolation_payload(
    status: str,
    results: list[dict[str, object]],
    *,
    batch_issue_items: list[dict],
    error_text: str,
) -> dict[str, object]:
    issues_by_profile: dict[str, list[dict]] = {}
    for issue in batch_issue_items:
        if not isinstance(issue, dict):
            continue
        key = _batch_profile_key(issue)
        issues_by_profile.setdefault(key, []).append(issue)

    profiles: list[dict[str, object]] = []
    success_count = 0
    warning_count = 0
    failed_count = 0
    for index, item in enumerate(results, start=1):
        profile_id = str(item.get("profile_id") or "")
        profile_name = str(item.get("profile_name") or "")
        profile_key = _batch_profile_key(item) or str(index)
        item_status = str(item.get("status") or "failed")
        profile_issues = issues_by_profile.get(profile_key, [])
        missing_fields = unique_manifest_values(
            field
            for issue in profile_issues
            for field in list(issue.get("missing_field_keys") or [])
        )
        missing_assets = unique_manifest_values(
            asset
            for issue in profile_issues
            for asset in list(issue.get("missing_asset_roles") or [])
        )
        if item_status == "success":
            success_count += 1
        elif item_status == "partial_success":
            warning_count += 1
        else:
            failed_count += 1
        profiles.append(
            {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": item_status,
                "output_dir": str(item.get("output_dir") or ""),
                "output_path": str(item.get("output_path") or ""),
                "report_paths": [
                    str(path) for path in list(item.get("report_paths") or [])
                ],
                "material_manifest_paths": material_artifact_path_map(
                    item.get("material_manifest_paths")
                ),
                "material_package_paths": material_artifact_path_map(
                    item.get("material_package_paths")
                ),
                "material_package_receipt": dict(
                    item.get("material_package_receipt")
                    if isinstance(item.get("material_package_receipt"), Mapping)
                    else {}
                ),
                "issue_count": len(profile_issues),
                "missing_field_keys": list(missing_fields),
                "missing_asset_roles": list(missing_assets),
                "repair_targets": [
                    {
                        "type": str(issue.get("repair_target_type") or ""),
                        "key": str(issue.get("repair_target_key") or ""),
                    }
                    for issue in profile_issues
                    if str(issue.get("repair_target_type") or "").strip()
                    and str(issue.get("repair_target_key") or "").strip()
                ],
                "summary": _batch_profile_summary(item, profile_issues),
            }
        )

    return {
        "kind": "batch_failure_isolation",
        "status": status,
        "total_count": len(results),
        "success_count": success_count,
        "warning_count": warning_count,
        "failed_count": failed_count,
        "error_text": str(error_text or ""),
        "profiles": profiles,
        "successful_profiles": [
            profile for profile in profiles if profile.get("status") == "success"
        ],
        "warning_profiles": [
            profile
            for profile in profiles
            if profile.get("status") == "partial_success"
        ],
        "failed_profiles": [
            profile
            for profile in profiles
            if profile.get("status") not in {"success", "partial_success"}
        ],
    }


def _batch_profile_key(value: dict[str, object]) -> str:
    return str(value.get("profile_id") or value.get("profile_name") or "").strip()


def _batch_profile_summary(
    item: dict[str, object],
    profile_issues: list[dict],
) -> str:
    if profile_issues:
        return "; ".join(
            str(issue.get("summary") or issue.get("kind") or "issue")
            for issue in profile_issues
        )
    return str(item.get("error_text") or item.get("diagnostics_summary") or "")


def build_batch_issue_items_for_result(
    item: dict[str, object],
) -> list[dict[str, object]]:
    """Project one item result into report- and UI-ready batch issues."""

    profile_id = str(item.get("profile_id") or "")
    profile_name = str(item.get("profile_name") or "")
    status = str(item.get("status") or "failed")
    issues: list[dict[str, object]] = []
    for index, diagnostic in enumerate(
        list(item.get("material_diagnostics") or []),
        start=1,
    ):
        if not isinstance(diagnostic, dict):
            continue
        missing_fields = [
            str(value)
            for value in list(diagnostic.get("missing_field_keys") or [])
            if str(value or "").strip()
        ]
        missing_assets = [
            str(value)
            for value in list(diagnostic.get("missing_asset_roles") or [])
            if str(value or "").strip()
        ]
        suspicious_asset_items = list(
            diagnostic.get("suspicious_asset_items") or []
        )
        comparison_issue_items = list(
            diagnostic.get("comparison_issue_items") or []
        )
        kind = str(diagnostic.get("change_type") or "material_diagnostic")
        parameter_paths = [
            str(value).strip()
            for value in list(diagnostic.get("parameter_paths") or [])
            if str(value or "").strip()
        ]
        parameter_path = str(
            diagnostic.get("parameter_path") or diagnostic.get("field_id") or ""
        ).strip()
        if parameter_path and parameter_path not in parameter_paths:
            parameter_paths.insert(0, parameter_path)
        repair_target_type = str(
            diagnostic.get("repair_target_type") or ""
        ).strip()
        repair_target_key = str(
            diagnostic.get("repair_target_key") or ""
        ).strip()
        if not repair_target_type:
            repair_target_type = (
                "field"
                if missing_fields
                else "asset"
                if missing_assets
                else ""
            )
        if not repair_target_key:
            repair_target_key = (
                missing_fields[0]
                if missing_fields
                else missing_assets[0]
                if missing_assets
                else ""
            )
        issues.append(
            {
                "issue_id": _batch_issue_id(
                    profile_id,
                    profile_name,
                    kind,
                    index,
                ),
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": status,
                "category": "material",
                "kind": kind,
                "severity": str(diagnostic.get("level") or "warning"),
                "summary": str(diagnostic.get("reason") or kind),
                "missing_field_keys": missing_fields,
                "missing_asset_roles": missing_assets,
                "missing_asset_items": list(
                    diagnostic.get("missing_asset_items") or []
                ),
                "suspicious_asset_items": suspicious_asset_items,
                "comparison_issue_items": comparison_issue_items,
                "parameter_paths": parameter_paths,
                "repair_target_type": repair_target_type,
                "repair_target_key": repair_target_key,
            }
        )
    if status not in {"success", "partial_success"} and not issues:
        error_text = str(item.get("error_text") or "").strip()
        issues.append(
            {
                "issue_id": _batch_issue_id(
                    profile_id,
                    profile_name,
                    "execution_failed",
                    1,
                ),
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": status,
                "category": "execution",
                "kind": "execution_failed",
                "severity": "error",
                "summary": error_text or "Batch item failed",
                "missing_field_keys": [],
                "missing_asset_roles": [],
                "repair_target_type": "",
                "repair_target_key": "",
            }
        )
    return issues


def _batch_issue_id(
    profile_id: str,
    profile_name: str,
    kind: str,
    index: int,
) -> str:
    profile_key = profile_id or profile_name or "profile"
    safe_profile = (
        re.sub(r"[^A-Za-z0-9_\-]+", "_", profile_key).strip("_")
        or "profile"
    )
    safe_kind = (
        re.sub(r"[^A-Za-z0-9_\-]+", "_", str(kind or "issue")).strip("_")
        or "issue"
    )
    return f"batch:{safe_profile}:{safe_kind}:{index}"


__all__ = [
    "attach_batch_reports",
    "batch_profile_ids",
    "build_batch_issue_items_for_result",
    "build_batch_payload",
]
