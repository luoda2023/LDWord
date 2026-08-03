"""Qt-free production runner consuming only a frozen material snapshot."""

from __future__ import annotations

import copy
import time
from pathlib import Path

from src.application.materials import ExecutionMaterialSnapshot
from src.config.master_library import default_master, get_master
from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)
from src.config.template import TemplateConfig
from src.modules.registry import create_all_modules
from src.pipeline.module_selection import build_module_selection_plan
from src.pipeline.runner import Pipeline, pipeline_terminal_assembly_owner
from src.services.artifact_failure import apply_artifact_failures
from src.services.delivery_template_validation import (
    unsupported_delivery_target_template_issue,
)
from src.services.exam_markdown_source import load_exam_markdown_source
from src.services.material_delivery import DeliveryPackageBuildError
from src.services.official_draft_source import load_official_draft_source
from src.services.production_runtime import formatting_runtime
from src.services.production_runtime.delivery_reporting import (
    finalize_result_artifacts,
    primary_output_path,
    should_force_delivery_presets,
)
from src.services.production_runtime.material_artifacts import material_artifact_payload
from src.services.production_runtime.material_only_delivery import (
    run_material_only_delivery,
)
from src.services.production_runtime.result_projection import (
    apply_official_draft_evidence,
    project_pipeline_result_evidence,
)
from src.shared.engine.exam_question_schema import (
    build_exam_delivery_runtime,
    exam_delivery_filename_stem,
    exam_markdown_import_entity_data,
    inspect_exam_question_schema,
)


class WorkbenchProductionRunner:
    """Internal low-level runner for one already-bound source."""

    def __init__(
        self,
        *,
        doc_path: str,
        template: TemplateConfig,
        scene: SceneWorkspace,
        session_overrides: dict[str, object] | None = None,
        material_snapshot: ExecutionMaterialSnapshot | None = None,
        output_dir: str | Path | None = None,
        output_suffix: str = "_formatted",
        document_type_id: str = "",
        exam_scale_profile_id: str = "",
        exam_visual_quality_required: bool = False,
        require_format_change: bool = False,
        document_scope_context=(None, ()),
    ) -> None:
        self.doc_path = str(doc_path)
        self._template = copy.deepcopy(template)
        self._scene = copy.deepcopy(scene)
        self._session_overrides = dict(session_overrides or {})
        if material_snapshot is not None and not isinstance(
            material_snapshot,
            ExecutionMaterialSnapshot,
        ):
            raise TypeError("execution_material_snapshot_type_invalid")
        self._material_snapshot = material_snapshot
        self._output_dir = Path(output_dir) if output_dir is not None else None
        self._output_suffix = str(output_suffix or "_formatted")
        self._document_type_id = str(document_type_id or "").strip()
        self._exam_scale_profile_id = str(exam_scale_profile_id or "").strip()
        self._exam_visual_quality_required = bool(exam_visual_quality_required)
        self._require_format_change = bool(require_format_change)
        self._document_scope_context = document_scope_context

    def run(self, progress_cb, cancel_check) -> dict[str, object]:
        input_path = Path(self.doc_path)
        if not input_path.is_file():
            return _failed(f"input_document_missing:{input_path}")
        suffix = input_path.suffix.casefold()
        exam_markdown = suffix in {".md", ".markdown"} and scene_uses_exam_paper_surface(
            self._scene
        )
        official_draft = suffix == ".json" and scene_uses_official_document_surface(
            self._scene
        )
        if suffix != ".docx" and not exam_markdown and not official_draft:
            return _failed(f"input_document_unsupported:{input_path.suffix}")
        if cancel_check():
            return _cancelled()
        if unsupported_target := unsupported_delivery_target_template_issue(self._scene):
            return _failed(unsupported_target)
        snapshot = self._material_snapshot
        if snapshot is not None:
            if snapshot.work_mode_id != str(self._scene.mode_id or "").strip():
                return _failed("execution_material_mode_mismatch")
            if len(snapshot.records) > 1:
                return _failed("single_document_execution_requires_one_material_record")
        record = snapshot.records[0] if snapshot and snapshot.records else None
        material_values = dict(record.field_values) if record is not None else {}
        material_owners = dict(record.field_owners) if record is not None else {}
        values: dict[str, object] = {}
        owners: dict[str, str] = {}
        working_input_path = input_path
        prepared_input = formatting_runtime.PreparedFormattingInput(path=input_path)
        official_source = None
        if official_draft:
            try:
                official_source = load_official_draft_source(input_path)
            except (OSError, TypeError, ValueError) as exc:
                return _failed(f"official_draft_source_invalid:{type(exc).__name__}")
            if official_source.missing_user_fields:
                return _failed(
                    "official_draft_missing_required_fields:"
                    + ",".join(official_source.missing_user_fields)
                )
            if (
                self._document_type_id
                and official_source.document_type_id != self._document_type_id
            ):
                return _failed("official_draft_document_type_mismatch")
            preview_path = Path(official_source.preview_docx_path)
            try:
                resolved_preview = preview_path.expanduser().resolve(strict=True)
                resolved_source_parent = input_path.resolve().parent
            except OSError:
                return _failed("official_draft_preview_missing")
            if (
                resolved_preview.suffix.casefold() != ".docx"
                or resolved_preview.parent != resolved_source_parent
            ):
                return _failed("official_draft_preview_path_invalid")
            working_input_path = resolved_preview
            values.update(official_source.fields)
            owners.update({key: "run" for key in official_source.fields})
        values.update(material_values)
        owners.update(material_owners)
        import_result = None
        if exam_markdown:
            try:
                import_result = load_exam_markdown_source(input_path)
            except (OSError, UnicodeError, ValueError) as exc:
                return _failed(f"exam_markdown_source_invalid:{type(exc).__name__}")
            if import_result.error_count:
                issue_codes = ",".join(
                    dict.fromkeys(
                        str(issue.kind or "unknown")
                        for issue in import_result.issues
                        if str(issue.severity or "").casefold() == "error"
                    )
                )
                return _failed(
                    f"exam_markdown_source_invalid:{issue_codes or 'parse_error'}"
                )
            values = {
                **exam_markdown_import_entity_data(import_result),
                **values,
            }
        try:
            config = resolve_config(
                self._template,
                self._scene,
                self._session_overrides,
                entity_data=values,
                field_scopes=owners,
                exact_material_placeholders=True,
            )
            modules = create_all_modules()
            material_only = run_material_only_delivery(
                config=config,
                input_path=input_path,
                output_dir=self._output_dir or input_path.parent,
                material_snapshot=snapshot,
                modules_total=len(modules),
                progress_cb=progress_cb,
                cancel_check=cancel_check,
            )
            if material_only is not None:
                return material_only
            terminal_owner = pipeline_terminal_assembly_owner(config)
            selection = build_module_selection_plan(
                modules,
                formatting_runtime.production_module_selector(config, record),
            )
            enabled = [] if terminal_owner else list(selection.select_modules(modules))
            official_master = None
            exam_master = None
            if terminal_owner == "official":
                official_master = (
                    get_master(self._scene.master_id, "official")
                    if self._scene.master_id
                    else None
                ) or default_master("official")
            elif terminal_owner == "exam":
                exam_master = (
                    get_master(
                        self._scene.master_id,
                        "exam",
                        exam_config=self._scene.exam_paper,
                    )
                    if self._scene.master_id
                    else None
                ) or default_master(
                    "exam",
                    exam_config=self._scene.exam_paper,
                )
            if exam_markdown:
                if terminal_owner != "exam":
                    return _failed(
                        f"exam_markdown_terminal_owner_invalid:{terminal_owner or 'none'}"
                    )
                progress_cb(0, 3, "解析并校验 Markdown 题稿")
                validation = inspect_exam_question_schema(config)
                if validation.error_count:
                    issue_codes = ",".join(
                        dict.fromkeys(
                            str(issue.kind or "unknown")
                            for issue in validation.issues
                            if str(issue.severity or "").casefold() == "error"
                        )
                    )
                    return _failed(
                        f"exam_question_schema_invalid:{issue_codes or 'validation_error'}"
                    )
                if cancel_check():
                    return _cancelled()
                progress_cb(1, 3, "生成学生卷和答案卷")
                started = time.perf_counter()
                runtime = build_exam_delivery_runtime(
                    config,
                    output_dir=self._output_dir or input_path.parent,
                    source_stem=exam_delivery_filename_stem(
                        payload=import_result.payload,
                        fallback=input_path.stem,
                    ),
                    validation=validation,
                    master=exam_master,
                    exam_scene_id=self._scene.scene_id,
                    exam_scale_profile_id=self._exam_scale_profile_id,
                    verify_visual_quality=self._exam_visual_quality_required,
                )
                elapsed = time.perf_counter() - started
                output_paths = {
                    str(version.preset_id): str(version.docx_path)
                    for version in runtime.rendered_versions
                    if str(version.preset_id or "").strip()
                    and str(version.docx_path or "").strip()
                }
                if runtime.status not in {"ok", "warning"} or not output_paths:
                    blocked = _failed(
                        "exam_delivery_runtime_blocked:"
                        f"{runtime.skipped_reason or runtime.status}"
                    )
                    blocked["exam_delivery_runtime"] = runtime.to_dict()
                    return blocked
                progress_cb(3, 3, "Completed")
                primary = next(iter(output_paths.values()), "")
                quality_needs_review = runtime.status == "warning" or (
                    runtime.quality_status
                    in {"quality_unverified", "quality_review_required"}
                )
                quality_summary = {
                    "quality_ok": "视觉质量验收通过",
                    "quality_unverified": "视觉质量尚未验证",
                    "quality_review_required": ("候选版已生成，视觉质量需要人工审阅"),
                    "not_checked": "未执行视觉质量验收",
                }.get(
                    runtime.quality_status,
                    f"视觉质量状态：{runtime.quality_status or '未知'}",
                )
                report_paths = [
                    path
                    for path in (
                        runtime.markdown_preview_path,
                        runtime.quality_manifest_path,
                    )
                    if path
                ]
                payload = {
                    "status": (
                        "partial_success" if quality_needs_review else "success"
                    ),
                    "summary": (
                        f"执行完成，共发布 {len(output_paths)} 个试卷文件；"
                        + quality_summary
                    ),
                    "output_path": primary,
                    "output_paths": output_paths,
                    "report_paths": report_paths,
                    "failed_count": 0,
                    "artifact_failure_count": 0,
                    "error_text": "",
                    "elapsed_seconds": elapsed,
                    "modules_enabled": 0,
                    "modules_total": len(modules),
                    "exam_markdown_import": import_result.to_dict(),
                    "exam_question_schema": validation.to_dict(),
                    "exam_delivery_runtime": runtime.to_dict(),
                    "release_tier": runtime.release_tier,
                    "execution_material_snapshot_id": (
                        snapshot.snapshot_id if snapshot is not None else ""
                    ),
                }
                payload.update(
                    material_artifact_payload(
                        input_path=input_path,
                        output_dir=self._output_dir or input_path.parent,
                        config=config,
                        material_snapshot=snapshot,
                        output_paths=output_paths,
                        report_paths=report_paths,
                    )
                )
                return payload
            prepared_input = formatting_runtime.prepare_formatting_input(
                working_input_path,
                snapshot=snapshot,
                record=record,
                output_dir=self._output_dir or input_path.parent,
            )
            working_input_path = prepared_input.path
            started = time.perf_counter()
            pipeline = Pipeline(
                modules=enabled,
                config=config,
                output_dir=str(self._output_dir) if self._output_dir else None,
                output_suffix=self._output_suffix,
                progress_callback=progress_cb,
                cancel_check=cancel_check,
                force_delivery_presets=should_force_delivery_presets(config),
                official_master=official_master,
                exam_master=exam_master,
                official_document_type_id=self._document_type_id,
                **formatting_runtime.document_scope_pipeline_kwargs(self._document_scope_context, working_input_path if snapshot is not None else None),
            )
            result = pipeline.execute(str(working_input_path))
            elapsed = time.perf_counter() - started
        except (DeliveryPackageBuildError, OSError, TypeError, ValueError) as exc:
            prepared_input.cleanup()
            return _failed(f"{type(exc).__name__}: {exc}")

        status = str(getattr(result, "status", "") or "")
        if getattr(result, "cancelled", False) or status == "cancelled":
            prepared_input.cleanup()
            return _cancelled()
        output_paths = {
            str(key): str(value)
            for key, value in dict(getattr(result, "output_paths", {}) or {}).items()
        }
        primary = primary_output_path(config, output_paths)
        format_change_evidence = formatting_runtime.collect_format_change_evidence(prepared_input.path, primary)
        prepared_input.cleanup()
        artifacts = finalize_result_artifacts(
            result,
            input_path=input_path,
            output_dir=self._output_dir or input_path.parent,
            output_paths=output_paths,
            fallback_output_path=primary,
            config=config,
            elapsed=elapsed,
            modules_enabled=len(enabled),
            modules_total=len(modules),
            material_snapshot=snapshot,
        )
        if not bool(getattr(result, "success", False)):
            payload = _failed(str(getattr(result, "error", "") or "pipeline_failed"))
            payload.update(project_pipeline_result_evidence(result))
            payload["format_change_evidence"] = format_change_evidence
            payload.update(artifacts.to_payload())
            apply_artifact_failures(payload, artifacts.artifact_failures)
            return payload
        payload = {
            "status": status or "success",
            "summary": f"执行完成，共发布 {len(output_paths)} 个交付文件",
            "output_path": primary,
            "output_paths": output_paths,
            "report_paths": [],
            "failed_count": 0,
            "artifact_failure_count": 0,
            "error_text": "",
            "elapsed_seconds": elapsed,
            "modules_enabled": len(enabled),
            "modules_total": len(modules),
            "execution_material_snapshot_id": (
                snapshot.snapshot_id if snapshot is not None else ""
            ),
            "materialized_resource_count": prepared_input.materialized_resource_count,
            "format_change_evidence": format_change_evidence,
        }
        payload.update(project_pipeline_result_evidence(result))
        payload.update(artifacts.to_payload())
        apply_official_draft_evidence(payload, official_source)
        apply_artifact_failures(payload, artifacts.artifact_failures)
        formatting_runtime.apply_required_format_change_policy(
            payload,
            format_change_evidence,
            required=self._require_format_change,
        )
        return payload


def _failed(message: str) -> dict[str, object]:
    return {
        "status": "failed",
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "failed_count": 1,
        "artifact_failure_count": 0,
        "error_text": str(message),
    }


def _cancelled() -> dict[str, object]:
    payload = _failed("execution_cancelled")
    payload.update(status="cancelled", failed_count=0)
    return payload


__all__: list[str] = []
