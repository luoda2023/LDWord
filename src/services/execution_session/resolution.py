"""Resolve canonical execution identity and capture its resource graph."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from .support import object_revision, resource_ref
from .builder import (
    ExecutionSessionBuildRequest,
    CapturedMaster,
    ResolvedExecutionIdentity,
    ResolvedExecutionResourceGraph,
)
from src.config.library import (
    get_scene_entry,
    get_template_entry,
    load_template_from_library,
)
from src.config.loader import ConfigLoadError
from src.config.master_library import (
    MasterSpec,
    get_master,
    resolve_official_master_for_contract,
)
from src.config.object_preflight_evidence import build_object_preflight_evidence
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)
from src.config.resource_ref import ResourceRef
from src.config.work_mode import resolve_execution_work_mode_id
from src.services.document_structure_evidence import (
    build_document_structure_evidence_from_bytes,
)


def resolve_execution_identity(
    request: ExecutionSessionBuildRequest,
) -> ResolvedExecutionIdentity:
    """Resolve caller hints once into the canonical identity for this run."""

    mode_id = resolve_execution_work_mode_id(
        request.scene,
        requested_mode_id=request.requested_mode_id,
    )
    plan_id = str(request.plan_id or "").strip()
    template_id = str(request.template_id or "").strip()

    plan_entry = (
        get_scene_entry(plan_id, mode_id=mode_id)
        if plan_id and not request.plan_path
        else None
    )
    template_entry = (
        get_template_entry(template_id, mode_id=mode_id)
        if template_id and not request.template_path
        else None
    )
    plan_path = str(
        request.plan_path or getattr(plan_entry, "path", "") or ""
    ).strip()
    template_path = str(
        request.template_path or getattr(template_entry, "path", "") or ""
    ).strip()

    material_profile_id = str(
        getattr(request.material_context, "profile_id", "") or ""
    ).strip()
    document_type_id = str(request.document_type_id or "").strip()
    requested_master_id = str(
        getattr(request.scene, "master_id", "") or ""
    ).strip()
    official_document_type_ids = _official_execution_document_type_ids(
        document_type_id,
        request.official_document_type_ids,
    )

    session_id = _new_session_id()
    if request.output_root:
        output_base = Path(request.output_root)
    elif request.input_path:
        output_base = Path(request.input_path).parent / "output"
    else:
        output_base = Path.cwd() / "output" / "batch"
    return ResolvedExecutionIdentity(
        mode_id=mode_id,
        plan_id=plan_id,
        template_id=template_id,
        plan_entry=plan_entry,
        template_entry=template_entry,
        plan_path=plan_path,
        template_path=template_path,
        material_profile_id=material_profile_id,
        document_type_id=document_type_id,
        requested_master_id=requested_master_id,
        raw_official_document_type_ids=request.official_document_type_ids,
        official_document_type_ids=official_document_type_ids,
        session_id=session_id,
        output_namespace=str(output_base / session_id),
    )


def resolve_execution_resource_graph(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> ResolvedExecutionResourceGraph:
    """Resolve and capture every resource before any validation or freezing."""

    plan_ref = resource_ref(
        "plan",
        mode_id=identity.mode_id,
        resource_id=identity.plan_id,
        source_type=(
            request.plan_source_type
            or str(getattr(identity.plan_entry, "source_type", "") or "")
        ),
        path=identity.plan_path,
        value=request.scene,
    )
    template_ref = _build_primary_template_ref(request, identity)
    (
        captured_masters,
        master_ref,
        official_master_ids,
        unresolved_master_ids,
        requested_official_master_found,
    ) = _resolve_master_resources(request, identity)
    package_ref = _build_material_package_ref(request, identity)
    input_ref, input_source_bytes = _capture_input_resource(request, identity)
    object_preflight_evidence = build_object_preflight_evidence(
        request.scene,
        request.input_path,
    )
    document_structure_evidence = build_document_structure_evidence_from_bytes(
        request.input_path,
        input_source_bytes,
        source_revision=str(getattr(input_ref, "source_revision", "") or ""),
    )
    dependent_template_refs, dependent_resource_issues = (
        _delivery_target_template_refs(
            request.scene,
            mode_id=identity.mode_id,
            primary_template_id=identity.template_id,
        )
    )
    return ResolvedExecutionResourceGraph(
        plan_ref=plan_ref,
        template_ref=template_ref,
        master_ref=master_ref,
        package_ref=package_ref,
        input_ref=input_ref,
        input_source_bytes=input_source_bytes,
        primary_master=(
            captured_masters[0].value if captured_masters else None
        ),
        captured_masters=captured_masters,
        dependent_template_refs=dependent_template_refs,
        dependent_resource_issues=tuple(dependent_resource_issues),
        official_master_ids_by_document_type=official_master_ids,
        unresolved_official_master_ids=unresolved_master_ids,
        requested_official_master_found=requested_official_master_found,
        object_preflight_evidence=object_preflight_evidence,
        document_structure_evidence=document_structure_evidence,
    )


def _build_primary_template_ref(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> ResourceRef:
    return resource_ref(
        "template",
        mode_id=identity.mode_id,
        resource_id=identity.template_id,
        source_type=(
            request.template_source_type
            or str(getattr(identity.template_entry, "source_type", "") or "")
        ),
        path=identity.template_path,
        value=request.template,
    )


def _resolve_master_resources(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> tuple[
    tuple[CapturedMaster, ...],
    ResourceRef,
    tuple[tuple[str, str], ...],
    tuple[str, ...],
    bool,
]:
    requested_official_master = (
        get_master(identity.requested_master_id, "official")
        if identity.mode_id == "official" and identity.requested_master_id
        else None
    )
    candidates, official_master_ids, unresolved_master_ids = (
        _select_master_candidates(
            request,
            identity,
            requested_official_master=requested_official_master,
        )
    )
    captured_masters = tuple(
        _capture_master_resource(
            requested_id=requested_id,
            candidate=candidate,
            mode_id=identity.mode_id,
        )
        for requested_id, candidate in candidates
    )
    if captured_masters:
        master_ref = captured_masters[0].resource_ref
    elif identity.mode_id in {"official", "exam"} or identity.requested_master_id:
        unresolved_id = (
            unresolved_master_ids[0]
            if unresolved_master_ids
            else identity.requested_master_id
        )
        master_ref = ResourceRef(
            kind="master",
            mode_id=identity.mode_id,
            resource_id=unresolved_id,
            status="missing",
            requested_id=unresolved_id,
            effective_id="",
        )
    else:
        master_ref = ResourceRef(
            kind="master",
            mode_id=identity.mode_id,
            status="not_applicable",
        )
    return (
        captured_masters,
        master_ref,
        official_master_ids,
        unresolved_master_ids,
        bool(requested_official_master),
    )


def _select_master_candidates(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
    *,
    requested_official_master: MasterSpec | None,
) -> tuple[
    tuple[tuple[str, MasterSpec], ...],
    tuple[tuple[str, str], ...],
    tuple[str, ...],
]:
    if identity.mode_id != "official" or not identity.official_document_type_ids:
        selected_master = (
            get_master(
                identity.requested_master_id,
                identity.mode_id,
                exam_config=getattr(request.scene, "exam_paper", None),
            )
            if identity.requested_master_id
            else None
        )
        candidates = (
            (
                identity.requested_master_id or selected_master.master_id,
                selected_master,
            ),
        ) if selected_master is not None else ()
        return candidates, (), ()

    mappings: list[tuple[str, str]] = []
    unresolved_ids: list[str] = []
    candidates: list[tuple[str, MasterSpec]] = []
    seen_master_ids: set[str] = set()
    for document_type_id in identity.official_document_type_ids:
        contract = get_official_document_assembly_contract(document_type_id)
        if contract is None:
            continue
        contract_master_id = str(contract.master_id or "").strip()
        effective_master = resolve_official_master_for_contract(
            contract,
            requested=requested_official_master,
        )
        if effective_master is None:
            mappings.append((document_type_id, contract_master_id))
            unresolved_ids.append(contract_master_id)
            continue
        effective_master_id = str(effective_master.master_id or "").strip()
        mappings.append((document_type_id, effective_master_id))
        if effective_master_id in seen_master_ids:
            continue
        seen_master_ids.add(effective_master_id)
        candidates.append(
            (
                identity.requested_master_id or contract_master_id,
                effective_master,
            )
        )
    return tuple(candidates), tuple(mappings), tuple(unresolved_ids)


def _capture_master_resource(
    *,
    requested_id: str,
    candidate: MasterSpec,
    mode_id: str,
) -> CapturedMaster:
    source_bytes, source_revision = _capture_file_bytes(candidate.docx_path)
    captured_ref = resource_ref(
        "master",
        mode_id=mode_id,
        resource_id=str(candidate.master_id or ""),
        source_type=str(candidate.source_type or ""),
        path=str(candidate.docx_path or ""),
        value=candidate,
        explicit_source_revision=source_revision,
    )
    captured_ref = replace(
        captured_ref,
        requested_id=requested_id or captured_ref.requested_id,
        effective_id=captured_ref.resource_id,
    )
    return CapturedMaster(
        requested_id=requested_id,
        value=candidate,
        resource_ref=captured_ref,
        source_bytes=source_bytes,
    )


def _build_material_package_ref(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> ResourceRef:
    package_id = str(
        getattr(request.material_context, "package_id", "")
        or getattr(request.material_context, "archive_id", "")
        or ""
    ).strip()
    revision = object_revision(request.material_context)
    return ResourceRef(
        kind="material_package",
        mode_id=str(
            getattr(request.material_context, "mode_id", "")
            or identity.mode_id
        ).strip(),
        resource_id=package_id,
        source_type="runtime",
        revision=revision,
        effective_revision=revision,
        status=(
            "ok" if package_id or identity.material_profile_id else "empty"
        ),
        requested_id=package_id,
        effective_id=package_id,
    )


def _capture_input_resource(
    request: ExecutionSessionBuildRequest,
    identity: ResolvedExecutionIdentity,
) -> tuple[ResourceRef, bytes | None]:
    if not request.input_path:
        return (
            ResourceRef(
                kind="input_document",
                mode_id=identity.mode_id,
                source_type="external",
                status="not_applicable",
            ),
            None,
        )
    source_bytes, source_revision = _capture_file_bytes(request.input_path)
    resource_id = Path(request.input_path).name
    if source_bytes is None or not source_revision:
        return (
            ResourceRef(
                kind="input_document",
                mode_id=identity.mode_id,
                resource_id=resource_id,
                source_type="external",
                path=request.input_path,
                status="missing",
                requested_id=resource_id,
            ),
            None,
        )
    return (
        resource_ref(
            "input_document",
            mode_id=identity.mode_id,
            resource_id=resource_id,
            source_type="external",
            path=request.input_path,
            explicit_source_revision=source_revision,
        ),
        source_bytes,
    )


def _delivery_target_template_refs(
    scene,
    *,
    mode_id: str,
    primary_template_id: str,
) -> tuple[tuple[ResourceRef, ...], list[str]]:
    refs: list[ResourceRef] = []
    issues: list[str] = []
    seen: set[str] = set()
    for preset in list(getattr(scene, "delivery_presets", []) or []):
        target_id = str(getattr(preset, "target_template_id", "") or "").strip()
        if not target_id or target_id == primary_template_id or target_id in seen:
            continue
        seen.add(target_id)
        entry = get_template_entry(target_id, mode_id=mode_id)
        path = str(getattr(entry, "path", "") or "").strip()
        source_type = str(getattr(entry, "source_type", "") or "").strip()
        try:
            target_template = load_template_from_library(
                target_id,
                mode_id=mode_id,
            )
        except (ConfigLoadError, FileNotFoundError):
            refs.append(
                ResourceRef(
                    kind="delivery_target_template",
                    mode_id=mode_id,
                    resource_id=target_id,
                    source_type=source_type,
                    path=path,
                    status="missing",
                    requested_id=target_id,
                    effective_id="",
                )
            )
            issues.append(f"dependent_template_ref_unresolved:{target_id}")
            continue
        refs.append(
            resource_ref(
                "delivery_target_template",
                mode_id=mode_id,
                resource_id=target_id,
                source_type=source_type,
                path=path,
                value=target_template,
            )
        )
    return tuple(refs), issues


def _official_execution_document_type_ids(
    document_type_id: str,
    selected_document_type_ids: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    normalized_task_type = str(document_type_id or "").strip()
    candidates = (
        selected_document_type_ids
        if normalized_task_type == "per_item"
        else ((normalized_task_type,) if normalized_task_type else ())
    )
    return tuple(
        dict.fromkeys(
            str(candidate or "").strip()
            for candidate in candidates
            if str(candidate or "").strip()
        )
    )


def _capture_file_bytes(path: str | Path) -> tuple[bytes | None, str]:
    normalized = str(path or "").strip()
    if not normalized:
        return None, ""
    try:
        payload = Path(normalized).read_bytes()
    except OSError:
        return None, ""
    return payload, _bytes_revision(payload)


def _bytes_revision(payload: bytes) -> str:
    return f"sha256:{sha256(payload).hexdigest()}"


def _new_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run_{stamp}_{uuid4().hex[:8]}"


__all__ = [
    "resolve_execution_identity",
    "resolve_execution_resource_graph",
]
