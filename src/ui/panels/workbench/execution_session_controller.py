"""Canonical Workbench worker construction.

Execution consumes either no material or one immutable MaterialRunSelection.
There is no archive/context compatibility path in this controller.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.application.materials import (
    project_execution_material_record_snapshot,
)
from src.config.scene import SceneWorkspace
from src.config.document_structure_contract import (
    DocumentStructureEvidence,
    RegionDecision,
)
from src.config.template import TemplateConfig
from src.document_batch import (
    DocumentBatchRequest,
    compile_document_batch_plan,
)
from src.domain.materials import MaterialRunSelection
from src.services.production_execution import (
    ProductionExecutionRequest,
    execute_production_request,
)

from .diagnostics import log_best_effort_shutdown_failure
from .material_state import bind_workbench_material
from .output_path_policy import resolve_workbench_output_root


@dataclass(frozen=True)
class ExecutionBuildResult:
    worker: object | None
    cancelled: bool = False
    already_running: bool = False
    error_text: str = ""
    session_snapshot: object | None = None


class _ProductionRunner:
    def __init__(self, request: ProductionExecutionRequest) -> None:
        self._request = request

    def run(self, progress_callback, cancel_check):
        result = execute_production_request(
            self._request,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        return _attach_request_trace(result, self._request)


class _DocumentBatchRunner:
    def __init__(
        self,
        snapshot,
        *,
        source_paths: tuple[str, ...],
        output_root: str,
    ) -> None:
        self._snapshot = snapshot
        self._source_paths = source_paths
        self._output_root = output_root

    def run(self, progress_callback, cancel_check):
        if cancel_check():
            return _cancelled()
        progress_callback(0, 0, "正在准备…")
        plan = compile_document_batch_plan(
            self._snapshot,
            DocumentBatchRequest(
                source_paths=self._source_paths,
                output_root=self._output_root,
            ),
        )
        if cancel_check():
            return _cancelled()
        progress_callback(0, 0, "正在生成文档")
        return plan.run()


class _FileProductionRunner:
    def __init__(
        self,
        requests: tuple[ProductionExecutionRequest, ...],
    ) -> None:
        self._requests = requests

    def run(self, progress_callback, cancel_check):
        items: list[dict[str, object]] = []
        output_paths: dict[str, str] = {}
        total = len(self._requests)
        for index, request in enumerate(self._requests, start=1):
            if cancel_check():
                return _cancelled(items=items)
            outer_current, outer_total = _composite_file_batch_progress(
                index=index,
                file_count=total,
            )
            progress_callback(
                outer_current,
                outer_total,
                f"处理 {request.input_path.name}",
            )

            def _forward_file_progress(
                inner_current: int,
                inner_total: int,
                message: str,
                *,
                _index: int = index,
            ) -> None:
                current, combined_total = _composite_file_batch_progress(
                    index=_index,
                    file_count=total,
                    inner_current=inner_current,
                    inner_total=inner_total,
                )
                progress_callback(current, combined_total, message)

            result = execute_production_request(
                request,
                progress_callback=_forward_file_progress,
                cancel_check=cancel_check,
            )
            result = _attach_request_trace(result, request)
            status = str(result.get("status") or "failed")
            path = str(result.get("output_path") or "")
            items.append(
                {
                    "status": status,
                    "source_path": str(request.input_path),
                    "output_path": path,
                    "error_text": str(result.get("error_text") or ""),
                    "warnings": list(result.get("warnings") or ()),
                    "format_change_evidence": dict(
                        result.get("format_change_evidence") or {}
                    ),
                }
            )
            if path:
                output_paths[f"{index:04d}"] = path
        failed = sum(item["status"] == "failed" for item in items)
        partial = sum(item["status"] == "partial_success" for item in items)
        cancelled = sum(item["status"] == "cancelled" for item in items)
        status = (
            "success"
            if failed == 0 and partial == 0 and cancelled == 0
            else (
                "failed"
                if failed + cancelled == total
                else "partial_success"
            )
        )
        progress_callback(total * 1000, total * 1000, "多文档执行完成")
        format_change_evidence = _batch_format_change_evidence(items)
        return {
            "status": status,
            "summary": f"完成 {total - failed}/{total} 份文档",
            "output_path": (
                str(self._requests[0].output_root)
                if self._requests
                else ""
            ),
            "output_paths": output_paths,
            "items": items,
            "format_change_evidence": format_change_evidence,
            "failed_count": failed,
            "execution_route": (
                "production_with_material"
                if any(
                    item.material_snapshot is not None
                    for item in self._requests
                )
                else "production"
            ),
            "input_paths": [str(item.input_path) for item in self._requests],
            "output_root": (
                str(self._requests[0].output_root) if self._requests else ""
            ),
            "plan_id": self._requests[0].plan_id if self._requests else "",
            "template_id": (
                self._requests[0].template_id if self._requests else ""
            ),
            "error_text": (
                "部分文档执行失败" if failed else ""
            ),
        }


def build_threaded_runner(runner, *, parent=None) -> ExecutionBuildResult:
    try:
        from .execution_thread_handle import ThreadedExecutionHandle
        from .execution_worker import ExecutionWorker

        worker = ExecutionWorker(runner, parent=None)
        handle = ThreadedExecutionHandle(worker, parent=parent)
    except Exception as exc:
        return ExecutionBuildResult(
            worker=None,
            error_text=f"execution_worker_build_failed:{type(exc).__name__}:{exc}",
        )
    return ExecutionBuildResult(worker=handle)


class WorkbenchExecutionSessionController:
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
        snapshot=None,
        timeout_ms: int | None = 1000,
    ) -> list[str]:
        del snapshot
        if self._active_worker is worker:
            self._active_worker = None
        shutdown = getattr(worker, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown(timeout_ms=timeout_ms)
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution session controller",
                    "discard_worker.shutdown",
                    exc,
                )
        return []

    def build_document_worker(
        self,
        *,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        selection: MaterialRunSelection | None,
        session_overrides: dict[str, object] | None = None,
        document_type_id: str = "",
        mode_id: str,
        plan_id: str = "",
        plan_path: str = "",
        plan_source_type: str = "",
        template_id: str = "",
        template_path: str = "",
        template_source_type: str = "",
        output_root: str = "",
        document_structure_evidence: DocumentStructureEvidence | None = None,
        document_scope_decisions: tuple[RegionDecision, ...] = (),
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )
        source = self._resolve_document_path()
        if source is None:
            return ExecutionBuildResult(worker=None, cancelled=True)
        return self._build_for_paths(
            paths=(str(source),),
            template=template,
            scene=scene,
            selection=selection,
            session_overrides=session_overrides,
            document_type_id=document_type_id,
            mode_id=mode_id,
            plan_id=plan_id,
            plan_path=plan_path,
            plan_source_type=plan_source_type,
            template_id=template_id,
            template_path=template_path,
            template_source_type=template_source_type,
            output_root=output_root,
            output_roots_by_path=None,
            force_record_batch=False,
            document_structure_evidence=document_structure_evidence,
            document_scope_decisions=document_scope_decisions,
        )

    def build_record_batch_worker(
        self,
        *,
        document_paths: tuple[str, ...],
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        selection: MaterialRunSelection,
        session_overrides: dict[str, object] | None = None,
        document_type_id: str = "",
        mode_id: str,
        plan_id: str = "",
        plan_path: str = "",
        plan_source_type: str = "",
        template_id: str = "",
        template_path: str = "",
        template_source_type: str = "",
        output_root: str = "",
        document_structure_evidence: DocumentStructureEvidence | None = None,
        document_scope_decisions: tuple[RegionDecision, ...] = (),
    ) -> ExecutionBuildResult:
        return self._build_for_paths(
            paths=document_paths,
            template=template,
            scene=scene,
            selection=selection,
            session_overrides=session_overrides,
            document_type_id=document_type_id,
            mode_id=mode_id,
            plan_id=plan_id,
            plan_path=plan_path,
            plan_source_type=plan_source_type,
            template_id=template_id,
            template_path=template_path,
            template_source_type=template_source_type,
            output_root=output_root,
            output_roots_by_path=None,
            force_record_batch=True,
            document_structure_evidence=document_structure_evidence,
            document_scope_decisions=document_scope_decisions,
        )

    def build_file_batch_worker(
        self,
        *,
        document_paths: tuple[str, ...],
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        selection: MaterialRunSelection | None,
        session_overrides: dict[str, object] | None = None,
        document_type_id: str = "",
        mode_id: str,
        plan_id: str = "",
        plan_path: str = "",
        plan_source_type: str = "",
        template_id: str = "",
        template_path: str = "",
        template_source_type: str = "",
        output_root: str = "",
        output_roots_by_path: Mapping[str, str] | None = None,
        document_structure_evidence: DocumentStructureEvidence | None = None,
        document_scope_decisions: tuple[RegionDecision, ...] = (),
        **_ignored,
    ) -> ExecutionBuildResult:
        return self._build_for_paths(
            paths=document_paths,
            template=template,
            scene=scene,
            selection=selection,
            session_overrides=session_overrides,
            document_type_id=document_type_id,
            mode_id=mode_id,
            plan_id=plan_id,
            plan_path=plan_path,
            plan_source_type=plan_source_type,
            template_id=template_id,
            template_path=template_path,
            template_source_type=template_source_type,
            output_root=output_root,
            output_roots_by_path=output_roots_by_path,
            force_record_batch=False,
            document_structure_evidence=document_structure_evidence,
            document_scope_decisions=document_scope_decisions,
        )

    def _build_for_paths(
        self,
        *,
        paths: tuple[str, ...],
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
        selection: MaterialRunSelection | None,
        session_overrides: dict[str, object] | None,
        document_type_id: str,
        mode_id: str,
        plan_id: str,
        plan_path: str,
        plan_source_type: str,
        template_id: str,
        template_path: str,
        template_source_type: str,
        output_root: str,
        output_roots_by_path: Mapping[str, str] | None,
        force_record_batch: bool,
        document_structure_evidence: DocumentStructureEvidence | None,
        document_scope_decisions: tuple[RegionDecision, ...],
    ) -> ExecutionBuildResult:
        if self._active_worker is not None:
            return ExecutionBuildResult(
                worker=self._active_worker,
                already_running=True,
            )
        normalized = tuple(
            str(Path(path).expanduser().resolve())
            for path in paths
            if Path(path).expanduser().is_file()
        )
        if not normalized:
            return ExecutionBuildResult(
                worker=None,
                error_text="请选择至少一个可读取的输入文档",
            )
        if scene is None or template is None:
            return ExecutionBuildResult(
                worker=None,
                error_text="请先选择有效的处理方案和模板",
            )
        destination = resolve_workbench_output_root(output_root, normalized)
        destinations, destination_issue = _production_output_roots(
            normalized,
            base_root=destination,
            configured_root=output_root,
            output_roots_by_path=output_roots_by_path,
        )
        if destination_issue:
            return ExecutionBuildResult(
                worker=None,
                error_text=destination_issue,
            )
        requests: list[ProductionExecutionRequest] = []
        if selection is not None:
            if any(Path(path).suffix.casefold() != ".docx" for path in normalized):
                return ExecutionBuildResult(
                    worker=None,
                    error_text="资料批量执行目前只接受 DOCX 输入",
                )
            snapshot, issues = bind_workbench_material(
                selection,
                work_mode_id=mode_id,
                recipe_id="document_batch",
                scene_id=plan_id,
                document_type=document_type_id if mode_id == "official" else "",
            )
            if snapshot is None:
                return ExecutionBuildResult(
                    worker=None,
                    error_text="；".join(
                        item.message or item.code for item in issues
                    ),
                )
            if (
                not force_record_batch
                and len(normalized) > 1
                and len(selection.selected_record_ids) > 1
            ):
                return ExecutionBuildResult(
                    worker=None,
                    error_text="多文档与多资料记录需要显式映射，不能自动组合",
                )
            group_by_record = len(snapshot.records) > 1
            for path in normalized:
                source_destination = destinations[path.casefold()]
                for record in snapshot.records:
                    record_destination = source_destination
                    if group_by_record:
                        record_destination = (
                            source_destination
                            / _safe_output_component(
                                record.display_name,
                                fallback=record.record_id,
                            )
                        )
                    requests.append(
                        _production_request(
                            path=path,
                            output_root=record_destination,
                            mode_id=mode_id,
                            scene=scene,
                            template=template,
                            plan_id=plan_id,
                            plan_path=plan_path,
                            plan_source_type=plan_source_type,
                            template_id=template_id,
                            template_path=template_path,
                            template_source_type=template_source_type,
                            document_type_id=document_type_id,
                            session_overrides=session_overrides,
                            material_snapshot=(
                                project_execution_material_record_snapshot(
                                    snapshot,
                                    record.record_id,
                                )
                            ),
                            document_structure_evidence=document_structure_evidence,
                            document_scope_decisions=document_scope_decisions,
                        )
                    )
        else:
            requests.extend(
                _production_request(
                    path=path,
                    output_root=destinations[path.casefold()],
                    mode_id=mode_id,
                    scene=scene,
                    template=template,
                    plan_id=plan_id,
                    plan_path=plan_path,
                    plan_source_type=plan_source_type,
                    template_id=template_id,
                    template_path=template_path,
                    template_source_type=template_source_type,
                    document_type_id=document_type_id,
                    session_overrides=session_overrides,
                    material_snapshot=None,
                    document_structure_evidence=document_structure_evidence,
                    document_scope_decisions=document_scope_decisions,
                )
                for path in normalized
            )
        runner = (
            _ProductionRunner(requests[0])
            if len(requests) == 1
            else _FileProductionRunner(tuple(requests))
        )
        return build_threaded_runner(runner, parent=self._worker_parent)

    @staticmethod
    def start_worker(worker) -> None:
        start = getattr(worker, "start", None)
        if callable(start):
            start()
            return
        run = getattr(worker, "run", None)
        if callable(run):
            run()

    def shutdown_active_execution(
        self,
        timeout_ms: int | None = 1000,
    ) -> bool:
        worker = self._active_worker
        if worker is None:
            return True
        request_cancel = getattr(worker, "request_cancel", None)
        if callable(request_cancel):
            try:
                request_cancel()
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution session controller",
                    "worker.request_cancel",
                    exc,
                )
        shutdown = getattr(worker, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown(timeout_ms=timeout_ms)
            except Exception as exc:
                log_best_effort_shutdown_failure(
                    "execution session controller",
                    "worker.shutdown",
                    exc,
                )
        thread = getattr(worker, "_thread", None)
        is_running = getattr(thread, "isRunning", None)
        return not bool(is_running()) if callable(is_running) else True


def _composite_file_batch_progress(
    *,
    index: int,
    file_count: int,
    inner_current: int = 0,
    inner_total: int = 0,
) -> tuple[int, int]:
    """Combine one file's internal progress into a stable batch percentage."""

    safe_count = max(1, int(file_count or 0))
    safe_index = min(max(1, int(index or 1)), safe_count)
    completed_units = (safe_index - 1) * 1000
    if int(inner_total or 0) > 0:
        fraction = min(
            max(float(inner_current or 0) / float(inner_total), 0.0),
            1.0,
        )
        completed_units += int(fraction * 1000)
    return completed_units, safe_count * 1000


def _cancelled(*, items: list[dict[str, object]] | None = None):
    return {
        "status": "cancelled",
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "failed_count": 0,
        "error_text": "execution_cancelled",
        "items": list(items or ()),
    }


def _production_request(
    *,
    path: str,
    output_root: Path,
    mode_id: str,
    scene: SceneWorkspace,
    template: TemplateConfig,
    plan_id: str,
    plan_path: str,
    plan_source_type: str,
    template_id: str,
    template_path: str,
    template_source_type: str,
    document_type_id: str,
    session_overrides: dict[str, object] | None,
    material_snapshot,
    document_structure_evidence: DocumentStructureEvidence | None,
    document_scope_decisions: tuple[RegionDecision, ...],
) -> ProductionExecutionRequest:
    return ProductionExecutionRequest(
        input_path=Path(path),
        output_root=Path(output_root),
        mode_id=mode_id,
        scene=scene,
        template=template,
        plan_id=plan_id,
        plan_path=plan_path,
        plan_source_type=plan_source_type,
        template_id=template_id,
        template_path=template_path,
        template_source_type=template_source_type,
        document_type_id=(document_type_id if mode_id == "official" else ""),
        session_overrides=dict(session_overrides or {}),
        output_suffix="-formatted",
        material_snapshot=material_snapshot,
        require_format_change=True,
        document_structure_evidence=document_structure_evidence,
        document_scope_decisions=document_scope_decisions,
    )


def _production_output_roots(
    paths: tuple[str, ...],
    *,
    base_root: Path,
    configured_root: str,
    output_roots_by_path: Mapping[str, str] | None,
) -> tuple[dict[str, Path], str]:
    configured = str(configured_root or "").strip()
    base = Path(base_root).expanduser().resolve()
    provided = {
        str(key or "").casefold(): str(value or "").strip()
        for key, value in dict(output_roots_by_path or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    resolved: dict[str, Path] = {}
    seen: set[tuple[str, str]] = set()
    for raw_path in paths:
        source = Path(raw_path).expanduser().resolve()
        raw_destination = provided.get(str(source).casefold())
        destination = (
            Path(raw_destination).expanduser().resolve()
            if raw_destination
            else base
        )
        if configured and not _path_is_within(destination, base):
            return {}, f"workbench_output_path_outside_root:{destination}"
        if _path_is_within(source, destination):
            return {}, f"workbench_output_root_contains_input:{source}"
        identity = (
            str(destination).casefold(),
            source.stem.casefold(),
        )
        if identity in seen and len(paths) > 1:
            return {}, f"workbench_output_path_collision:{destination}"
        seen.add(identity)
        resolved[str(source).casefold()] = destination
    return resolved, ""


def _batch_format_change_evidence(
    items: list[dict[str, object]],
) -> dict[str, object]:
    evidence = [
        dict(item.get("format_change_evidence") or {})
        for item in items
        if item.get("format_change_evidence")
    ]
    compared = [item for item in evidence if item.get("status") == "compared"]
    unchanged = sum(not bool(item.get("format_changed")) for item in compared)
    return {
        "schema_version": "docx-format-change-batch-v1",
        "status": "compared" if len(compared) == len(items) else "partial",
        "format_changed": bool(items) and len(compared) == len(items) and unchanged == 0,
        "documents_total": len(items),
        "documents_compared": len(compared),
        "documents_unchanged": unchanged,
    }


def _attach_request_trace(
    result: dict[str, object],
    request: ProductionExecutionRequest,
) -> dict[str, object]:
    payload = dict(result)
    payload.setdefault(
        "execution_route",
        (
            "production_with_material"
            if request.material_snapshot is not None
            else "production"
        ),
    )
    payload.setdefault("input_paths", [str(request.input_path)])
    payload.setdefault("output_root", str(request.output_root))
    payload.setdefault("plan_id", request.plan_id)
    payload.setdefault("template_id", request.template_id)
    return payload


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_output_component(value: str, *, fallback: str) -> str:
    normalized = "".join(
        "_" if char in '<>:"/\\|?*' or ord(char) < 32 else char
        for char in str(value or "").strip()
    ).rstrip(" .")
    return normalized[:120] or fallback


__all__ = [
    "ExecutionBuildResult",
    "WorkbenchExecutionSessionController",
    "build_threaded_runner",
]
