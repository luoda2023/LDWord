from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from src.execution_diagnostics import (
    build_execution_diagnostics,
    summarize_execution_diagnostics,
)
from src.reporting.common import (
    _clean_list,
    _clean_mapping_lists,
    _clean_module_skips,
    _clean_text,
)


def diagnostics_payload(
    result: Any,
    extra_diagnostics: list[dict] | None = None,
) -> dict[str, object]:
    base_items: list[dict] = []
    if result is not None:
        base_items = list(build_execution_diagnostics(result)["items"])
    items = [*[dict(item) for item in (extra_diagnostics or [])], *base_items]
    return {
        "count": len(items),
        "items": items,
        "summary": summarize_execution_diagnostics(items),
    }


def content_visibility_scan_payload(result: Any) -> dict[str, object]:
    context = getattr(result, "context", None)
    scan = getattr(context, "content_visibility_scan", None)
    if scan is None:
        return {}
    payload = asdict(scan)
    payload["has_issues"] = bool(getattr(scan, "has_issues", False))
    payload["issue_messages"] = list(scan.issue_messages())
    return payload


def content_visibility_preview_payload(result: Any) -> list[dict[str, object]]:
    context = getattr(result, "context", None)
    previews = getattr(context, "content_visibility_preview", None)
    if not previews:
        return []
    return [asdict(preview) for preview in list(previews or [])]


def content_visibility_receipts_payload(result: Any) -> dict[str, object]:
    context = getattr(result, "context", None)
    receipts = getattr(context, "content_visibility_receipts", None)
    return plain_data(dict(receipts or {}))


def output_target_preflight_payload(result: Any) -> dict[str, object]:
    context = getattr(result, "context", None)
    preflight = getattr(context, "output_target_preflight", None)
    if preflight is None:
        return {}
    payload = asdict(preflight)
    payload["has_issues"] = bool(getattr(preflight, "has_issues", False))
    payload["issue_count"] = int(getattr(preflight, "issue_count", 0) or 0)
    payload["has_errors"] = bool(getattr(preflight, "has_errors", False))
    payload["error_count"] = int(getattr(preflight, "error_count", 0) or 0)
    return payload


def object_preflight_payload(result: Any) -> dict[str, object]:
    context = getattr(result, "context", None)
    if context is None:
        return {}

    policy = getattr(context, "object_preflight_policy", None)
    preflight = getattr(context, "object_preflight", None)
    if policy is None and preflight is None:
        return {}

    policy_dict = dict(policy) if isinstance(policy, dict) else {}
    findings = [
        {
            "kind": _clean_text(getattr(finding, "kind", "")),
            "severity": _clean_text(getattr(finding, "severity", "")),
            "location": _clean_text(getattr(finding, "location", "")),
            "message": _clean_text(getattr(finding, "message", "")),
        }
        for finding in list(getattr(preflight, "findings", []) or [])
    ]
    module_skips = _clean_module_skips(
        getattr(context, "object_preflight_module_skips", []) or []
    )
    return {
        "enabled": bool(policy_dict.get("enabled", True)),
        "preservation_mode": _clean_text(policy_dict.get("preservation_mode", "")),
        "material_schema_id": _clean_text(policy_dict.get("material_schema_id", "")),
        "material_schema_ids": _clean_list(policy_dict.get("material_schema_ids", [])),
        "planning_family_id": _clean_text(policy_dict.get("planning_family_id", "")),
        "planning_ooxml_touchpoints": _clean_list(
            policy_dict.get("planning_ooxml_touchpoints", [])
        ),
        "recommended_scan_targets": _clean_list(
            policy_dict.get("recommended_scan_targets", [])
        ),
        "scan_targets": _clean_list(policy_dict.get("scan_targets", [])),
        "block_on": _clean_list(policy_dict.get("block_on", [])),
        "skip_high_risk_modules": bool(policy_dict.get("skip_high_risk_modules", True)),
        "skip_modules_by_finding": _clean_mapping_lists(
            policy_dict.get("skip_modules_by_finding", {})
        ),
        "findings_count": len(findings),
        "findings": findings,
        "module_skips_count": len(module_skips),
        "module_skips": module_skips,
    }


def document_scope_payload(result: Any) -> dict[str, object]:
    context = getattr(result, "context", None)
    receipt = (
        getattr(context, "document_scope_receipt", None)
        if context is not None
        else None
    )
    return plain_data(dict(receipt or {}))


def material_field_consistency_payload(result: Any) -> dict[str, object]:
    context = getattr(result, "context", None)
    consistency = getattr(context, "material_field_consistency", None)
    if consistency is None:
        return {}

    items: list[dict[str, object]] = []
    issues: list[dict[str, str]] = []
    for item in list(getattr(consistency, "items", []) or []):
        item_issues = [
            material_field_issue_payload(issue)
            for issue in list(getattr(item, "issues", []) or [])
        ]
        issues.extend(item_issues)
        items.append(
            {
                "field_key": _clean_text(getattr(item, "field_key", "")),
                "expected": _clean_text(getattr(item, "expected", "")),
                "status": _clean_text(getattr(item, "status", "")) or "ok",
                "occurrence_count": int(getattr(item, "occurrence_count", 0) or 0),
                "placeholders_remaining": _clean_list(
                    getattr(item, "placeholders_remaining", [])
                ),
                "issues": item_issues,
            }
        )

    if not items and not _clean_text(getattr(consistency, "schema_id", "")):
        return {}
    return {
        "schema_id": _clean_text(getattr(consistency, "schema_id", "")),
        "family_id": _clean_text(getattr(consistency, "family_id", "")),
        "status": _clean_text(getattr(consistency, "status", "")),
        "field_count": len(items),
        "issue_count": len(issues),
        "items": items,
        "issues": issues,
    }


def journal_submission_package_payload(result: Any) -> dict[str, object]:
    return _context_evidence_payload(result, "journal_submission_package")


def official_document_assembly_payload(result: Any) -> dict[str, object]:
    return _context_evidence_payload(result, "official_document_assembly")


def official_numbering_preservation_payload(result: Any) -> dict[str, object]:
    return _context_evidence_payload(result, "official_numbering_preservation")


def technical_chapter_inventory_payload(result: Any) -> dict[str, object]:
    return _context_evidence_payload(result, "technical_chapter_inventory")


def application_section_word_limits_payload(result: Any) -> dict[str, object]:
    return _context_evidence_payload(result, "application_section_word_limits")


def material_field_issue_payload(issue: Any) -> dict[str, str]:
    return {
        "field_key": _clean_text(getattr(issue, "field_key", "")),
        "kind": _clean_text(getattr(issue, "kind", "")),
        "severity": _clean_text(getattr(issue, "severity", "")) or "warning",
        "expected": _clean_text(getattr(issue, "expected", "")),
        "observed": _clean_text(getattr(issue, "observed", "")),
        "location": _clean_text(getattr(issue, "location", "")),
        "message": _clean_text(getattr(issue, "message", "")),
    }


def plain_data(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return plain_data(asdict(value))
    if isinstance(value, dict):
        return {str(key): plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain_data(item) for item in value]
    return value


def _context_evidence_payload(result: Any, attribute: str) -> dict[str, object]:
    context = getattr(result, "context", None)
    evidence = getattr(context, attribute, None) if context is not None else None
    if evidence is None:
        return {}
    to_dict = getattr(evidence, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(evidence, dict):
        payload = dict(evidence)
    else:
        return {}
    if _clean_text(payload.get("status")) in {"", "not_applicable"}:
        return {}
    return plain_data(payload)


__all__ = [
    "application_section_word_limits_payload",
    "content_visibility_preview_payload",
    "content_visibility_receipts_payload",
    "content_visibility_scan_payload",
    "diagnostics_payload",
    "document_scope_payload",
    "journal_submission_package_payload",
    "material_field_consistency_payload",
    "material_field_issue_payload",
    "object_preflight_payload",
    "official_document_assembly_payload",
    "official_numbering_preservation_payload",
    "output_target_preflight_payload",
    "plain_data",
    "technical_chapter_inventory_payload",
]
