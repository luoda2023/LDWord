"""Cross-template delivery-group orchestration for production execution.

The workbench runner supplies one pipeline-execution callable.  This module
owns delivery grouping, frozen target-template resolution, group aggregation,
and the terminal delivery payload; it never imports the runner itself.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.services.execution_session import (
    assert_execution_resource_matches,
    execution_session_resource_ref,
)
from src.config.library import get_template_entry, load_template_from_library
from src.config.material_context import MaterialExecutionContext
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.config.work_mode import resolve_work_mode_id
from src.execution_diagnostics import (
    build_execution_diagnostics,
    summarize_execution_diagnostics,
)
from src.pipeline.context import PipelineContext
from src.pipeline.result import PipelineResult
from src.pipeline.runner import pipeline_terminal_assembly_owner, plan_pipeline_output_paths
from src.reporting.execution_payload import (
    application_section_word_limits_payload,
    content_visibility_preview_payload,
    content_visibility_receipts_payload,
    content_visibility_scan_payload,
    diagnostics_payload,
    journal_submission_package_payload,
    material_field_consistency_payload,
    object_preflight_payload,
    official_document_assembly_payload,
    official_numbering_preservation_payload,
    technical_chapter_inventory_payload,
)
from src.services.artifact_failure import apply_artifact_failures, capture_artifact_write

from .delivery_group_preflight import (
    PreparedDeliveryTargetGroup,
    build_delivery_group_output_preflight,
)
from .delivery_reporting import (
    ResultArtifactOutcome,
    finalize_result_artifacts,
    plan_delivery_artifact_paths,
    primary_output_path,
    primary_output_path_for_default,
)
from .exam_question_assets import material_context_with_exam_question_assets
from .material_artifacts import (
    material_package_path_map,
    material_package_receipt_payload,
    write_material_manifest,
    write_material_package_artifacts,
)


@dataclass(slots=True)
class _DeliveryAggregate:
    material_diagnostics: list[dict]
    output_paths: dict[str, str] = field(default_factory=dict)
    compare_paths: dict[str, str] = field(default_factory=dict)
    report_paths: list[str] = field(default_factory=list)
    intermediate_paths: dict[str, str] = field(default_factory=dict)
    artifact_failures: list[dict[str, str]] = field(default_factory=list)
    failed_count: int = 0
    diagnostics_count: int = 0
    diagnostics_items: list[dict] = field(default_factory=list)
    diagnostics_summary_parts: list[str] = field(default_factory=list)
    content_visibility_scans: dict[str, dict[str, object]] = field(
        default_factory=dict
    )
    content_visibility_preview: list[dict[str, object]] = field(default_factory=list)
    content_visibility_receipts: dict[str, object] = field(default_factory=dict)
    object_preflight: dict[str, object] = field(default_factory=dict)
    material_field_consistency: dict[str, object] = field(default_factory=dict)
    journal_submission_package: dict[str, object] = field(default_factory=dict)
    official_document_assembly: dict[str, object] = field(default_factory=dict)
    official_numbering_preservation: dict[str, object] = field(default_factory=dict)
    technical_chapter_inventory: dict[str, object] = field(default_factory=dict)
    application_section_word_limits: dict[str, object] = field(default_factory=dict)
    statuses: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def start(cls, material_diagnostics: list[dict] | None) -> _DeliveryAggregate:
        items = list(material_diagnostics or [])
        state = cls(
            material_diagnostics=items,
            diagnostics_count=len(items),
            diagnostics_items=[
                dict(item) for item in items if isinstance(item, dict)
            ],
        )
        summary = summarize_execution_diagnostics(items)
        if summary:
            state.diagnostics_summary_parts.append(summary)
        return state

    def record_configuration_failure(
        self,
        prepared_group: PreparedDeliveryTargetGroup,
    ) -> None:
        self.statuses.append("failed")
        self.failed_count += 1
        label = prepared_group.target_template_id or "current"
        reason = prepared_group.error or "configuration failed"
        self.errors.append(f"{label}: {reason}")

    def record_result(self, result, *, target_template_id: str) -> dict[str, str]:
        status = str(getattr(result, "status", "failed") or "failed")
        raw_output_paths = getattr(result, "output_paths", None)
        if not isinstance(raw_output_paths, dict):
            raw_output_paths = {}
        group_output_paths = {
            str(key): str(value) for key, value in raw_output_paths.items()
        }
        self.output_paths.update(group_output_paths)

        visibility_key = target_template_id or "current"
        visibility_scan = content_visibility_scan_payload(result)
        if visibility_scan:
            self.content_visibility_scans[visibility_key] = visibility_scan
        self.content_visibility_preview.extend(
            content_visibility_preview_payload(result)
        )
        self.content_visibility_receipts.update(
            content_visibility_receipts_payload(result)
        )
        self._record_first_result_payloads(result)
        self.statuses.append(status)
        self.failed_count += len(list(getattr(result, "failed_items", []) or []))

        diagnostics = build_execution_diagnostics(result)
        self.diagnostics_count += int(diagnostics["count"])
        self.diagnostics_items.extend(
            dict(item)
            for item in list(diagnostics.get("items") or [])
            if isinstance(item, dict)
        )
        summary = str(diagnostics["summary"] or "").strip()
        if summary:
            self.diagnostics_summary_parts.append(summary)
        return group_output_paths

    def _record_first_result_payloads(self, result) -> None:
        payloads = (
            ("object_preflight", object_preflight_payload(result)),
            (
                "material_field_consistency",
                material_field_consistency_payload(result),
            ),
            ("journal_submission_package", journal_submission_package_payload(result)),
            ("official_document_assembly", official_document_assembly_payload(result)),
            (
                "official_numbering_preservation",
                official_numbering_preservation_payload(result),
            ),
            ("technical_chapter_inventory", technical_chapter_inventory_payload(result)),
            (
                "application_section_word_limits",
                application_section_word_limits_payload(result),
            ),
        )
        for attribute, payload in payloads:
            if not getattr(self, attribute):
                setattr(self, attribute, payload)

    def record_artifacts(self, outcome: ResultArtifactOutcome) -> None:
        self.artifact_failures.extend(outcome.artifact_failures)
        self.compare_paths.update(outcome.compare_paths)
        self.report_paths.extend(outcome.report_paths)
        self.intermediate_paths.update(outcome.intermediate_paths)


def delivery_target_groups(
    scene: SceneWorkspace,
    *,
    execution_session=None,
) -> list[tuple[str, list]]:
    presets = list(getattr(scene, "delivery_presets", []) or [])
    if not presets:
        return []

    base_template_id = _scene_current_template_id(
        scene,
        execution_session=execution_session,
    )
    explicit_target_ids: list[str] = []
    groups: list[tuple[str, list]] = []
    group_by_template: dict[str, list] = {}

    for preset in presets:
        target_template_id = str(
            getattr(preset, "target_template_id", "") or ""
        ).strip()
        if target_template_id:
            explicit_target_ids.append(target_template_id)
        group_key = target_template_id or base_template_id
        if group_key not in group_by_template:
            group_by_template[group_key] = []
            groups.append((group_key, group_by_template[group_key]))
        group_by_template[group_key].append(copy.deepcopy(preset))

    if not explicit_target_ids:
        return []
    if len(groups) == 1 and groups[0][0] == base_template_id:
        return []
    return groups


def load_delivery_template(
    current_template: TemplateConfig,
    *,
    scene: SceneWorkspace,
    target_template_id: str,
    execution_session=None,
) -> TemplateConfig:
    normalized_id = str(target_template_id or "").strip()
    effective_mode_id = mode_id_for_scene(
        scene,
        execution_session=execution_session,
    )
    if not normalized_id or normalized_id == _scene_current_template_id(
        scene,
        execution_session=execution_session,
    ):
        if execution_session is not None:
            expected = getattr(execution_session, "template_ref", None)
            if expected is None:
                raise RuntimeError(
                    f"execution_resource_unproven:template:{normalized_id}"
                )
            assert_execution_resource_matches(
                expected,
                value=current_template,
                path=expected.path,
                verify_source=False,
            )
        return current_template

    selected = load_template_from_library(normalized_id, mode_id=effective_mode_id)
    if execution_session is not None:
        expected = execution_session_resource_ref(
            execution_session,
            kind="delivery_target_template",
            resource_id=normalized_id,
        )
        if expected is None:
            raise RuntimeError(
                "execution_resource_unproven:delivery_target_template:"
                f"{normalized_id}"
            )
        entry = get_template_entry(normalized_id, mode_id=effective_mode_id)
        assert_execution_resource_matches(
            expected,
            value=selected,
            path=str(getattr(entry, "path", "") or ""),
        )
    return selected


def mode_id_for_scene(
    scene: SceneWorkspace | None,
    *,
    execution_session=None,
) -> str:
    """Resolve the frozen execution mode used by delivery and batch surfaces."""

    return resolve_work_mode_id(
        scene,
        requested_mode_id=getattr(execution_session, "mode_id", ""),
    )


def run_delivery_target_groups(
    *,
    input_path: Path,
    output_dir: Path,
    template: TemplateConfig,
    scene: SceneWorkspace,
    target_groups: list[tuple[str, list]],
    progress_cb,
    cancel_check,
    execute_config: Callable,
    output_suffix: str,
    session_overrides: dict[str, object],
    execution_session,
    default_material_context: MaterialExecutionContext,
    official_master,
    exam_master=None,
    official_document_type_id: str = "",
    material_diagnostics: list[dict] | None = None,
    material_context: MaterialExecutionContext | None = None,
    style_source_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    state = _DeliveryAggregate.start(material_diagnostics)
    runtime_material = material_context_with_exam_question_assets(
        scene,
        material_context
        if isinstance(material_context, MaterialExecutionContext)
        else default_material_context,
    )
    prepared_groups = _prepare_delivery_target_groups(
        template=template,
        scene=scene,
        target_groups=target_groups,
        input_path=input_path,
        output_dir=output_dir,
        output_suffix=output_suffix,
        session_overrides=session_overrides,
        runtime_material=runtime_material,
        execution_session=execution_session,
    )
    group_output_preflight = build_delivery_group_output_preflight(prepared_groups)
    if bool(group_output_preflight.get("has_errors")):
        return _delivery_preflight_failure_payload(
            group_output_preflight,
            material_diagnostics=state.material_diagnostics,
            style_source_summary=style_source_summary,
        )

    _run_prepared_delivery_groups(
        prepared_groups,
        state=state,
        input_path=input_path,
        output_dir=output_dir,
        progress_cb=progress_cb,
        cancel_check=cancel_check,
        execute_config=execute_config,
        official_master=official_master,
        exam_master=exam_master,
        official_document_type_id=official_document_type_id,
        runtime_material=runtime_material,
        style_source_summary=style_source_summary,
    )
    status = aggregate_delivery_status(state.statuses)
    material_paths = _publish_group_material_artifacts(
        state,
        status=status,
        input_path=input_path,
        output_dir=output_dir,
        template=template,
        scene=scene,
        runtime_material=runtime_material,
        session_overrides=session_overrides,
    )
    payload = _delivery_payload(
        state,
        status=status,
        default_delivery_preset_id=scene.default_delivery_preset_id,
        output_target_preflight=group_output_preflight,
        style_source_summary=style_source_summary,
        material_manifest_paths=material_paths[0],
        material_package_paths=material_paths[1],
        material_package_receipt=material_paths[2],
    )
    apply_artifact_failures(payload, state.artifact_failures)
    return payload


def _run_prepared_delivery_groups(
    prepared_groups: list[PreparedDeliveryTargetGroup],
    *,
    state: _DeliveryAggregate,
    input_path: Path,
    output_dir: Path,
    progress_cb,
    cancel_check,
    execute_config: Callable,
    official_master,
    exam_master,
    official_document_type_id: str,
    runtime_material: MaterialExecutionContext,
    style_source_summary: dict[str, object] | None,
) -> None:
    for prepared_group in prepared_groups:
        if prepared_group.error or prepared_group.config is None:
            state.record_configuration_failure(prepared_group)
            continue

        config = prepared_group.config
        if cancel_check():
            state.statuses.append("cancelled")
            cancelled_result = _cancelled_group_result(input_path, config)
            state.record_artifacts(
                finalize_result_artifacts(
                    cancelled_result,
                    input_path=input_path,
                    output_dir=output_dir,
                    output_paths={},
                    fallback_output_path="",
                    config=config,
                    elapsed=0.0,
                    modules_enabled=0,
                    modules_total=0,
                    material_diagnostics=state.material_diagnostics,
                    material_context=runtime_material,
                    style_source_summary=style_source_summary,
                    include_material_artifacts=False,
                )
            )
            break

        result, elapsed, modules_enabled, modules_total = execute_config(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
            force_delivery_presets=True,
            official_master=official_master,
            exam_master=exam_master,
            official_document_type_id=official_document_type_id,
        )
        group_output_paths = state.record_result(
            result,
            target_template_id=prepared_group.target_template_id,
        )
        state.record_artifacts(
            finalize_result_artifacts(
                result,
                input_path=input_path,
                output_dir=output_dir,
                output_paths=group_output_paths,
                fallback_output_path=primary_output_path(config, group_output_paths),
                config=config,
                elapsed=elapsed,
                modules_enabled=modules_enabled,
                modules_total=modules_total,
                material_diagnostics=state.material_diagnostics,
                material_context=runtime_material,
                style_source_summary=style_source_summary,
                include_material_artifacts=False,
            )
        )

        status = str(getattr(result, "status", "failed") or "failed")
        if status == "cancelled":
            cancellation_text = str(getattr(result, "error", "") or "").strip()
            if cancellation_text:
                state.errors.append(cancellation_text)
            break
        if not getattr(result, "success", False):
            error_text = str(getattr(result, "error", "") or "")
            if error_text:
                state.errors.append(error_text)


def _prepare_delivery_target_groups(
    *,
    template: TemplateConfig,
    scene: SceneWorkspace,
    target_groups: list[tuple[str, list]],
    input_path: Path,
    output_dir: Path,
    output_suffix: str,
    session_overrides: dict[str, object],
    runtime_material: MaterialExecutionContext,
    execution_session=None,
) -> list[PreparedDeliveryTargetGroup]:
    """Resolve and plan every group before the first group may execute."""

    prepared: list[PreparedDeliveryTargetGroup] = []
    for target_template_id, presets in target_groups:
        try:
            target_template = load_delivery_template(
                template,
                scene=scene,
                target_template_id=target_template_id,
                execution_session=execution_session,
            )
            target_scene = _scene_for_delivery_presets(scene, presets)
            config = resolve_config(
                target_template,
                target_scene,
                session_overrides=session_overrides,
                **runtime_material.to_resolve_kwargs(),
            )
            terminal_owner = pipeline_terminal_assembly_owner(config)
            planned_output_paths = (
                {}
                if terminal_owner
                else plan_pipeline_output_paths(
                    input_path,
                    config,
                    output_dir=output_dir,
                    output_suffix=output_suffix,
                    force_delivery_presets=True,
                )
            )
            planned_artifact_paths = plan_delivery_artifact_paths(
                input_path=input_path,
                output_dir=output_dir,
                config=config,
                output_paths=planned_output_paths,
            )
        except Exception as exc:
            prepared.append(
                PreparedDeliveryTargetGroup(
                    target_template_id=target_template_id,
                    config=None,
                    planned_output_paths={},
                    terminal_owner="",
                    error=str(exc) or type(exc).__name__,
                    planned_artifact_paths={},
                )
            )
            continue
        prepared.append(
            PreparedDeliveryTargetGroup(
                target_template_id=target_template_id,
                config=config,
                planned_output_paths=planned_output_paths,
                terminal_owner=terminal_owner,
                error="",
                planned_artifact_paths=planned_artifact_paths,
            )
        )
    return prepared


def _publish_group_material_artifacts(
    state: _DeliveryAggregate,
    *,
    status: str,
    input_path: Path,
    output_dir: Path,
    template: TemplateConfig,
    scene: SceneWorkspace,
    runtime_material: MaterialExecutionContext,
    session_overrides: dict[str, object],
) -> tuple[dict[str, str], dict[str, str], dict[str, object]]:
    if status == "cancelled":
        return {}, {}, {}

    manifest_config = capture_artifact_write(
        state.artifact_failures,
        "material_manifest",
        lambda: resolve_config(
            template,
            scene,
            session_overrides=session_overrides,
            **runtime_material.to_resolve_kwargs(),
        ),
        None,
    )
    if manifest_config is None:
        return {}, {}, {}

    material_manifest_paths = capture_artifact_write(
        state.artifact_failures,
        "material_manifest",
        lambda: write_material_manifest(
            input_path=input_path,
            output_dir=output_dir,
            config=manifest_config,
            material_context=runtime_material,
            material_diagnostics=state.material_diagnostics,
            output_paths=state.output_paths,
            compare_paths=state.compare_paths,
            report_paths=state.report_paths,
            intermediate_paths=state.intermediate_paths,
        ),
        {},
    )
    material_package_result = capture_artifact_write(
        state.artifact_failures,
        "material_package",
        lambda: write_material_package_artifacts(
            input_path=input_path,
            output_dir=output_dir,
            config=manifest_config,
            material_manifest_paths=material_manifest_paths,
            material_context=runtime_material,
            output_paths=state.output_paths,
            compare_paths=state.compare_paths,
            report_paths=state.report_paths,
            intermediate_paths=state.intermediate_paths,
        ),
        None,
    )
    return (
        material_manifest_paths,
        material_package_path_map(material_package_result),
        material_package_receipt_payload(material_package_result),
    )


def _delivery_payload(
    state: _DeliveryAggregate,
    *,
    status: str,
    default_delivery_preset_id: str,
    output_target_preflight: dict[str, object],
    style_source_summary: dict[str, object] | None,
    material_manifest_paths: dict[str, str],
    material_package_paths: dict[str, str],
    material_package_receipt: dict[str, object],
) -> dict[str, object]:
    return {
        "status": status,
        "output_path": primary_output_path_for_default(
            default_delivery_preset_id,
            state.output_paths,
        ),
        "output_paths": state.output_paths,
        "compare_paths": state.compare_paths,
        "report_paths": state.report_paths,
        "intermediate_paths": state.intermediate_paths,
        "material_manifest_paths": material_manifest_paths,
        "material_package_paths": material_package_paths,
        "material_package_receipt": material_package_receipt,
        "failed_count": state.failed_count,
        "artifact_failure_count": 0,
        "error_text": "; ".join(state.errors),
        "artifact_failures": [],
        "diagnostics_count": state.diagnostics_count,
        "diagnostics_summary": "\n".join(state.diagnostics_summary_parts),
        "diagnostics_items": state.diagnostics_items,
        "material_diagnostics": state.material_diagnostics,
        "content_visibility_scan": {
            "group_count": len(state.content_visibility_scans),
            "groups": state.content_visibility_scans,
        }
        if state.content_visibility_scans
        else {},
        "content_visibility_preview": state.content_visibility_preview,
        "content_visibility_receipts": state.content_visibility_receipts,
        "output_target_preflight": output_target_preflight,
        "object_preflight": state.object_preflight,
        "material_field_consistency": state.material_field_consistency,
        "style_source": dict(style_source_summary or {}),
        "journal_submission_package": state.journal_submission_package,
        "official_document_assembly": state.official_document_assembly,
        "official_numbering_preservation": state.official_numbering_preservation,
        "technical_chapter_inventory": state.technical_chapter_inventory,
        "application_section_word_limits": state.application_section_word_limits,
    }


def _delivery_preflight_failure_payload(
    output_target_preflight: dict[str, object],
    *,
    material_diagnostics: list[dict],
    style_source_summary: dict[str, object] | None,
) -> dict[str, object]:
    messages = [
        str(issue.get("message") or "")
        for item in list(output_target_preflight.get("items") or [])
        if isinstance(item, dict)
        for issue in list(item.get("issues") or [])
        if isinstance(issue, dict) and str(issue.get("message") or "").strip()
    ]
    diagnostics = diagnostics_payload(None, material_diagnostics)
    payload: dict[str, object] = {
        "status": "failed",
        "output_path": "",
        "output_paths": {},
        "compare_paths": {},
        "report_paths": [],
        "intermediate_paths": {},
        "material_manifest_paths": {},
        "material_package_paths": {},
        "failed_count": 0,
        "error_text": (
            "Delivery target group preflight blocked execution: "
            + "; ".join(dict.fromkeys(messages))
        ),
        "diagnostics_count": int(diagnostics["count"]),
        "diagnostics_summary": str(diagnostics["summary"] or ""),
        "diagnostics_items": list(diagnostics.get("items") or []),
        "material_diagnostics": list(material_diagnostics),
        "output_target_preflight": output_target_preflight,
        "style_source": dict(style_source_summary or {}),
    }
    return payload


def _cancelled_group_result(input_path: Path, config) -> PipelineResult:
    return PipelineResult(
        success=False,
        status="cancelled",
        context=PipelineContext(
            source_doc_path=str(input_path),
            source_doc_dir=str(input_path.parent),
        ),
        output_paths={},
        cancelled=True,
        config=config,
    )


def _scene_current_template_id(
    scene: SceneWorkspace,
    *,
    execution_session=None,
) -> str:
    if execution_session is not None:
        template_ref = getattr(execution_session, "template_ref", None)
        return str(
            getattr(template_ref, "effective_id", "")
            or getattr(template_ref, "resource_id", "")
            or ""
        ).strip()
    return str(getattr(scene, "template_id", "") or "").strip()


def _scene_for_delivery_presets(scene: SceneWorkspace, presets: list) -> SceneWorkspace:
    target_scene = copy.deepcopy(scene)
    target_scene.delivery_presets = [copy.deepcopy(preset) for preset in presets]
    preset_ids = [
        str(getattr(preset, "preset_id", "") or "").strip()
        for preset in target_scene.delivery_presets
    ]
    default_id = str(
        getattr(target_scene, "default_delivery_preset_id", "") or ""
    ).strip()
    if default_id not in preset_ids:
        target_scene.default_delivery_preset_id = next(
            (preset_id for preset_id in preset_ids if preset_id),
            "final",
        )
    return target_scene


def aggregate_delivery_status(statuses: list[str]) -> str:
    normalized = [str(status or "failed") for status in statuses]
    if not normalized:
        return "failed"
    if "cancelled" in normalized:
        return "cancelled"
    if all(status == "success" for status in normalized):
        return "success"
    if any(status in {"success", "partial_success"} for status in normalized):
        return "partial_success"
    return "failed"


__all__ = [
    "aggregate_delivery_status",
    "delivery_target_groups",
    "load_delivery_template",
    "mode_id_for_scene",
    "run_delivery_target_groups",
]
