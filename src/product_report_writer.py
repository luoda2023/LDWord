"""
report_writer — 排版报告生成

将 PipelineResult 输出为 JSON 和 Markdown 报告。
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
import json
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.atomic_io import atomic_write_text
from src.execution_diagnostics import build_execution_diagnostics, describe_execution_diagnostic
from src.reporting.academic_confidence import (
    _extract_academic_confidence,
    _extract_count_result,
    _format_academic_confidence_markdown,
)
from src.reporting.common import (
    _clean_list,
    _clean_text,
    _join_or_dash,
    _normalize_extra_diagnostics,
)
from src.reporting.document_sections import (
    _extract_application_section_word_limits,
    _extract_official_document_assembly,
    _extract_official_numbering_preservation,
    _extract_technical_chapter_inventory,
    _format_application_section_word_limits_markdown,
    _format_official_document_assembly_markdown,
    _format_official_numbering_preservation_markdown,
    _format_technical_chapter_inventory_markdown,
)
from src.reporting.exam_sections import (
    _extract_exam_delivery_runtime,
    _extract_exam_markdown_import,
    _extract_exam_question_schema,
    _format_exam_delivery_runtime_markdown,
    format_exam_markdown_import_markdown,
    _format_exam_question_schema_markdown,
)
from src.reporting.front_matter import (
    _format_delivery_preset_markdown,
    _format_style_source_markdown,
    _normalize_delivery_preset_context,
    _normalize_style_source_summary,
)
from src.reporting.journal_citations import (
    _extract_journal_citations,
    _format_journal_citations_markdown,
)
from src.reporting.journal_rule_source import (
    _extract_journal_rule_source_governance,
    _format_journal_rule_source_governance_markdown,
)
from src.reporting.material_sections import (
    _extract_coverage_boundaries,
    _extract_material_field_consistency,
    _extract_object_preflight,
    _format_coverage_boundaries_markdown,
    _format_material_field_consistency_markdown,
    _format_object_preflight_markdown,
)
from src.reporting.material_assembly import (
    extract_material_assembly,
    format_material_assembly_markdown,
)
from src.reporting.execution_payload import document_scope_payload
if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def _write_internal_report(writer_name: str, result, **kwargs) -> None:
    """Delegate explicit engineering reports to the source-only writer."""

    writer = getattr(import_module("src.report_writer"), writer_name)
    writer(result, include_internal_evidence=True, **kwargs)


def write_json_report(
    result: PipelineResult,
    *,
    input_path: Path,
    output_path: Path | None,
    report_path: Path,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    extra_diagnostics: list[dict] | None = None,
    style_source_summary: Mapping[str, object] | None = None,
    delivery_preset: Mapping[str, object] | None = None,
    include_internal_evidence: bool = False,
) -> None:
    """写入 JSON 变更报告。"""
    if include_internal_evidence:
        return _write_internal_report(
            "write_json_report",
            result,
            input_path=input_path,
            output_path=output_path,
            report_path=report_path,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            extra_diagnostics=extra_diagnostics,
            style_source_summary=style_source_summary,
            delivery_preset=delivery_preset,
        )
    changes = _extract_changes(result)
    diagnostics = build_execution_diagnostics(result)
    diagnostic_items = [
        *_normalize_extra_diagnostics(extra_diagnostics),
        *diagnostics["items"],
    ]
    count_result = _extract_count_result(result)
    academic_confidence = _extract_academic_confidence(result, count_result)
    journal_rule_source_governance = _extract_journal_rule_source_governance(result)
    journal_citations = _extract_journal_citations(result)
    journal_submission_package = _extract_journal_submission_package(result)
    official_document_assembly = _extract_official_document_assembly(result)
    official_numbering_preservation = _extract_official_numbering_preservation(result)
    technical_chapter_inventory = _extract_technical_chapter_inventory(result)
    application_section_word_limits = _extract_application_section_word_limits(result)
    exam_markdown_import = _extract_exam_markdown_import(result)
    exam_question_schema = _extract_exam_question_schema(result)
    exam_delivery_runtime = _extract_exam_delivery_runtime(result)
    field_consistency = _extract_material_field_consistency(result)
    material_assembly = extract_material_assembly(result)
    object_preflight = _extract_object_preflight(result)
    coverage_boundaries = _extract_coverage_boundaries(result)
    document_scope = document_scope_payload(result)
    scene_journey_runtime = _extract_scene_journey_runtime(result)
    style_source = _normalize_style_source_summary(style_source_summary)
    delivery_context = _normalize_delivery_preset_context(delivery_preset)
    report_data = {
        "input": str(input_path),
        "output": str(output_path) if output_path is not None else "",
        "delivery_preset": delivery_context,
        "status": result.status,
        "elapsed_seconds": round(elapsed, 2),
        "modules_enabled": modules_enabled,
        "modules_total": modules_total,
        "changes": changes,
        "diagnostics": {
            "count": len(diagnostic_items),
            "items": diagnostic_items,
        },
        "counts": count_result,
        "academic_confidence": academic_confidence,
        "journal_rule_source_governance": journal_rule_source_governance,
        "journal_citations": journal_citations,
        "journal_submission_package": journal_submission_package,
        "official_document_assembly": official_document_assembly,
        "official_numbering_preservation": official_numbering_preservation,
        "technical_chapter_inventory": technical_chapter_inventory,
        "application_section_word_limits": application_section_word_limits,
        "exam_markdown_import": exam_markdown_import,
        "exam_question_schema": exam_question_schema,
        "exam_delivery_runtime": exam_delivery_runtime,
        "material_field_consistency": field_consistency,
        "material_assembly": material_assembly,
        "object_preflight": object_preflight,
        "coverage_boundaries": coverage_boundaries,
        "document_scope": document_scope,
        "scene_journey_runtime": scene_journey_runtime,
        "style_source": style_source,
        "failed_items": result.failed_items or [],
    }
    atomic_write_text(
        report_path,
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_report(
    result: PipelineResult,
    *,
    input_path: Path,
    output_path: Path | None = None,
    report_path: Path,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    extra_diagnostics: list[dict] | None = None,
    style_source_summary: Mapping[str, object] | None = None,
    delivery_preset: Mapping[str, object] | None = None,
    include_internal_evidence: bool = False,
) -> None:
    """写入 Markdown 变更报告。"""
    if include_internal_evidence:
        return _write_internal_report(
            "write_markdown_report",
            result,
            input_path=input_path,
            output_path=output_path,
            report_path=report_path,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            extra_diagnostics=extra_diagnostics,
            style_source_summary=style_source_summary,
            delivery_preset=delivery_preset,
        )
    changes = _extract_changes(result)
    diagnostics = build_execution_diagnostics(result)
    diagnostic_items = [
        *_normalize_extra_diagnostics(extra_diagnostics),
        *diagnostics["items"],
    ]
    count_result = _extract_count_result(result)
    academic_confidence = _extract_academic_confidence(result, count_result)
    journal_rule_source_governance = _extract_journal_rule_source_governance(result)
    journal_citations = _extract_journal_citations(result)
    journal_submission_package = _extract_journal_submission_package(result)
    official_document_assembly = _extract_official_document_assembly(result)
    official_numbering_preservation = _extract_official_numbering_preservation(result)
    technical_chapter_inventory = _extract_technical_chapter_inventory(result)
    application_section_word_limits = _extract_application_section_word_limits(result)
    exam_markdown_import = _extract_exam_markdown_import(result)
    exam_question_schema = _extract_exam_question_schema(result)
    exam_delivery_runtime = _extract_exam_delivery_runtime(result)
    field_consistency = _extract_material_field_consistency(result)
    material_assembly = extract_material_assembly(result)
    object_preflight = _extract_object_preflight(result)
    coverage_boundaries = _extract_coverage_boundaries(result)
    scene_journey_runtime = _extract_scene_journey_runtime(result)
    style_source = _normalize_style_source_summary(style_source_summary)
    delivery_context = _normalize_delivery_preset_context(delivery_preset)
    lines = [
        f"# 排版报告 - {input_path.name}",
        "",
        f"- 状态: **{result.status}**",
        f"- 耗时: {elapsed:.2f}s",
        f"- 模块: {modules_enabled}/{modules_total} 启用",
        "",
    ]

    if delivery_context:
        lines.extend(
            _format_delivery_preset_markdown(
                delivery_context,
                output_path=output_path,
            )
        )

    if style_source:
        lines.extend(_format_style_source_markdown(style_source))

    if result.failed_items:
        lines.append(f"## ⚠️ 非关键失败 ({len(result.failed_items)})")
        lines.append("")
        for item in result.failed_items:
            lines.append(f"- **{item.get('rule_name', '?')}**: {item.get('reason', '?')}")
        lines.append("")

    if diagnostic_items:
        lines.append(f"## 诊断提示 ({len(diagnostic_items)} 项)")
        lines.append("")
        for item in diagnostic_items:
            lines.append(f"- {describe_execution_diagnostic(item)}")
        lines.append("")

    if count_result:
        lines.append("## 计数口径")
        lines.append("")
        lines.append(f"- Profile: {count_result.get('profile_id', 'basic')}")
        profile_name = str(count_result.get("profile_name") or "").strip()
        if profile_name:
            lines.append(f"- Name: {profile_name}")
        scope = str(count_result.get("scope") or "").strip()
        if scope:
            lines.append(f"- Scope: {scope}")
        included_scopes = count_result.get("included_scopes") or []
        if included_scopes:
            lines.append(f"- Included scopes: {', '.join(map(str, included_scopes))}")
        excluded_scopes = count_result.get("excluded_scopes") or []
        if excluded_scopes:
            lines.append(f"- Excluded scopes: {', '.join(map(str, excluded_scopes))}")
        counts = count_result.get("counts", {}) if isinstance(count_result, dict) else {}
        for key, label in (
            ("cjk_characters", "中文字符"),
            ("english_words", "英文词"),
            ("characters_no_spaces", "不含空格字符"),
            ("paragraph_count", "段落"),
            ("reference_count", "参考文献"),
            ("figure_count", "图"),
            ("table_count", "表"),
            ("equation_count", "公式"),
        ):
            if key in counts:
                lines.append(f"- {label}: {counts[key]}")
        lines.append("")

    if academic_confidence:
        lines.extend(_format_academic_confidence_markdown(academic_confidence))

    if journal_rule_source_governance:
        lines.extend(
            _format_journal_rule_source_governance_markdown(
                journal_rule_source_governance
            )
        )

    if journal_citations:
        lines.extend(_format_journal_citations_markdown(journal_citations))

    if journal_submission_package:
        lines.extend(_format_journal_submission_package_markdown(journal_submission_package))

    if official_document_assembly:
        lines.extend(_format_official_document_assembly_markdown(official_document_assembly))

    if official_numbering_preservation:
        lines.extend(
            _format_official_numbering_preservation_markdown(
                official_numbering_preservation
            )
        )

    if technical_chapter_inventory:
        lines.extend(
            _format_technical_chapter_inventory_markdown(
                technical_chapter_inventory
            )
        )

    if application_section_word_limits:
        lines.extend(
            _format_application_section_word_limits_markdown(
                application_section_word_limits
            )
        )

    if exam_markdown_import:
        lines.extend(format_exam_markdown_import_markdown(exam_markdown_import))

    if exam_question_schema:
        lines.extend(_format_exam_question_schema_markdown(exam_question_schema))

    if exam_delivery_runtime:
        lines.extend(_format_exam_delivery_runtime_markdown(exam_delivery_runtime))

    if field_consistency:
        lines.extend(_format_material_field_consistency_markdown(field_consistency))

    lines.extend(format_material_assembly_markdown(material_assembly))

    if object_preflight:
        lines.extend(_format_object_preflight_markdown(object_preflight))

    if coverage_boundaries:
        lines.extend(_format_coverage_boundaries_markdown(coverage_boundaries))

    if scene_journey_runtime:
        lines.extend(_format_scene_journey_runtime_markdown(scene_journey_runtime))

    lines.append(f"## 变更记录 ({len(changes)} 项)")
    lines.append("")
    for c in changes[:50]:
        if isinstance(c, dict):
            lines.append(
                f"- [{c.get('rule_name', '?')}] {c.get('target', '')} "
                f"→ {c.get('after', '')}"
            )
    lines.append("")

    atomic_write_text(report_path, "\n".join(lines), encoding="utf-8")


def _extract_changes(result: PipelineResult) -> list[dict]:
    """从 tracker 提取变更记录。"""
    if not result.tracker:
        return []
    return [
        {
            "rule_name": r.rule_name,
            "target": r.target,
            "section": r.section,
            "change_type": r.change_type,
            "before": r.before,
            "after": r.after,
            "paragraph_index": r.paragraph_index,
            "success": r.success,
        }
        for r in result.tracker.get_all()
    ]


def _extract_journal_submission_package(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "journal_submission_package", None)
        if context is not None
        else None
    )
    if validation is None:
        return None
    to_dict = getattr(validation, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(validation, dict):
        payload = dict(validation)
    else:
        return None
    status = _clean_text(payload.get("status", ""))
    if not status or status == "not_applicable":
        return None
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    items = [
        item
        for item in (
            _clean_journal_submission_package_item(item)
            for item in list(payload.get("items", []) or [])
        )
        if item
    ]
    issues = [
        issue
        for issue in (
            _clean_journal_submission_package_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    return {
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "default_delivery_preset_id": _clean_text(
            payload.get("default_delivery_preset_id", "")
        ),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "summary": {
            "component_count": int(summary.get("component_count") or 0),
            "required_component_count": int(summary.get("required_component_count") or 0),
            "satisfied_required_count": int(summary.get("satisfied_required_count") or 0),
            "output_count": int(summary.get("output_count") or 0),
            "report_enabled_count": int(summary.get("report_enabled_count") or 0),
            "material_artifact_enabled_count": int(
                summary.get("material_artifact_enabled_count") or 0
            ),
        },
        "items": items,
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _clean_journal_submission_package_item(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    component_id = _clean_text(value.get("component_id", ""))
    if not component_id:
        return {}
    return {
        "component_id": component_id,
        "label": _clean_text(value.get("label", "")),
        "required": bool(value.get("required", False)),
        "preset_id": _clean_text(value.get("preset_id", "")),
        "output_path": _clean_text(value.get("output_path", "")),
        "report_json": bool(value.get("report_json", False)),
        "report_markdown": bool(value.get("report_markdown", False)),
        "material_manifest": bool(value.get("material_manifest", False)),
        "material_package": bool(value.get("material_package", False)),
        "include_structured_intermediate": bool(
            value.get("include_structured_intermediate", False)
        ),
        "satisfied": bool(value.get("satisfied", False)),
    }


def _clean_journal_submission_package_issue(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    kind = _clean_text(value.get("kind", ""))
    message = _clean_text(value.get("message", ""))
    if not kind and not message:
        return {}
    return {
        "component_id": _clean_text(value.get("component_id", "")),
        "kind": kind,
        "severity": _clean_text(value.get("severity", "")) or "warning",
        "expected": _clean_text(value.get("expected", "")),
        "observed": _clean_text(value.get("observed", "")),
        "message": message,
    }


def _format_journal_submission_package_markdown(evidence: dict) -> list[str]:
    lines = ["## 英文期刊投稿包证据", ""]
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    default_preset = _clean_text(evidence.get("default_delivery_preset_id", ""))
    if default_preset:
        lines.append(f"- Default preset: {default_preset}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(
        "- Required components: "
        f"{int(summary.get('satisfied_required_count') or 0)}/"
        f"{int(summary.get('required_component_count') or 0)}"
    )
    lines.append(f"- Runtime outputs: {int(summary.get('output_count') or 0)}")
    lines.append(f"- Report-enabled components: {int(summary.get('report_enabled_count') or 0)}")
    lines.append(
        "- Material package components: "
        f"{int(summary.get('material_artifact_enabled_count') or 0)}"
    )
    items = list(evidence.get("items", []) or [])
    if items:
        lines.append("- Components:")
        for item in items:
            if not isinstance(item, dict):
                continue
            marker = "ok" if item.get("satisfied") else "missing"
            required = "required" if item.get("required") else "optional"
            artifact_parts = []
            if item.get("output_path"):
                artifact_parts.append("docx")
            if item.get("report_json") or item.get("report_markdown"):
                artifact_parts.append("report")
            if item.get("material_manifest") or item.get("material_package"):
                artifact_parts.append("material_package")
            if item.get("include_structured_intermediate"):
                artifact_parts.append("intermediate")
            lines.append(
                "  - "
                f"{_clean_text(item.get('component_id', ''))} "
                f"({required}, {marker}): "
                f"{_join_or_dash(artifact_parts)}"
            )
    issues = list(evidence.get("issues", []) or [])
    if issues:
        lines.append("- Issues:")
        for issue in issues[:20]:
            lines.append(
                "  - "
                f"[{_clean_text(issue.get('severity', 'warning'))}] "
                f"{_clean_text(issue.get('component_id', '-'))}: "
                f"{_clean_text(issue.get('kind', 'issue'))} - "
                f"{_clean_text(issue.get('message', ''))}"
            )
        if len(issues) > 20:
            lines.append("  - ...")
    lines.append("")
    return lines


def _extract_scene_journey_runtime(
    result: PipelineResult,
) -> dict[str, object] | None:
    context = getattr(result, "context", None)
    evidence = (
        getattr(context, "scene_journey_runtime", None)
        if context is not None
        else None
    )
    if evidence is None:
        return None
    to_payload = getattr(evidence, "to_payload", None)
    if callable(to_payload):
        payload = to_payload()
    elif isinstance(evidence, dict):
        payload = dict(evidence)
    else:
        return None
    status = _clean_text(payload.get("status", ""))
    if not status or status == "not_applicable":
        return None
    paths = [
        path
        for path in (
            _clean_scene_journey_runtime_path(path)
            for path in list(payload.get("paths", []) or [])
        )
        if path
    ]
    return {
        "status": status,
        "evidence_scope": _clean_text(payload.get("evidence_scope", "")),
        "static_audit_status": _clean_text(
            payload.get("static_audit_status", "")
        ),
        "source_scan_performed": bool(payload.get("source_scan_performed", False)),
        "pack_ids": _clean_list(payload.get("pack_ids", [])),
        "family_ids": _clean_list(payload.get("family_ids", [])),
        "capability_ids": _clean_list(payload.get("capability_ids", [])),
        "contract_ids": _clean_list(payload.get("contract_ids", [])),
        "contract_count": _safe_int(payload.get("contract_count")),
        "journey_type_ids": _clean_list(payload.get("journey_type_ids", [])),
        "manual_gate_ids": _clean_list(payload.get("manual_gate_ids", [])),
        "manual_gate_count": _safe_int(payload.get("manual_gate_count")),
        "expected_behaviors": _clean_list(payload.get("expected_behaviors", [])),
        "report_expectations": _clean_list(payload.get("report_expectations", [])),
        "artifact_channel_ids": _clean_list(payload.get("artifact_channel_ids", [])),
        "repair_target_types": _clean_list(payload.get("repair_target_types", [])),
        "boundary_notes": _clean_list(payload.get("boundary_notes", [])),
        "path_count": _safe_int(payload.get("path_count")),
        "sampled_path_count": _safe_int(payload.get("sampled_path_count")),
        "paths": paths,
    }


def _clean_scene_journey_runtime_path(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    path_id = _clean_text(value.get("path_id", ""))
    if not path_id:
        return {}
    return {
        "path_id": path_id,
        "journey_type": _clean_text(value.get("journey_type", "")),
        "label": _clean_text(value.get("label", "")),
        "contract_id": _clean_text(value.get("contract_id", "")),
        "manual_gate_ids": _clean_list(value.get("manual_gate_ids", [])),
        "expected_behaviors": _clean_list(value.get("expected_behaviors", [])),
        "report_expectations": _clean_list(value.get("report_expectations", [])),
        "boundary_notes": _clean_list(value.get("boundary_notes", [])),
    }


def _format_scene_journey_runtime_markdown(evidence: dict) -> list[str]:
    lines = ["## 方案旅程运行时证据", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    evidence_scope = _clean_text(evidence.get("evidence_scope", ""))
    if evidence_scope:
        lines.append(f"- Evidence scope: {evidence_scope}")
    static_audit_status = _clean_text(evidence.get("static_audit_status", ""))
    if static_audit_status:
        lines.append(f"- Static audit: {static_audit_status}")
    lines.append(
        "- Source scan during execution: "
        + ("yes" if evidence.get("source_scan_performed") else "no")
    )
    lines.append("- Packs: " + _join_or_dash(evidence.get("pack_ids", [])))
    families = _clean_list(evidence.get("family_ids", []))
    if families:
        lines.append("- Families: " + _join_or_dash(families))
    capabilities = _clean_list(evidence.get("capability_ids", []))
    if capabilities:
        lines.append("- Capabilities: " + _join_or_dash(capabilities))
    contract_ids = _clean_list(evidence.get("contract_ids", []))
    if contract_ids:
        lines.append("- Runtime contracts: " + _join_or_dash(contract_ids))
    lines.append(
        "- Contract paths: "
        f"{_safe_int(evidence.get('path_count'))} paths, "
        + _join_or_dash(evidence.get("journey_type_ids", []))
    )
    reports = _clean_list(evidence.get("report_expectations", []))
    if reports:
        lines.append("- Expected reports: " + _join_or_dash(reports[:18]))
    artifacts = _clean_list(evidence.get("artifact_channel_ids", []))
    if artifacts:
        lines.append("- Artifact channels: " + _join_or_dash(artifacts[:18]))
    repairs = _clean_list(evidence.get("repair_target_types", []))
    if repairs:
        lines.append("- Repair targets: " + _join_or_dash(repairs))
    gates = _clean_list(evidence.get("manual_gate_ids", []))
    if gates:
        lines.append("- Manual/plugin gates: " + _join_or_dash(gates))
    notes = _clean_list(evidence.get("boundary_notes", []))
    if notes:
        lines.append("- Boundary notes:")
        for note in notes[:6]:
            lines.append(f"  - {note}")
    paths = list(evidence.get("paths", []) or [])
    if paths:
        lines.append("- Contract path samples:")
        for path in paths[:8]:
            if not isinstance(path, dict):
                continue
            suffix_parts = []
            reports_for_path = _clean_list(path.get("report_expectations", []))
            gates_for_path = _clean_list(path.get("manual_gate_ids", []))
            if reports_for_path:
                suffix_parts.append("reports=" + _join_or_dash(reports_for_path[:4]))
            if gates_for_path:
                suffix_parts.append("gates=" + _join_or_dash(gates_for_path[:4]))
            suffix = "; " + "; ".join(suffix_parts) if suffix_parts else ""
            lines.append(
                "  - "
                f"{_clean_text(path.get('path_id', ''))} "
                f"[{_clean_text(path.get('journey_type', ''))}]"
                f"{suffix}"
            )
    lines.append("")
    return lines


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
