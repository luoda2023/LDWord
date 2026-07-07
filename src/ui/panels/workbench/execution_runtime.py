from __future__ import annotations

import copy
import json
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QThread

from src.config.delivery_preset_display import delivery_preset_display_name
from src.config.entity import EntityArchive
from src.config.library import load_template_from_library
from src.config.material_batch import build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.style_source_report_summary import build_style_source_report_summary
from src.config.template import TemplateConfig
from src.execution_diagnostics import (
    build_execution_diagnostics,
    summarize_execution_diagnostics,
)
from src.modules.registry import create_all_modules
from src.pipeline.runner import Pipeline
from src.pipeline.scheduler import select_enabled_modules
from src.qt_api import QObject, Signal
from src.report_writer import write_json_report, write_markdown_report
from src.shared.engine.docx_compare import write_compare_docx
from src.shared.engine.scene_sample_docx_builder import scene_sample_fixture_manifest_paths

from .diagnostics import log_best_effort_shutdown_failure
from .exam_question_assets import material_context_with_exam_question_assets
from .material_artifacts import (
    _path_map,
    _unique_manifest_values,
    _write_material_manifest,
    _write_material_package_artifacts,
)
from .material_preflight import (
    material_failure_policy,
    material_preflight_error_text,
    material_requirement_diagnostics,
    missing_asset_rule_diagnostics,
    question_figure_file_diagnostics,
)
from .question_figure_repair_runtime import (
    _batch_question_figure_comparison_matrix,
    _batch_question_figure_repair_queue,
)


class WorkbenchProductionRunner:
    """Wrap pipeline execution for the workbench UI."""

    def __init__(
        self,
        *,
        doc_path: str,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        session_overrides: dict[str, object] | None = None,
        material_context: MaterialExecutionContext | None = None,
        output_dir: str | Path | None = None,
        output_suffix: str = "_formatted",
    ) -> None:
        self.doc_path = str(doc_path or "")
        self._template = template
        self._scene = scene
        self._session_overrides = dict(session_overrides or {})
        self._material_context = (
            material_context.clone()
            if isinstance(material_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        self._output_dir = Path(output_dir) if output_dir else None
        self._output_suffix = str(output_suffix or "_formatted")

    def run(self, progress_cb, cancel_check):
        input_path = Path(self.doc_path)
        output_dir = self._output_dir or input_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        template = self._template or TemplateConfig()
        scene = self._scene or SceneWorkspace()
        material_context = self._material_context.clone()
        style_source_summary = build_style_source_report_summary(scene, template)
        requirement_diagnostics = material_requirement_diagnostics(
            scene,
            material_context,
        )
        asset_file_diagnostics = question_figure_file_diagnostics(material_context)
        material_diagnostics = [*requirement_diagnostics, *asset_file_diagnostics]
        missing_roles = material_context.missing_required_asset_roles()
        asset_rule_diagnostics = missing_asset_rule_diagnostics(missing_roles)
        blocking_diagnostics = [
            *(
                requirement_diagnostics
                if material_failure_policy(scene) == "block"
                else []
            ),
            *asset_rule_diagnostics,
        ]
        if blocking_diagnostics:
            payload = _failed_payload(
                material_preflight_error_text(blocking_diagnostics),
                material_diagnostics=[*material_diagnostics, *asset_rule_diagnostics],
            )
            payload["style_source"] = dict(style_source_summary or {})
            _attach_material_preflight_reports(
                payload,
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                material_context=material_context,
            )
            return payload
        target_groups = _delivery_target_groups(scene)
        if target_groups:
            return self._run_delivery_target_groups(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                target_groups=target_groups,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
                material_diagnostics=material_diagnostics,
                material_context=material_context,
                style_source_summary=style_source_summary,
            )

        runtime_material = material_context_with_exam_question_assets(
            scene,
            material_context,
        )
        config = resolve_config(
            template,
            scene,
            session_overrides=self._session_overrides,
            **runtime_material.to_resolve_kwargs(),
        )

        result, elapsed, modules_enabled, modules_total = self._execute_config(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
            force_delivery_presets=_should_force_delivery_presets(config),
        )
        return self._payload_from_result(
            result,
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            material_context=runtime_material,
            style_source_summary=style_source_summary,
        )

    def _execute_config(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        config,
        progress_cb,
        cancel_check,
        force_delivery_presets: bool = False,
    ):
        modules = create_all_modules()
        enabled, _auto_pruned = select_enabled_modules(modules, config.is_module_enabled)

        started_at = time.perf_counter()
        pipeline = Pipeline(
            modules=enabled,
            config=config,
            output_dir=str(output_dir),
            output_suffix=self._output_suffix,
            progress_callback=progress_cb,
            cancel_check=cancel_check,
            force_delivery_presets=force_delivery_presets,
        )
        result = pipeline.execute(str(input_path))
        elapsed = time.perf_counter() - started_at
        return result, elapsed, len(enabled), len(modules)

    def _payload_from_result(
        self,
        result,
        *,
        input_path: Path,
        output_dir: Path,
        config,
        elapsed: float,
        modules_enabled: int,
        modules_total: int,
        material_diagnostics: list[dict] | None = None,
        material_context: MaterialExecutionContext | None = None,
        style_source_summary: dict[str, object] | None = None,
    ) -> dict[str, object]:
        runtime_material = (
            material_context.clone()
            if isinstance(material_context, MaterialExecutionContext)
            else self._material_context.clone()
        )
        diagnostics = _diagnostics_payload(result, material_diagnostics)
        visibility_scan = _content_visibility_scan_payload(result)
        visibility_preview = _content_visibility_preview_payload(result)
        output_target_preflight = _output_target_preflight_payload(result)
        object_preflight = _object_preflight_payload(result)
        material_field_consistency = _material_field_consistency_payload(result)
        journal_submission_package = _journal_submission_package_payload(result)
        official_numbering_preservation = _official_numbering_preservation_payload(result)
        technical_chapter_inventory = _technical_chapter_inventory_payload(result)
        application_section_word_limits = _application_section_word_limits_payload(result)

        status = getattr(result, "status", "failed") or "failed"
        if status == "cancelled":
            return {"status": "cancelled"}

        failed_items = list(getattr(result, "failed_items", []) or [])
        failed_count = len(failed_items)

        if not getattr(result, "success", False):
            material_manifest_paths = _write_material_manifest(
                input_path=input_path,
                output_dir=output_dir,
                config=config,
                material_context=runtime_material,
                material_diagnostics=list(material_diagnostics or []),
                output_paths={},
                compare_paths={},
                report_paths=[],
                intermediate_paths={},
            )
            material_package_paths = _write_material_package_artifacts(
                input_path=input_path,
                output_dir=output_dir,
                config=config,
                material_manifest_paths=material_manifest_paths,
            )
            return {
                "status": "failed",
                "output_path": "",
                "output_paths": {},
                "compare_paths": {},
                "report_paths": [],
                "intermediate_paths": {},
                "material_manifest_paths": material_manifest_paths,
                "material_package_paths": material_package_paths,
                "failed_count": failed_count,
                "error_text": str(getattr(result, "error", "") or ""),
                "diagnostics_count": int(diagnostics["count"]),
                "diagnostics_summary": str(diagnostics["summary"] or ""),
                "diagnostics_items": list(diagnostics.get("items") or []),
                "material_diagnostics": list(material_diagnostics or []),
                "content_visibility_scan": visibility_scan,
                "content_visibility_preview": visibility_preview,
                "output_target_preflight": output_target_preflight,
                "object_preflight": object_preflight,
                "material_field_consistency": material_field_consistency,
                "style_source": dict(style_source_summary or {}),
                "journal_submission_package": journal_submission_package,
                "official_numbering_preservation": official_numbering_preservation,
                "technical_chapter_inventory": technical_chapter_inventory,
                "application_section_word_limits": application_section_word_limits,
            }

        output_paths = getattr(result, "output_paths", None)
        if not isinstance(output_paths, dict):
            output_paths = {}
        output_paths = {str(key): str(value) for key, value in output_paths.items()}
        output_path = _primary_output_path(config, output_paths)
        compare_paths = _write_compare_docx_artifacts(
            result,
            input_path=input_path,
            output_dir=output_dir,
            output_paths=output_paths,
            fallback_output_path=output_path,
            config=config,
        )

        report_paths: list[str] = []
        if _uses_delivery_presets(config):
            report_paths.extend(
                _write_delivery_reports(
                    result,
                    input_path=input_path,
                    output_dir=output_dir,
                    output_paths=output_paths,
                    config=config,
                    elapsed=elapsed,
                    modules_enabled=modules_enabled,
                    modules_total=modules_total,
                    material_diagnostics=list(material_diagnostics or []),
                    material_context=runtime_material,
                    style_source_summary=style_source_summary,
                )
            )
        else:
            output_cfg = getattr(config, "output", None)
            report_json_enabled = bool(getattr(output_cfg, "report_json", True))
            report_markdown_enabled = bool(getattr(output_cfg, "report_markdown", True))
            final_output_path = Path(output_path) if output_path else None

            if report_json_enabled:
                report_json = output_dir / f"{input_path.stem}_changes.json"
                write_json_report(
                    result,
                    input_path=input_path,
                    output_path=final_output_path,
                    report_path=report_json,
                    elapsed=elapsed,
                    modules_enabled=modules_enabled,
                    modules_total=modules_total,
                    extra_diagnostics=list(material_diagnostics or []),
                    style_source_summary=style_source_summary,
                )
                report_paths.append(str(report_json))

            if report_markdown_enabled:
                report_md = output_dir / f"{input_path.stem}_changes.md"
                write_markdown_report(
                    result,
                    input_path=input_path,
                    report_path=report_md,
                    elapsed=elapsed,
                    modules_enabled=modules_enabled,
                    modules_total=modules_total,
                    extra_diagnostics=list(material_diagnostics or []),
                    style_source_summary=style_source_summary,
                )
                report_paths.append(str(report_md))

        intermediate_paths = _write_structured_intermediates(
            result,
            input_path=input_path,
            output_dir=output_dir,
            output_paths=output_paths,
            fallback_output_path=output_path,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
        )
        material_manifest_paths = _write_material_manifest(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            material_context=runtime_material,
            material_diagnostics=list(material_diagnostics or []),
            output_paths=output_paths,
            compare_paths=compare_paths,
            report_paths=report_paths,
            intermediate_paths=intermediate_paths,
        )
        material_package_paths = _write_material_package_artifacts(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            material_manifest_paths=material_manifest_paths,
        )

        payload = {
            "status": str(status),
            "output_path": output_path,
            "output_paths": output_paths,
            "compare_paths": compare_paths,
            "report_paths": report_paths,
            "intermediate_paths": intermediate_paths,
            "material_manifest_paths": material_manifest_paths,
            "material_package_paths": material_package_paths,
            "failed_count": failed_count,
            "error_text": str(getattr(result, "error", "") or ""),
            "diagnostics_count": int(diagnostics["count"]),
            "diagnostics_summary": str(diagnostics["summary"] or ""),
            "diagnostics_items": list(diagnostics.get("items") or []),
            "material_diagnostics": list(material_diagnostics or []),
            "content_visibility_scan": visibility_scan,
            "content_visibility_preview": visibility_preview,
            "output_target_preflight": output_target_preflight,
            "object_preflight": object_preflight,
            "material_field_consistency": material_field_consistency,
            "style_source": dict(style_source_summary or {}),
            "journal_submission_package": journal_submission_package,
            "official_numbering_preservation": official_numbering_preservation,
            "technical_chapter_inventory": technical_chapter_inventory,
            "application_section_word_limits": application_section_word_limits,
        }
        return _attach_scene_sample_manifest_paths(payload)

    def _run_delivery_target_groups(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        target_groups: list[tuple[str, list]],
        progress_cb,
        cancel_check,
        material_diagnostics: list[dict] | None = None,
        material_context: MaterialExecutionContext | None = None,
        style_source_summary: dict[str, object] | None = None,
    ) -> dict[str, object]:
        output_paths: dict[str, str] = {}
        compare_paths: dict[str, str] = {}
        report_paths: list[str] = []
        intermediate_paths: dict[str, str] = {}
        failed_count = 0
        material_diagnostics = list(material_diagnostics or [])
        diagnostics_count = len(material_diagnostics)
        diagnostics_items: list[dict] = [
            dict(item) for item in material_diagnostics if isinstance(item, dict)
        ]
        diagnostics_summary_parts: list[str] = []
        object_preflight: dict[str, object] = {}
        material_field_consistency: dict[str, object] = {}
        journal_submission_package: dict[str, object] = {}
        official_numbering_preservation: dict[str, object] = {}
        technical_chapter_inventory: dict[str, object] = {}
        application_section_word_limits: dict[str, object] = {}
        material_summary = summarize_execution_diagnostics(material_diagnostics)
        if material_summary:
            diagnostics_summary_parts.append(material_summary)
        statuses: list[str] = []
        errors: list[str] = []
        runtime_material = material_context_with_exam_question_assets(
            scene,
            material_context
            if isinstance(material_context, MaterialExecutionContext)
            else self._material_context,
        )

        for target_template_id, presets in target_groups:
            if cancel_check():
                return {"status": "cancelled"}

            try:
                target_template = _load_delivery_template(
                    template,
                    scene=scene,
                    target_template_id=target_template_id,
                )
            except Exception as exc:
                statuses.append("failed")
                failed_count += 1
                label = target_template_id or "current"
                errors.append(f"{label}: {exc}")
                continue

            target_scene = _scene_for_delivery_presets(scene, presets)
            config = resolve_config(
                target_template,
                target_scene,
                session_overrides=self._session_overrides,
                **runtime_material.to_resolve_kwargs(),
            )
            result, elapsed, modules_enabled, modules_total = self._execute_config(
                input_path=input_path,
                output_dir=output_dir,
                config=config,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
                force_delivery_presets=True,
            )

            status = str(getattr(result, "status", "failed") or "failed")
            if not object_preflight:
                object_preflight = _object_preflight_payload(result)
            if not material_field_consistency:
                material_field_consistency = _material_field_consistency_payload(result)
            if not journal_submission_package:
                journal_submission_package = _journal_submission_package_payload(result)
            if not official_numbering_preservation:
                official_numbering_preservation = (
                    _official_numbering_preservation_payload(result)
                )
            if not technical_chapter_inventory:
                technical_chapter_inventory = _technical_chapter_inventory_payload(result)
            if not application_section_word_limits:
                application_section_word_limits = (
                    _application_section_word_limits_payload(result)
                )
            if status == "cancelled":
                return {"status": "cancelled"}
            statuses.append(status)

            failed_items = list(getattr(result, "failed_items", []) or [])
            failed_count += len(failed_items)

            diagnostics = build_execution_diagnostics(result)
            diagnostics_count += int(diagnostics["count"])
            diagnostics_items.extend(
                dict(item)
                for item in list(diagnostics.get("items") or [])
                if isinstance(item, dict)
            )
            summary = str(diagnostics["summary"] or "").strip()
            if summary:
                diagnostics_summary_parts.append(summary)

            if not getattr(result, "success", False):
                error_text = str(getattr(result, "error", "") or "")
                if error_text:
                    errors.append(error_text)
                continue

            group_output_paths = getattr(result, "output_paths", None)
            if not isinstance(group_output_paths, dict):
                group_output_paths = {}
            group_output_paths = {
                str(key): str(value) for key, value in group_output_paths.items()
            }
            output_paths.update(group_output_paths)
            compare_paths.update(
                _write_compare_docx_artifacts(
                    result,
                    input_path=input_path,
                    output_dir=output_dir,
                    output_paths=group_output_paths,
                    fallback_output_path=_primary_output_path(config, group_output_paths),
                    config=config,
                )
            )
            report_paths.extend(
                _write_delivery_reports(
                    result,
                    input_path=input_path,
                    output_dir=output_dir,
                    output_paths=group_output_paths,
                    config=config,
                    elapsed=elapsed,
                    modules_enabled=modules_enabled,
                    modules_total=modules_total,
                    material_diagnostics=material_diagnostics,
                    material_context=runtime_material,
                    style_source_summary=style_source_summary,
                )
            )
            intermediate_paths.update(
                _write_structured_intermediates(
                    result,
                    input_path=input_path,
                    output_dir=output_dir,
                    output_paths=group_output_paths,
                    fallback_output_path=_primary_output_path(config, group_output_paths),
                    config=config,
                    elapsed=elapsed,
                    modules_enabled=modules_enabled,
                    modules_total=modules_total,
                )
            )

        status = _aggregate_delivery_status(statuses)
        manifest_config = resolve_config(
            template,
            scene,
            session_overrides=self._session_overrides,
            **runtime_material.to_resolve_kwargs(),
        )
        material_manifest_paths = _write_material_manifest(
            input_path=input_path,
            output_dir=output_dir,
            config=manifest_config,
            material_context=runtime_material,
            material_diagnostics=material_diagnostics,
            output_paths=output_paths,
            compare_paths=compare_paths,
            report_paths=report_paths,
            intermediate_paths=intermediate_paths,
        )
        material_package_paths = _write_material_package_artifacts(
            input_path=input_path,
            output_dir=output_dir,
            config=manifest_config,
            material_manifest_paths=material_manifest_paths,
        )
        payload = {
            "status": status,
            "output_path": _primary_output_path_for_default(
                scene.default_delivery_preset_id,
                output_paths,
            ),
            "output_paths": output_paths,
            "compare_paths": compare_paths,
            "report_paths": report_paths,
            "intermediate_paths": intermediate_paths,
            "material_manifest_paths": material_manifest_paths,
            "material_package_paths": material_package_paths,
            "failed_count": failed_count,
            "error_text": "; ".join(errors),
            "diagnostics_count": diagnostics_count,
            "diagnostics_summary": "\n".join(diagnostics_summary_parts),
            "diagnostics_items": diagnostics_items,
            "material_diagnostics": material_diagnostics,
            "object_preflight": object_preflight,
            "material_field_consistency": material_field_consistency,
            "style_source": dict(style_source_summary or {}),
            "journal_submission_package": journal_submission_package,
            "official_numbering_preservation": official_numbering_preservation,
            "technical_chapter_inventory": technical_chapter_inventory,
            "application_section_word_limits": application_section_word_limits,
        }
        return _attach_scene_sample_manifest_paths(payload)


class WorkbenchBatchProductionRunner:
    """Run the same source document once per selected entity profile."""

    def __init__(
        self,
        *,
        doc_path: str,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        archive: EntityArchive,
        profile_ids: list[str] | None = None,
        base_output_dir: str | Path | None = None,
        output_dir_template: str = "{entity_name}",
        session_overrides: dict[str, object] | None = None,
        base_context: MaterialExecutionContext | None = None,
    ) -> None:
        self.doc_path = str(doc_path or "")
        self._template = template
        self._scene = scene
        self._archive = archive
        self._profile_ids = list(profile_ids) if profile_ids is not None else None
        self._base_output_dir = base_output_dir
        self._output_dir_template = output_dir_template
        self._session_overrides = dict(session_overrides or {})
        self._base_context = (
            base_context.clone()
            if isinstance(base_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )

    def run(self, progress_cb, cancel_check):
        input_path = Path(self.doc_path)
        base_output_dir = self._base_output_dir or (input_path.parent / "output" / "batch")
        batch_items = build_material_batch_items(
            self._archive,
            profile_ids=self._profile_ids,
            base_output_dir=base_output_dir,
            output_dir_template=self._output_dir_template,
            base_context=self._base_context,
        )

        results: list[dict[str, object]] = []

        for index, item in enumerate(batch_items, start=1):
            if cancel_check():
                payload = _batch_payload("cancelled", results, error_text="")
                _attach_batch_reports(payload, base_output_dir, input_path)
                return payload
            progress_cb(index - 1, len(batch_items), f"批量生成: {item.profile_name or item.profile_id}")
            missing_roles = item.context.missing_required_asset_roles()
            if missing_roles:
                results.append(_batch_missing_assets_result(item, missing_roles))
                continue
            payload = WorkbenchProductionRunner(
                doc_path=self.doc_path,
                template=self._template,
                scene=self._scene,
                session_overrides=self._session_overrides,
                material_context=item.context,
                output_dir=item.output_dir,
            ).run(progress_cb, cancel_check)
            payload = dict(payload)
            payload["profile_id"] = item.profile_id
            payload["profile_name"] = item.profile_name
            payload["output_dir"] = item.output_dir
            results.append(payload)

        if not results:
            payload = _batch_payload("failed", results, error_text="No profiles selected for batch execution")
            _attach_batch_reports(payload, base_output_dir, input_path)
            return payload

        statuses = {str(item.get("status") or "failed") for item in results}
        if statuses == {"success"}:
            status = "success"
            error_text = ""
        elif "success" in statuses or "partial_success" in statuses:
            status = "partial_success"
            error_text = ""
        else:
            status = "failed"
            error_text = _batch_all_failed_error(results)
        payload = _batch_payload(status, results, error_text=error_text)
        _attach_batch_reports(payload, base_output_dir, input_path)
        return payload


def _failed_payload(
    error_text: str,
    *,
    material_diagnostics: list[dict] | None = None,
) -> dict[str, object]:
    diagnostics = _diagnostics_payload(None, material_diagnostics)
    return {
        "status": "failed",
        "output_path": "",
        "output_paths": {},
        "compare_paths": {},
        "report_paths": [],
        "intermediate_paths": {},
        "material_manifest_paths": {},
        "material_package_paths": {},
        "failed_count": 0,
        "error_text": error_text,
        "diagnostics_count": int(diagnostics["count"]),
        "diagnostics_summary": str(diagnostics["summary"] or ""),
        "diagnostics_items": list(diagnostics.get("items") or []),
        "material_diagnostics": list(material_diagnostics or []),
    }


def _attach_scene_sample_manifest_paths(payload: dict[str, object]) -> dict[str, object]:
    manifest_paths = scene_sample_fixture_manifest_paths()
    if manifest_paths:
        payload["scene_sample_manifest_paths"] = manifest_paths
    return payload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _diagnostics_payload(result, extra_diagnostics: list[dict] | None = None) -> dict[str, object]:
    base_items: list[dict] = []
    if result is not None:
        base_items = list(build_execution_diagnostics(result)["items"])
    items = [*[dict(item) for item in (extra_diagnostics or [])], *base_items]
    return {
        "count": len(items),
        "items": items,
        "summary": summarize_execution_diagnostics(items),
    }


def _content_visibility_scan_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    scan = getattr(context, "content_visibility_scan", None)
    if scan is None:
        return {}
    payload = asdict(scan)
    payload["has_issues"] = bool(getattr(scan, "has_issues", False))
    payload["issue_messages"] = list(scan.issue_messages())
    return payload


def _content_visibility_preview_payload(result) -> list[dict[str, object]]:
    context = getattr(result, "context", None)
    previews = getattr(context, "content_visibility_preview", None)
    if not previews:
        return []
    return [asdict(preview) for preview in list(previews or [])]


def _output_target_preflight_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    preflight = getattr(context, "output_target_preflight", None)
    if preflight is None:
        return {}
    payload = asdict(preflight)
    payload["has_issues"] = bool(getattr(preflight, "has_issues", False))
    payload["issue_count"] = int(getattr(preflight, "issue_count", 0) or 0)
    return payload


def _object_preflight_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    if context is None:
        return {}

    policy = getattr(context, "object_preflight_policy", None)
    preflight = getattr(context, "object_preflight", None)
    if policy is None and preflight is None:
        return {}

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


def _material_field_consistency_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    consistency = getattr(context, "material_field_consistency", None)
    if consistency is None:
        return {}

    items: list[dict[str, object]] = []
    issues: list[dict[str, str]] = []
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

    if not items and not _clean_text(getattr(consistency, "schema_id", "")):
        return {}
    return {
        "schema_id": _clean_text(getattr(consistency, "schema_id", "")),
        "family_id": _clean_text(getattr(consistency, "family_id", "")),
        "status": _clean_text(getattr(consistency, "status", "")),
        "field_count": len(items),
        "issue_count": len(issues),
        "items": items,
        "issues": issues,
    }


def _journal_submission_package_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    evidence = (
        getattr(context, "journal_submission_package", None)
        if context is not None
        else None
    )
    if evidence is None:
        return {}
    to_dict = getattr(evidence, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(evidence, dict):
        payload = dict(evidence)
    else:
        return {}
    if _clean_text(payload.get("status")) in {"", "not_applicable"}:
        return {}
    return _plain_data(payload)


def _official_numbering_preservation_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    evidence = (
        getattr(context, "official_numbering_preservation", None)
        if context is not None
        else None
    )
    if evidence is None:
        return {}
    to_dict = getattr(evidence, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(evidence, dict):
        payload = dict(evidence)
    else:
        return {}
    if _clean_text(payload.get("status")) in {"", "not_applicable"}:
        return {}
    return _plain_data(payload)


def _technical_chapter_inventory_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    evidence = (
        getattr(context, "technical_chapter_inventory", None)
        if context is not None
        else None
    )
    if evidence is None:
        return {}
    to_dict = getattr(evidence, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(evidence, dict):
        payload = dict(evidence)
    else:
        return {}
    if _clean_text(payload.get("status")) in {"", "not_applicable"}:
        return {}
    return _plain_data(payload)


def _application_section_word_limits_payload(result) -> dict[str, object]:
    context = getattr(result, "context", None)
    evidence = (
        getattr(context, "application_section_word_limits", None)
        if context is not None
        else None
    )
    if evidence is None:
        return {}
    to_dict = getattr(evidence, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    elif isinstance(evidence, dict):
        payload = dict(evidence)
    else:
        return {}
    if _clean_text(payload.get("status")) in {"", "not_applicable"}:
        return {}
    return _plain_data(payload)


def _material_field_issue_payload(issue) -> dict[str, str]:
    return {
        "field_key": _clean_text(getattr(issue, "field_key", "")),
        "kind": _clean_text(getattr(issue, "kind", "")),
        "severity": _clean_text(getattr(issue, "severity", "")) or "warning",
        "expected": _clean_text(getattr(issue, "expected", "")),
        "observed": _clean_text(getattr(issue, "observed", "")),
        "location": _clean_text(getattr(issue, "location", "")),
        "message": _clean_text(getattr(issue, "message", "")),
    }


def _clean_text(value) -> str:
    return str(value or "").strip()


def _clean_list(values) -> list[str]:
    return [
        _clean_text(value)
        for value in list(values or [])
        if _clean_text(value)
    ]


def _clean_mapping_lists(value) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {
        _clean_text(key): _clean_list(items)
        for key, items in value.items()
        if _clean_text(key)
    }


def _clean_module_skips(values) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for value in list(values or []):
        if not isinstance(value, dict):
            continue
        module_name = _clean_text(value.get("module_name"))
        if not module_name:
            continue
        entries.append(
            {
                "module_name": module_name,
                "finding_kinds": _clean_list(value.get("finding_kinds", [])),
                "reason": _clean_text(value.get("reason")),
            }
        )
    return entries


def _attach_material_preflight_reports(
    payload: dict[str, object],
    *,
    input_path: Path,
    output_dir: Path,
    template: TemplateConfig,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext | None = None,
) -> None:
    runtime_material = (
        material_context.clone()
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    config = resolve_config(template, scene, **runtime_material.to_resolve_kwargs())
    output_cfg = getattr(config, "output", None)
    diagnostics = list(payload.get("material_diagnostics") or [])
    report_paths: list[str] = []
    if bool(getattr(output_cfg, "report_json", True)):
        report_json = output_dir / f"{input_path.stem}_changes.json"
        report_json.write_text(
            json.dumps(
                {
                    "input": str(input_path),
                    "output": "",
                    "status": payload.get("status", "failed"),
                    "elapsed_seconds": 0,
                    "modules_enabled": 0,
                    "modules_total": 0,
                    "changes": [],
                    "diagnostics": {
                        "count": len(diagnostics),
                        "items": diagnostics,
                    },
                    "material_diagnostics": diagnostics,
                    "counts": None,
                    "failed_items": [],
                    "error_text": str(payload.get("error_text") or ""),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        report_paths.append(str(report_json))
    if bool(getattr(output_cfg, "report_markdown", True)):
        report_md = output_dir / f"{input_path.stem}_changes.md"
        lines = [
            f"# 排版报告 - {input_path.name}",
            "",
            "- 状态: **failed**",
            "- 耗时: 0.00s",
            "- 模块: 0/0 启用",
            "",
            f"- Error: {payload.get('error_text', '')}",
            "",
        ]
        if diagnostics:
            lines.append(f"## 诊断提示 ({len(diagnostics)} 项)")
            lines.append("")
            for item in diagnostics:
                reason = str(item.get("reason") or "").strip()
                target = str(item.get("target") or "").strip()
                rule_name = str(item.get("rule_name") or "material_schema").strip()
                lines.append(f"- [{rule_name}] {target}: {reason}")
            lines.append("")
        report_md.write_text("\n".join(lines), encoding="utf-8")
        report_paths.append(str(report_md))
    payload["report_paths"] = report_paths
    payload["material_manifest_paths"] = _write_material_manifest(
        input_path=input_path,
        output_dir=output_dir,
        config=config,
        material_context=runtime_material,
        material_diagnostics=diagnostics,
        output_paths={},
        compare_paths={},
        report_paths=report_paths,
        intermediate_paths={},
    )
    payload["material_package_paths"] = _write_material_package_artifacts(
        input_path=input_path,
        output_dir=output_dir,
        config=config,
        material_manifest_paths=_path_map(payload.get("material_manifest_paths")),
    )


def _missing_required_assets_text(roles: list[str]) -> str:
    return "Missing required material assets: " + ", ".join(sorted(set(roles)))


def _batch_missing_assets_result(item, roles: list[str]) -> dict[str, object]:
    missing_roles = sorted(set(str(role) for role in roles if str(role or "").strip()))
    reason = _missing_required_assets_text(missing_roles)
    diagnostic = {
        "rule_name": "material_assets",
        "target": "required_asset_roles",
        "section": "material",
        "change_type": "preflight_missing_asset_roles",
        "before": "",
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": "error",
        "missing_asset_roles": missing_roles,
        "reason": reason,
    }
    return {
        "status": "failed",
        "profile_id": item.profile_id,
        "profile_name": item.profile_name,
        "output_dir": item.output_dir,
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "material_manifest_paths": {},
        "material_package_paths": {},
        "material_diagnostics": [diagnostic],
        "failed_count": 1,
        "error_text": reason,
        "diagnostics_count": 1,
        "diagnostics_summary": reason,
    }


def _batch_missing_required_assets(batch_items) -> list[str]:
    missing: list[str] = []
    for item in batch_items:
        roles = item.context.missing_required_asset_roles()
        if not roles:
            continue
        label = item.profile_name or item.profile_id or "profile"
        missing.append(f"{label}: {', '.join(sorted(set(roles)))}")
    return missing


def _batch_all_failed_error(results: list[dict[str, object]]) -> str:
    reasons: list[str] = []
    for item in results:
        label = str(item.get("profile_name") or item.get("profile_id") or "profile")
        error_text = str(item.get("error_text") or "").strip()
        if error_text:
            reasons.append(f"{label}: {error_text}")
    return "; ".join(reasons) or "All batch items failed"


def _attach_batch_reports(
    payload: dict[str, object],
    base_output_dir: str | Path,
    input_path: Path,
) -> None:
    output_dir = Path(base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{input_path.stem}_batch_report.json"
    md_path = output_dir / f"{input_path.stem}_batch_report.md"

    batch_issue_items = payload.get("batch_issue_items", [])
    comparison_matrix = _batch_question_figure_comparison_matrix(batch_issue_items)
    repair_queue = _batch_question_figure_repair_queue(batch_issue_items)
    report_payload = {
        "status": payload.get("status", "failed"),
        "input_path": str(input_path),
        "items": payload.get("items", []),
        "output_paths": payload.get("output_paths", []),
        "material_manifest_paths": payload.get("material_manifest_paths", {}),
        "material_package_paths": payload.get("material_package_paths", {}),
        "material_diagnostics": payload.get("material_diagnostics", []),
        "batch_issue_items": batch_issue_items,
        "question_figure_comparison_matrix": comparison_matrix,
        "question_figure_repair_queue": repair_queue,
        "failed_count": int(payload.get("failed_count") or 0),
        "error_text": str(payload.get("error_text") or ""),
        "diagnostics_count": int(payload.get("diagnostics_count") or 0),
        "diagnostics_summary": str(payload.get("diagnostics_summary") or ""),
        "batch_isolation": payload.get("batch_isolation", {}),
    }
    json_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_render_batch_markdown_report(report_payload), encoding="utf-8")

    batch_report_paths = [str(json_path), str(md_path)]
    payload["batch_report_paths"] = batch_report_paths
    payload["question_figure_comparison_matrix"] = comparison_matrix
    payload["question_figure_repair_queue"] = repair_queue
    report_paths = [str(path) for path in payload.get("report_paths", []) or []]
    payload["report_paths"] = [*report_paths, *batch_report_paths]


def _render_batch_markdown_report(report_payload: dict[str, object]) -> str:
    lines = [
        "# Batch Material Execution Report",
        "",
        f"- Status: {report_payload.get('status', 'failed')}",
        f"- Input: {report_payload.get('input_path', '')}",
        f"- Failed count: {report_payload.get('failed_count', 0)}",
    ]
    error_text = str(report_payload.get("error_text") or "")
    if error_text:
        lines.append(f"- Error: {error_text}")
    issue_items = [
        item for item in list(report_payload.get("batch_issue_items", []) or [])
        if isinstance(item, dict)
    ]
    if issue_items:
        lines.extend(["", "## Batch Issue Center"])
        for issue in issue_items[:50]:
            profile = issue.get("profile_name") or issue.get("profile_id") or "profile"
            lines.append(
                f"- {profile}: {issue.get('kind', 'issue')} -> {issue.get('summary', '')}"
            )
    comparison_matrix = report_payload.get("question_figure_comparison_matrix", {})
    if isinstance(comparison_matrix, dict) and int(comparison_matrix.get("total_issue_count") or 0):
        lines.extend(["", "## Question Figure Comparison Matrix"])
        lines.append(
            "- Total issues: {issues}; profiles: {profiles}; questions: {questions}".format(
                issues=comparison_matrix.get("total_issue_count", 0),
                profiles=comparison_matrix.get("profile_count", 0),
                questions=comparison_matrix.get("question_count", 0),
            )
        )
        for profile in list(comparison_matrix.get("profiles", []) or [])[:30]:
            if not isinstance(profile, dict):
                continue
            profile_label = (
                profile.get("profile_name")
                or profile.get("profile_id")
                or "profile"
            )
            for question in list(profile.get("questions", []) or [])[:50]:
                if not isinstance(question, dict):
                    continue
                question_index = question.get("question_index") or "-"
                item_labels = [
                    str(
                        item.get("display_name")
                        or item.get("reference")
                        or item.get("path")
                        or item.get("item_id")
                        or "issue"
                    )
                    for item in list(question.get("items", []) or [])[:5]
                    if isinstance(item, dict)
                ]
                label_text = ", ".join(item_labels) if item_labels else "issue"
                region_text = ""
                first_item = next(
                    (
                        item
                        for item in list(question.get("items", []) or [])
                        if isinstance(item, dict)
                        and str(item.get("region_summary") or "").strip()
                    ),
                    None,
                )
                if isinstance(first_item, dict):
                    region_text = f" · {first_item.get('region_summary')}"
                lines.append(
                    f"- {profile_label} / Q{question_index}: "
                    f"{question.get('issue_count', 0)} issue(s) -> {label_text}{region_text}"
                )
    repair_queue = report_payload.get("question_figure_repair_queue", {})
    if isinstance(repair_queue, dict) and int(repair_queue.get("queue_count") or 0):
        lines.extend(["", "## Question Figure Repair Queue"])
        conflict_count = int(repair_queue.get("conflict_count") or 0)
        conflict_text = f"; conflicts: {conflict_count}" if conflict_count else ""
        lines.append(
            "- Candidate count: {count}; confirmation: required; auto apply: disabled{conflicts}".format(
                count=repair_queue.get("queue_count", 0),
                conflicts=conflict_text,
            )
        )
        plan = repair_queue.get("batch_confirmation_plan", {})
        if isinstance(plan, dict):
            lines.append(
                "- Batch confirmation plan: status={status}; eligible={eligible}; "
                "blocked={blocked}; conflicts={conflicts}; batch_apply=false".format(
                    status=_clean_text(plan.get("status")) or "empty",
                    eligible=plan.get("eligible_count", 0),
                    blocked=plan.get("blocked_count", 0),
                    conflicts=plan.get("conflict_count", 0),
                )
            )
            blocked_ids = [
                _clean_text(queue_id)
                for queue_id in list(plan.get("blocked_queue_ids") or [])[:20]
                if _clean_text(queue_id)
            ]
            if blocked_ids:
                lines.append("- Batch blocked queue ids: " + ", ".join(blocked_ids))
        freeze = repair_queue.get("batch_confirmation_freeze", {})
        if isinstance(freeze, dict) and freeze:
            lines.append(
                "- Batch confirmation freeze: status={status}; frozen={frozen}; "
                "blocked={blocked}; fingerprint={fingerprint}; batch_apply=false".format(
                    status=_clean_text(freeze.get("status")) or "blocked",
                    frozen=freeze.get("frozen_candidate_count", 0),
                    blocked=freeze.get("blocked_count", 0),
                    fingerprint=_clean_text(freeze.get("plan_fingerprint")),
                )
            )
        dry_run = repair_queue.get("batch_apply_dry_run", {})
        if isinstance(dry_run, dict) and dry_run:
            lines.append(
                "- Batch apply dry-run: status={status}; checked={checked}; "
                "blocked={blocked}; guard_passed={guard}; batch_apply=false".format(
                    status=_clean_text(dry_run.get("status")) or "blocked",
                    checked=dry_run.get("checked_candidate_count", 0),
                    blocked=len(list(dry_run.get("blocked_queue_ids") or [])),
                    guard=str(bool(dry_run.get("execution_guard_passed"))).lower(),
                )
            )
        execution_plan = repair_queue.get("batch_apply_execution_plan", {})
        if isinstance(execution_plan, dict) and execution_plan:
            final_confirmation = (
                "provided"
                if bool(execution_plan.get("final_confirmation_provided"))
                else "required"
            )
            lines.append(
                "- Batch apply execution plan: status={status}; planned={planned}; "
                "final_confirmation={confirmation}; batch_apply=false".format(
                    status=_clean_text(execution_plan.get("status")) or "blocked",
                    planned=execution_plan.get("planned_candidate_count", 0),
                    confirmation=final_confirmation,
                )
            )
        execution_result = repair_queue.get("batch_apply_execution_result", {})
        if isinstance(execution_result, dict) and execution_result:
            lines.append(
                "- Batch apply execution result: status={status}; applied={applied}; "
                "output={output}; word_write={word_write}; audit={audit}".format(
                    status=_clean_text(execution_result.get("status")) or "blocked",
                    applied=execution_result.get("applied_count", 0),
                    output=_clean_text(execution_result.get("output_path")),
                    word_write=str(bool(execution_result.get("word_write_enabled"))).lower(),
                    audit=(
                        "written"
                        if bool(execution_result.get("audit_written"))
                        else "not_written"
                    ),
                )
            )
        rollback_result = repair_queue.get("batch_apply_rollback_result", {})
        if isinstance(rollback_result, dict) and rollback_result:
            lines.append(
                "- Batch apply rollback result: status={status}; restored={restored}; "
                "output={output}; word_write={word_write}; audit={audit}".format(
                    status=_clean_text(rollback_result.get("status")) or "blocked",
                    restored=rollback_result.get("restored_count", 0),
                    output=_clean_text(rollback_result.get("output_path")),
                    word_write=str(bool(rollback_result.get("word_write_enabled"))).lower(),
                    audit=(
                        "written"
                        if bool(rollback_result.get("audit_written"))
                        else "not_written"
                    ),
                )
            )
        transaction_manifest = repair_queue.get("batch_apply_transaction_manifest", {})
        if isinstance(transaction_manifest, dict) and transaction_manifest:
            transaction_artifact = (
                "written"
                if bool(transaction_manifest.get("artifact_written"))
                else "not_written"
            )
            transaction_report = (
                "written"
                if bool(transaction_manifest.get("report_written"))
                else "not_written"
            )
            lines.append(
                "- Batch apply transaction manifest: status={status}; "
                "transactions={transactions}; active={active}; rolled_back={rolled}; "
                "orphan_rollback={orphan}; task={task}; rollback_available={rollback_available}; "
                "artifact={artifact}; report={report}".format(
                    status=_clean_text(transaction_manifest.get("status")) or "empty",
                    transactions=transaction_manifest.get("transaction_count", 0),
                    active=transaction_manifest.get("active_count", 0),
                    rolled=transaction_manifest.get("rolled_back_count", 0),
                    orphan=transaction_manifest.get("orphan_rollback_count", 0),
                    task=_clean_text(
                        (transaction_manifest.get("task_summary") or {}).get("status")
                        if isinstance(
                            transaction_manifest.get("task_summary"), Mapping
                        )
                        else ""
                    )
                    or "empty",
                    rollback_available=(
                        (transaction_manifest.get("task_summary") or {}).get(
                            "rollback_available_count", 0
                        )
                        if isinstance(
                            transaction_manifest.get("task_summary"), Mapping
                        )
                        else 0
                    ),
                    artifact=transaction_artifact,
                    report=transaction_report,
                )
            )
        for entry in list(repair_queue.get("entries", []) or [])[:50]:
            if not isinstance(entry, dict):
                continue
            profile_label = (
                entry.get("profile_name")
                or entry.get("profile_id")
                or "profile"
            )
            question_index = entry.get("question_index") or "-"
            target = (
                entry.get("repair_target_key")
                or entry.get("item_id")
                or entry.get("current_path")
                or "question_figure"
            )
            reference = (
                entry.get("comparison_display_name")
                or entry.get("comparison_reference")
                or "manual comparison"
            )
            region_summary = _clean_text(entry.get("region_summary"))
            region_text = f"; region={region_summary}" if region_summary else ""
            confirm_status = _clean_text(entry.get("confirmation_status")) or "blocked"
            lines.append(
                f"- {profile_label} / Q{question_index}: "
                f"{entry.get('action', 'review_question_figure_replacement')} -> "
                f"{target}; reference={reference}; confirmation=required; "
                f"auto_apply=false; confirm={confirm_status}{region_text}"
            )
    isolation = report_payload.get("batch_isolation", {})
    if isinstance(isolation, dict) and isolation:
        lines.extend(["", "## Batch Isolation"])
        lines.append(
            "- Total: {total}; success: {success}; warning: {warning}; failed: {failed}".format(
                total=isolation.get("total_count", 0),
                success=isolation.get("success_count", 0),
                warning=isolation.get("warning_count", 0),
                failed=isolation.get("failed_count", 0),
            )
        )
        for profile in list(isolation.get("profiles", []) or []):
            if not isinstance(profile, dict) or profile.get("status") == "success":
                continue
            label = profile.get("profile_name") or profile.get("profile_id") or "profile"
            lines.append(
                f"- {label}: {profile.get('status', 'failed')} -> {profile.get('summary', '')}"
            )
    lines.extend(["", "## Items"])
    for item in report_payload.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        label = item.get("profile_name") or item.get("profile_id") or "profile"
        lines.append(
            f"- {label}: {item.get('status', 'failed')} -> {item.get('output_path', '')}"
        )
        for diagnostic in item.get("material_diagnostics", []) or []:
            if not isinstance(diagnostic, dict):
                continue
            reason = str(diagnostic.get("reason") or "").strip()
            if reason:
                lines.append(f"  - material: {reason}")
    return "\n".join(lines)


def _batch_payload(
    status: str,
    results: list[dict[str, object]],
    *,
    error_text: str,
) -> dict[str, object]:
    report_paths: list[str] = []
    failed_count = 0
    diagnostics_count = 0
    diagnostics_summary_parts: list[str] = []
    material_diagnostics: list[dict] = []
    batch_issue_items: list[dict] = []
    material_manifest_paths: dict[str, str] = {}
    material_package_paths: dict[str, str] = {}
    for item in results:
        report_paths.extend(str(path) for path in item.get("report_paths", []) or [])
        failed_count += int(item.get("failed_count") or 0)
        diagnostics_count += int(item.get("diagnostics_count") or 0)
        material_diagnostics.extend(
            dict(diagnostic)
            for diagnostic in item.get("material_diagnostics", []) or []
            if isinstance(diagnostic, dict)
        )
        summary = str(item.get("diagnostics_summary") or "")
        if summary:
            diagnostics_summary_parts.append(summary)
        batch_issue_items.extend(_batch_issue_items_for_result(item))
        profile_key = str(
            item.get("profile_id") or item.get("profile_name") or len(material_manifest_paths) + 1
        )
        for manifest_key, manifest_path in _path_map(item.get("material_manifest_paths")).items():
            material_manifest_paths[f"{profile_key}:{manifest_key}"] = manifest_path
        for package_key, package_path in _path_map(item.get("material_package_paths")).items():
            material_package_paths[f"{profile_key}:{package_key}"] = package_path

    payload = {
        "status": status,
        "items": results,
        "output_paths": [str(item.get("output_path") or "") for item in results],
        "report_paths": report_paths,
        "material_manifest_paths": material_manifest_paths,
        "material_package_paths": material_package_paths,
        "material_diagnostics": material_diagnostics,
        "batch_issue_items": batch_issue_items,
        "failed_count": failed_count,
        "error_text": error_text,
        "diagnostics_count": diagnostics_count,
        "diagnostics_summary": "\n".join(diagnostics_summary_parts),
    }
    payload["batch_isolation"] = _batch_isolation_payload(
        status,
        results,
        batch_issue_items=batch_issue_items,
        error_text=error_text,
    )
    return payload


def _batch_isolation_payload(
    status: str,
    results: list[dict[str, object]],
    *,
    batch_issue_items: list[dict],
    error_text: str,
) -> dict[str, object]:
    issues_by_profile: dict[str, list[dict]] = {}
    for issue in batch_issue_items:
        if not isinstance(issue, dict):
            continue
        key = _batch_profile_key(issue)
        issues_by_profile.setdefault(key, []).append(issue)

    profiles: list[dict[str, object]] = []
    success_count = 0
    warning_count = 0
    failed_count = 0
    for index, item in enumerate(results, start=1):
        profile_id = str(item.get("profile_id") or "")
        profile_name = str(item.get("profile_name") or "")
        profile_key = _batch_profile_key(item) or str(index)
        item_status = str(item.get("status") or "failed")
        profile_issues = issues_by_profile.get(profile_key, [])
        missing_fields = _unique_manifest_values(
            field
            for issue in profile_issues
            for field in list(issue.get("missing_field_keys") or [])
        )
        missing_assets = _unique_manifest_values(
            asset
            for issue in profile_issues
            for asset in list(issue.get("missing_asset_roles") or [])
        )
        if item_status == "success":
            success_count += 1
        elif item_status == "partial_success":
            warning_count += 1
        else:
            failed_count += 1
        profiles.append(
            {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": item_status,
                "output_dir": str(item.get("output_dir") or ""),
                "output_path": str(item.get("output_path") or ""),
                "report_paths": [str(path) for path in list(item.get("report_paths") or [])],
                "material_manifest_paths": _path_map(item.get("material_manifest_paths")),
                "material_package_paths": _path_map(item.get("material_package_paths")),
                "issue_count": len(profile_issues),
                "missing_field_keys": list(missing_fields),
                "missing_asset_roles": list(missing_assets),
                "repair_targets": [
                    {
                        "type": str(issue.get("repair_target_type") or ""),
                        "key": str(issue.get("repair_target_key") or ""),
                    }
                    for issue in profile_issues
                    if str(issue.get("repair_target_type") or "").strip()
                    and str(issue.get("repair_target_key") or "").strip()
                ],
                "summary": _batch_profile_summary(item, profile_issues),
            }
        )

    return {
        "kind": "batch_failure_isolation",
        "status": status,
        "total_count": len(results),
        "success_count": success_count,
        "warning_count": warning_count,
        "failed_count": failed_count,
        "error_text": str(error_text or ""),
        "profiles": profiles,
        "successful_profiles": [
            profile for profile in profiles if profile.get("status") == "success"
        ],
        "warning_profiles": [
            profile for profile in profiles if profile.get("status") == "partial_success"
        ],
        "failed_profiles": [
            profile
            for profile in profiles
            if profile.get("status") not in {"success", "partial_success"}
        ],
    }


def _batch_profile_key(value: dict[str, object]) -> str:
    return str(value.get("profile_id") or value.get("profile_name") or "").strip()


def _batch_profile_summary(
    item: dict[str, object],
    profile_issues: list[dict],
) -> str:
    if profile_issues:
        return "; ".join(
            str(issue.get("summary") or issue.get("kind") or "issue")
            for issue in profile_issues
        )
    return str(item.get("error_text") or item.get("diagnostics_summary") or "")


def _batch_issue_items_for_result(item: dict[str, object]) -> list[dict[str, object]]:
    profile_id = str(item.get("profile_id") or "")
    profile_name = str(item.get("profile_name") or "")
    status = str(item.get("status") or "failed")
    issues: list[dict[str, object]] = []
    for index, diagnostic in enumerate(list(item.get("material_diagnostics") or []), start=1):
        if not isinstance(diagnostic, dict):
            continue
        missing_fields = [
            str(value)
            for value in list(diagnostic.get("missing_field_keys") or [])
            if str(value or "").strip()
        ]
        missing_assets = [
            str(value)
            for value in list(diagnostic.get("missing_asset_roles") or [])
            if str(value or "").strip()
        ]
        suspicious_asset_items = list(diagnostic.get("suspicious_asset_items") or [])
        comparison_issue_items = list(diagnostic.get("comparison_issue_items") or [])
        kind = str(diagnostic.get("change_type") or "material_diagnostic")
        parameter_paths = [
            str(value).strip()
            for value in list(diagnostic.get("parameter_paths") or [])
            if str(value or "").strip()
        ]
        parameter_path = str(
            diagnostic.get("parameter_path") or diagnostic.get("field_id") or ""
        ).strip()
        if parameter_path and parameter_path not in parameter_paths:
            parameter_paths.insert(0, parameter_path)
        repair_target_type = str(diagnostic.get("repair_target_type") or "").strip()
        repair_target_key = str(diagnostic.get("repair_target_key") or "").strip()
        if not repair_target_type:
            repair_target_type = "field" if missing_fields else "asset" if missing_assets else ""
        if not repair_target_key:
            repair_target_key = (
                missing_fields[0]
                if missing_fields
                else missing_assets[0]
                if missing_assets
                else ""
            )
        issues.append(
            {
                "issue_id": _batch_issue_id(profile_id, profile_name, kind, index),
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": status,
                "category": "material",
                "kind": kind,
                "severity": str(diagnostic.get("level") or "warning"),
                "summary": str(diagnostic.get("reason") or kind),
                "missing_field_keys": missing_fields,
                "missing_asset_roles": missing_assets,
                "missing_asset_items": list(diagnostic.get("missing_asset_items") or []),
                "suspicious_asset_items": suspicious_asset_items,
                "comparison_issue_items": comparison_issue_items,
                "parameter_paths": parameter_paths,
                "repair_target_type": repair_target_type,
                "repair_target_key": repair_target_key,
            }
        )
    if status not in {"success", "partial_success"} and not issues:
        error_text = str(item.get("error_text") or "").strip()
        issues.append(
            {
                "issue_id": _batch_issue_id(profile_id, profile_name, "execution_failed", 1),
                "profile_id": profile_id,
                "profile_name": profile_name,
                "status": status,
                "category": "execution",
                "kind": "execution_failed",
                "severity": "error",
                "summary": error_text or "Batch item failed",
                "missing_field_keys": [],
                "missing_asset_roles": [],
                "repair_target_type": "",
                "repair_target_key": "",
            }
        )
    return issues


def _batch_issue_id(profile_id: str, profile_name: str, kind: str, index: int) -> str:
    profile_key = profile_id or profile_name or "profile"
    safe_profile = re.sub(r"[^A-Za-z0-9_\-]+", "_", profile_key).strip("_") or "profile"
    safe_kind = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(kind or "issue")).strip("_") or "issue"
    return f"batch:{safe_profile}:{safe_kind}:{index}"


def _delivery_target_groups(scene: SceneWorkspace) -> list[tuple[str, list]]:
    presets = list(getattr(scene, "delivery_presets", []) or [])
    if not presets:
        return []

    base_template_id = _scene_current_template_id(scene)
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


def _scene_current_template_id(scene: SceneWorkspace) -> str:
    for attr_name in ("template_id", "default_template_id"):
        value = str(getattr(scene, attr_name, "") or "").strip()
        if value:
            return value
    for value in list(getattr(scene, "compatible_template_ids", []) or []):
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _load_delivery_template(
    current_template: TemplateConfig,
    *,
    scene: SceneWorkspace,
    target_template_id: str,
) -> TemplateConfig:
    normalized_id = str(target_template_id or "").strip()
    if not normalized_id or normalized_id == _scene_current_template_id(scene):
        return current_template
    return load_template_from_library(normalized_id)


def _scene_for_delivery_presets(scene: SceneWorkspace, presets: list) -> SceneWorkspace:
    target_scene = copy.deepcopy(scene)
    target_scene.delivery_presets = [copy.deepcopy(preset) for preset in presets]
    preset_ids = [
        str(getattr(preset, "preset_id", "") or "").strip()
        for preset in target_scene.delivery_presets
    ]
    default_id = str(getattr(target_scene, "default_delivery_preset_id", "") or "").strip()
    if default_id not in preset_ids:
        target_scene.default_delivery_preset_id = next(
            (preset_id for preset_id in preset_ids if preset_id),
            "final",
        )
    return target_scene


def _aggregate_delivery_status(statuses: list[str]) -> str:
    normalized = [str(status or "failed") for status in statuses]
    if not normalized:
        return "failed"
    if all(status == "success" for status in normalized):
        return "success"
    if any(status in {"success", "partial_success"} for status in normalized):
        return "partial_success"
    return "failed"


def _uses_delivery_presets(config) -> bool:
    return _should_force_delivery_presets(config)


def _should_force_delivery_presets(config) -> bool:
    presets = list(getattr(config, "delivery_presets", []) or [])
    if len(presets) > 1:
        return True
    if len(presets) != 1:
        return False

    preset = presets[0]
    preset_id = str(getattr(preset, "preset_id", "") or "").strip()
    default_id = str(getattr(config, "default_delivery_preset_id", "") or "").strip()
    if preset_id and preset_id != "final":
        return True
    if default_id and default_id != "final":
        return True

    output_dir_template = str(
        getattr(preset, "output_dir_template", "") or ""
    ).strip()
    if output_dir_template and output_dir_template != "{document_dir}/output":
        return True

    filename_template = str(getattr(preset, "filename_template", "") or "").strip()
    if filename_template and filename_template != "{stem}_{preset_id}":
        return True

    return False


def _primary_output_path(config, output_paths: dict[str, str]) -> str:
    default_id = str(getattr(config, "default_delivery_preset_id", "") or "").strip()
    return _primary_output_path_for_default(default_id, output_paths)


def _primary_output_path_for_default(
    default_id: str,
    output_paths: dict[str, str],
) -> str:
    if default_id and output_paths.get(default_id):
        return output_paths[default_id]
    if output_paths.get("final"):
        return output_paths["final"]
    return next(iter(output_paths.values()), "")


def _write_compare_docx_artifacts(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
) -> dict[str, str]:
    compare_paths: dict[str, str] = {}
    for preset in list(getattr(config, "delivery_presets", []) or []):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue

        artifacts = getattr(preset, "artifacts", None)
        if not bool(getattr(artifacts, "compare_docx", False)):
            continue

        revised_path = _preset_output_path(
            preset_id=preset_id,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
        )
        if not revised_path:
            continue
        revised = Path(revised_path)
        if not revised.exists():
            continue

        compare_dir = _delivery_report_dir(output_dir, input_path, preset)
        compare_dir.mkdir(parents=True, exist_ok=True)
        compare_path = compare_dir / f"{_delivery_report_stem(input_path, preset)}_compare.docx"
        write_compare_docx(
            input_path,
            revised,
            compare_path,
            compare_text=bool(getattr(artifacts, "compare_text", True)),
            compare_formatting=bool(getattr(artifacts, "compare_formatting", True)),
        )
        compare_paths[preset_id] = str(compare_path)
    return compare_paths


def _write_structured_intermediates(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> dict[str, str]:
    intermediate_paths: dict[str, str] = {}
    for preset in list(getattr(config, "delivery_presets", []) or []):
        if not bool(getattr(preset, "include_structured_intermediate", False)):
            continue
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue

        artifact_dir = _delivery_report_dir(output_dir, input_path, preset)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{_delivery_report_stem(input_path, preset)}_intermediate.json"
        output_path = _preset_output_path(
            preset_id=preset_id,
            output_paths=output_paths,
            fallback_output_path=fallback_output_path,
            config=config,
        )
        payload = _structured_intermediate_payload(
            result,
            input_path=input_path,
            output_path=output_path,
            preset=preset,
            config=config,
            elapsed=elapsed,
            modules_enabled=modules_enabled,
            modules_total=modules_total,
        )
        artifact_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        intermediate_paths[preset_id] = str(artifact_path)
    return intermediate_paths


def _preset_output_path(
    *,
    preset_id: str,
    output_paths: dict[str, str],
    fallback_output_path: str,
    config,
) -> str:
    direct = str(output_paths.get(preset_id) or "")
    if direct:
        return direct

    default_id = str(getattr(config, "default_delivery_preset_id", "") or "").strip()
    if preset_id == default_id:
        return str(fallback_output_path or "")

    presets = list(getattr(config, "delivery_presets", []) or [])
    if len(presets) == 1:
        return str(fallback_output_path or "")

    return ""


def _structured_intermediate_payload(
    result,
    *,
    input_path: Path,
    output_path: str,
    preset,
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
) -> dict[str, object]:
    diagnostics = build_execution_diagnostics(result)
    return {
        "kind": "delivery_structured_intermediate",
        "schema_version": 1,
        "input": str(input_path),
        "output": str(output_path or ""),
        "status": str(getattr(result, "status", "failed") or "failed"),
        "elapsed_seconds": round(elapsed, 2),
        "modules_enabled": modules_enabled,
        "modules_total": modules_total,
        "preset": _delivery_preset_payload(preset),
        "diagnostics": {
            "count": diagnostics["count"],
            "items": diagnostics["items"],
        },
        "counts": _extract_count_result(result),
        "changes": _extract_change_records(result),
        "runtime_inputs": _runtime_inputs_payload(config),
        "context": _pipeline_context_payload(getattr(result, "context", None)),
        "failed_items": list(getattr(result, "failed_items", []) or []),
    }


def _delivery_preset_payload(preset) -> dict[str, object]:
    return {
        "preset_id": str(getattr(preset, "preset_id", "") or ""),
        "label": str(getattr(preset, "label", "") or ""),
        "display_label": delivery_preset_display_name(preset),
        "target_template_id": str(getattr(preset, "target_template_id", "") or ""),
        "output_dir_template": str(getattr(preset, "output_dir_template", "") or ""),
        "filename_template": str(getattr(preset, "filename_template", "") or ""),
        "artifacts": _plain_data(getattr(preset, "artifacts", None)),
        "content_visibility_rules": _plain_data(
            list(getattr(preset, "content_visibility_rules", []) or [])
        ),
        "include_structured_intermediate": bool(
            getattr(preset, "include_structured_intermediate", False)
        ),
        "report_level": str(getattr(preset, "report_level", "") or ""),
    }


def _runtime_inputs_payload(config) -> dict[str, object]:
    return {
        "entity_data": dict(getattr(config, "entity_data", {}) or {}),
        "entity_assets_dir": str(getattr(config, "entity_assets_dir", "") or ""),
        "images": _plain_data(list(getattr(config, "images", []) or [])),
        "replacements": _plain_data(list(getattr(config, "replacements", []) or [])),
    }


def _pipeline_context_payload(context) -> dict[str, object]:
    if context is None:
        return {}
    return {
        "source_doc_path": str(getattr(context, "source_doc_path", "") or ""),
        "source_doc_dir": str(getattr(context, "source_doc_dir", "") or ""),
        "entity_values": dict(getattr(context, "entity_values", None) or {}),
        "source_values": dict(getattr(context, "source_values", None) or {}),
        "exam_question_schema": _plain_data(
            getattr(context, "exam_question_schema", None)
        ),
        "journal_rule_source_governance": _plain_data(
            getattr(context, "journal_rule_source_governance", None)
        ),
        "journal_citations": _plain_data(
            getattr(context, "journal_citations", None)
        ),
        "journal_submission_package": _plain_data(
            getattr(context, "journal_submission_package", None)
        ),
        "official_numbering_preservation": _plain_data(
            getattr(context, "official_numbering_preservation", None)
        ),
        "technical_chapter_inventory": _plain_data(
            getattr(context, "technical_chapter_inventory", None)
        ),
        "application_section_word_limits": _plain_data(
            getattr(context, "application_section_word_limits", None)
        ),
        "inserted_images": _plain_data(getattr(context, "inserted_images", None) or []),
    }


def _extract_change_records(result) -> list[dict[str, object]]:
    tracker = getattr(result, "tracker", None)
    if tracker is None:
        return []
    return [
        {
            "rule_name": getattr(record, "rule_name", ""),
            "target": getattr(record, "target", ""),
            "section": getattr(record, "section", ""),
            "change_type": getattr(record, "change_type", ""),
            "before": getattr(record, "before", ""),
            "after": getattr(record, "after", ""),
            "paragraph_index": getattr(record, "paragraph_index", -1),
            "success": bool(getattr(record, "success", True)),
            "failure_reason": getattr(record, "failure_reason", None),
        }
        for record in tracker.get_all()
    ]


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


def _plain_data(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _plain_data(asdict(value))
    if isinstance(value, dict):
        return {str(key): _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    return value


def _write_delivery_reports(
    result,
    *,
    input_path: Path,
    output_dir: Path,
    output_paths: dict[str, str],
    config,
    elapsed: float,
    modules_enabled: int,
    modules_total: int,
    material_diagnostics: list[dict] | None = None,
    material_context: MaterialExecutionContext | None = None,
    style_source_summary: dict[str, object] | None = None,
) -> list[str]:
    _ = material_context
    report_paths: list[str] = []
    for preset in list(getattr(config, "delivery_presets", []) or []):
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if not preset_id:
            continue
        artifacts = getattr(preset, "artifacts", None)
        output_path = output_paths.get(preset_id, "")
        output_report_path = Path(output_path) if output_path else None
        preset_payload = _delivery_preset_payload(preset)
        report_stem = _delivery_report_stem(input_path, preset)
        report_dir = _delivery_report_dir(output_dir, input_path, preset)
        report_dir.mkdir(parents=True, exist_ok=True)

        if bool(getattr(artifacts, "report_json", False)):
            report_json = report_dir / f"{report_stem}_changes.json"
            write_json_report(
                result,
                input_path=input_path,
                output_path=output_report_path,
                report_path=report_json,
                elapsed=elapsed,
                modules_enabled=modules_enabled,
                modules_total=modules_total,
                extra_diagnostics=list(material_diagnostics or []),
                style_source_summary=style_source_summary,
                delivery_preset=preset_payload,
            )
            report_paths.append(str(report_json))

        if bool(getattr(artifacts, "report_markdown", False)):
            report_md = report_dir / f"{report_stem}_changes.md"
            write_markdown_report(
                result,
                input_path=input_path,
                output_path=output_report_path,
                report_path=report_md,
                elapsed=elapsed,
                modules_enabled=modules_enabled,
                modules_total=modules_total,
                extra_diagnostics=list(material_diagnostics or []),
                style_source_summary=style_source_summary,
                delivery_preset=preset_payload,
            )
            report_paths.append(str(report_md))
    return report_paths


class _SafeReportFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _delivery_report_stem(input_path: Path, preset) -> str:
    template = str(getattr(preset, "filename_template", "") or "").strip()
    if not template:
        template = "{stem}_{preset_id}"
    rendered = template.format_map(
        _SafeReportFormatDict(
            {
                "document_dir": str(input_path.parent),
                "output_dir": "",
                "stem": input_path.stem,
                "suffix": input_path.suffix or ".docx",
                "preset_id": str(getattr(preset, "preset_id", "") or ""),
                "preset_label": delivery_preset_display_name(preset),
            }
        )
    )
    return Path(rendered).stem or f"{input_path.stem}_{getattr(preset, 'preset_id', 'final')}"


def _delivery_report_dir(base_output_dir: Path, input_path: Path, preset) -> Path:
    template = str(getattr(preset, "output_dir_template", "") or "").strip()
    if not template or template == "{document_dir}/output":
        return base_output_dir
    rendered = template.format_map(
        _SafeReportFormatDict(
            {
                "document_dir": str(input_path.parent),
                "output_dir": str(base_output_dir),
                "stem": input_path.stem,
                "suffix": input_path.suffix or ".docx",
                "preset_id": str(getattr(preset, "preset_id", "") or ""),
                "preset_label": delivery_preset_display_name(preset),
            }
        )
    )
    path = Path(rendered)
    return path if path.is_absolute() else base_output_dir / path


class ThreadedExecutionHandle(QObject):
    """Run an ExecutionWorker on a dedicated QThread."""

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal()
    execution_finished = Signal()

    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._thread = QThread(self)

        self._worker.progress_changed.connect(self.progress_changed.emit)
        self._worker.execution_started.connect(self.execution_started.emit)
        self._worker.execution_succeeded.connect(self.execution_succeeded.emit)
        self._worker.execution_partial.connect(self.execution_partial.emit)
        self._worker.execution_failed.connect(self.execution_failed.emit)
        self._worker.execution_cancelled.connect(self.execution_cancelled.emit)
        self._worker.execution_finished.connect(self.execution_finished.emit)

        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.execution_finished.connect(self._thread.quit)

        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self.deleteLater)

    def start(self) -> None:
        self._thread.start()

    def request_cancel(self) -> None:
        self._worker.request_cancel()

    def shutdown(self, timeout_ms: int | None = 1000) -> None:
        try:
            self.request_cancel()
        except Exception as exc:
            log_best_effort_shutdown_failure("execution thread handle", "request_cancel", exc)

        thread = getattr(self, "_thread", None)
        if thread is None:
            return

        is_running = getattr(thread, "isRunning", None)
        try:
            running = bool(is_running()) if callable(is_running) else True
        except Exception as exc:
            log_best_effort_shutdown_failure("execution thread handle", "thread.isRunning", exc)
            running = True

        if not running:
            return

        quit_thread = getattr(thread, "quit", None)
        if callable(quit_thread):
            try:
                quit_thread()
            except Exception as exc:
                log_best_effort_shutdown_failure("execution thread handle", "thread.quit", exc)

        wait_thread = getattr(thread, "wait", None)
        if callable(wait_thread):
            try:
                if timeout_ms is None:
                    wait_thread()
                else:
                    wait_thread(int(timeout_ms))
            except TypeError:
                try:
                    wait_thread()
                except Exception as exc:
                    log_best_effort_shutdown_failure("execution thread handle", "thread.wait", exc)
            except Exception as exc:
                log_best_effort_shutdown_failure("execution thread handle", "thread.wait", exc)


__all__ = ["ThreadedExecutionHandle", "WorkbenchBatchProductionRunner", "WorkbenchProductionRunner"]
