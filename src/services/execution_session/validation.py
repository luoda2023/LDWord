"""Validate a captured execution-session resource graph fail-closed."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from docx import Document

from src.config.document_scope import (
    coerce_document_scope_policy,
    selectable_document_scope_roles,
)
from src.config.execution_config_integrity import execution_config_integrity_issues
from src.config.execution_feature_state import execution_plan_is_enabled
from src.config.material_schema_registry import resolve_material_schema_ids
from src.config.official_document_profiles import get_official_document_profile
from src.config.resource_ref import ResourceRef
from src.config.work_mode import execution_work_mode_issue
from src.services.delivery_template_validation import (
    unsupported_delivery_target_template_issue,
)
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    RegionDecision,
    document_structure_evidence_is_current,
    pending_document_structure_review_roles,
    validate_region_decisions,
)
from src.shared.engine.document_scope_runtime import bind_document_scope

from .builder import (
    DocumentStructureConfirmation,
    ExecutionSessionBuildRequest,
    ObjectPreflightConfirmation,
    ResolvedExecutionIdentity,
    ResolvedExecutionResourceGraph,
    ValidatedExecutionResourceGraph,
)


def validate_execution_resource_graph(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
    graph: ResolvedExecutionResourceGraph,
) -> ValidatedExecutionResourceGraph:
    """Apply every fail-closed invariant before immutable bytes are written."""

    confirmation = _validate_object_preflight_confirmation(request, graph)
    structure_confirmation = _validate_document_structure_confirmation(
        request,
        identity,
        graph,
    )
    issues = [
        *graph.dependent_resource_issues,
        *confirmation.issues,
        *structure_confirmation.issues,
    ]
    mode_issue = execution_work_mode_issue(
        request.scene,
        requested_mode_id=request.requested_mode_id,
    )
    if mode_issue:
        issues.append(mode_issue)
    issues.extend(_validate_explicit_plan_selection(request, identity))
    issues.extend(_validate_delivery_target_templates(request, identity))
    issues.extend(_validate_primary_resource_refs(identity, graph))
    issues.extend(_validate_master_resources(request, identity, graph))
    issues.extend(
        execution_config_integrity_issues(
            request.scene,
            entity_data=(getattr(request.material_context, "entity_data", {}) or {}),
        )
    )
    issues.extend(_validate_material_scope(request, identity, graph))
    issues.extend(_validate_input_resource(identity, graph.input_ref))
    issues.extend(_validate_official_document_types(identity))
    return ValidatedExecutionResourceGraph(
        graph=graph,
        confirmation=confirmation,
        structure_confirmation=structure_confirmation,
        issues=tuple(issues),
    )


def _validate_document_structure_confirmation(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
    graph: ResolvedExecutionResourceGraph,
) -> DocumentStructureConfirmation:
    if (
        not execution_plan_is_enabled(request.scene)
        or identity.mode_id in {"official", "exam"}
    ):
        return _not_applicable_document_structure_confirmation()

    evidence = graph.document_structure_evidence
    requested_evidence = request.document_structure_evidence
    decisions = tuple(request.document_scope_decisions or ())
    issues: list[str] = []
    if not isinstance(evidence, DocumentStructureEvidence) or not evidence.ready:
        issues.extend(
            tuple(getattr(evidence, "issues", ()) or ())
            or ("document_structure_evidence_not_ready",)
        )
        return DocumentStructureConfirmation(
            status="failed",
            source_revision=str(getattr(evidence, "source_revision", "") or ""),
            evidence_digest=str(getattr(evidence, "evidence_digest", "") or ""),
            decisions=(),
            issues=tuple(dict.fromkeys(issues)),
        )

    issues.extend(
        _requested_document_structure_evidence_issues(
            requested_evidence,
            evidence,
            input_path=request.input_path,
        )
    )

    if any(not isinstance(decision, RegionDecision) for decision in decisions):
        issues.append("document_structure_decision_invalid")
        decisions = ()

    policy = coerce_document_scope_policy(
        getattr(request.scene, "document_scope", None)
    )
    included_roles = policy.included_roles(identity.mode_id)
    captured_input_revision = str(
        getattr(graph.input_ref, "source_revision", "") or ""
    ).strip()
    if captured_input_revision != evidence.source_revision:
        issues.append("document_structure_captured_input_mismatch")
    issues.extend(
        validate_region_decisions(
            evidence,
            decisions,
            allowed_roles=tuple(
                dict.fromkeys(
                    (
                        *selectable_document_scope_roles(identity.mode_id),
                        *(region.role_id for region in evidence.regions),
                    )
                )
            ),
        )
    )
    pending = pending_document_structure_review_roles(
        evidence,
        decisions,
        included_roles=included_roles,
    )
    if pending:
        issues.append("document_structure_review_required:" + ",".join(pending))

    if not issues:
        issues.extend(
            _document_structure_binding_issues(
                graph,
                evidence,
                decisions,
                policy,
                mode_id=identity.mode_id,
                included_roles=included_roles,
            )
        )
    return _document_structure_confirmation_result(
        evidence,
        decisions,
        issues,
        pending=bool(pending),
    )


def _not_applicable_document_structure_confirmation() -> DocumentStructureConfirmation:
    return DocumentStructureConfirmation(
        status="not_applicable",
        source_revision="",
        evidence_digest="",
        decisions=(),
        issues=(),
    )


def _requested_document_structure_evidence_issues(
    requested_evidence,
    captured_evidence: DocumentStructureEvidence,
    *,
    input_path,
) -> list[str]:
    if requested_evidence is None:
        return []
    if not isinstance(requested_evidence, DocumentStructureEvidence):
        return ["document_structure_confirmation_invalid"]
    if not document_structure_evidence_is_current(
        requested_evidence,
        input_path,
    ):
        return ["document_structure_confirmation_stale"]
    if requested_evidence.evidence_digest != captured_evidence.evidence_digest:
        return ["document_structure_confirmation_digest_mismatch"]
    return []


def _document_structure_binding_issues(
    graph: ResolvedExecutionResourceGraph,
    evidence: DocumentStructureEvidence,
    decisions: tuple[RegionDecision, ...],
    policy,
    *,
    mode_id: str,
    included_roles: tuple[str, ...],
) -> list[str]:
    if not graph.input_source_bytes:
        return ["document_structure_input_unavailable"]
    try:
        binding = bind_document_scope(
            Document(BytesIO(graph.input_source_bytes)),
            evidence,
            decisions,
            policy,
            mode_id=mode_id,
        )
    except Exception as exc:
        return [f"document_structure_binding_failed:{exc}"]
    if not any(
        region.role_id in included_roles and not region.excluded
        for region in binding.regions
    ):
        return ["document_scope_effective_regions_missing"]
    return []


def _document_structure_confirmation_result(
    evidence: DocumentStructureEvidence,
    decisions: tuple[RegionDecision, ...],
    issues: list[str],
    *,
    pending: bool,
) -> DocumentStructureConfirmation:
    status = (
        "review_required"
        if issues and pending
        else "failed"
        if issues
        else "user_confirmed"
        if decisions
        else "auto_accepted"
    )
    return DocumentStructureConfirmation(
        status=status,
        source_revision=evidence.source_revision,
        evidence_digest=evidence.evidence_digest,
        decisions=decisions,
        issues=tuple(dict.fromkeys(issues)),
    )


def _validate_explicit_plan_selection(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> list[str]:
    issues: list[str] = []
    scene_plan_id = str(getattr(request.scene, "scene_id", "") or "").strip()
    if not identity.plan_id:
        issues.append("plan_ref_missing")
    elif not scene_plan_id:
        issues.append("plan_identity_missing")
    elif scene_plan_id != identity.plan_id:
        issues.append(f"plan_identity_mismatch:{identity.plan_id}:{scene_plan_id}")

    compatible_template_ids = {
        str(value or "").strip()
        for value in getattr(request.scene, "compatible_template_ids", ()) or ()
        if str(value or "").strip()
    }
    if not identity.template_id:
        issues.append("template_ref_missing")
    elif identity.template_id not in compatible_template_ids:
        issues.append(f"runtime_template_not_compatible:{identity.template_id}")
    return issues


def _validate_delivery_target_templates(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> list[str]:
    """Block V1 presets that claim an unimplemented alternate render template."""

    issue = unsupported_delivery_target_template_issue(
        request.scene,
        primary_template_id=identity.template_id,
    )
    return [issue] if issue else []


def _validate_object_preflight_confirmation(
    request: ExecutionSessionBuildRequest,
    graph: ResolvedExecutionResourceGraph,
) -> ObjectPreflightConfirmation:
    evidence = graph.object_preflight_evidence
    confirmed_revision = request.object_preflight_confirmation_revision
    confirmation_digest = request.object_preflight_confirmation_digest
    issues: list[str] = []
    status = "not_applicable"
    if not evidence.applicable:
        if confirmation_digest or confirmed_revision:
            issues.append("object_preflight_confirmation_not_applicable")
        return ObjectPreflightConfirmation(
            status=status,
            source_revision=confirmed_revision,
            evidence_digest=confirmation_digest,
            issues=tuple(issues),
        )

    if evidence.blocked:
        issues.append("object_preflight_blocked")
        status = "blocked"
    if not confirmed_revision:
        issues.append("object_preflight_confirmation_revision_missing")
    if not confirmation_digest:
        issues.append("object_preflight_confirmation_digest_missing")

    revision_is_stale = bool(confirmed_revision) and (
        graph.input_ref.source_revision != confirmed_revision
        or evidence.source_revision != confirmed_revision
    )
    if revision_is_stale:
        issues.append("object_preflight_confirmation_stale:input_revision")
    digest_is_invalid = bool(confirmation_digest) and (
        re.fullmatch(r"sha256:[0-9a-f]{64}", confirmation_digest) is None
    )
    digest_is_mismatch = bool(confirmation_digest) and (
        not digest_is_invalid and confirmation_digest != evidence.evidence_digest
    )
    if digest_is_invalid:
        issues.append("object_preflight_confirmation_digest_invalid")
    elif digest_is_mismatch:
        issues.append("object_preflight_confirmation_digest_mismatch")

    if not evidence.blocked:
        if not confirmed_revision or not confirmation_digest:
            status = "missing"
        elif revision_is_stale:
            status = "stale"
        elif digest_is_invalid:
            status = "invalid"
        elif digest_is_mismatch:
            status = "mismatch"
        else:
            status = "confirmed"
    return ObjectPreflightConfirmation(
        status=status,
        source_revision=confirmed_revision,
        evidence_digest=confirmation_digest,
        issues=tuple(issues),
    )


def _validate_primary_resource_refs(
    identity: ResolvedExecutionIdentity,
    graph: ResolvedExecutionResourceGraph,
) -> list[str]:
    issues: list[str] = []
    if not identity.plan_id:
        issues.append("plan_ref_missing")
    elif graph.plan_ref.status != "ok":
        issues.append(f"plan_ref_unresolved:{identity.plan_id}")
    if not identity.template_id:
        issues.append("template_ref_missing")
    elif (
        graph.template_ref.requested_id
        and graph.template_ref.requested_id != graph.template_ref.effective_id
    ):
        issues.append(f"template_ref_unresolved:{graph.template_ref.requested_id}")
    elif identity.template_entry is None and not _existing_file(identity.template_path):
        issues.append(f"template_ref_unresolved:{identity.template_id}")
    return issues


def _validate_master_resources(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
    graph: ResolvedExecutionResourceGraph,
) -> list[str]:
    if not execution_plan_is_enabled(request.scene):
        return []
    issues: list[str] = []
    if identity.mode_id in {"official", "exam"} and not identity.requested_master_id:
        issues.append("master_ref_missing")
    if identity.mode_id in {"official", "exam"} and graph.primary_master is None:
        unresolved_id = (
            graph.master_ref.resource_id
            or identity.requested_master_id
            or identity.mode_id
        )
        issues.append(f"master_ref_unresolved:{unresolved_id}")
    if (
        identity.mode_id == "official"
        and identity.requested_master_id
        and not graph.requested_official_master_found
    ):
        issues.append(f"master_ref_unresolved:{identity.requested_master_id}")
    for captured in graph.captured_masters:
        if captured.resource_ref.status != "ok":
            issues.append(f"master_file_unresolved:{captured.resource_ref.resource_id}")
    for unresolved_id in graph.unresolved_official_master_ids:
        issues.append(f"master_ref_unresolved:{unresolved_id}")
    for captured in graph.captured_masters:
        compatible_templates = tuple(
            getattr(
                captured.value,
                "compatible_template_config_ids",
                (),
            )
            or ()
        )
        if (
            compatible_templates
            and identity.template_id
            and identity.template_id not in compatible_templates
        ):
            issues.append(
                "master_template_incompatible:"
                f"{captured.value.master_id}:{identity.template_id}"
            )
    return issues


def _validate_material_scope(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
    graph: ResolvedExecutionResourceGraph,
) -> list[str]:
    material_context = request.material_context
    issues: list[str] = []
    compatible = getattr(material_context, "is_compatible_with", None)
    if callable(compatible) and not compatible(
        mode_id=identity.mode_id,
        scene_id=identity.plan_id,
    ):
        issues.append("material_scope_incompatible")
    compatible_profiles = tuple(
        getattr(material_context, "compatible_profile_ids", ()) or ()
    )
    normalized_profile = identity.material_profile_id.split(":", 1)[-1]
    if (
        compatible_profiles
        and normalized_profile
        and normalized_profile not in compatible_profiles
    ):
        issues.append(f"material_profile_incompatible:{normalized_profile}")
    package_schemas = set(getattr(material_context, "material_schema_ids", ()) or ())
    input_profile = getattr(request.scene, "input_source_profile", None)
    plan_schemas = set(
        resolve_material_schema_ids(
            str(getattr(input_profile, "material_schema_id", "") or ""),
            list(getattr(input_profile, "material_schema_ids", ()) or ()),
        )
    )
    if package_schemas and plan_schemas and not package_schemas.issubset(plan_schemas):
        issues.append(
            "material_schema_incompatible:"
            + ",".join(sorted(package_schemas - plan_schemas))
        )
    compatible_master_families = tuple(
        getattr(material_context, "compatible_master_families", ()) or ()
    )
    master_family = str(getattr(graph.primary_master, "family", "") or "")
    if (
        compatible_master_families
        and master_family
        and master_family not in compatible_master_families
    ):
        issues.append(f"material_master_incompatible:{master_family}")
    return issues


def _validate_input_resource(
    identity: ResolvedExecutionIdentity,
    input_ref: ResourceRef,
) -> list[str]:
    if input_ref.status == "not_applicable" and identity.mode_id != "official":
        return ["input_document_unresolved"]
    if input_ref.status not in {"ok", "not_applicable"}:
        return ["input_document_unresolved"]
    return []


def official_document_type_applicability_issue(
    mode_id: str,
    document_type_id: str,
) -> str:
    """Return the stable error for an official-only identity in another mode."""

    normalized_mode_id = str(mode_id or "").strip()
    normalized_document_type_id = str(document_type_id or "").strip()
    if not normalized_document_type_id or normalized_mode_id == "official":
        return ""
    return (
        "official_document_type_not_applicable:"
        f"{normalized_mode_id or 'missing'}:{normalized_document_type_id}"
    )


def _validate_official_document_types(
    identity: ResolvedExecutionIdentity,
) -> list[str]:
    applicability_issue = official_document_type_applicability_issue(
        identity.mode_id,
        identity.document_type_id,
    )
    if applicability_issue:
        return [applicability_issue]
    if identity.mode_id != "official":
        return []
    issues: list[str] = []
    if not identity.document_type_id:
        issues.append("official_document_type_missing")
    elif (
        identity.document_type_id == "per_item"
        and not identity.official_document_type_ids
    ):
        issues.append("official_document_type_set_missing")
    elif identity.document_type_id == "per_item" and any(
        not value for value in identity.raw_official_document_type_ids
    ):
        issues.append("official_document_type_missing")
    elif (
        identity.document_type_id != "per_item"
        and get_official_document_profile(identity.document_type_id) is None
    ):
        issues.append(f"official_document_type_unknown:{identity.document_type_id}")
    for document_type_id in identity.official_document_type_ids:
        if get_official_document_profile(document_type_id) is None:
            issues.append(f"official_document_type_unknown:{document_type_id}")
    return issues


def _existing_file(path: str) -> bool:
    return bool(path) and Path(path).is_file()


__all__ = [
    "official_document_type_applicability_issue",
    "validate_execution_resource_graph",
]
