"""Build-phase contracts and immutable snapshot assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .contract import ExecutionSessionSnapshot
from src.config.master_library import MasterSpec
from src.config.resource_ref import ResourceRef


@dataclass(frozen=True, slots=True)
class ExecutionSessionBuildRequest:
    """Unresolved caller input for one snapshot build."""

    requested_mode_id: str
    scene: object
    template: object
    material_context: object
    input_path: str
    output_root: str
    plan_id: str
    plan_path: str
    plan_source_type: str
    template_id: str
    template_path: str
    template_source_type: str
    document_type_id: str
    official_document_type_ids: tuple[str, ...]
    object_preflight_confirmation_revision: str
    object_preflight_confirmation_digest: str
    document_structure_evidence: object | None
    document_scope_decisions: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class ResolvedExecutionIdentity:
    """Canonical mode, IDs, paths and namespace used by the whole build."""

    mode_id: str
    plan_id: str
    template_id: str
    plan_entry: object | None
    template_entry: object | None
    plan_path: str
    template_path: str
    material_profile_id: str
    document_type_id: str
    requested_master_id: str
    raw_official_document_type_ids: tuple[str, ...]
    official_document_type_ids: tuple[str, ...]
    session_id: str
    output_namespace: str


@dataclass(frozen=True, slots=True)
class CapturedMaster:
    requested_id: str
    value: MasterSpec
    resource_ref: ResourceRef
    source_bytes: bytes | None


@dataclass(frozen=True, slots=True)
class ResolvedExecutionResourceGraph:
    plan_ref: ResourceRef
    template_ref: ResourceRef
    master_ref: ResourceRef
    package_ref: ResourceRef
    input_ref: ResourceRef
    input_source_bytes: bytes | None
    primary_master: MasterSpec | None
    captured_masters: tuple[CapturedMaster, ...]
    dependent_template_refs: tuple[ResourceRef, ...]
    dependent_resource_issues: tuple[str, ...]
    official_master_ids_by_document_type: tuple[tuple[str, str], ...]
    unresolved_official_master_ids: tuple[str, ...]
    requested_official_master_found: bool
    object_preflight_evidence: object
    document_structure_evidence: object


@dataclass(frozen=True, slots=True)
class ObjectPreflightConfirmation:
    status: str
    source_revision: str
    evidence_digest: str
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentStructureConfirmation:
    status: str
    source_revision: str
    evidence_digest: str
    decisions: tuple[object, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidatedExecutionResourceGraph:
    graph: ResolvedExecutionResourceGraph
    confirmation: ObjectPreflightConfirmation
    structure_confirmation: DocumentStructureConfirmation
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FrozenExecutionResources:
    master_ref: ResourceRef
    input_ref: ResourceRef
    dependent_resource_refs: tuple[ResourceRef, ...]
    frozen_master: MasterSpec | None
    frozen_dependent_masters: tuple[MasterSpec, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FrozenMasterResources:
    refs: tuple[ResourceRef, ...]
    primary_master: MasterSpec | None
    dependent_masters: tuple[MasterSpec, ...]
    issues: tuple[str, ...]


def assemble_execution_session_snapshot(
    identity: ResolvedExecutionIdentity,
    validated: ValidatedExecutionResourceGraph,
    frozen: FrozenExecutionResources,
) -> ExecutionSessionSnapshot:
    graph = validated.graph
    evidence = graph.object_preflight_evidence
    confirmation = validated.confirmation
    structure_confirmation = validated.structure_confirmation
    return ExecutionSessionSnapshot(
        session_id=identity.session_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        mode_id=identity.mode_id,
        plan_ref=graph.plan_ref,
        template_ref=graph.template_ref,
        master_ref=frozen.master_ref,
        package_ref=graph.package_ref,
        input_ref=frozen.input_ref,
        output_namespace=identity.output_namespace,
        frozen_master=frozen.frozen_master,
        frozen_dependent_masters=frozen.frozen_dependent_masters,
        dependent_resource_refs=frozen.dependent_resource_refs,
        official_master_ids_by_document_type=(
            graph.official_master_ids_by_document_type
        ),
        object_preflight_applicable=evidence.applicable,
        object_preflight_blocked=evidence.blocked,
        object_preflight_confirmation_status=confirmation.status,
        object_preflight_confirmation_revision=confirmation.source_revision,
        object_preflight_confirmation_digest=confirmation.evidence_digest,
        document_structure_evidence=graph.document_structure_evidence,
        document_scope_decisions=structure_confirmation.decisions,
        structure_confirmation_status=structure_confirmation.status,
        structure_confirmation_revision=structure_confirmation.source_revision,
        structure_confirmation_digest=structure_confirmation.evidence_digest,
        document_type_id=identity.document_type_id,
        material_profile_id=identity.material_profile_id,
        issues=tuple(dict.fromkeys(frozen.issues)),
    )


__all__ = [
    "CapturedMaster",
    "ExecutionSessionBuildRequest",
    "DocumentStructureConfirmation",
    "FrozenExecutionResources",
    "FrozenMasterResources",
    "ObjectPreflightConfirmation",
    "ResolvedExecutionIdentity",
    "ResolvedExecutionResourceGraph",
    "ValidatedExecutionResourceGraph",
    "assemble_execution_session_snapshot",
]
