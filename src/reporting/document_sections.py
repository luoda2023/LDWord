"""Document-family report sections extracted from the main report writer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.reporting.common import _clean_list, _clean_text, _join_or_dash

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def _extract_official_numbering_preservation(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "official_numbering_preservation", None)
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
            _clean_official_numbering_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    changed_headings = [
        item
        for item in (
            _clean_official_numbering_changed_heading(item)
            for item in list(payload.get("changed_headings", []) or [])
        )
        if item
    ]
    return {
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "strategy": _clean_text(payload.get("strategy", "")),
        "rule_family": _clean_text(payload.get("rule_family", "")),
        "profile_id": _clean_text(payload.get("profile_id", "")),
        "material_schema_ids": _clean_list(payload.get("material_schema_ids", [])),
        "word_surfaces": _clean_list(payload.get("word_surfaces", [])),
        "heading_numbering_enabled": bool(
            payload.get("heading_numbering_enabled", False)
        ),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "summary": {
            "heading_count": int(summary.get("heading_count") or 0),
            "changed_heading_count": int(summary.get("changed_heading_count") or 0),
            "heading_numbering_record_count": int(
                summary.get("heading_numbering_record_count") or 0
            ),
            "heading_numbering_changed_count": int(
                summary.get("heading_numbering_changed_count") or 0
            ),
        },
        "changed_headings": changed_headings,
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _clean_official_numbering_issue(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    kind = _clean_text(value.get("kind", ""))
    message = _clean_text(value.get("message", ""))
    if not kind and not message:
        return {}
    return {
        "kind": kind,
        "severity": _clean_text(value.get("severity", "")) or "warning",
        "expected": _clean_text(value.get("expected", "")),
        "observed": _clean_text(value.get("observed", "")),
        "paragraph_index": int(value.get("paragraph_index") or -1),
        "message": message,
    }


def _clean_official_numbering_changed_heading(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    before = _clean_text(value.get("before", ""))
    after = _clean_text(value.get("after", ""))
    if not before and not after:
        return {}
    return {
        "paragraph_index": int(value.get("paragraph_index") or -1),
        "level": int(value.get("level") or 0),
        "before": before,
        "after": after,
    }


def _format_official_numbering_preservation_markdown(evidence: dict) -> list[str]:
    lines = ["## 公文编号保留证据", ""]
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    rule_family = _clean_text(evidence.get("rule_family", ""))
    if rule_family:
        lines.append(f"- Rule family: {rule_family}")
    profile_id = _clean_text(evidence.get("profile_id", ""))
    if profile_id:
        lines.append(f"- Profile: {profile_id}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(f"- Strategy: {_clean_text(evidence.get('strategy', '')) or '-'}")
    lines.append(
        "- Heading numbering module: "
        + ("enabled" if evidence.get("heading_numbering_enabled") else "disabled")
    )
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(f"- Headings detected: {int(summary.get('heading_count') or 0)}")
    lines.append(f"- Changed headings: {int(summary.get('changed_heading_count') or 0)}")
    lines.append(
        "- Heading-numbering records: "
        f"{int(summary.get('heading_numbering_record_count') or 0)}"
    )
    lines.append(
        "- Heading-numbering changed count: "
        f"{int(summary.get('heading_numbering_changed_count') or 0)}"
    )
    surfaces = _clean_list(evidence.get("word_surfaces", []))
    if surfaces:
        lines.append("- Word surfaces: " + _join_or_dash(surfaces))
    changed_headings = list(evidence.get("changed_headings", []) or [])
    if changed_headings:
        lines.append("- Changed heading samples:")
        for item in changed_headings[:10]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  - "
                f"p{int(item.get('paragraph_index') or -1)} "
                f"L{int(item.get('level') or 0)}: "
                f"{_clean_text(item.get('before', ''))} -> "
                f"{_clean_text(item.get('after', ''))}"
            )
    issues = list(evidence.get("issues", []) or [])
    if issues:
        lines.append("- Issues:")
        for issue in issues[:20]:
            if not isinstance(issue, dict):
                continue
            lines.append(
                "  - "
                f"[{_clean_text(issue.get('severity', 'warning'))}] "
                f"{_clean_text(issue.get('kind', 'issue'))}: "
                f"{_clean_text(issue.get('message', ''))}"
            )
        if len(issues) > 20:
            lines.append("  - ...")
    lines.append("")
    return lines


def _extract_technical_chapter_inventory(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "technical_chapter_inventory", None)
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
            _clean_technical_chapter_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    chapters = [
        item
        for item in (
            _clean_technical_chapter_item(item)
            for item in list(payload.get("chapters", []) or [])
        )
        if item
    ]
    headings = [
        item
        for item in (
            _clean_technical_chapter_item(item)
            for item in list(payload.get("headings", []) or [])
        )
        if item
    ]
    return {
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "rule_family": _clean_text(payload.get("rule_family", "")),
        "profile_id": _clean_text(payload.get("profile_id", "")),
        "material_schema_ids": _clean_list(payload.get("material_schema_ids", [])),
        "word_surfaces": _clean_list(payload.get("word_surfaces", [])),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "summary": {
            "heading_count": int(summary.get("heading_count") or 0),
            "chapter_count": int(summary.get("chapter_count") or 0),
            "appendix_count": int(summary.get("appendix_count") or 0),
            "max_heading_level": int(summary.get("max_heading_level") or 0),
            "table_count": int(summary.get("table_count") or 0),
            "figure_count": int(summary.get("figure_count") or 0),
            "toc_present": bool(summary.get("toc_present", False)),
        },
        "chapters": chapters,
        "headings": headings,
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _clean_technical_chapter_issue(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    kind = _clean_text(value.get("kind", ""))
    message = _clean_text(value.get("message", ""))
    if not kind and not message:
        return {}
    return {
        "kind": kind,
        "severity": _clean_text(value.get("severity", "")) or "warning",
        "expected": _clean_text(value.get("expected", "")),
        "observed": _clean_text(value.get("observed", "")),
        "message": message,
    }


def _clean_technical_chapter_item(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    title = _clean_text(value.get("title", ""))
    if not title:
        return {}
    return {
        "paragraph_index": int(value.get("paragraph_index") or -1),
        "level": int(value.get("level") or 0),
        "title": title,
        "section_type": _clean_text(value.get("section_type", "")),
        "start_index": int(value.get("start_index") or -1),
        "end_index": int(value.get("end_index") or -1),
    }


def _format_technical_chapter_inventory_markdown(evidence: dict) -> list[str]:
    lines = ["## 技术长文档章节清单", ""]
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    rule_family = _clean_text(evidence.get("rule_family", ""))
    if rule_family:
        lines.append(f"- Rule family: {rule_family}")
    profile_id = _clean_text(evidence.get("profile_id", ""))
    if profile_id:
        lines.append(f"- Profile: {profile_id}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(f"- Chapters: {int(summary.get('chapter_count') or 0)}")
    lines.append(f"- Headings: {int(summary.get('heading_count') or 0)}")
    lines.append(f"- Appendix headings: {int(summary.get('appendix_count') or 0)}")
    lines.append(f"- Max heading level: {int(summary.get('max_heading_level') or 0)}")
    lines.append(f"- Tables: {int(summary.get('table_count') or 0)}")
    lines.append(f"- Figures: {int(summary.get('figure_count') or 0)}")
    lines.append("- TOC present: " + ("yes" if summary.get("toc_present") else "no"))
    surfaces = _clean_list(evidence.get("word_surfaces", []))
    if surfaces:
        lines.append("- Word surfaces: " + _join_or_dash(surfaces))
    chapters = list(evidence.get("chapters", []) or [])
    if chapters:
        lines.append("- Chapters:")
        for item in chapters[:20]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  - "
                f"p{int(item.get('paragraph_index') or -1)} "
                f"L{int(item.get('level') or 0)} "
                f"[{_clean_text(item.get('section_type', '')) or '-'}] "
                f"{_clean_text(item.get('title', ''))}"
            )
    issues = list(evidence.get("issues", []) or [])
    if issues:
        lines.append("- Issues:")
        for issue in issues[:20]:
            if not isinstance(issue, dict):
                continue
            lines.append(
                "  - "
                f"[{_clean_text(issue.get('severity', 'warning'))}] "
                f"{_clean_text(issue.get('kind', 'issue'))}: "
                f"{_clean_text(issue.get('message', ''))}"
            )
        if len(issues) > 20:
            lines.append("  - ...")
    lines.append("")
    return lines


def _extract_application_section_word_limits(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "application_section_word_limits", None)
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
    sections = [
        item
        for item in (
            _clean_application_section_word_limit_item(item)
            for item in list(payload.get("sections", []) or [])
        )
        if item
    ]
    issues = [
        issue
        for issue in (
            _clean_application_section_word_limit_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    return {
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "profile_id": _clean_text(payload.get("profile_id", "")),
        "profile_name": _clean_text(payload.get("profile_name", "")),
        "rule_family": _clean_text(payload.get("rule_family", "")),
        "material_schema_ids": _clean_list(payload.get("material_schema_ids", [])),
        "word_surfaces": _clean_list(payload.get("word_surfaces", [])),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "summary": {
            "section_count": int(summary.get("section_count") or 0),
            "matched_section_count": int(summary.get("matched_section_count") or 0),
            "exceeded_section_count": int(summary.get("exceeded_section_count") or 0),
            "required_missing_count": int(summary.get("required_missing_count") or 0),
            "table_count": int(summary.get("table_count") or 0),
        },
        "sections": sections,
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _clean_application_section_word_limit_item(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    section_id = _clean_text(value.get("section_id", ""))
    heading_title = _clean_text(value.get("heading_title", ""))
    if not section_id and not heading_title:
        return {}
    counts = value.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    limits = value.get("limits", {})
    if not isinstance(limits, dict):
        limits = {}
    return {
        "section_id": section_id,
        "label": _clean_text(value.get("label", "")),
        "heading_title": heading_title,
        "paragraph_index": int(value.get("paragraph_index") or -1),
        "start_index": int(value.get("start_index") or -1),
        "end_index": int(value.get("end_index") or -1),
        "status": _clean_text(value.get("status", "")) or "ok",
        "counts": {
            "characters_no_spaces": int(counts.get("characters_no_spaces") or 0),
            "cjk_characters": int(counts.get("cjk_characters") or 0),
            "english_words": int(counts.get("english_words") or 0),
        },
        "limits": {
            "max_characters_no_spaces": int(
                limits.get("max_characters_no_spaces") or 0
            ),
            "max_cjk_characters": int(limits.get("max_cjk_characters") or 0),
            "max_english_words": int(limits.get("max_english_words") or 0),
        },
    }


def _clean_application_section_word_limit_issue(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    kind = _clean_text(value.get("kind", ""))
    message = _clean_text(value.get("message", ""))
    if not kind and not message:
        return {}
    return {
        "kind": kind,
        "section_id": _clean_text(value.get("section_id", "")),
        "severity": _clean_text(value.get("severity", "")) or "warning",
        "expected": _clean_text(value.get("expected", "")),
        "observed": _clean_text(value.get("observed", "")),
        "message": message,
    }


def _format_application_section_word_limits_markdown(evidence: dict) -> list[str]:
    lines = ["## 应用材料分节限字证据", ""]
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    lines.append(f"- Profile: {_clean_text(evidence.get('profile_id', '')) or '-'}")
    profile_name = _clean_text(evidence.get("profile_name", ""))
    if profile_name:
        lines.append(f"- Name: {profile_name}")
    rule_family = _clean_text(evidence.get("rule_family", ""))
    if rule_family:
        lines.append(f"- Rule family: {rule_family}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(f"- Sections detected: {int(summary.get('section_count') or 0)}")
    lines.append(
        f"- Matched limited sections: {int(summary.get('matched_section_count') or 0)}"
    )
    lines.append(
        f"- Exceeded sections: {int(summary.get('exceeded_section_count') or 0)}"
    )
    lines.append(
        f"- Required missing sections: {int(summary.get('required_missing_count') or 0)}"
    )
    surfaces = _clean_list(evidence.get("word_surfaces", []))
    if surfaces:
        lines.append("- Word surfaces: " + _join_or_dash(surfaces))
    sections = list(evidence.get("sections", []) or [])
    if sections:
        lines.append("- Section samples:")
        for item in sections[:20]:
            if not isinstance(item, dict):
                continue
            counts = item.get("counts", {})
            limits = item.get("limits", {})
            if not isinstance(counts, dict):
                counts = {}
            if not isinstance(limits, dict):
                limits = {}
            observed = int(counts.get("characters_no_spaces") or 0)
            max_value = int(limits.get("max_characters_no_spaces") or 0)
            limit_text = f"/{max_value}" if max_value else ""
            lines.append(
                "  - "
                f"{_clean_text(item.get('section_id', ''))}: "
                f"{_clean_text(item.get('heading_title', ''))} "
                f"[{_clean_text(item.get('status', 'ok'))}] "
                f"chars={observed}{limit_text}"
            )
    issues = list(evidence.get("issues", []) or [])
    if issues:
        lines.append("- Issues:")
        for issue in issues[:20]:
            if not isinstance(issue, dict):
                continue
            lines.append(
                "  - "
                f"[{_clean_text(issue.get('severity', 'warning'))}] "
                f"{_clean_text(issue.get('section_id', '-'))}: "
                f"{_clean_text(issue.get('kind', 'issue'))} - "
                f"{_clean_text(issue.get('message', ''))}"
            )
        if len(issues) > 20:
            lines.append("  - ...")
    lines.append("")
    return lines
