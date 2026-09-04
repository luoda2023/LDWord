"""Bind an exact repository revision selected by the live application."""

from __future__ import annotations

from src.application.materials.contracts import get_package_material_contract
from src.application.materials.execution import (
    MaterialRunBindRequest,
    MaterialRunBindResult,
    bind_material_run,
)
from src.domain.materials import MaterialIssue, MaterialRunSelection
from src.infrastructure.materials.repository import MaterialPackageRepository


def bind_repository_material_run(
    repository: MaterialPackageRepository,
    selection: MaterialRunSelection,
    *,
    work_mode_id: str,
    recipe_id: str,
    scene_id: str = "",
    document_type: str = "",
) -> MaterialRunBindResult:
    """Load by package ID and exact revision, then freeze the selected run.

    The source directory is repository metadata, never part of package identity.
    A missing or changed revision is an explicit bind failure; there is no
    fallback to another package or to the newest revision.
    """

    entry = next(
        (
            item
            for item in repository.list_entries(work_mode_id=work_mode_id)
            if item.package_id == selection.package_ref.package_id
            and item.revision == selection.package_ref.revision
            and item.is_available
        ),
        None,
    )
    if entry is None:
        return MaterialRunBindResult(
            issues=(
                MaterialIssue(
                    code="material.bind.repository_revision_unavailable",
                    path="selection.package_ref",
                    message="资料包或其精确版本已不可用，请重新确认本次运行选择。",
                ),
            )
        )
    try:
        package_snapshot = repository.load(
            work_mode_id=work_mode_id,
            source_type=entry.source_type,
            package_id=entry.package_id,
        )
        contract = get_package_material_contract(package_snapshot.package)
        return bind_material_run(
            MaterialRunBindRequest(
                package=package_snapshot.package,
                package_revision=package_snapshot.ref.revision,
                source_type=package_snapshot.source_type,
                selection=selection,
                contract=contract,
                recipe_id=recipe_id,
                scene_id=scene_id,
                work_mode_id=work_mode_id,
                document_type=document_type,
            ),
            object_path=lambda object_ref: repository.object_path(
                package_snapshot,
                object_ref,
            ),
        )
    except Exception as exc:
        return MaterialRunBindResult(
            issues=(
                MaterialIssue(
                    code="material.bind.repository_failure",
                    path="selection.package_ref",
                    message=f"{type(exc).__name__}: {exc}",
                ),
            )
        )


__all__ = ["bind_repository_material_run"]
