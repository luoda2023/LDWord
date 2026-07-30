"""Pure persistence contracts for non-inline attachment materials."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Mapping, Sequence
import unicodedata

from src.config.content_materials import FileAssetRef
from src.config.image_materials import ResolvedImageInsertionPlan
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
)


class AttachmentCardinality(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class AttachmentSourceKind(str, Enum):
    SINGLE_FILE = "single_file"
    FILE_SET = "file_set"
    DIRECTORY_PACKAGE = "directory_package"


class AttachmentProcessingMode(str, Enum):
    PASSTHROUGH = "passthrough"
    SUBSTITUTE_COPY = "substitute_copy"


@dataclass(frozen=True, slots=True)
class AttachmentRoleSpec:
    """Profile-owned attachment definition, independent from source binding."""

    role: str
    label: str
    accepted_types: tuple[str, ...] = ("image", "pdf")
    required: bool = False
    cardinality: str = "single"
    source_kind: str = "single_file"
    recursive: bool = False
    processing_mode: str = "passthrough"
    min_items: int = 0
    max_items: int | None = 1
    origin: str = "schema"

    def __post_init__(self) -> None:
        role = str(self.role or "").strip()
        material_token(MaterialTokenNamespace.ATTACHMENT, role)
        label = " ".join(str(self.label or "").split()) or role
        accepted_types = tuple(
            dict.fromkeys(
                str(value or "").strip().casefold()
                for value in tuple(self.accepted_types or ())
                if str(value or "").strip()
            )
        )
        if not accepted_types:
            raise ValueError("accepted_types cannot be empty")
        source_kind = AttachmentSourceKind(str(self.source_kind or "single_file"))
        expected_cardinality = (
            AttachmentCardinality.SINGLE
            if source_kind is AttachmentSourceKind.SINGLE_FILE
            else AttachmentCardinality.MULTIPLE
        )
        cardinality = AttachmentCardinality(str(self.cardinality or "single"))
        if cardinality is not expected_cardinality:
            raise ValueError("attachment role cardinality conflicts with source_kind")
        processing_mode = AttachmentProcessingMode(
            str(self.processing_mode or "passthrough")
        )
        recursive = bool(self.recursive)
        if recursive and source_kind is not AttachmentSourceKind.DIRECTORY_PACKAGE:
            raise ValueError("recursive is only valid for directory_package")
        min_items = _as_nonnegative_int(self.min_items, "min_items")
        max_items = (
            None
            if self.max_items is None
            else _as_nonnegative_int(self.max_items, "max_items")
        )
        if source_kind is AttachmentSourceKind.SINGLE_FILE:
            min_items = min(min_items, 1)
            max_items = 1
        elif max_items == 1:
            max_items = None
        if max_items is not None and max_items < min_items:
            raise ValueError("max_items cannot be less than min_items")
        origin = str(self.origin or "schema").strip().casefold()
        if origin not in {"schema", "profile"}:
            raise ValueError("attachment role origin must be schema or profile")
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "accepted_types", accepted_types)
        object.__setattr__(self, "cardinality", expected_cardinality.value)
        object.__setattr__(self, "source_kind", source_kind.value)
        object.__setattr__(self, "recursive", recursive)
        object.__setattr__(self, "processing_mode", processing_mode.value)
        object.__setattr__(self, "min_items", min_items)
        object.__setattr__(self, "max_items", max_items)
        object.__setattr__(self, "origin", origin)

    @property
    def anchor_token(self) -> str:
        return material_token(MaterialTokenNamespace.ATTACHMENT, self.role)

    @property
    def deletable(self) -> bool:
        return self.origin == "profile"

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "label": self.label,
            "accepted_types": list(self.accepted_types),
            "required": self.required,
            "cardinality": self.cardinality,
            "source_kind": self.source_kind,
            "recursive": self.recursive,
            "processing_mode": self.processing_mode,
            "min_items": self.min_items,
            "max_items": self.max_items,
            "origin": self.origin,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "AttachmentRoleSpec":
        if not isinstance(payload, Mapping):
            raise TypeError("attachment role spec payload must be a mapping")
        return cls(
            role=str(payload.get("role", "") or ""),
            label=str(payload.get("label", "") or ""),
            accepted_types=tuple(payload.get("accepted_types", ()) or ()),
            required=bool(payload.get("required", False)),
            cardinality=str(payload.get("cardinality", "single") or "single"),
            source_kind=str(payload.get("source_kind", "single_file") or "single_file"),
            recursive=bool(payload.get("recursive", False)),
            processing_mode=str(
                payload.get("processing_mode", "passthrough") or "passthrough"
            ),
            min_items=payload.get("min_items", 0),
            max_items=payload.get("max_items", 1),
            origin=str(payload.get("origin", "schema") or "schema"),
        )


class AttachmentFileStatus(str, Enum):
    PASSTHROUGH = "passthrough"
    SUBSTITUTED = "substituted"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"


class AttachmentRenderMode(str, Enum):
    INVENTORY_BLOCK = "inventory_block"


ATTACHMENT_BINDING_CONTRACT_VERSION = "attachment-binding-v2"


@dataclass(frozen=True, slots=True)
class AttachmentItem:
    """One original file collected for delivery, never inline insertion."""

    item_id: str
    file_ref: FileAssetRef
    label: str = ""
    sequence: int = 0
    relative_path: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must not be empty")
        if not isinstance(self.file_ref, FileAssetRef):
            raise TypeError("file_ref must be a FileAssetRef")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence must be an integer")
        if self.sequence < 0:
            raise ValueError("sequence cannot be negative")
        if not isinstance(self.label, str):
            raise TypeError("label must be a string")
        object.__setattr__(
            self,
            "relative_path",
            normalize_attachment_relative_path(
                self.relative_path or self.file_ref.original_name
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "file_ref": self.file_ref.to_dict(),
            "label": self.label,
            "sequence": self.sequence,
            "relative_path": self.relative_path,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "AttachmentItem":
        raw_ref = payload.get("file_ref", {})
        if not isinstance(raw_ref, Mapping):
            raise TypeError("file_ref must be a mapping")
        return cls(
            item_id=str(payload.get("item_id", "") or ""),
            file_ref=FileAssetRef.from_dict(raw_ref),
            label=str(payload.get("label", "") or ""),
            sequence=_as_nonnegative_int(payload.get("sequence", 0), "sequence"),
            # v3 bindings had no relative_path and were necessarily flat.
            relative_path=str(
                payload.get("relative_path", "")
                or raw_ref.get("original_name", "")
                or ""
            ),
        )


@dataclass(frozen=True, slots=True)
class AttachmentBinding:
    """Typed role binding for one or many delivery attachments."""

    role: str
    label: str = ""
    source_kind: AttachmentSourceKind = AttachmentSourceKind.SINGLE_FILE
    source_path: str = ""
    recursive: bool = False
    processing_mode: AttachmentProcessingMode = AttachmentProcessingMode.PASSTHROUGH
    cardinality: AttachmentCardinality = AttachmentCardinality.SINGLE
    items: tuple[AttachmentItem, ...] = ()
    required: bool = False
    min_items: int = 0
    max_items: int | None = 1
    accepted_media_types: tuple[str, ...] = ()
    accepted_extensions: tuple[str, ...] = ()
    binding_revision: str = ""

    def __post_init__(self) -> None:
        role = str(self.role or "").strip()
        if not role or any(char in role for char in "/\\\r\n{}@:") or any(
            char.isspace() for char in role
        ):
            raise ValueError(
                "role must be a token-safe identifier without whitespace, paths, "
                "braces, @, or colon"
            )
        object.__setattr__(self, "role", role)
        if not isinstance(self.label, str):
            raise TypeError("label must be a string")
        if not isinstance(self.source_path, str):
            raise TypeError("source_path must be a string")
        source_path = self.source_path.strip()
        try:
            source_kind = (
                self.source_kind
                if isinstance(self.source_kind, AttachmentSourceKind)
                else AttachmentSourceKind(str(self.source_kind))
            )
        except ValueError as exc:
            raise ValueError("source_kind is not supported") from exc
        try:
            processing_mode = (
                self.processing_mode
                if isinstance(self.processing_mode, AttachmentProcessingMode)
                else AttachmentProcessingMode(str(self.processing_mode))
            )
        except ValueError as exc:
            raise ValueError("processing_mode is not supported") from exc
        if not isinstance(self.recursive, bool):
            raise TypeError("recursive must be a boolean")
        if self.recursive and source_kind is not AttachmentSourceKind.DIRECTORY_PACKAGE:
            raise ValueError("recursive is only valid for directory_package")
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "processing_mode", processing_mode)
        try:
            cardinality = (
                self.cardinality
                if isinstance(self.cardinality, AttachmentCardinality)
                else AttachmentCardinality(str(self.cardinality))
            )
        except ValueError as exc:
            raise ValueError("cardinality must be single or multiple") from exc
        expected_cardinality = (
            AttachmentCardinality.SINGLE
            if source_kind is AttachmentSourceKind.SINGLE_FILE
            else AttachmentCardinality.MULTIPLE
        )
        if cardinality is not expected_cardinality:
            raise ValueError(
                "cardinality conflicts with source_kind: "
                f"{cardinality.value}/{source_kind.value}"
            )
        object.__setattr__(self, "cardinality", expected_cardinality)
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")
        min_items = _as_nonnegative_int(self.min_items, "min_items")
        max_items = (
            None
            if self.max_items is None
            else _as_nonnegative_int(self.max_items, "max_items")
        )
        items = tuple(self.items or ())
        if any(not isinstance(item, AttachmentItem) for item in items):
            raise TypeError("items must contain only AttachmentItem values")
        relative_keys = [item.relative_path.casefold() for item in items]
        if len(set(relative_keys)) != len(relative_keys):
            raise ValueError(
                "attachment relative_path values must be unique within a binding"
            )
        if len({item.item_id for item in items}) != len(items):
            raise ValueError("attachment item_id values must be unique within a binding")
        items = tuple(
            replace(item, sequence=index)
            for index, item in enumerate(
                sorted(
                    items,
                    key=lambda item: (
                        attachment_natural_path_key(item.relative_path),
                        item.item_id.casefold(),
                    ),
                )
            )
        )
        if source_kind is AttachmentSourceKind.SINGLE_FILE:
            if len(items) > 1:
                raise ValueError("single attachment bindings cannot contain multiple items")
            max_items = 1
            min_items = min(min_items, 1)
            if not source_path and items:
                source_path = items[0].file_ref.source_path
        else:
            if max_items == 1:
                max_items = None
            if max_items is not None and max_items < min_items:
                raise ValueError("max_items cannot be less than min_items")
        if max_items is not None and len(items) > max_items:
            raise ValueError("attachment item count exceeds max_items")
        accepted_media_types = _normalize_media_types(self.accepted_media_types)
        accepted_extensions = _normalize_extensions(self.accepted_extensions)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "min_items", min_items)
        object.__setattr__(self, "max_items", max_items)
        object.__setattr__(self, "accepted_media_types", accepted_media_types)
        object.__setattr__(self, "accepted_extensions", accepted_extensions)
        for item in items:
            self.validate_item(item)
        if source_kind is AttachmentSourceKind.DIRECTORY_PACKAGE and not source_path:
            raise ValueError("directory_package requires source_path")
        computed_revision = compute_attachment_binding_revision(
            role=role,
            source_kind=source_kind,
            recursive=self.recursive,
            processing_mode=processing_mode,
            items=items,
        )
        object.__setattr__(self, "binding_revision", computed_revision)

    @property
    def anchor_token(self) -> str:
        """Derived template identity; never persisted as a second truth."""

        return material_token(MaterialTokenNamespace.ATTACHMENT, self.role)

    @property
    def rule_id(self) -> str:
        return "attachment:" + self.role

    @property
    def token_required(self) -> bool:
        """Delivery requirement and template occurrence are independent."""

        return False

    @property
    def occurrence_policy(self) -> str:
        return "exactly_one"

    @property
    def render_mode(self) -> AttachmentRenderMode:
        return AttachmentRenderMode.INVENTORY_BLOCK

    def validate_item(self, item: AttachmentItem) -> None:
        """Enforce this role's declared MIME and extension boundary."""

        if not isinstance(item, AttachmentItem):
            raise TypeError("item must be an AttachmentItem")
        media_type = item.file_ref.media_type.strip().casefold()
        if self.accepted_media_types and not any(
            _media_type_matches(media_type, accepted)
            for accepted in self.accepted_media_types
        ):
            raise ValueError(
                f"attachment_media_type_not_allowed:{self.role}:{item.item_id}:"
                f"{item.file_ref.media_type}"
            )
        extension = Path(item.file_ref.original_name).suffix.casefold()
        if self.accepted_extensions and extension not in self.accepted_extensions:
            raise ValueError(
                f"attachment_extension_not_allowed:{self.role}:{item.item_id}:"
                f"{extension or '<none>'}"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "label": self.label,
            "source_kind": self.source_kind.value,
            "source_path": self.source_path,
            "recursive": self.recursive,
            "processing_mode": self.processing_mode.value,
            "cardinality": self.cardinality.value,
            "items": [item.to_dict() for item in self.items],
            "required": self.required,
            "min_items": self.min_items,
            "max_items": self.max_items,
            "accepted_media_types": list(self.accepted_media_types),
            "accepted_extensions": list(self.accepted_extensions),
            "binding_revision": self.binding_revision,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "AttachmentBinding":
        raw_items = payload.get("items", ())
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            raise TypeError("items must be a sequence")
        items: list[AttachmentItem] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                raise TypeError("each attachment item must be a mapping")
            items.append(AttachmentItem.from_dict(raw_item))
        raw_max = payload.get("max_items", 1)
        raw_media_types = payload.get("accepted_media_types", ())
        raw_extensions = payload.get("accepted_extensions", ())
        if not isinstance(raw_media_types, Sequence) or isinstance(
            raw_media_types, (str, bytes)
        ):
            raise TypeError("accepted_media_types must be a sequence")
        if not isinstance(raw_extensions, Sequence) or isinstance(
            raw_extensions, (str, bytes)
        ):
            raise TypeError("accepted_extensions must be a sequence")
        raw_source_kind = payload.get("source_kind")
        if raw_source_kind in (None, ""):
            # Non-destructive v3 migration. Multiple never implied a folder.
            source_kind = (
                AttachmentSourceKind.FILE_SET
                if str(payload.get("cardinality", "single") or "single")
                == AttachmentCardinality.MULTIPLE.value
                else AttachmentSourceKind.SINGLE_FILE
            )
        else:
            try:
                source_kind = AttachmentSourceKind(str(raw_source_kind))
            except ValueError as exc:
                raise ValueError("source_kind is not supported") from exc
            raw_cardinality = AttachmentCardinality(
                str(payload.get("cardinality", "single") or "single")
            )
            expected = (
                AttachmentCardinality.SINGLE
                if source_kind is AttachmentSourceKind.SINGLE_FILE
                else AttachmentCardinality.MULTIPLE
            )
            if raw_cardinality is not expected:
                raise ValueError("cardinality conflicts with source_kind")
        source_path = str(payload.get("source_path", "") or "").strip()
        if not source_path and source_kind is AttachmentSourceKind.SINGLE_FILE and items:
            source_path = items[0].file_ref.source_path
        supplied_revision = str(payload.get("binding_revision", "") or "").strip()
        binding = cls(
            role=str(payload.get("role", "") or ""),
            label=str(payload.get("label", "") or ""),
            source_kind=source_kind,
            source_path=source_path,
            recursive=_as_bool(payload.get("recursive", False), "recursive"),
            processing_mode=str(
                payload.get("processing_mode", "passthrough") or "passthrough"
            ),
            cardinality=(
                AttachmentCardinality.SINGLE
                if source_kind is AttachmentSourceKind.SINGLE_FILE
                else AttachmentCardinality.MULTIPLE
            ),
            items=tuple(items),
            required=_as_bool(payload.get("required", False), "required"),
            min_items=_as_nonnegative_int(payload.get("min_items", 0), "min_items"),
            max_items=(
                None
                if raw_max is None
                else _as_nonnegative_int(raw_max, "max_items")
            ),
            accepted_media_types=tuple(str(item) for item in raw_media_types),
            accepted_extensions=tuple(str(item) for item in raw_extensions),
            binding_revision="",
        )
        if supplied_revision and supplied_revision.casefold() != binding.binding_revision:
            raise ValueError("binding_revision does not match canonical binding facts")
        return binding


def normalize_attachment_relative_path(value: object) -> str:
    """Return one portable POSIX file path or reject an unsafe path."""

    raw = unicodedata.normalize("NFC", str(value or "").strip()).replace("\\", "/")
    if (
        not raw
        or raw.startswith("/")
        or raw.endswith("/")
        or "//" in raw
        or re.match(r"^[A-Za-z]:", raw)
        or "\x00" in raw
    ):
        raise ValueError(f"attachment_relative_path_invalid:{value}")
    segments = raw.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"attachment_relative_path_invalid:{value}")
    if any(any(char in segment for char in '<>:"|?*') for segment in segments):
        raise ValueError(f"attachment_relative_path_invalid:{value}")
    normalized = PurePosixPath(*segments).as_posix()
    if normalized != raw:
        raise ValueError(f"attachment_relative_path_not_normalized:{value}")
    return normalized


def attachment_natural_path_key(value: str) -> tuple[tuple[tuple[int, object], ...], ...]:
    """Case-insensitive natural ordering over every relative-path segment."""

    path = normalize_attachment_relative_path(value)
    return tuple(
        tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in re.split(r"(\d+)", segment.casefold())
            if part
        )
        for segment in path.split("/")
    )


def compute_attachment_binding_revision(
    *,
    role: str,
    source_kind: AttachmentSourceKind,
    recursive: bool,
    processing_mode: AttachmentProcessingMode,
    items: Sequence[AttachmentItem],
) -> str:
    payload = {
        "contract_version": ATTACHMENT_BINDING_CONTRACT_VERSION,
        "role": role,
        "source_kind": source_kind.value,
        "recursive": recursive,
        "processing_mode": processing_mode.value,
        "items": [
            {
                "relative_path": item.relative_path,
                "media_type": item.file_ref.media_type,
                "byte_size": item.file_ref.byte_size,
                "content_sha256": item.file_ref.content_sha256,
            }
            for item in items
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AttachmentDocumentPlan:
    plan_id: str
    snapshot_id: str
    consumer_id: str
    binding_role: str
    item_id: str
    input_ref: FileAssetRef
    output_relative_path: str
    dependency_index_id: str
    resolved_image_plans: tuple[ResolvedImageInsertionPlan, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "consumer_id",
            "binding_role",
            "item_id",
            "dependency_index_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not _SHA256_PATTERN.fullmatch(self.snapshot_id):
            raise ValueError("snapshot_id must be a lowercase SHA-256")
        if not _SHA256_PATTERN.fullmatch(self.dependency_index_id):
            raise ValueError("dependency_index_id must be a lowercase SHA-256")
        if not isinstance(self.input_ref, FileAssetRef):
            raise TypeError("input_ref must be a FileAssetRef")
        object.__setattr__(
            self,
            "output_relative_path",
            normalize_attachment_relative_path(self.output_relative_path),
        )
        image_plans = tuple(self.resolved_image_plans or ())
        if any(not isinstance(item, ResolvedImageInsertionPlan) for item in image_plans):
            raise TypeError(
                "resolved_image_plans must contain ResolvedImageInsertionPlan values"
            )
        object.__setattr__(self, "resolved_image_plans", image_plans)
        payload = self._identity_payload()
        computed = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        supplied = str(self.plan_id or "").strip()
        if supplied and supplied != computed:
            raise ValueError("plan_id does not match canonical attachment plan")
        object.__setattr__(self, "plan_id", computed)

    def _identity_payload(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "consumer_id": self.consumer_id,
            "binding_role": self.binding_role,
            "item_id": self.item_id,
            "input_ref": self.input_ref.to_dict(),
            "output_relative_path": self.output_relative_path,
            "dependency_index_id": self.dependency_index_id,
            "resolved_image_plans": [
                item.to_dict() for item in self.resolved_image_plans
            ],
        }

    def to_dict(self) -> dict[str, object]:
        return {"plan_id": self.plan_id, **self._identity_payload()}


@dataclass(frozen=True, slots=True)
class AttachmentFileReceipt:
    consumer_id: str
    item_id: str
    relative_path: str
    input_sha256: str
    output_sha256: str
    output_byte_size: int
    status: AttachmentFileStatus
    field_replacement_count: int = 0
    replaced_field_keys: tuple[str, ...] = ()
    image_job_count: int = 0
    unresolved_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("consumer_id", "item_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(
            self,
            "relative_path",
            normalize_attachment_relative_path(self.relative_path),
        )
        for name in ("input_sha256", "output_sha256"):
            if not isinstance(getattr(self, name), str) or not _SHA256_PATTERN.fullmatch(
                getattr(self, name)
            ):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if (
            isinstance(self.output_byte_size, bool)
            or not isinstance(self.output_byte_size, int)
            or self.output_byte_size < 0
        ):
            raise ValueError("output_byte_size must be a non-negative integer")
        try:
            status = (
                self.status
                if isinstance(self.status, AttachmentFileStatus)
                else AttachmentFileStatus(str(self.status))
            )
        except ValueError as exc:
            raise ValueError("unsupported attachment file status") from exc
        object.__setattr__(self, "status", status)
        for name in ("field_replacement_count", "image_job_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        object.__setattr__(
            self,
            "replaced_field_keys",
            tuple(dict.fromkeys(str(item) for item in self.replaced_field_keys)),
        )
        object.__setattr__(
            self,
            "unresolved_tokens",
            tuple(dict.fromkeys(str(item) for item in self.unresolved_tokens)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "consumer_id": self.consumer_id,
            "item_id": self.item_id,
            "relative_path": self.relative_path,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "output_byte_size": self.output_byte_size,
            "status": self.status.value,
            "field_replacement_count": self.field_replacement_count,
            "replaced_field_keys": list(self.replaced_field_keys),
            "image_job_count": self.image_job_count,
            "unresolved_tokens": list(self.unresolved_tokens),
        }


@dataclass(frozen=True, slots=True)
class AttachmentBundleReceipt:
    snapshot_id: str
    binding_role: str
    binding_revision: str
    dependency_index_id: str
    output_directory: str
    files: tuple[AttachmentFileReceipt, ...]
    bundle_sha256: str = ""
    receipt_id: str = ""

    def __post_init__(self) -> None:
        for name in ("snapshot_id", "binding_revision", "dependency_index_id"):
            if not isinstance(getattr(self, name), str) or not _SHA256_PATTERN.fullmatch(
                getattr(self, name)
            ):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if not isinstance(self.binding_role, str) or not self.binding_role.strip():
            raise ValueError("binding_role must not be empty")
        if not isinstance(self.output_directory, str) or not self.output_directory.strip():
            raise ValueError("output_directory must not be empty")
        files = tuple(self.files or ())
        if any(not isinstance(item, AttachmentFileReceipt) for item in files):
            raise TypeError("files must contain AttachmentFileReceipt values")
        if len({item.item_id for item in files}) != len(files):
            raise ValueError("attachment receipt item_id values must be unique")
        if len({item.relative_path.casefold() for item in files}) != len(files):
            raise ValueError("attachment receipt relative paths must be unique")
        files = tuple(sorted(files, key=lambda item: attachment_natural_path_key(item.relative_path)))
        object.__setattr__(self, "files", files)
        bundle_payload = [
            {
                "relative_path": item.relative_path,
                "output_sha256": item.output_sha256,
                "status": item.status.value,
            }
            for item in files
        ]
        computed_bundle = sha256(
            _canonical_json(bundle_payload).encode("utf-8")
        ).hexdigest()
        supplied_bundle = str(self.bundle_sha256 or "").strip()
        if supplied_bundle and supplied_bundle != computed_bundle:
            raise ValueError("bundle_sha256 does not match file receipts")
        object.__setattr__(self, "bundle_sha256", computed_bundle)
        identity = {
            "snapshot_id": self.snapshot_id,
            "binding_role": self.binding_role,
            "binding_revision": self.binding_revision,
            "dependency_index_id": self.dependency_index_id,
            "bundle_sha256": computed_bundle,
            "files": [item.to_dict() for item in files],
        }
        computed_receipt = sha256(
            _canonical_json(identity).encode("utf-8")
        ).hexdigest()
        supplied_receipt = str(self.receipt_id or "").strip()
        if supplied_receipt and supplied_receipt != computed_receipt:
            raise ValueError("receipt_id does not match attachment bundle facts")
        object.__setattr__(self, "receipt_id", computed_receipt)

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "snapshot_id": self.snapshot_id,
            "binding_role": self.binding_role,
            "binding_revision": self.binding_revision,
            "dependency_index_id": self.dependency_index_id,
            "output_directory": self.output_directory,
            "files": [item.to_dict() for item in self.files],
            "bundle_sha256": self.bundle_sha256,
        }


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _as_nonnegative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return value


def _as_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _normalize_media_types(values: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError("accepted_media_types must be a sequence")
    normalized: set[str] = set()
    for raw in values:
        value = str(raw or "").strip().casefold()
        if not re.fullmatch(r"[a-z0-9!#$&^_.+-]+/(?:[a-z0-9!#$&^_.+-]+|\*)", value):
            raise ValueError(f"invalid accepted media type: {raw!r}")
        normalized.add(value)
    return tuple(sorted(normalized))


def _normalize_extensions(values: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError("accepted_extensions must be a sequence")
    normalized: set[str] = set()
    for raw in values:
        value = str(raw or "").strip().casefold()
        if value and not value.startswith("."):
            value = "." + value
        if not re.fullmatch(r"\.[a-z0-9][a-z0-9._+-]*", value):
            raise ValueError(f"invalid accepted extension: {raw!r}")
        normalized.add(value)
    return tuple(sorted(normalized))


def _media_type_matches(actual: str, accepted: str) -> bool:
    if accepted.endswith("/*"):
        return actual.startswith(accepted[:-1])
    return actual == accepted


__all__ = [
    "ATTACHMENT_BINDING_CONTRACT_VERSION",
    "AttachmentBinding",
    "AttachmentBundleReceipt",
    "AttachmentCardinality",
    "AttachmentDocumentPlan",
    "AttachmentFileReceipt",
    "AttachmentFileStatus",
    "AttachmentItem",
    "AttachmentProcessingMode",
    "AttachmentRenderMode",
    "AttachmentRoleSpec",
    "AttachmentSourceKind",
    "FileAssetRef",
    "attachment_natural_path_key",
    "compute_attachment_binding_revision",
    "normalize_attachment_relative_path",
]
