"""Journal rule-source governance report section."""

from __future__ import annotations

from src.reporting.common import _clean_issue, _clean_list, _clean_text, _join_or_dash


def _extract_journal_rule_source_governance(result) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "journal_rule_source_governance", None)
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
    issues = [
        issue
        for issue in (
            _clean_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    return {
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "rule_source_id": _clean_text(payload.get("rule_source_id", "")),
        "rule_source_label": _clean_text(payload.get("rule_source_label", "")),
        "source_type": _clean_text(payload.get("source_type", "")),
        "source_reference": _clean_text(payload.get("source_reference", "")),
        "version": _clean_text(payload.get("version", "")),
        "review_status": _clean_text(payload.get("review_status", "")),
        "reviewed_by": _clean_text(payload.get("reviewed_by", "")),
        "reviewed_on": _clean_text(payload.get("reviewed_on", "")),
        "count_profile_id": _clean_text(payload.get("count_profile_id", "")),
        "target_journal_name": _clean_text(payload.get("target_journal_name", "")),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "declared_count_profile_ids": _clean_list(
            payload.get("declared_count_profile_ids", [])
        ),
        "include_scope_summary": _clean_list(payload.get("include_scope_summary", [])),
        "exclude_scope_summary": _clean_list(payload.get("exclude_scope_summary", [])),
        "boundary_notes": _clean_list(payload.get("boundary_notes", [])),
        "summary": {
            "declared_count_profile_count": int(
                summary.get("declared_count_profile_count") or 0
            ),
            "matched_count_profile_count": int(
                summary.get("matched_count_profile_count") or 0
            ),
            "reviewed_source_count": int(summary.get("reviewed_source_count") or 0),
            "generic_source_count": int(summary.get("generic_source_count") or 0),
            "target_journal_declared": bool(
                summary.get("target_journal_declared", False)
            ),
        },
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _format_journal_rule_source_governance_markdown(evidence: dict) -> list[str]:
    lines = ["## 英文期刊规则源治理", ""]
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    rule_source_id = _clean_text(evidence.get("rule_source_id", ""))
    if rule_source_id:
        lines.append(f"- Rule source: {rule_source_id}")
    source_label = _clean_text(evidence.get("rule_source_label", ""))
    if source_label:
        lines.append(f"- Source label: {source_label}")
    target_journal = _clean_text(evidence.get("target_journal_name", ""))
    if target_journal:
        lines.append(f"- Target journal: {target_journal}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(f"- Review status: {_clean_text(evidence.get('review_status', '')) or '-'}")
    reviewed_by = _clean_text(evidence.get("reviewed_by", ""))
    reviewed_on = _clean_text(evidence.get("reviewed_on", ""))
    if reviewed_by or reviewed_on:
        lines.append(f"- Reviewed by/on: {reviewed_by or '-'} / {reviewed_on or '-'}")
    lines.append(f"- Version: {_clean_text(evidence.get('version', '')) or '-'}")
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    lines.append(f"- Count profile: {_clean_text(evidence.get('count_profile_id', '')) or '-'}")
    declared_profiles = _clean_list(evidence.get("declared_count_profile_ids", []))
    if declared_profiles:
        lines.append("- Declared CountProfiles: " + _join_or_dash(declared_profiles))
    include_scopes = _clean_list(evidence.get("include_scope_summary", []))
    exclude_scopes = _clean_list(evidence.get("exclude_scope_summary", []))
    if include_scopes:
        lines.append("- Include scope summary: " + _join_or_dash(include_scopes))
    if exclude_scopes:
        lines.append("- Exclude scope summary: " + _join_or_dash(exclude_scopes))
    boundary_notes = _clean_list(evidence.get("boundary_notes", []))
    if boundary_notes:
        lines.append("- Boundary notes:")
        for note in boundary_notes:
            lines.append(f"  - {note}")
    issues = list(evidence.get("issues", []) or [])
    if issues:
        lines.append("- Issues:")
        for issue in issues[:20]:
            lines.append(
                "  - "
                f"[{_clean_text(issue.get('severity', 'warning'))}] "
                f"{_clean_text(issue.get('path', '-'))}: "
                f"{_clean_text(issue.get('kind', 'issue'))} - "
                f"{_clean_text(issue.get('message', ''))}"
            )
        if len(issues) > 20:
            lines.append("  - ...")
    lines.append("")
    return lines
