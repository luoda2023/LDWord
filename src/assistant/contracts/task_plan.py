"""Typed capability, source, production, and delivery contracts for Assistant plans."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


TASK_OPERATION_AUTHOR = "author"
TASK_OPERATION_TRANSFORM = "transform"
TASK_OPERATION_REVIEW = "review"
TASK_OPERATION_BATCH = "batch"
TASK_OPERATION_IMPORT = "import"
TASK_OPERATION_AUTHOR_MASTER = "author_master"

CAPABILITY_EXECUTABLE = "executable"
CAPABILITY_PLANNED = "planned"
CAPABILITY_GATED = "gated"

ARTIFACT_KIND_NARRATIVE = "narrative_markdown"
ARTIFACT_KIND_EXAM = "exam_paper_markdown"
ARTIFACT_KIND_EXISTING_DOCUMENT = "existing_document"

SOURCE_ROLE_PRODUCTION_INPUT = "production_input"
SOURCE_ROLE_REFERENCE_MATERIAL = "reference_material"
SOURCE_ROLE_STRUCTURED_SOURCE = "structured_source"
SOURCE_ROLE_STANDARD_FORMAT_REFERENCE = "standard_format_reference"


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, Sequence):
        return ()
    return tuple(str(item) for item in value if str(item or "").strip())


@dataclass(frozen=True, slots=True)
class TaskCapabilityRef:
    """Resolved product capability; it must never be inferred again by the UI."""

    capability_id: str = ""
    route_id: str = ""
    family_id: str = ""
    profile_id: str = ""
    route_type: str = ""
    status: str = CAPABILITY_EXECUTABLE
    gate_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "route_id": self.route_id,
            "family_id": self.family_id,
            "profile_id": self.profile_id,
            "route_type": self.route_type,
            "status": self.status,
            "gate_id": self.gate_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "TaskCapabilityRef":
        data = value or {}
        return cls(
            capability_id=str(data.get("capability_id") or ""),
            route_id=str(data.get("route_id") or ""),
            family_id=str(data.get("family_id") or ""),
            profile_id=str(data.get("profile_id") or ""),
            route_type=str(data.get("route_type") or ""),
            status=str(data.get("status") or CAPABILITY_EXECUTABLE),
            gate_id=str(data.get("gate_id") or ""),
        )


@dataclass(frozen=True, slots=True)
class SourceArtifactRef:
    """One immutable source role in a task, independent from its local file type."""

    artifact_id: str = ""
    role: str = ""
    media_type: str = ""
    path: str = ""
    name: str = ""
    schema_id: str = ""
    digest: str = ""
    source_kind: str = "file"

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "role": self.role,
            "media_type": self.media_type,
            "path": self.path,
            "name": self.name,
            "schema_id": self.schema_id,
            "digest": self.digest,
            "source_kind": self.source_kind,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceArtifactRef":
        return cls(
            artifact_id=str(value.get("artifact_id") or ""),
            role=str(value.get("role") or ""),
            media_type=str(value.get("media_type") or ""),
            path=str(value.get("path") or ""),
            name=str(value.get("name") or ""),
            schema_id=str(value.get("schema_id") or ""),
            digest=str(value.get("digest") or ""),
            source_kind=str(value.get("source_kind") or "file"),
        )


@dataclass(frozen=True, slots=True)
class GenerationContract:
    """The exact artifact an AI provider may produce for this task."""

    required: bool = False
    artifact_kind: str = ""
    prompt_profile_id: str = ""
    validator_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "required": self.required,
            "artifact_kind": self.artifact_kind,
            "prompt_profile_id": self.prompt_profile_id,
            "validator_id": self.validator_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "GenerationContract":
        data = value or {}
        return cls(
            required=bool(data.get("required", False)),
            artifact_kind=str(data.get("artifact_kind") or ""),
            prompt_profile_id=str(data.get("prompt_profile_id") or ""),
            validator_id=str(data.get("validator_id") or ""),
        )


@dataclass(frozen=True, slots=True)
class ProductionContract:
    """Domain validator and the single terminal publication owner."""

    input_role: str = SOURCE_ROLE_PRODUCTION_INPUT
    artifact_kind: str = ARTIFACT_KIND_EXISTING_DOCUMENT
    validator_id: str = ""
    terminal_assembler: str = "generic"
    master_id: str = ""
    document_type_id: str = ""
    accepted_suffixes: tuple[str, ...] = (".docx",)

    def to_dict(self) -> dict[str, object]:
        return {
            "input_role": self.input_role,
            "artifact_kind": self.artifact_kind,
            "validator_id": self.validator_id,
            "terminal_assembler": self.terminal_assembler,
            "master_id": self.master_id,
            "document_type_id": self.document_type_id,
            "accepted_suffixes": list(self.accepted_suffixes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "ProductionContract":
        data = value or {}
        suffixes = tuple(
            suffix if suffix.startswith(".") else f".{suffix}"
            for suffix in _strings(data.get("accepted_suffixes"))
        )
        return cls(
            input_role=str(data.get("input_role") or SOURCE_ROLE_PRODUCTION_INPUT),
            artifact_kind=str(
                data.get("artifact_kind") or ARTIFACT_KIND_EXISTING_DOCUMENT
            ),
            validator_id=str(data.get("validator_id") or ""),
            terminal_assembler=str(data.get("terminal_assembler") or "generic"),
            master_id=str(data.get("master_id") or ""),
            document_type_id=str(data.get("document_type_id") or ""),
            accepted_suffixes=suffixes or (".docx",),
        )


@dataclass(frozen=True, slots=True)
class DeliveryContract:
    """Expected publication bundle, not merely an output directory."""

    default_preset_id: str = ""
    preset_ids: tuple[str, ...] = ()
    required_artifact_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "default_preset_id": self.default_preset_id,
            "preset_ids": list(self.preset_ids),
            "required_artifact_keys": list(self.required_artifact_keys),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "DeliveryContract":
        data = value or {}
        return cls(
            default_preset_id=str(data.get("default_preset_id") or ""),
            preset_ids=_strings(data.get("preset_ids")),
            required_artifact_keys=_strings(data.get("required_artifact_keys")),
        )


__all__ = [
    "ARTIFACT_KIND_EXAM",
    "ARTIFACT_KIND_EXISTING_DOCUMENT",
    "ARTIFACT_KIND_NARRATIVE",
    "CAPABILITY_EXECUTABLE",
    "CAPABILITY_GATED",
    "CAPABILITY_PLANNED",
    "DeliveryContract",
    "GenerationContract",
    "ProductionContract",
    "SOURCE_ROLE_PRODUCTION_INPUT",
    "SOURCE_ROLE_REFERENCE_MATERIAL",
    "SOURCE_ROLE_STANDARD_FORMAT_REFERENCE",
    "SOURCE_ROLE_STRUCTURED_SOURCE",
    "SourceArtifactRef",
    "TASK_OPERATION_AUTHOR",
    "TASK_OPERATION_AUTHOR_MASTER",
    "TASK_OPERATION_BATCH",
    "TASK_OPERATION_IMPORT",
    "TASK_OPERATION_REVIEW",
    "TASK_OPERATION_TRANSFORM",
    "TaskCapabilityRef",
]
