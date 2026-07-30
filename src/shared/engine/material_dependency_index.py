"""Pure, consumer-scoped dependency facts for material token occurrences."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType

from src.config.image_materials import ImageOccurrencePolicy
from src.shared.engine.material_token_router import (
    MATERIAL_TOKEN_PATTERN,
    MaterialTokenKind,
    TokenDeclaration,
    TokenDiagnosticSeverity,
    TokenOccurrencePolicy,
    TokenRoutingResult,
    TokenTextBlock,
    normalize_material_token,
    route_material_tokens,
)


MATERIAL_DEPENDENCY_SCANNER_CONTRACT = "material-dependency-scanner-v1"


class MaterialConsumerKind(str, Enum):
    MAIN_DOCUMENT = "main_document"
    CONTENT_SOURCE = "content_source"
    ATTACHMENT_ITEM = "attachment_item"


class DependencyDiagnosticSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class MaterialConsumerRef:
    kind: MaterialConsumerKind
    owner_id: str
    item_id: str = ""

    def __post_init__(self) -> None:
        try:
            kind = (
                self.kind
                if isinstance(self.kind, MaterialConsumerKind)
                else MaterialConsumerKind(str(self.kind))
            )
        except ValueError as exc:
            raise ValueError("unsupported material consumer kind") from exc
        owner_id = str(self.owner_id or "").strip()
        item_id = str(self.item_id or "").strip()
        if not owner_id or any(char in owner_id for char in "\r\n"):
            raise ValueError("owner_id must be a non-empty single-line string")
        if any(char in item_id for char in "\r\n"):
            raise ValueError("item_id must be a single-line string")
        if kind is MaterialConsumerKind.ATTACHMENT_ITEM and not item_id:
            raise ValueError("attachment consumers require item_id")
        if kind is not MaterialConsumerKind.ATTACHMENT_ITEM and item_id:
            raise ValueError("item_id is reserved for attachment consumers")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "owner_id", owner_id)
        object.__setattr__(self, "item_id", item_id)

    @property
    def consumer_id(self) -> str:
        if self.kind is MaterialConsumerKind.MAIN_DOCUMENT:
            return f"main:{self.owner_id}"
        if self.kind is MaterialConsumerKind.CONTENT_SOURCE:
            return f"content:{self.owner_id}"
        return f"attachment:{self.owner_id}:{self.item_id}"

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "owner_id": self.owner_id,
            "item_id": self.item_id,
            "consumer_id": self.consumer_id,
        }


@dataclass(frozen=True, slots=True)
class MaterialConsumerScan:
    consumer: MaterialConsumerRef
    routing: TokenRoutingResult
    replaceable_field_surfaces: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "body",
                "table_or_nested_body",
                "header",
                "footer",
                "other_story",
                "textboxes",
                "content_controls",
            }
        )
    )
    replaceable_image_surfaces: frozenset[str] = field(
        default_factory=lambda: frozenset({"body"})
    )
    replaceable_attachment_surfaces: frozenset[str] = field(
        default_factory=lambda: frozenset({"body"})
    )
    content_replacement_enabled: bool = False
    attachment_replacement_enabled: bool = False
    material_replacement_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.consumer, MaterialConsumerRef):
            raise TypeError("consumer must be a MaterialConsumerRef")
        if not isinstance(self.routing, TokenRoutingResult):
            raise TypeError("routing must be a TokenRoutingResult")
        if self.routing.consumer_id != self.consumer.consumer_id:
            raise ValueError("routing result is not scoped to this consumer")
        for name in (
            "replaceable_field_surfaces",
            "replaceable_image_surfaces",
            "replaceable_attachment_surfaces",
        ):
            values = frozenset(str(item or "").strip() for item in getattr(self, name))
            if not values or "" in values:
                raise ValueError(f"{name} must contain non-empty surface names")
            object.__setattr__(self, name, values)
        if not isinstance(self.content_replacement_enabled, bool):
            raise TypeError("content_replacement_enabled must be a boolean")
        if not isinstance(self.attachment_replacement_enabled, bool):
            raise TypeError("attachment_replacement_enabled must be a boolean")
        if not isinstance(self.material_replacement_enabled, bool):
            raise TypeError("material_replacement_enabled must be a boolean")


@dataclass(frozen=True, slots=True)
class MaterialDependencyOccurrence:
    occurrence_id: str
    consumer: MaterialConsumerRef
    token: str
    kind: MaterialTokenKind
    resource_key: str
    surface: str
    replaceable: bool
    reason: str = ""
    router_occurrence_id: str = ""
    block_id: str = ""
    ordinal: int = 0

    def __post_init__(self) -> None:
        for name in ("occurrence_id", "token", "resource_key", "surface"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.consumer, MaterialConsumerRef):
            raise TypeError("consumer must be a MaterialConsumerRef")
        try:
            kind = (
                self.kind
                if isinstance(self.kind, MaterialTokenKind)
                else MaterialTokenKind(str(self.kind))
            )
        except ValueError as exc:
            raise ValueError("unsupported material token kind") from exc
        object.__setattr__(self, "kind", kind)
        if not isinstance(self.replaceable, bool):
            raise TypeError("replaceable must be a boolean")
        if self.replaceable and self.reason:
            raise ValueError("replaceable dependencies cannot carry a failure reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "occurrence_id": self.occurrence_id,
            "router_occurrence_id": self.router_occurrence_id,
            "consumer": self.consumer.to_dict(),
            "token": self.token,
            "kind": self.kind.value,
            "resource_key": self.resource_key,
            "surface": self.surface,
            "replaceable": self.replaceable,
            "reason": self.reason,
            "block_id": self.block_id,
            "ordinal": self.ordinal,
        }


@dataclass(frozen=True, slots=True)
class MaterialDependencyDiagnostic:
    code: str
    severity: DependencyDiagnosticSeverity
    message: str
    consumer: MaterialConsumerRef
    token: str = ""
    occurrence_id: str = ""
    resource_key: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("diagnostic code must not be empty")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("diagnostic message must not be empty")
        if not isinstance(self.consumer, MaterialConsumerRef):
            raise TypeError("diagnostic consumer must be a MaterialConsumerRef")
        try:
            severity = (
                self.severity
                if isinstance(self.severity, DependencyDiagnosticSeverity)
                else DependencyDiagnosticSeverity(str(self.severity))
            )
        except ValueError as exc:
            raise ValueError("unsupported dependency diagnostic severity") from exc
        object.__setattr__(self, "severity", severity)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "consumer": self.consumer.to_dict(),
            "token": self.token,
            "occurrence_id": self.occurrence_id,
            "resource_key": self.resource_key,
        }


@dataclass(frozen=True, slots=True)
class MaterialDependencyIndex:
    scanner_contract: str
    occurrences: tuple[MaterialDependencyOccurrence, ...]
    diagnostics: tuple[MaterialDependencyDiagnostic, ...] = ()
    source_revisions: Mapping[str, str] = field(default_factory=dict)
    declaration_revision: str = ""
    index_id: str = ""

    def __post_init__(self) -> None:
        if self.scanner_contract != MATERIAL_DEPENDENCY_SCANNER_CONTRACT:
            raise ValueError("unsupported dependency scanner contract")
        occurrences = tuple(self.occurrences or ())
        diagnostics = tuple(self.diagnostics or ())
        if any(not isinstance(item, MaterialDependencyOccurrence) for item in occurrences):
            raise TypeError("occurrences must contain MaterialDependencyOccurrence values")
        if any(not isinstance(item, MaterialDependencyDiagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain MaterialDependencyDiagnostic values")
        if len({item.occurrence_id for item in occurrences}) != len(occurrences):
            raise ValueError("dependency occurrence_id values must be unique")
        occurrences = tuple(
            sorted(
                occurrences,
                key=lambda item: (
                    item.consumer.consumer_id.casefold(),
                    item.ordinal,
                    item.occurrence_id,
                ),
            )
        )
        diagnostics = tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.consumer.consumer_id.casefold(),
                    item.occurrence_id,
                    item.code,
                    item.token,
                ),
            )
        )
        object.__setattr__(self, "occurrences", occurrences)
        object.__setattr__(self, "diagnostics", diagnostics)
        source_revisions = {
            str(key): str(value)
            for key, value in self.source_revisions.items()
        }
        if any(not key.strip() or not value.strip() for key, value in source_revisions.items()):
            raise ValueError("source revisions must have non-empty keys and values")
        object.__setattr__(
            self,
            "source_revisions",
            MappingProxyType(dict(sorted(source_revisions.items()))),
        )
        if not isinstance(self.declaration_revision, str):
            raise TypeError("declaration_revision must be a string")
        supplied = str(self.index_id or "").strip()
        computed = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied and supplied != computed:
            raise ValueError("index_id does not match canonical dependency facts")
        object.__setattr__(self, "index_id", computed)

    @property
    def ok(self) -> bool:
        return not any(
            item.severity is DependencyDiagnosticSeverity.ERROR
            for item in self.diagnostics
        )

    @property
    def consumer_count(self) -> int:
        return len({item.consumer.consumer_id for item in self.occurrences})

    def occurrences_for_resource(
        self,
        kind: MaterialTokenKind,
        resource_key: str,
    ) -> tuple[MaterialDependencyOccurrence, ...]:
        return tuple(
            item
            for item in self.occurrences
            if item.kind is kind and item.resource_key == resource_key
        )

    def occurrences_for_consumer(
        self,
        consumer_id: str,
    ) -> tuple[MaterialDependencyOccurrence, ...]:
        return tuple(
            item
            for item in self.occurrences
            if item.consumer.consumer_id == consumer_id
        )

    def diagnostics_for_consumer(
        self,
        consumer_id: str,
    ) -> tuple[MaterialDependencyDiagnostic, ...]:
        return tuple(
            item
            for item in self.diagnostics
            if item.consumer.consumer_id == consumer_id
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "scanner_contract": self.scanner_contract,
            "occurrences": [item.to_dict() for item in self.occurrences],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "source_revisions": dict(self.source_revisions),
            "declaration_revision": self.declaration_revision,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"index_id": self.index_id, **self.canonical_payload()}


def scan_material_consumer(
    consumer: MaterialConsumerRef,
    text_blocks: Sequence[TokenTextBlock | str | Sequence[str]],
    *,
    image_rules: Iterable[object] = (),
    content_rules: Iterable[object] = (),
    attachment_bindings: Iterable[object] = (),
    declaration_scope: str = "present",
    replaceable_field_surfaces: Iterable[str] | None = None,
    replaceable_image_surfaces: Iterable[str] | None = None,
    content_replacement_enabled: bool = False,
    attachment_replacement_enabled: bool = False,
    material_replacement_enabled: bool = True,
) -> MaterialConsumerScan:
    """Route one consumer independently so occurrence policies never cross files."""

    if not isinstance(consumer, MaterialConsumerRef):
        raise TypeError("consumer must be a MaterialConsumerRef")
    if declaration_scope not in {"present", "all"}:
        raise ValueError("declaration_scope must be present or all")
    blocks = tuple(text_blocks)
    present_tokens = _present_tokens(blocks)
    image_declarations = tuple(
        declaration
        for declaration in (_image_declaration(rule, index) for index, rule in enumerate(image_rules))
        if declaration_scope == "all" or declaration.token in present_tokens
    )
    selected_content_rules = tuple(
        rule
        for rule in content_rules
        if declaration_scope == "all"
        or _rule_token(rule, "anchor_token") in present_tokens
    )
    selected_attachment_bindings = tuple(
        binding
        for binding in attachment_bindings
        if declaration_scope == "all"
        or _rule_token(binding, "anchor_token") in present_tokens
    )
    routing = route_material_tokens(
        blocks,
        image_tokens=image_declarations,
        content_rules=selected_content_rules,
        attachment_rules=selected_attachment_bindings,
        consumer_id=consumer.consumer_id,
    )
    kwargs: dict[str, object] = {
        "consumer": consumer,
        "routing": routing,
        "content_replacement_enabled": content_replacement_enabled,
        "attachment_replacement_enabled": attachment_replacement_enabled,
        "material_replacement_enabled": material_replacement_enabled,
    }
    if replaceable_field_surfaces is not None:
        kwargs["replaceable_field_surfaces"] = frozenset(replaceable_field_surfaces)
    if replaceable_image_surfaces is not None:
        kwargs["replaceable_image_surfaces"] = frozenset(replaceable_image_surfaces)
    return MaterialConsumerScan(**kwargs)


def build_material_dependency_index(
    scans: Sequence[MaterialConsumerScan],
    *,
    field_values: Mapping[str, object],
    field_token_bindings: Mapping[str, str],
    image_rules: Iterable[object] = (),
    image_source_bindings: Iterable[object] = (),
    attachment_bindings: Iterable[object] = (),
    source_revisions: Mapping[str, str] | None = None,
    declaration_revision: str = "",
) -> MaterialDependencyIndex:
    """Resolve routed occurrences to one frozen field/image resource graph."""

    scans = tuple(scans or ())
    if any(not isinstance(scan, MaterialConsumerScan) for scan in scans):
        raise TypeError("scans must contain MaterialConsumerScan values")
    if len({scan.consumer.consumer_id for scan in scans}) != len(scans):
        raise ValueError("consumer scans must have unique consumer ids")
    if not isinstance(field_values, Mapping) or not isinstance(
        field_token_bindings, Mapping
    ):
        raise TypeError("field values and token bindings must be mappings")
    frozen_bindings = MappingProxyType(
        {
            str(key): str(value)
            for key, value in field_token_bindings.items()
        }
    )
    rules_by_token = {
        normalize_material_token(_rule_token(rule, "anchor_token")): rule
        for rule in image_rules
    }
    image_roles_with_sources = {
        str(getattr(item, "role", "") or "") for item in image_source_bindings
    }
    attachment_by_role = {
        str(getattr(item, "role", "") or ""): item
        for item in attachment_bindings
        if str(getattr(item, "role", "") or "").strip()
    }
    occurrences: list[MaterialDependencyOccurrence] = []
    diagnostics: list[MaterialDependencyDiagnostic] = []
    for scan in scans:
        for routing_diagnostic in scan.routing.diagnostics:
            diagnostics.append(
                MaterialDependencyDiagnostic(
                    code=f"token_{routing_diagnostic.code.value}",
                    severity=(
                        DependencyDiagnosticSeverity.ERROR
                        if routing_diagnostic.severity is TokenDiagnosticSeverity.ERROR
                        and scan.material_replacement_enabled
                        else DependencyDiagnosticSeverity.WARNING
                    ),
                    message=routing_diagnostic.message,
                    consumer=scan.consumer,
                    token=routing_diagnostic.token,
                    occurrence_id=(
                        routing_diagnostic.occurrence_ids[0]
                        if routing_diagnostic.occurrence_ids
                        else ""
                    ),
                )
            )
        for routed in scan.routing.occurrences:
            resource_key, replaceable, reason = _resolve_occurrence(
                routed,
                scan=scan,
                field_values=field_values,
                field_token_bindings=frozen_bindings,
                rules_by_token=rules_by_token,
                image_roles_with_sources=image_roles_with_sources,
                attachment_by_role=attachment_by_role,
            )
            dependency = MaterialDependencyOccurrence(
                occurrence_id=routed.occurrence_id,
                router_occurrence_id=routed.router_occurrence_id,
                consumer=scan.consumer,
                token=routed.token,
                kind=routed.kind,
                resource_key=resource_key,
                surface=routed.surface,
                replaceable=replaceable,
                reason=reason,
                block_id=routed.block_id,
                ordinal=routed.ordinal,
            )
            occurrences.append(dependency)
            if reason:
                severity = (
                    DependencyDiagnosticSeverity.ERROR
                    if scan.material_replacement_enabled
                    else DependencyDiagnosticSeverity.WARNING
                )
                diagnostics.append(
                    MaterialDependencyDiagnostic(
                        code=reason,
                        severity=severity,
                        message=_reason_message(reason, dependency),
                        consumer=scan.consumer,
                        token=routed.token,
                        occurrence_id=routed.occurrence_id,
                        resource_key=resource_key,
                    )
                )
    return MaterialDependencyIndex(
        scanner_contract=MATERIAL_DEPENDENCY_SCANNER_CONTRACT,
        occurrences=tuple(occurrences),
        diagnostics=tuple(diagnostics),
        source_revisions=source_revisions or {},
        declaration_revision=declaration_revision,
    )


def _resolve_occurrence(
    routed,
    *,
    scan: MaterialConsumerScan,
    field_values: Mapping[str, object],
    field_token_bindings: Mapping[str, str],
    rules_by_token: Mapping[str, object],
    image_roles_with_sources: set[str],
    attachment_by_role: Mapping[str, object],
) -> tuple[str, bool, str]:
    if routed.kind is MaterialTokenKind.FIELD:
        canonical = field_token_bindings.get(routed.key, "")
        if not canonical:
            return routed.key, False, "unknown_field_token"
        if canonical not in field_values:
            return canonical, False, "field_value_missing"
        if routed.surface not in scan.replaceable_field_surfaces:
            return canonical, False, "field_surface_unsupported"
        if not scan.material_replacement_enabled:
            return canonical, False, "consumer_processing_disabled"
        return canonical, True, ""
    if routed.kind is MaterialTokenKind.IMAGE:
        rule = rules_by_token.get(routed.token)
        if rule is None:
            return routed.key, False, "image_rule_missing"
        role = str(getattr(rule, "source_role", "") or "")
        if role not in image_roles_with_sources:
            return role or routed.key, False, "image_source_missing"
        if routed.surface not in scan.replaceable_image_surfaces:
            return role, False, "image_surface_unsupported"
        if not scan.material_replacement_enabled:
            return role, False, "consumer_processing_disabled"
        return role, True, ""
    if routed.kind is MaterialTokenKind.CONTENT:
        content_id = routed.identifier
        if not scan.content_replacement_enabled:
            return content_id, False, "content_token_unsupported"
        if not scan.material_replacement_enabled:
            return content_id, False, "consumer_processing_disabled"
        return content_id, True, ""
    if routed.kind is MaterialTokenKind.ATTACHMENT:
        binding = attachment_by_role.get(routed.identifier)
        if binding is None:
            return routed.identifier, False, "attachment_binding_missing"
        if not tuple(getattr(binding, "items", ()) or ()):
            return routed.identifier, False, "attachment_items_missing"
        if routed.surface not in scan.replaceable_attachment_surfaces:
            return routed.identifier, False, "attachment_surface_unsupported"
        if not scan.attachment_replacement_enabled:
            return routed.identifier, False, "attachment_token_unsupported"
        if not scan.material_replacement_enabled:
            return routed.identifier, False, "consumer_processing_disabled"
        return routed.identifier, True, ""
    return routed.identifier, False, "material_token_kind_unsupported"


def _image_declaration(rule: object, index: int) -> TokenDeclaration:
    occurrence_policy = getattr(rule, "occurrence_policy", "exactly_one")
    return TokenDeclaration(
        token=_rule_token(rule, "anchor_token"),
        kind=MaterialTokenKind.IMAGE,
        declaration_id=str(getattr(rule, "rule_id", "") or f"image-{index + 1}"),
        required=bool(getattr(rule, "required", True)),
        occurrence_policy=(
            TokenOccurrencePolicy.EXACTLY_ONE
            if occurrence_policy
            in {ImageOccurrencePolicy.EXACTLY_ONE, "exactly_one"}
            else TokenOccurrencePolicy.ALL
        ),
    )


def _present_tokens(
    blocks: Sequence[TokenTextBlock | str | Sequence[str]],
) -> frozenset[str]:
    tokens: set[str] = set()
    for block in blocks:
        if isinstance(block, TokenTextBlock):
            text = block.combined_text
        elif isinstance(block, str):
            text = block
        else:
            text = "".join(str(item) for item in block)
        for match in MATERIAL_TOKEN_PATTERN.finditer(text):
            try:
                tokens.add(normalize_material_token(match.group(0)))
            except (TypeError, ValueError):
                continue
    return frozenset(tokens)


def _rule_token(rule: object, name: str) -> str:
    raw = rule.get(name, "") if isinstance(rule, Mapping) else getattr(rule, name, "")
    return normalize_material_token(str(raw or ""))


def _reason_message(
    reason: str,
    dependency: MaterialDependencyOccurrence,
) -> str:
    messages = {
        "unknown_field_token": "field token is not present in frozen token bindings",
        "field_value_missing": "field token resolves to a missing frozen value",
        "field_surface_unsupported": "field token occurs on an unsupported surface",
        "image_rule_missing": "image token has no frozen image rule",
        "image_source_missing": "image token has no frozen source item",
        "image_surface_unsupported": "image token occurs on an unsupported surface",
        "content_token_unsupported": "content tokens are unsupported for this consumer",
        "attachment_token_unsupported": (
            "nested attachment tokens are unsupported for this consumer"
        ),
        "material_token_kind_unsupported": "material token kind is unsupported",
        "consumer_processing_disabled": "consumer is configured for passthrough processing",
    }
    return f"{dependency.token}: {messages.get(reason, reason)}"


__all__ = [
    "DependencyDiagnosticSeverity",
    "MATERIAL_DEPENDENCY_SCANNER_CONTRACT",
    "MaterialConsumerKind",
    "MaterialConsumerRef",
    "MaterialConsumerScan",
    "MaterialDependencyDiagnostic",
    "MaterialDependencyIndex",
    "MaterialDependencyOccurrence",
    "build_material_dependency_index",
    "scan_material_consumer",
]
