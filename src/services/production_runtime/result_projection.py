"""Project pipeline evidence onto the stable workbench terminal payload."""

from __future__ import annotations

from src.reporting.execution_payload import (
    application_section_word_limits_payload,
    content_visibility_preview_payload,
    content_visibility_receipts_payload,
    content_visibility_scan_payload,
    diagnostics_payload,
    document_scope_payload,
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
from src.services.official_draft_source import OfficialDraftSource


def project_pipeline_result_evidence(result) -> dict[str, object]:
    """Return JSON-safe evidence already computed by the pipeline."""

    diagnostics = diagnostics_payload(result)
    context = getattr(result, "context", None)
    material_assembly = extract_material_assembly(result)
    payload: dict[str, object] = {
        "diagnostics_count": int(diagnostics["count"]),
        "diagnostics_summary": str(diagnostics["summary"] or ""),
        "diagnostics_items": list(diagnostics.get("items") or []),
        "content_visibility_scan": content_visibility_scan_payload(result),
        "content_visibility_preview": content_visibility_preview_payload(result),
        "content_visibility_receipts": content_visibility_receipts_payload(result),
        "output_target_preflight": output_target_preflight_payload(result),
        "object_preflight": object_preflight_payload(result),
        "document_scope": document_scope_payload(result),
        "material_field_consistency": material_field_consistency_payload(result),
        "journal_submission_package": journal_submission_package_payload(result),
        "official_document_assembly": official_document_assembly_payload(result),
        "official_numbering_preservation": official_numbering_preservation_payload(
            result
        ),
        "technical_chapter_inventory": technical_chapter_inventory_payload(result),
        "application_section_word_limits": application_section_word_limits_payload(
            result
        ),
        "material_assembly": material_assembly,
        "material_assembly_receipt": material_assembly_receipt_payload(result),
        "material_assembly_error": material_assembly_error_payload(result),
        "attachment_bundles": extract_attachment_bundles(result),
        "material_dependency_usage": dict(
            material_assembly.get("dependency_usage") or {}
        ),
    }
    for key in (
        "scene_journey_runtime",
        "exam_markdown_import",
        "exam_question_schema",
        "exam_delivery_runtime",
        "journal_rule_source_governance",
        "journal_citations",
        "coverage_boundaries",
        "parameter_runtime_consumption",
    ):
        payload[key] = plain_data(
            getattr(context, key, None) if context is not None else None
        )
    return {key: value for key, value in payload.items() if value is not None}


def apply_official_draft_evidence(
    payload: dict[str, object],
    source: OfficialDraftSource | None,
) -> None:
    if source is None:
        return
    payload["official_draft"] = {
        "schema_id": source.schema_id,
        "document_type_id": source.document_type_id,
        "field_provenance": dict(source.field_provenance),
        "provisional_fields": list(source.provisional_fields),
        "warnings": list(source.warnings),
    }
    if source.warnings:
        payload["summary"] = str(payload.get("summary") or "") + "；" + "；".join(
            source.warnings
        )


__all__ = ["apply_official_draft_evidence", "project_pipeline_result_evidence"]
