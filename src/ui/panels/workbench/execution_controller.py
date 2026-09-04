from __future__ import annotations

from collections.abc import Callable

from src.config.object_preflight_evidence import build_object_preflight_evidence
from src.config.scene_surface_registry import scene_uses_exam_paper_surface

from .state import ExecutionResultState


class WorkbenchExecutionController:
    """Coordinate worker lifecycle feedback for the quick-execute surface."""

    def __init__(
        self,
        execution_adapter,
        quick_execution_detail,
        batch_generation_detail=None,
        suite_generation_detail=None,
        file_batch_execution_detail=None,
        document_execution_detail=None,
        *,
        refresh_navigation: Callable[[], None] | None = None,
        refresh_quick_execute_card: Callable[[], None] | None = None,
        clear_execution_worker: Callable[[], None],
        has_ready_document: Callable[[], bool],
    ) -> None:
        self._execution_adapter = execution_adapter
        self._quick_execution_detail = quick_execution_detail
        self._file_batch_execution_detail = file_batch_execution_detail
        self._document_execution_detail = document_execution_detail
        self._batch_generation_detail = batch_generation_detail
        self._suite_generation_detail = suite_generation_detail
        self._refresh_navigation = (
            refresh_navigation
            or refresh_quick_execute_card
            or (lambda: None)
        )
        self._clear_execution_worker = clear_execution_worker
        self._has_ready_document = has_ready_document
        self._execution_result_received = False
        self._feedback_target = "single"

    def set_feedback_target(self, target: str) -> None:
        if target not in {"single", "files", "batch", "suite"}:
            raise ValueError(f"Unsupported execution feedback target: {target}")
        self._feedback_target = target

    def set_suite_generation_detail(self, detail) -> None:
        self._suite_generation_detail = detail

    def _feedback_surface(self):
        if self._feedback_target == "suite" and self._suite_generation_detail is not None:
            return self._suite_generation_detail
        if (
            self._feedback_target in {"single", "files", "batch"}
            and self._document_execution_detail is not None
        ):
            return self._document_execution_detail
        if (
            self._feedback_target == "files"
            and self._file_batch_execution_detail is not None
        ):
            return self._file_batch_execution_detail
        if self._feedback_target == "batch" and self._batch_generation_detail is not None:
            return self._batch_generation_detail
        return self._quick_execution_detail

    def reset_feedback(self) -> None:
        self._feedback_surface().reset_execution_feedback()
        self._refresh_navigation()

    def cancel_execution(self, worker) -> None:
        if worker is None:
            return
        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            request_cancel()

    def prepare_worker(self, worker) -> None:
        self._execution_result_received = False
        self._wire_worker(worker)
        target = self._feedback_surface()
        target.reset_execution_feedback()
        self._quick_execution_detail.set_execute_enabled(False)
        if self._document_execution_detail is not None:
            self._document_execution_detail.set_execute_enabled(False)
        if self._file_batch_execution_detail is not None:
            self._file_batch_execution_detail.set_execute_enabled(False)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_execute_enabled(False)
        if self._suite_generation_detail is not None:
            self._suite_generation_detail.set_execute_enabled(False)
        target.set_execution_progress(
            self._execution_adapter.build_progress_state(
                stage_text="Starting",
                current_step=0,
                total_steps=0,
            )
        )
        self._refresh_navigation()

    def apply_execution_result(self, result) -> None:
        if isinstance(result, ExecutionResultState):
            result_state = result
        else:
            result_state = self._execution_adapter.build_result_state(
                terminal_payload=result,
            )

        surface = self._feedback_surface()
        self._feedback_surface().set_execution_result(result_state)
        # Short-lived compatibility projection for callers that still inspect
        # the retired mode detail. The shared footer remains authoritative.
        compatibility_surface = None
        if self._document_execution_detail is not None:
            if self._feedback_target == "files":
                compatibility_surface = self._file_batch_execution_detail
            elif self._feedback_target == "batch":
                compatibility_surface = self._batch_generation_detail
        if (
            compatibility_surface is not None
            and compatibility_surface is not surface
            and (
                not hasattr(compatibility_surface, "has_local_execution_surface")
                or compatibility_surface.has_local_execution_surface()
            )
        ):
            compatibility_surface.set_execution_result(result_state)
        self._execution_result_received = True
        self._refresh_navigation()

    def _wire_worker(self, worker) -> None:
        def _connect(signal, handler) -> None:
            connect = getattr(signal, "connect", None)
            if callable(connect):
                connect(handler)

        _connect(getattr(worker, "execution_started", None), self._on_execution_started)
        _connect(getattr(worker, "progress_changed", None), self._on_execution_progress)
        _connect(getattr(worker, "execution_succeeded", None), self._on_execution_succeeded)
        _connect(getattr(worker, "execution_partial", None), self._on_execution_partial)
        _connect(getattr(worker, "execution_failed", None), self._on_execution_failed)
        _connect(getattr(worker, "execution_cancelled", None), self._on_execution_cancelled)
        _connect(getattr(worker, "execution_finished", None), self._on_execution_finished)

    def _on_execution_started(self) -> None:
        progress_state = self._execution_adapter.build_progress_state(
            stage_text="开始执行",
            current_step=0,
            total_steps=0,
        )
        self._feedback_surface().set_execution_progress(progress_state)
        self._refresh_navigation()

    def _on_execution_progress(self, current_step: int, total_steps: int, stage_text: str) -> None:
        progress_state = self._execution_adapter.build_progress_state(
            stage_text=stage_text,
            current_step=current_step,
            total_steps=total_steps,
        )
        self._feedback_surface().set_execution_progress(progress_state)
        self._refresh_navigation()

    def _on_execution_succeeded(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_partial(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_failed(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_cancelled(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_finished(self) -> None:
        self._clear_execution_worker()
        if not self._execution_result_received:
            self._feedback_surface().finish_execution()
        self._quick_execution_detail.set_execute_enabled(self._has_ready_document())
        if self._document_execution_detail is not None:
            self._document_execution_detail.set_execute_enabled(True)
        if self._file_batch_execution_detail is not None:
            self._file_batch_execution_detail.set_execute_enabled(True)
        if self._batch_generation_detail is not None:
            self._batch_generation_detail.set_execute_enabled(True)
        if self._suite_generation_detail is not None:
            self._suite_generation_detail.set_execute_enabled(True)
        self._refresh_navigation()


class FileBatchWorkbenchController:
    """Coordinate file-batch gating without expanding the Workbench panel."""

    def __init__(
        self,
        detail,
        execution,
        execution_session,
        quick_detail,
        *,
        active_worker: Callable[[], object | None],
        current_template: Callable[[], object | None],
        current_scene: Callable[[], object | None],
        current_mode_id: Callable[[], str],
        current_material_selection: Callable[[], object],
        current_document_type_id: Callable[[], str],
        execution_binding: Callable[[], dict[str, str]],
        current_output_root: Callable[[], str] | None = None,
        publish_confirmation: Callable[[str], None] | None = None,
        start_worker: Callable[[object], None],
        apply_execution_result: Callable[[object], None],
        refresh_navigation: Callable[[], None],
    ) -> None:
        self._detail = detail
        self._execution = execution
        self._execution_session = execution_session
        self._quick_detail = quick_detail
        self._active_worker = active_worker
        self._current_template = current_template
        self._current_scene = current_scene
        self._current_mode_id = current_mode_id
        self._current_material_selection = current_material_selection
        self._current_document_type_id = current_document_type_id
        self._execution_binding = execution_binding
        self._current_output_root = current_output_root
        self._publish_confirmation = publish_confirmation
        self._start_worker = start_worker
        self._apply_execution_result = apply_execution_result
        self._refresh_navigation = refresh_navigation

    def start(self) -> None:
        if self._active_worker() is not None:
            return
        paths = tuple(self._detail.selected_paths())
        if not paths:
            return
        manifest = self._detail.input_manifest()
        if manifest.truncated:
            self._publish_failure(
                f"扫描结果超过单次上限 {manifest.max_documents} 个文档，"
                "请缩小文件夹范围后重试",
            )
            return

        self._execution.set_feedback_target("files")
        mode_id = self._current_mode_id()
        scene = self._current_scene() or self._quick_detail.current_scene()
        source_dependent_gate = scene_uses_exam_paper_surface(
            scene,
            mode_id=mode_id,
        )
        material_gate = None
        if not source_dependent_gate:
            material_gate = self._quick_detail.current_execution_gate_decision()
            if not material_gate.can_run:
                self._publish_failure(
                    "；".join(material_gate.blocking_reasons),
                )
                return

        evidences = [
            build_object_preflight_evidence(scene, path)
            for path in paths
        ]
        blocked_evidence = [
            evidence
            for evidence in evidences
            if evidence.applicable and evidence.blocked
        ]
        review_evidence = [
            evidence
            for evidence in evidences
            if evidence.applicable
            and not evidence.blocked
            and (
                int(evidence.to_payload().get("findings_count") or 0) > 0
                or int(evidence.to_payload().get("module_skips_count") or 0) > 0
            )
        ]
        attention_evidence = [*blocked_evidence, *review_evidence]
        material_confirmation_reasons = (
            tuple(material_gate.confirmation_reasons)
            if material_gate is not None
            and material_gate.requires_confirmation
            else ()
        )
        confirmation_key = "\n".join(
            (
                *(
                    f"object:{evidence.canonical_key}"
                    for evidence in attention_evidence
                ),
                *(
                    f"material:{reason}"
                    for reason in material_confirmation_reasons
                ),
            )
        )
        confirmation_accepted = bool(confirmation_key) and (
            self._detail.preflight_confirmation_matches(confirmation_key)
        )
        if (
            confirmation_key
            and not confirmation_accepted
        ):
            messages: list[str] = []
            if material_confirmation_reasons:
                messages.append(
                    "资料待确认："
                    + "；".join(material_confirmation_reasons)
                )
            if blocked_evidence:
                messages.append(
                    f"{len(blocked_evidence)} 个文档将记为预检失败"
                )
            if review_evidence:
                messages.append(
                    f"{len(review_evidence)} 个文档含需保留或跳过的对象"
                )
            confirmation_message = (
                "；".join(messages) + "；其余文档将继续处理"
            )
            self._detail.set_preflight_confirmation(
                confirmation_key,
                confirmation_message,
            )
            if self._publish_confirmation is not None:
                self._publish_confirmation(confirmation_message)
            self._refresh_navigation()
            return

        confirmations = {
            str(path): (evidence.source_revision, evidence.evidence_digest)
            for path, evidence in zip(paths, evidences)
            if evidence.applicable and not evidence.blocked
        }
        material_selection = self._current_material_selection()
        self._detail.set_work_mode(mode_id)
        self._detail.set_scene_context(scene)
        self._detail.set_material_selection(material_selection)
        self._detail.set_runtime_template_overrides(
            self._quick_detail.runtime_template_overrides()
        )
        binding = dict(self._execution_binding() or {})
        output_root = (
            str(self._current_output_root() or "").strip()
            if self._current_output_root is not None
            else self._detail.output_dir()
        )
        output_roots = (
            manifest.output_roots(output_root)
            if callable(getattr(manifest, "output_roots", None))
            else self._detail.output_roots_by_path()
        )
        build = self._execution_session.build_file_batch_worker(
            document_paths=paths,
            template=self._current_template(),
            scene=scene,
            session_overrides=self._detail.runtime_template_overrides(),
            selection=material_selection,
            document_type_id=(
                self._current_document_type_id()
                if mode_id == "official"
                else ""
            ),
            mode_id=mode_id,
            plan_id=binding.get("plan_id", ""),
            plan_path=binding.get("plan_path", ""),
            plan_source_type=binding.get("plan_source_type", ""),
            template_id=binding.get("template_id", ""),
            template_path=binding.get("template_path", ""),
            template_source_type=binding.get("template_source_type", ""),
            output_root=output_root,
            output_roots_by_path=output_roots,
            material_gate_confirmed=confirmation_accepted,
            object_preflight_confirmations=confirmations,
        )
        self._start_worker(build)

    def _publish_failure(
        self,
        error_text: str,
        *,
        failed_count: int = 0,
    ) -> None:
        self._execution.reset_feedback()
        self._apply_execution_result(
            {
                "status": "failed",
                "output_path": "",
                "report_paths": [],
                "failed_count": int(failed_count),
                "error_text": str(error_text or "多文件执行失败"),
            }
        )
