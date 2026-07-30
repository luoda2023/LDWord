"""Typed findings and receipts shared by every content source compiler."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from src.config.content_artifacts import ContentArtifactRef
from src.config.content_materials import DocumentFragment


class ContentImportDisposition(str, Enum):
    IGNORED = "ignored"
    NORMALIZED = "normalized"
    WARNING = "warning"
    BLOCKER = "blocker"


_DISPOSITION_PRIORITY = {
    ContentImportDisposition.IGNORED: 0,
    ContentImportDisposition.NORMALIZED: 1,
    ContentImportDisposition.WARNING: 2,
    ContentImportDisposition.BLOCKER: 3,
}


def _normalized_context(
    value: Mapping[str, object] | Sequence[tuple[str, object]],
) -> tuple[tuple[str, str], ...]:
    items = value.items() if isinstance(value, Mapping) else value
    normalized = tuple(
        sorted(
            (
                (str(key or "").strip(), str(item or "").strip())
                for key, item in items
                if str(key or "").strip() and str(item or "").strip()
            ),
            key=lambda pair: pair[0].casefold(),
        )
    )
    if len({key.casefold() for key, _item in normalized}) != len(normalized):
        raise ValueError("technical_context contains duplicate keys")
    return normalized


@dataclass(frozen=True, slots=True)
class ContentImportFinding:
    code: str
    disposition: ContentImportDisposition
    scope: str
    object_id: str
    message_key: str
    user_message: str
    cause_id: str = ""
    count: int = 1
    technical_context: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "code",
            "scope",
            "object_id",
            "message_key",
            "user_message",
        ):
            normalized = str(getattr(self, name) or "").strip()
            if not normalized:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, normalized)
        if not isinstance(self.disposition, ContentImportDisposition):
            object.__setattr__(
                self,
                "disposition",
                ContentImportDisposition(str(self.disposition)),
            )
        object.__setattr__(self, "cause_id", str(self.cause_id or "").strip())
        if isinstance(self.count, bool) or int(self.count) < 1:
            raise ValueError("count must be a positive integer")
        object.__setattr__(self, "count", int(self.count))
        object.__setattr__(
            self,
            "technical_context",
            _normalized_context(self.technical_context),
        )

    @property
    def grouping_id(self) -> str:
        return self.cause_id or self.object_id

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "disposition": self.disposition.value,
            "scope": self.scope,
            "object_id": self.object_id,
            "cause_id": self.cause_id,
            "count": self.count,
            "message_key": self.message_key,
            "user_message": self.user_message,
            "technical_context": dict(self.technical_context),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentImportFinding":
        context = payload.get("technical_context", {})
        if not isinstance(context, Mapping):
            raise TypeError("technical_context must be a mapping")
        return cls(
            code=str(payload.get("code", "") or ""),
            disposition=ContentImportDisposition(
                str(payload.get("disposition", "") or "")
            ),
            scope=str(payload.get("scope", "") or ""),
            object_id=str(payload.get("object_id", "") or ""),
            cause_id=str(payload.get("cause_id", "") or ""),
            count=int(payload.get("count", 1) or 1),
            message_key=str(payload.get("message_key", "") or ""),
            user_message=str(payload.get("user_message", "") or ""),
            technical_context=tuple(context.items()),
        )


def aggregate_content_findings(
    findings: Sequence[ContentImportFinding],
) -> tuple[ContentImportFinding, ...]:
    """Collapse XML-level evidence into stable root-cause findings."""

    grouped: dict[tuple[str, str], list[ContentImportFinding]] = {}
    for finding in tuple(findings or ()):
        if not isinstance(finding, ContentImportFinding):
            raise TypeError("findings must contain only ContentImportFinding values")
        grouped.setdefault((finding.scope, finding.grouping_id), []).append(finding)

    output: list[ContentImportFinding] = []
    for (_scope, _grouping_id), members in grouped.items():
        primary = max(
            members,
            key=lambda item: (
                _DISPOSITION_PRIORITY[item.disposition],
                -members.index(item),
            ),
        )
        contexts: dict[str, str] = {}
        for member in members:
            for key, value in member.technical_context:
                contexts.setdefault(key, value)
        output.append(
            ContentImportFinding(
                code=primary.code,
                disposition=primary.disposition,
                scope=primary.scope,
                object_id=primary.object_id,
                cause_id=primary.cause_id,
                count=max(item.count for item in members),
                message_key=primary.message_key,
                user_message=primary.user_message,
                technical_context=tuple(contexts.items()),
            )
        )
    return tuple(
        sorted(
            output,
            key=lambda item: (
                -_DISPOSITION_PRIORITY[item.disposition],
                item.scope.casefold(),
                item.object_id.casefold(),
                item.code.casefold(),
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class ContentSemanticInventory:
    normalized_text_sha256: str
    block_counts: tuple[tuple[str, int], ...] = ()
    heading_count: int = 0
    list_item_count: int = 0
    table_cell_count: int = 0
    image_count: int = 0
    field_token_count: int = 0
    page_break_count: int = 0

    def __post_init__(self) -> None:
        digest = str(self.normalized_text_sha256 or "").strip().casefold()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("normalized_text_sha256 must be a SHA-256 digest")
        object.__setattr__(self, "normalized_text_sha256", digest)
        counts = tuple(sorted(self.block_counts, key=lambda item: item[0].casefold()))
        if any(not str(name or "").strip() or int(count) < 0 for name, count in counts):
            raise ValueError("block_counts must contain non-negative named counts")
        if len({name.casefold() for name, _count in counts}) != len(counts):
            raise ValueError("block_counts contains duplicate names")
        object.__setattr__(
            self,
            "block_counts",
            tuple((str(name), int(count)) for name, count in counts),
        )
        for name in (
            "heading_count",
            "list_item_count",
            "table_cell_count",
            "image_count",
            "field_token_count",
            "page_break_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or int(value) < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            object.__setattr__(self, name, int(value))

    @classmethod
    def empty(cls) -> "ContentSemanticInventory":
        return cls(sha256(b"").hexdigest())

    def to_dict(self) -> dict[str, object]:
        return {
            "normalized_text_sha256": self.normalized_text_sha256,
            "block_counts": dict(self.block_counts),
            "heading_count": self.heading_count,
            "list_item_count": self.list_item_count,
            "table_cell_count": self.table_cell_count,
            "image_count": self.image_count,
            "field_token_count": self.field_token_count,
            "page_break_count": self.page_break_count,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentSemanticInventory":
        counts = payload.get("block_counts", {})
        if not isinstance(counts, Mapping):
            raise TypeError("block_counts must be a mapping")
        return cls(
            normalized_text_sha256=str(payload.get("normalized_text_sha256", "") or ""),
            block_counts=tuple((str(key), int(value)) for key, value in counts.items()),
            heading_count=int(payload.get("heading_count", 0) or 0),
            list_item_count=int(payload.get("list_item_count", 0) or 0),
            table_cell_count=int(payload.get("table_cell_count", 0) or 0),
            image_count=int(payload.get("image_count", 0) or 0),
            field_token_count=int(payload.get("field_token_count", 0) or 0),
            page_break_count=int(payload.get("page_break_count", 0) or 0),
        )


@dataclass(frozen=True, slots=True)
class ContentCompileReceipt:
    compiler_contract: str
    parser_contract: str
    source_sha256: str
    inventory: ContentSemanticInventory
    findings: tuple[ContentImportFinding, ...] = ()
    receipt_id: str = ""

    def __post_init__(self) -> None:
        for name in ("compiler_contract", "parser_contract"):
            normalized = str(getattr(self, name) or "").strip()
            if not normalized:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, normalized)
        digest = str(self.source_sha256 or "").strip().casefold()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("source_sha256 must be a SHA-256 digest")
        object.__setattr__(self, "source_sha256", digest)
        if not isinstance(self.inventory, ContentSemanticInventory):
            raise TypeError("inventory must be ContentSemanticInventory")
        findings = aggregate_content_findings(self.findings)
        if any(item.disposition is ContentImportDisposition.BLOCKER for item in findings):
            raise ValueError("a published compile receipt cannot contain blockers")
        object.__setattr__(self, "findings", findings)
        computed_id = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        supplied = str(self.receipt_id or "").strip().casefold()
        if supplied and supplied != computed_id:
            raise ValueError("receipt_id does not match canonical receipt payload")
        object.__setattr__(self, "receipt_id", computed_id)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "compiler_contract": self.compiler_contract,
            "parser_contract": self.parser_contract,
            "source_sha256": self.source_sha256,
            "inventory": self.inventory.to_dict(),
            "findings": [item.to_dict() for item in self.findings],
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

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContentCompileReceipt":
        inventory = payload.get("inventory", {})
        raw_findings = payload.get("findings", ())
        if not isinstance(inventory, Mapping):
            raise TypeError("inventory must be a mapping")
        if not isinstance(raw_findings, Sequence) or isinstance(raw_findings, (str, bytes)):
            raise TypeError("findings must be a sequence")
        if any(not isinstance(item, Mapping) for item in raw_findings):
            raise TypeError("each finding must be a mapping")
        return cls(
            compiler_contract=str(payload.get("compiler_contract", "") or ""),
            parser_contract=str(payload.get("parser_contract", "") or ""),
            source_sha256=str(payload.get("source_sha256", "") or ""),
            inventory=ContentSemanticInventory.from_dict(inventory),
            findings=tuple(
                ContentImportFinding.from_dict(item)
                for item in raw_findings
            ),
            receipt_id=str(payload.get("receipt_id", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class ContentCompileResult:
    """Public result of one capture/normalize/publish transaction."""

    findings: tuple[ContentImportFinding, ...]
    inventory: ContentSemanticInventory
    artifact_ref: ContentArtifactRef | None = None
    fragment: DocumentFragment | None = None
    receipt: ContentCompileReceipt | None = None

    def __post_init__(self) -> None:
        findings = aggregate_content_findings(self.findings)
        object.__setattr__(self, "findings", findings)
        if not isinstance(self.inventory, ContentSemanticInventory):
            raise TypeError("inventory must be a ContentSemanticInventory")
        blocked = any(
            item.disposition is ContentImportDisposition.BLOCKER
            for item in findings
        )
        if blocked:
            if self.artifact_ref is not None or self.receipt is not None:
                raise ValueError("blocked compile results cannot publish an artifact")
            if self.fragment is not None and not isinstance(
                self.fragment, DocumentFragment
            ):
                raise TypeError("fragment must be a DocumentFragment when provided")
            return
        if not isinstance(self.artifact_ref, ContentArtifactRef):
            raise ValueError("successful compile results require artifact_ref")
        if not isinstance(self.fragment, DocumentFragment):
            raise ValueError("successful compile results require fragment")
        if not isinstance(self.receipt, ContentCompileReceipt):
            raise ValueError("successful compile results require receipt")
        if self.receipt.inventory != self.inventory:
            raise ValueError("result inventory must match its compile receipt")

    @property
    def blocked(self) -> bool:
        return any(
            item.disposition is ContentImportDisposition.BLOCKER
            for item in self.findings
        )


__all__ = [
    "ContentCompileResult",
    "ContentCompileReceipt",
    "ContentImportDisposition",
    "ContentImportFinding",
    "ContentSemanticInventory",
    "aggregate_content_findings",
]
