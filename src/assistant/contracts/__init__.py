"""Versioned, UI-free contracts for the Form assistant."""

from src.assistant.contracts.artifacts import AssistantArtifactRef
from src.assistant.contracts.document_plan import DocumentPlan, OutputPolicy
from src.assistant.contracts.execution import ExecutionApproval, PreflightReceipt
from src.assistant.contracts.jobs import DocumentJob
from src.assistant.contracts.messages import AssistantMessage, MessageBlock
from src.assistant.contracts.permissions import (
    DisclosureGrant,
    PermissionDecision,
    ToolPermissionRequest,
    ToolRiskLevel,
)
from src.assistant.contracts.runtime import AssistantRuntimeResult, AssistantTurnRequest
from src.assistant.contracts.task_plan import (
    DeliveryContract,
    GenerationContract,
    ProductionContract,
    SourceArtifactRef,
    TaskCapabilityRef,
)

__all__ = [
    "AssistantArtifactRef",
    "AssistantMessage",
    "AssistantRuntimeResult",
    "AssistantTurnRequest",
    "DisclosureGrant",
    "DeliveryContract",
    "DocumentJob",
    "DocumentPlan",
    "ExecutionApproval",
    "GenerationContract",
    "MessageBlock",
    "OutputPolicy",
    "PermissionDecision",
    "PreflightReceipt",
    "ProductionContract",
    "SourceArtifactRef",
    "TaskCapabilityRef",
    "ToolPermissionRequest",
    "ToolRiskLevel",
]
