"""Authoritative execution-gate semantics shared by Workbench projections.

The gate deliberately separates three different outcomes:

* warnings keep execution available;
* blockers make execution unavailable;
* confirmations keep execution eligible but require an explicit user choice.

Keeping these states in one immutable model prevents UI copy, issue badges, and
runtime policy from inventing different meanings for the same finding.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.config.execution_failure_policy import (
    EXECUTION_FAILURE_POLICY_VALUES,
    normalize_execution_failure_policy,
)
from src.ui.adapters.workbench_issue_models import (
    ISSUE_TERMINAL_STATUS_VALUES,
    WorkbenchIssueItem,
)

@dataclass(frozen=True, slots=True)
class ExecutionGateAction:
    """One explicit next action associated with an execution-gate decision."""

    label: str
    target_type: str
    target_key: str = ""

    @property
    def available(self) -> bool:
        return bool(self.label.strip() and self.target_type.strip())


@dataclass(frozen=True, slots=True)
class ExecutionGateDecision:
    """Single source of truth for whether and how execution may continue."""

    can_run: bool = True
    requires_confirmation: bool = False
    blocking_reasons: tuple[str, ...] = ()
    warning_reasons: tuple[str, ...] = ()
    confirmation_reasons: tuple[str, ...] = ()
    primary_action: ExecutionGateAction | None = None

    def __post_init__(self) -> None:
        if self.blocking_reasons and self.can_run:
            raise ValueError("blocking reasons require can_run=False")
        if not self.can_run and not self.blocking_reasons:
            raise ValueError("can_run=False requires at least one blocking reason")
        if self.requires_confirmation and not self.can_run:
            raise ValueError("a blocked decision cannot request confirmation")
        if self.requires_confirmation and not self.confirmation_reasons:
            raise ValueError(
                "requires_confirmation=True requires at least one confirmation reason"
            )

    @property
    def ready_to_start(self) -> bool:
        """Whether execution may start immediately without another user choice."""

        return self.can_run and not self.requires_confirmation

    @property
    def state(self) -> str:
        """Stable compact state for UI projections and tests."""

        if not self.can_run:
            return "blocked"
        if self.requires_confirmation:
            return "confirmation"
        if self.warning_reasons:
            return "warning"
        return "ready"


def decide_execution_gate(
    *,
    warning_reasons: Iterable[object] = (),
    blocking_reasons: Iterable[object] = (),
    confirmation_reasons: Iterable[object] = (),
    primary_action: ExecutionGateAction | None = None,
) -> ExecutionGateDecision:
    """Build a valid decision from explicitly classified reasons.

    Blockers dominate confirmations. Confirmation reasons are retained as
    evidence, but ``requires_confirmation`` becomes true only when execution is
    otherwise eligible.
    """

    warnings = _clean_reasons(warning_reasons)
    blockers = _clean_reasons(blocking_reasons)
    confirmations = _clean_reasons(confirmation_reasons)
    can_run = not blockers
    return ExecutionGateDecision(
        can_run=can_run,
        requires_confirmation=can_run and bool(confirmations),
        blocking_reasons=blockers,
        warning_reasons=warnings,
        confirmation_reasons=confirmations,
        primary_action=primary_action,
    )


def decide_execution_gate_for_policy(
    reasons: Iterable[object],
    *,
    failure_policy: object = "warn",
    primary_action: ExecutionGateAction | None = None,
) -> ExecutionGateDecision:
    """Apply one persisted warn/block/confirm policy to a set of findings."""

    normalized_reasons = _clean_reasons(reasons)
    try:
        policy = normalize_execution_failure_policy(failure_policy)
    except ValueError as exc:
        return decide_execution_gate(
            blocking_reasons=(*normalized_reasons, str(exc)),
            primary_action=primary_action,
        )
    if policy == "block":
        return decide_execution_gate(
            blocking_reasons=normalized_reasons,
            primary_action=primary_action,
        )
    if policy == "confirm":
        return decide_execution_gate(
            confirmation_reasons=normalized_reasons,
            primary_action=primary_action,
        )
    return decide_execution_gate(
        warning_reasons=normalized_reasons,
        primary_action=primary_action,
    )


def execution_gate_decision_from_issues(
    items: Iterable[WorkbenchIssueItem],
    *,
    confirmation_issue_ids: Iterable[object] = (),
    primary_action: ExecutionGateAction | None = None,
) -> ExecutionGateDecision:
    """Project active structured issues into the authoritative gate model.

    Confirmation is opt-in by issue id. A non-blocking issue is otherwise a
    warning, so informational findings cannot silently disable execution.
    """

    confirmation_ids = set(_clean_reasons(confirmation_issue_ids))
    warnings: list[str] = []
    blockers: list[str] = []
    confirmations: list[str] = []
    for item in items or ():
        if not isinstance(item, WorkbenchIssueItem):
            continue
        status = str(item.status or "open").strip().lower()
        if status in ISSUE_TERMINAL_STATUS_VALUES:
            continue
        reason = _issue_reason(item)
        if not reason:
            continue
        if item.blocking:
            blockers.append(reason)
        elif item.issue_id in confirmation_ids:
            confirmations.append(reason)
        else:
            warnings.append(reason)
    return decide_execution_gate(
        warning_reasons=warnings,
        blocking_reasons=blockers,
        confirmation_reasons=confirmations,
        primary_action=primary_action,
    )


def _issue_reason(item: WorkbenchIssueItem) -> str:
    title = " ".join(str(item.title or "").strip().split())
    summary = " ".join(str(item.summary or "").strip().split())
    if title and summary:
        return f"{title}：{summary}"
    return title or summary


def _clean_reasons(values: Iterable[object]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        values = (values,)
    result: list[str] = []
    for value in values or ():
        reason = " ".join(str(value or "").strip().split())
        if reason and reason not in result:
            result.append(reason)
    return tuple(result)


__all__ = [
    "EXECUTION_FAILURE_POLICY_VALUES",
    "ExecutionGateAction",
    "ExecutionGateDecision",
    "decide_execution_gate",
    "decide_execution_gate_for_policy",
    "execution_gate_decision_from_issues",
    "normalize_execution_failure_policy",
]
