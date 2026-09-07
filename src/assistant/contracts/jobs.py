"""Document job state is deliberately separate from assistant turn state."""

from __future__ import annotations

from dataclasses import dataclass


JOB_DRAFT = "draft"
JOB_RESOLVING_CONTEXT = "resolving_context"
JOB_PROVIDER_RUNNING = "provider_running"
JOB_RESPONSE_WAITING = "response_waiting"
JOB_RESPONSE_READY = "response_ready"
JOB_NEEDS_ROUTE_CLARIFICATION = "needs_route_clarification"
JOB_NEEDS_DATA_DISCLOSURE = "needs_data_disclosure"
JOB_RESPONSE_CLOSED = "response_closed"
JOB_PLAN_CANDIDATE = "plan_candidate"
JOB_PLAN_READY = "plan_ready"
JOB_CONTENT_GENERATION_READY = "content_generation_ready"
JOB_CONTENT_GENERATION_RUNNING = "content_generation_running"
JOB_NEEDS_OFFICIAL_FIELD_COMPLETION = "needs_official_field_completion"
JOB_CONTENT_DRAFT_READY = "content_draft_ready"
JOB_PREFLIGHT_RUNNING = "preflight_running"
JOB_PREFLIGHT_FAILED = "preflight_failed"
JOB_NEEDS_EXECUTION_APPROVAL = "needs_execution_approval"
JOB_EXECUTION_QUEUED = "execution_queued"
JOB_EXECUTION_RUNNING = "execution_running"
JOB_SUCCESS = "success"
JOB_PARTIAL_SUCCESS = "partial_success"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

JOB_STATUSES = frozenset(
    {
        JOB_DRAFT,
        JOB_RESOLVING_CONTEXT,
        JOB_PROVIDER_RUNNING,
        JOB_RESPONSE_WAITING,
        JOB_RESPONSE_READY,
        JOB_NEEDS_ROUTE_CLARIFICATION,
        JOB_NEEDS_DATA_DISCLOSURE,
        JOB_RESPONSE_CLOSED,
        JOB_PLAN_CANDIDATE,
        JOB_PLAN_READY,
        JOB_CONTENT_GENERATION_READY,
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_NEEDS_OFFICIAL_FIELD_COMPLETION,
        JOB_CONTENT_DRAFT_READY,
        JOB_PREFLIGHT_RUNNING,
        JOB_PREFLIGHT_FAILED,
        JOB_NEEDS_EXECUTION_APPROVAL,
        JOB_EXECUTION_QUEUED,
        JOB_EXECUTION_RUNNING,
        JOB_SUCCESS,
        JOB_PARTIAL_SUCCESS,
        JOB_FAILED,
        JOB_CANCELLED,
    }
)

_ENTRY_STATUSES = frozenset(
    {
        JOB_DRAFT,
        JOB_RESOLVING_CONTEXT,
        JOB_PROVIDER_RUNNING,
        JOB_NEEDS_ROUTE_CLARIFICATION,
        JOB_NEEDS_DATA_DISCLOSURE,
        JOB_RESPONSE_CLOSED,
        JOB_PLAN_READY,
    }
)

_JOB_TRANSITIONS = {
    JOB_DRAFT: _ENTRY_STATUSES | {JOB_FAILED, JOB_CANCELLED},
    JOB_RESOLVING_CONTEXT: _ENTRY_STATUSES | {JOB_FAILED, JOB_CANCELLED},
    JOB_PROVIDER_RUNNING: {
        JOB_RESPONSE_WAITING,
        JOB_RESPONSE_READY,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_RESPONSE_WAITING: {
        JOB_PROVIDER_RUNNING,
        JOB_RESPONSE_READY,
        JOB_RESPONSE_CLOSED,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_RESPONSE_READY: _ENTRY_STATUSES | {JOB_FAILED, JOB_CANCELLED},
    JOB_NEEDS_ROUTE_CLARIFICATION: {
        JOB_PLAN_READY,
        JOB_RESPONSE_CLOSED,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_NEEDS_DATA_DISCLOSURE: {
        JOB_PROVIDER_RUNNING,
        JOB_PLAN_READY,
        JOB_CONTENT_GENERATION_READY,
        JOB_RESPONSE_CLOSED,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_RESPONSE_CLOSED: _ENTRY_STATUSES | {JOB_FAILED, JOB_CANCELLED},
    # Kept only as a migration source for sessions written before automatic
    # local-plan creation replaced the candidate click.
    JOB_PLAN_CANDIDATE: {
        JOB_PLAN_READY,
        JOB_NEEDS_ROUTE_CLARIFICATION,
        JOB_RESPONSE_CLOSED,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_PLAN_READY: {
        JOB_PLAN_READY,
        JOB_NEEDS_ROUTE_CLARIFICATION,
        JOB_NEEDS_DATA_DISCLOSURE,
        JOB_RESPONSE_CLOSED,
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_PREFLIGHT_RUNNING,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_CONTENT_GENERATION_READY: {
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_PLAN_READY,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_CONTENT_GENERATION_RUNNING: {
        JOB_NEEDS_OFFICIAL_FIELD_COMPLETION,
        JOB_CONTENT_DRAFT_READY,
        # 一条龙：确认目录后写作完成自动接管预检，允许直接进入
        # preflight_running（草稿卡仍会补发，用户无感）。
        JOB_PREFLIGHT_RUNNING,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_NEEDS_OFFICIAL_FIELD_COMPLETION: {
        JOB_CONTENT_DRAFT_READY,
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_PLAN_READY,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_CONTENT_DRAFT_READY: {
        JOB_NEEDS_DATA_DISCLOSURE,
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_PREFLIGHT_RUNNING,
        JOB_PLAN_READY,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_PREFLIGHT_RUNNING: {
        JOB_PREFLIGHT_FAILED,
        JOB_NEEDS_EXECUTION_APPROVAL,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_PREFLIGHT_FAILED: {
        JOB_PREFLIGHT_RUNNING,
        JOB_PLAN_READY,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_NEEDS_EXECUTION_APPROVAL: {
        JOB_EXECUTION_RUNNING,
        JOB_PREFLIGHT_RUNNING,
        JOB_PREFLIGHT_FAILED,
        JOB_PLAN_READY,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_EXECUTION_QUEUED: {
        JOB_EXECUTION_RUNNING,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_EXECUTION_RUNNING: {
        JOB_SUCCESS,
        JOB_PARTIAL_SUCCESS,
        JOB_FAILED,
        JOB_CANCELLED,
    },
    JOB_SUCCESS: _ENTRY_STATUSES,
    JOB_PARTIAL_SUCCESS: _ENTRY_STATUSES | {JOB_PREFLIGHT_RUNNING},
    JOB_FAILED: _ENTRY_STATUSES
    | {
        JOB_CONTENT_DRAFT_READY,
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_PREFLIGHT_RUNNING,
    },
    JOB_CANCELLED: _ENTRY_STATUSES
    | {
        JOB_CONTENT_DRAFT_READY,
        JOB_CONTENT_GENERATION_RUNNING,
        JOB_PREFLIGHT_RUNNING,
    },
}


def validate_document_job_transition(
    previous: str,
    next_status: str,
) -> str:
    """Validate one persisted status edge and return the normalized target."""

    source = str(previous or "").strip()
    target = str(next_status or "").strip()
    if not target:
        if source:
            raise ValueError("Document job status cannot be cleared")
        return ""
    if target not in JOB_STATUSES:
        raise ValueError(f"Unsupported document job status: {target!r}")
    if not source or source == target:
        return target
    if source not in JOB_STATUSES:
        raise ValueError(f"Unsupported previous document job status: {source!r}")
    if target not in _JOB_TRANSITIONS[source]:
        raise ValueError(
            f"Unsupported document job transition: {source!r} -> {target!r}"
        )
    return target


@dataclass(frozen=True, slots=True)
class DocumentJob:
    job_id: str
    session_id: str
    plan_id: str
    plan_revision: int
    status: str = JOB_DRAFT
    execution_id: str = ""
    error_text: str = ""

    def __post_init__(self) -> None:
        if self.status not in JOB_STATUSES:
            raise ValueError(f"Unsupported document job status: {self.status!r}")
        if not self.job_id or not self.session_id:
            raise ValueError("Document job identity is required")


__all__ = [name for name in globals() if name.startswith("JOB_")] + [
    "DocumentJob",
    "validate_document_job_transition",
]
