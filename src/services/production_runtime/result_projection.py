"""Project pipeline results into the canonical workbench terminal payload.

The projection owns the field shape shared by success, failure, and
cancellation.  The runner remains responsible only for orchestration and for
supplying the frozen execution context.
"""

from __future__ import annotations

from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.reporting.execution_payload import (
    application_section_word_limits_payload,
    content_visibility_preview_payload,
    content_visibility_receipts_payload,
    content_visibility_scan_payload,
    diagnostics_payload,
    journal_submission_package_payload,
    material_field_consistency_payload,
    object_preflight_payload,
    official_document_assembly_payload,
    official_numbering_preservation_payload,
    output_target_preflight_payload,
    plain_data,
    technical_chapter_inventory_payload,
)
from src.reporting.material_assembly import (
    extract_attachment_bundles,
    extract_material_assembly,
    material_assembly_error_payload,
    material_assembly_receipt_payload,
)
from src.services.artifact_failure import apply_artifact_failures

from .delivery_reporting import (
    finalize_result_artifacts,
    primary_output_path,
)


def project_execution_result(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    material_diagnostics: list[dict] | None,
    material_context: MaterialExecutionContext,
    style_source_summary: dict[str, object] | None,
) -> dict[str, object]:
    """Finalize auxiliary artifacts and return one canonical terminal shape."""

    diagnostics_items = list(material_diagnostics or [])
    result_output_paths = _normalized_output_paths(result)
    branch = _terminal_branch(result)
    publication_paths, output_path = _publication_paths(
        branch,
        config=config,
        result_output_paths=result_output_paths,
    )
    artifact_outcome = finalize_result_artifacts(
        result,
        input_path=input_path,
        output_dir=output_dir,
        output_paths=publication_paths,
        fallback_output_path=output_path,
        config=config,
        elapsed=elapsed,
        modules_enabled=modules_enabled,
        modules_total=modules_total,
        material_diagnostics=diagnostics_items,
        material_context=material_context,
        style_source_summary=style_source_summary,
        include_material_artifacts=branch != "cancelled",
    )
    payload = _terminal_payload(
        result,
        branch=branch,
        output_path=output_path,
        output_paths=publication_paths,
        artifact_outcome=artifact_outcome,
        evidence=_result_evidence(
            result,
            material_diagnostics=diagnostics_items,
            style_source_summary=style_source_summary,
        ),
    )
    apply_artifact_failures(payload, artifact_outcome.artifact_failures)
    return without_absent_terminal_fields(payload)


def _terminal_branch(result) -> str:
    status = str(getattr(result, "status", "failed") or "failed")
    if status == "cancelled":
        return "cancelled"
    if not bool(getattr(result, "success", False)):
        return "failed"
    return "success"


def _normalized_output_paths(result) -> dict[str, str]:
    output_paths = getattr(result, "output_paths", None)
    if not isinstance(output_paths, dict):
        return {}
    return {str(key): str(value) for key, value in output_paths.items()}


def _publication_paths(
    branch: str,
    *,
    config,
    result_output_paths: dict[str, str],
) -> tuple[dict[str, str], str]:
    if branch == "failed":
        return {}, ""
    return result_output_paths, primary_output_path(config, result_output_paths)


def _result_evidence(
    result,
    *,
    material_diagnostics: list[dict],
    style_source_summary: dict[str, object] | None,
) -> dict[str, object]:
    diagnostics = diagnostics_payload(result, material_diagnostics)
    context = getattr(result, "context", None)
    material_assembly = extract_material_assembly(result)
    return {
        "diagnostics_count": int(diagnostics["count"]),
        "diagnostics_summary": str(diagnostics["summary"] or ""),
        "diagnostics_items": list(diagnostics.get("items") or []),
        "material_diagnostics": material_diagnostics,
        "content_visibility_scan": content_visibility_scan_payload(result),
        "content_visibility_preview": content_visibility_preview_payload(result),
        "content_visibility_receipts": content_visibility_receipts_payload(result),
        "output_target_preflight": output_target_preflight_payload(result),
        "object_preflight": object_preflight_payload(result),
        "material_field_consistency": material_field_consistency_payload(result),
        "style_source": dict(style_source_summary or {}),
        "journal_submission_package": journal_submission_package_payload(result),
        "official_document_assembly": official_document_assembly_payload(result),
        "official_numbering_preservation": official_numbering_preservation_payload(
            result
        ),
        "technical_chapter_inventory": technical_chapter_inventory_payload(result),
        "application_section_word_limits": application_section_word_limits_payload(
            result
        ),
        "exam_markdown_import": plain_data(
            getattr(context, "exam_markdown_import", None)
        ),
        "exam_question_schema": plain_data(
            getattr(context, "exam_question_schema", None)
        ),
        "exam_delivery_runtime": plain_data(
            getattr(context, "exam_delivery_runtime", None)
        ),
        "material_assembly": material_assembly,
        "material_assembly_receipt": material_assembly_receipt_payload(result),
        "material_assembly_error": material_assembly_error_payload(result),
        "attachment_bundles": extract_attachment_bundles(result),
        "material_dependency_usage": dict(
            material_assembly.get("dependency_usage") or {}
        ),
    }


def _terminal_payload(
    result,
    *,
    branch: str,
    output_path: str,
    output_paths: dict[str, str],
    artifact_outcome,
    evidence: dict[str, object],
) -> dict[str, object]:
    status = str(getattr(result, "status", "failed") or "failed")
    if branch in {"failed", "cancelled"}:
        status = branch
    payload: dict[str, object] = {
        "status": status,
        "output_path": output_path,
        "output_paths": output_paths,
        "compare_paths": artifact_outcome.compare_paths,
        "report_paths": artifact_outcome.report_paths,
        "intermediate_paths": artifact_outcome.intermediate_paths,
        "material_manifest_paths": artifact_outcome.material_manifest_paths,
        "material_package_paths": artifact_outcome.material_package_paths,
        "failed_count": len(list(getattr(result, "failed_items", []) or [])),
        "artifact_failure_count": 0,
        "error_text": str(getattr(result, "error", "") or ""),
        "artifact_failures": [],
        **evidence,
    }
    if branch != "cancelled":
        payload["material_package_receipt"] = (
            artifact_outcome.material_package_receipt
        )
    return payload


def without_absent_terminal_fields(
    payload: dict[str, object],
) -> dict[str, object]:
    """Keep direct-runner shape aligned with worker terminal normalization."""

    return {key: value for key, value in payload.items() if value is not None}


__all__ = ["project_execution_result", "without_absent_terminal_fields"]
