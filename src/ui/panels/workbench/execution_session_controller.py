from __future__ import annotations

import copy
from dataclasses import dataclass

from src.config.entity import EntityArchive
from src.services.execution_session import (
    ExecutionSessionSnapshot,
    build_execution_session_snapshot,
    cleanup_execution_session_resources,
    execution_session_frozen_input_path,
)
from src.config.material_batch import (
    MaterialBatchSelection,
    build_material_batch_items,
    check_material_batch_preflight,
)
from src.config.material_context import MaterialExecutionContext
from src.config.official_document_profiles import (
    get_official_document_profile,
    resolve_official_batch_document_type_id,
)
from src.config.document_scope import document_scope_policy_issue
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    RegionDecision,
)
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.config.work_mode import execution_work_mode_issue, resolve_work_mode_id
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)
from src.ui.adapters.workbench_material_issues import (
    material_batch_readiness_gate_decision,
    material_readiness_gate_decision,
)

from .diagnostics import log_best_effort_shutdown_failure


def _project_official_document_type(
    context: MaterialExecutionContext,
    *,
    document_type_id: str,
    mode_id: str,
) -> MaterialExecutionContext:
    """Project the task-level document type into the legacy runtime payload."""

    normalized_mode = str(mode_id or "").strip()
    normalized_type = str(document_type_id or "").strip()
    if normalized_mode != "official" or get_official_document_profile(normalized_type) is None:
        return context
    projected = context.clone()
    projected.mode_id = "official"
    projected.profile_id = f"official:{normalized_type}"
    projected.entity_data = {
        **dict(projected.entity_data or {}),
        "document_type": normalized_type,
    }
    return projected


def _selected_official_document_type_ids(
    archive: EntityArchive,
    *,
    profile_ids: list[str] | None,
    item_metadata: dict[str, dict[str, object]] | None,
    base_context: MaterialExecutionContext,
) -> tuple[str, ...]:
    """Project the exact batch selection into the session resource graph."""

    selected_ids = (
        {str(profile_id or "").strip() for profile_id in profile_ids}
        if profile_ids is not None
        else None
    )
    metadata_by_profile = item_metadata or {}
    document_type_ids: list[str] = []
    items = build_material_batch_items(
        archive,
        profile_ids=(tuple(selected_ids) if selected_ids is not None else None),
        base_context=base_context,
    )
    for item in items:
        profile_id = str(item.profile_id or "").strip()
        metadata = dict(metadata_by_profile.get(profile_id, {}) or {})
        document_type_id = resolve_official_batch_document_type_id(
            item.context.resolved_entity_data(),
            metadata,
        )
        document_type_ids.append(document_type_id)
    return tuple(dict.fromkeys(document_type_ids))


@dataclass(frozen=True)
class ExecutionBuildResult:
    worker: object | None
    cancelled: bool = False
    already_running: bool = False
    error_text: str = ""
    session_snapshot: ExecutionSessionSnapshot | None = None


def _failed_build_after_snapshot(
    snapshot: ExecutionSessionSnapshot,
    error_text: str,
) -> ExecutionBuildResult:
    cleanup_issues = cleanup_execution_session_resources(snapshot)
    reasons = [str(error_text or "").strip(), *cleanup_issues]
    return ExecutionBuildResult(
        worker=None,
        error_text="；".join(reason for reason in reasons if reason),
        session_snapshot=snapshot,
    )


class WorkbenchExecutionSessionController:
    """Own active worker lifecycle for the workbench panel."""

    def __init__(self, *, resolve_document_path, worker_parent=None) -> None:
        self._resolve_document_path = resolve_document_path
        self._worker_parent = worker_parent
        self._active_worker = None

    @property
    def active_worker(self):
        return self._active_worker

    def set_active_worker(self, worker) -> None:
        self._active_worker = worker

    def clear_active_worker(self) -> None:
        self._active_worker = None

    def discard_worker(
        self,
        worker,
        *,
        snapshot: ExecutionSessionSnapshot | None = None,
        timeout_ms: int | None = 1000,
    ) -> list[str]:
        """Dispose a built worker that could not be prepared or started."""

        if self._active_worker is worker:
            self._active_worker = None
        shutdown = getattr(worker, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown(timeout_ms=timeout_ms)
            except TypeError:
                try:
                    shutdown() if timeout_ms is None else shutdown(int(timeout_ms))
                except Exception as exc:
                    log_best_effort_shutdown_failure(
                        "execution session controller",
                        "discard_worker.shutdown",
                        exc,
                    )
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution session controller",
                    "discard_worker.shutdown",
                    exc,
                )
        elif callable(getattr(worker, "request_cancel", None)):
            try:
                worker.request_cancel()
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution session controller",
                    "discard_worker.request_cancel",
                    exc,
                )
        if isinstance(snapshot, ExecutionSessionSnapshot):
            return list(cleanup_execution_session_resources(snapshot))
        return []

    def build_worker(
        self,
        *,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        session_overrides: dict[str, object] | None = None,
        material_context: MaterialExecutionContext | None = None,
        document_type_id: str = "",
        mode_id: str = "",
        plan_id: str = "",
        plan_path: str = "",
        plan_source_type: str = "",
        template_id: str = "",
        template_path: str = "",
        template_source_type: str = "",
        output_root: str = "",
        material_gate_confirmed: bool = False,
        expected_input_revision: str = "",
        object_preflight_confirmation_digest: str = "",
        document_structure_evidence: DocumentStructureEvidence | None = None,
        document_scope_decisions: tuple[RegionDecision, ...] = (),
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )

        runtime_scene = copy.deepcopy(scene or SceneWorkspace())
        runtime_template = copy.deepcopy(template or TemplateConfig())
        mode_issue = execution_work_mode_issue(
            runtime_scene,
            requested_mode_id=mode_id,
        )
        if mode_issue:
            return ExecutionBuildResult(worker=None, error_text=mode_issue)
        effective_mode_id = resolve_work_mode_id(
            runtime_scene,
            requested_mode_id=mode_id,
        )
        effective_document_type_id = (
            str(document_type_id or "").strip()
            if effective_mode_id == "official"
            else ""
        )
        scope_issue = document_scope_policy_issue(
            runtime_scene.document_scope,
            mode_id=effective_mode_id,
        )
        if scope_issue:
            return ExecutionBuildResult(worker=None, error_text=scope_issue)
        runtime_material = (
            material_context.clone()
            if isinstance(material_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        runtime_material = _project_official_document_type(
            runtime_material,
            document_type_id=effective_document_type_id,
            mode_id=effective_mode_id,
        )
        defer_material_gate = scene_uses_exam_paper_surface(
            runtime_scene,
            mode_id=effective_mode_id,
        )
        if not defer_material_gate:
            material_gate = material_readiness_gate_decision(
                runtime_scene,
                runtime_material,
            )
            if not material_gate.can_run:
                return ExecutionBuildResult(
                    worker=None,
                    error_text="；".join(material_gate.blocking_reasons),
                )
            if material_gate.requires_confirmation and not material_gate_confirmed:
                return ExecutionBuildResult(
                    worker=None,
                    error_text="；".join(material_gate.confirmation_reasons),
                )
        doc_path = self._resolve_document_path()
        if doc_path is None:
            return ExecutionBuildResult(worker=None, cancelled=True)
        snapshot = build_execution_session_snapshot(
            mode_id=effective_mode_id,
            scene=runtime_scene,
            template=runtime_template,
            material_context=runtime_material,
            input_path=doc_path,
            output_root=output_root,
            plan_id=plan_id,
            plan_path=plan_path,
            plan_source_type=plan_source_type,
            template_id=template_id,
            template_path=template_path,
            template_source_type=template_source_type,
            document_type_id=effective_document_type_id,
            object_preflight_confirmation_revision=expected_input_revision,
            object_preflight_confirmation_digest=(
                object_preflight_confirmation_digest
            ),
            document_structure_evidence=document_structure_evidence,
            document_scope_decisions=document_scope_decisions,
            session_overrides=session_overrides,
        )
        if not snapshot.ready:
            return ExecutionBuildResult(
                worker=None,
                error_text="；".join(snapshot.issues),
                session_snapshot=snapshot,
            )
        try:
            expected_revision = str(expected_input_revision or "").strip()
            if (
                expected_revision
                and snapshot.input_ref.frozen_revision != expected_revision
            ):
                return _failed_build_after_snapshot(
                    snapshot,
                    "object_preflight_confirmation_stale:input_revision",
                )
            frozen_input_path = execution_session_frozen_input_path(snapshot)

            from src.services.production_runtime.exam_markdown_execution_input import (
                is_exam_markdown_input,
                prepare_exam_markdown_input,
            )
            from src.services.production_runtime.execution_runtime import (
                WorkbenchProductionRunner,
            )
            from .execution_thread_handle import ThreadedExecutionHandle
            from .execution_worker import ExecutionWorker

            prepared_exam_input = None
            gate_scene = runtime_scene
            gate_material = runtime_material
            if frozen_input_path is not None and is_exam_markdown_input(
                runtime_scene,
                frozen_input_path,
            ):
                try:
                    prepared_exam_input = prepare_exam_markdown_input(
                        scene=runtime_scene,
                        material_context=runtime_material,
                        source_path=frozen_input_path,
                        expected_source_revision=(
                            snapshot.input_ref.frozen_revision
                        ),
                    )
                except Exception as exc:
                    return _failed_build_after_snapshot(
                        snapshot,
                        f"exam_markdown_prepare_failed:{type(exc).__name__}:{exc}",
                    )
                gate_scene = prepared_exam_input.scene
                gate_material = prepared_exam_input.material_context

            if defer_material_gate:
                material_gate = material_readiness_gate_decision(
                    gate_scene,
                    gate_material,
                )
                if not material_gate.can_run:
                    return _failed_build_after_snapshot(
                        snapshot,
                        "；".join(material_gate.blocking_reasons),
                    )
                if (
                    material_gate.requires_confirmation
                    and not material_gate_confirmed
                ):
                    return _failed_build_after_snapshot(
                        snapshot,
                        "；".join(material_gate.confirmation_reasons),
                    )

            runner = WorkbenchProductionRunner(
                doc_path=str(frozen_input_path or ""),
                template=runtime_template,
                scene=runtime_scene,
                session_overrides=session_overrides,
                material_context=runtime_material,
                execution_session=snapshot,
                output_dir=snapshot.output_namespace,
                prepared_exam_markdown_input=prepared_exam_input,
            )
            worker = ExecutionWorker(runner, parent=None)
            handle = ThreadedExecutionHandle(
                worker,
                parent=self._worker_parent,
            )
        except Exception as exc:
            return _failed_build_after_snapshot(
                snapshot,
                f"execution_worker_build_failed:{type(exc).__name__}:{exc}",
            )
        return ExecutionBuildResult(
            worker=handle,
            session_snapshot=snapshot,
        )

    def build_batch_worker(
        self,
        *,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        archive: EntityArchive,
        profile_ids: list[str] | None = None,
        base_output_dir: str | None = None,
        output_dir_template: str = "{entity_name}",
        session_overrides: dict[str, object] | None = None,
        base_context: MaterialExecutionContext | None = None,
        source_kind: str = "",
        source_path: str = "",
        item_metadata: dict[str, dict[str, object]] | None = None,
        retry_of_run_id: str = "",
        attempt_number: int = 1,
        mode_id: str = "",
        plan_id: str = "",
        plan_path: str = "",
        plan_source_type: str = "",
        template_id: str = "",
        template_path: str = "",
        template_source_type: str = "",
        material_gate_confirmed: bool = False,
        expected_input_revision: str = "",
        object_preflight_confirmation_digest: str = "",
        document_structure_evidence: DocumentStructureEvidence | None = None,
        document_scope_decisions: tuple[RegionDecision, ...] = (),
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )

        runtime_scene = copy.deepcopy(scene or SceneWorkspace())
        runtime_template = copy.deepcopy(template or TemplateConfig())
        mode_issue = execution_work_mode_issue(
            runtime_scene,
            requested_mode_id=mode_id,
        )
        if mode_issue:
            return ExecutionBuildResult(worker=None, error_text=mode_issue)
        effective_mode_id = resolve_work_mode_id(
            runtime_scene,
            requested_mode_id=mode_id,
        )
        scope_issue = document_scope_policy_issue(
            runtime_scene.document_scope,
            mode_id=effective_mode_id,
        )
        if scope_issue:
            return ExecutionBuildResult(worker=None, error_text=scope_issue)
        is_official_batch_surface = scene_uses_official_document_surface(
            runtime_scene,
            mode_id=effective_mode_id,
        )
        if (
            is_official_batch_surface
            and str(source_kind or "").strip() != "official_document_table"
        ):
            return ExecutionBuildResult(
                worker=None,
                error_text=(
                    "official_batch_source_not_supported:"
                    "official_document_table_required"
                ),
            )
        runtime_context = (
            base_context.clone()
            if isinstance(base_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        readiness_profile_ids = (
            list(profile_ids)
            if profile_ids is not None
            else [
                str(profile.profile_id or "").strip()
                for profile in archive.profiles
                if str(profile.profile_id or "").strip()
            ]
        )
        readiness_selection = MaterialBatchSelection(
            mode_id=effective_mode_id,
            scene_id=plan_id,
            package_id=str(getattr(archive, "package_id", "") or ""),
            archive=copy.deepcopy(archive),
            profile_ids=readiness_profile_ids,
            output_dir_template=output_dir_template,
            base_context=runtime_context.clone(),
            source_kind=source_kind,
            source_path=source_path,
            item_metadata=copy.deepcopy(item_metadata or {}),
        )
        material_gate = material_batch_readiness_gate_decision(
            runtime_scene,
            readiness_selection,
        )
        if not material_gate.can_run:
            return ExecutionBuildResult(
                worker=None,
                error_text="；".join(material_gate.blocking_reasons),
            )
        if material_gate.requires_confirmation and not material_gate_confirmed:
            return ExecutionBuildResult(
                worker=None,
                error_text="；".join(material_gate.confirmation_reasons),
            )
        is_official_table_batch = (
            str(source_kind or "").strip() == "official_document_table"
            and is_official_batch_surface
        )
        if is_official_table_batch:
            doc_path = ""
        else:
            doc_path = self._resolve_document_path()
            if doc_path is None:
                return ExecutionBuildResult(worker=None, cancelled=True)

        snapshot = build_execution_session_snapshot(
            mode_id=effective_mode_id,
            scene=runtime_scene,
            template=runtime_template,
            material_context=runtime_context,
            input_path=doc_path,
            output_root=base_output_dir or "",
            plan_id=plan_id,
            plan_path=plan_path,
            plan_source_type=plan_source_type,
            template_id=template_id,
            template_path=template_path,
            template_source_type=template_source_type,
            document_type_id=("per_item" if is_official_table_batch else ""),
            official_document_type_ids=(
                _selected_official_document_type_ids(
                    archive,
                    profile_ids=profile_ids,
                    item_metadata=item_metadata,
                    base_context=runtime_context,
                )
                if is_official_table_batch
                else ()
            ),
            object_preflight_confirmation_revision=expected_input_revision,
            object_preflight_confirmation_digest=(
                object_preflight_confirmation_digest
            ),
            document_structure_evidence=document_structure_evidence,
            document_scope_decisions=document_scope_decisions,
            session_overrides=session_overrides,
        )
        if not snapshot.ready:
            return ExecutionBuildResult(
                worker=None,
                error_text="；".join(snapshot.issues),
                session_snapshot=snapshot,
            )
        try:
            expected_revision = str(expected_input_revision or "").strip()
            if (
                expected_revision
                and snapshot.input_ref.frozen_revision != expected_revision
            ):
                return _failed_build_after_snapshot(
                    snapshot,
                    "object_preflight_confirmation_stale:input_revision",
                )
            frozen_input_path = execution_session_frozen_input_path(snapshot)
            batch_preflight = check_material_batch_preflight(
                archive,
                profile_ids=profile_ids,
                base_output_dir=snapshot.output_namespace,
                output_dir_template=output_dir_template,
            )
            if not batch_preflight.ok:
                return _failed_build_after_snapshot(
                    snapshot,
                    "；".join(batch_preflight.issues),
                )

            from src.services.production_runtime.execution_runtime import (
                WorkbenchBatchProductionRunner,
            )
            from .execution_thread_handle import ThreadedExecutionHandle
            from .execution_worker import ExecutionWorker

            runner = WorkbenchBatchProductionRunner(
                doc_path=str(frozen_input_path or ""),
                template=runtime_template,
                scene=runtime_scene,
                archive=copy.deepcopy(archive),
                profile_ids=profile_ids,
                base_output_dir=snapshot.output_namespace,
                output_dir_template=output_dir_template,
                session_overrides=session_overrides,
                base_context=runtime_context,
                source_kind=source_kind,
                source_path=source_path,
                item_metadata=item_metadata,
                retry_of_run_id=retry_of_run_id,
                attempt_number=attempt_number,
                execution_session=snapshot,
            )
            worker = ExecutionWorker(runner, parent=None)
            handle = ThreadedExecutionHandle(
                worker,
                parent=self._worker_parent,
            )
        except Exception as exc:
            return _failed_build_after_snapshot(
                snapshot,
                f"batch_execution_worker_build_failed:{type(exc).__name__}:{exc}",
            )
        return ExecutionBuildResult(
            worker=handle,
            session_snapshot=snapshot,
        )

    @staticmethod
    def start_worker(worker) -> None:
        start = getattr(worker, "start", None)
        if callable(start):
            start()
            return

        run = getattr(worker, "run", None)
        if callable(run):
            run()

    def shutdown_active_execution(self, timeout_ms: int | None = 1000) -> bool:
        worker = self._active_worker
        if worker is None:
            return True

        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            try:
                request_cancel()
            except Exception as exc:
                log_best_effort_shutdown_failure("execution session controller", "request_cancel", exc)

        shutdown = getattr(worker, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown(timeout_ms=timeout_ms)
            except TypeError:
                try:
                    if timeout_ms is None:
                        shutdown()
                    else:
                        shutdown(int(timeout_ms))
                except Exception as exc:
                    log_best_effort_shutdown_failure(
                        "execution session controller",
                        "worker.shutdown",
                        exc,
                    )
            except Exception as exc:
                log_best_effort_shutdown_failure("execution session controller", "worker.shutdown", exc)

        thread = getattr(worker, "_thread", None)
        is_running = getattr(thread, "isRunning", None) if thread is not None else None
        if not callable(is_running):
            is_running = getattr(worker, "isRunning", None)

        if callable(is_running):
            try:
                return not bool(is_running())
            except Exception as exc:
                log_best_effort_shutdown_failure("execution session controller", "worker.isRunning", exc)
                return False
        return True


__all__ = ["ExecutionBuildResult", "WorkbenchExecutionSessionController"]
