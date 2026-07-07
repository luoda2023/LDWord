"""Pipeline execution entry point."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Callable

from docx import Document

from src.config.delivery_preset_display import delivery_preset_display_name
from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids
from src.config.plugin_manual_gate import plugin_manual_gate_payload
from src.config.resolved import ResolvedConfig
from src.config.scene import FormatScopeConfig, SceneApplicationBoundaryConfig
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_config,
)
from src.config.scene_family_registry import get_planned_scene_family
from src.modules.base import BaseModule
from src.pipeline.context import PipelineContext
from src.pipeline.result import PipelineResult
from src.shared.engine.field_refresh import (
    document_has_toc,
    refresh_doc_fields_with_word,
)
from src.shared.engine.content_visibility import (
    preview_content_visibility_effects,
    scan_content_visibility_markers,
)
from src.shared.engine.material_field_consistency import (
    inspect_material_field_consistency,
)
from src.shared.engine.exam_question_schema import inspect_exam_question_schema
from src.shared.engine.exam_question_schema import build_exam_delivery_runtime
from src.shared.engine.journal_citation_schema import inspect_journal_citations
from src.shared.engine.journal_rule_source_governance import (
    inspect_journal_rule_source_governance,
)
from src.shared.engine.journal_submission_package import inspect_journal_submission_package
from src.shared.engine.official_numbering_preservation import (
    inspect_official_numbering_preservation,
)
from src.shared.engine.technical_chapter_inventory import (
    inspect_technical_chapter_inventory,
)
from src.shared.engine.application_section_word_limits import (
    inspect_application_section_word_limits,
)
from src.pipeline.scheduler import (
    topological_sort,
    validate_data_flow,
    validate_schema_contract,
)
from src.pipeline.tracker import ChangeTracker
from src.shared.engine.object_preflight import (
    inspect_docx_package,
    object_preflight_module_skips,
    object_preflight_targets_for_touchpoints,
)
from src.shared.engine.scene_journey_runtime import (
    build_scene_journey_runtime_evidence,
)


@dataclass(slots=True)
class OutputTargetIssue:
    kind: str = ""
    severity: str = "warning"
    message: str = ""


@dataclass(slots=True)
class OutputTargetPreflightItem:
    preset_id: str = ""
    label: str = ""
    path: str = ""
    artifact: str = "final_docx"
    exists: bool = False
    parent_path: str = ""
    parent_exists: bool = False
    parent_writable: bool = True
    path_length: int = 0
    issues: list[OutputTargetIssue] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


@dataclass(slots=True)
class OutputTargetPreflightResult:
    items: list[OutputTargetPreflightItem] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return any(item.has_issues for item in self.items)

    @property
    def issue_count(self) -> int:
        return sum(len(item.issues) for item in self.items)


def build_coverage_boundary_report_items(config) -> list[dict[str, object]]:
    """Build report-ready coverage/plugin boundary evidence for a config."""

    return [
        _coverage_boundary_payload(pack)
        for pack in coverage_packs_for_config(config)
        if _coverage_boundary_should_report(pack)
    ]


def _coverage_boundary_should_report(pack: SceneCoveragePack) -> bool:
    if pack.plugin_boundary:
        return True
    return pack.pack_id == "contract_delivery"


def _coverage_boundary_payload(pack: SceneCoveragePack) -> dict[str, object]:
    return {
        "pack_id": pack.pack_id,
        "label": pack.label,
        "boundary": pack.boundary,
        "primary_landings": list(pack.primary_landings),
        "secondary_landings": list(pack.secondary_landings),
        "capability_axis_ids": list(pack.capability_axis_ids),
        "implemented_closures": list(pack.implemented_closures),
        "missing_closures": list(pack.missing_closures),
        "closure_tasks": [
            {
                "summary": task.summary,
                "priority": task.priority,
                "owner": task.owner,
                "target_phase": task.target_phase,
                "validation_commands": list(task.validation_commands),
            }
            for task in pack.closure_tasks
        ],
        "plugin_manual_gate": plugin_manual_gate_payload(pack.pack_id),
    }


class Pipeline:
    """Execute registered modules against a document."""

    def __init__(
        self,
        modules: list[BaseModule],
        config: ResolvedConfig,
        *,
        output_dir: str | None = None,
        output_suffix: str = "_new",
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        force_delivery_presets: bool = False,
    ) -> None:
        self._config = config
        self._output_dir = Path(output_dir) if output_dir else None
        self._output_suffix = output_suffix
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._force_delivery_presets = bool(force_delivery_presets)
        self._tracker = ChangeTracker()

        self._modules = topological_sort(modules)

        schema_errors = validate_schema_contract(self._modules)
        if schema_errors:
            raise ValueError(
                "Pipeline schema contract validation failed:\n"
                + "\n".join(f"  - {error}" for error in schema_errors)
            )

        data_flow_errors = validate_data_flow(self._modules)
        if data_flow_errors:
            raise ValueError(
                "Pipeline data-flow validation failed:\n"
                + "\n".join(f"  - {error}" for error in data_flow_errors)
            )

    def execute(self, doc_path: str) -> PipelineResult:
        """Run the full pipeline for one .docx file."""
        if self._is_cancelled():
            return self._cancelled_result()

        path = Path(doc_path)
        if not path.exists():
            return PipelineResult(
                success=False,
                error=f"File not found: {path}",
                config=self._config,
            )

        total_steps = len(self._modules) + 3
        step = 0

        self._emit(step, total_steps, "Loading document")
        if self._is_cancelled():
            return self._cancelled_result()

        try:
            doc = Document(str(path))
        except Exception as exc:
            return PipelineResult(
                success=False,
                error=f"Failed to open document: {exc}",
                config=self._config,
            )

        original_doc = copy.deepcopy(doc)
        step += 1

        ctx = PipelineContext(
            source_doc_path=str(path),
            source_doc_dir=str(path.parent),
            application_boundary=copy.deepcopy(
                getattr(self._config, "application_boundary", None)
                or SceneApplicationBoundaryConfig()
            ),
            format_scope=copy.deepcopy(
                getattr(self._config, "format_scope", None) or FormatScopeConfig()
            ),
        )
        ctx.coverage_boundaries = build_coverage_boundary_report_items(self._config)
        self._run_scene_journey_runtime(ctx)
        self._run_exam_question_schema_validation(ctx)
        self._run_journal_rule_source_governance(ctx)
        self._run_journal_citation_validation(doc, ctx)
        self._emit(step, total_steps, "Object preflight")
        preflight_blocked, preflight_skips = self._run_object_preflight(path, ctx)
        if preflight_blocked:
            return self._failed_result(
                error="Object preflight blocked execution due to fragile embedded content.",
                doc=doc,
                original_doc=original_doc,
                ctx=ctx,
            )
        self._run_content_visibility_preflight(doc, ctx)
        self._run_output_target_preflight(path, ctx)

        for mod in self._modules:
            if self._is_cancelled():
                return self._cancelled_result()

            skip_entry = preflight_skips.get(mod.meta.name)
            if skip_entry:
                skip_reason = str(skip_entry.get("reason", "") or "")
                self._record_parameter_runtime_consumption(
                    ctx,
                    mod,
                    status="skipped",
                    reason=skip_reason,
                )
                self._tracker.record(
                    rule_name=mod.meta.name,
                    target="object_preflight",
                    section="global",
                    change_type="skip",
                    before="",
                    after=skip_reason,
                    paragraph_index=-1,
                    success=True,
                )
                step += 1
                continue

            self._emit(step, total_steps, f"Running module: {mod.meta.description}")

            try:
                issues = mod.validate(doc, self._config, ctx) or []
                fatal_issues = self._record_validation_issues(mod, issues)
                if fatal_issues:
                    error = (
                        f"Module '{mod.meta.name}' validation failed: "
                        f"{fatal_issues[0].message}"
                    )
                    self._record_parameter_runtime_consumption(
                        ctx,
                        mod,
                        status="validation_failed",
                        reason=fatal_issues[0].message,
                    )
                    if self._is_strict_mode():
                        return self._failed_result(
                            error=error,
                            doc=doc,
                            original_doc=original_doc,
                            ctx=ctx,
                        )
                    step += 1
                    continue

                mod.apply(doc, self._config, self._tracker, ctx)
                self._record_parameter_runtime_consumption(
                    ctx,
                    mod,
                    status="executed",
                )
            except Exception as exc:
                self._record_parameter_runtime_consumption(
                    ctx,
                    mod,
                    status="failed",
                    reason=str(exc),
                )
                self._tracker.record(
                    rule_name=mod.meta.name,
                    target="pipeline",
                    section="global",
                    change_type="error",
                    paragraph_index=-1,
                    success=False,
                    failure_reason=str(exc),
                )
                if self._is_strict_mode():
                    return self._failed_result(
                        error=f"Module '{mod.meta.name}' execution failed: {exc}",
                        doc=doc,
                        original_doc=original_doc,
                        ctx=ctx,
                    )

            step += 1

        if self._is_cancelled():
            return self._cancelled_result()

        self._run_official_numbering_preservation_validation(doc, original_doc, ctx)
        self._run_technical_chapter_inventory_validation(doc, ctx)
        self._run_application_section_word_limits_validation(doc, ctx)
        self._run_material_field_consistency(doc, ctx)

        self._emit(step, total_steps, "Writing report")
        self._emit(step, total_steps, "Saving output")
        output_paths = self._save_outputs(doc, path)
        output_paths = _exam_delivery_runtime_output_paths(ctx) or output_paths
        self._run_journal_submission_package_validation(output_paths, ctx)
        step += 1

        self._emit(step, total_steps, "Completed")
        return self._build_result(
            doc=doc,
            original_doc=original_doc,
            output_paths=output_paths,
            ctx=ctx,
        )

    def _emit(self, current: int, total: int, message: str) -> None:
        if self._progress_callback:
            self._progress_callback(current, total, message)

    def _is_cancelled(self) -> bool:
        if self._cancel_check is None:
            return False
        try:
            return bool(self._cancel_check())
        except Exception:
            return False

    def _is_strict_mode(self) -> bool:
        return bool(getattr(self._config, "strict_mode", False))

    def _cancelled_result(self) -> PipelineResult:
        return PipelineResult(
            success=False,
            tracker=self._tracker,
            failed_items=self._collect_failures(),
            error="Cancelled by user.",
            cancelled=True,
            config=self._config,
        )

    def _failed_result(
        self,
        *,
        error: str,
        doc: Document | None = None,
        original_doc: Document | None = None,
        ctx: PipelineContext | None = None,
    ) -> PipelineResult:
        return PipelineResult(
            success=False,
            status="failed",
            doc=doc,
            original_doc=original_doc,
            tracker=self._tracker,
            context=ctx,
            failed_items=self._collect_failures(),
            error=error,
            config=self._config,
        )

    def _collect_failures(self) -> list[dict]:
        return [
            {
                "rule_name": record.rule_name,
                "target": record.target,
                "section": record.section,
                "change_type": record.change_type,
                "paragraph_index": record.paragraph_index,
                "reason": record.failure_reason or "",
            }
            for record in self._tracker.get_failures()
        ]

    def _record_validation_issues(self, mod: BaseModule, issues: list) -> list:
        fatal_issues = []

        for issue in issues:
            is_error = getattr(issue, "level", "") == "error"
            if is_error:
                fatal_issues.append(issue)

            self._tracker.record(
                rule_name=mod.meta.name,
                target=getattr(issue, "location", "") or "validate",
                section="global",
                change_type=f"validate_{getattr(issue, 'level', 'info')}",
                after=getattr(issue, "message", ""),
                paragraph_index=-1,
                success=not is_error,
                failure_reason=getattr(issue, "message", "") if is_error else None,
            )

        return fatal_issues

    def _record_parameter_runtime_consumption(
        self,
        ctx: PipelineContext | None,
        mod: BaseModule,
        *,
        status: str,
        reason: str = "",
    ) -> None:
        if ctx is None:
            return
        if ctx.parameter_runtime_consumption is None:
            ctx.parameter_runtime_consumption = []
        ctx.parameter_runtime_consumption.append(
            {
                "module_name": mod.meta.name,
                "description": mod.meta.description,
                "category": mod.meta.category,
                "status": status,
                "reason": str(reason or ""),
                "config_paths": [
                    str(path or "").strip()
                    for path in getattr(mod.meta, "requires_config", ()) or ()
                    if str(path or "").strip()
                ],
            }
        )

    def _run_scene_journey_runtime(self, ctx: PipelineContext) -> None:
        result = build_scene_journey_runtime_evidence(self._config)
        if not result.is_applicable:
            return
        ctx.scene_journey_runtime = result
        self._tracker.record(
            rule_name="scene_journey_runtime",
            target=";".join(result.pack_ids) or "scene_matrix",
            section="scene",
            change_type="scene_journey_runtime",
            before="",
            after=(
                f"status={result.status}; paths={result.path_count}; "
                f"journeys={','.join(result.journey_type_ids) or '-'}; "
                f"reports={len(result.report_expectations)}; "
                f"artifacts={len(result.artifact_channel_ids)}; "
                f"repair={len(result.repair_target_types)}"
            ),
            paragraph_index=-1,
            success=True,
        )

    def _run_object_preflight(
        self,
        path: Path,
        ctx: PipelineContext,
    ) -> tuple[bool, dict[str, dict[str, object]]]:
        compliance = getattr(self._config, "compliance_profile", None)
        policy = getattr(compliance, "object_preflight", None)
        if policy is None or not bool(getattr(policy, "enabled", True)):
            return False, {}

        ctx.object_preflight_policy = self._build_object_preflight_policy_snapshot(policy)
        result = inspect_docx_package(path, policy)
        ctx.object_preflight = result
        for finding in result.findings:
            is_error = finding.severity == "error"
            self._tracker.record(
                rule_name="object_preflight",
                target=finding.kind,
                section=finding.location,
                change_type=f"preflight_{finding.severity}",
                before="",
                after=finding.message,
                paragraph_index=-1,
                success=not is_error,
                failure_reason=finding.message if is_error else None,
            )

        preflight_skips = object_preflight_module_skips(result.findings, policy)
        ctx.object_preflight_module_skips = list(preflight_skips.values())
        failure_policy = str(getattr(compliance, "failure_policy", "") or "").strip()
        blocked = bool(result.blocking_findings) and (
            self._is_strict_mode() or failure_policy == "block"
        )
        return blocked, preflight_skips

    def _build_object_preflight_policy_snapshot(self, policy) -> dict[str, object]:
        input_profile = getattr(self._config, "input_source_profile", None)
        schema_ids = resolve_material_schema_ids(
            str(getattr(input_profile, "material_schema_id", "") or "").strip(),
            list(getattr(input_profile, "material_schema_ids", []) or []),
        )
        schema_id = schema_ids[0] if schema_ids else ""
        family_id = ""
        ooxml_touchpoints: tuple[str, ...] = ()
        recommended_targets: tuple[str, ...] = ()
        for candidate_schema_id in schema_ids:
            try:
                family_id = get_material_schema(candidate_schema_id).family
                family = get_planned_scene_family(family_id)
                ooxml_touchpoints = family.ooxml_touchpoints
                recommended_targets = object_preflight_targets_for_touchpoints(ooxml_touchpoints)
                break
            except KeyError:
                family_id = ""
                ooxml_touchpoints = ()
                recommended_targets = ()
        return {
            "enabled": bool(getattr(policy, "enabled", True)),
            "preservation_mode": str(getattr(policy, "preservation_mode", "") or ""),
            "scan_targets": _string_list(getattr(policy, "scan_targets", []) or []),
            "block_on": _string_list(getattr(policy, "block_on", []) or []),
            "skip_high_risk_modules": bool(
                getattr(policy, "skip_high_risk_modules", True)
            ),
            "skip_modules_by_finding": {
                str(kind): _string_list(modules)
                for kind, modules in dict(
                    getattr(policy, "skip_modules_by_finding", {}) or {}
                ).items()
            },
            "material_schema_id": schema_id,
            "material_schema_ids": list(schema_ids),
            "planning_family_id": family_id,
            "planning_ooxml_touchpoints": list(ooxml_touchpoints),
            "recommended_scan_targets": list(recommended_targets),
        }

    def _run_content_visibility_preflight(self, doc: Document, ctx: PipelineContext) -> None:
        scan = scan_content_visibility_markers(
            doc,
            getattr(self._config, "delivery_presets", []) or [],
        )
        ctx.content_visibility_scan = scan
        ctx.content_visibility_preview = preview_content_visibility_effects(
            doc,
            getattr(self._config, "delivery_presets", []) or [],
        )
        if not scan.selectors and not scan.used_rule_selectors:
            return
        before = (
            "document selectors: "
            + (", ".join(scan.selectors) if scan.selectors else "-")
        )
        after = (
            "preset selectors: "
            + (", ".join(scan.used_rule_selectors) if scan.used_rule_selectors else "-")
        )
        issue_messages = scan.issue_messages()
        if issue_messages:
            after += "; " + "; ".join(issue_messages)
        else:
            after += "; selectors matched"
        preview_text = _content_visibility_preview_summary(
            list(ctx.content_visibility_preview or [])
        )
        if preview_text:
            after += "; preview: " + preview_text
        self._tracker.record(
            rule_name="delivery_visibility_preflight",
            target="delivery_presets",
            section="delivery",
            change_type=(
                "visibility_preflight_warning"
                if issue_messages
                else "visibility_preflight"
            ),
            before=before,
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_exam_question_schema_validation(self, ctx: PipelineContext) -> None:
        result = inspect_exam_question_schema(self._config)
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.exam_question_schema = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"sections={int(getattr(summary, 'section_count', 0) or 0)}; "
            f"questions={int(getattr(summary, 'question_count', 0) or 0)}; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="exam_question_schema",
            target=getattr(result, "schema_id", "") or "exam_items_v1",
            section="input",
            change_type=(
                "schema_validation_warning"
                if getattr(result, "has_issues", False)
                else "schema_validation"
            ),
            before=getattr(result, "source_key", "") or "structured source",
            after=after,
            paragraph_index=-1,
            success=True,
        )
        runtime_output_dir = self._output_dir or Path(ctx.source_doc_dir or ".")
        runtime = build_exam_delivery_runtime(
            self._config,
            output_dir=runtime_output_dir,
            source_stem=Path(ctx.source_doc_path or "exam").stem,
            validation=result,
        )
        if str(getattr(runtime, "status", "") or "") == "not_applicable":
            return
        ctx.exam_delivery_runtime = runtime
        self._tracker.record(
            rule_name="exam_delivery_runtime",
            target=getattr(runtime, "schema_id", "") or "exam_items_v1",
            section="input_to_delivery",
            change_type=(
                "exam_delivery_runtime_blocked"
                if getattr(runtime, "status", "") == "blocked"
                else "exam_delivery_runtime"
            ),
            before=getattr(runtime, "source_key", "") or "structured source",
            after=(
                f"status={getattr(runtime, 'status', '') or '-'}; "
                f"preview={getattr(runtime, 'markdown_preview_path', '') or '-'}; "
                f"versions={int(getattr(runtime, 'version_count', 0) or 0)}"
            ),
            paragraph_index=-1,
            success=True,
        )

    def _run_journal_citation_validation(self, doc: Document, ctx: PipelineContext) -> None:
        result = inspect_journal_citations(self._config, doc)
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.journal_citations = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"references={int(getattr(summary, 'reference_count', 0) or 0)}; "
            f"citations={int(getattr(summary, 'citation_count', 0) or 0)}; "
            f"matched={int(getattr(summary, 'matched_citation_count', 0) or 0)}; "
            f"missing={int(getattr(summary, 'missing_reference_count', 0) or 0)}; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="journal_citations",
            target=getattr(result, "schema_id", "") or "journal_submission_materials_v1",
            section="input",
            change_type=(
                "citation_source_warning"
                if getattr(result, "has_issues", False)
                else "citation_source_validation"
            ),
            before=getattr(result, "source_key", "") or "BibTeX/CSL source",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_journal_rule_source_governance(self, ctx: PipelineContext) -> None:
        result = inspect_journal_rule_source_governance(self._config)
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.journal_rule_source_governance = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"source={getattr(result, 'rule_source_id', '') or '-'}; "
            f"review={getattr(result, 'review_status', '') or '-'}; "
            f"count_profile={getattr(result, 'count_profile_id', '') or '-'}; "
            "matched_profiles="
            f"{int(getattr(summary, 'matched_count_profile_count', 0) or 0)}; "
            "manual="
            + ("yes" if getattr(result, "manual_confirmation_required", False) else "no")
            + "; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="journal_rule_source_governance",
            target=getattr(result, "rule_source_id", "") or "journal_rule_source",
            section="rules",
            change_type=(
                "journal_rule_source_warning"
                if getattr(result, "has_issues", False)
                else "journal_rule_source_governance"
            ),
            before=getattr(result, "target_journal_name", "") or "reviewed registry",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_journal_submission_package_validation(
        self,
        output_paths: dict[str, str],
        ctx: PipelineContext,
    ) -> None:
        result = inspect_journal_submission_package(
            self._config,
            output_paths=output_paths,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.journal_submission_package = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"required={int(getattr(summary, 'satisfied_required_count', 0) or 0)}/"
            f"{int(getattr(summary, 'required_component_count', 0) or 0)}; "
            f"outputs={int(getattr(summary, 'output_count', 0) or 0)}; "
            f"reports={int(getattr(summary, 'report_enabled_count', 0) or 0)}; "
            f"errors={int(getattr(result, 'error_count', 0) or 0)}; "
            f"warnings={int(getattr(result, 'warning_count', 0) or 0)}"
        )
        self._tracker.record(
            rule_name="journal_submission_package",
            target="delivery_presets",
            section="delivery",
            change_type=(
                "submission_package_warning"
                if getattr(result, "has_issues", False)
                else "submission_package"
            ),
            before=getattr(result, "default_delivery_preset_id", "") or "delivery presets",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_official_numbering_preservation_validation(
        self,
        doc: Document,
        original_doc: Document,
        ctx: PipelineContext,
    ) -> None:
        result = inspect_official_numbering_preservation(
            self._config,
            original_doc=original_doc,
            current_doc=doc,
            heading_map=ctx.heading_map,
            tracker_records=self._tracker.get_all(),
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.official_numbering_preservation = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"strategy={getattr(result, 'strategy', '') or '-'}; "
            f"headings={int(getattr(summary, 'heading_count', 0) or 0)}; "
            f"changed_headings={int(getattr(summary, 'changed_heading_count', 0) or 0)}; "
            f"numbering_records={int(getattr(summary, 'heading_numbering_record_count', 0) or 0)}"
        )
        if not getattr(result, "has_issues", False):
            return
        self._tracker.record(
            rule_name="official_numbering_preservation",
            target="numbering.xml",
            section="official_policy",
            change_type="preflight_warning",
            before="official numbering preserve evidence",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_technical_chapter_inventory_validation(
        self,
        doc: Document,
        ctx: PipelineContext,
    ) -> None:
        result = inspect_technical_chapter_inventory(
            self._config,
            doc,
            doc_tree=ctx.doc_tree,
            heading_map=ctx.heading_map,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.technical_chapter_inventory = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"chapters={int(getattr(summary, 'chapter_count', 0) or 0)}; "
            f"headings={int(getattr(summary, 'heading_count', 0) or 0)}; "
            f"appendix={int(getattr(summary, 'appendix_count', 0) or 0)}; "
            f"tables={int(getattr(summary, 'table_count', 0) or 0)}; "
            f"figures={int(getattr(summary, 'figure_count', 0) or 0)}"
        )
        if not getattr(result, "has_issues", False):
            return
        self._tracker.record(
            rule_name="technical_chapter_inventory",
            target="chapter_inventory",
            section="technical_long_docs",
            change_type="preflight_warning",
            before="technical chapter inventory",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_application_section_word_limits_validation(
        self,
        doc: Document,
        ctx: PipelineContext,
    ) -> None:
        result = inspect_application_section_word_limits(
            self._config,
            doc,
            doc_tree=ctx.doc_tree,
            heading_map=ctx.heading_map,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.application_section_word_limits = result
        summary = getattr(result, "summary", None)
        after = (
            f"status={getattr(result, 'status', '') or '-'}; "
            f"matched_sections={int(getattr(summary, 'matched_section_count', 0) or 0)}; "
            f"exceeded={int(getattr(summary, 'exceeded_section_count', 0) or 0)}; "
            f"required_missing={int(getattr(summary, 'required_missing_count', 0) or 0)}"
        )
        if not getattr(result, "has_issues", False):
            return
        self._tracker.record(
            rule_name="application_section_word_limits",
            target="section_limits",
            section="application_reports",
            change_type="preflight_warning",
            before="application section word limit evidence",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _run_output_target_preflight(self, src_path: Path, ctx: PipelineContext) -> None:
        result = _build_output_target_preflight(
            src_path=src_path,
            config=self._config,
            output_dir=self._output_dir,
            output_suffix=self._output_suffix,
            force_delivery_presets=self._force_delivery_presets,
        )
        ctx.output_target_preflight = result
        if not result.has_issues:
            return
        before = "; ".join(
            f"{_output_target_display_label(item)}: {item.path}"
            for item in result.items
        )
        issue_text = "; ".join(
            issue.message
            for item in result.items
            for issue in item.issues
            if issue.message
        )
        self._tracker.record(
            rule_name="output_target_preflight",
            target="output",
            section="delivery",
            change_type="output_target_warning",
            before=before,
            after=issue_text,
            paragraph_index=-1,
            success=True,
        )

    def _run_material_field_consistency(self, doc: Document, ctx: PipelineContext) -> None:
        input_profile = getattr(self._config, "input_source_profile", None)
        schema_id = str(getattr(input_profile, "material_schema_id", "") or "").strip()
        entity_data = getattr(self._config, "entity_data", {}) or {}
        result = inspect_material_field_consistency(
            doc,
            schema_id=schema_id,
            entity_data=entity_data,
        )
        if str(getattr(result, "status", "") or "") == "not_applicable":
            return
        ctx.material_field_consistency = result

    def _build_result(
        self,
        *,
        doc: Document,
        original_doc: Document,
        output_paths: dict[str, str],
        ctx: PipelineContext | None = None,
    ) -> PipelineResult:
        failed_items = self._collect_failures()

        if not failed_items:
            return PipelineResult(
                success=True,
                status="success",
                doc=doc,
                original_doc=original_doc,
                tracker=self._tracker,
                context=ctx,
                output_paths=output_paths,
                config=self._config,
            )

        return PipelineResult(
            success=True,
            status="partial_success",
            doc=doc,
            original_doc=original_doc,
            tracker=self._tracker,
            context=ctx,
            output_paths=output_paths,
            failed_items=failed_items,
            error=f"{len(failed_items)} module operation(s) failed.",
            config=self._config,
        )

    def _save_outputs(self, doc: Document, src_path: Path) -> dict[str, str]:
        stem = src_path.stem
        suffix = src_path.suffix or ".docx"
        out_dir = self._output_dir or src_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        presets = list(getattr(self._config, "delivery_presets", []) or [])
        if len(presets) > 1 or (self._force_delivery_presets and presets):
            return self._save_delivery_outputs(doc, src_path, presets, suffix)

        output_cfg = getattr(self._config, "output", None)
        final_enabled = bool(getattr(output_cfg, "final_docx", True))
        output_paths: dict[str, str] = {}

        if final_enabled:
            final_path = out_dir / f"{stem}{self._output_suffix}{suffix}"
            doc.save(str(final_path))
            self._best_effort_refresh_fields(doc, final_path)
            output_paths["final"] = str(final_path)

        return output_paths

    def _save_delivery_outputs(
        self,
        doc: Document,
        src_path: Path,
        presets: list,
        suffix: str,
    ) -> dict[str, str]:
        output_paths: dict[str, str] = {}
        for preset in presets:
            preset_id = str(getattr(preset, "preset_id", "") or "").strip()
            if not preset_id:
                continue
            artifacts = getattr(preset, "artifacts", None)
            if not bool(getattr(artifacts, "final_docx", False)):
                continue

            out_dir = self._delivery_output_dir(preset, src_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = self._delivery_filename(preset, src_path)
            final_path = out_dir / _ensure_suffix(filename, suffix)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            preset_doc = _clone_document(doc)
            visibility_summary = _apply_content_visibility_rules(preset_doc, preset)
            self._record_content_visibility_summary(preset, visibility_summary)
            preset_doc.save(str(final_path))
            self._best_effort_refresh_fields(preset_doc, final_path)
            output_paths[preset_id] = str(final_path)
        return output_paths

    def _record_content_visibility_summary(self, preset, summary: dict[str, object]) -> None:
        removed_count = int(summary.get("removed_paragraphs") or 0)
        stripped_count = int(summary.get("stripped_marker_paragraphs") or 0)
        if not removed_count and not stripped_count:
            return
        preset_id = str(getattr(preset, "preset_id", "") or "final").strip() or "final"
        removed_keys = ", ".join(str(value) for value in summary.get("removed_selectors", []) or [])
        after = f"Removed {removed_count} paragraph(s)"
        if removed_keys:
            after += f" for {removed_keys}"
        if stripped_count:
            after += f"; stripped {stripped_count} marker paragraph(s)"
        self._tracker.record(
            rule_name="delivery_visibility",
            target=f"preset:{preset_id}",
            section="delivery",
            change_type="content_visibility",
            before="",
            after=after,
            paragraph_index=-1,
            success=True,
        )

    def _delivery_output_dir(self, preset, src_path: Path) -> Path:
        return _delivery_output_dir_for_preset(
            preset,
            src_path=src_path,
            base_output_dir=self._output_dir or src_path.parent,
        )

    def _delivery_filename(self, preset, src_path: Path) -> str:
        return _delivery_filename_for_preset(
            preset,
            src_path=src_path,
            base_output_dir=self._output_dir or src_path.parent,
        )

    def _best_effort_refresh_fields(self, doc: Document, final_path: Path) -> None:
        if not document_has_toc(doc):
            return
        try:
            refresh_doc_fields_with_word(str(final_path), timeout_sec=30)
        except Exception:
            return


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_delivery_template(
    template: str,
    *,
    src_path: Path,
    preset,
    base_output_dir: Path,
) -> str:
    values = _SafeFormatDict(
        {
            "document_dir": str(src_path.parent),
            "output_dir": str(base_output_dir),
            "stem": src_path.stem,
            "suffix": src_path.suffix or ".docx",
            "preset_id": str(getattr(preset, "preset_id", "") or ""),
            "preset_label": delivery_preset_display_name(preset),
        }
    )
    return str(template or "").format_map(values)


def _content_visibility_preview_summary(previews: list[object]) -> str:
    parts: list[str] = []
    for preview in previews:
        removed = int(getattr(preview, "removed_paragraph_count", 0) or 0)
        stripped = int(getattr(preview, "stripped_marker_paragraph_count", 0) or 0)
        if not removed and not stripped:
            continue
        preset_id = str(getattr(preview, "preset_id", "") or "preset").strip()
        text = f"{preset_id}: remove {removed}"
        blocks = int(getattr(preview, "removed_block_count", 0) or 0)
        if removed and blocks:
            text += f" in {blocks} block(s)"
        sample = _content_visibility_preview_sample(preview)
        if removed and sample:
            text += f" sample={sample}"
        if stripped:
            text += f", strip {stripped}"
        parts.append(text)
    return "; ".join(parts)


def _content_visibility_preview_sample(preview: object, *, max_length: int = 40) -> str:
    for block in list(getattr(preview, "removed_blocks", []) or []):
        for sample in list(getattr(block, "text_samples", []) or []):
            cleaned = str(sample or "").strip()
            if cleaned:
                return _trim_content_visibility_preview(cleaned, max_length=max_length)
    for sample in list(getattr(preview, "removed_text_samples", []) or []):
        cleaned = str(sample or "").strip()
        if cleaned:
            return _trim_content_visibility_preview(cleaned, max_length=max_length)
    return ""


def _trim_content_visibility_preview(text: str, *, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def _build_output_target_preflight(
    *,
    src_path: Path,
    config,
    output_dir: Path | None,
    output_suffix: str,
    force_delivery_presets: bool,
) -> OutputTargetPreflightResult:
    base_output_dir = output_dir or src_path.parent
    targets = _planned_output_targets(
        src_path=src_path,
        config=config,
        base_output_dir=base_output_dir,
        output_suffix=output_suffix,
        force_delivery_presets=force_delivery_presets,
    )
    path_counts: dict[str, int] = {}
    for item in targets:
        key = _output_target_key(item.path)
        path_counts[key] = path_counts.get(key, 0) + 1
    for item in targets:
        _append_output_target_file_issues(item, path_counts)
    return OutputTargetPreflightResult(items=targets)


def _planned_output_targets(
    *,
    src_path: Path,
    config,
    base_output_dir: Path,
    output_suffix: str,
    force_delivery_presets: bool,
) -> list[OutputTargetPreflightItem]:
    suffix = src_path.suffix or ".docx"
    presets = list(getattr(config, "delivery_presets", []) or [])
    if len(presets) > 1 or (force_delivery_presets and presets):
        items: list[OutputTargetPreflightItem] = []
        for preset in presets:
            preset_id = str(getattr(preset, "preset_id", "") or "").strip()
            if not preset_id:
                continue
            artifacts = getattr(preset, "artifacts", None)
            if not bool(getattr(artifacts, "final_docx", False)):
                continue
            out_dir = _delivery_output_dir_for_preset(
                preset,
                src_path=src_path,
                base_output_dir=base_output_dir,
            )
            filename = _delivery_filename_for_preset(
                preset,
                src_path=src_path,
                base_output_dir=base_output_dir,
            )
            items.append(
                _output_target_item(
                    preset_id=preset_id,
                    label=delivery_preset_display_name(preset),
                    path=out_dir / _ensure_suffix(filename, suffix),
                )
            )
        return items

    output_cfg = getattr(config, "output", None)
    if not bool(getattr(output_cfg, "final_docx", True)):
        return []
    return [
        _output_target_item(
            preset_id="final",
            label="Final DOCX",
            path=base_output_dir / f"{src_path.stem}{output_suffix}{suffix}",
        )
    ]


def _delivery_output_dir_for_preset(
    preset,
    *,
    src_path: Path,
    base_output_dir: Path,
) -> Path:
    template = str(getattr(preset, "output_dir_template", "") or "").strip()
    if not template or template == "{document_dir}/output":
        return base_output_dir

    rendered = _render_delivery_template(
        template,
        src_path=src_path,
        preset=preset,
        base_output_dir=base_output_dir,
    )
    path = Path(rendered)
    return path if path.is_absolute() else base_output_dir / path


def _delivery_filename_for_preset(
    preset,
    *,
    src_path: Path,
    base_output_dir: Path,
) -> str:
    template = str(getattr(preset, "filename_template", "") or "").strip()
    if not template:
        template = "{stem}_{preset_id}"
    rendered = _render_delivery_template(
        template,
        src_path=src_path,
        preset=preset,
        base_output_dir=base_output_dir,
    )
    return rendered or f"{src_path.stem}_{getattr(preset, 'preset_id', 'final')}"


def _output_target_item(
    *,
    preset_id: str,
    label: str,
    path: Path,
) -> OutputTargetPreflightItem:
    parent = path.parent
    nearest_parent = _nearest_existing_parent(parent)
    parent_writable = True
    if nearest_parent is not None:
        parent_writable = os.access(str(nearest_parent), os.W_OK)
    return OutputTargetPreflightItem(
        preset_id=preset_id,
        label=label,
        path=str(path),
        exists=path.exists(),
        parent_path=str(parent),
        parent_exists=parent.exists(),
        parent_writable=parent_writable,
        path_length=len(str(path)),
    )


def _append_output_target_file_issues(
    item: OutputTargetPreflightItem,
    path_counts: dict[str, int],
) -> None:
    path = Path(item.path)
    display_label = _output_target_display_label(item)
    if path_counts.get(_output_target_key(item.path), 0) > 1:
        item.issues.append(
            OutputTargetIssue(
                kind="duplicate_target",
                severity="warning",
                message=f"{display_label} 与其它交付指向同一输出文件: {item.path}",
            )
        )
    if item.exists:
        kind = "target_is_directory" if path.is_dir() else "target_exists"
        severity = "error" if path.is_dir() else "warning"
        message = (
            f"{display_label} 输出目标是目录: {item.path}"
            if path.is_dir()
            else f"{display_label} 输出文件已存在，将被覆盖: {item.path}"
        )
        item.issues.append(OutputTargetIssue(kind=kind, severity=severity, message=message))
    if not item.parent_writable:
        item.issues.append(
            OutputTargetIssue(
                kind="parent_not_writable",
                severity="error",
                message=f"{display_label} 输出目录不可写: {item.parent_path}",
            )
        )
    if item.path_length >= 260:
        item.issues.append(
            OutputTargetIssue(
                kind="path_too_long",
                severity="warning",
                message=f"{display_label} 输出路径长度 {item.path_length}，可能超过 Windows 限制",
            )
        )
    elif item.path_length >= 240:
        item.issues.append(
            OutputTargetIssue(
                kind="path_near_limit",
                severity="warning",
                message=f"{display_label} 输出路径长度 {item.path_length}，接近 Windows 限制",
            )
        )


def _output_target_display_label(item: OutputTargetPreflightItem) -> str:
    raw_label = str(item.label or "").strip()
    if raw_label:
        return raw_label
    return delivery_preset_display_name(
        str(item.preset_id or item.artifact or "output").strip()
    )


def _nearest_existing_parent(path: Path) -> Path | None:
    current = path
    while True:
        if current.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _output_target_key(path: str) -> str:
    return str(Path(path)).casefold()


def _string_list(values) -> list[str]:
    return [
        str(value).strip()
        for value in list(values or [])
        if str(value or "").strip()
    ]


def _ensure_suffix(filename: str, suffix: str) -> Path:
    path = Path(str(filename or "").strip() or "output")
    return path if path.suffix else path.with_suffix(suffix)


def _exam_delivery_runtime_output_paths(ctx: PipelineContext | None) -> dict[str, str]:
    if ctx is None:
        return {}
    runtime = getattr(ctx, "exam_delivery_runtime", None)
    if runtime is None:
        return {}
    output_paths: dict[str, str] = {}
    for version in list(getattr(runtime, "rendered_versions", ()) or ()):
        preset_id = str(getattr(version, "preset_id", "") or "").strip()
        docx_path = str(getattr(version, "docx_path", "") or "").strip()
        if preset_id and docx_path:
            output_paths[preset_id] = docx_path
    return output_paths


def _clone_document(doc: Document) -> Document:
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return Document(buffer)


_VISIBILITY_MARKER_RE = re.compile(
    r"\{\{\s*([#/])\s*(?:visibility|content)\s*:\s*([A-Za-z0-9_.-]+)\s*\}\}"
)


def _apply_content_visibility_rules(doc: Document, preset) -> dict[str, object]:
    remove_selectors = _content_visibility_remove_selectors(preset)
    removed = 0
    stripped = 0
    active_remove_selector = ""

    for paragraph in list(_iter_document_paragraphs(doc)):
        text = paragraph.text or ""
        markers = _visibility_markers(text)

        if active_remove_selector:
            removed += 1
            if _has_visibility_end(markers, active_remove_selector):
                active_remove_selector = ""
            _remove_paragraph(paragraph)
            continue

        start_remove_selector = next(
            (
                selector
                for marker_type, selector in markers
                if marker_type == "#" and selector in remove_selectors
            ),
            "",
        )
        if start_remove_selector:
            removed += 1
            if not _has_visibility_end(markers, start_remove_selector):
                active_remove_selector = start_remove_selector
            _remove_paragraph(paragraph)
            continue

        if markers and _strip_visibility_markers(paragraph):
            stripped += 1

    return {
        "removed_paragraphs": removed,
        "stripped_marker_paragraphs": stripped,
        "removed_selectors": sorted(remove_selectors),
    }


def _content_visibility_remove_selectors(preset) -> set[str]:
    selectors: set[str] = set()
    for rule in list(getattr(preset, "content_visibility_rules", []) or []):
        selector_type = str(
            _visibility_rule_value(rule, "selector_type", "marker_block")
        ).strip().lower()
        action = str(_visibility_rule_value(rule, "action", "remove")).strip().lower()
        selector = _normalize_visibility_selector(_visibility_rule_value(rule, "selector", ""))
        if selector_type != "marker_block" or action not in {"remove", "hide", "exclude"}:
            continue
        if selector:
            selectors.add(selector)
    return selectors


def _visibility_rule_value(rule, key: str, default=""):
    if isinstance(rule, dict):
        return rule.get(key, default)
    return getattr(rule, key, default)


def _visibility_markers(text: str) -> list[tuple[str, str]]:
    return [
        (match.group(1), _normalize_visibility_selector(match.group(2)))
        for match in _VISIBILITY_MARKER_RE.finditer(text or "")
    ]


def _has_visibility_end(markers: list[tuple[str, str]], selector: str) -> bool:
    return any(
        marker_type == "/" and marker_selector == selector
        for marker_type, marker_selector in markers
    )


def _normalize_visibility_selector(value) -> str:
    return str(value or "").strip().lower()


def _strip_visibility_markers(paragraph) -> bool:
    text = paragraph.text or ""
    if not _VISIBILITY_MARKER_RE.search(text):
        return False

    stripped_text = _VISIBILITY_MARKER_RE.sub("", text)
    if not stripped_text.strip():
        _remove_paragraph(paragraph)
        return True

    for run in paragraph.runs:
        if _VISIBILITY_MARKER_RE.search(run.text or ""):
            run.text = _VISIBILITY_MARKER_RE.sub("", run.text or "")
    if _VISIBILITY_MARKER_RE.search(paragraph.text or ""):
        paragraph.text = stripped_text
    return True


def _iter_document_paragraphs(container):
    for paragraph in list(getattr(container, "paragraphs", []) or []):
        yield paragraph
    for table in list(getattr(container, "tables", []) or []):
        for row in list(getattr(table, "rows", []) or []):
            for cell in list(getattr(row, "cells", []) or []):
                yield from _iter_document_paragraphs(cell)


def _remove_paragraph(paragraph) -> None:
    element = paragraph._element
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
