"""Semantic attachment roles derived from the pre-provider request decision."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.assistant.application.request_policy import (
    POLICY_DOCUMENT_ACTION,
    RequestPolicyDecision,
)
from src.assistant.contracts.task_plan import (
    SOURCE_ROLE_PRODUCTION_INPUT,
    SOURCE_ROLE_REFERENCE_MATERIAL,
    SOURCE_ROLE_STANDARD_FORMAT_REFERENCE,
)


def bind_policy_attachment_roles(
    refs: Iterable[Mapping[str, object]],
    decision: RequestPolicyDecision,
) -> tuple[dict[str, object], ...]:
    """Bind one explicit role per attachment before provider disclosure."""

    rows = [dict(item) for item in refs]
    for row in rows:
        explicit_role = str(row.get("semantic_role") or "")
        role_source = str(row.get("semantic_role_source") or "")
        if (
            explicit_role == SOURCE_ROLE_STANDARD_FORMAT_REFERENCE
            and role_source != "assistant_intent"
        ):
            continue
        if explicit_role == SOURCE_ROLE_STANDARD_FORMAT_REFERENCE:
            role = explicit_role
            source = role_source or "assistant_intent"
        elif decision.kind == POLICY_DOCUMENT_ACTION:
            role = (
                SOURCE_ROLE_REFERENCE_MATERIAL
                if decision.capability.generation.required
                else SOURCE_ROLE_PRODUCTION_INPUT
            )
            source = "request_policy"
        else:
            role = SOURCE_ROLE_REFERENCE_MATERIAL
            source = "request_policy"
        row["semantic_role"] = role
        row["semantic_role_source"] = source
    return tuple(rows)


__all__ = ["bind_policy_attachment_roles"]
