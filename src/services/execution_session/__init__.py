"""Immutable evidence for one fully resolved execution resource graph."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from . import builder, freezing, resolution, validation
from .contract import ExecutionSessionSnapshot
from .support import (
    cleanup_frozen_path as _cleanup_frozen_path,
    file_sha256 as _file_sha256,
    object_revision as _object_revision,
    path_identity as _path_identity,
    resource_ref as _resource_ref,
)
from src.config.master_library import MasterSpec
from src.config.resource_ref import ResourceRef
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    RegionDecision,
)


official_document_type_applicability_issue = (
    validation.official_document_type_applicability_issue
)


def build_execution_session_snapshot(
    *,
    mode_id: str,
    scene,
    template,
    material_context,
    input_path: str | Path,
    output_root: str | Path = "",
    plan_id: str = "",
    plan_path: str = "",
    plan_source_type: str = "",
    template_id: str = "",
    template_path: str = "",
    template_source_type: str = "",
    document_type_id: str = "",
    official_document_type_ids: tuple[str, ...] | list[str] = (),
    object_preflight_confirmation_revision: str = "",
    object_preflight_confirmation_digest: str = "",
    document_structure_evidence: DocumentStructureEvidence | None = None,
    document_scope_decisions: tuple[RegionDecision, ...] | list[RegionDecision] = (),
    session_overrides: dict[str, object] | None = None,
) -> ExecutionSessionSnapshot:
    """Freeze requested/effective resources and validate their scope."""

    request = builder.ExecutionSessionBuildRequest(
        requested_mode_id=str(mode_id or "").strip(),
        scene=scene,
        template=template,
        material_context=material_context,
        input_path=str(input_path or "").strip(),
        output_root=str(output_root or "").strip(),
        plan_id=str(plan_id or "").strip(),
        plan_path=str(plan_path or "").strip(),
        plan_source_type=str(plan_source_type or "").strip(),
        template_id=str(template_id or "").strip(),
        template_path=str(template_path or "").strip(),
        template_source_type=str(template_source_type or "").strip(),
        document_type_id=str(document_type_id or "").strip(),
        official_document_type_ids=tuple(
            str(value or "").strip() for value in official_document_type_ids
        ),
        object_preflight_confirmation_revision=str(
            object_preflight_confirmation_revision or ""
        ).strip(),
        object_preflight_confirmation_digest=str(
            object_preflight_confirmation_digest or ""
        ).strip(),
        document_structure_evidence=document_structure_evidence,
        document_scope_decisions=tuple(document_scope_decisions or ()),
    )
    identity = resolution.resolve_execution_identity(request)
    graph = resolution.resolve_execution_resource_graph(request, identity)
    validated = validation.validate_execution_resource_graph(
        request,
        identity,
        graph,
    )
    frozen = freezing.freeze_execution_resources(identity, validated)
    snapshot = builder.assemble_execution_session_snapshot(
        identity,
        validated,
        frozen,
    )
    return replace(
        snapshot,
        session_overrides_revision=_object_revision(
            dict(session_overrides or {})
        ),
    )


def validate_ready_session_bindings(
    snapshot: ExecutionSessionSnapshot,
    *,
    scene,
    template,
    material_context,
    output_namespace: str | Path,
    session_overrides: dict[str, object] | None = None,
) -> tuple[str, ...]:
    """Prove that a ready receipt still describes the runtime inputs."""

    if not isinstance(snapshot, ExecutionSessionSnapshot):
        return ("execution_session_binding_unproven:snapshot",)
    if not snapshot.ready:
        return tuple(
            dict.fromkeys(("execution_session_not_ready", *snapshot.issues))
        )

    issues: list[str] = []
    bindings = (
        ("scene", snapshot.plan_ref.effective_revision, scene),
        ("template", snapshot.template_ref.effective_revision, template),
        (
            "material_context",
            snapshot.package_ref.effective_revision,
            material_context,
        ),
    )
    for kind, expected_revision, value in bindings:
        expected = str(expected_revision or "").strip()
        if not expected:
            issues.append(f"execution_session_binding_unproven:{kind}")
            continue
        if expected != _object_revision(value):
            issues.append(f"execution_session_binding_drift:{kind}")

    expected_output = _path_identity(snapshot.output_namespace)
    if not expected_output:
        issues.append("execution_session_binding_unproven:output_namespace")
    elif expected_output != _path_identity(output_namespace):
        issues.append("execution_session_binding_drift:output_namespace")

    expected_overrides = str(
        snapshot.session_overrides_revision or ""
    ).strip()
    if not expected_overrides:
        issues.append("execution_session_binding_unproven:session_overrides")
    elif expected_overrides != _object_revision(dict(session_overrides or {})):
        issues.append("execution_session_binding_drift:session_overrides")
    return tuple(dict.fromkeys(issues))


def execution_session_resource_ref(
    snapshot: ExecutionSessionSnapshot,
    *,
    kind: str,
    resource_id: str,
) -> ResourceRef | None:
    """Return one frozen ref from the exact execution resource graph."""

    normalized_kind = str(kind or "").strip()
    normalized_id = str(resource_id or "").strip()
    direct_refs = (
        snapshot.plan_ref,
        snapshot.template_ref,
        snapshot.master_ref,
        snapshot.package_ref,
        snapshot.input_ref,
    )
    for resource_ref in (*direct_refs, *snapshot.dependent_resource_refs):
        if (
            resource_ref.kind == normalized_kind
            and resource_ref.resource_id == normalized_id
        ):
            return resource_ref
    return None


def assert_execution_resource_matches(
    expected: ResourceRef,
    *,
    value,
    path: str | Path = "",
    verify_source: bool = True,
) -> None:
    """Fail closed when a re-resolved runtime resource differs from its receipt."""

    current = _resource_ref(
        expected.kind,
        mode_id=expected.mode_id,
        resource_id=expected.resource_id,
        source_type=expected.source_type,
        path=str(path or ""),
        value=value,
    )
    prefix = f"execution_resource_drift:{expected.kind}:{expected.resource_id}"
    if verify_source:
        if _path_identity(expected.path) != _path_identity(current.path):
            raise RuntimeError(f"{prefix}:path")
        if expected.source_revision != current.source_revision:
            raise RuntimeError(f"{prefix}:source_revision")
    if not expected.effective_revision:
        raise RuntimeError(
            f"execution_resource_unproven:{expected.kind}:{expected.resource_id}"
        )
    if expected.effective_revision != current.effective_revision:
        raise RuntimeError(f"{prefix}:effective_revision")


def execution_session_frozen_master(
    snapshot: ExecutionSessionSnapshot,
    *,
    resource_id: str = "",
) -> MasterSpec | None:
    """Return the exact session-owned master after verifying its frozen bytes."""

    requested_id = str(resource_id or "").strip()
    master_refs = (
        snapshot.master_ref,
        *(
            resource_ref
            for resource_ref in snapshot.dependent_resource_refs
            if resource_ref.kind == "master"
        ),
    )
    expected = snapshot.master_ref
    if requested_id:
        expected = next(
            (
                resource_ref
                for resource_ref in master_refs
                if resource_ref.resource_id == requested_id
            ),
            None,
        )
        if expected is None:
            raise RuntimeError(
                f"execution_resource_unproven:master:{requested_id}:resource_ref"
            )
    if expected.status == "not_applicable":
        return None
    expected_id = str(expected.resource_id or "").strip()
    frozen_masters = (
        snapshot.frozen_master,
        *snapshot.frozen_dependent_masters,
    )
    master = next(
        (
            candidate
            for candidate in frozen_masters
            if candidate is not None
            and str(candidate.master_id or "").strip() == expected_id
        ),
        None,
    )
    if master is None:
        raise RuntimeError(
            f"execution_resource_unproven:master:{expected_id}:frozen_copy"
        )
    if str(getattr(master, "master_id", "") or "").strip() != expected_id:
        raise RuntimeError(
            f"execution_resource_drift:master:{expected_id}:effective_revision"
        )
    if _path_identity(getattr(master, "docx_path", "")) != _path_identity(
        expected.frozen_path
    ):
        raise RuntimeError(
            f"execution_resource_drift:master:{expected_id}:frozen_path"
        )
    _verified_frozen_resource_path(expected)
    if not master.execution_frozen:
        raise RuntimeError(
            f"execution_resource_unproven:master:{expected_id}:frozen_identity"
        )
    source_identity = replace(
        master,
        docx_path=Path(expected.path),
        execution_frozen=False,
    )
    if _object_revision(source_identity) != expected.effective_revision:
        raise RuntimeError(
            f"execution_resource_drift:master:{expected_id}:effective_revision"
        )
    return master


def execution_session_frozen_official_master(
    snapshot: ExecutionSessionSnapshot,
    *,
    document_type_id: str,
) -> MasterSpec:
    """Return the contract master frozen for one official document type."""

    normalized_type = str(document_type_id or "").strip()
    master_id = dict(snapshot.official_master_ids_by_document_type).get(
        normalized_type,
        "",
    )
    if not master_id:
        raise RuntimeError(
            "execution_resource_unproven:official_master:"
            f"{normalized_type or 'missing'}:document_type"
        )
    master = execution_session_frozen_master(
        snapshot,
        resource_id=master_id,
    )
    if master is None:
        raise RuntimeError(
            f"execution_resource_unproven:official_master:{normalized_type}:master"
        )
    return master


def execution_session_frozen_input_path(
    snapshot: ExecutionSessionSnapshot,
) -> Path | None:
    """Return the immutable input bytes owned by this execution session."""

    expected = snapshot.input_ref
    if expected.status == "not_applicable":
        return None
    if expected.status != "ok":
        raise RuntimeError(
            "execution_resource_unproven:input_document:"
            f"{expected.resource_id}:status:{expected.status}"
        )
    return _verified_frozen_resource_path(expected)


def _verified_frozen_resource_path(expected: ResourceRef) -> Path:
    kind = str(expected.kind or "resource").strip() or "resource"
    resource_id = str(expected.resource_id or "").strip()
    prefix = f"{kind}:{resource_id}"
    if not expected.frozen_path or not expected.frozen_revision:
        raise RuntimeError(
            f"execution_resource_unproven:{prefix}:frozen_copy"
        )
    if (
        expected.source_revision
        and expected.frozen_revision != expected.source_revision
    ):
        raise RuntimeError(
            f"execution_resource_drift:{prefix}:frozen_receipt"
        )
    frozen_path = Path(expected.frozen_path)
    if not frozen_path.is_file():
        raise RuntimeError(
            f"execution_resource_missing:{prefix}:frozen_copy"
        )
    frozen_revision = f"sha256:{_file_sha256(frozen_path)}"
    if frozen_revision != expected.frozen_revision:
        raise RuntimeError(
            f"execution_resource_drift:{prefix}:frozen_revision"
        )
    return frozen_path


def cleanup_execution_session_resources(
    snapshot: ExecutionSessionSnapshot,
) -> tuple[str, ...]:
    """Remove only files materialized inside this session's owned namespace."""

    issues: list[str] = []
    refs = (
        snapshot.input_ref,
        snapshot.master_ref,
        *snapshot.dependent_resource_refs,
    )
    for resource_ref in refs:
        frozen_path = str(resource_ref.frozen_path or "").strip()
        if not frozen_path:
            continue
        try:
            _cleanup_frozen_path(frozen_path, snapshot.output_namespace)
        except OSError as exc:
            issues.append(
                "execution_resource_cleanup_failed:"
                f"{resource_ref.kind}:{resource_ref.resource_id}:{type(exc).__name__}"
            )
    return tuple(issues)


def execution_value_revision(value) -> str:
    """Return the canonical revision used by execution resource receipts."""

    return _object_revision(value)


__all__ = [
    "ExecutionSessionSnapshot",
    "ResourceRef",
    "assert_execution_resource_matches",
    "build_execution_session_snapshot",
    "cleanup_execution_session_resources",
    "execution_session_frozen_input_path",
    "execution_session_frozen_master",
    "execution_session_frozen_official_master",
    "execution_value_revision",
    "execution_session_resource_ref",
    "official_document_type_applicability_issue",
    "validate_ready_session_bindings",
]
