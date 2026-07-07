"""Journal citation report section."""

from __future__ import annotations

from src.reporting.common import _clean_list, _clean_text, _join_or_dash


def _extract_journal_citations(result) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "journal_citations", None)
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
            _clean_journal_citation_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    return {
        "schema_id": _clean_text(payload.get("schema_id", "")),
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "source_key": _clean_text(payload.get("source_key", "")),
        "citation_source": _clean_text(payload.get("citation_source", "")),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "summary": {
            "source_format": _clean_text(summary.get("source_format", "")),
            "reference_count": int(summary.get("reference_count") or 0),
            "citation_count": int(summary.get("citation_count") or 0),
            "matched_citation_count": int(summary.get("matched_citation_count") or 0),
            "missing_reference_count": int(summary.get("missing_reference_count") or 0),
            "unreferenced_source_count": int(summary.get("unreferenced_source_count") or 0),
            "duplicate_key_count": int(summary.get("duplicate_key_count") or 0),
            "incomplete_reference_count": int(summary.get("incomplete_reference_count") or 0),
        },
        "reference_keys": _clean_list(payload.get("reference_keys", [])),
        "citation_keys": _clean_list(payload.get("citation_keys", [])),
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _clean_journal_citation_issue(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    kind = _clean_text(value.get("kind", ""))
    message = _clean_text(value.get("message", ""))
    if not kind and not message:
        return {}
    return {
        "path": _clean_text(value.get("path", "")),
        "kind": kind,
        "severity": _clean_text(value.get("severity", "")) or "warning",
        "expected": _clean_text(value.get("expected", "")),
        "observed": _clean_text(value.get("observed", "")),
        "message": message,
    }


def _format_journal_citations_markdown(evidence: dict) -> list[str]:
    lines = ["## 英文期刊引用源校验", ""]
    schema_id = _clean_text(evidence.get("schema_id", ""))
    if schema_id:
        lines.append(f"- Schema: {schema_id}")
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    source_key = _clean_text(evidence.get("source_key", ""))
    if source_key:
        lines.append(f"- Source: {source_key}")
    citation_source = _clean_text(evidence.get("citation_source", ""))
    if citation_source:
        lines.append(f"- Citation source: {citation_source}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(f"- Format: {_clean_text(summary.get('source_format', '')) or '-'}")
    lines.append(f"- References: {int(summary.get('reference_count') or 0)}")
    lines.append(f"- Citations: {int(summary.get('citation_count') or 0)}")
    lines.append(f"- Matched: {int(summary.get('matched_citation_count') or 0)}")
    lines.append(f"- Missing references: {int(summary.get('missing_reference_count') or 0)}")
    lines.append(f"- Unreferenced source entries: {int(summary.get('unreferenced_source_count') or 0)}")
    lines.append(f"- Duplicate keys: {int(summary.get('duplicate_key_count') or 0)}")
    lines.append(f"- Incomplete references: {int(summary.get('incomplete_reference_count') or 0)}")
    reference_keys = _clean_list(evidence.get("reference_keys", []))
    citation_keys = _clean_list(evidence.get("citation_keys", []))
    if reference_keys:
        lines.append("- Reference keys: " + _join_or_dash(reference_keys[:20]))
    if citation_keys:
        lines.append("- Citation keys: " + _join_or_dash(citation_keys[:20]))
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
