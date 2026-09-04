"""Material, object preflight, and coverage report sections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.reporting.common import (
    _clean_list,
    _clean_mapping_lists,
    _clean_module_skips,
    _clean_text,
    _join_or_dash,
)
from src.reporting.execution_payload import (
    material_field_issue_payload as _material_field_issue_payload,
)

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def _extract_material_field_consistency(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    consistency = (
        getattr(context, "material_field_consistency", None)
        if context is not None
        else None
    )
    if consistency is None:
        return None

    items = []
    issues = []
    for item in list(getattr(consistency, "items", []) or []):
        item_issues = [
            _material_field_issue_payload(issue)
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

    return {
        "schema_id": _clean_text(getattr(consistency, "schema_id", "")),
        "family_id": _clean_text(getattr(consistency, "family_id", "")),
        "status": _clean_text(getattr(consistency, "status", "")),
        "field_count": len(items),
        "issue_count": len(issues),
        "items": items,
        "issues": issues,
    }


def _format_material_field_consistency_markdown(evidence: dict) -> list[str]:
    lines = ["## Material Field Consistency", ""]
    schema_id = _clean_text(evidence.get("schema_id", ""))
    if schema_id:
        lines.append(f"- Schema: {schema_id}")
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(f"- Fields: {int(evidence.get('field_count') or 0)}")
    lines.append(f"- Issues: {int(evidence.get('issue_count') or 0)}")
    for item in list(evidence.get("items", []) or [])[:20]:
        lines.append(
            "- "
            f"{_clean_text(item.get('field_key', '?'))}: "
            f"{_clean_text(item.get('status', 'ok'))}, "
            f"occurrences={int(item.get('occurrence_count') or 0)}"
        )
        for issue in list(item.get("issues", []) or [])[:5]:
            lines.append(
                "  - "
                f"{_clean_text(issue.get('kind', 'issue'))}: "
                f"{_clean_text(issue.get('message', ''))}"
            )
    if int(evidence.get("field_count") or 0) > 20:
        lines.append("- ...")
    lines.append("")
    return lines


def _extract_object_preflight(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    if context is None:
        return None

    policy = getattr(context, "object_preflight_policy", None)
    preflight = getattr(context, "object_preflight", None)
    if policy is None and preflight is None:
        return None

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


def _format_object_preflight_markdown(evidence: dict) -> list[str]:
    lines = ["## 对象预检证据", ""]
    family_id = _clean_text(evidence.get("planning_family_id", ""))
    if family_id:
        lines.append(f"- Planning family: {family_id}")
    schema_id = _clean_text(evidence.get("material_schema_id", ""))
    if schema_id:
        lines.append(f"- Material schema: {schema_id}")
    schema_ids = _clean_list(evidence.get("material_schema_ids", []))
    if schema_ids:
        lines.append("- Material schemas: " + _join_or_dash(schema_ids))
    lines.append(
        "- Planning touchpoints: "
        + _join_or_dash(evidence.get("planning_ooxml_touchpoints", []))
    )
    lines.append(
        "- Recommended targets: "
        + _join_or_dash(evidence.get("recommended_scan_targets", []))
    )
    lines.append("- Scan targets: " + _join_or_dash(evidence.get("scan_targets", [])))
    lines.append("- Block on: " + _join_or_dash(evidence.get("block_on", [])))
    lines.append(f"- Findings: {int(evidence.get('findings_count') or 0)}")
    for finding in list(evidence.get("findings", []) or [])[:20]:
        lines.append(
            "- "
            f"[{_clean_text(finding.get('severity', 'warning'))}] "
            f"{_clean_text(finding.get('kind', '?'))} @ "
            f"{_clean_text(finding.get('location', '-'))}: "
            f"{_clean_text(finding.get('message', ''))}"
        )
    if int(evidence.get("findings_count") or 0) > 20:
        lines.append("- ...")
    module_skips = list(evidence.get("module_skips", []) or [])
    if module_skips:
        lines.append("- Skipped modules:")
        for skip in module_skips[:20]:
            lines.append(
                "  - "
                f"{_clean_text(skip.get('module_name', '?'))}: "
                f"{_join_or_dash(skip.get('finding_kinds', []))}"
            )
        if len(module_skips) > 20:
            lines.append("  - ...")
    lines.append("")
    return lines


def _extract_coverage_boundaries(result: PipelineResult) -> list[dict[str, object]]:
    context = getattr(result, "context", None)
    boundaries = (
        getattr(context, "coverage_boundaries", None) if context is not None else None
    )
    if not boundaries:
        return []
    return [
        item
        for item in (
            _clean_coverage_boundary_item(value) for value in list(boundaries or [])
        )
        if item
    ]


def _clean_coverage_boundary_item(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    pack_id = _clean_text(value.get("pack_id", ""))
    if not pack_id:
        return {}
    closure_tasks = [
        task
        for task in (
            _clean_coverage_closure_task(task)
            for task in list(value.get("closure_tasks", []) or [])
        )
        if task
    ]
    return {
        "pack_id": pack_id,
        "label": _clean_text(value.get("label", "")),
        "boundary": _clean_text(value.get("boundary", "")),
        "primary_landings": _clean_list(value.get("primary_landings", [])),
        "secondary_landings": _clean_list(value.get("secondary_landings", [])),
        "capability_axis_ids": _clean_list(value.get("capability_axis_ids", [])),
        "implemented_closures": _clean_list(value.get("implemented_closures", [])),
        "missing_closures": _clean_list(value.get("missing_closures", [])),
        "closure_tasks": closure_tasks,
        "plugin_manual_gate": _clean_plugin_manual_gate(
            value.get("plugin_manual_gate")
        ),
    }


def _clean_plugin_manual_gate(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    gate_id = _clean_text(value.get("gate_id", ""))
    if not gate_id:
        return {}
    return {
        "gate_id": gate_id,
        "pack_id": _clean_text(value.get("pack_id", "")),
        "label": _clean_text(value.get("label", "")),
        "plugin_entry_id": _clean_text(value.get("plugin_entry_id", "")),
        "plugin_entry_label": _clean_text(value.get("plugin_entry_label", "")),
        "manual_confirmation_required": bool(
            value.get("manual_confirmation_required", False)
        ),
        "confidence_report_required": bool(
            value.get("confidence_report_required", False)
        ),
        "boundary_report_required": bool(
            value.get("boundary_report_required", False)
        ),
        "blocks_core_execution_until_confirmed": bool(
            value.get("blocks_core_execution_until_confirmed", False)
        ),
        "professional_review_required": bool(
            value.get("professional_review_required", False)
        ),
        "risk_domain_ids": _clean_list(value.get("risk_domain_ids", [])),
        "accepted_inputs": _clean_list(value.get("accepted_inputs", [])),
        "unsupported_core_inputs": _clean_list(
            value.get("unsupported_core_inputs", [])
        ),
        "confirmation_scope": _clean_list(value.get("confirmation_scope", [])),
        "confirmation_decision_states": _clean_list(
            value.get("confirmation_decision_states", [])
        ),
        "report_fields": _clean_list(value.get("report_fields", [])),
    }


def _clean_coverage_closure_task(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    summary = _clean_text(value.get("summary", ""))
    if not summary:
        return {}
    return {
        "summary": summary,
        "priority": _clean_text(value.get("priority", "")),
        "owner": _clean_text(value.get("owner", "")),
        "target_phase": _clean_text(value.get("target_phase", "")),
        "validation_commands": _clean_list(value.get("validation_commands", [])),
    }


def _format_coverage_boundaries_markdown(items: list[dict[str, object]]) -> list[str]:
    lines = ["## 方案边界证据", ""]
    for item in items:
        pack_id = _clean_text(item.get("pack_id", ""))
        label = _clean_text(item.get("label", ""))
        title = pack_id if not label else f"{pack_id} ({label})"
        lines.append(f"- Coverage pack: {title}")
        boundary = _clean_text(item.get("boundary", ""))
        if boundary:
            lines.append(f"  - Boundary: {boundary}")
        lines.append(
            "  - Primary landings: "
            + _join_or_dash(item.get("primary_landings", []))
        )
        lines.append(
            "  - Secondary landings: "
            + _join_or_dash(item.get("secondary_landings", []))
        )
        lines.append(
            "  - Capability axes: "
            + _join_or_dash(item.get("capability_axis_ids", []))
        )
        gate = item.get("plugin_manual_gate", {})
        if isinstance(gate, dict) and gate:
            lines.append("  - Plugin/manual gate:")
            plugin_entry = _clean_text(gate.get("plugin_entry_id", ""))
            if plugin_entry:
                lines.append(f"    - Plugin entry: {plugin_entry}")
            lines.append(
                "    - Manual confirmation: "
                + (
                    "required"
                    if gate.get("manual_confirmation_required")
                    else "optional"
                )
            )
            lines.append(
                "    - Confidence report: "
                + (
                    "required"
                    if gate.get("confidence_report_required")
                    else "optional"
                )
            )
            risk_domains = _clean_list(gate.get("risk_domain_ids", []))
            if risk_domains:
                lines.append(
                    "    - Risk domains: " + _join_or_dash(risk_domains)
                )
            decisions = _clean_list(gate.get("confirmation_decision_states", []))
            if decisions:
                lines.append(
                    "    - Decision states: " + _join_or_dash(decisions)
                )
            report_fields = _clean_list(gate.get("report_fields", []))
            if report_fields:
                lines.append(
                    "    - Report fields: " + _join_or_dash(report_fields)
                )
            unsupported = _clean_list(gate.get("unsupported_core_inputs", []))
            if unsupported:
                lines.append(
                    "    - Core exclusions: " + _join_or_dash(unsupported)
                )
        missing = _clean_list(item.get("missing_closures", []))
        if missing:
            lines.append("  - Missing closures: " + " / ".join(missing[:3]))
        tasks = list(item.get("closure_tasks", []) or [])
        if tasks:
            lines.append("  - Closure tasks:")
            for task in tasks[:3]:
                summary = _clean_text(task.get("summary", ""))
                metadata = "/".join(
                    value
                    for value in (
                        _clean_text(task.get("priority", "")),
                        _clean_text(task.get("owner", "")),
                        _clean_text(task.get("target_phase", "")),
                    )
                    if value
                )
                prefix = f"[{metadata}] " if metadata else ""
                lines.append(f"    - {prefix}{summary}")
    lines.append("")
    return lines
