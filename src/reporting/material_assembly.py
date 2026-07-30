"""Report projections for the material assembly execution contract.

The immutable ``MaterialAssemblyReceipt`` is the execution fact.  This module
never reconstructs execution from configured rules, output paths, or file
existence: those are useful configuration/delivery projections, but they are
not proof that material assembly ran.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.shared.engine.material_dependency_projection import (
    project_material_dependency_usage,
)


def material_assembly_receipt_payload(result: object) -> dict[str, object] | None:
    """Return the exact public receipt payload attached to a pipeline result."""

    return _object_payload(getattr(result, "material_assembly_receipt", None))


def material_assembly_error_payload(result: object) -> dict[str, object] | None:
    """Return a structured assembly failure without inventing a receipt."""

    payload = _object_payload(getattr(result, "material_assembly_error", None))
    if payload is not None:
        return payload
    diagnostics = getattr(result, "material_assembly_diagnostics", None)
    if isinstance(diagnostics, (list, tuple)) and diagnostics:
        return {
            "error": "material_assembly_failed",
            "diagnostics": [
                dict(item) for item in diagnostics if isinstance(item, Mapping)
            ],
        }
    return None


def attachment_bundle_receipts_payload(
    result: object,
) -> dict[str, dict[str, object]]:
    """Return role-keyed attachment receipts without filesystem inference."""

    values = getattr(result, "attachment_bundle_receipts", None)
    if not isinstance(values, Mapping):
        return {}
    payload: dict[str, dict[str, object]] = {}
    for role, value in values.items():
        item = _object_payload(value)
        if item is not None:
            payload[str(role)] = item
    return dict(sorted(payload.items(), key=lambda item: item[0].casefold()))


def attachment_bundle_errors_payload(
    result: object,
) -> dict[str, dict[str, object]]:
    """Return role-keyed attachment failures without inventing receipts."""

    values = getattr(result, "attachment_bundle_errors", None)
    if not isinstance(values, Mapping):
        return {}
    payload: dict[str, dict[str, object]] = {}
    for role, value in values.items():
        item = _object_payload(value)
        if item is not None:
            payload[str(role)] = item
    return dict(sorted(payload.items(), key=lambda item: item[0].casefold()))


def extract_attachment_bundles(result: object) -> dict[str, object]:
    """Build the compact attachment execution view used by UI and manifests."""

    receipts = attachment_bundle_receipts_payload(result)
    errors = attachment_bundle_errors_payload(result)
    cancelled_roles = sorted(
        role
        for role, error in errors.items()
        if _attachment_error_payload_is_cancelled(error)
    )
    if cancelled_roles:
        status = "cancelled"
    elif receipts and errors:
        status = "partial_success"
    elif errors:
        status = "failed"
    elif receipts:
        status = "applied"
    else:
        status = "not_run"
    files = [
        _mapping(file_payload)
        for receipt in receipts.values()
        for file_payload in _sequence(receipt.get("files"))
    ]
    return {
        "status": status,
        "receipts": receipts,
        "errors": errors,
        "binding_count": len(receipts) + len(errors),
        "succeeded_binding_count": len(receipts),
        "failed_binding_count": len(errors),
        "cancelled_binding_count": len(cancelled_roles),
        "cancelled_roles": cancelled_roles,
        "file_count": len(files),
        "substituted_file_count": sum(
            1 for item in files if str(item.get("status") or "") == "substituted"
        ),
        "passthrough_file_count": sum(
            1 for item in files if str(item.get("status") or "") == "passthrough"
        ),
        "field_replacement_count": sum(
            int(item.get("field_replacement_count") or 0) for item in files
        ),
        "image_job_count": sum(
            int(item.get("image_job_count") or 0) for item in files
        ),
    }


def _attachment_error_payload_is_cancelled(
    payload: Mapping[str, object],
) -> bool:
    return any(
        str(item.get("code") or "").casefold().endswith("cancelled")
        for item in _sequence(payload.get("diagnostics"))
        if isinstance(item, Mapping)
    )


def extract_material_assembly(result: object) -> dict[str, object]:
    """Build a compact report view while retaining the exact receipt/error.

    ``not_run`` is deliberately distinct from ``configured_only``.  A normal
    report has no material-configuration argument, so absence of a receipt can
    prove only that this execution did not run the assembly transaction.  The
    material manifest, which owns the configuration projection, upgrades that
    state to ``configured_only``.
    """

    receipt = material_assembly_receipt_payload(result)
    if receipt is not None:
        projection = _applied_projection(receipt)
        projection["attachments"] = extract_attachment_bundles(result)
        return projection

    error = material_assembly_error_payload(result)
    if error is not None:
        projection = _failed_projection(error)
        projection["attachments"] = extract_attachment_bundles(result)
        return projection

    return {
        "status": "not_run",
        "receipt": None,
        "error": None,
        "snapshot": None,
        "compose": None,
        "pipeline": None,
        "variants": [],
        "measured_duration_ms": 0.0,
        "warnings": [],
        "attachments": extract_attachment_bundles(result),
    }


def format_material_assembly_markdown(evidence: Mapping[str, object]) -> list[str]:
    """Render a compact, execution-fact-only Markdown section."""

    status = str(evidence.get("status") or "not_run")
    if status == "not_run":
        return []

    lines = ["## 资料装配执行", "", f"- 状态: `{status}`"]
    if status == "failed":
        error = _mapping(evidence.get("error"))
        diagnostics = _sequence(error.get("diagnostics"))
        lines.append(f"- 失败证据: {len(diagnostics)} 项")
        for item in diagnostics[:8]:
            diagnostic = _mapping(item)
            stage = str(diagnostic.get("stage") or "unknown")
            code = str(diagnostic.get("code") or "unknown")
            variant_id = str(diagnostic.get("variant_id") or "").strip()
            suffix = f" / variant={variant_id}" if variant_id else ""
            message = str(diagnostic.get("message") or "").strip()
            lines.append(f"  - `{stage}:{code}`{suffix}: {message or '-'}")
        lines.append("")
        return lines

    receipt = _mapping(evidence.get("receipt"))
    snapshot = _mapping(evidence.get("snapshot"))
    compose = _mapping(evidence.get("compose"))
    pipeline = _mapping(evidence.get("pipeline"))
    lines.extend(
        [
            f"- Receipt: `{receipt.get('receipt_id', '-')}`",
            (
                "- Snapshot: "
                f"`{snapshot.get('snapshot_id', '-')}` "
                f"(content={snapshot.get('content_rule_count', 0)}, "
                f"image={snapshot.get('image_rule_count', 0)}, "
                f"attachment_roles={snapshot.get('attachment_role_count', 0)})"
            ),
            (
                "- Compose: "
                f"`{compose.get('status', '-')}` / "
                f"receipt=`{compose.get('receipt_id', '-')}` / "
                f"blocks={compose.get('rendered_block_count', 0)} / "
                f"deferred_images={compose.get('deferred_image_job_count', 0)}"
            ),
            (
                "- Pipeline: "
                f"`{pipeline.get('status', '-')}` / "
                f"variants={pipeline.get('variant_count', 0)} / "
                f"outputs={pipeline.get('output_count', 0)} / "
                f"prepared=`{pipeline.get('prepared_input_after_sha256', '-')}`"
            ),
        ]
    )

    for raw_variant in _sequence(evidence.get("variants")):
        variant = _mapping(raw_variant)
        configured = _mapping(variant.get("configured"))
        planned = _mapping(variant.get("planned"))
        applied = _mapping(variant.get("applied"))
        not_applicable = _mapping(variant.get("not_applicable"))
        failed = _sequence(variant.get("failed"))
        not_applicable_stages = [
            str(item) for item in _sequence(not_applicable.get("stages"))
        ]
        variant_id = str(variant.get("variant_id") or "-")
        lines.append(
            f"- Variant `{variant_id}`: "
            f"configured={'yes' if configured else 'no'}; "
            f"planned={planned.get('image_job_count', 0)}; "
            f"applied={applied.get('image_job_count', 0)}; "
            f"not_applicable={','.join(not_applicable_stages) or 'no'}; "
            f"failed={len(failed)}"
        )
        transform = _mapping(applied.get("transform"))
        layout = _mapping(applied.get("layout"))
        publish = _mapping(applied.get("publish"))
        lines.append(
            "  - Evidence: "
            f"transform=`{transform.get('identity_sha256', '-')}` "
            f"({float(transform.get('duration_ms') or 0.0):.1f}ms); "
            f"layout=`{layout.get('identity_sha256', '-')}` "
            f"({float(layout.get('duration_ms') or 0.0):.1f}ms); "
            f"publish=`{publish.get('sha256', '-')}`"
        )

    duration = float(evidence.get("measured_duration_ms") or 0.0)
    warnings = _sequence(evidence.get("warnings"))
    lines.append(f"- 已记录阶段耗时: {duration:.1f}ms")
    if warnings:
        lines.append(f"- 警告: {len(warnings)} 项")
        for item in warnings[:8]:
            warning = _mapping(item)
            variant_id = str(warning.get("variant_id") or "").strip()
            code = str(warning.get("code") or "warning")
            message = str(warning.get("message") or "").strip()
            prefix = f"{variant_id}:" if variant_id else ""
            lines.append(f"  - `{prefix}{code}`: {message or '-'}")
    attachments = _mapping(evidence.get("attachments"))
    if str(attachments.get("status") or "not_run") != "not_run":
        lines.append(
            "- Attachment bundles: "
            f"`{attachments.get('status', '-')}` / "
            f"bindings={attachments.get('succeeded_binding_count', 0)} "
            f"succeeded, {attachments.get('failed_binding_count', 0)} failed / "
            f"files={attachments.get('file_count', 0)} / "
            f"fields={attachments.get('field_replacement_count', 0)} / "
            f"images={attachments.get('image_job_count', 0)}"
        )
    lines.append("")
    return lines


def _applied_projection(receipt: Mapping[str, object]) -> dict[str, object]:
    snapshot_payload = _mapping(receipt.get("intake_snapshot"))
    dependency_payload = _mapping(receipt.get("dependency_index"))
    compose_payload = _mapping(receipt.get("content_compose_receipt"))
    pipeline_payload = _mapping(receipt.get("pipeline_receipt"))
    snapshot = {
        "snapshot_id": str(snapshot_payload.get("snapshot_id") or ""),
        "contract_version": str(snapshot_payload.get("contract_version") or ""),
        "material_schema_id": str(snapshot_payload.get("material_schema_id") or ""),
        "material_schema_version": str(
            snapshot_payload.get("material_schema_version") or ""
        ),
        "field_count": len(_mapping(snapshot_payload.get("field_values"))),
        "content_binding_count": len(
            _sequence(snapshot_payload.get("content_bindings"))
        ),
        "content_rule_count": len(_sequence(snapshot_payload.get("content_rules"))),
        "image_rule_count": len(
            _sequence(snapshot_payload.get("frozen_image_rules"))
        ),
        "image_source_count": len(
            _sequence(snapshot_payload.get("image_source_bindings"))
        ),
        "attachment_role_count": len(
            _sequence(snapshot_payload.get("attachment_bindings"))
        ),
        "source_revision_count": len(
            _mapping(snapshot_payload.get("source_revisions"))
        ),
    }
    dependency_occurrences = _sequence(dependency_payload.get("occurrences"))
    dependency_diagnostics = _sequence(dependency_payload.get("diagnostics"))
    dependencies = {
        "status": "applied",
        "index_id": str(dependency_payload.get("index_id") or ""),
        "scanner_contract": str(
            dependency_payload.get("scanner_contract") or ""
        ),
        "occurrence_count": len(dependency_occurrences),
        "replaceable_count": sum(
            1
            for item in dependency_occurrences
            if bool(_mapping(item).get("replaceable"))
        ),
        "consumer_count": len(
            {
                str(
                    _mapping(_mapping(item).get("consumer")).get("consumer_id")
                    or ""
                )
                for item in dependency_occurrences
                if str(
                    _mapping(_mapping(item).get("consumer")).get("consumer_id")
                    or ""
                )
            }
        ),
        "field_occurrence_count": sum(
            1
            for item in dependency_occurrences
            if str(_mapping(item).get("kind") or "") == "field"
        ),
        "image_occurrence_count": sum(
            1
            for item in dependency_occurrences
            if str(_mapping(item).get("kind") or "") == "image"
        ),
        "content_occurrence_count": sum(
            1
            for item in dependency_occurrences
            if str(_mapping(item).get("kind") or "") == "content"
        ),
        "diagnostic_count": len(dependency_diagnostics),
        "warning_count": sum(
            1
            for item in dependency_diagnostics
            if str(_mapping(item).get("severity") or "") == "warning"
        ),
        "source_revision_count": len(
            _mapping(dependency_payload.get("source_revisions"))
        ),
    }
    dependency_usage = project_material_dependency_usage(dependency_payload)
    dependencies["usage"] = dependency_usage
    rendered_blocks = sum(
        int(_mapping(item).get("rendered_block_count") or 0)
        for item in _sequence(compose_payload.get("render_receipts"))
    )
    materialization = _mapping(compose_payload.get("resource_materialization"))
    compose = {
        "status": "applied",
        "receipt_id": str(compose_payload.get("receipt_id") or ""),
        "snapshot_id": str(compose_payload.get("snapshot_id") or ""),
        "source_sha256": str(compose_payload.get("source_sha256") or ""),
        "output_sha256": str(compose_payload.get("output_sha256") or ""),
        "content_artifact_count": len(
            _sequence(compose_payload.get("content_artifacts"))
        ),
        "render_receipt_count": len(
            _sequence(compose_payload.get("render_receipts"))
        ),
        "rendered_block_count": rendered_blocks,
        "deferred_image_job_count": len(
            _sequence(compose_payload.get("deferred_image_drafts"))
        ),
        "materialized_resource_count": len(
            _sequence(materialization.get("entries"))
        ),
    }
    pipeline_outputs = _sequence(pipeline_payload.get("outputs"))
    pipeline = {
        "status": "applied",
        "prepared_input_before_sha256": str(
            _mapping(pipeline_payload.get("prepared_input_before")).get("sha256")
            or ""
        ),
        "prepared_input_after_sha256": str(
            _mapping(pipeline_payload.get("prepared_input_after")).get("sha256")
            or ""
        ),
        "output_count": len(pipeline_outputs),
        "variant_count": len(
            {
                str(_mapping(item).get("variant_id") or "")
                for item in pipeline_outputs
                if str(_mapping(item).get("variant_id") or "")
            }
        ),
        "visibility_evidence_count": len(
            _sequence(pipeline_payload.get("visibility_evidence"))
        ),
    }

    variants: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    measured_duration_ms = 0.0
    for raw_variant in _sequence(receipt.get("variants")):
        variant_payload = _mapping(raw_variant)
        variant = _mapping(variant_payload.get("variant"))
        delivery_plan = _mapping(variant_payload.get("delivery_plan"))
        plan_receipt = _mapping(variant_payload.get("image_plan_receipt"))
        transform_receipt = _mapping(variant_payload.get("image_transform_receipt"))
        layout_receipt = _mapping(variant_payload.get("office_layout_receipt"))
        final_output = _mapping(variant_payload.get("final_output"))
        visibility = _mapping(variant_payload.get("visibility_evidence"))
        not_applicable_jobs = _sequence(
            variant_payload.get("not_applicable_content_image_jobs")
        )
        variant_id = str(variant.get("variant_id") or delivery_plan.get("variant_id") or "")
        plan_jobs = _sequence(delivery_plan.get("resolved_image_plans"))
        transform_jobs = _sequence(transform_receipt.get("jobs"))
        transform_duration = sum(
            float(_mapping(item).get("duration_ms") or 0.0) for item in transform_jobs
        )
        layout_duration = float(layout_receipt.get("elapsed_ms") or 0.0)
        measured_duration_ms += transform_duration + layout_duration
        layout_warnings = [
            {"variant_id": variant_id, **_mapping(item)}
            for item in _sequence(layout_receipt.get("warnings"))
        ]
        warnings.extend(layout_warnings)
        layout_summary: dict[str, object]
        if layout_receipt:
            layout_summary = {
                "status": str(layout_receipt.get("status") or ""),
                "identity_sha256": str(layout_receipt.get("identity_sha256") or ""),
                "transaction_id": str(layout_receipt.get("transaction_id") or ""),
                "provider": str(layout_receipt.get("provider") or ""),
                "duration_ms": layout_duration,
                "job_count": len(_sequence(layout_receipt.get("jobs"))),
                "stabilization_round_count": len(
                    _sequence(layout_receipt.get("stabilization_rounds"))
                ),
                "warning_count": len(layout_warnings),
                "failure_count": len(_sequence(layout_receipt.get("failures"))),
                "document_open_count": int(
                    layout_receipt.get("document_open_count") or 0
                ),
                "document_save_count": int(
                    layout_receipt.get("document_save_count") or 0
                ),
                "repaginate_count": int(layout_receipt.get("repaginate_count") or 0),
            }
        else:
            layout_summary = {
                "status": "not_applicable",
                "identity_sha256": "",
                "duration_ms": 0.0,
                "job_count": 0,
                "warning_count": 0,
                "failure_count": 0,
            }
        not_applicable_stages: list[str] = []
        if not_applicable_jobs:
            not_applicable_stages.append("content_image_jobs")
        if str(visibility.get("kind") or "") == "not_applicable":
            not_applicable_stages.append("content_visibility")
        if not layout_receipt:
            not_applicable_stages.append("office_layout")
        variants.append(
            {
                "variant_id": variant_id,
                "variant_version": str(variant.get("variant_version") or ""),
                "status": "applied",
                "configured": {
                    "final_output_path": str(variant.get("final_output_path") or ""),
                    "rule_versions": dict(_mapping(variant.get("rule_versions"))),
                },
                "planned": {
                    "plan_id": str(delivery_plan.get("plan_id") or ""),
                    "plan_receipt_id": str(plan_receipt.get("receipt_id") or ""),
                    "snapshot_id": str(delivery_plan.get("snapshot_id") or ""),
                    "staged_docx_sha256": str(
                        delivery_plan.get("staged_docx_sha256") or ""
                    ),
                    "image_job_count": len(plan_jobs),
                },
                "applied": {
                    "image_job_count": len(transform_jobs),
                    "transform": {
                        "identity_sha256": str(
                            transform_receipt.get("identity_sha256") or ""
                        ),
                        "job_count": len(transform_jobs),
                        "duration_ms": transform_duration,
                        "cache_hit_group_count": int(
                            transform_receipt.get("cache_hit_group_count") or 0
                        ),
                    },
                    "layout": layout_summary,
                    "publish": {
                        "path": str(final_output.get("path") or ""),
                        "sha256": str(final_output.get("sha256") or ""),
                        "byte_size": int(final_output.get("byte_size") or 0),
                        "candidate_sha256": str(
                            _mapping(variant_payload.get("publish_candidate")).get(
                                "sha256"
                            )
                            or ""
                        ),
                    },
                },
                "not_applicable": (
                    {
                        "stages": not_applicable_stages,
                        "content_image_job_count": len(not_applicable_jobs),
                        "jobs": [dict(_mapping(item)) for item in not_applicable_jobs],
                        "visibility": dict(visibility),
                    }
                    if not_applicable_stages
                    else None
                ),
                "failed": [
                    dict(_mapping(item))
                    for item in _sequence(layout_receipt.get("failures"))
                ],
            }
        )

    return {
        "status": "applied",
        "receipt": dict(receipt),
        "error": None,
        "receipt_id": str(receipt.get("receipt_id") or ""),
        "contract_version": str(receipt.get("contract_version") or ""),
        "execution_id": str(receipt.get("execution_id") or ""),
        "snapshot": snapshot,
        "dependencies": dependencies,
        "dependency_usage": dependency_usage,
        "compose": compose,
        "pipeline": pipeline,
        "variants": variants,
        "measured_duration_ms": round(measured_duration_ms, 3),
        "warnings": warnings,
    }


def _failed_projection(error: Mapping[str, object]) -> dict[str, object]:
    diagnostics = [
        dict(_mapping(item)) for item in _sequence(error.get("diagnostics"))
    ]
    grouped: dict[str, list[dict[str, object]]] = {}
    for diagnostic in diagnostics:
        variant_id = str(diagnostic.get("variant_id") or "").strip()
        grouped.setdefault(variant_id, []).append(diagnostic)
    variants = [
        {
            "variant_id": variant_id,
            "status": "failed",
            "configured": None,
            "planned": None,
            "applied": None,
            "not_applicable": None,
            "failed": items,
        }
        for variant_id, items in sorted(grouped.items())
        if variant_id
    ]
    return {
        "status": "failed",
        "receipt": None,
        "error": dict(error),
        "snapshot": None,
        "compose": None,
        "pipeline": None,
        "variants": variants,
        "measured_duration_ms": 0.0,
        "warnings": [],
    }


def _object_payload(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
    if not isinstance(value, Mapping):
        return None
    return {str(key): _plain(item) for key, item in value.items()}


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return value


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


__all__ = [
    "attachment_bundle_errors_payload",
    "attachment_bundle_receipts_payload",
    "extract_attachment_bundles",
    "extract_material_assembly",
    "format_material_assembly_markdown",
    "material_assembly_error_payload",
    "material_assembly_receipt_payload",
]
