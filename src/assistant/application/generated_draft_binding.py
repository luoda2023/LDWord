"""Bind a validated generated artifact to a plan without UI-owned workflow logic."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.assistant.adapters.content_generation_adapter import (
    GeneratedDraft,
    generated_draft_source_ref,
    generated_draft_trace_refs,
)
from src.assistant.contracts.document_plan import DocumentPlan


def bind_generated_draft(
    plan: DocumentPlan,
    draft: GeneratedDraft,
) -> DocumentPlan:
    expected_kind = str(plan.generation_contract.artifact_kind or "").strip()
    actual_kind = str(draft.artifact_kind or "").strip()
    if not plan.generation_contract.required:
        raise ValueError("generated_draft_not_required_by_plan")
    if not expected_kind or actual_kind != expected_kind:
        raise ValueError(
            f"generated_draft_kind_mismatch:{expected_kind or 'none'}:{actual_kind or 'none'}"
        )

    source = generated_draft_source_ref(draft)
    expected_role = str(plan.production_contract.input_role or "").strip()
    if not expected_role or source.role != expected_role:
        raise ValueError(
            f"generated_draft_role_mismatch:{expected_role or 'none'}:{source.role}"
        )

    retained_sources = tuple(
        item
        for item in plan.source_artifacts
        if item.role != expected_role
    )
    legacy_input = {
        "path": source.path,
        "name": source.name or Path(source.path).name,
        "source": "assistant_generated_draft",
        "draft_id": draft.draft_id,
        "artifact_id": source.artifact_id,
        "artifact_kind": actual_kind,
        "schema_id": source.schema_id,
        "digest": source.digest,
    }
    return replace(
        plan,
        revision=plan.revision + 1,
        input_document_ref=legacy_input,
        scene_ref={**dict(plan.scene_ref), "generation_mode": "generated_draft"},
        source_artifacts=(*retained_sources, source),
        content_fragment_refs=generated_draft_trace_refs(draft),
    )


__all__ = ["bind_generated_draft"]
