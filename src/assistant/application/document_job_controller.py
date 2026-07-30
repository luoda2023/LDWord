"""Plan, preflight, approval and leased Form execution orchestration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from src.assistant.adapters.production_adapter import AssistantProductionAdapter
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.application.execution_lease import (
    GLOBAL_EXECUTION_LEASE,
    ExecutionLease,
    ExecutionLeaseManager,
)
from src.assistant.application.plan_builder import FormDocumentPlanBuilder
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import ExecutionApproval, PreflightReceipt
from src.assistant.contracts.permissions import PermissionDecision, ToolRiskLevel
from src.assistant.tools.gateway import FormToolGateway
from src.assistant.tools.registry import ToolCall, ToolDefinition, ToolRegistry
from src.assistant.storage.execution_journal import (
    ExecutionJournalRecord,
    ExecutionJournalStore,
)
from src.config.material_context import MaterialExecutionContext


class DocumentJobController:
    def __init__(
        self,
        *,
        plans: FormDocumentPlanBuilder | None = None,
        production: AssistantProductionAdapter | None = None,
        leases: ExecutionLeaseManager | None = None,
        journal: ExecutionJournalStore | None = None,
    ) -> None:
        self.plans = plans or FormDocumentPlanBuilder()
        self.production = production or AssistantProductionAdapter()
        self.leases = leases or GLOBAL_EXECUTION_LEASE
        self.journal = journal or ExecutionJournalStore()

    def draft_plan(
        self,
        *,
        query: str,
        workspace: WorkspaceSnapshot,
        turn_id: str,
        previous_plan: DocumentPlan | None = None,
        route_id_override: str = "",
    ) -> DocumentPlan:
        return self.plans.build(
            query=query,
            workspace=workspace,
            turn_id=turn_id,
            previous_plan=previous_plan,
            route_id_override=route_id_override,
        )

    def preflight(
        self,
        plan: DocumentPlan,
        *,
        material_context: MaterialExecutionContext | None = None,
    ) -> PreflightReceipt:
        call_id = uuid4().hex
        registry = ToolRegistry(
            (
                ToolDefinition(
                    "build_preflight_preview",
                    "读取输入及配置并生成确定性执行前检查",
                    ToolRiskLevel.LOCAL_CONTENT_READ,
                    lambda args: self.production.build_preflight(
                        DocumentPlan.from_dict(args["plan"]),
                        material_context=material_context,
                    ).to_dict(),
                ),
            )
        )
        result = FormToolGateway(registry).invoke(
            ToolCall(
                call_id=call_id,
                session_id="preflight-local",
                turn_id=plan.created_by_turn_id,
                tool_name="build_preflight_preview",
                arguments={"plan": plan.to_dict()},
            ),
            decision=PermissionDecision(request_id=call_id, allowed=True),
        )
        if result.status != "success":
            raise RuntimeError(str(result.error.get("message") or "assistant_preflight_failed"))
        return PreflightReceipt.from_dict(result.output)

    @staticmethod
    def approve(
        *,
        session_id: str,
        plan: DocumentPlan,
        preflight: PreflightReceipt,
    ) -> ExecutionApproval:
        if not preflight.ready or preflight.plan_fingerprint != plan.fingerprint:
            raise ValueError("Only the current ready preflight can be approved")
        return ExecutionApproval(
            approval_id=uuid4().hex,
            session_id=session_id,
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            preflight_hash=preflight.evidence_hash,
            input_hash=preflight.input_hash,
            output_root=preflight.output_root,
            overwrite_policy=("replace_confirmed" if plan.output_policy.overwrite else "deny"),
            approved_at=datetime.now(timezone.utc).isoformat(),
        )

    def execute(
        self,
        *,
        session_id: str,
        plan: DocumentPlan,
        preflight: PreflightReceipt,
        approval: ExecutionApproval,
        material_context: MaterialExecutionContext | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        execution_id: str = "",
    ) -> dict[str, object]:
        stable_execution_id = execution_id or uuid4().hex
        try:
            existing = self.journal.load(stable_execution_id)
        except FileNotFoundError:
            existing = None
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {
                "status": "failed",
                "output_path": "",
                "output_paths": {},
                "report_paths": [],
                "failed_count": 0,
                "artifact_failure_count": 0,
                "error_text": f"assistant_execution_journal_unavailable:{type(exc).__name__}",
            }
        if existing is not None:
            same_owner = bool(
                existing.session_id == session_id
                and existing.plan_id == plan.plan_id
                and existing.plan_revision == plan.revision
                and existing.plan_fingerprint == plan.fingerprint
            )
            if not same_owner:
                return {
                    "status": "failed",
                    "output_path": "",
                    "output_paths": {},
                    "report_paths": [],
                    "failed_count": 0,
                    "artifact_failure_count": 0,
                    "error_text": "assistant_execution_id_collision",
                }
            if existing.status != "running":
                replayed = dict(existing.result)
                replayed["assistant_execution_replayed"] = True
                return replayed
            return {
                "status": "failed",
                "output_path": "",
                "output_paths": {},
                "report_paths": [],
                "failed_count": 0,
                "artifact_failure_count": 0,
                "error_text": "assistant_execution_incomplete_requires_recovery",
            }
        lease = ExecutionLease(
            execution_id=stable_execution_id,
            session_id=session_id,
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        if not self.leases.acquire(lease):
            current = self.leases.current
            return {
                "status": "failed",
                "output_path": "",
                "output_paths": {},
                "report_paths": [],
                "failed_count": 0,
                "artifact_failure_count": 0,
                "error_text": "assistant_execution_lease_busy",
                "active_execution_id": current.execution_id if current is not None else "",
                "active_session_id": current.session_id if current is not None else "",
            }
        try:
            self.journal.begin(
                ExecutionJournalRecord(
                    execution_id=stable_execution_id,
                    session_id=session_id,
                    plan_id=plan.plan_id,
                    plan_revision=plan.revision,
                    plan_fingerprint=plan.fingerprint,
                    status="running",
                    started_at=lease.acquired_at,
                )
            )
            registry = ToolRegistry(
                (
                    ToolDefinition(
                        "run_document_production",
                        "通过 Form 生产引擎创建本地文档产物",
                        ToolRiskLevel.DOCUMENT_PRODUCTION,
                        lambda args: self.production.execute_approved_plan(
                            DocumentPlan.from_dict(args["plan"]),
                            PreflightReceipt.from_dict(args["preflight"]),
                            ExecutionApproval.from_dict(args["approval"]),
                            material_context=material_context,
                            progress_callback=progress_callback,
                            cancel_check=cancel_check,
                        ),
                    ),
                )
            )
            call = ToolCall(
                call_id=approval.approval_id,
                session_id=session_id,
                turn_id=plan.created_by_turn_id,
                tool_name="run_document_production",
                arguments={
                    "plan": plan.to_dict(),
                    "preflight": preflight.to_dict(),
                    "approval": approval.to_dict(),
                },
                idempotency_key=stable_execution_id,
            )
            tool_result = FormToolGateway(registry).invoke(
                call,
                decision=PermissionDecision(
                    request_id=approval.approval_id,
                    allowed=True,
                ),
            )
            if tool_result.status == "success":
                result = dict(tool_result.output)
            else:
                result = {
                    "status": "failed",
                    "output_path": "",
                    "output_paths": {},
                    "report_paths": [],
                    "failed_count": 0,
                    "artifact_failure_count": 0,
                    "error_text": str(
                        tool_result.error.get("message")
                        or "assistant_production_tool_failed"
                    ),
                }
            result["assistant_execution_id"] = stable_execution_id
            result["assistant_session_id"] = session_id
            terminal_status = str(result.get("status") or "failed")
            if terminal_status not in {"success", "partial_success", "failed", "cancelled"}:
                terminal_status = "failed"
            try:
                self.journal.finish(
                    stable_execution_id,
                    status=terminal_status,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    result=result,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                result["assistant_journal_error"] = str(exc) or type(exc).__name__
                if terminal_status == "success":
                    result["status"] = "partial_success"
            return result
        finally:
            self.leases.release(stable_execution_id)


__all__ = ["DocumentJobController"]
