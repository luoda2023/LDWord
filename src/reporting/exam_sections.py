"""Exam-family report sections extracted from the main report writer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.reporting.common import _clean_issue, _clean_list, _clean_text, _join_or_dash

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


def _extract_exam_markdown_import(result: PipelineResult) -> dict | None:
    context = getattr(result, "context", None)
    import_result = (
        getattr(context, "exam_markdown_import", None)
        if context is not None
        else None
    )
    if import_result is None:
        return None
    to_dict = getattr(import_result, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(import_result, dict):
        payload = dict(import_result)
    else:
        return None
    return payload if isinstance(payload, dict) and payload else None


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
            _clean_issue(issue)
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
    master_evidence = _clean_exam_master_evidence(payload.get("master_evidence", {}))
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
        "master_evidence": master_evidence,
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


def format_exam_markdown_import_markdown(evidence: dict) -> list[str]:
    """Render the source-import receipt separately from later schema/runtime."""

    lines = ["## Markdown 题稿导入证据", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    source_path = _clean_text(evidence.get("source_path", ""))
    if source_path:
        lines.append(f"- Source: `{source_path}`")
    summary = evidence.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.extend(
        [
            f"- Sections: {int(summary.get('section_count') or 0)}",
            f"- Questions: {int(summary.get('question_count') or 0)}",
            (
                "- Answers / analysis: "
                f"{int(summary.get('answered_question_count') or 0)} / "
                f"{int(summary.get('analysis_count') or 0)}"
            ),
            (
                "- Issues: "
                f"{int(evidence.get('issue_count') or 0)} "
                f"(errors={int(evidence.get('error_count') or 0)}, "
                f"warnings={int(evidence.get('warning_count') or 0)})"
            ),
        ]
    )
    issues = [
        item
        for item in list(evidence.get("issues", []) or [])
        if isinstance(item, dict)
    ]
    if issues:
        lines.append("- Import issues:")
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


def _clean_exam_master_evidence(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    master_id = _clean_text(value.get("master_id", ""))
    docx_path = _clean_text(value.get("master_docx_path", ""))
    status = _clean_text(value.get("placeholder_contract_status", ""))
    if not master_id and not docx_path and not status:
        return {}
    return {
        "mode_id": _clean_text(value.get("mode_id", "")),
        "master_id": master_id,
        "master_label": _clean_text(value.get("master_label", "")),
        "master_source_type": _clean_text(value.get("master_source_type", "")),
        "master_docx_path": docx_path,
        "master_version": _clean_text(value.get("master_version", "")),
        "manifest_path": _clean_text(value.get("manifest_path", "")),
        "placeholder_contract_status": status,
        "required_placeholders": _clean_list(value.get("required_placeholders", [])),
        "optional_placeholders": _clean_list(value.get("optional_placeholders", [])),
        "runtime_fields": _clean_list(value.get("runtime_fields", [])),
        "generated_fields": _clean_list(value.get("generated_fields", [])),
        "missing_required_placeholders": _clean_list(
            value.get("missing_required_placeholders", [])
        ),
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
    master_evidence = evidence.get("master_evidence", {})
    if isinstance(master_evidence, dict) and master_evidence:
        mode_id = _clean_text(master_evidence.get("mode_id", ""))
        if mode_id:
            lines.append(f"- Work mode: {mode_id}")
        master_id = _clean_text(master_evidence.get("master_id", ""))
        master_label = _clean_text(master_evidence.get("master_label", ""))
        source_type = _clean_text(master_evidence.get("master_source_type", ""))
        contract_status = _clean_text(
            master_evidence.get("placeholder_contract_status", "")
        )
        master_bits = [bit for bit in (master_label, master_id) if bit]
        if master_bits:
            suffix_bits = []
            if source_type:
                suffix_bits.append(f"source={source_type}")
            if contract_status:
                suffix_bits.append(f"contract={contract_status}")
            suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
            lines.append(f"- Master: {' / '.join(master_bits)}{suffix}")
        master_path = _clean_text(master_evidence.get("master_docx_path", ""))
        if master_path:
            lines.append(f"- Master DOCX: `{master_path}`")
        manifest_path = _clean_text(master_evidence.get("manifest_path", ""))
        if manifest_path:
            lines.append(f"- Master manifest: `{manifest_path}`")
        missing = _clean_list(master_evidence.get("missing_required_placeholders", []))
        if missing:
            lines.append("- Missing placeholders: " + _join_or_dash(missing))
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
