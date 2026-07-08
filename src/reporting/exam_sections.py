"""Exam-family report sections extracted from the main report writer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.reporting.common import _clean_list, _clean_text, _join_or_dash

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def _extract_exam_question_schema(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    validation = (
        getattr(context, "exam_question_schema", None)
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
            _clean_exam_question_schema_issue(issue)
            for issue in list(payload.get("issues", []) or [])
        )
        if issue
    ]
    return {
        "schema_id": _clean_text(payload.get("schema_id", "")),
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "source_key": _clean_text(payload.get("source_key", "")),
        "manual_confirmation_required": bool(
            payload.get("manual_confirmation_required", False)
        ),
        "summary": {
            "section_count": int(summary.get("section_count") or 0),
            "question_count": int(summary.get("question_count") or 0),
            "answered_question_count": int(
                summary.get("answered_question_count") or 0
            ),
            "analysis_count": int(summary.get("analysis_count") or 0),
            "knowledge_point_count": int(
                summary.get("knowledge_point_count") or 0
            ),
            "figure_count": int(summary.get("figure_count") or 0),
            "scored_question_count": int(summary.get("scored_question_count") or 0),
            "declared_total_score": summary.get("declared_total_score"),
            "computed_total_score": summary.get("computed_total_score"),
            "question_types": _clean_list(summary.get("question_types", [])),
        },
        "issue_count": len(issues),
        "error_count": int(payload.get("error_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "issues": issues,
    }


def _extract_exam_delivery_runtime(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    runtime = (
        getattr(context, "exam_delivery_runtime", None)
        if context is not None
        else None
    )
    if runtime is None:
        return None
    to_dict = getattr(runtime, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(runtime, dict):
        payload = dict(runtime)
    else:
        return None
    status = _clean_text(payload.get("status", ""))
    if not status or status == "not_applicable":
        return None
    versions = [
        _clean_exam_rendered_version(version)
        for version in list(payload.get("rendered_versions", []) or [])
    ]
    versions = [version for version in versions if version]
    return {
        "schema_id": _clean_text(payload.get("schema_id", "")),
        "family_id": _clean_text(payload.get("family_id", "")),
        "status": status,
        "source_key": _clean_text(payload.get("source_key", "")),
        "markdown_preview_path": _clean_text(payload.get("markdown_preview_path", "")),
        "markdown_preview_excerpt": _clean_text(
            payload.get("markdown_preview_excerpt", "")
        ),
        "version_count": int(payload.get("version_count") or len(versions)),
        "skipped_reason": _clean_text(payload.get("skipped_reason", "")),
        "rendered_versions": versions,
    }


def _clean_exam_rendered_version(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    preset_id = _clean_text(value.get("preset_id", ""))
    docx_path = _clean_text(value.get("docx_path", ""))
    if not preset_id and not docx_path:
        return {}
    return {
        "preset_id": preset_id,
        "label": _clean_text(value.get("label", "")),
        "docx_path": docx_path,
        "hidden_selectors": _clean_list(value.get("hidden_selectors", [])),
        "visible_question_count": int(value.get("visible_question_count") or 0),
        "visible_answer_count": int(value.get("visible_answer_count") or 0),
        "visible_analysis_count": int(value.get("visible_analysis_count") or 0),
        "fixed_layout_kind": _clean_text(value.get("fixed_layout_kind", "")),
        "fixed_layout_row_count": int(value.get("fixed_layout_row_count") or 0),
        "fixed_layout_column_count": int(
            value.get("fixed_layout_column_count") or 0
        ),
        "fixed_layout_row_height_twips": (
            int(value.get("fixed_layout_row_height_twips"))
            if value.get("fixed_layout_row_height_twips") is not None
            else None
        ),
        "fixed_layout_row_height_rule": _clean_text(
            value.get("fixed_layout_row_height_rule", "")
        ),
        "question_asset_count": int(value.get("question_asset_count") or 0),
        "rendered_question_asset_count": int(
            value.get("rendered_question_asset_count") or 0
        ),
        "missing_question_asset_count": int(
            value.get("missing_question_asset_count") or 0
        ),
        "question_asset_alt_text_count": int(
            value.get("question_asset_alt_text_count") or 0
        ),
        "rendered_question_asset_alt_text_count": int(
            value.get("rendered_question_asset_alt_text_count") or 0
        ),
        "missing_question_asset_alt_text_count": int(
            value.get("missing_question_asset_alt_text_count") or 0
        ),
    }


def _clean_exam_question_schema_issue(value) -> dict[str, str]:
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


def _format_exam_question_schema_markdown(evidence: dict) -> list[str]:
    lines = ["## 试卷题源结构校验", ""]
    schema_id = _clean_text(evidence.get("schema_id", ""))
    if schema_id:
        lines.append(f"- Schema: {schema_id}")
    family_id = _clean_text(evidence.get("family_id", ""))
    if family_id:
        lines.append(f"- Family: {family_id}")
    source_key = _clean_text(evidence.get("source_key", ""))
    if source_key:
        lines.append(f"- Source: {source_key}")
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        "- Manual confirmation: "
        + ("yes" if evidence.get("manual_confirmation_required") else "no")
    )
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(f"- Sections: {int(summary.get('section_count') or 0)}")
    lines.append(f"- Questions: {int(summary.get('question_count') or 0)}")
    lines.append(
        "- Answers: "
        f"{int(summary.get('answered_question_count') or 0)}/"
        f"{int(summary.get('question_count') or 0)}"
    )
    lines.append(f"- Analysis items: {int(summary.get('analysis_count') or 0)}")
    lines.append(f"- Figures: {int(summary.get('figure_count') or 0)}")
    declared = summary.get("declared_total_score")
    computed = summary.get("computed_total_score")
    if declared is not None or computed is not None:
        lines.append(
            "- Scores: "
            f"declared={_clean_text(declared) or '-'}, "
            f"computed={_clean_text(computed) or '-'}"
        )
    question_types = _clean_list(summary.get("question_types", []))
    if question_types:
        lines.append("- Question types: " + _join_or_dash(question_types))
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


def _format_exam_delivery_runtime_markdown(evidence: dict) -> list[str]:
    lines = ["## 试卷多版本运行时渲染", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    source_key = _clean_text(evidence.get("source_key", ""))
    if source_key:
        lines.append(f"- Source: {source_key}")
    preview_path = _clean_text(evidence.get("markdown_preview_path", ""))
    if preview_path:
        lines.append(f"- Markdown preview: `{preview_path}`")
    skipped = _clean_text(evidence.get("skipped_reason", ""))
    if skipped:
        lines.append(f"- Skipped reason: {skipped}")
    versions = list(evidence.get("rendered_versions", []) or [])
    lines.append(f"- Word versions: {int(evidence.get('version_count') or len(versions))}")
    if versions:
        lines.append("- Rendered versions:")
        for version in versions[:20]:
            if not isinstance(version, dict):
                continue
            selectors = _clean_list(version.get("hidden_selectors", []))
            suffix = f"; hidden={_join_or_dash(selectors)}" if selectors else ""
            fixed_layout_kind = _clean_text(version.get("fixed_layout_kind", ""))
            if fixed_layout_kind:
                height = version.get("fixed_layout_row_height_twips")
                height_suffix = f", trHeight={height}" if height is not None else ""
                suffix += (
                    f"; fixed_layout={fixed_layout_kind}, "
                    f"rows={int(version.get('fixed_layout_row_count') or 0)}, "
                    f"cols={int(version.get('fixed_layout_column_count') or 0)}"
                    f"{height_suffix}"
                )
            asset_count = int(version.get("question_asset_count") or 0)
            if asset_count:
                suffix += (
                    f"; assets={int(version.get('rendered_question_asset_count') or 0)}/"
                    f"{asset_count}"
                )
                missing_assets = int(version.get("missing_question_asset_count") or 0)
                if missing_assets:
                    suffix += f", missing_assets={missing_assets}"
                rendered_assets = int(version.get("rendered_question_asset_count") or 0)
                rendered_alt_text = 0
                if rendered_assets:
                    rendered_alt_text = int(
                        version.get("rendered_question_asset_alt_text_count") or 0
                    )
                    suffix += f", altText={rendered_alt_text}/{rendered_assets}"
                    missing_alt_text = int(
                        version.get("missing_question_asset_alt_text_count") or 0
                    )
                    if missing_alt_text:
                        suffix += f", missing_altText={missing_alt_text}"
                source_alt_text = int(version.get("question_asset_alt_text_count") or 0)
                if source_alt_text and (
                    not rendered_assets or source_alt_text != rendered_alt_text
                ):
                    suffix += f", source_altText={source_alt_text}/{asset_count}"
            lines.append(
                "  - "
                f"{_clean_text(version.get('preset_id', '-'))}: "
                f"`{_clean_text(version.get('docx_path', ''))}` "
                f"(questions={int(version.get('visible_question_count') or 0)}, "
                f"answers={int(version.get('visible_answer_count') or 0)}, "
                f"analysis={int(version.get('visible_analysis_count') or 0)}"
                f"{suffix})"
            )
    excerpt = _clean_text(evidence.get("markdown_preview_excerpt", ""))
    if excerpt:
        lines.append(f"- Preview excerpt: {excerpt}")
    lines.append("")
    return lines
