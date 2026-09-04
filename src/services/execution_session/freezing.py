"""Materialize immutable execution resources with transactional rollback."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from src.config.atomic_io import atomic_write_bytes
from .builder import (
    CapturedMaster,
    FrozenExecutionResources,
    FrozenMasterResources,
    ResolvedExecutionIdentity,
    ValidatedExecutionResourceGraph,
)
from .support import cleanup_frozen_path, file_sha256
from src.config.master_library import MasterSpec
from src.config.resource_ref import ResourceRef


def freeze_execution_resources(
    identity: ResolvedExecutionIdentity,
    validated: ValidatedExecutionResourceGraph,
) -> FrozenExecutionResources:
    """Freeze validated source bytes and roll back the full set on failure."""

    graph = validated.graph
    issues = list(validated.issues)
    frozen_masters = _freeze_master_resources(
        graph.captured_masters,
        output_namespace=identity.output_namespace,
        blocked=bool(issues),
    )
    issues.extend(frozen_masters.issues)
    master_ref = (
        frozen_masters.refs[0]
        if frozen_masters.refs
        else graph.master_ref
    )
    input_ref = graph.input_ref
    dependent_resource_refs = (
        *graph.dependent_template_refs,
        *frozen_masters.refs[1:],
    )
    frozen_master = frozen_masters.primary_master
    frozen_dependent_masters = frozen_masters.dependent_masters

    if input_ref.status == "ok" and not issues:
        try:
            input_ref = _materialize_frozen_input(
                input_ref,
                source_bytes=graph.input_source_bytes,
                output_namespace=identity.output_namespace,
            )
        except OSError as exc:
            input_ref = replace(input_ref, status="freeze_failed")
            issues.append(
                "input_freeze_failed:"
                f"{input_ref.resource_id}:{type(exc).__name__}"
            )
            all_master_refs = (master_ref, *frozen_masters.refs[1:])
            issues.extend(
                _cleanup_materialized_resource_refs(
                    all_master_refs,
                    output_namespace=identity.output_namespace,
                )
            )
            cleared_master_refs = tuple(
                replace(ref, frozen_path="", frozen_revision="")
                for ref in all_master_refs
            )
            if cleared_master_refs:
                master_ref = cleared_master_refs[0]
            dependent_resource_refs = (
                *graph.dependent_template_refs,
                *cleared_master_refs[1:],
            )
            frozen_master = None
            frozen_dependent_masters = ()

    return FrozenExecutionResources(
        master_ref=master_ref,
        input_ref=input_ref,
        dependent_resource_refs=tuple(dependent_resource_refs),
        frozen_master=frozen_master,
        frozen_dependent_masters=frozen_dependent_masters,
        issues=tuple(issues),
    )


def _freeze_master_resources(
    captured_masters: tuple[CapturedMaster, ...],
    *,
    output_namespace: str,
    blocked: bool,
) -> FrozenMasterResources:
    source_refs = tuple(
        captured.resource_ref for captured in captured_masters
    )
    if not captured_masters or blocked:
        return FrozenMasterResources(
            refs=source_refs,
            primary_master=None,
            dependent_masters=(),
            issues=(),
        )

    materialized_refs: list[ResourceRef] = []
    materialized_masters: list[MasterSpec] = []
    for index, captured in enumerate(captured_masters):
        try:
            frozen_ref, frozen_master = _materialize_frozen_master(
                captured.value,
                captured.resource_ref,
                source_bytes=captured.source_bytes,
                output_namespace=output_namespace,
            )
        except OSError as exc:
            refs = (
                *materialized_refs,
                replace(captured.resource_ref, status="freeze_failed"),
                *(
                    remaining.resource_ref
                    for remaining in captured_masters[index + 1 :]
                ),
            )
            issues = [
                "master_freeze_failed:"
                f"{captured.resource_ref.resource_id}:{type(exc).__name__}"
            ]
            issues.extend(
                _cleanup_materialized_resource_refs(
                    materialized_refs,
                    output_namespace=output_namespace,
                )
            )
            return FrozenMasterResources(
                refs=tuple(
                    replace(ref, frozen_path="", frozen_revision="")
                    for ref in refs
                ),
                primary_master=None,
                dependent_masters=(),
                issues=tuple(issues),
            )
        materialized_refs.append(frozen_ref)
        materialized_masters.append(frozen_master)

    return FrozenMasterResources(
        refs=tuple(materialized_refs),
        primary_master=materialized_masters[0],
        dependent_masters=tuple(materialized_masters[1:]),
        issues=(),
    )


def _cleanup_materialized_resource_refs(
    resource_refs: list[ResourceRef] | tuple[ResourceRef, ...],
    *,
    output_namespace: str,
) -> list[str]:
    issues: list[str] = []
    for resource_ref in resource_refs:
        if not resource_ref.frozen_path:
            continue
        try:
            cleanup_frozen_path(
                resource_ref.frozen_path,
                output_namespace,
            )
        except OSError as exc:
            issues.append(
                "execution_resource_cleanup_failed:"
                f"{resource_ref.kind}:{resource_ref.resource_id}:"
                f"{type(exc).__name__}"
            )
    return issues


def _materialize_frozen_master(
    master: MasterSpec,
    master_ref: ResourceRef,
    *,
    source_bytes: bytes | None,
    output_namespace: str,
) -> tuple[ResourceRef, MasterSpec]:
    digest = master_ref.source_revision.removeprefix("sha256:")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", master_ref.resource_id).strip(
        "._"
    ) or "master"
    frozen_ref = _materialize_frozen_file(
        master_ref,
        source_bytes=source_bytes,
        output_namespace=output_namespace,
        relative_path=(
            Path("masters") / f"{safe_id}-{digest[:16]}.docx"
        ),
    )
    frozen_master = replace(
        master,
        docx_path=Path(frozen_ref.frozen_path),
        execution_frozen=True,
    )
    return frozen_ref, frozen_master


def _materialize_frozen_input(
    input_ref: ResourceRef,
    *,
    source_bytes: bytes | None,
    output_namespace: str,
) -> ResourceRef:
    digest = input_ref.source_revision.removeprefix("sha256:")
    original_name = _safe_frozen_filename(input_ref.resource_id or "input.docx")
    return _materialize_frozen_file(
        input_ref,
        source_bytes=source_bytes,
        output_namespace=output_namespace,
        relative_path=Path("inputs") / digest[:16] / original_name,
    )


def _materialize_frozen_file(
    resource_ref: ResourceRef,
    *,
    source_bytes: bytes | None,
    output_namespace: str,
    relative_path: Path,
) -> ResourceRef:
    if source_bytes is None or not resource_ref.source_revision:
        raise OSError(f"{resource_ref.kind} source bytes were not captured")
    frozen_path = (
        Path(output_namespace)
        / ".execution_resources"
        / relative_path
    )
    try:
        atomic_write_bytes(frozen_path, source_bytes)
        frozen_revision = f"sha256:{file_sha256(frozen_path)}"
        if frozen_revision != resource_ref.source_revision:
            raise OSError(f"frozen {resource_ref.kind} revision mismatch")
        frozen_path.chmod(0o444)
    except OSError:
        try:
            cleanup_frozen_path(frozen_path, output_namespace)
        except OSError:
            pass
        raise
    return replace(
        resource_ref,
        frozen_path=str(frozen_path),
        frozen_revision=frozen_revision,
    )


def _safe_frozen_filename(value: str) -> str:
    raw_name = Path(str(value or "")).name.strip(" .")
    safe_name = re.sub(r"[^\w.()\[\] -]+", "_", raw_name).strip(" .")
    if not safe_name:
        return "input.docx"
    if len(safe_name) <= 160:
        return safe_name
    suffix = Path(safe_name).suffix[:12]
    return safe_name[: max(1, 160 - len(suffix))].rstrip(" .") + suffix


__all__ = ["freeze_execution_resources"]
