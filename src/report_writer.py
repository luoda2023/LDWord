"""
report_writer — 排版报告生成

将 PipelineResult 输出为 JSON 和 Markdown 报告。
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import is_dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from src import product_report_writer as _product_report
from src.config.atomic_io import atomic_write_text
from src.config.scene import SceneWorkspace
from src.config.scene_coverage_manifest import (
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
from src.execution_diagnostics import (
    build_execution_diagnostics,
    describe_execution_diagnostic,
)
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
    _format_exam_question_schema_markdown,
    format_exam_markdown_import_markdown,
)
from src.reporting.execution_payload import document_scope_payload
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
from src.reporting.material_assembly import (
    extract_material_assembly,
    format_material_assembly_markdown,
)
from src.reporting.material_sections import (
    _extract_coverage_boundaries,
    _extract_material_field_consistency,
    _extract_object_preflight,
    _format_coverage_boundaries_markdown,
    _format_material_field_consistency_markdown,
    _format_object_preflight_markdown,
)
from src.reporting.section_layout import (
    extract_section_layout_evidence,
    format_section_layout_evidence_markdown,
)

if TYPE_CHECKING:
    from src.pipeline.result import PipelineResult


class _SceneProductReadinessSpec(Protocol):
    subject_type: str
    subject_id: str
    static_closure_level: str
    product_readiness_level: str
    is_green: bool
    is_boundary: bool
    evidence_surfaces: tuple[str, ...]
    remaining_product_gaps: tuple[str, ...]
    rationale: str


def _audit_scene_product_readiness():
    module = import_module("src.config.scene_product_readiness")
    return module.audit_scene_product_readiness()


def _product_readiness_for(subject_id: str, *, subject_type: str):
    module = import_module("src.config.scene_product_readiness")
    return module.product_readiness_for(subject_id, subject_type=subject_type)


def _control_contract_registry():
    return import_module("src.config.control_contract_registry")


def _scene_parameter_ownership():
    return import_module("src.config.scene_parameter_ownership")


def scene_sample_fixture_manifest_paths() -> dict[str, str]:
    module = import_module("src.shared.engine.scene_sample_docx_builder")
    return module.scene_sample_fixture_manifest_paths()


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
    section_layout = extract_section_layout_evidence(result)
    coverage_boundaries = _extract_coverage_boundaries(result)
    document_scope = document_scope_payload(result)
    scene_journey_runtime = _extract_scene_journey_runtime(result)
    scene_product_readiness = None
    scene_sample_fixtures = None
    parameter_ownership = None
    control_contracts = None
    if include_internal_evidence:
        scene_product_readiness = _extract_scene_product_readiness(result)
        scene_sample_fixtures = _extract_scene_sample_fixture_manifest()
        parameter_ownership = _extract_parameter_ownership(result)
        control_contracts = _extract_control_contracts(result)
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
        "section_layout": section_layout,
        "coverage_boundaries": coverage_boundaries,
        "document_scope": document_scope,
        "scene_journey_runtime": scene_journey_runtime,
        "style_source": style_source,
        "failed_items": result.failed_items or [],
    }
    if include_internal_evidence:
        report_data["scene_product_readiness"] = scene_product_readiness
        report_data["scene_sample_fixtures"] = scene_sample_fixtures
        report_data["parameter_ownership"] = parameter_ownership
        report_data["control_contracts"] = control_contracts
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
    section_layout = extract_section_layout_evidence(result)
    coverage_boundaries = _extract_coverage_boundaries(result)
    scene_journey_runtime = _extract_scene_journey_runtime(result)
    scene_product_readiness = None
    scene_sample_fixtures = None
    parameter_ownership = None
    control_contracts = None
    if include_internal_evidence:
        scene_product_readiness = _extract_scene_product_readiness(result)
        scene_sample_fixtures = _extract_scene_sample_fixture_manifest()
        parameter_ownership = _extract_parameter_ownership(result)
        control_contracts = _extract_control_contracts(result)
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

    if section_layout:
        lines.extend(format_section_layout_evidence_markdown(section_layout))

    if coverage_boundaries:
        lines.extend(_format_coverage_boundaries_markdown(coverage_boundaries))

    if scene_journey_runtime:
        lines.extend(_format_scene_journey_runtime_markdown(scene_journey_runtime))

    if scene_product_readiness:
        lines.extend(_format_scene_product_readiness_markdown(scene_product_readiness))

    if scene_sample_fixtures:
        lines.extend(_format_scene_sample_fixture_manifest_markdown(scene_sample_fixtures))

    if parameter_ownership:
        lines.extend(_format_parameter_ownership_markdown(parameter_ownership))

    if control_contracts:
        lines.extend(_format_control_contracts_markdown(control_contracts))

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


# Product and engineering reports share these pure projections.
# Keep one implementation so their serialized evidence cannot drift.
_extract_changes = _product_report._extract_changes
_extract_journal_submission_package = _product_report._extract_journal_submission_package
_clean_journal_submission_package_item = _product_report._clean_journal_submission_package_item
_clean_journal_submission_package_issue = _product_report._clean_journal_submission_package_issue
_format_journal_submission_package_markdown = _product_report._format_journal_submission_package_markdown
_extract_scene_journey_runtime = _product_report._extract_scene_journey_runtime
_clean_scene_journey_runtime_path = _product_report._clean_scene_journey_runtime_path
_format_scene_journey_runtime_markdown = _product_report._format_scene_journey_runtime_markdown
_safe_int = _product_report._safe_int


def _extract_scene_product_readiness(
    result: PipelineResult,
) -> dict[str, object] | None:
    specs = _scene_product_readiness_specs_for_result(result)
    if not specs:
        return None

    audit = _audit_scene_product_readiness()
    level_counts = Counter(spec.product_readiness_level for spec in specs)
    static_counts = Counter(spec.static_closure_level for spec in specs)
    static_closed_not_green = [
        spec
        for spec in specs
        if spec.static_closure_level == "closed" and not spec.is_green
    ]
    config = getattr(result, "config", None)
    return {
        "status": _scene_product_readiness_status(specs),
        "registry_audit_status": "clean" if not audit else "has_gaps",
        "registry_audit_issue_count": len(audit),
        "candidate_keys": list(coverage_candidate_keys_for_config(config)),
        "subject_count": len(specs),
        "level_counts": {
            level: int(count) for level, count in sorted(level_counts.items())
        },
        "static_closure_counts": {
            level: int(count) for level, count in sorted(static_counts.items())
        },
        "green_l5_count": sum(1 for spec in specs if spec.is_green),
        "boundary_count": sum(1 for spec in specs if spec.is_boundary),
        "static_closed_but_not_green_count": len(static_closed_not_green),
        "static_closed_but_not_green_subjects": [
            f"{spec.subject_type}:{spec.subject_id}"
            for spec in static_closed_not_green
        ],
        "remaining_gap_count": sum(
            len(spec.remaining_product_gaps) for spec in specs
        ),
        "subjects": [
            _scene_product_readiness_subject_payload(spec) for spec in specs
        ],
    }


def _scene_product_readiness_specs_for_result(
    result: PipelineResult,
) -> tuple[_SceneProductReadinessSpec, ...]:
    specs: list[_SceneProductReadinessSpec] = []
    seen: set[tuple[str, str]] = set()
    config = getattr(result, "config", None)
    if config is not None:
        for pack in coverage_packs_for_config(config):
            _append_scene_product_readiness_spec(specs, seen, "pack", pack.pack_id)
        for candidate in coverage_candidate_keys_for_config(config):
            _append_scene_product_readiness_spec(specs, seen, "family", candidate)
    if not specs:
        for pack_id in _coverage_boundary_pack_ids_for_product_readiness(result):
            _append_scene_product_readiness_spec(specs, seen, "pack", pack_id)
    return tuple(specs)


def _append_scene_product_readiness_spec(
    specs: list[_SceneProductReadinessSpec],
    seen: set[tuple[str, str]],
    subject_type: str,
    subject_id: str,
) -> None:
    normalized = _clean_text(subject_id)
    if not normalized:
        return
    key = (subject_type, normalized)
    if key in seen:
        return
    try:
        spec = _product_readiness_for(normalized, subject_type=subject_type)
    except KeyError:
        return
    specs.append(spec)
    seen.add(key)


def _coverage_boundary_pack_ids_for_product_readiness(
    result: PipelineResult,
) -> tuple[str, ...]:
    context = getattr(result, "context", None)
    boundaries = getattr(context, "coverage_boundaries", None) if context is not None else None
    if not boundaries:
        return ()
    return tuple(
        _unique_clean_values(
            value.get("pack_id", "")
            for value in list(boundaries or [])
            if isinstance(value, dict)
        )
    )


def _scene_product_readiness_status(
    specs: tuple[_SceneProductReadinessSpec, ...],
) -> str:
    if all(spec.is_green for spec in specs):
        return "green_l5"
    if all(spec.is_boundary for spec in specs):
        return "boundary"
    return "not_green"


def _scene_product_readiness_subject_payload(
    spec: _SceneProductReadinessSpec,
) -> dict[str, object]:
    return {
        "subject_type": spec.subject_type,
        "subject_id": spec.subject_id,
        "static_closure_level": spec.static_closure_level,
        "product_readiness_level": spec.product_readiness_level,
        "is_green_l5": spec.is_green,
        "is_boundary": spec.is_boundary,
        "evidence_surfaces": list(spec.evidence_surfaces),
        "remaining_product_gaps": list(spec.remaining_product_gaps),
        "rationale": spec.rationale,
    }


def _format_scene_product_readiness_markdown(
    evidence: dict[str, object],
) -> list[str]:
    lines = ["## 方案产品成熟度证据", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(
        "- Registry audit: "
        f"{_clean_text(evidence.get('registry_audit_status', '')) or '-'}, "
        f"issues={int(evidence.get('registry_audit_issue_count') or 0)}"
    )
    candidate_keys = _clean_list(evidence.get("candidate_keys", []))
    if candidate_keys:
        lines.append("- Candidate keys: " + _join_or_dash(candidate_keys))

    lines.append(f"- Subjects: {int(evidence.get('subject_count') or 0)}")
    lines.append(
        "- Static closed != Green/L5: "
        f"{int(evidence.get('static_closed_but_not_green_count') or 0)}"
    )
    level_counts = evidence.get("level_counts", {})
    if isinstance(level_counts, dict) and level_counts:
        lines.append(
            "- Readiness levels: "
            + ", ".join(
                f"{key}={int(value or 0)}"
                for key, value in sorted(level_counts.items())
            )
        )
    static_counts = evidence.get("static_closure_counts", {})
    if isinstance(static_counts, dict) and static_counts:
        lines.append(
            "- Static closure levels: "
            + ", ".join(
                f"{key}={int(value or 0)}"
                for key, value in sorted(static_counts.items())
            )
        )

    subjects = list(evidence.get("subjects", []) or [])
    if subjects:
        lines.append("- Subjects:")
        for subject in subjects[:12]:
            if not isinstance(subject, dict):
                continue
            gaps = _clean_list(subject.get("remaining_product_gaps", []))
            evidence_surfaces = _clean_list(subject.get("evidence_surfaces", []))
            lines.append(
                "  - "
                f"{_clean_text(subject.get('subject_type', ''))}:"
                f"{_clean_text(subject.get('subject_id', ''))}: "
                f"readiness={_clean_text(subject.get('product_readiness_level', ''))}, "
                f"static={_clean_text(subject.get('static_closure_level', ''))}, "
                f"evidence={_join_or_dash(evidence_surfaces[:5])}, "
                f"gaps={_join_or_dash(gaps[:3])}"
            )
    lines.append("")
    return lines


def _extract_scene_sample_fixture_manifest() -> dict[str, object] | None:
    paths = scene_sample_fixture_manifest_paths()
    manifest_path_text = _clean_text(paths.get("fixture_manifest", ""))
    if not manifest_path_text:
        return None
    manifest_path = Path(manifest_path_text)
    if not manifest_path.exists() or not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {
            "status": "unreadable",
            "manifest_path": str(manifest_path),
            "error": _clean_text(str(exc)),
        }
    if not isinstance(manifest, dict):
        return {
            "status": "unreadable",
            "manifest_path": str(manifest_path),
            "error": "Manifest root is not an object.",
        }
    artifacts = [
        item for item in list(manifest.get("artifacts") or []) if isinstance(item, dict)
    ]
    request_cells = [
        item
        for item in list(manifest.get("request_cells") or [])
        if isinstance(item, dict)
    ]
    request_cell_summary = _clean_request_cell_summary(
        manifest.get("request_cell_summary")
    )
    request_cell_report_path = _clean_text(
        manifest.get("request_cell_report_path", "")
    )
    request_cell_report_anchors = [
        {
            "sample_id": _clean_text(item.get("sample_id", "")),
            "anchor": _clean_text(item.get("report_anchor", "")),
            "report_path": _clean_text(item.get("report_path", "")),
        }
        for item in request_cells
        if _clean_text(item.get("sample_id", ""))
    ]
    return {
        "status": "available",
        "manifest_path": str(manifest_path),
        "output_dir": _clean_text(manifest.get("output_dir", "")),
        "request_cell_report_path": request_cell_report_path,
        "request_cell_report_available": bool(
            request_cell_report_path and Path(request_cell_report_path).exists()
        ),
        "artifact_count": _safe_int(manifest.get("artifact_count"), len(artifacts)),
        "request_cell_count": _safe_int(
            manifest.get("request_cell_count"), len(request_cells)
        ),
        "pack_ids": _unique_clean_values(item.get("pack_id", "") for item in artifacts),
        "fixture_ids": _unique_clean_values(
            item.get("fixture_id", "") for item in artifacts
        ),
        "request_cell_sample_ids": _unique_clean_values(
            item.get("sample_id", "") for item in request_cells
        ),
        "request_cell_report_anchors": request_cell_report_anchors,
        "request_cell_fixture_ids": _unique_clean_values(
            fixture_id
            for item in request_cells
            for fixture_id in list(item.get("fixture_ids") or [])
        ),
        "request_cell_coverage_levels": _unique_clean_values(
            item.get("coverage_level", "") for item in request_cells
        ),
        "request_cell_family_proxy_sample_ids": _unique_clean_values(
            [
                *list(request_cell_summary.get("family_proxy_sample_ids", []) or []),
                *[
                    item.get("sample_id", "")
                    for item in request_cells
                    if item.get("coverage_level") == "pack_fixture_proxy"
                ],
            ]
        ),
        "request_cell_summary": request_cell_summary,
        "docx_surfaces": _unique_clean_values(
            surface
            for item in artifacts
            for surface in list(item.get("docx_surfaces") or [])
        ),
        "expected_behaviors": _unique_clean_values(
            behavior
            for item in artifacts
            for behavior in list(item.get("expected_behaviors") or [])
        ),
        "manual_gate_ids": _unique_clean_values(
            item.get("manual_gate_id", "") for item in artifacts
        ),
        "boundary_notes": _unique_clean_values(
            note
            for item in artifacts
            for note in list(item.get("boundary_notes") or [])
        ),
    }


def _format_scene_sample_fixture_manifest_markdown(
    evidence: dict[str, object],
) -> list[str]:
    lines = ["## 样本库证据", ""]
    status = _clean_text(evidence.get("status", ""))
    lines.append(f"- Status: {status or 'unknown'}")
    manifest_path = _clean_text(evidence.get("manifest_path", ""))
    if manifest_path:
        lines.append(f"- Manifest: `{manifest_path}`")
    request_cell_report_path = _clean_text(
        evidence.get("request_cell_report_path", "")
    )
    if request_cell_report_path:
        available = "yes" if evidence.get("request_cell_report_available") else "no"
        lines.append(f"- Request-cell report: `{request_cell_report_path}` ({available})")
    output_dir = _clean_text(evidence.get("output_dir", ""))
    if output_dir:
        lines.append(f"- Output dir: `{output_dir}`")
    lines.append(f"- Artifacts: {_safe_int(evidence.get('artifact_count'))}")
    request_cell_count = _safe_int(evidence.get("request_cell_count"))
    if request_cell_count:
        lines.append(f"- Request cells: {request_cell_count}")
        request_cell_summary = evidence.get("request_cell_summary", {})
        if isinstance(request_cell_summary, dict):
            lines.append(
                "- Request-cell coverage: "
                f"fixtures={_safe_int(request_cell_summary.get('fixture_cell_count'))}, "
                f"negative={_safe_int(request_cell_summary.get('negative_control_count'))}, "
                f"family_proxy={_safe_int(request_cell_summary.get('family_proxy_count'))}, "
                f"manual_boundary={_safe_int(request_cell_summary.get('manual_boundary_count'))}, "
                f"ambiguous={_safe_int(request_cell_summary.get('ambiguous_count'))}"
            )
            level_counts = list(
                request_cell_summary.get("coverage_level_counts", []) or []
            )
            if level_counts:
                lines.append(
                    "- Request-cell levels: "
                    + ", ".join(
                        f"{_clean_text(item.get('coverage_level', ''))}="
                        f"{_safe_int(item.get('count'))}"
                        for item in level_counts
                        if isinstance(item, dict)
                    )
                )
        report_anchors = [
            item
            for item in list(evidence.get("request_cell_report_anchors", []) or [])
            if isinstance(item, dict)
        ]
        if report_anchors:
            lines.append(
                "- Request-cell report anchors: "
                + ", ".join(
                    f"{_clean_text(item.get('sample_id', ''))}"
                    f"#{_clean_text(item.get('anchor', ''))}"
                    for item in report_anchors[:8]
                    if _clean_text(item.get("sample_id", ""))
                )
            )
    proxy_sample_ids = _clean_list(
        evidence.get("request_cell_family_proxy_sample_ids", [])
    )
    if proxy_sample_ids:
        lines.append("- Family proxy request cells: " + _join_or_dash(proxy_sample_ids))
    for key, label in (
        ("pack_ids", "Packs"),
        ("fixture_ids", "Fixtures"),
        ("request_cell_coverage_levels", "Request-cell levels"),
        ("docx_surfaces", "OOXML surfaces"),
        ("expected_behaviors", "Behaviors"),
        ("manual_gate_ids", "Manual gates"),
    ):
        values = _clean_list(evidence.get(key, []))
        if values:
            lines.append(f"- {label}: {_join_or_dash(values)}")
    notes = _clean_list(evidence.get("boundary_notes", []))
    if notes:
        lines.append("- Boundary notes:")
        for note in notes[:10]:
            lines.append(f"  - {note}")
    error = _clean_text(evidence.get("error", ""))
    if error:
        lines.append(f"- Error: {error}")
    lines.append("")
    return lines


def _clean_request_cell_summary(value) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    level_counts = [
        {
            "coverage_level": _clean_text(item.get("coverage_level", "")),
            "count": _safe_int(item.get("count")),
        }
        for item in list(value.get("coverage_level_counts") or [])
        if isinstance(item, dict)
    ]
    return {
        "cell_count": _safe_int(value.get("cell_count")),
        "fixture_cell_count": _safe_int(value.get("fixture_cell_count")),
        "negative_control_count": _safe_int(value.get("negative_control_count")),
        "family_proxy_count": _safe_int(value.get("family_proxy_count")),
        "manual_boundary_count": _safe_int(value.get("manual_boundary_count")),
        "ambiguous_count": _safe_int(value.get("ambiguous_count")),
        "coverage_level_counts": level_counts,
        "family_proxy_sample_ids": _clean_list(
            value.get("family_proxy_sample_ids", [])
        ),
    }


def _unique_clean_values(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        result.append(cleaned)
        seen.add(cleaned)
    return result


def _extract_control_contracts(result: PipelineResult) -> dict[str, object]:
    registry = _control_contract_registry()
    contracts = registry.list_control_contracts()
    audit = registry.audit_control_contract_registry()
    config = getattr(result, "config", None)
    context = getattr(result, "context", None)
    owner_counts_counter = Counter(contract.owner_layer for contract in contracts)
    owner_counts = {
        layer: int(owner_counts_counter.get(layer, 0))
        for layer in registry.ALLOWED_CONTROL_OWNER_LAYERS
    }
    for layer, count in sorted(owner_counts_counter.items()):
        owner_counts.setdefault(layer, int(count))

    canonical_controls = sorted(
        {
            _clean_text(contract.canonical_control)
            for contract in contracts
            if _clean_text(contract.canonical_control)
        }
    )
    paired_contracts = [
        contract
        for contract in contracts
        if contract.paired_contract_ids
    ]
    disabled_rules = [
        {
            "contract_id": contract.contract_id,
            "rule": contract.disabled_state_rule,
        }
        for contract in contracts
        if _clean_text(contract.disabled_state_rule)
    ]
    field_trace_samples = _control_contract_field_trace_samples(
        contracts,
        config,
        context,
    )
    field_trace_status_counts = Counter(
        _clean_text(sample.get("trace_status", "")) or "unknown"
        for sample in field_trace_samples
    )
    return {
        "status": "clean" if audit.is_clean else "has_gaps",
        "contract_count": len(contracts),
        "owner_counts": owner_counts,
        "canonical_control_count": len(canonical_controls),
        "canonical_controls": canonical_controls,
        "paired_contract_count": len(paired_contracts),
        "disabled_state_rule_count": len(disabled_rules),
        "disabled_state_rules": disabled_rules[:30],
        "field_trace_status_counts": {
            status: int(count)
            for status, count in sorted(field_trace_status_counts.items())
        },
        "field_trace_sample_count": len(field_trace_samples),
        "field_trace_samples": field_trace_samples,
        "audit": _control_contract_audit_payload(audit),
        "samples": _control_contract_samples(contracts),
    }


def _control_contract_audit_payload(audit) -> dict[str, object]:
    missing_paired = [
        {"contract_id": contract_id, "paired_contract_id": paired_id}
        for contract_id, paired_id in audit.missing_paired_contracts
    ]
    invalid_owner_layers = [
        {"contract_id": contract_id, "owner_layer": owner_layer}
        for contract_id, owner_layer in audit.invalid_owner_layers
    ]
    missing_files = [
        {"contract_id": contract_id, "source_path": source_path}
        for contract_id, source_path in audit.missing_evidence_files
    ]
    missing_markers = [
        {
            "contract_id": contract_id,
            "source_path": source_path,
            "marker": marker,
        }
        for contract_id, source_path, marker in audit.missing_evidence_markers
    ]
    gap_count = (
        len(audit.missing_required_contracts)
        + len(invalid_owner_layers)
        + len(missing_paired)
        + len(missing_files)
        + len(missing_markers)
    )
    return {
        "gap_count": gap_count,
        "missing_required_contracts": list(audit.missing_required_contracts),
        "invalid_owner_layers": invalid_owner_layers,
        "missing_paired_contracts": missing_paired,
        "missing_evidence_files": missing_files,
        "missing_evidence_markers": missing_markers,
    }


def _control_contract_samples(contracts) -> list[dict[str, object]]:
    priority = {
        "body.left_indent": 0,
        "body.right_indent": 1,
        "body.special_indent": 2,
        "body.line_spacing": 3,
        "body.space_before": 4,
        "body.space_after": 5,
        "fixed_layout.table_row_height": 6,
    }
    sorted_contracts = sorted(
        contracts,
        key=lambda contract: priority.get(contract.contract_id, 100),
    )
    samples: list[dict[str, object]] = []
    for contract in sorted_contracts[:30]:
        samples.append(
            {
                "contract_id": contract.contract_id,
                "label": contract.canonical_label,
                "owner_layer": contract.owner_layer,
                "canonical_control": contract.canonical_control,
                "unit_set": list(contract.unit_set),
                "paired_contract_ids": list(contract.paired_contract_ids),
                "disabled_state_rule": contract.disabled_state_rule,
                "template_surface": contract.template_surface,
                "scene_surface": contract.scene_surface,
                "workbench_surface": contract.workbench_surface,
                "parameter_paths": list(contract.parameter_paths),
                "evidence_count": len(contract.evidence),
                "evidence_locations": _control_contract_evidence_locations(
                    contract.contract_id
                ),
            }
        )
    return samples


def _control_contract_field_trace_samples(
    contracts,
    config,
    context,
) -> list[dict[str, object]]:
    events = [
        event
        for event in list(getattr(context, "parameter_runtime_consumption", []) or [])
        if isinstance(event, dict)
    ]
    samples: list[dict[str, object]] = []
    for contract in _prioritized_control_contracts(contracts)[:30]:
        parameter_traces = _control_contract_parameter_traces(contract, config)
        consumed_events = _control_contract_consumed_events(parameter_traces, events)
        has_effective_value = any(
            bool(trace.get("runtime_available"))
            for trace in parameter_traces
        )
        has_runtime_consumption = bool(consumed_events)
        if has_effective_value and has_runtime_consumption:
            trace_status = "effective_and_consumed"
        elif has_effective_value:
            trace_status = "effective_only"
        elif has_runtime_consumption:
            trace_status = "consumed_without_effective_value"
        else:
            trace_status = "declared_only"
        samples.append(
            {
                "contract_id": contract.contract_id,
                "label": contract.canonical_label,
                "canonical_control": contract.canonical_control,
                "trace_status": trace_status,
                "parameter_traces": parameter_traces,
                "runtime_consumption_events": consumed_events[:8],
            }
        )
    return samples


def _control_contract_parameter_traces(contract, config) -> list[dict[str, object]]:
    traces: list[dict[str, object]] = []
    for runtime_path, declared_paths in _control_contract_runtime_path_map(
        contract.parameter_paths
    ).items():
        found, resolved_runtime_path, value = _parameter_runtime_value(
            runtime_path,
            config,
        )
        provenance = _parameter_provenance_value(
            runtime_path,
            resolved_runtime_path,
            config,
        )
        source = _clean_text(getattr(provenance, "source", "")) if provenance else ""
        traces.append(
            {
                "runtime_path": resolved_runtime_path or runtime_path,
                "declared_paths": declared_paths,
                "runtime_available": bool(found),
                "source": source or ("runtime" if found else ""),
                "source_kind": "provenance" if provenance else ("runtime" if found else ""),
                "overridden": bool(getattr(provenance, "is_overridden", False))
                if provenance
                else False,
                "value": _parameter_value_preview(value) if found else None,
            }
        )
    return traces


def _control_contract_runtime_path_map(
    declared_paths: tuple[str, ...],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for declared_path in declared_paths:
        runtime_path = _control_contract_runtime_path(declared_path)
        if not runtime_path:
            continue
        result.setdefault(runtime_path, []).append(declared_path)
    return result


def _control_contract_runtime_path(declared_path: str) -> str:
    path = _clean_text(declared_path)
    for prefix in ("template.styles.body.",):
        if path.startswith(prefix):
            return "styles.body." + path[len(prefix):]
    return ""


def _control_contract_consumed_events(
    parameter_traces: list[dict[str, object]],
    events: list[dict[str, object]],
) -> list[dict[str, object]]:
    runtime_paths = [
        _clean_text(trace.get("runtime_path", ""))
        for trace in parameter_traces
        if _clean_text(trace.get("runtime_path", ""))
    ]
    consumed: list[dict[str, object]] = []
    for event in events:
        config_paths = _clean_list(event.get("config_paths", []))
        matched_paths = [
            runtime_path
            for runtime_path in runtime_paths
            if _runtime_event_consumes_path(config_paths, runtime_path)
        ]
        if not matched_paths:
            continue
        consumed.append(
            {
                "module_name": _clean_text(event.get("module_name", "")),
                "description": _clean_text(event.get("description", "")),
                "category": _clean_text(event.get("category", "")),
                "status": _clean_text(event.get("status", "")) or "unknown",
                "config_paths": config_paths,
                "matched_runtime_paths": matched_paths,
            }
        )
    return consumed


def _runtime_event_consumes_path(
    config_paths: list[str],
    runtime_path: str,
) -> bool:
    for config_path in config_paths:
        cleaned = _clean_text(config_path)
        if not cleaned:
            continue
        if runtime_path == cleaned:
            return True
        if runtime_path.startswith(cleaned + "."):
            return True
        if cleaned.startswith(runtime_path + "."):
            return True
    return False


def _prioritized_control_contracts(contracts) -> list:
    priority = {
        "body.left_indent": 0,
        "body.right_indent": 1,
        "body.special_indent": 2,
        "body.line_spacing": 3,
        "body.space_before": 4,
        "body.space_after": 5,
        "fixed_layout.table_row_height": 6,
    }
    return sorted(
        contracts,
        key=lambda contract: priority.get(contract.contract_id, 100),
    )


def _control_contract_evidence_locations(contract_id: str) -> list[dict[str, object]]:
    registry = _control_contract_registry()
    return [
        {
            "source_path": location.source_path,
            "marker": location.marker,
            "line_number": int(location.line_number or 0),
        }
        for location in registry.resolve_control_contract_evidence_locations(contract_id)
    ]


def _extract_parameter_ownership(result: PipelineResult) -> dict[str, object]:
    registry = _scene_parameter_ownership()
    specs = registry.scene_parameter_ownership_specs()
    config = getattr(result, "config", None)
    audit = registry.audit_scene_parameter_ownership(
        _parameter_ownership_audit_type(config)
    )
    layer_counts_counter = Counter(spec.owner_layer for spec in specs.values())
    layer_counts = {
        layer: int(layer_counts_counter.get(layer, 0))
        for layer in registry.ALLOWED_PARAMETER_OWNER_LAYERS
    }
    for layer, count in sorted(layer_counts_counter.items()):
        layer_counts.setdefault(layer, int(count))

    available_paths = [
        path
        for path in specs
        if _parameter_path_exists_on_config(path, config)
    ]
    execution_consumers = sorted(
        {
            _clean_text(spec.execution_consumer)
            for spec in specs.values()
            if _clean_text(spec.execution_consumer)
        }
    )
    audit_payload = _parameter_ownership_audit_payload(audit)
    consumer_audit = registry.audit_parameter_execution_consumers()
    consumer_anchor_payload = _parameter_consumer_anchor_audit_payload(consumer_audit)
    effective_value_samples = _parameter_effective_value_samples(specs, config)
    effective_value_gaps = _parameter_effective_value_gap_paths(specs, config)
    effective_source_counts = Counter(
        _clean_text(sample.get("source", "")) or "unknown"
        for sample in effective_value_samples
    )
    runtime_consumption = _parameter_runtime_consumption_payload(
        getattr(result, "context", None),
        specs,
        config,
    )

    return {
        "status": "clean" if audit.is_clean else "has_gaps",
        "spec_count": len(specs),
        "layer_counts": layer_counts,
        "ui_surface_count": len(
            {
                _clean_text(spec.ui_surface)
                for spec in specs.values()
                if _clean_text(spec.ui_surface)
            }
        ),
        "execution_consumer_count": len(execution_consumers),
        "execution_consumers": execution_consumers,
        "execution_consumer_anchor_status": (
            "clean" if consumer_audit.is_clean else "has_gaps"
        ),
        "execution_consumer_anchor_count": sum(
            len(anchors) for anchors in registry.parameter_consumer_anchors().values()
        ),
        "execution_consumer_anchor_audit": consumer_anchor_payload,
        "execution_consumer_anchor_samples": _parameter_consumer_anchor_samples(),
        "config_type": type(config).__name__ if config is not None else "",
        "config_identity": _parameter_ownership_config_identity(config),
        "provenance_source_counts": _parameter_ownership_provenance_counts(config),
        "runtime_available_path_count": len(available_paths),
        "runtime_available_paths": available_paths[:100],
        "effective_value_status": (
            "available" if config is not None else "no_config"
        ),
        "effective_value_sample_count": len(effective_value_samples),
        "effective_value_source_counts": {
            source: int(count)
            for source, count in sorted(effective_source_counts.items())
        },
        "effective_value_samples": effective_value_samples,
        "effective_value_gap_paths": effective_value_gaps[:50],
        "runtime_consumption_status": runtime_consumption["status"],
        "runtime_consumption_event_count": runtime_consumption["event_count"],
        "runtime_consumption_module_count": runtime_consumption["module_count"],
        "runtime_consumption_config_path_count": runtime_consumption["config_path_count"],
        "runtime_consumption_status_counts": runtime_consumption["status_counts"],
        "runtime_consumption_samples": runtime_consumption["samples"],
        "audit": audit_payload,
        "samples": _parameter_ownership_samples(specs, config),
    }


def _parameter_ownership_audit_type(config) -> type:
    if isinstance(config, SceneWorkspace):
        return type(config)
    return SceneWorkspace


def _parameter_ownership_audit_payload(audit) -> dict[str, object]:
    invalid_owner_layers = [
        {"path": path, "owner_layer": owner_layer}
        for path, owner_layer in audit.invalid_owner_layers
    ]
    gap_count = (
        len(audit.missing_top_level_paths)
        + len(audit.missing_required_paths)
        + len(audit.unknown_spec_paths)
        + len(invalid_owner_layers)
    )
    return {
        "gap_count": gap_count,
        "missing_top_level_paths": list(audit.missing_top_level_paths),
        "missing_required_paths": list(audit.missing_required_paths),
        "unknown_spec_paths": list(audit.unknown_spec_paths),
        "invalid_owner_layers": invalid_owner_layers,
    }


def _parameter_consumer_anchor_audit_payload(audit) -> dict[str, object]:
    gap_count = (
        len(audit.missing_consumers)
        + len(audit.unused_anchor_consumers)
        + len(audit.missing_anchor_files)
        + len(audit.missing_anchor_markers)
    )
    return {
        "gap_count": gap_count,
        "missing_consumers": list(audit.missing_consumers),
        "unused_anchor_consumers": list(audit.unused_anchor_consumers),
        "missing_anchor_files": [
            {"consumer": consumer, "source_path": source_path}
            for consumer, source_path in audit.missing_anchor_files
        ],
        "missing_anchor_markers": [
            {
                "consumer": consumer,
                "source_path": source_path,
                "marker": marker,
            }
            for consumer, source_path, marker in audit.missing_anchor_markers
        ],
    }


def _parameter_consumer_anchor_samples() -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for consumer, anchors in sorted(
        _scene_parameter_ownership().parameter_consumer_anchors().items()
    ):
        for anchor in anchors:
            samples.append(
                {
                    "consumer": anchor.consumer,
                    "source_path": anchor.source_path,
                    "markers": list(anchor.markers),
                }
            )
    return samples[:30]


def _parameter_ownership_config_identity(config) -> dict[str, object]:
    if config is None:
        return {}
    identity: dict[str, object] = {}
    for key in (
        "scene_id",
        "category",
        "template_id",
        "default_delivery_preset_id",
    ):
        value = _clean_text(getattr(config, key, ""))
        if value:
            identity[key] = value
    if hasattr(config, "strict_mode"):
        identity["strict_mode"] = bool(getattr(config, "strict_mode", False))
    return identity


def _parameter_ownership_provenance_counts(config) -> dict[str, int]:
    provenance = getattr(config, "_provenance", None)
    if not isinstance(provenance, dict):
        return {}
    counts = Counter(
        _clean_text(getattr(value, "source", "")) or "unknown"
        for value in provenance.values()
    )
    return {source: int(count) for source, count in sorted(counts.items())}


def _parameter_effective_value_samples(specs: dict, config) -> list[dict[str, object]]:
    if config is None:
        return []
    priority_paths = _parameter_priority_paths(specs)
    priority_order = {path: index for index, path in enumerate(priority_paths)}
    samples: list[dict[str, object]] = []
    for path in priority_paths:
        spec = specs[path]
        found, runtime_path, value = _parameter_runtime_value(path, config)
        if not found:
            continue
        provenance = _parameter_provenance_value(path, runtime_path, config)
        source = _clean_text(getattr(provenance, "source", "")) if provenance else ""
        samples.append(
            {
                "path": spec.path,
                "runtime_path": runtime_path,
                "owner_layer": spec.owner_layer,
                "source": source or spec.owner_layer,
                "source_kind": "provenance" if provenance else "owner_layer",
                "template_baseline": bool(spec.template_baseline),
                "overridden": bool(getattr(provenance, "is_overridden", False))
                if provenance
                else spec.owner_layer != "template",
                "value": _parameter_value_preview(value),
                "template_default": (
                    _parameter_value_preview(getattr(provenance, "template_default", None))
                    if provenance
                    else None
                ),
            }
        )
    samples.sort(
        key=lambda sample: (
            0
            if sample.get("source_kind") == "provenance"
            and bool(sample.get("overridden"))
            else 1
            if bool(sample.get("overridden"))
            else 2,
            priority_order.get(_clean_text(sample.get("path", "")), 9999),
        )
    )
    return samples[:40]


def _parameter_effective_value_gap_paths(specs: dict, config) -> list[str]:
    if config is None:
        return list(_parameter_priority_paths(specs))
    gaps: list[str] = []
    for path in _parameter_priority_paths(specs):
        found, _, _ = _parameter_runtime_value(path, config)
        if not found:
            gaps.append(path)
    return gaps


def _parameter_runtime_consumption_payload(context, specs: dict, config) -> dict[str, object]:
    events = list(getattr(context, "parameter_runtime_consumption", []) or [])
    if not events:
        return {
            "status": "not_recorded",
            "event_count": 0,
            "module_count": 0,
            "config_path_count": 0,
            "status_counts": {},
            "samples": [],
        }

    status_counts = Counter(
        _clean_text(event.get("status", "")) or "unknown"
        for event in events
        if isinstance(event, dict)
    )
    module_names = {
        _clean_text(event.get("module_name", ""))
        for event in events
        if isinstance(event, dict) and _clean_text(event.get("module_name", ""))
    }
    config_paths = {
        path
        for event in events
        if isinstance(event, dict)
        for path in _clean_list(event.get("config_paths", []))
    }

    samples: list[dict[str, object]] = []
    for event in events[:40]:
        if not isinstance(event, dict):
            continue
        paths = _clean_list(event.get("config_paths", []))
        source_counts = Counter()
        for path in paths:
            source_counts.update(_parameter_source_counts_for_section(path, config))
        samples.append(
            {
                "module_name": _clean_text(event.get("module_name", "")),
                "description": _clean_text(event.get("description", "")),
                "category": _clean_text(event.get("category", "")),
                "status": _clean_text(event.get("status", "")) or "unknown",
                "reason": _clean_text(event.get("reason", "")),
                "config_paths": paths,
                "runtime_available_paths": [
                    path for path in paths if _parameter_runtime_value(path, config)[0]
                ],
                "owned_spec_paths": _owned_spec_paths_for_config_sections(
                    paths,
                    specs,
                    limit=12,
                ),
                "source_counts": {
                    source: int(count)
                    for source, count in sorted(source_counts.items())
                },
            }
        )

    return {
        "status": "available",
        "event_count": len(events),
        "module_count": len(module_names),
        "config_path_count": len(config_paths),
        "status_counts": {
            status: int(count) for status, count in sorted(status_counts.items())
        },
        "samples": samples,
    }


def _owned_spec_paths_for_config_sections(
    config_paths: list[str],
    specs: dict,
    *,
    limit: int,
) -> list[str]:
    matched: list[str] = []
    for config_path in config_paths:
        for path in specs:
            if path == config_path or path.startswith(config_path + "."):
                if path not in matched:
                    matched.append(path)
                if len(matched) >= limit:
                    return matched
    return matched


def _parameter_source_counts_for_section(path: str, config) -> Counter:
    counts: Counter = Counter()
    provenance = getattr(config, "_provenance", None)
    if isinstance(provenance, dict):
        prefix = path + "."
        for key, value in provenance.items():
            if key == path or str(key).startswith(prefix):
                counts[_clean_text(getattr(value, "source", "")) or "unknown"] += 1
    if counts:
        return counts

    found, _, _ = _parameter_runtime_value(path, config)
    if found:
        counts["runtime"] = 1
    return counts


def _parameter_priority_paths(specs: dict) -> list[str]:
    priority_paths: list[str] = []
    for path in _scene_parameter_ownership().REQUIRED_SCENE_PARAMETER_PATHS:
        if path in specs and path not in priority_paths:
            priority_paths.append(path)
    for path in specs:
        if path not in priority_paths:
            priority_paths.append(path)
    return priority_paths


def _parameter_ownership_samples(specs: dict, config) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for path in _parameter_priority_paths(specs)[:30]:
        spec = specs[path]
        samples.append(
            {
                "path": spec.path,
                "owner_layer": spec.owner_layer,
                "ui_surface": spec.ui_surface,
                "execution_consumer": spec.execution_consumer,
                "template_baseline": bool(spec.template_baseline),
                "runtime_available": _parameter_path_exists_on_config(path, config),
            }
        )
    return samples


def _parameter_runtime_value(path: str, config) -> tuple[bool, str, object]:
    if config is None:
        return False, path, None
    normalized = _clean_text(path)
    if not normalized:
        return False, normalized, None

    current = config
    runtime_segments: list[str] = []
    for segment in normalized.split("."):
        if segment == "*":
            if not isinstance(current, (list, tuple)):
                return False, ".".join(runtime_segments + [segment]), None
            if not current:
                runtime_segments.append(segment)
                return True, ".".join(runtime_segments), []
            current = current[0]
            runtime_segments.append("0")
            continue
        if isinstance(current, (list, tuple)):
            if not segment.isdigit():
                return False, ".".join(runtime_segments + [segment]), None
            index = int(segment)
            if index < 0 or index >= len(current):
                return False, ".".join(runtime_segments + [segment]), None
            current = current[index]
            runtime_segments.append(segment)
            continue
        if isinstance(current, dict):
            if segment not in current:
                return False, ".".join(runtime_segments + [segment]), None
            current = current[segment]
            runtime_segments.append(segment)
            continue
        if not hasattr(current, segment):
            return False, ".".join(runtime_segments + [segment]), None
        current = getattr(current, segment)
        runtime_segments.append(segment)
    return True, ".".join(runtime_segments), current


def _parameter_provenance_value(path: str, runtime_path: str, config):
    provenance = getattr(config, "_provenance", None)
    if not isinstance(provenance, dict):
        return None
    for candidate in (runtime_path, path):
        value = provenance.get(candidate)
        if value is not None:
            return value
    return None


def _parameter_value_preview(value) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        if len(value) <= 3 and all(
            item is None or isinstance(item, (bool, int, float, str))
            for item in value
        ):
            return list(value)
        return f"{type(value).__name__}[{len(value)}]"
    if isinstance(value, dict):
        if len(value) <= 5 and all(
            isinstance(key, str)
            and (item is None or isinstance(item, (bool, int, float, str)))
            for key, item in value.items()
        ):
            return dict(value)
        return f"dict[{len(value)}]"
    if is_dataclass(value):
        identity = _parameter_dataclass_identity(value)
        if identity:
            return identity
        return type(value).__name__
    return type(value).__name__


def _parameter_dataclass_identity(value) -> str:
    for key in (
        "preset_id",
        "profile_id",
        "material_schema_id",
        "output_mode",
        "numbering_format",
    ):
        if hasattr(value, key):
            text = _clean_text(getattr(value, key, ""))
            if text:
                return f"{type(value).__name__}({key}={text})"
    return ""


def _parameter_path_exists_on_config(path: str, config) -> bool:
    if config is None:
        return False
    normalized = _clean_text(path)
    if not normalized:
        return False

    current = config
    for segment in normalized.split("."):
        if segment == "*":
            if not isinstance(current, (list, tuple)):
                return False
            if not current:
                return True
            current = current[0]
            continue
        if isinstance(current, (list, tuple)):
            if not segment.isdigit():
                return False
            index = int(segment)
            if index < 0 or index >= len(current):
                return False
            current = current[index]
            continue
        if isinstance(current, dict):
            if segment not in current:
                return False
            current = current[segment]
            continue
        if not hasattr(current, segment):
            return False
        current = getattr(current, segment)
    return True


def _format_parameter_ownership_markdown(evidence: dict[str, object]) -> list[str]:
    lines = ["## 参数归属证据", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(f"- Specs: {int(evidence.get('spec_count') or 0)}")

    layer_counts = evidence.get("layer_counts", {})
    if isinstance(layer_counts, dict):
        lines.append(
            "- Owner layers: "
            + ", ".join(
                f"{layer}={int(layer_counts.get(layer) or 0)}"
                for layer in _scene_parameter_ownership().ALLOWED_PARAMETER_OWNER_LAYERS
            )
        )

    identity = evidence.get("config_identity", {})
    if isinstance(identity, dict) and identity:
        lines.append(
            "- Config: "
            + ", ".join(f"{key}={value}" for key, value in identity.items())
        )

    source_counts = evidence.get("provenance_source_counts", {})
    if isinstance(source_counts, dict) and source_counts:
        lines.append(
            "- Source counts: "
            + ", ".join(f"{key}={value}" for key, value in source_counts.items())
        )

    lines.append(
        "- Runtime-visible specs: "
        f"{int(evidence.get('runtime_available_path_count') or 0)}/"
        f"{int(evidence.get('spec_count') or 0)}"
    )
    effective_source_counts = evidence.get("effective_value_source_counts", {})
    effective_source_text = "-"
    if isinstance(effective_source_counts, dict) and effective_source_counts:
        effective_source_text = ", ".join(
            f"{key}={int(value or 0)}"
            for key, value in effective_source_counts.items()
        )
    lines.append(
        "- Effective values: "
        f"{_clean_text(evidence.get('effective_value_status', '')) or '-'}, "
        f"samples={int(evidence.get('effective_value_sample_count') or 0)}, "
        f"sources={effective_source_text}"
    )
    runtime_status_counts = evidence.get("runtime_consumption_status_counts", {})
    runtime_status_text = "-"
    if isinstance(runtime_status_counts, dict) and runtime_status_counts:
        runtime_status_text = ", ".join(
            f"{key}={int(value or 0)}"
            for key, value in runtime_status_counts.items()
        )
    lines.append(
        "- Runtime consumption: "
        f"{_clean_text(evidence.get('runtime_consumption_status', '')) or '-'}, "
        f"events={int(evidence.get('runtime_consumption_event_count') or 0)}, "
        f"modules={int(evidence.get('runtime_consumption_module_count') or 0)}, "
        f"paths={int(evidence.get('runtime_consumption_config_path_count') or 0)}, "
        f"statuses={runtime_status_text}"
    )
    lines.append(
        "- Execution consumers: "
        + _join_or_dash(list(evidence.get("execution_consumers", []) or [])[:20])
    )
    lines.append(
        "- Consumer anchors: "
        f"{_clean_text(evidence.get('execution_consumer_anchor_status', '')) or '-'}"
        f", anchors={int(evidence.get('execution_consumer_anchor_count') or 0)}"
    )
    consumer_anchor_audit = evidence.get("execution_consumer_anchor_audit", {})
    consumer_anchor_gap_count = (
        int(consumer_anchor_audit.get("gap_count") or 0)
        if isinstance(consumer_anchor_audit, dict)
        else 0
    )
    if consumer_anchor_gap_count:
        lines.append(f"- Consumer anchor gaps: {consumer_anchor_gap_count}")
        _append_parameter_consumer_anchor_gap_lines(lines, consumer_anchor_audit)

    audit = evidence.get("audit", {})
    gap_count = int(audit.get("gap_count") or 0) if isinstance(audit, dict) else 0
    if gap_count:
        lines.append(f"- Audit gaps: {gap_count}")
        _append_parameter_ownership_gap_lines(lines, audit)
    else:
        lines.append("- Audit gaps: -")

    effective_samples = list(evidence.get("effective_value_samples", []) or [])
    if effective_samples:
        lines.append("- Effective samples:")
        for sample in effective_samples[:8]:
            if not isinstance(sample, dict):
                continue
            lines.append(
                "  - "
                f"{_clean_text(sample.get('path', ''))}: "
                f"source={_clean_text(sample.get('source', '')) or '-'}, "
                f"kind={_clean_text(sample.get('source_kind', '')) or '-'}, "
                f"value={_clean_text(sample.get('value', '')) or '-'}"
            )

    runtime_samples = list(evidence.get("runtime_consumption_samples", []) or [])
    if runtime_samples:
        lines.append("- Runtime consumption samples:")
        for sample in runtime_samples[:8]:
            if not isinstance(sample, dict):
                continue
            lines.append(
                "  - "
                f"{_clean_text(sample.get('module_name', ''))}: "
                f"{_clean_text(sample.get('status', '')) or '-'}, "
                f"config={_join_or_dash(sample.get('config_paths', []))}"
            )

    samples = list(evidence.get("samples", []) or [])
    if samples:
        lines.append("- Samples:")
        for sample in samples[:12]:
            if not isinstance(sample, dict):
                continue
            runtime_state = (
                "runtime-visible"
                if bool(sample.get("runtime_available"))
                else "registry-only"
            )
            template_note = (
                ", template baseline"
                if bool(sample.get("template_baseline"))
                else ""
            )
            lines.append(
                "  - "
                f"{_clean_text(sample.get('path', ''))}: "
                f"{_clean_text(sample.get('owner_layer', ''))}, "
                f"{_clean_text(sample.get('ui_surface', ''))} -> "
                f"{_clean_text(sample.get('execution_consumer', ''))}, "
                f"{runtime_state}{template_note}"
            )
    lines.append("")
    return lines


def _format_control_contracts_markdown(evidence: dict[str, object]) -> list[str]:
    lines = ["## 控件契约证据", ""]
    lines.append(f"- Status: {_clean_text(evidence.get('status', '')) or '-'}")
    lines.append(f"- Contracts: {int(evidence.get('contract_count') or 0)}")

    owner_counts = evidence.get("owner_counts", {})
    if isinstance(owner_counts, dict):
        lines.append(
            "- Owner layers: "
            + ", ".join(
                f"{layer}={int(owner_counts.get(layer) or 0)}"
                for layer in _control_contract_registry().ALLOWED_CONTROL_OWNER_LAYERS
            )
        )

    lines.append(
        "- Controls: "
        + _join_or_dash(list(evidence.get("canonical_controls", []) or [])[:20])
    )
    lines.append(
        "- Paired controls: "
        f"{int(evidence.get('paired_contract_count') or 0)}"
    )
    lines.append(
        "- Disabled-state rules: "
        f"{int(evidence.get('disabled_state_rule_count') or 0)}"
    )
    trace_counts = evidence.get("field_trace_status_counts", {})
    if isinstance(trace_counts, dict) and trace_counts:
        lines.append(
            "- Field trace: "
            + ", ".join(f"{key}={int(value or 0)}" for key, value in trace_counts.items())
        )
    else:
        lines.append("- Field trace: -")

    audit = evidence.get("audit", {})
    gap_count = int(audit.get("gap_count") or 0) if isinstance(audit, dict) else 0
    if gap_count:
        lines.append(f"- Audit gaps: {gap_count}")
        _append_control_contract_gap_lines(lines, audit)
    else:
        lines.append("- Audit gaps: -")

    samples = list(evidence.get("samples", []) or [])
    if samples:
        lines.append("- Samples:")
        for sample in samples[:12]:
            if not isinstance(sample, dict):
                continue
            units = _join_or_dash(sample.get("unit_set", []))
            pairs = _join_or_dash(sample.get("paired_contract_ids", []))
            rule = _clean_text(sample.get("disabled_state_rule", ""))
            rule_suffix = f", rule={rule}" if rule else ""
            lines.append(
                "  - "
                f"{_clean_text(sample.get('contract_id', ''))}: "
                f"{_clean_text(sample.get('canonical_control', ''))}, "
                f"label={_clean_text(sample.get('label', ''))}, "
                f"units={units}, pairs={pairs}{rule_suffix}"
            )
            evidence_lines = _control_contract_sample_evidence_lines(sample)
            if evidence_lines:
                lines.append("    evidence=" + " / ".join(evidence_lines[:4]))
    field_trace_samples = list(evidence.get("field_trace_samples", []) or [])
    if field_trace_samples:
        lines.append("- Field trace samples:")
        for sample in field_trace_samples[:8]:
            if not isinstance(sample, dict):
                continue
            trace_paths = _control_contract_trace_path_lines(sample)
            event_lines = _control_contract_trace_event_lines(sample)
            lines.append(
                "  - "
                f"{_clean_text(sample.get('contract_id', ''))}: "
                f"{_clean_text(sample.get('trace_status', '')) or '-'}, "
                f"control={_clean_text(sample.get('canonical_control', ''))}, "
                f"paths={_join_or_dash(trace_paths[:4])}, "
                f"events={_join_or_dash(event_lines[:4])}"
            )
    lines.append("")
    return lines


def _control_contract_trace_path_lines(sample: dict[str, object]) -> list[str]:
    lines: list[str] = []
    for trace in list(sample.get("parameter_traces", []) or []):
        if not isinstance(trace, dict):
            continue
        runtime_path = _clean_text(trace.get("runtime_path", ""))
        source = _clean_text(trace.get("source", ""))
        available = "yes" if bool(trace.get("runtime_available")) else "no"
        if runtime_path:
            lines.append(f"{runtime_path}[available={available}, source={source or '-'}]")
    return lines


def _control_contract_trace_event_lines(sample: dict[str, object]) -> list[str]:
    lines: list[str] = []
    for event in list(sample.get("runtime_consumption_events", []) or []):
        if not isinstance(event, dict):
            continue
        module_name = _clean_text(event.get("module_name", ""))
        status = _clean_text(event.get("status", "")) or "-"
        matched = _join_or_dash(event.get("matched_runtime_paths", []))
        if module_name:
            lines.append(f"{module_name}:{status}@{matched}")
    return lines


def _control_contract_sample_evidence_lines(sample: dict[str, object]) -> list[str]:
    evidence_locations = list(sample.get("evidence_locations", []) or [])
    lines: list[str] = []
    for location in evidence_locations:
        if not isinstance(location, dict):
            continue
        source_path = _clean_text(location.get("source_path", ""))
        marker = _clean_text(location.get("marker", ""))
        line_number = int(location.get("line_number") or 0)
        if not source_path:
            continue
        suffix = f":{line_number}" if line_number > 0 else ":0"
        if marker:
            lines.append(f"{source_path}{suffix}#{marker}")
        else:
            lines.append(f"{source_path}{suffix}")
    return lines


def _append_control_contract_gap_lines(lines: list[str], audit: dict) -> None:
    required = _clean_list(audit.get("missing_required_contracts", []))
    if required:
        lines.append("  - missing required: " + ", ".join(required[:20]))

    for label, key in (
        ("invalid owner layers", "invalid_owner_layers"),
        ("missing pairs", "missing_paired_contracts"),
        ("missing files", "missing_evidence_files"),
        ("missing markers", "missing_evidence_markers"),
    ):
        rows = list(audit.get(key, []) or [])
        if not rows:
            continue
        formatted: list[str] = []
        for item in rows[:20]:
            if not isinstance(item, dict):
                continue
            contract_id = _clean_text(item.get("contract_id", ""))
            if key == "invalid_owner_layers":
                formatted.append(
                    f"{contract_id}={_clean_text(item.get('owner_layer', ''))}"
                )
            elif key == "missing_paired_contracts":
                formatted.append(
                    f"{contract_id}->{_clean_text(item.get('paired_contract_id', ''))}"
                )
            elif key == "missing_evidence_files":
                formatted.append(
                    f"{contract_id}@{_clean_text(item.get('source_path', ''))}"
                )
            else:
                formatted.append(
                    f"{contract_id}@{_clean_text(item.get('source_path', ''))}:"
                    f"{_clean_text(item.get('marker', ''))}"
                )
        if formatted:
            lines.append(f"  - {label}: " + ", ".join(formatted))


def _append_parameter_ownership_gap_lines(lines: list[str], audit: dict) -> None:
    for label, key in (
        ("missing top-level", "missing_top_level_paths"),
        ("missing required", "missing_required_paths"),
        ("unknown spec paths", "unknown_spec_paths"),
    ):
        values = _clean_list(audit.get(key, []))
        if values:
            lines.append(f"  - {label}: " + ", ".join(values[:20]))

    invalid = list(audit.get("invalid_owner_layers", []) or [])
    if invalid:
        formatted = []
        for item in invalid[:20]:
            if not isinstance(item, dict):
                continue
            formatted.append(
                f"{_clean_text(item.get('path', ''))}"
                f"={_clean_text(item.get('owner_layer', ''))}"
            )
        if formatted:
            lines.append("  - invalid owner layers: " + ", ".join(formatted))


def _append_parameter_consumer_anchor_gap_lines(lines: list[str], audit: dict) -> None:
    for label, key in (
        ("missing consumers", "missing_consumers"),
        ("unused anchor consumers", "unused_anchor_consumers"),
    ):
        values = _clean_list(audit.get(key, []))
        if values:
            lines.append(f"  - {label}: " + ", ".join(values[:20]))

    missing_files = list(audit.get("missing_anchor_files", []) or [])
    if missing_files:
        formatted = [
            f"{_clean_text(item.get('consumer', ''))}@{_clean_text(item.get('source_path', ''))}"
            for item in missing_files[:20]
            if isinstance(item, dict)
        ]
        if formatted:
            lines.append("  - missing files: " + ", ".join(formatted))

    missing_markers = list(audit.get("missing_anchor_markers", []) or [])
    if missing_markers:
        formatted = [
            f"{_clean_text(item.get('consumer', ''))}@"
            f"{_clean_text(item.get('source_path', ''))}:"
            f"{_clean_text(item.get('marker', ''))}"
            for item in missing_markers[:20]
            if isinstance(item, dict)
        ]
        if formatted:
            lines.append("  - missing markers: " + ", ".join(formatted))
