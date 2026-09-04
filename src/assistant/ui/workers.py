"""Qt signal bridges for provider turns and local document production threads."""

from __future__ import annotations

from threading import Event, Thread

from src.assistant.application.document_job_controller import DocumentJobController
from src.assistant.application.content_generation_service import (
    AssistantContentGenerationService,
    ContentGenerationRequest,
)
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import ExecutionApproval, PreflightReceipt
from src.assistant.contracts.runtime import (
    TURN_FAILED,
    AssistantRuntimeResult,
    AssistantTurnRequest,
)
from src.assistant.runtime.cancellation import AssistantCancellationToken
from src.assistant.runtime.turn_runner import AssistantTurnRunner
from src.application.materials.execution import ExecutionMaterialSnapshot
from src.qt_api import QObject, Signal


class AssistantTurnWorker(QObject):
    event_received = Signal(object)
    finished = Signal(object)

    def __init__(self, runner: AssistantTurnRunner, request: AssistantTurnRequest, parent=None) -> None:
        super().__init__(parent)
        self.runner = runner
        self.request = request
        self.cancellation = AssistantCancellationToken()
        self.workspace_snapshot = None
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Assistant turn worker is already running")
        self._thread = Thread(target=self._run, name=f"assistant-turn-{self.request.turn_id[:8]}", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self.cancellation.cancel()

    def shutdown(self, timeout_ms: int = 3000) -> bool:
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0, timeout_ms) / 1000)
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            result = self.runner.run(
                self.request,
                emit=self.event_received.emit,
                cancellation=self.cancellation,
            )
        except Exception as exc:
            # Workspace/prompt/baseline I/O happens before provider streaming
            # and may otherwise terminate the daemon thread without a finished
            # signal, leaving the composer permanently busy.
            result = AssistantRuntimeResult(
                status=TURN_FAILED,
                visible_text="",
                provider_audit={
                    "provider_profile_id": self.request.provider_profile_id,
                    "model_id": self.request.model_id,
                },
                error={
                    "category": "internal",
                    "message": str(exc) or type(exc).__name__,
                },
            )
        self.finished.emit(result)


class PreflightWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        controller: DocumentJobController,
        *,
        session_id: str,
        plan: DocumentPlan,
        material_snapshot: ExecutionMaterialSnapshot | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.session_id = session_id
        self.plan = plan
        self.material_snapshot = (
            material_snapshot
            if isinstance(material_snapshot, ExecutionMaterialSnapshot)
            else None
        )
        self._cancel_event = Event()
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Preflight worker is already running")
        self._thread = Thread(
            target=self._run,
            name=f"assistant-preflight-{self.plan.plan_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self.cancel()
        if self._thread is None:
            return True
        self._thread.join(max(0, timeout_ms) / 1000)
        return not self._thread.is_alive()

    def _run(self) -> None:
        if self._cancel_event.is_set():
            self.failed.emit("assistant_preflight_cancelled")
            return
        try:
            receipt = self.controller.preflight(
                self.plan,
                material_snapshot=self.material_snapshot,
            )
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)
            return
        if self._cancel_event.is_set():
            self.failed.emit("assistant_preflight_cancelled")
            return
        self.finished.emit(receipt)


class DocumentExecutionWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)

    def __init__(
        self,
        controller: DocumentJobController,
        *,
        session_id: str,
        plan: DocumentPlan,
        preflight: PreflightReceipt,
        approval: ExecutionApproval,
        material_snapshot: ExecutionMaterialSnapshot | None,
        execution_id: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.session_id = session_id
        self.plan = plan
        self.preflight = preflight
        self.approval = approval
        self.material_snapshot = material_snapshot
        self.execution_id = execution_id
        self._cancel_event = Event()
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Document execution worker is already running")
        self._thread = Thread(
            target=self._run,
            name=f"assistant-production-{self.execution_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0, timeout_ms) / 1000)
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            result = self.controller.execute(
                session_id=self.session_id,
                plan=self.plan,
                preflight=self.preflight,
                approval=self.approval,
                material_snapshot=self.material_snapshot,
                progress_callback=self.progress.emit,
                cancel_check=self._cancel_event.is_set,
                execution_id=self.execution_id,
            )
        except Exception as exc:
            result = {
                "status": "failed",
                "output_path": "",
                "output_paths": {},
                "report_paths": [],
                "failed_count": 0,
                "artifact_failure_count": 0,
                "error_text": str(exc) or type(exc).__name__,
                "assistant_execution_id": self.execution_id,
                "assistant_session_id": self.session_id,
            }
        self.finished.emit(result)


class ContentGenerationWorker(QObject):
    delta = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: AssistantContentGenerationService,
        request: ContentGenerationRequest,
        gateway,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.request = request
        self.gateway = gateway
        self.cancellation = AssistantCancellationToken()
        self._thread: Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Content generation worker is already running")
        self._thread = Thread(
            target=self._run,
            name=f"assistant-content-{self.request.turn_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self.cancellation.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self.cancel()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0, timeout_ms) / 1000)
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            draft = self.service.generate(
                self.request,
                self.gateway,
                cancellation=self.cancellation,
                delta_callback=self.delta.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)
            return
        self.finished.emit(draft)


__all__ = [
    "AssistantTurnWorker",
    "ContentGenerationWorker",
    "DocumentExecutionWorker",
    "PreflightWorker",
]
