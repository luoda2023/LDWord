"""Central contract for every user-visible material token.

The public namespace describes what a user believes the token represents.
The internal ``kind`` describes how the assembly engine must consume it, and
``producer`` records where its value/resource is produced.  Only the namespace
is persisted as editable token syntax; ``kind`` is always derived from this
registry so the two facts cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping


MATERIAL_TOKEN_PATTERN = re.compile(r"\{\{([^{}\r\n]+)\}\}")
MATERIAL_TOKEN_CONTRACT_VERSION = "material-token-v1"
_TOKEN_KEY_PATTERN = re.compile(r"@([a-z]+):([^\s{}:@]+)", re.IGNORECASE)


class _StringEnum(str, Enum):
    pass


class MaterialTokenNamespace(_StringEnum):
    """Stable, short vocabulary visible in a DOCX template."""

    TEXT = "text"
    FILE = "file"
    TIME = "time"
    IMAGE = "img"
    ATTACHMENT = "attach"


class MaterialTokenKind(_StringEnum):
    """Internal renderer shape; never independently user-editable."""

    FIELD = "field"
    CONTENT = "content"
    IMAGE = "image"
    ATTACHMENT = "attachment"


class MaterialTokenProducer(_StringEnum):
    """Source of a frozen value/resource, independent from renderer shape."""

    MANUAL = "manual"
    FUNCTION = "function"
    TIMELINE = "timeline"
    FILE_BINDING = "file_binding"
    IMAGE_BINDING = "image_binding"
    ATTACHMENT_BINDING = "attachment_binding"


@dataclass(frozen=True, slots=True)
class MaterialTokenNamespaceSpec:
    namespace: MaterialTokenNamespace
    kind: MaterialTokenKind
    default_producer: MaterialTokenProducer
    allowed_producers: frozenset[MaterialTokenProducer]
    requires_declaration: bool
    isolated_body_paragraph: bool = False

    def __post_init__(self) -> None:
        if self.default_producer not in self.allowed_producers:
            raise ValueError("default_producer must be allowed")


_SPECS = (
    MaterialTokenNamespaceSpec(
        MaterialTokenNamespace.TEXT,
        MaterialTokenKind.FIELD,
        MaterialTokenProducer.MANUAL,
        frozenset({MaterialTokenProducer.MANUAL, MaterialTokenProducer.FUNCTION}),
        requires_declaration=False,
    ),
    MaterialTokenNamespaceSpec(
        MaterialTokenNamespace.FILE,
        MaterialTokenKind.CONTENT,
        MaterialTokenProducer.FILE_BINDING,
        frozenset({MaterialTokenProducer.FILE_BINDING}),
        requires_declaration=True,
        isolated_body_paragraph=True,
    ),
    MaterialTokenNamespaceSpec(
        MaterialTokenNamespace.TIME,
        MaterialTokenKind.FIELD,
        MaterialTokenProducer.TIMELINE,
        frozenset({MaterialTokenProducer.TIMELINE}),
        requires_declaration=False,
    ),
    MaterialTokenNamespaceSpec(
        MaterialTokenNamespace.IMAGE,
        MaterialTokenKind.IMAGE,
        MaterialTokenProducer.IMAGE_BINDING,
        frozenset({MaterialTokenProducer.IMAGE_BINDING}),
        requires_declaration=True,
    ),
    MaterialTokenNamespaceSpec(
        MaterialTokenNamespace.ATTACHMENT,
        MaterialTokenKind.ATTACHMENT,
        MaterialTokenProducer.ATTACHMENT_BINDING,
        frozenset({MaterialTokenProducer.ATTACHMENT_BINDING}),
        requires_declaration=True,
        isolated_body_paragraph=True,
    ),
)

MATERIAL_TOKEN_NAMESPACE_REGISTRY: Mapping[
    MaterialTokenNamespace, MaterialTokenNamespaceSpec
] = MappingProxyType({item.namespace: item for item in _SPECS})


@dataclass(frozen=True, slots=True)
class MaterialTokenRef:
    """Parsed token identity with derived, non-editable engine semantics."""

    namespace: MaterialTokenNamespace
    identifier: str

    def __post_init__(self) -> None:
        namespace = _coerce_enum(self.namespace, MaterialTokenNamespace, "namespace")
        identifier = str(self.identifier or "").strip()
        if not identifier or not re.fullmatch(r"[^\s{}:@]+", identifier):
            raise ValueError(
                "material token identifier must not be empty or contain whitespace, "
                "braces, @, or colon"
            )
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "identifier", identifier)

    @property
    def spec(self) -> MaterialTokenNamespaceSpec:
        return MATERIAL_TOKEN_NAMESPACE_REGISTRY[self.namespace]

    @property
    def kind(self) -> MaterialTokenKind:
        return self.spec.kind

    @property
    def default_producer(self) -> MaterialTokenProducer:
        return self.spec.default_producer

    @property
    def key(self) -> str:
        return f"@{self.namespace.value}:{self.identifier}"

    @property
    def token(self) -> str:
        return "{{" + self.key + "}}"

    @property
    def locked_prefix(self) -> str:
        return "{{@" + self.namespace.value + ":"

    def validate_kind(self, kind: MaterialTokenKind | str) -> MaterialTokenKind:
        resolved = _coerce_enum(kind, MaterialTokenKind, "kind")
        if resolved is not self.kind:
            raise ValueError(
                f"namespace @{self.namespace.value}: derives kind={self.kind.value}; "
                f"kind={resolved.value} conflicts with the token contract"
            )
        return resolved

    def validate_producer(
        self, producer: MaterialTokenProducer | str | None
    ) -> MaterialTokenProducer:
        if producer in (None, ""):
            return self.default_producer
        resolved = _coerce_enum(producer, MaterialTokenProducer, "producer")
        if resolved not in self.spec.allowed_producers:
            allowed = ", ".join(
                item.value
                for item in sorted(
                    self.spec.allowed_producers, key=lambda item: item.value
                )
            )
            raise ValueError(
                f"producer={resolved.value} is not valid for @{self.namespace.value}:; "
                f"expected one of: {allowed}"
            )
        return resolved


@dataclass(frozen=True, slots=True)
class FrozenMaterialTokenEvidence:
    """Freeze receipt for a derived token classification and resource link."""

    token: str
    kind: MaterialTokenKind
    producer: MaterialTokenProducer
    resource_id: str

    def __post_init__(self) -> None:
        ref = parse_material_token(self.token)
        kind = ref.validate_kind(self.kind)
        producer = ref.validate_producer(self.producer)
        resource_id = str(self.resource_id or "").strip()
        if not resource_id:
            raise ValueError("resource_id must not be empty")
        object.__setattr__(self, "token", ref.token)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "producer", producer)
        object.__setattr__(self, "resource_id", resource_id)

    @property
    def namespace(self) -> MaterialTokenNamespace:
        return parse_material_token(self.token).namespace

    @property
    def identifier(self) -> str:
        return parse_material_token(self.token).identifier

    def to_dict(self) -> dict[str, str]:
        return {
            "token": self.token,
            "namespace": self.namespace.value,
            "identifier": self.identifier,
            "kind": self.kind.value,
            "producer": self.producer.value,
            "resource_id": self.resource_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "FrozenMaterialTokenEvidence":
        if not isinstance(payload, Mapping):
            raise TypeError("token evidence must be a mapping")
        evidence = cls(
            token=str(payload.get("token", "") or ""),
            kind=str(payload.get("kind", "") or ""),
            producer=str(payload.get("producer", "") or ""),
            resource_id=str(payload.get("resource_id", "") or ""),
        )
        if str(payload.get("namespace", "") or "") != evidence.namespace.value:
            raise ValueError("token evidence namespace conflicts with token")
        if str(payload.get("identifier", "") or "") != evidence.identifier:
            raise ValueError("token evidence identifier conflicts with token")
        return evidence

def parse_material_token(value: object) -> MaterialTokenRef:
    """Parse one strict namespaced key/token; unnamespaced tokens are invalid."""

    if not isinstance(value, str):
        raise TypeError("material token must be a string")
    text = value.strip()
    if text.startswith("{{") or text.endswith("}}"):
        match = MATERIAL_TOKEN_PATTERN.fullmatch(text)
        if match is None or match.group(1) != match.group(1).strip():
            raise ValueError(f"invalid material token: {value!r}")
        key = match.group(1)
    else:
        key = text
    match = _TOKEN_KEY_PATTERN.fullmatch(key)
    if match is None:
        raise ValueError(
            "material token must use one of the registered namespaces: "
            + ", ".join(f"@{item.value}:" for item in MaterialTokenNamespace)
        )
    try:
        namespace = MaterialTokenNamespace(match.group(1).casefold())
    except ValueError as exc:
        raise ValueError(f"unknown material token namespace: @{match.group(1)}:") from exc
    return MaterialTokenRef(namespace, match.group(2))


def try_parse_material_token(value: object) -> MaterialTokenRef | None:
    """Return a parsed reference or ``None`` at UI/scanner classification seams."""

    try:
        return parse_material_token(value)
    except (TypeError, ValueError):
        return None


def material_token(
    namespace: MaterialTokenNamespace | str,
    identifier: object,
) -> str:
    """Format the canonical token for a namespace and logical identifier."""

    resolved_namespace = _coerce_enum(
        namespace, MaterialTokenNamespace, "namespace"
    )
    return MaterialTokenRef(resolved_namespace, str(identifier or "")).token


def normalize_material_token(
    value: object,
    *,
    namespace: MaterialTokenNamespace | str | None = None,
) -> str:
    """Return canonical syntax, optionally applying a namespace to an id."""

    if namespace is None:
        return parse_material_token(value).token
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{{") or stripped.startswith("@"):
            ref = parse_material_token(stripped)
            expected = _coerce_enum(namespace, MaterialTokenNamespace, "namespace")
            if ref.namespace is not expected:
                raise ValueError(
                    f"expected @{expected.value}: token, got @{ref.namespace.value}:"
                )
            return ref.token
    return material_token(namespace, value)


def material_token_key(value: object) -> str:
    return parse_material_token(value).key


def material_token_identifier(value: object) -> str:
    return parse_material_token(value).identifier


def material_token_kind(value: object) -> MaterialTokenKind:
    return parse_material_token(value).kind


def material_token_prefix(namespace: MaterialTokenNamespace | str) -> str:
    resolved = _coerce_enum(namespace, MaterialTokenNamespace, "namespace")
    return "{{@" + resolved.value + ":"


def _coerce_enum(value, enum_type, name: str):
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{name} must be one of: {allowed}") from exc


__all__ = [
    "FrozenMaterialTokenEvidence",
    "MATERIAL_TOKEN_CONTRACT_VERSION",
    "MATERIAL_TOKEN_NAMESPACE_REGISTRY",
    "MATERIAL_TOKEN_PATTERN",
    "MaterialTokenKind",
    "MaterialTokenNamespace",
    "MaterialTokenNamespaceSpec",
    "MaterialTokenProducer",
    "MaterialTokenRef",
    "material_token",
    "material_token_identifier",
    "material_token_key",
    "material_token_kind",
    "material_token_prefix",
    "normalize_material_token",
    "parse_material_token",
    "try_parse_material_token",
]
