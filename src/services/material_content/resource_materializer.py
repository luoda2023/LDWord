"""Resolve already-published artifact resources for image execution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from src.config.content_artifacts import (
    ContentArtifactRef,
    ContentArtifactResource,
    ContentMaterialBinding,
)
from src.config.content_materials import (
    ContentResourceKey,
    DocumentFragment,
    ImageBlock,
    TableBlock,
)
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)


@dataclass(frozen=True, slots=True)
class ContentResourceMaterializationDiagnostic:
    code: str
    message: str
    content_id: str = ""
    resource_id: str = ""
    path: str = ""


class ContentResourceMaterializationError(RuntimeError):
    def __init__(
        self,
        diagnostics: Sequence[ContentResourceMaterializationDiagnostic],
    ) -> None:
        self.diagnostics = tuple(diagnostics)
        detail = "\n".join(f"- [{item.code}] {item.message}" for item in self.diagnostics)
        super().__init__(f"Content resource resolution failed:\n{detail}")


@dataclass(frozen=True, slots=True)
class MaterializedContentResource:
    key: ContentResourceKey
    artifact_ref: ContentArtifactRef
    resource: ContentArtifactResource
    source_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, ContentResourceKey):
            raise TypeError("key must be a ContentResourceKey")
        if not isinstance(self.artifact_ref, ContentArtifactRef):
            raise TypeError("artifact_ref must be a ContentArtifactRef")
        if not isinstance(self.resource, ContentArtifactResource):
            raise TypeError("resource must be a ContentArtifactResource")
        if self.key.resource_id != self.resource.resource_id:
            raise ValueError("key.resource_id must match resource.resource_id")
        path = Path(self.source_path)
        if not self.source_path or not path.is_file():
            raise ValueError("source_path must identify a verified artifact file")

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key.to_dict(),
            "artifact_ref": self.artifact_ref.to_dict(),
            "resource": self.resource.to_dict(),
            "source_path": self.source_path,
        }


@dataclass(frozen=True, slots=True)
class ContentResourceMaterializationReceipt:
    receipt_id: str
    cache_root: str
    entries: tuple[MaterializedContentResource, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.entries or ())
        if any(not isinstance(item, MaterializedContentResource) for item in entries):
            raise TypeError(
                "entries must contain only MaterializedContentResource values"
            )
        entries = tuple(sorted(entries, key=lambda item: item.key))
        keys = [item.key for item in entries]
        if len(keys) != len(set(keys)):
            raise ValueError("entries contain duplicate ContentResourceKey values")
        object.__setattr__(self, "entries", entries)
        supplied = str(self.receipt_id or "").strip()
        computed = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied and supplied != computed:
            raise ValueError("receipt_id does not match canonical receipt payload")
        object.__setattr__(self, "receipt_id", computed)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "cache_root": self.cache_root,
            "entries": [item.to_dict() for item in self.entries],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"receipt_id": self.receipt_id, **self.canonical_payload()}

    def by_key(self) -> Mapping[ContentResourceKey, MaterializedContentResource]:
        return MappingProxyType({item.key: item for item in self.entries})


def materialize_content_fragment_resources(
    bindings: Sequence[ContentMaterialBinding],
    fragments: Mapping[str, DocumentFragment],
    repository: ContentArtifactRepository,
) -> ContentResourceMaterializationReceipt:
    """Resolve resources without opening an original Markdown/DOCX source."""

    normalized_bindings = tuple(bindings or ())
    if any(not isinstance(item, ContentMaterialBinding) for item in normalized_bindings):
        raise TypeError("bindings must contain only ContentMaterialBinding values")
    if not isinstance(fragments, Mapping):
        raise TypeError("fragments must be a mapping")
    if not isinstance(repository, ContentArtifactRepository):
        raise TypeError("repository must be a ContentArtifactRepository")
    diagnostics: list[ContentResourceMaterializationDiagnostic] = []
    entries: list[MaterializedContentResource] = []
    binding_ids = [item.content_id for item in normalized_bindings]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("bindings contain duplicate content_id values")
    if set(fragments) != set(binding_ids):
        raise ValueError("fragments must exactly match content binding ids")

    for binding in normalized_bindings:
        fragment = fragments[binding.content_id]
        if not isinstance(fragment, DocumentFragment):
            raise TypeError("fragments must contain DocumentFragment values")
        try:
            resolved = repository.validate(binding.artifact_ref)
            frozen_fragment = repository.load_fragment(binding.artifact_ref)
        except ContentArtifactRepositoryError as exc:
            diagnostics.append(
                ContentResourceMaterializationDiagnostic(
                    code=exc.code,
                    message="compiled content artifact is missing or invalid",
                    content_id=binding.content_id,
                )
            )
            continue
        if frozen_fragment != fragment:
            diagnostics.append(
                ContentResourceMaterializationDiagnostic(
                    code="artifact_fragment_mismatch",
                    message="resolved fragment differs from the artifact fragment",
                    content_id=binding.content_id,
                )
            )
            continue
        referenced_ids = set(_fragment_resource_ids(fragment))
        declared_ids = {item.resource_id for item in resolved.manifest.resources}
        if referenced_ids != declared_ids:
            diagnostics.append(
                ContentResourceMaterializationDiagnostic(
                    code="artifact_resource_closure_mismatch",
                    message="artifact resources do not close the semantic fragment",
                    content_id=binding.content_id,
                )
            )
            continue
        for resource in resolved.manifest.resources:
            path = resolved.resource_path(resource.resource_id)
            entries.append(
                MaterializedContentResource(
                    key=ContentResourceKey(
                        binding.content_id,
                        resource.resource_id,
                    ),
                    artifact_ref=binding.artifact_ref,
                    resource=resource,
                    source_path=str(path),
                )
            )

    if diagnostics:
        raise ContentResourceMaterializationError(diagnostics)
    return ContentResourceMaterializationReceipt(
        receipt_id="",
        cache_root=str(repository.root) if entries else "",
        entries=tuple(entries),
    )


def _fragment_resource_ids(fragment: DocumentFragment) -> tuple[str, ...]:
    result: list[str] = []

    def visit(block) -> None:
        if isinstance(block, ImageBlock):
            result.append(block.resource_id)
        elif isinstance(block, TableBlock):
            for row in block.rows:
                for cell in row.cells:
                    for child in cell.blocks:
                        visit(child)

    for block in fragment.blocks:
        visit(block)
    return tuple(result)


__all__ = [
    "ContentResourceMaterializationDiagnostic",
    "ContentResourceMaterializationError",
    "ContentResourceMaterializationReceipt",
    "MaterializedContentResource",
    "materialize_content_fragment_resources",
]
