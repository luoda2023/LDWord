from __future__ import annotations

from typing import Callable

from src.ui.adapters.workbench_execution_adapter import workbench_artifact_display_items

from .state import ExecutionResultState


class WorkbenchExecutionController:
    """Coordinate worker lifecycle feedback between quick execute and history panes."""

    def __init__(
        self,
        execution_adapter,
        quick_execution_detail,
        execution_history_detail,
        *,
        refresh_quick_execute_card: Callable[[], None],
        clear_execution_worker: Callable[[], None],
        has_ready_document: Callable[[], bool],
    ) -> None:
        self._execution_adapter = execution_adapter
        self._quick_execution_detail = quick_execution_detail
        self._execution_history_detail = execution_history_detail
        self._refresh_quick_execute_card = refresh_quick_execute_card
        self._clear_execution_worker = clear_execution_worker
        self._has_ready_document = has_ready_document
        self._execution_result_received = False
        self._history_runtime_modules: list[str] = []

    def cancel_execution(self, worker) -> None:
        if worker is None:
            return
        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            request_cancel()

    def prepare_worker(self, worker) -> None:
        self._execution_result_received = False
        self._wire_worker(worker)
        self._quick_execution_detail.reset_execution_feedback()
        self._reset_execution_history_feedback()
        self._quick_execution_detail.set_execute_enabled(False)
        self._quick_execution_detail.set_execution_progress(
            self._execution_adapter.build_progress_state(
                stage_text="Starting",
                current_step=0,
                total_steps=0,
            )
        )
        self._refresh_quick_execute_card()

    def apply_execution_result(self, result) -> None:
        if isinstance(result, ExecutionResultState):
            result_state = result
        else:
            payload = dict(result or {})
            result_state = self._execution_adapter.build_result_state(
                status=str(payload.get("status") or "failed"),
                output_path=str(payload.get("output_path") or ""),
                output_paths=_path_map(payload.get("output_paths")),
                compare_paths=_path_map(payload.get("compare_paths")),
                report_paths=list(payload.get("report_paths") or []),
                intermediate_paths=_path_map(payload.get("intermediate_paths")),
                material_manifest_paths=_path_map(payload.get("material_manifest_paths")),
                material_package_paths=_path_map(payload.get("material_package_paths")),
                scene_sample_manifest_paths=_path_map(
                    payload.get("scene_sample_manifest_paths")
                ),
                output_target_preflight=_dict_payload(payload.get("output_target_preflight")),
                failed_count=int(payload.get("failed_count") or 0),
                error_text=str(payload.get("error_text") or ""),
                diagnostics_count=int(payload.get("diagnostics_count") or 0),
                diagnostics_summary=str(payload.get("diagnostics_summary") or ""),
                style_source=_dict_payload(payload.get("style_source")),
                object_preflight=_dict_payload(payload.get("object_preflight")),
                material_field_consistency=_dict_payload(
                    payload.get("material_field_consistency")
                ),
                batch_isolation=_dict_payload(payload.get("batch_isolation")),
                question_figure_repair_queue=_dict_payload(
                    payload.get("question_figure_repair_queue")
                ),
                diagnostics_items=_diagnostics_items(payload),
                batch_issue_items=list(payload.get("batch_issue_items") or []),
            )

        self._quick_execution_detail.set_execution_result(result_state)
        self._sync_execution_history_result(result_state)
        self._execution_result_received = True
        self._refresh_quick_execute_card()

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
        self._quick_execution_detail.set_execution_progress(progress_state)
        self._sync_execution_history_progress(progress_state)
        self._refresh_quick_execute_card()

    def _on_execution_progress(self, current_step: int, total_steps: int, stage_text: str) -> None:
        progress_state = self._execution_adapter.build_progress_state(
            stage_text=stage_text,
            current_step=current_step,
            total_steps=total_steps,
        )
        self._quick_execution_detail.set_execution_progress(progress_state)
        self._sync_execution_history_progress(progress_state)
        self._refresh_quick_execute_card()

    def _on_execution_succeeded(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_partial(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_failed(self, payload) -> None:
        self.apply_execution_result(payload)

    def _on_execution_cancelled(self) -> None:
        self.apply_execution_result(
            self._execution_adapter.build_result_state(
                status="cancelled",
                output_path="",
                output_paths={},
                compare_paths={},
                report_paths=[],
                intermediate_paths={},
                material_manifest_paths={},
                material_package_paths={},
                output_target_preflight={},
                failed_count=0,
                error_text="",
                diagnostics_count=0,
                diagnostics_summary="",
            )
        )

    def _on_execution_finished(self) -> None:
        self._clear_execution_worker()
        if not self._execution_result_received:
            self._quick_execution_detail.finish_execution()
        self._quick_execution_detail.set_execute_enabled(self._has_ready_document())
        self._refresh_quick_execute_card()

    def _reset_execution_history_feedback(self) -> None:
        self._history_runtime_modules = []
        progress_widget = getattr(self._execution_history_detail, "_progress_widget", None)
        module_list = getattr(self._execution_history_detail, "_module_list", None)
        if progress_widget is not None:
            progress_widget.reset()
        if module_list is not None:
            clear = getattr(module_list, "clear", None)
            if callable(clear):
                clear()
        if hasattr(self._execution_history_detail, "set_summary"):
            self._execution_history_detail.set_summary("执行历史 · 暂无运行记录")

    def _sync_execution_history_progress(self, progress_state) -> None:
        stage_text = str(progress_state.stage_text or "处理中")
        progress_widget = getattr(self._execution_history_detail, "_progress_widget", None)
        module_list = getattr(self._execution_history_detail, "_module_list", None)
        if progress_widget is None or module_list is None:
            return

        progress_widget.set_progress(progress_state.current_step, progress_state.total_steps, stage_text)
        if stage_text not in self._history_runtime_modules:
            self._history_runtime_modules.append(stage_text)
            add_module = getattr(module_list, "add_module", None)
            if callable(add_module):
                add_module(stage_text, stage_text)
            if len(self._history_runtime_modules) > 1:
                previous = self._history_runtime_modules[-2]
                update_status = getattr(module_list, "update_status", None)
                if callable(update_status):
                    update_status(previous, "completed", 100)
                progress_widget.update_module_status(previous, "completed", 100)
        update_status = getattr(module_list, "update_status", None)
        if callable(update_status):
            update_status(stage_text, "running", progress_state.percent)
        progress_widget.update_module_status(stage_text, "running", progress_state.percent)
        progress_widget.append_log("info", f"执行阶段：{stage_text}")
        if hasattr(self._execution_history_detail, "set_summary"):
            self._execution_history_detail.set_summary(
                f"执行历史 · 当前阶段：{stage_text}"
            )

    def _sync_execution_history_result(self, result_state: ExecutionResultState) -> None:
        progress_widget = getattr(self._execution_history_detail, "_progress_widget", None)
        module_list = getattr(self._execution_history_detail, "_module_list", None)
        if progress_widget is None or module_list is None:
            return

        success = result_state.status in {"success", "partial_success"}
        if self._history_runtime_modules:
            final_stage = self._history_runtime_modules[-1]
            final_status = "completed" if success else ("failed" if result_state.status == "failed" else "cancelled")
            final_progress = 100 if success else 0
            update_status = getattr(module_list, "update_status", None)
            if callable(update_status):
                update_status(final_stage, final_status, final_progress)
            progress_widget.update_module_status(final_stage, final_status, final_progress)
        progress_widget.set_completed(success, {"success_count": 1 if success else 0})
        progress_widget.append_log("info", result_state.summary)
        for label, path in workbench_artifact_display_items(
            result_state.output_paths,
            delivery_preset_labels=True,
        ):
            progress_widget.append_log("info", f"输出文件[{label}]：{path}")
        if result_state.output_path and not result_state.output_paths:
            progress_widget.append_log("info", f"输出文件：{result_state.output_path}")
        for label, path in workbench_artifact_display_items(
            result_state.compare_paths,
            delivery_preset_labels=True,
        ):
            progress_widget.append_log("info", f"对比稿[{label}]：{path}")
        for label, path in workbench_artifact_display_items(
            result_state.intermediate_paths,
            delivery_preset_labels=True,
        ):
            progress_widget.append_log("info", f"中间产物[{label}]：{path}")
        for label, path in workbench_artifact_display_items(
            result_state.material_manifest_paths
        ):
            progress_widget.append_log("info", f"资料清单[{label}]：{path}")
        for label, path in workbench_artifact_display_items(
            result_state.material_package_paths
        ):
            progress_widget.append_log("info", f"资料包[{label}]：{path}")
        for item in list(result_state.artifact_items or []):
            if item.detail:
                progress_widget.append_log(
                    "warning",
                    f"产物预检[{item.label}]：{item.detail}",
                )
        if result_state.report_paths:
            progress_widget.append_log("info", f"报告文件：{', '.join(result_state.report_paths)}")
        if result_state.object_preflight_summary:
            level = _object_preflight_log_level(result_state)
            progress_widget.append_log(level, result_state.object_preflight_summary)
            for line in list(result_state.object_preflight_details or []):
                progress_widget.append_log(level, f"对象预检明细：{line}")
        if result_state.diagnostics_summary:
            progress_widget.append_log("warning", result_state.diagnostics_summary)
        if result_state.material_field_consistency_summary:
            progress_widget.append_log(
                _material_field_consistency_log_level(result_state),
                result_state.material_field_consistency_summary,
            )
        if result_state.error_text:
            progress_widget.append_log("error", result_state.error_text)
        if hasattr(self._execution_history_detail, "set_summary"):
            self._execution_history_detail.set_summary(
                f"执行历史 · {result_state.summary}"
            )


def _path_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(path)
        for key, path in value.items()
        if str(key or "").strip() and str(path or "").strip()
    }


def _dict_payload(value) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _diagnostics_items(payload: dict[str, object]) -> list[dict]:
    raw_items = payload.get("diagnostics_items")
    if not raw_items:
        diagnostics = payload.get("diagnostics")
        if isinstance(diagnostics, dict):
            raw_items = diagnostics.get("items")
    if not raw_items and not payload.get("batch_issue_items"):
        raw_items = payload.get("material_diagnostics")
    return [dict(item) for item in list(raw_items or []) if isinstance(item, dict)]


def _object_preflight_log_level(result_state: ExecutionResultState) -> str:
    payload = getattr(result_state, "object_preflight", {}) or {}
    if not isinstance(payload, dict):
        return "info"
    findings_count = _safe_int(payload.get("findings_count"))
    module_skips_count = _safe_int(payload.get("module_skips_count"))
    return "warning" if findings_count > 0 or module_skips_count > 0 else "info"


def _material_field_consistency_log_level(result_state: ExecutionResultState) -> str:
    payload = getattr(result_state, "material_field_consistency", {}) or {}
    issue_count = _safe_int(payload.get("issue_count")) if isinstance(payload, dict) else 0
    return "warning" if issue_count > 0 else "info"


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
