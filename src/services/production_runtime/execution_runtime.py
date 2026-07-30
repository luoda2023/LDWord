from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path

from src.config.entity import EntityArchive
from src.services.execution_session import (
    ExecutionSessionSnapshot,
    execution_session_frozen_input_path,
    execution_session_frozen_master,
    execution_session_frozen_official_master,
    execution_value_revision,
    validate_ready_session_bindings,
)
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    RegionDecision,
    build_document_structure_evidence,
)
from src.config.master_library import get_master
from src.config.material_context import MaterialExecutionContext
from src.config.official_document_profiles import (
    resolve_official_batch_document_type_id,
)
from src.config.resolver import resolve_config, resolve_template_baseline
from src.config.document_scope import document_scope_policy_issue
from src.config.scene import SceneWorkspace
from src.config.style_source_report_summary import build_style_source_report_summary
from src.config.template import TemplateConfig
from src.modules.registry import create_all_modules
from src.pipeline.context import PipelineContext
from src.pipeline.module_selection import build_module_selection_plan
from src.pipeline.result import PipelineResult
from src.pipeline.runner import (
    Pipeline,
    pipeline_terminal_assembly_owner,
)
from src.reporting.execution_payload import (
    diagnostics_payload,
)
from src.shared.engine.exam_question_schema import (
    build_exam_delivery_runtime,
    inspect_exam_question_schema,
)
from src.shared.engine.official_document_assembly import assemble_official_document_docx
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)

from .delivery_reporting import (
    should_force_delivery_presets,
)
from .delivery_runtime import (
    delivery_target_groups,
    mode_id_for_scene,
    run_delivery_target_groups,
)
from src.services.artifact_failure import (
    apply_artifact_failures as _apply_artifact_failures,
)
from .exam_question_assets import material_context_with_exam_question_assets
from .exam_markdown_execution_input import (
    PreparedExamMarkdownInput,
    is_exam_markdown_input as _prepared_is_exam_markdown_input,
    prepare_exam_markdown_input,
    validated_prepared_exam_markdown_input,
)
from .material_preflight import (
    material_preflight_error_text,
    material_requirement_diagnostics,
)
from .material_assembly_runtime import (
    material_assembly_is_active,
    run_workbench_material_assembly,
)
from .material_preflight_reporting import (
    attach_material_preflight_reports as _attach_material_preflight_reports,
)
from .execution_preflight import (
    document_scope_diagnostic,
    prepare_document_material_preflight,
)
from .result_projection import project_execution_result


def _lazy_optional_function(module_name: str, function_name: str):
    def call(*args, **kwargs):
        function = getattr(import_module(module_name), function_name)
        return function(*args, **kwargs)

    return call


official_document_batch_exception_payload = _lazy_optional_function(
    "src.reporting.official_batch_payload",
    "official_document_batch_exception_payload",
)
official_document_batch_item_payload = _lazy_optional_function(
    "src.reporting.official_batch_payload",
    "official_document_batch_item_payload",
)
official_document_batch_preflight_failure_payload = _lazy_optional_function(
    "src.reporting.official_batch_payload",
    "official_document_batch_preflight_failure_payload",
)
attach_batch_reports = _lazy_optional_function(
    "src.services.production_runtime.batch_reporting",
    "attach_batch_reports",
)
batch_profile_ids = _lazy_optional_function(
    "src.services.production_runtime.batch_reporting",
    "batch_profile_ids",
)
build_batch_payload = _lazy_optional_function(
    "src.services.production_runtime.batch_reporting",
    "build_batch_payload",
)


_UNRESOLVED_OFFICIAL_MASTER = object()
_SESSION_BINDINGS_PREVALIDATED = object()


def _batch_config_module():
    return import_module("src.config.material_batch")


def build_material_batch_items(*args, **kwargs):
    return _batch_config_module().build_material_batch_items(*args, **kwargs)


def check_material_batch_preflight(*args, **kwargs):
    return _batch_config_module().check_material_batch_preflight(*args, **kwargs)


def validate_material_batch_output_target(*args, **kwargs):
    return _batch_config_module().validate_material_batch_output_target(
        *args,
        **kwargs,
    )


def _error_level_diagnostics(diagnostics) -> list[dict]:
    """Return only diagnostics whose declared severity is blocking."""

    return [
        diagnostic
        for diagnostic in diagnostics
        if isinstance(diagnostic, dict)
        and str(diagnostic.get("level") or "").strip().lower() == "error"
    ]


def _execution_uses_official_document_surface(
    scene: SceneWorkspace | None,
    execution_session=None,
) -> bool:
    """Use one effective-mode rule for master selection and terminal ownership."""

    execution_mode_id = mode_id_for_scene(
        scene,
        execution_session=execution_session,
    )
    return scene_uses_official_document_surface(
        scene,
        mode_id=execution_mode_id,
    )


def _terminal_assembly_surface_issue(
    terminal_owner: str,
    *,
    scene: SceneWorkspace | None,
    execution_session=None,
) -> str:
    """Reject specialized assembly when its effective UI surface is inactive."""

    if terminal_owner != "official":
        return ""
    if _execution_uses_official_document_surface(scene, execution_session):
        return ""
    return (
        "terminal_assembly_surface_mismatch:official:"
        "official_document_surface_required"
    )


class WorkbenchProductionRunner:
    """Internal low-level runner; product code must use an approved facade.

    Direct construction remains available for focused test harnesses and for
    the batch runner's already-validated child executions. Product entry
    points are owned by ``production_execution`` and the workbench execution
    session controller.
    """

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
        execution_session=None,
        prepared_exam_markdown_input: PreparedExamMarkdownInput | None = None,
        document_structure_evidence: DocumentStructureEvidence | None = None,
        document_scope_decisions: tuple[RegionDecision, ...] = (),
        _session_binding_token=None,
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
        self.execution_session_snapshot = execution_session
        self._session_binding_token = _session_binding_token
        self._prepared_exam_markdown_input = (
            prepared_exam_markdown_input.clone()
            if isinstance(
                prepared_exam_markdown_input,
                PreparedExamMarkdownInput,
            )
            else None
        )
        self._document_structure_evidence = (
            document_structure_evidence
            or getattr(execution_session, "document_structure_evidence", None)
        )
        self._document_scope_decisions = tuple(
            document_scope_decisions
            or getattr(execution_session, "document_scope_decisions", ())
            or ()
        )

    def run(self, progress_cb, cancel_check):
        started_at = time.perf_counter()
        snapshot = self.execution_session_snapshot
        template = self._template or TemplateConfig()
        scene = self._scene or SceneWorkspace()
        material_context = self._material_context.clone()
        if isinstance(snapshot, ExecutionSessionSnapshot):
            output_dir = self._output_dir or Path(snapshot.output_namespace)
            if self._session_binding_token is not _SESSION_BINDINGS_PREVALIDATED:
                binding_issues = validate_ready_session_bindings(
                    snapshot,
                    scene=scene,
                    template=template,
                    material_context=material_context,
                    output_namespace=output_dir,
                    session_overrides=self._session_overrides,
                )
                if binding_issues:
                    return _failed_payload("; ".join(binding_issues))
            input_path = execution_session_frozen_input_path(snapshot)
        else:
            input_path = (
                execution_session_frozen_input_path(snapshot)
                if snapshot is not None
                else None
            )
        if input_path is None:
            input_path = Path(self.doc_path)
        if not isinstance(snapshot, ExecutionSessionSnapshot):
            output_dir = self._output_dir or input_path.parent / "output"

        if cancel_check():
            return self._initial_cancelled_payload(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                material_context=material_context,
                started_at=started_at,
            )

        scene, material_context, prepared_exam_input = self._prepare_runtime_input(
            input_path=input_path,
            scene=scene,
            material_context=material_context,
        )
        style_source_summary = build_style_source_report_summary(scene, template)
        scope_issue = document_scope_policy_issue(
            scene.document_scope,
            mode_id=mode_id_for_scene(scene, execution_session=snapshot),
        )
        if scope_issue:
            return self._document_scope_failure(
                input_path=input_path,
                reason=scope_issue,
                style_source_summary=style_source_summary,
            )

        material_assembly_active = material_assembly_is_active(material_context)
        assembly_failure = self._material_assembly_gate(
            active=material_assembly_active,
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            material_context=material_context,
            style_source_summary=style_source_summary,
        )
        if assembly_failure is not None:
            return assembly_failure

        if prepared_exam_input is not None:
            return self._run_prepared_exam_input(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                material_context=material_context,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
                style_source_summary=style_source_summary,
                prepared_exam_input=prepared_exam_input,
            )

        return self._run_document_input(
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            material_context=material_context,
            material_assembly_active=material_assembly_active,
            style_source_summary=style_source_summary,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )

    def _run_document_input(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        material_assembly_active: bool,
        style_source_summary: dict[str, object] | None,
        progress_cb,
        cancel_check,
    ) -> dict[str, object]:
        preflight = prepare_document_material_preflight(
            input_path=input_path,
            scene=scene,
            material_context=material_context,
        )
        material_context = preflight.material_context
        if preflight.blocking_diagnostics:
            return self._material_preflight_failure(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                material_context=material_context,
                blocking_diagnostics=preflight.blocking_diagnostics,
                failure_diagnostics=preflight.failure_diagnostics,
                style_source_summary=style_source_summary,
            )

        target_groups = delivery_target_groups(
            scene,
            execution_session=self.execution_session_snapshot,
        )
        if target_groups:
            return self._run_delivery_groups(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                material_context=material_context,
                target_groups=target_groups,
                material_assembly_active=material_assembly_active,
                material_diagnostics=preflight.diagnostics,
                style_source_summary=style_source_summary,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
            )
        return self._run_default_document(
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            material_context=material_context,
            material_diagnostics=preflight.diagnostics,
            style_source_summary=style_source_summary,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )

    def _material_assembly_gate(
        self,
        *,
        active: bool,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        style_source_summary: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if not active:
            return None
        unsupported_reason = _material_assembly_unsupported_surface_reason(
            scene,
            input_path,
            mode_id=mode_id_for_scene(
                scene,
                execution_session=self.execution_session_snapshot,
            ),
        )
        if not unsupported_reason:
            return None
        return _blocked_material_assembly_payload(
            unsupported_reason,
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            material_context=material_context,
            style_source_summary=style_source_summary,
        )

    def _run_prepared_exam_input(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        prepared_exam_input: PreparedExamMarkdownInput,
        progress_cb,
        cancel_check,
        style_source_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        return self._run_exam_markdown_source(
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            material_context=material_context,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
            style_source_summary=style_source_summary,
            import_result=prepared_exam_input.import_result,
        )

    def _initial_cancelled_payload(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        started_at: float,
    ) -> dict[str, object]:
        report_config, config_failure = self._cancel_report_config(
            template=template,
            runtime_scene=scene,
        )
        return self._prepublication_cancelled_payload(
            input_path=input_path,
            output_dir=output_dir,
            config=report_config,
            runtime_material=material_context,
            started_at=started_at,
            modules_total=0,
            material_diagnostics=[],
            style_source_summary=None,
            config_failure=config_failure,
        )

    def _prepare_runtime_input(
        self,
        *,
        input_path: Path,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
    ) -> tuple[
        SceneWorkspace,
        MaterialExecutionContext,
        PreparedExamMarkdownInput | None,
    ]:
        if not _is_exam_markdown_input(scene, input_path):
            return (
                scene,
                material_context_with_exam_question_assets(scene, material_context),
                None,
            )

        expected_revision = (
            str(self.execution_session_snapshot.input_ref.frozen_revision or "")
            if self.execution_session_snapshot is not None
            else ""
        )
        expected_scene_revision = (
            str(self.execution_session_snapshot.plan_ref.effective_revision or "")
            if self.execution_session_snapshot is not None
            else execution_value_revision(scene)
        )
        expected_material_revision = (
            str(self.execution_session_snapshot.package_ref.effective_revision or "")
            if self.execution_session_snapshot is not None
            else execution_value_revision(material_context)
        )
        prepared = self._prepared_exam_markdown_input
        if prepared is None:
            prepared = prepare_exam_markdown_input(
                scene=scene,
                material_context=material_context,
                source_path=input_path,
                expected_source_revision=expected_revision,
            )
        prepared = validated_prepared_exam_markdown_input(
            prepared,
            source_path=input_path,
            expected_source_revision=expected_revision,
            expected_scene_revision=expected_scene_revision,
            expected_material_revision=expected_material_revision,
        )
        return prepared.scene, prepared.material_context, prepared

    @staticmethod
    def _document_scope_failure(
        *,
        input_path: Path,
        reason: str,
        style_source_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        payload = _failed_payload(
            reason,
            material_diagnostics=[
                document_scope_diagnostic(input_path, reason)
            ],
        )
        payload["style_source"] = dict(style_source_summary or {})
        return payload

    @staticmethod
    def _material_preflight_failure(
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        blocking_diagnostics: list[dict],
        failure_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        payload = _failed_payload(
            material_preflight_error_text(blocking_diagnostics),
            material_diagnostics=failure_diagnostics,
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

    def _run_delivery_groups(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        target_groups,
        material_assembly_active: bool,
        material_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
        progress_cb,
        cancel_check,
    ) -> dict[str, object]:
        if material_assembly_active:
            return _blocked_material_assembly_payload(
                "文件资料/图片规则暂不支持跨目标模板分组输出；"
                "该入口尚不能保证所有分组在同一装配事务中原子发布。",
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                material_context=material_context,
                style_source_summary=style_source_summary,
                material_diagnostics=material_diagnostics,
            )
        official_master = _selected_official_master(
            scene,
            execution_session=self.execution_session_snapshot,
        )
        exam_master = _selected_exam_master(
            scene,
            execution_session=self.execution_session_snapshot,
        )
        official_document_type_id = _single_official_document_type_id(
            self.execution_session_snapshot
        )
        return run_delivery_target_groups(
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            target_groups=target_groups,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
            execute_config=self._execute_config,
            output_suffix=self._output_suffix,
            session_overrides=self._session_overrides,
            execution_session=self.execution_session_snapshot,
            default_material_context=self._material_context,
            material_diagnostics=material_diagnostics,
            material_context=material_context,
            style_source_summary=style_source_summary,
            official_master=official_master,
            exam_master=exam_master,
            official_document_type_id=official_document_type_id,
        )

    def _run_default_document(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        material_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
        progress_cb,
        cancel_check,
    ) -> dict[str, object]:
        config = resolve_config(
            template,
            scene,
            session_overrides=self._session_overrides,
            **material_context.to_resolve_kwargs(),
        )
        official_master = _selected_official_master(
            scene,
            execution_session=self.execution_session_snapshot,
        )
        exam_master = _selected_exam_master(
            scene,
            execution_session=self.execution_session_snapshot,
        )
        result, elapsed, modules_enabled, modules_total = self._execute_config(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
            force_delivery_presets=should_force_delivery_presets(config),
            material_context=material_context,
            official_master=official_master,
            exam_master=exam_master,
            official_document_type_id=_single_official_document_type_id(
                self.execution_session_snapshot
            ),
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
            material_context=material_context,
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
        material_context: MaterialExecutionContext | None = None,
        official_master=_UNRESOLVED_OFFICIAL_MASTER,
        exam_master=None,
        official_document_type_id: str = "",
    ):
        terminal_owner = pipeline_terminal_assembly_owner(config)
        terminal_surface_issue = _terminal_assembly_surface_issue(
            terminal_owner,
            scene=self._scene,
            execution_session=self.execution_session_snapshot,
        )
        if terminal_surface_issue:
            context = PipelineContext(terminal_assembly_owner=terminal_owner)
            modules_total = len(create_all_modules())
            return (
                PipelineResult(
                    success=False,
                    status="failed",
                    context=context,
                    error=terminal_surface_issue,
                    config=config,
                ),
                0.0,
                0,
                modules_total,
            )
        material_active = (
            isinstance(material_context, MaterialExecutionContext)
            and material_assembly_is_active(material_context)
        )
        if terminal_owner and material_active:
            context = PipelineContext(terminal_assembly_owner=terminal_owner)
            modules_total = len(create_all_modules())
            return (
                PipelineResult(
                    success=False,
                    status="failed",
                    context=context,
                    error=(
                        f"Terminal assembler '{terminal_owner}' cannot ignore or "
                        "delegate active generic material assembly rules."
                    ),
                    config=config,
                ),
                0.0,
                0,
                modules_total,
            )
        if official_master is _UNRESOLVED_OFFICIAL_MASTER:
            official_master = (
                _UNRESOLVED_OFFICIAL_MASTER
                if self.execution_session_snapshot is not None
                else _selected_official_master(self._scene)
            )
        if material_active:
            outcome = run_workbench_material_assembly(
                input_path=input_path,
                output_dir=output_dir,
                output_suffix=self._output_suffix,
                config=config,
                material_context=material_context,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
                force_delivery_presets=force_delivery_presets,
                official_master=official_master,
                document_structure_evidence=self._document_structure_evidence,
                document_scope_decisions=self._document_scope_decisions,
            )
            return (
                outcome.result,
                outcome.elapsed_seconds,
                outcome.modules_enabled,
                outcome.modules_total,
            )

        modules = create_all_modules()
        selection = build_module_selection_plan(modules, config.is_module_enabled)
        enabled = (
            []
            if terminal_owner
            else list(selection.select_modules(modules))
        )

        started_at = time.perf_counter()
        pipeline = Pipeline(
            modules=enabled,
            config=config,
            output_dir=str(output_dir),
            output_suffix=self._output_suffix,
            progress_callback=progress_cb,
            cancel_check=cancel_check,
            force_delivery_presets=force_delivery_presets,
            official_master=official_master,
            exam_master=exam_master,
            official_document_type_id=official_document_type_id,
            document_structure_evidence=(
                self._document_structure_evidence
                or build_document_structure_evidence(input_path)
            ),
            document_scope_decisions=self._document_scope_decisions,
        )
        result = pipeline.execute(str(input_path))
        elapsed = time.perf_counter() - started_at
        return result, elapsed, len(enabled), len(modules)

    def _run_exam_markdown_source(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        material_context: MaterialExecutionContext,
        progress_cb,
        cancel_check,
        style_source_summary: dict[str, object] | None = None,
        import_result=None,
    ) -> dict[str, object]:
        started_at = time.perf_counter()
        modules_total = len(create_all_modules())
        runtime_scene = copy.deepcopy(scene)
        runtime_material = material_context.clone()

        if cancel_check():
            return self._exam_prepublication_cancelled(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                runtime_scene=runtime_scene,
                runtime_material=runtime_material,
                started_at=started_at,
                modules_total=modules_total,
                material_diagnostics=[],
                style_source_summary=style_source_summary,
            )
        progress_cb(0, 4, "解析 Markdown 题稿")
        if import_result is None:
            raise RuntimeError("exam_markdown_input_not_prepared")

        (
            runtime_material,
            import_diagnostics,
            requirement_diagnostics,
            material_diagnostics,
        ) = self._prepare_exam_material_preflight(
            runtime_scene=runtime_scene,
            runtime_material=runtime_material,
            import_result=import_result,
        )
        if cancel_check():
            return self._exam_prepublication_cancelled(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                runtime_scene=runtime_scene,
                runtime_material=runtime_material,
                started_at=started_at,
                modules_total=modules_total,
                material_diagnostics=material_diagnostics,
                style_source_summary=style_source_summary,
                import_result=import_result,
            )

        blocking_diagnostics = _error_level_diagnostics(requirement_diagnostics)
        if blocking_diagnostics:
            return self._exam_material_preflight_failure(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                scene=scene,
                runtime_material=runtime_material,
                import_result=import_result,
                blocking_diagnostics=blocking_diagnostics,
                material_diagnostics=material_diagnostics,
                style_source_summary=style_source_summary,
            )

        config = resolve_config(
            template,
            runtime_scene,
            session_overrides=self._session_overrides,
            **runtime_material.to_resolve_kwargs(),
        )
        progress_cb(1, 4, "校验试卷题源")
        validation = inspect_exam_question_schema(config)
        if cancel_check():
            return self._exam_prepublication_cancelled(
                input_path=input_path,
                output_dir=output_dir,
                template=template,
                runtime_scene=runtime_scene,
                runtime_material=runtime_material,
                started_at=started_at,
                modules_total=modules_total,
                material_diagnostics=material_diagnostics,
                style_source_summary=style_source_summary,
                import_result=import_result,
                validation=validation,
                config=config,
            )

        return self._run_exam_delivery_phase(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            validation=validation,
            import_result=import_result,
            runtime_material=runtime_material,
            started_at=started_at,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            style_source_summary=style_source_summary,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )

    def _run_exam_delivery_phase(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        config,
        validation,
        import_result,
        runtime_material: MaterialExecutionContext,
        started_at: float,
        modules_total: int,
        material_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
        progress_cb,
        cancel_check,
    ) -> dict[str, object]:
        progress_cb(2, 4, "生成试卷版本")
        frozen_master = (
            execution_session_frozen_master(self.execution_session_snapshot)
            if self.execution_session_snapshot is not None
            else None
        )
        runtime = build_exam_delivery_runtime(
            config,
            output_dir=output_dir,
            source_stem=input_path.stem,
            validation=validation,
            master=frozen_master,
        )
        output_paths = _exam_runtime_output_paths(runtime)
        context = self._exam_pipeline_context(
            input_path=input_path,
            import_result=import_result,
            validation=validation,
            runtime=runtime,
        )
        cancelled_after_publication = bool(cancel_check())
        result = self._exam_pipeline_result(
            cancelled=cancelled_after_publication,
            context=context,
            config=config,
            output_paths=output_paths,
            import_result=import_result,
            validation=validation,
            runtime=runtime,
        )
        if not cancelled_after_publication:
            progress_cb(3, 4, "写入报告")
        payload = self._project_exam_result(
            result,
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            started_at=started_at,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            runtime_material=runtime_material,
            style_source_summary=style_source_summary,
            import_result=import_result,
        )
        if not cancelled_after_publication:
            progress_cb(4, 4, "Completed")
        return payload

    def _exam_prepublication_cancelled(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        runtime_scene: SceneWorkspace,
        runtime_material: MaterialExecutionContext,
        started_at: float,
        modules_total: int,
        material_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
        import_result=None,
        validation=None,
        config=None,
    ) -> dict[str, object]:
        config_failure = None
        if config is None:
            config, config_failure = self._cancel_report_config(
                template=template,
                runtime_scene=runtime_scene,
            )
        return self._prepublication_cancelled_payload(
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            runtime_material=runtime_material,
            started_at=started_at,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            style_source_summary=style_source_summary,
            import_result=import_result,
            validation=validation,
            config_failure=config_failure,
        )

    @staticmethod
    def _prepare_exam_material_preflight(
        *,
        runtime_scene: SceneWorkspace,
        runtime_material: MaterialExecutionContext,
        import_result,
    ) -> tuple[MaterialExecutionContext, list[dict], list[dict], list[dict]]:
        import_diagnostics = _exam_markdown_import_diagnostics(import_result)
        field_resolution = runtime_material.resolve_material_fields()
        requirement_diagnostics = material_requirement_diagnostics(
            runtime_scene,
            runtime_material,
            field_resolution=field_resolution,
        )
        runtime_material = runtime_material.with_frozen_field_resolution(
            field_resolution
        )
        return (
            runtime_material,
            import_diagnostics,
            requirement_diagnostics,
            [*import_diagnostics, *requirement_diagnostics],
        )

    @staticmethod
    def _exam_material_preflight_failure(
        *,
        input_path: Path,
        output_dir: Path,
        template: TemplateConfig,
        scene: SceneWorkspace,
        runtime_material: MaterialExecutionContext,
        import_result,
        blocking_diagnostics: list[dict],
        material_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        payload = _failed_payload(
            material_preflight_error_text(blocking_diagnostics),
            material_diagnostics=material_diagnostics,
        )
        payload["exam_markdown_import"] = import_result.to_dict()
        payload["exam_question_schema"] = {}
        payload["exam_delivery_runtime"] = {}
        payload["style_source"] = dict(style_source_summary or {})
        _attach_material_preflight_reports(
            payload,
            input_path=input_path,
            output_dir=output_dir,
            template=template,
            scene=scene,
            material_context=runtime_material,
        )
        return payload

    @staticmethod
    def _exam_pipeline_context(
        *,
        input_path: Path,
        import_result,
        validation,
        runtime,
    ) -> PipelineContext:
        context = PipelineContext(
            source_doc_path=str(input_path),
            source_doc_dir=str(input_path.parent),
        )
        context.exam_markdown_import = import_result
        context.exam_question_schema = validation
        context.exam_delivery_runtime = runtime
        return context

    @staticmethod
    def _exam_pipeline_result(
        *,
        cancelled: bool,
        context: PipelineContext,
        config,
        output_paths: dict[str, str],
        import_result,
        validation,
        runtime,
    ) -> PipelineResult:
        if cancelled:
            return PipelineResult(
                success=False,
                context=context,
                output_paths=output_paths,
                config=config,
                error="Cancelled by user after exam artifacts were published.",
                cancelled=True,
            )
        success = (
            import_result.error_count == 0
            and int(getattr(validation, "error_count", 0) or 0) == 0
            and str(getattr(runtime, "status", "") or "") != "blocked"
            and bool(output_paths)
        )
        error_text = (
            ""
            if success
            else _exam_markdown_failure_text(import_result, validation, runtime)
        )
        return PipelineResult(
            success=success,
            status="success" if success else "failed",
            context=context,
            output_paths=output_paths,
            config=config,
            error=error_text,
        )

    def _project_exam_result(
        self,
        result: PipelineResult,
        *,
        input_path: Path,
        output_dir: Path,
        config,
        started_at: float,
        modules_total: int,
        material_diagnostics: list[dict],
        runtime_material: MaterialExecutionContext,
        style_source_summary: dict[str, object] | None,
        import_result,
    ) -> dict[str, object]:
        payload = self._payload_from_result(
            result,
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            elapsed=time.perf_counter() - started_at,
            modules_enabled=0,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            material_context=runtime_material,
            style_source_summary=style_source_summary,
        )
        payload["exam_markdown_import"] = import_result.to_dict()
        return payload

    def _cancel_report_config(
        self,
        *,
        template: TemplateConfig,
        runtime_scene: SceneWorkspace,
    ):
        """Resolve configured cancellation reports without rejecting cancellation."""

        try:
            return (
                resolve_config(
                    template,
                    runtime_scene,
                    session_overrides=self._session_overrides,
                ),
                None,
            )
        except Exception as exc:
            fallback_scope = "scene_without_session_overrides"
            fallback_error = ""
            primary_error = str(exc) or type(exc).__name__
            try:
                fallback_config = resolve_config(template, runtime_scene)
            except Exception as fallback_exc:
                fallback_scope = "template_baseline"
                fallback_config = resolve_template_baseline(template)
                fallback_message = str(fallback_exc) or type(fallback_exc).__name__
                if fallback_message == primary_error:
                    fallback_error = (
                        "; scene fallback failed with the same "
                        f"{type(fallback_exc).__name__}"
                    )
                else:
                    fallback_error = (
                        "; scene fallback failed: "
                        f"{type(fallback_exc).__name__}: {fallback_message}"
                    )
            return (
                fallback_config,
                {
                    "kind": "report_config",
                    "path": "",
                    "error_type": type(exc).__name__,
                    "error": primary_error + fallback_error,
                    "fallback": fallback_scope,
                },
            )

    def _prepublication_cancelled_payload(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        config,
        runtime_material: MaterialExecutionContext,
        started_at: float,
        modules_total: int,
        material_diagnostics: list[dict],
        style_source_summary: dict[str, object] | None,
        import_result=None,
        validation=None,
        config_failure: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Finalize configured evidence for every pre-publication cancel point."""

        context = PipelineContext(
            source_doc_path=str(input_path),
            source_doc_dir=str(input_path.parent),
        )
        if import_result is not None:
            context.exam_markdown_import = import_result
        if validation is not None:
            context.exam_question_schema = validation
        result = PipelineResult(
            success=False,
            status="cancelled",
            context=context,
            output_paths={},
            config=config,
            error="Cancelled by user before delivery artifacts were published.",
            cancelled=True,
        )
        payload = self._payload_from_result(
            result,
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            elapsed=time.perf_counter() - started_at,
            modules_enabled=0,
            modules_total=modules_total,
            material_diagnostics=material_diagnostics,
            material_context=runtime_material,
            style_source_summary=style_source_summary,
        )
        if import_result is not None:
            payload["exam_markdown_import"] = import_result.to_dict()
        if config_failure:
            _apply_artifact_failures(payload, [dict(config_failure)])
        return payload

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
        return project_execution_result(
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



class WorkbenchBatchProductionRunner:
    """Internal low-level batch runner behind approved product entry points.

    Direct construction is retained for focused test harnesses. Product code
    must enter through ``production_execution`` or the workbench execution
    session controller so an execution-session snapshot is built first.
    """

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
        source_kind: str = "",
        source_path: str = "",
        item_metadata: dict[str, dict[str, object]] | None = None,
        retry_of_run_id: str = "",
        attempt_number: int = 1,
        execution_session=None,
    ) -> None:
        self.doc_path = str(doc_path or "")
        self._template = template
        self._scene = scene
        self._archive = archive
        self._profile_ids = list(profile_ids) if profile_ids is not None else None
        self._base_output_dir = base_output_dir
        self._output_dir_template = output_dir_template
        self._session_overrides = dict(session_overrides or {})
        self._source_kind = str(source_kind or "").strip()
        self._source_path = str(source_path or "").strip()
        self._item_metadata = copy.deepcopy(item_metadata or {})
        self._retry_of_run_id = str(retry_of_run_id or "").strip()
        self._attempt_number = max(1, int(attempt_number or 1))
        self.execution_session_snapshot = execution_session
        self._base_context = (
            base_context.clone()
            if isinstance(base_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )

    def run(self, progress_cb, cancel_check):
        input_path = Path(self._source_path or self.doc_path or "batch_materials")
        snapshot = self.execution_session_snapshot
        if isinstance(snapshot, ExecutionSessionSnapshot):
            base_output_dir = self._base_output_dir or snapshot.output_namespace
            binding_issues = validate_ready_session_bindings(
                snapshot,
                scene=self._scene or SceneWorkspace(),
                template=self._template or TemplateConfig(),
                material_context=self._base_context,
                output_namespace=base_output_dir,
                session_overrides=self._session_overrides,
            )
            if binding_issues:
                return build_batch_payload(
                    "failed",
                    [],
                    error_text="; ".join(binding_issues),
                )
        else:
            base_output_dir = self._base_output_dir or (
                input_path.parent / "output" / "batch"
            )
        execution_mode_id = mode_id_for_scene(
            self._scene,
            execution_session=self.execution_session_snapshot,
        )
        is_official_surface = scene_uses_official_document_surface(
            self._scene,
            mode_id=execution_mode_id,
        )
        if (
            is_official_surface
            and self._source_kind != "official_document_table"
        ):
            return build_batch_payload(
                "failed",
                [],
                error_text=(
                    "official_batch_source_not_supported:"
                    "official_document_table_required"
                ),
            )

        batch_items, failure_payload = self._prepare_batch_items(
            input_path=input_path,
            base_output_dir=base_output_dir,
        )
        if failure_payload is not None:
            return failure_payload

        if (
            self._source_kind == "official_document_table"
            and is_official_surface
        ):
            official_master = (
                _UNRESOLVED_OFFICIAL_MASTER
                if self.execution_session_snapshot is not None
                else _selected_official_master(self._scene)
            )
            return self._run_official_document_batch(
                batch_items,
                input_path=input_path,
                base_output_dir=base_output_dir,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
                official_master=official_master,
            )
        return self._run_generic_batch(
            batch_items,
            input_path=input_path,
            base_output_dir=base_output_dir,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )

    def _prepare_batch_items(
        self,
        *,
        input_path: Path,
        base_output_dir: str | Path,
    ) -> tuple[list, dict[str, object] | None]:
        batch_preflight = check_material_batch_preflight(
            self._archive,
            profile_ids=self._profile_ids,
            base_output_dir=base_output_dir,
            output_dir_template=self._output_dir_template,
        )
        if not batch_preflight.ok:
            payload = build_batch_payload(
                "failed",
                [],
                error_text="; ".join(batch_preflight.issues),
            )
            attach_batch_reports(payload, base_output_dir, input_path)
            return [], payload

        batch_items = build_material_batch_items(
            self._archive,
            profile_ids=self._profile_ids,
            base_output_dir=base_output_dir,
            output_dir_template=self._output_dir_template,
            base_context=self._base_context,
        )
        try:
            for item in batch_items:
                validate_material_batch_output_target(
                    item.output_dir,
                    base_output_dir=base_output_dir,
                )
        except ValueError as exc:
            payload = build_batch_payload("failed", [], error_text=str(exc))
            attach_batch_reports(payload, base_output_dir, input_path)
            return [], payload
        return batch_items, None

    def _run_generic_batch(
        self,
        batch_items,
        *,
        input_path: Path,
        base_output_dir: str | Path,
        progress_cb,
        cancel_check,
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for index, item in enumerate(batch_items, start=1):
            if cancel_check():
                return self._reported_batch_payload(
                    "cancelled",
                    results,
                    input_path=input_path,
                    base_output_dir=base_output_dir,
                )
            progress_cb(
                index - 1,
                len(batch_items),
                f"批量生成: {item.profile_name or item.profile_id}",
            )
            missing_roles = item.context.missing_required_asset_roles()
            if missing_roles:
                results.append(_batch_missing_assets_result(item, missing_roles))
                continue
            try:
                validate_material_batch_output_target(
                    item.output_dir,
                    base_output_dir=base_output_dir,
                )
            except ValueError as exc:
                return self._reported_batch_payload(
                    "failed",
                    results,
                    input_path=input_path,
                    base_output_dir=base_output_dir,
                    error_text=str(exc),
                )

            payload = self._run_generic_batch_item(
                item,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
            )
            results.append(payload)
            if str(payload.get("status") or "") == "cancelled":
                return self._reported_batch_payload(
                    "cancelled",
                    results,
                    input_path=input_path,
                    base_output_dir=base_output_dir,
                    pending_profile_ids=batch_profile_ids(batch_items[index:]),
                )

        payload = _completed_batch_payload(
            results,
            empty_error="No profiles selected for batch execution",
        )
        attach_batch_reports(payload, base_output_dir, input_path)
        return payload

    def _run_generic_batch_item(
        self,
        item,
        *,
        progress_cb,
        cancel_check,
    ) -> dict[str, object]:
        payload = WorkbenchProductionRunner(
            doc_path=self.doc_path,
            template=self._template,
            scene=self._scene,
            session_overrides=self._session_overrides,
            material_context=item.context,
            output_dir=item.output_dir,
            execution_session=self.execution_session_snapshot,
            _session_binding_token=_SESSION_BINDINGS_PREVALIDATED,
        ).run(progress_cb, cancel_check)
        payload = dict(payload)
        payload["profile_id"] = item.profile_id
        payload["profile_name"] = item.profile_name
        payload["output_dir"] = item.output_dir
        return payload

    @staticmethod
    def _reported_batch_payload(
        status: str,
        results: list[dict[str, object]],
        *,
        input_path: Path,
        base_output_dir: str | Path,
        error_text: str = "",
        pending_profile_ids: list[str] | None = None,
    ) -> dict[str, object]:
        payload = build_batch_payload(status, results, error_text=error_text)
        if pending_profile_ids is not None:
            payload["pending_profile_ids"] = pending_profile_ids
        attach_batch_reports(payload, base_output_dir, input_path)
        return payload

    def _run_official_document_batch(
        self,
        batch_items,
        *,
        input_path: Path,
        base_output_dir: str | Path,
        progress_cb,
        cancel_check,
        official_master=_UNRESOLVED_OFFICIAL_MASTER,
    ) -> dict[str, object]:
        if (
            official_master is _UNRESOLVED_OFFICIAL_MASTER
            and self.execution_session_snapshot is None
        ):
            official_master = _selected_official_master(self._scene)
        results: list[dict[str, object]] = []
        output_config = self._scene.default_delivery_preset().artifacts
        generate_review_pdf = bool(output_config.review_pdf)

        for index, item in enumerate(batch_items, start=1):
            if cancel_check():
                return self._official_cancelled_payload(
                    results,
                    pending_items=batch_items[index - 1 :],
                    base_output_dir=base_output_dir,
                    input_path=input_path,
                )
            progress_cb(
                index - 1,
                len(batch_items),
                f"批量生成公文: {item.profile_name or item.profile_id}",
            )
            try:
                validate_material_batch_output_target(
                    item.output_dir,
                    base_output_dir=base_output_dir,
                )
            except ValueError as exc:
                payload = build_batch_payload("failed", results, error_text=str(exc))
                self._attach_official_batch_reports(
                    payload,
                    base_output_dir,
                    input_path,
                )
                return payload

            results.append(
                self._run_official_batch_item(
                    item,
                    input_path=input_path,
                    official_master=official_master,
                    generate_review_pdf=generate_review_pdf,
                )
            )
            if cancel_check():
                return self._official_cancelled_payload(
                    results,
                    pending_items=batch_items[index:],
                    base_output_dir=base_output_dir,
                    input_path=input_path,
                )

        payload = _completed_batch_payload(
            results,
            empty_error=(
                "No official-document records selected for batch execution"
            ),
        )
        self._attach_official_batch_reports(payload, base_output_dir, input_path)
        return payload

    def _run_official_batch_item(
        self,
        item,
        *,
        input_path: Path,
        official_master,
        generate_review_pdf: bool,
    ) -> dict[str, object]:
        metadata = dict(self._item_metadata.get(item.profile_id, {}) or {})
        profile_id = ""
        try:
            resolved_entity_data = item.context.resolved_entity_data()
            profile_id = resolve_official_batch_document_type_id(
                resolved_entity_data,
                metadata,
            )
            if material_assembly_is_active(item.context):
                return official_document_batch_exception_payload(
                    item,
                    profile_id=profile_id,
                    error_text=(
                        "文件资料/图片规则尚未接入公文批次的专用生成事务；"
                        "为避免绕过 assembler-owned staging，已阻止本条执行"
                    ),
                    metadata=metadata,
                )

            preflight = prepare_document_material_preflight(
                input_path=input_path,
                scene=self._scene,
                material_context=item.context,
            )
            if preflight.blocking_diagnostics:
                return official_document_batch_preflight_failure_payload(
                    item,
                    profile_id=profile_id,
                    error_text=material_preflight_error_text(
                        preflight.blocking_diagnostics
                    ),
                    material_diagnostics=preflight.failure_diagnostics,
                    metadata=metadata,
                )

            item_official_master = (
                _selected_official_master(
                    self._scene,
                    execution_session=self.execution_session_snapshot,
                    document_type_id=profile_id,
                )
                if self.execution_session_snapshot is not None
                else official_master
            )
            assembly = assemble_official_document_docx(
                profile_id,
                resolved_entity_data,
                output_dir=item.output_dir,
                field_aliases=item.context.field_aliases,
                master=item_official_master,
                generate_review_pdf=generate_review_pdf,
            )
            return official_document_batch_item_payload(
                item,
                assembly,
                material_diagnostics=preflight.diagnostics,
                metadata=metadata,
            )
        except Exception as exc:
            return official_document_batch_exception_payload(
                item,
                profile_id=profile_id,
                error_text=str(exc),
                metadata=metadata,
            )

    def _official_cancelled_payload(
        self,
        results: list[dict[str, object]],
        *,
        pending_items,
        base_output_dir: str | Path,
        input_path: Path,
    ) -> dict[str, object]:
        payload = build_batch_payload("cancelled", results, error_text="")
        payload["pending_profile_ids"] = batch_profile_ids(pending_items)
        self._attach_official_batch_reports(
            payload,
            base_output_dir,
            input_path,
        )
        return payload

    def _attach_official_batch_reports(
        self,
        payload: dict[str, object],
        base_output_dir: str | Path,
        input_path: Path,
    ) -> None:
        payload["batch_source_kind"] = self._source_kind
        payload["batch_source_path"] = self._source_path
        payload["batch_retry_of_run_id"] = self._retry_of_run_id
        payload["batch_attempt_number"] = self._attempt_number
        attach_batch_reports(payload, base_output_dir, input_path)


def _completed_batch_payload(
    results: list[dict[str, object]],
    *,
    empty_error: str,
) -> dict[str, object]:
    if not results:
        return build_batch_payload("failed", results, error_text=empty_error)
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
    return build_batch_payload(status, results, error_text=error_text)


def _failed_payload(
    error_text: str,
    *,
    material_diagnostics: list[dict] | None = None,
) -> dict[str, object]:
    diagnostics = diagnostics_payload(None, material_diagnostics)
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




def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _material_assembly_unsupported_surface_reason(
    scene: SceneWorkspace,
    input_path: Path,
    *,
    mode_id: str = "",
) -> str:
    if input_path.suffix.casefold() != ".docx":
        return (
            "文件资料/图片规则当前只接受 DOCX staging 输入；"
            "Markdown 题稿等专用生成入口尚未接入原子装配事务。"
        )
    if scene_uses_exam_paper_surface(scene, mode_id=mode_id):
        return (
            "试卷专用生成入口会自行派生多份文档，当前不满足文件资料/"
            "图片规则的 assembler-owned staging 契约，已明确阻止执行。"
        )
    if scene_uses_official_document_surface(scene, mode_id=mode_id):
        return (
            "公文专用装配入口会在 Pipeline 外生成文档，当前不满足文件资料/"
            "图片规则的 assembler-owned staging 契约，已明确阻止执行。"
        )
    return ""


def _blocked_material_assembly_payload(
    reason: str,
    *,
    input_path: Path,
    output_dir: Path,
    template: TemplateConfig,
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
    style_source_summary: dict[str, object] | None = None,
    material_diagnostics: list[dict] | None = None,
) -> dict[str, object]:
    diagnostic = {
        "rule_name": "material_assembly_staging_contract",
        "target": str(input_path),
        "section": "material",
        "change_type": "material_assembly_surface_unsupported",
        "before": "",
        "after": "",
        "paragraph_index": -1,
        "success": False,
        "level": "error",
        "diagnostic_code": "material_assembly_surface_unsupported",
        "reason": reason,
    }
    diagnostics = [*list(material_diagnostics or []), diagnostic]
    payload = _failed_payload(reason, material_diagnostics=diagnostics)
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


def _is_exam_markdown_input(scene: SceneWorkspace, input_path: Path) -> bool:
    return _prepared_is_exam_markdown_input(scene, input_path)


def _selected_exam_master(
    scene: SceneWorkspace | None,
    *,
    execution_session=None,
):
    """Return only the session-frozen exam master; never consult the live registry."""

    if execution_session is None:
        return None
    execution_mode_id = mode_id_for_scene(
        scene,
        execution_session=execution_session,
    )
    if not scene_uses_exam_paper_surface(scene, mode_id=execution_mode_id):
        return None
    master = execution_session_frozen_master(execution_session)
    if master is None:
        raise RuntimeError("execution_resource_unproven:exam_master")
    return master


def _single_official_document_type_id(execution_session) -> str:
    """Project the exact single-item official profile frozen by the session."""

    if execution_session is None:
        return ""
    document_type_id = str(
        getattr(execution_session, "document_type_id", "") or ""
    ).strip()
    if document_type_id == "per_item":
        raise RuntimeError(
            "execution_resource_unproven:official_document_type:per_item"
        )
    return document_type_id


def _selected_official_master(
    scene: SceneWorkspace | None,
    *,
    execution_session=None,
    document_type_id: str = "",
):
    """Resolve the plan-bound official DOCX master for runtime assembly."""

    if not _execution_uses_official_document_surface(scene, execution_session):
        return None
    requested_id = str(
        getattr(scene, "master_id", "") or ""
    ).strip()
    if execution_session is not None:
        effective_document_type_id = str(
            document_type_id
            or getattr(execution_session, "document_type_id", "")
            or ""
        ).strip()
        if effective_document_type_id and effective_document_type_id != "per_item":
            return execution_session_frozen_official_master(
                execution_session,
                document_type_id=effective_document_type_id,
            )
        if effective_document_type_id == "per_item":
            frozen_type_ids = tuple(
                dict.fromkeys(
                    document_type
                    for document_type, _master_id in (
                        execution_session.official_master_ids_by_document_type
                    )
                )
            )
            if len(frozen_type_ids) == 1:
                return execution_session_frozen_official_master(
                    execution_session,
                    document_type_id=frozen_type_ids[0],
                )
            raise RuntimeError(
                "execution_resource_unproven:official_master:per_item:"
                "document_type_required"
            )
        return execution_session_frozen_master(
            execution_session,
        )
    if requested_id:
        selected = get_master(requested_id, "official")
        if selected is not None:
            return selected
    return None


def _exam_markdown_import_diagnostics(import_result) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for issue in list(getattr(import_result, "issues", ()) or ()):
        diagnostics.append(
            {
                "rule_name": "exam_markdown_import",
                "target": str(getattr(issue, "path", "") or "markdown"),
                "section": "input",
                "change_type": str(getattr(issue, "kind", "") or "markdown_import_issue"),
                "before": "",
                "after": str(getattr(issue, "message", "") or ""),
                "paragraph_index": -1,
                "success": str(getattr(issue, "severity", "") or "warning") != "error",
                "level": str(getattr(issue, "severity", "") or "warning"),
                "reason": str(getattr(issue, "message", "") or ""),
                "observed": str(getattr(issue, "observed", "") or ""),
            }
        )
    return diagnostics


def _exam_runtime_output_paths(runtime) -> dict[str, str]:
    output_paths: dict[str, str] = {}
    for version in list(getattr(runtime, "rendered_versions", ()) or ()):
        preset_id = str(getattr(version, "preset_id", "") or "").strip()
        docx_path = str(getattr(version, "docx_path", "") or "").strip()
        if preset_id and docx_path:
            output_paths[preset_id] = docx_path
    return output_paths


def _exam_markdown_failure_text(import_result, validation, runtime) -> str:
    import_errors = [
        str(getattr(issue, "message", "") or "").strip()
        for issue in list(getattr(import_result, "issues", ()) or ())
        if str(getattr(issue, "severity", "") or "") == "error"
        and str(getattr(issue, "message", "") or "").strip()
    ]
    if import_errors:
        return "Markdown 题稿解析失败：" + "；".join(import_errors[:3])
    validation_errors = [
        str(getattr(issue, "message", "") or "").strip()
        for issue in list(getattr(validation, "issues", ()) or ())
        if str(getattr(issue, "severity", "") or "") == "error"
        and str(getattr(issue, "message", "") or "").strip()
    ]
    if validation_errors:
        return "试卷题源校验失败：" + "；".join(validation_errors[:3])
    skipped = str(getattr(runtime, "skipped_reason", "") or "").strip()
    if skipped:
        return f"试卷生成被阻止：{skipped}"
    return "试卷 Markdown 题稿未生成可用输出。"


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


















__all__: list[str] = []
