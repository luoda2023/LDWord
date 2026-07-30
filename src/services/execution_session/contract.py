"""Immutable contracts shared by execution-session service phases and consumers."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config.master_library import MasterSpec
from src.config.resource_ref import ResourceRef
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    RegionDecision,
)


@dataclass(frozen=True, slots=True)
class ExecutionSessionSnapshot:
    session_id: str
    created_at: str
    mode_id: str
    plan_ref: ResourceRef
    template_ref: ResourceRef
    master_ref: ResourceRef
    package_ref: ResourceRef
    input_ref: ResourceRef
    output_namespace: str
    session_overrides_revision: str = ""
    frozen_master: MasterSpec | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    frozen_dependent_masters: tuple[MasterSpec, ...] = field(
        default=(),
        repr=False,
        compare=False,
    )
    dependent_resource_refs: tuple[ResourceRef, ...] = ()
    official_master_ids_by_document_type: tuple[tuple[str, str], ...] = ()
    object_preflight_applicable: bool = False
    object_preflight_blocked: bool = False
    object_preflight_confirmation_status: str = "not_applicable"
    object_preflight_confirmation_revision: str = ""
    object_preflight_confirmation_digest: str = ""
    document_structure_evidence: DocumentStructureEvidence | None = field(
        default=None,
        repr=False,
    )
    document_scope_decisions: tuple[RegionDecision, ...] = ()
    structure_confirmation_status: str = "not_applicable"
    structure_confirmation_revision: str = ""
    structure_confirmation_digest: str = ""
    document_type_id: str = ""
    material_profile_id: str = ""
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "mode_id": self.mode_id,
            "plan_ref": self.plan_ref.to_dict(),
            "template_ref": self.template_ref.to_dict(),
            "master_ref": self.master_ref.to_dict(),
            "package_ref": self.package_ref.to_dict(),
            "input_ref": self.input_ref.to_dict(),
            "output_namespace": self.output_namespace,
            "session_overrides_revision": self.session_overrides_revision,
            "dependent_resource_refs": [
                resource_ref.to_dict()
                for resource_ref in self.dependent_resource_refs
            ],
            "official_master_ids_by_document_type": {
                document_type_id: master_id
                for document_type_id, master_id in (
                    self.official_master_ids_by_document_type
                )
            },
            "object_preflight_confirmation": {
                "status": self.object_preflight_confirmation_status,
                "applicable": self.object_preflight_applicable,
                "blocked": self.object_preflight_blocked,
                "source_revision": self.object_preflight_confirmation_revision,
                "evidence_digest": self.object_preflight_confirmation_digest,
            },
            "document_structure_confirmation": {
                "status": self.structure_confirmation_status,
                "source_revision": self.structure_confirmation_revision,
                "evidence_digest": self.structure_confirmation_digest,
                "decisions": [
                    {
                        "role_id": decision.role_id,
                        "action": decision.action,
                        "start_anchor": (
                            {
                                "source_index": decision.start_anchor.source_index,
                                "text_digest": decision.start_anchor.text_digest,
                                "previous_text_digest": (
                                    decision.start_anchor.previous_text_digest
                                ),
                                "next_text_digest": (
                                    decision.start_anchor.next_text_digest
                                ),
                                "occurrence": decision.start_anchor.occurrence,
                                "preview_text": decision.start_anchor.preview_text,
                            }
                            if decision.start_anchor is not None
                            else None
                        ),
                    }
                    for decision in self.document_scope_decisions
                ],
            },
            "document_type_id": self.document_type_id,
            "material_profile_id": self.material_profile_id,
            "issues": list(self.issues),
            "status": "ready" if self.ready else "blocked",
        }


__all__ = ["ExecutionSessionSnapshot"]
