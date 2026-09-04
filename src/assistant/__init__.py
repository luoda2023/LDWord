"""LDWord AI assistant subsystem.

The package owns neutral assistant contracts and orchestration.  Product facts
and document production remain owned by the existing Form services and are
reachable only through explicit adapters/tools.
"""

from src.assistant.contracts.messages import AssistantMessage, MessageBlock
from src.assistant.contracts.runtime import AssistantRuntimeResult, AssistantTurnRequest

__all__ = [
    "AssistantMessage",
    "AssistantRuntimeResult",
    "AssistantTurnRequest",
    "MessageBlock",
]
