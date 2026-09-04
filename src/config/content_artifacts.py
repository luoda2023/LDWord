"""Pure contracts for immutable, compiled content-material artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Mapping, Sequence


CONTENT_ARTIFACT_CONTRACT = "content-artifact-v1"
CONTENT_COMPILER_CONTRACT = "content-compiler-v1"
CONTENT_IR_CONTRACT = "content-ir-v2"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTENT_ID_RE = re.compile(r"^[^\s{}:]+$")


def _require_sha256(value: object, label: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return normalized


def _require_text(value: object, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    return normalized


def _artifact_path(value: object, label: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in path.parts[0]
    ):
        raise ValueError(f"{label} must be a safe artifact-relative path")
    return path.as_posix()


@dataclass(frozen=True, slots=True)
class ContentArtifactRef:
    artifact_id: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_id",
            _require_sha256(self.artifact_id, "artifact_id"),
        )
        object.__setattr__(
            self,
            "manifest_sha256",
            _require_sha256(self.manifest_sha256, "manifest_sha256"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "manifest_sha256": self.manifest_sha256,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentArtifactRef":
        return cls(
            artifact_id=str(payload.get("artifact_id", "") or ""),
            manifest_sha256=str(payload.get("manifest_sha256", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class ContentMaterialBinding:
    content_id: str
    label: str
    artifact_ref: ContentArtifactRef

    def __post_init__(self) -> None:
        normalized_id = str(self.content_id or "").strip()
        if not _CONTENT_ID_RE.fullmatch(normalized_id):
            raise ValueError("content_id must be non-empty and cannot contain whitespace, braces, or ':'")
        object.__setattr__(self, "content_id", normalized_id)
        object.__setattr__(self, "label", _require_text(self.label, "label"))
        if not isinstance(self.artifact_ref, ContentArtifactRef):
            raise TypeError("artifact_ref must be a ContentArtifactRef")

    def to_dict(self) -> dict[str, object]:
        return {
            "content_id": self.content_id,
            "label": self.label,
            "artifact_ref": self.artifact_ref.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentMaterialBinding":
        artifact_payload = payload.get("artifact_ref", {})
        if not isinstance(artifact_payload, Mapping):
            raise TypeError("artifact_ref must be a mapping")
        return cls(
            content_id=str(payload.get("content_id", "") or ""),
            label=str(payload.get("label", "") or ""),
            artifact_ref=ContentArtifactRef.from_dict(artifact_payload),
        )


@dataclass(frozen=True, slots=True)
class ArtifactFileRef:
    path: str
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _artifact_path(self.path, "path"))
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "sha256"))
        if isinstance(self.byte_size, bool) or int(self.byte_size) < 0:
            raise ValueError("byte_size must be a non-negative integer")
        object.__setattr__(self, "byte_size", int(self.byte_size))

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ArtifactFileRef":
        return cls(
            path=str(payload.get("path", "") or ""),
            sha256=str(payload.get("sha256", "") or ""),
            byte_size=int(payload.get("byte_size", 0) or 0),
        )


@dataclass(frozen=True, slots=True)
class ContentSourceProvenance:
    format: str
    original_name: str
    media_type: str
    sha256: str
    byte_size: int
    blob: ArtifactFileRef

    def __post_init__(self) -> None:
        normalized_format = str(self.format or "").strip().casefold()
        if normalized_format not in {"markdown", "docx"}:
            raise ValueError("format must be 'markdown' or 'docx'")
        object.__setattr__(self, "format", normalized_format)
        object.__setattr__(
            self,
            "original_name",
            _require_text(self.original_name, "original_name"),
        )
        object.__setattr__(self, "media_type", _require_text(self.media_type, "media_type"))
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "source.sha256"))
        if isinstance(self.byte_size, bool) or int(self.byte_size) < 0:
            raise ValueError("source.byte_size must be a non-negative integer")
        object.__setattr__(self, "byte_size", int(self.byte_size))
        if not isinstance(self.blob, ArtifactFileRef):
            raise TypeError("blob must be an ArtifactFileRef")
        if self.sha256 != self.blob.sha256 or self.byte_size != self.blob.byte_size:
            raise ValueError("source identity must match its artifact blob")

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "original_name": self.original_name,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "blob": self.blob.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentSourceProvenance":
        blob = payload.get("blob", {})
        if not isinstance(blob, Mapping):
            raise TypeError("source.blob must be a mapping")
        return cls(
            format=str(payload.get("format", "") or ""),
            original_name=str(payload.get("original_name", "") or ""),
            media_type=str(payload.get("media_type", "") or ""),
            sha256=str(payload.get("sha256", "") or ""),
            byte_size=int(payload.get("byte_size", 0) or 0),
            blob=ArtifactFileRef.from_dict(blob),
        )


@dataclass(frozen=True, slots=True)
class ContentArtifactResource:
    resource_id: str
    media_type: str
    file: ArtifactFileRef

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resource_id",
            _artifact_path(self.resource_id, "resource_id"),
        )
        object.__setattr__(self, "media_type", _require_text(self.media_type, "media_type"))
        if not isinstance(self.file, ArtifactFileRef):
            raise TypeError("file must be an ArtifactFileRef")

    def to_dict(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "media_type": self.media_type,
            "file": self.file.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentArtifactResource":
        file_payload = payload.get("file", {})
        if not isinstance(file_payload, Mapping):
            raise TypeError("resource.file must be a mapping")
        return cls(
            resource_id=str(payload.get("resource_id", "") or ""),
            media_type=str(payload.get("media_type", "") or ""),
            file=ArtifactFileRef.from_dict(file_payload),
        )


@dataclass(frozen=True, slots=True)
class ContentArtifactManifest:
    source: ContentSourceProvenance
    fragment: ArtifactFileRef
    receipt: ArtifactFileRef
    resources: tuple[ContentArtifactResource, ...] = ()
    contract_version: str = CONTENT_ARTIFACT_CONTRACT
    compiler_contract: str = CONTENT_COMPILER_CONTRACT
    parser_contract: str = CONTENT_IR_CONTRACT
    artifact_id: str = ""

    def __post_init__(self) -> None:
        if self.contract_version != CONTENT_ARTIFACT_CONTRACT:
            raise ValueError(f"unsupported artifact contract: {self.contract_version!r}")
        if self.compiler_contract != CONTENT_COMPILER_CONTRACT:
            raise ValueError(f"unsupported compiler contract: {self.compiler_contract!r}")
        if self.parser_contract != CONTENT_IR_CONTRACT:
            raise ValueError(f"unsupported parser contract: {self.parser_contract!r}")
        if not isinstance(self.source, ContentSourceProvenance):
            raise TypeError("source must be ContentSourceProvenance")
        if not isinstance(self.fragment, ArtifactFileRef):
            raise TypeError("fragment must be ArtifactFileRef")
        if not isinstance(self.receipt, ArtifactFileRef):
            raise TypeError("receipt must be ArtifactFileRef")
        resources = tuple(self.resources or ())
        if any(not isinstance(item, ContentArtifactResource) for item in resources):
            raise TypeError("resources must contain only ContentArtifactResource values")
        resources = tuple(sorted(resources, key=lambda item: item.resource_id.casefold()))
        ids = [item.resource_id.casefold() for item in resources]
        paths = [item.file.path.casefold() for item in resources]
        if len(ids) != len(set(ids)):
            raise ValueError("resources contain duplicate resource_id values")
        if len(paths) != len(set(paths)):
            raise ValueError("resources contain duplicate file paths")
        reserved = {
            self.source.blob.path.casefold(),
            self.fragment.path.casefold(),
            self.receipt.path.casefold(),
        }
        if len(reserved) != 3 or reserved.intersection(paths):
            raise ValueError("artifact file paths must be unique")
        object.__setattr__(self, "resources", resources)
        computed_id = sha256(self.identity_json().encode("utf-8")).hexdigest()
        supplied_id = str(self.artifact_id or "").strip().casefold()
        if supplied_id and _require_sha256(supplied_id, "artifact_id") != computed_id:
            raise ValueError("artifact_id does not match canonical artifact payload")
        object.__setattr__(self, "artifact_id", computed_id)

    def identity_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "compiler_contract": self.compiler_contract,
            "parser_contract": self.parser_contract,
            "source": self.source.to_dict(),
            "fragment": self.fragment.to_dict(),
            "receipt": self.receipt.to_dict(),
            "resources": [item.to_dict() for item in self.resources],
        }

    def identity_json(self) -> str:
        return json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"artifact_id": self.artifact_id, **self.identity_payload()}

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def manifest_sha256(self) -> str:
        return sha256(self.to_json().encode("utf-8")).hexdigest()

    @property
    def ref(self) -> ContentArtifactRef:
        return ContentArtifactRef(self.artifact_id, self.manifest_sha256)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentArtifactManifest":
        source = payload.get("source", {})
        fragment = payload.get("fragment", {})
        receipt = payload.get("receipt", {})
        raw_resources = payload.get("resources", ())
        if not isinstance(source, Mapping):
            raise TypeError("source must be a mapping")
        if not isinstance(fragment, Mapping):
            raise TypeError("fragment must be a mapping")
        if not isinstance(receipt, Mapping):
            raise TypeError("receipt must be a mapping")
        if not isinstance(raw_resources, Sequence) or isinstance(raw_resources, (str, bytes)):
            raise TypeError("resources must be a sequence")
        if any(not isinstance(item, Mapping) for item in raw_resources):
            raise TypeError("each resource must be a mapping")
        return cls(
            source=ContentSourceProvenance.from_dict(source),
            fragment=ArtifactFileRef.from_dict(fragment),
            receipt=ArtifactFileRef.from_dict(receipt),
            resources=tuple(
                ContentArtifactResource.from_dict(item)
                for item in raw_resources
            ),
            contract_version=str(payload.get("contract_version", "") or ""),
            compiler_contract=str(payload.get("compiler_contract", "") or ""),
            parser_contract=str(payload.get("parser_contract", "") or ""),
            artifact_id=str(payload.get("artifact_id", "") or ""),
        )


__all__ = [
    "ArtifactFileRef",
    "CONTENT_ARTIFACT_CONTRACT",
    "CONTENT_COMPILER_CONTRACT",
    "CONTENT_IR_CONTRACT",
    "ContentArtifactManifest",
    "ContentArtifactRef",
    "ContentArtifactResource",
    "ContentMaterialBinding",
    "ContentSourceProvenance",
]
