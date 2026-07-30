"""Synchronous production-execution facade shared by non-GUI entry points.

The authoritative production runner is service-owned and Qt-free.  Headless
callers execute it directly, then apply the same pure terminal-payload contract
used by the GUI worker.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass, field, replace
from pathlib import Path

from src.services.execution_session import (
    ExecutionSessionSnapshot,
    build_execution_session_snapshot,
    cleanup_execution_session_resources,
    execution_session_frozen_input_path,
)
from src.config.material_context import MaterialExecutionContext
from src.config.object_preflight_evidence import build_object_preflight_evidence
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import scene_uses_exam_paper_surface
from src.config.template import TemplateConfig
from src.config.work_mode import execution_work_mode_issue, resolve_work_mode_id
from src.services.execution_result_contract import (
    execution_result_status,
    normalize_execution_result,
)
from src.services.execution_session_result import (
    attach_cleanup_issues,
    attach_execution_session,
)
from src.services.production_runtime import execution_runtime


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class ProductionExecutionRequest:
    input_path: Path
    output_root: Path
    mode_id: str
    scene: SceneWorkspace
    template: TemplateConfig
    plan_id: str
    plan_path: str = ""
    plan_source_type: str = ""
    template_id: str = ""
    template_path: str = ""
    template_source_type: str = ""
    document_type_id: str = ""
    output_suffix: str = "_formatted"
    session_overrides: Mapping[str, object] = field(default_factory=dict)
    material_context: MaterialExecutionContext = field(
        default_factory=MaterialExecutionContext
    )


def execute_production_request(
    request: ProductionExecutionRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict[str, object]:
    """Freeze one request, execute the GUI production path, and always clean."""

    input_path = Path(request.input_path).expanduser()
    output_root = Path(request.output_root).expanduser()
    preflight_error = _request_path_error(
        input_path,
        output_root,
        mode_id=request.mode_id,
        scene=request.scene,
    )
    if preflight_error:
        return _terminal_payload("failed", preflight_error)

    snapshot: ExecutionSessionSnapshot | None = None
    payload: dict[str, object] | None = None
    cleanup_issues: tuple[str, ...] = ()
    try:
        runtime_scene = copy.deepcopy(request.scene)
        mode_issue = execution_work_mode_issue(
            runtime_scene,
            requested_mode_id=request.mode_id,
        )
        if mode_issue:
            return _terminal_payload("failed", mode_issue)
        runtime_request = replace(
            request,
            mode_id=resolve_work_mode_id(
                runtime_scene,
                requested_mode_id=request.mode_id,
            ),
            scene=runtime_scene,
            template=copy.deepcopy(request.template),
            material_context=request.material_context.clone(),
            session_overrides=dict(request.session_overrides),
        )
        object_preflight_evidence = build_object_preflight_evidence(
            runtime_request.scene,
            input_path,
        )
        snapshot = build_execution_session_snapshot(
            mode_id=runtime_request.mode_id,
            scene=runtime_request.scene,
            template=runtime_request.template,
            material_context=runtime_request.material_context,
            input_path=input_path,
            output_root=output_root,
            plan_id=runtime_request.plan_id,
            plan_path=runtime_request.plan_path,
            plan_source_type=runtime_request.plan_source_type,
            template_id=runtime_request.template_id,
            template_path=runtime_request.template_path,
            template_source_type=runtime_request.template_source_type,
            document_type_id=runtime_request.document_type_id,
            object_preflight_confirmation_revision=(
                object_preflight_evidence.source_revision
            ),
            object_preflight_confirmation_digest=(
                object_preflight_evidence.evidence_digest
            ),
            session_overrides=dict(runtime_request.session_overrides),
        )
        if not snapshot.ready:
            payload = _terminal_payload(
                "failed",
                "；".join(snapshot.issues) or "execution_session_not_ready",
                snapshot=snapshot,
            )
        elif cancel_check is not None and cancel_check():
            payload = _terminal_payload(
                "cancelled",
                "execution_cancelled_before_start",
                snapshot=snapshot,
            )
        else:
            payload = _execute_frozen_session(
                runtime_request,
                snapshot,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
    except KeyboardInterrupt:
        payload = _terminal_payload(
            "cancelled",
            "execution_cancelled_by_keyboard_interrupt",
            snapshot=snapshot,
        )
    except Exception as exc:
        payload = _terminal_payload(
            "failed",
            str(exc) or type(exc).__name__,
            snapshot=snapshot,
        )
    finally:
        if snapshot is not None:
            try:
                cleanup_issues = cleanup_execution_session_resources(snapshot)
            except Exception as exc:  # cleanup must not hide the terminal result
                cleanup_issues = (
                    f"execution_resource_cleanup_failed:session:{type(exc).__name__}",
                )

    if payload is None:
        payload = _terminal_payload(
            "failed",
            "production_execution_returned_no_terminal_payload",
            snapshot=snapshot,
        )
    if snapshot is not None and not str(
        payload.get("execution_session_path") or ""
    ).strip():
        execution_session = (
            payload.get("execution_session")
            if isinstance(payload.get("execution_session"), Mapping)
            else None
        )
        attach_execution_session(
            payload,
            execution_session,
            snapshot=snapshot,
        )
    if cleanup_issues:
        attach_cleanup_issues(payload, cleanup_issues, snapshot=snapshot)
    return payload


def _execute_frozen_session(
    request: ProductionExecutionRequest,
    snapshot: ExecutionSessionSnapshot,
    *,
    progress_callback: ProgressCallback | None,
    cancel_check: CancelCheck | None,
) -> dict[str, object]:
    """Run the service-owned runner synchronously and normalize its payload."""

    frozen_input = execution_session_frozen_input_path(snapshot)
    if frozen_input is None:
        raise RuntimeError("execution_session_frozen_input_missing")
    runner = execution_runtime.WorkbenchProductionRunner(
        doc_path=str(frozen_input),
        template=request.template,
        scene=request.scene,
        session_overrides=dict(request.session_overrides),
        material_context=request.material_context,
        output_dir=snapshot.output_namespace,
        output_suffix=request.output_suffix,
        execution_session=snapshot,
    )
    progress = progress_callback or (lambda _current, _total, _message: None)
    cancelled = cancel_check or (lambda: False)
    result = runner.run(progress, cancelled)
    payload = normalize_execution_result(result, execution_result_status(result))
    execution_session = (
        result.get("execution_session")
        if isinstance(result, Mapping)
        and isinstance(result.get("execution_session"), Mapping)
        else None
    )
    attach_execution_session(
        payload,
        execution_session,
        snapshot=snapshot,
    )
    return payload


def _request_path_error(
    input_path: Path,
    output_root: Path,
    *,
    mode_id: str = "",
    scene: SceneWorkspace | None = None,
) -> str:
    if not input_path.is_file():
        return f"input_document_missing:{input_path}"
    suffix = input_path.suffix.casefold()
    exam_markdown = (
        suffix in {".md", ".markdown"}
        and scene_uses_exam_paper_surface(scene, mode_id=mode_id)
    )
    if suffix != ".docx" and not exam_markdown:
        return f"input_document_unsupported:{input_path.suffix}"
    try:
        if input_path.resolve() == output_root.resolve():
            return "output_root_overwrites_input_document"
    except OSError as exc:
        return f"execution_path_resolution_failed:{type(exc).__name__}"
    if output_root.exists() and not output_root.is_dir():
        return f"output_root_is_not_directory:{output_root}"
    return ""


def _terminal_payload(
    status: str,
    error_text: str,
    *,
    snapshot: ExecutionSessionSnapshot | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": str(status),
        "output_path": "",
        "output_paths": {},
        "report_paths": [],
        "failed_count": 0,
        "artifact_failure_count": 0,
        "error_text": str(error_text or ""),
    }
    if snapshot is not None:
        payload["execution_session"] = snapshot.to_dict()
    return payload


__all__ = [
    "ProductionExecutionRequest",
    "execute_production_request",
]
