"""Resolved document/material target shared by workbench and preview UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.master_library import get_master
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)


@dataclass(frozen=True, slots=True)
class ExecutionPlaceholderBinding:
    """One explicit assembly-contract binding; never an inferred alias."""

    placeholder_key: str
    field_key: str
    required: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionTarget:
    """Concrete input and placeholder host for the next execution."""

    mode_id: str = "custom"
    document_path: str = ""
    placeholder_source_kind: str = "none"
    placeholder_source_path: str = ""
    placeholder_source_label: str = ""
    master_id: str = ""
    master_path: str = ""
    placeholder_bindings: tuple[ExecutionPlaceholderBinding, ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def has_placeholder_source(self) -> bool:
        return bool(self.placeholder_source_path)

    @property
    def is_structured_assembly(self) -> bool:
        return self.placeholder_source_kind == "structured"

    def binding_field_key(self, placeholder_key: str) -> str:
        target = str(placeholder_key or "")
        for binding in self.placeholder_bindings:
            if binding.placeholder_key == target:
                return binding.field_key
        return target

    def binding_required(self, placeholder_key: str) -> bool | None:
        target = str(placeholder_key or "")
        for binding in self.placeholder_bindings:
            if binding.placeholder_key == target:
                return binding.required
        return None


def resolve_execution_target(
    *,
    mode_id: str,
    scene=None,
    document_path: str = "",
    official_document_type_id: str = "",
) -> ExecutionTarget:
    """Resolve the placeholder host without treating format JSON as a DOCX."""

    normalized_mode = str(mode_id or "").strip() or "custom"
    normalized_document = str(document_path or "").strip()

    if normalized_mode == "official":
        profile_id = str(official_document_type_id or "").strip()
        if not profile_id:
            return ExecutionTarget(
                mode_id=normalized_mode,
                document_path=normalized_document,
                placeholder_source_kind="unresolved_master",
                issues=("official_document_type_missing",),
            )
        contract = get_official_document_assembly_contract(profile_id)
        if contract is None:
            return ExecutionTarget(
                mode_id=normalized_mode,
                document_path=normalized_document,
                placeholder_source_kind="unresolved_master",
                issues=(f"official_document_type_unknown:{profile_id}",),
            )
        requested_master_id = str(
            getattr(scene, "master_id", "") or ""
        ).strip()
        master = (
            get_master(requested_master_id, "official")
            if requested_master_id
            else None
        )
        if requested_master_id and master is None:
            return ExecutionTarget(
                mode_id=normalized_mode,
                document_path=normalized_document,
                placeholder_source_kind="unresolved_master",
                master_id=requested_master_id,
                issues=(f"master_ref_unresolved:{requested_master_id}",),
            )
        if (
            master is not None
            and str(getattr(master, "source_type", "") or "") == "builtin"
            and tuple(getattr(master, "supported_assembly_types", ()) or ())
            and profile_id
            not in tuple(getattr(master, "supported_assembly_types", ()) or ())
        ):
            return ExecutionTarget(
                mode_id=normalized_mode,
                document_path=normalized_document,
                placeholder_source_kind="unresolved_master",
                master_id=requested_master_id,
                master_path=str(getattr(master, "docx_path", "") or ""),
                issues=(
                    f"master_ref_incompatible:{requested_master_id}:{profile_id}",
                ),
            )
        if master is not None:
            bindings = tuple(
                ExecutionPlaceholderBinding(
                    placeholder_key=str(binding.placeholder_id or "").strip(),
                    field_key=str(binding.field_key or "").strip(),
                    required=bool(binding.required),
                )
                for binding in tuple(getattr(contract, "field_bindings", ()) or ())
                if str(getattr(binding, "placeholder_id", "") or "").strip()
                and str(getattr(binding, "field_key", "") or "").strip()
                and bool(getattr(binding, "applicable", True))
            )
            return ExecutionTarget(
                mode_id=normalized_mode,
                document_path=normalized_document,
                placeholder_source_kind="master",
                placeholder_source_path=str(master.docx_path),
                placeholder_source_label=str(master.label or master.master_id),
                master_id=str(master.master_id),
                master_path=str(master.docx_path),
                placeholder_bindings=bindings,
            )
        return ExecutionTarget(
            mode_id=normalized_mode,
            document_path=normalized_document,
            placeholder_source_kind="unresolved_master",
            master_id=requested_master_id,
            issues=(f"master_ref_unresolved:{requested_master_id or 'official'}",),
        )

    if normalized_mode == "exam":
        exam_config = getattr(scene, "exam_paper", None)
        master_id = str(getattr(scene, "master_id", "") or "").strip()
        master = (
            get_master(master_id, "exam", exam_config=exam_config)
            if master_id
            else None
        )
        if master is None:
            return ExecutionTarget(
                mode_id=normalized_mode,
                document_path=normalized_document,
                placeholder_source_kind="unresolved_master",
                master_id=master_id,
                issues=(f"master_ref_unresolved:{master_id or 'exam'}",),
            )
        return ExecutionTarget(
            mode_id=normalized_mode,
            document_path=normalized_document,
            placeholder_source_kind="structured",
            placeholder_source_label="试卷结构化装配",
            master_id=master_id,
            master_path=str(master.docx_path),
        )

    source_path = normalized_document if _is_docx_path(normalized_document) else ""
    return ExecutionTarget(
        mode_id=normalized_mode,
        document_path=normalized_document,
        placeholder_source_kind="document" if source_path else "none",
        placeholder_source_path=source_path,
        placeholder_source_label=Path(source_path).name if source_path else "",
    )


def _is_docx_path(value: str) -> bool:
    try:
        return Path(value).suffix.lower() == ".docx"
    except (OSError, TypeError, ValueError):
        return False


__all__ = [
    "ExecutionPlaceholderBinding",
    "ExecutionTarget",
    "resolve_execution_target",
]
