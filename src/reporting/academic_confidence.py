"""Academic citation and formula confidence report section."""

from __future__ import annotations

import re

from src.reporting.common import _clean_text


def _extract_count_result(result) -> dict | None:
    context = getattr(result, "context", None)
    count_result = getattr(context, "count_result", None) if context is not None else None
    if count_result is None:
        return None
    to_dict = getattr(count_result, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(count_result, dict):
        return count_result
    return None


def _extract_academic_confidence(
    result,
    count_result: dict | None,
) -> dict | None:
    records = _tracker_records(result)
    if not _should_emit_academic_confidence(result, count_result, records):
        return None

    citation = _academic_citation_confidence(records, count_result)
    formula = _academic_formula_confidence(records, count_result)
    issues = [
        *list(citation.get("issues", []) or []),
        *list(formula.get("issues", []) or []),
    ]
    status = "needs_review" if issues else "ok"
    confidence_level = "low" if status == "needs_review" else "high"
    if status == "ok" and (
        citation.get("status") == "not_detected"
        or formula.get("status") == "not_detected"
    ):
        confidence_level = "medium"

    return {
        "status": status,
        "confidence_level": confidence_level,
        "manual_confirmation_required": bool(issues),
        "profile_id": _clean_text((count_result or {}).get("profile_id", "")),
        "scope": _clean_text((count_result or {}).get("scope", "")),
        "citation": citation,
        "formula": formula,
        "issues": issues,
    }


def _tracker_records(result) -> list:
    tracker = getattr(result, "tracker", None)
    if tracker is None:
        return []
    return list(tracker.get_all())


def _should_emit_academic_confidence(
    result,
    count_result: dict | None,
    records: list,
) -> bool:
    profile_id = _clean_text((count_result or {}).get("profile_id", ""))
    if profile_id in {"thesis_cn", "school_thesis", "journal_words", "journal_display_items"}:
        return True

    config = getattr(result, "config", None)
    compliance = getattr(config, "compliance_profile", None)
    for value in (
        getattr(compliance, "profile_id", ""),
        getattr(compliance, "rule_family", ""),
        getattr(compliance, "count_profile_id", ""),
    ):
        if _clean_text(value) in {
            "thesis_cn",
            "school_thesis",
            "academic_thesis",
            "journal_submission",
        }:
            return True

    return any(
        _clean_text(getattr(record, "rule_name", ""))
        in {"citation_link", "reference_format", "equation_table_format"}
        for record in records
    )


def _academic_citation_confidence(
    records: list,
    count_result: dict | None,
) -> dict[str, object]:
    counts = (count_result or {}).get("counts", {}) if isinstance(count_result, dict) else {}
    reference_count = int(counts.get("reference_count") or 0)
    paragraph_linked = 0
    linked: int | None = None
    unresolved = 0
    duplicates = 0
    reference_targets = 0
    entry_bookmarks = 0
    number_bookmarks = 0
    issues: list[dict[str, object]] = []
    record_count = 0

    for record in records:
        if _clean_text(getattr(record, "rule_name", "")) != "citation_link":
            continue
        record_count += 1
        before = _clean_text(getattr(record, "before", ""))
        after = _clean_text(getattr(record, "after", ""))
        change_type = _clean_text(getattr(record, "change_type", ""))
        paragraph_linked += _extract_int(after, r"linked citation fields \((\d+)\)")
        if _clean_text(getattr(record, "target", "")) == "summary":
            linked = _extract_int(after, r"linked=(\d+)", default=linked or 0)
            unresolved = _extract_int(after, r"unresolved=(\d+)", default=unresolved)
            duplicates = _extract_int(after, r"duplicates=(\d+)", default=duplicates)
            reference_targets = _extract_int(before, r"references=(\d+)", default=reference_targets)
            entry_bookmarks = _extract_int(before, r"entry_bookmarks=(\d+)", default=entry_bookmarks)
            number_bookmarks = _extract_int(before, r"number_bookmarks=(\d+)", default=number_bookmarks)
        if change_type == "skip" or not bool(getattr(record, "success", True)):
            issues.append(_academic_issue_from_record("citation", record))

    linked_count = linked if linked is not None else paragraph_linked
    if unresolved > 0:
        issues.append(
            {
                "domain": "citation",
                "severity": "warning",
                "reason": f"{unresolved} citation number(s) could not be linked to references.",
            }
        )
    if duplicates > 0:
        issues.append(
            {
                "domain": "citation",
                "severity": "warning",
                "reason": f"{duplicates} duplicated reference number(s) require manual review.",
            }
        )

    if issues:
        status = "needs_review"
        confidence_level = "low"
    elif linked_count > 0 or reference_targets > 0 or reference_count > 0:
        status = "ok"
        confidence_level = "high" if linked_count > 0 or reference_targets > 0 else "medium"
    else:
        status = "not_detected"
        confidence_level = "medium"

    return {
        "status": status,
        "confidence_level": confidence_level,
        "reference_count": reference_count,
        "reference_targets": reference_targets,
        "entry_bookmarks_added": entry_bookmarks,
        "number_bookmarks_added": number_bookmarks,
        "linked_citation_count": linked_count,
        "unresolved_citation_count": unresolved,
        "duplicate_reference_count": duplicates,
        "tracker_record_count": record_count,
        "issues": issues,
    }


def _academic_formula_confidence(
    records: list,
    count_result: dict | None,
) -> dict[str, object]:
    counts = (count_result or {}).get("counts", {}) if isinstance(count_result, dict) else {}
    equation_count = int(counts.get("equation_count") or 0)
    table_count = 0
    normalized_numbers = 0
    skipped_numbers = 0
    issues: list[dict[str, object]] = []
    record_count = 0

    for record in records:
        if _clean_text(getattr(record, "rule_name", "")) != "equation_table_format":
            continue
        record_count += 1
        target = _clean_text(getattr(record, "target", ""))
        change_type = _clean_text(getattr(record, "change_type", ""))
        if "公式表格" in target:
            table_count += _extract_int(target, r"(\d+)", default=0)
        elif "公式编号" in target and change_type != "skip":
            normalized_numbers += _extract_int(target, r"(\d+)", default=0)
        elif "公式编号" in target and change_type == "skip":
            skipped_numbers += _extract_int(target, r"(\d+)", default=0)
            issues.append(_academic_issue_from_record("formula", record))
        elif change_type == "skip" or not bool(getattr(record, "success", True)):
            issues.append(_academic_issue_from_record("formula", record))

    if issues:
        status = "needs_review"
        confidence_level = "low"
    elif equation_count > 0 or table_count > 0 or normalized_numbers > 0:
        status = "ok"
        confidence_level = "high"
    else:
        status = "not_detected"
        confidence_level = "medium"

    return {
        "status": status,
        "confidence_level": confidence_level,
        "equation_count": equation_count,
        "formatted_equation_table_count": table_count,
        "normalized_number_count": normalized_numbers,
        "skipped_number_count": skipped_numbers,
        "tracker_record_count": record_count,
        "issues": issues,
    }


def _academic_issue_from_record(domain: str, record) -> dict[str, object]:
    reason = _clean_text(getattr(record, "failure_reason", ""))
    if not reason:
        reason = _clean_text(getattr(record, "after", "")) or _clean_text(
            getattr(record, "before", "")
        )
    return {
        "domain": domain,
        "severity": "warning",
        "rule_name": _clean_text(getattr(record, "rule_name", "")),
        "target": _clean_text(getattr(record, "target", "")),
        "section": _clean_text(getattr(record, "section", "")),
        "change_type": _clean_text(getattr(record, "change_type", "")),
        "reason": reason,
        "paragraph_index": int(getattr(record, "paragraph_index", -1) or -1),
    }


def _extract_int(text: str, pattern: str, *, default: int = 0) -> int:
    match = re.search(pattern, text or "")
    if match is None:
        return int(default or 0)
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return int(default or 0)


def _format_academic_confidence_markdown(evidence: dict) -> list[str]:
    lines = ["## 学术引用与公式置信度", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        f"- Confidence: {_clean_text(evidence.get('confidence_level', '')) or '-'}"
    )
    profile_id = _clean_text(evidence.get("profile_id", ""))
    if profile_id:
        lines.append(f"- Profile: {profile_id}")
    citation = evidence.get("citation", {}) if isinstance(evidence, dict) else {}
    formula = evidence.get("formula", {}) if isinstance(evidence, dict) else {}
    if isinstance(citation, dict):
        lines.append(
            "- Citation: "
            f"status={_clean_text(citation.get('status', '')) or '-'}, "
            f"references={int(citation.get('reference_count') or 0)}, "
            f"linked={int(citation.get('linked_citation_count') or 0)}, "
            f"unresolved={int(citation.get('unresolved_citation_count') or 0)}, "
            f"duplicates={int(citation.get('duplicate_reference_count') or 0)}"
        )
    if isinstance(formula, dict):
        lines.append(
            "- Formula: "
            f"status={_clean_text(formula.get('status', '')) or '-'}, "
            f"equations={int(formula.get('equation_count') or 0)}, "
            f"tables={int(formula.get('formatted_equation_table_count') or 0)}, "
            f"normalized_numbers={int(formula.get('normalized_number_count') or 0)}, "
            f"skipped_numbers={int(formula.get('skipped_number_count') or 0)}"
        )
    issues = list(evidence.get("issues", []) or []) if isinstance(evidence, dict) else []
    if issues:
        lines.append("- Manual review:")
        for issue in issues[:20]:
            if not isinstance(issue, dict):
                continue
            reason = _clean_text(issue.get("reason", ""))
            if not reason:
                reason = _clean_text(issue.get("target", ""))
            lines.append(
                "  - "
                f"{_clean_text(issue.get('domain', 'academic'))}: "
                f"{reason or '-'}"
            )
    lines.append("")
    return lines
