"""Atomic, content-addressed storage for compiled content materials."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
from typing import Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from src.config.content_artifacts import (
    ArtifactFileRef,
    CONTENT_COMPILER_CONTRACT,
    CONTENT_IR_CONTRACT,
    ContentArtifactManifest,
    ContentArtifactRef,
    ContentArtifactResource,
    ContentSourceProvenance,
)
from src.config.content_materials import DocumentFragment, ImageBlock, TableBlock
from src.services.material_content.import_contract import ContentCompileReceipt
from src.services.material_content.source_capture import CapturedContentSource


_RESOURCE_ID_RE = re.compile(r"^sha256/([0-9a-f]{64})(\.[a-z0-9]{1,10})?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_FRAGMENT_BYTES = 64 * 1024 * 1024
_MAX_RECEIPT_BYTES = 16 * 1024 * 1024


class ContentArtifactRepositoryError(ValueError):
    def __init__(self, code: str, message: str, *, artifact_id: str = "") -> None:
        self.code = str(code or "").strip()
        self.artifact_id = str(artifact_id or "").strip()
        super().__init__(message)


class ContentArtifactPublishCancelled(ContentArtifactRepositoryError):
    def __init__(self) -> None:
        super().__init__("artifact_publish_cancelled", "Artifact publication was cancelled")


@dataclass(frozen=True, slots=True)
class ArtifactResourcePayload:
    resource_id: str
    media_type: str
    payload: bytes

    def __post_init__(self) -> None:
        normalized_id = str(self.resource_id or "").strip().casefold()
        match = _RESOURCE_ID_RE.fullmatch(normalized_id)
        if match is None:
            raise ValueError(
                "resource_id must use sha256/<digest> with an optional safe suffix"
            )
        if not str(self.media_type or "").strip():
            raise ValueError("media_type must not be empty")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")
        if match.group(1) != sha256(self.payload).hexdigest():
            raise ValueError("resource_id digest does not match payload")
        object.__setattr__(self, "resource_id", normalized_id)

    @classmethod
    def from_bytes(
        cls,
        payload: bytes,
        *,
        media_type: str,
        suffix: str = "",
    ) -> "ArtifactResourcePayload":
        normalized_suffix = str(suffix or "").strip().casefold().lstrip(".")
        if normalized_suffix and not re.fullmatch(r"[a-z0-9]{1,10}", normalized_suffix):
            raise ValueError("suffix must contain 1-10 lowercase letters or digits")
        digest = sha256(payload).hexdigest()
        resource_id = f"sha256/{digest}"
        if normalized_suffix:
            resource_id += "." + normalized_suffix
        return cls(resource_id, media_type, payload)


@dataclass(frozen=True, slots=True)
class ResolvedContentArtifact:
    directory: Path
    manifest: ContentArtifactManifest

    @property
    def ref(self) -> ContentArtifactRef:
        return self.manifest.ref

    def resource_path(self, resource_id: str) -> Path:
        matches = [
            item for item in self.manifest.resources if item.resource_id == resource_id
        ]
        if len(matches) != 1:
            raise ContentArtifactRepositoryError(
                "artifact_resource_missing",
                f"Artifact does not declare resource {resource_id!r}",
                artifact_id=self.manifest.artifact_id,
            )
        return _contained_path(self.directory, matches[0].file.path)


class ContentArtifactRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.artifacts_root = self.root / "sha256"
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        source: CapturedContentSource,
        fragment: DocumentFragment,
        receipt: ContentCompileReceipt,
        resources: Sequence[ArtifactResourcePayload] = (),
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> ContentArtifactRef:
        if not isinstance(source, CapturedContentSource):
            raise TypeError("source must be a CapturedContentSource")
        if not isinstance(fragment, DocumentFragment):
            raise TypeError("fragment must be a DocumentFragment")
        if not isinstance(receipt, ContentCompileReceipt):
            raise TypeError("receipt must be a ContentCompileReceipt")
        if receipt.compiler_contract != CONTENT_COMPILER_CONTRACT:
            raise ValueError("receipt compiler contract does not match repository contract")
        if receipt.parser_contract != CONTENT_IR_CONTRACT:
            raise ValueError("receipt parser contract does not match repository contract")
        if receipt.source_sha256 != source.sha256:
            raise ValueError("receipt source identity does not match captured bytes")
        normalized_resources = tuple(sorted(resources, key=lambda item: item.resource_id))
        if any(not isinstance(item, ArtifactResourcePayload) for item in normalized_resources):
            raise TypeError("resources must contain only ArtifactResourcePayload values")
        ids = [item.resource_id for item in normalized_resources]
        if len(ids) != len(set(ids)):
            raise ValueError("resources contain duplicate resource_id values")
        referenced = set(_fragment_resource_ids(fragment))
        declared = set(ids)
        if referenced != declared:
            missing = sorted(referenced - declared)
            unused = sorted(declared - referenced)
            raise ValueError(
                "fragment/resource closure mismatch: "
                f"missing={missing!r}, unused={unused!r}"
            )

        fragment_payload = _canonical_json_bytes(fragment.to_dict())
        receipt_payload = _canonical_json_bytes(receipt.to_dict())
        source_name = _safe_source_name(source.original_name, source.source_format)
        source_file = _file_ref(f"source/{source_name}", source.payload)
        resource_contracts = tuple(
            ContentArtifactResource(
                resource_id=item.resource_id,
                media_type=item.media_type,
                file=_file_ref(f"resources/{item.resource_id}", item.payload),
            )
            for item in normalized_resources
        )
        manifest = ContentArtifactManifest(
            source=ContentSourceProvenance(
                format=source.source_format,
                original_name=source.original_name,
                media_type=source.media_type,
                sha256=source.sha256,
                byte_size=source.byte_size,
                blob=source_file,
            ),
            fragment=_file_ref("fragment.json", fragment_payload),
            receipt=_file_ref("compile-receipt.json", receipt_payload),
            resources=resource_contracts,
        )
        destination = self._artifact_directory(manifest.artifact_id)
        if destination.exists():
            self.validate(manifest.ref)
            return manifest.ref
        _raise_if_cancelled(cancelled)
        staging = self.artifacts_root / (
            f".staging-{manifest.artifact_id}-{uuid4().hex}"
        )
        try:
            staging.mkdir(parents=False, exist_ok=False)
            _write_durable(_contained_path(staging, source_file.path), source.payload)
            _write_durable(_contained_path(staging, "fragment.json"), fragment_payload)
            _write_durable(
                _contained_path(staging, "compile-receipt.json"),
                receipt_payload,
            )
            for contract, resource in zip(
                resource_contracts,
                normalized_resources,
                strict=True,
            ):
                _write_durable(
                    _contained_path(staging, contract.file.path),
                    resource.payload,
                )
            _raise_if_cancelled(cancelled)
            _write_durable(
                _contained_path(staging, "manifest.json"),
                manifest.to_json().encode("utf-8"),
            )
            self._validate_directory(staging, manifest.ref, require_named_directory=False)
            _raise_if_cancelled(cancelled)
            _sync_directory(staging)
            try:
                os.replace(staging, destination)
            except (FileExistsError, PermissionError):
                if not destination.exists():
                    raise
                self.validate(manifest.ref)
            _sync_directory(self.artifacts_root)
            return manifest.ref
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def validate(self, ref: ContentArtifactRef) -> ResolvedContentArtifact:
        if not isinstance(ref, ContentArtifactRef):
            raise TypeError("ref must be a ContentArtifactRef")
        return self._validate_directory(
            self._artifact_directory(ref.artifact_id),
            ref,
            require_named_directory=True,
        )

    def load_fragment(self, ref: ContentArtifactRef) -> DocumentFragment:
        resolved = self.validate(ref)
        payload = _read_bounded(
            _contained_path(resolved.directory, resolved.manifest.fragment.path),
            _MAX_FRAGMENT_BYTES,
            "artifact_fragment_too_large",
            resolved.manifest.artifact_id,
        )
        decoded = _strict_json_mapping(payload, "artifact_fragment_invalid")
        fragment = DocumentFragment.from_dict(decoded)
        if _canonical_json_bytes(fragment.to_dict()) != payload:
            raise ContentArtifactRepositoryError(
                "artifact_fragment_not_canonical",
                "Artifact fragment JSON is not canonical",
                artifact_id=resolved.manifest.artifact_id,
            )
        return fragment

    def load_receipt(self, ref: ContentArtifactRef) -> ContentCompileReceipt:
        resolved = self.validate(ref)
        payload = _read_bounded(
            _contained_path(resolved.directory, resolved.manifest.receipt.path),
            _MAX_RECEIPT_BYTES,
            "artifact_receipt_too_large",
            resolved.manifest.artifact_id,
        )
        decoded = _strict_json_mapping(payload, "artifact_receipt_invalid")
        receipt = ContentCompileReceipt.from_dict(decoded)
        if _canonical_json_bytes(receipt.to_dict()) != payload:
            raise ContentArtifactRepositoryError(
                "artifact_receipt_not_canonical",
                "Artifact compile receipt JSON is not canonical",
                artifact_id=resolved.manifest.artifact_id,
            )
        return receipt

    def resolve_resource(self, ref: ContentArtifactRef, resource_id: str) -> Path:
        return self.validate(ref).resource_path(resource_id)

    def garbage_collection_candidates(
        self,
        references: Iterable[ContentArtifactRef],
    ) -> tuple[str, ...]:
        referenced: set[str] = set()
        for ref in references:
            if not isinstance(ref, ContentArtifactRef):
                raise TypeError("references must contain only ContentArtifactRef values")
            referenced.add(ref.artifact_id)
        candidates = []
        for path in self.artifacts_root.iterdir():
            if (
                path.is_dir()
                and not path.is_symlink()
                and _SHA256_RE.fullmatch(path.name)
                and path.name not in referenced
            ):
                candidates.append(path.name)
        return tuple(sorted(candidates))

    def vendor(
        self,
        ref: ContentArtifactRef,
        vendor_artifacts_root: str | Path,
    ) -> Path:
        """Copy one verified artifact into a package-owned sha256 directory."""

        resolved = self.validate(ref)
        vendor_root = Path(vendor_artifacts_root).expanduser().resolve()
        vendor_root.mkdir(parents=True, exist_ok=True)
        target = _contained_path(vendor_root, ref.artifact_id)
        if target.exists() or target.is_symlink():
            self._validate_directory(
                target,
                ref,
                require_named_directory=True,
            )
            return target
        staging = vendor_root / f".staging-vendor-{ref.artifact_id}-{uuid4().hex}"
        try:
            shutil.copytree(resolved.directory, staging, symlinks=False)
            self._validate_directory(
                staging,
                ref,
                require_named_directory=False,
            )
            try:
                os.replace(staging, target)
            except (FileExistsError, PermissionError):
                if not target.exists() and not target.is_symlink():
                    raise
                self._validate_directory(
                    target,
                    ref,
                    require_named_directory=True,
                )
            return target
        finally:
            if staging.exists() or staging.is_symlink():
                shutil.rmtree(staging, ignore_errors=True)

    def install_vendored(self, artifact_directory: str | Path) -> ContentArtifactRef:
        """Validate and deduplicate one package-vendored artifact locally."""

        source = Path(artifact_directory).expanduser().resolve()
        ref = _artifact_ref_from_directory(source)
        self._validate_directory(source, ref, require_named_directory=True)
        destination = self._artifact_directory(ref.artifact_id)
        if destination.exists():
            self.validate(ref)
            return ref
        staging = self.artifacts_root / f".staging-install-{ref.artifact_id}-{uuid4().hex}"
        try:
            shutil.copytree(source, staging, symlinks=False)
            self._validate_directory(staging, ref, require_named_directory=False)
            try:
                os.replace(staging, destination)
            except (FileExistsError, PermissionError):
                if not destination.exists():
                    raise
                self.validate(ref)
            return ref
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def _artifact_directory(self, artifact_id: str) -> Path:
        if not _SHA256_RE.fullmatch(str(artifact_id or "")):
            raise ValueError("artifact_id must be a lowercase SHA-256 digest")
        return _contained_path(self.artifacts_root, artifact_id)

    def _validate_directory(
        self,
        directory: Path,
        ref: ContentArtifactRef,
        *,
        require_named_directory: bool,
    ) -> ResolvedContentArtifact:
        artifact_id = ref.artifact_id
        if not directory.is_dir() or directory.is_symlink():
            raise ContentArtifactRepositoryError(
                "artifact_missing",
                "Compiled content artifact is missing",
                artifact_id=artifact_id,
            )
        if require_named_directory and directory.name != artifact_id:
            raise ContentArtifactRepositoryError(
                "artifact_directory_mismatch",
                "Artifact directory does not match its identity",
                artifact_id=artifact_id,
            )
        manifest_path = _contained_path(directory, "manifest.json")
        raw_manifest = _read_bounded(
            manifest_path,
            _MAX_MANIFEST_BYTES,
            "artifact_manifest_too_large",
            artifact_id,
        )
        payload = _strict_json_mapping(raw_manifest, "artifact_manifest_invalid")
        try:
            manifest = ContentArtifactManifest.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise ContentArtifactRepositoryError(
                "artifact_manifest_invalid",
                "Artifact manifest violates its contract",
                artifact_id=artifact_id,
            ) from exc
        if manifest.ref != ref:
            raise ContentArtifactRepositoryError(
                "artifact_reference_mismatch",
                "Artifact manifest does not match the requested reference",
                artifact_id=artifact_id,
            )
        if raw_manifest != manifest.to_json().encode("utf-8"):
            raise ContentArtifactRepositoryError(
                "artifact_manifest_not_canonical",
                "Artifact manifest JSON is not canonical",
                artifact_id=artifact_id,
            )
        contracts = (
            manifest.source.blob,
            manifest.fragment,
            manifest.receipt,
            *(item.file for item in manifest.resources),
        )
        expected = {"manifest.json", *(item.path for item in contracts)}
        actual = _artifact_files(directory, artifact_id)
        if actual != expected:
            raise ContentArtifactRepositoryError(
                "artifact_file_set_mismatch",
                "Artifact contains missing or undeclared files",
                artifact_id=artifact_id,
            )
        for contract in contracts:
            _validate_file(directory, contract, artifact_id)
        return ResolvedContentArtifact(directory=directory, manifest=manifest)


def _fragment_resource_ids(fragment: DocumentFragment) -> tuple[str, ...]:
    result: list[str] = []

    def visit(block) -> None:
        if isinstance(block, ImageBlock):
            result.append(block.resource_id)
        elif isinstance(block, TableBlock):
            for row in block.rows:
                for cell in row.cells:
                    for child in getattr(cell, "blocks", ()):
                        visit(child)

    for block in fragment.blocks:
        visit(block)
    return tuple(result)


def _safe_source_name(original_name: str, source_format: str) -> str:
    base = re.split(r"[\\/]", str(original_name or ""))[-1].strip(" .")
    fallback = "source.md" if source_format == "markdown" else "source.docx"
    if not base:
        return fallback
    base = re.sub(r"[^\w.()\[\] -]", "_", base, flags=re.UNICODE).strip(" .")
    if not base:
        return fallback
    if len(base) <= 120:
        return base
    suffix = Path(base).suffix[:12]
    stem_limit = max(1, 120 - len(suffix))
    return base[:stem_limit].rstrip(" .") + suffix


def _file_ref(path: str, payload: bytes) -> ArtifactFileRef:
    return ArtifactFileRef(path, sha256(payload).hexdigest(), len(payload))


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _strict_json_mapping(payload: bytes, code: str) -> Mapping[str, object]:
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContentArtifactRepositoryError(code, "Artifact JSON is invalid") from exc
    if not isinstance(decoded, Mapping):
        raise ContentArtifactRepositoryError(code, "Artifact JSON root must be an object")
    return decoded


def _artifact_ref_from_directory(directory: Path) -> ContentArtifactRef:
    raw = _read_bounded(
        directory / "manifest.json",
        _MAX_MANIFEST_BYTES,
        "artifact_manifest_too_large",
        directory.name,
    )
    payload = _strict_json_mapping(raw, "artifact_manifest_invalid")
    try:
        manifest = ContentArtifactManifest.from_dict(payload)
    except (TypeError, ValueError) as exc:
        raise ContentArtifactRepositoryError(
            "artifact_manifest_invalid",
            "Artifact manifest violates its contract",
            artifact_id=directory.name,
        ) from exc
    if raw != manifest.to_json().encode("utf-8"):
        raise ContentArtifactRepositoryError(
            "artifact_manifest_not_canonical",
            "Artifact manifest JSON is not canonical",
            artifact_id=manifest.artifact_id,
        )
    return manifest.ref


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _contained_path(root: Path, relative: str) -> Path:
    base = root.resolve()
    candidate = (base / Path(relative.replace("/", os.sep))).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ContentArtifactRepositoryError(
            "artifact_path_escape",
            "Artifact path escapes its repository directory",
        ) from exc
    return candidate


def _write_durable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _read_bounded(path: Path, limit: int, code: str, artifact_id: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ContentArtifactRepositoryError(
            "artifact_file_missing",
            "Artifact file is missing or not a regular file",
            artifact_id=artifact_id,
        )
    if path.stat().st_size > limit:
        raise ContentArtifactRepositoryError(
            code,
            "Artifact file exceeds its configured size limit",
            artifact_id=artifact_id,
        )
    with path.open("rb") as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ContentArtifactRepositoryError(
            code,
            "Artifact file exceeds its configured size limit",
            artifact_id=artifact_id,
        )
    return payload


def _artifact_files(directory: Path, artifact_id: str) -> set[str]:
    files: set[str] = set()
    for root, directory_names, file_names in os.walk(directory, followlinks=False):
        root_path = Path(root)
        for name in tuple(directory_names):
            child = root_path / name
            if child.is_symlink():
                raise ContentArtifactRepositoryError(
                    "artifact_symlink_forbidden",
                    "Artifact directories cannot contain symbolic links",
                    artifact_id=artifact_id,
                )
        for name in file_names:
            child = root_path / name
            if child.is_symlink() or not child.is_file():
                raise ContentArtifactRepositoryError(
                    "artifact_file_invalid",
                    "Artifact contains a non-regular file",
                    artifact_id=artifact_id,
                )
            files.add(child.relative_to(directory).as_posix())
    return files


def _validate_file(directory: Path, contract: ArtifactFileRef, artifact_id: str) -> None:
    path = _contained_path(directory, contract.path)
    if path.is_symlink() or not path.is_file():
        raise ContentArtifactRepositoryError(
            "artifact_file_missing",
            f"Artifact file is missing: {contract.path}",
            artifact_id=artifact_id,
        )
    stat = path.stat()
    if stat.st_size != contract.byte_size:
        raise ContentArtifactRepositoryError(
            "artifact_file_size_mismatch",
            f"Artifact file size does not match: {contract.path}",
            artifact_id=artifact_id,
        )
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != contract.sha256:
        raise ContentArtifactRepositoryError(
            "artifact_file_digest_mismatch",
            f"Artifact file digest does not match: {contract.path}",
            artifact_id=artifact_id,
        )


def _raise_if_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise ContentArtifactPublishCancelled()


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "ArtifactResourcePayload",
    "ContentArtifactPublishCancelled",
    "ContentArtifactRepository",
    "ContentArtifactRepositoryError",
    "ResolvedContentArtifact",
]
