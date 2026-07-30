"""Immutable, content-addressed intake material Freeze.

The snapshot contains source and policy facts only.  It deliberately excludes
delivery variants, target-DOCX identity, anchors, and resolved insertion jobs;
those facts are produced later as a one-way :class:`DeliveryVariantPlan`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from types import MappingProxyType
from typing import Any

from src.config.attachment_materials import AttachmentBinding
from src.config.content_artifacts import ContentMaterialBinding
from src.config.content_materials import ContentInsertionRule
from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImageSourceBinding,
)
from src.shared.engine.material_token_contract import (
    FrozenMaterialTokenEvidence,
    MATERIAL_TOKEN_CONTRACT_VERSION,
    MaterialTokenKind,
    parse_material_token,
)


MATERIAL_SNAPSHOT_CONTRACT_VERSION = "material-snapshot-v5"


@dataclass(frozen=True, slots=True)
class MaterialSnapshot:
    """One deterministic intake Freeze shared by all delivery variants."""

    snapshot_id: str = ""
    contract_version: str = MATERIAL_SNAPSHOT_CONTRACT_VERSION
    field_values: Mapping[str, object] = field(default_factory=dict)
    field_token_bindings: Mapping[str, str] = field(default_factory=dict)
    content_bindings: tuple[ContentMaterialBinding, ...] = ()
    content_rules: tuple[ContentInsertionRule, ...] = ()
    frozen_image_rules: tuple[FrozenImageMaterialRule, ...] = ()
    image_source_bindings: tuple[ImageSourceBinding, ...] = ()
    attachment_bindings: tuple[AttachmentBinding, ...] = ()
    token_evidence: tuple[FrozenMaterialTokenEvidence, ...] = ()
    material_schema_id: str = ""
    material_schema_version: str = ""
    rule_versions: Mapping[str, str] = field(default_factory=dict)
    source_revisions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.contract_version != MATERIAL_SNAPSHOT_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported material snapshot contract: {self.contract_version!r}"
            )
        _require_text(self.material_schema_id, "material_schema_id")
        _require_text(self.material_schema_version, "material_schema_version")
        object.__setattr__(
            self,
            "field_values",
            _freeze_mapping(self.field_values, path="field_values"),
        )
        object.__setattr__(
            self,
            "field_token_bindings",
            _freeze_text_mapping(
                self.field_token_bindings,
                "field_token_bindings",
            ),
        )
        object.__setattr__(
            self,
            "rule_versions",
            _freeze_text_mapping(self.rule_versions, "rule_versions"),
        )
        object.__setattr__(
            self,
            "source_revisions",
            _freeze_text_mapping(self.source_revisions, "source_revisions"),
        )

        content_bindings = _typed_tuple(
            self.content_bindings,
            ContentMaterialBinding,
            "content_bindings",
        )
        _require_unique(
            (item.content_id for item in content_bindings),
            "content binding content_id",
        )
        content_bindings = tuple(
            sorted(content_bindings, key=lambda item: item.content_id.casefold())
        )
        object.__setattr__(self, "content_bindings", content_bindings)

        content_rules = _typed_tuple(
            self.content_rules,
            ContentInsertionRule,
            "content_rules",
        )
        _require_unique(
            (item.rule_id for item in content_rules),
            "content rule rule_id",
        )
        binding_ids = {item.content_id for item in content_bindings}
        orphan_ids = sorted(
            {item.content_id for item in content_rules if item.content_id not in binding_ids}
        )
        if orphan_ids:
            raise ValueError(
                "content rules reference missing bindings: " + ", ".join(orphan_ids)
            )
        rule_counts = {content_id: 0 for content_id in binding_ids}
        for rule in content_rules:
            rule_counts[rule.content_id] += 1
        invalid_cardinality = tuple(
            (content_id, count)
            for content_id, count in sorted(rule_counts.items())
            if count != 1
        )
        if invalid_cardinality:
            details = ", ".join(
                f"{content_id}={count}"
                for content_id, count in invalid_cardinality
            )
            raise ValueError(
                "binding_rule_cardinality_invalid: " + details
            )
        # Rule tuple order is an explicit content-composition fact.
        object.__setattr__(self, "content_rules", content_rules)

        image_rules = _typed_tuple(
            self.frozen_image_rules,
            FrozenImageMaterialRule,
            "frozen_image_rules",
        )
        for attribute, label in (
            ("rule_id", "frozen image rule rule_id"),
            ("source_role", "frozen image rule source_role"),
            ("anchor_token", "frozen image rule anchor_token"),
        ):
            _require_unique(
                (getattr(item, attribute) for item in image_rules),
                label,
            )
        image_rules = tuple(
            sorted(image_rules, key=lambda item: item.rule_id.casefold())
        )
        object.__setattr__(self, "frozen_image_rules", image_rules)

        image_sources = _typed_tuple(
            self.image_source_bindings,
            ImageSourceBinding,
            "image_source_bindings",
        )
        _require_unique(
            (item.item_id for item in image_sources),
            "image source item_id",
        )
        _require_unique(
            ((item.role, item.sequence) for item in image_sources),
            "image source role/sequence",
        )
        known_roles = {item.source_role for item in image_rules}
        unknown_roles = sorted({item.role for item in image_sources} - known_roles)
        if unknown_roles:
            raise ValueError(
                "image sources reference missing frozen rules: "
                + ", ".join(unknown_roles)
            )
        image_sources = tuple(
            sorted(
                image_sources,
                key=lambda item: (
                    item.role.casefold(),
                    item.sequence,
                    item.item_id.casefold(),
                ),
            )
        )
        object.__setattr__(self, "image_source_bindings", image_sources)

        attachment_bindings = _typed_tuple(
            self.attachment_bindings,
            AttachmentBinding,
            "attachment_bindings",
        )
        _require_unique(
            (item.role for item in attachment_bindings),
            "attachment binding role",
        )
        _require_unique(
            (
                item.item_id
                for binding in attachment_bindings
                for item in binding.items
            ),
            "attachment item_id",
        )
        _require_unique(
            (item.binding_revision for item in attachment_bindings),
            "attachment binding revision",
        )
        attachment_bindings = tuple(
            sorted(attachment_bindings, key=lambda item: item.role.casefold())
        )
        object.__setattr__(self, "attachment_bindings", attachment_bindings)

        expected_resources = _expected_token_resources(
            self.field_token_bindings,
            content_rules,
            image_rules,
            attachment_bindings,
        )
        evidence = _typed_tuple(
            self.token_evidence,
            FrozenMaterialTokenEvidence,
            "token_evidence",
        )
        if evidence:
            _require_unique((item.token for item in evidence), "token evidence token")
            evidence_resources = {
                item.token: (item.kind, item.resource_id) for item in evidence
            }
            if evidence_resources != expected_resources:
                raise ValueError(
                    "token evidence does not match frozen material domain bindings"
                )
        else:
            evidence = tuple(
                FrozenMaterialTokenEvidence(
                    token=token,
                    kind=kind,
                    producer=parse_material_token(token).default_producer,
                    resource_id=resource_id,
                )
                for token, (kind, resource_id) in expected_resources.items()
            )
        evidence = tuple(sorted(evidence, key=lambda item: item.token.casefold()))
        object.__setattr__(self, "token_evidence", evidence)

        supplied_id = str(self.snapshot_id or "").strip()
        computed_id = sha256(self.canonical_json().encode("utf-8")).hexdigest()
        if supplied_id and supplied_id != computed_id:
            raise ValueError(
                f"snapshot_id does not match canonical payload: {supplied_id!r}"
            )
        object.__setattr__(self, "snapshot_id", computed_id)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "token_contract_version": MATERIAL_TOKEN_CONTRACT_VERSION,
            "field_values": _plain_value(self.field_values),
            "field_token_bindings": _plain_value(self.field_token_bindings),
            "content_bindings": [item.to_dict() for item in self.content_bindings],
            "content_rules": [item.to_dict() for item in self.content_rules],
            "frozen_image_rules": [
                item.to_dict() for item in self.frozen_image_rules
            ],
            "image_source_bindings": [
                item.to_dict() for item in self.image_source_bindings
            ],
            "attachment_bindings": [
                item.to_dict() for item in self.attachment_bindings
            ],
            "token_evidence": [item.to_dict() for item in self.token_evidence],
            "material_schema_id": self.material_schema_id,
            "material_schema_version": self.material_schema_version,
            "rule_versions": _plain_value(self.rule_versions),
            "source_revisions": _plain_value(self.source_revisions),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def to_dict(self) -> dict[str, object]:
        return {"snapshot_id": self.snapshot_id, **self.canonical_payload()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MaterialSnapshot":
        if not isinstance(payload, Mapping):
            raise TypeError("material snapshot payload must be a mapping")
        raw_contract_version = str(payload.get("contract_version", "") or "")
        if raw_contract_version != MATERIAL_SNAPSHOT_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported material snapshot contract: {raw_contract_version!r}"
            )
        if str(payload.get("token_contract_version", "") or "") != MATERIAL_TOKEN_CONTRACT_VERSION:
            raise ValueError("unsupported material token contract")
        raw_bindings = _require_sequence(
            payload.get("content_bindings", ()),
            "content_bindings",
        )
        raw_content_rules = _require_sequence(
            payload.get("content_rules", ()),
            "content_rules",
        )
        raw_image_rules = _require_sequence(
            payload.get("frozen_image_rules", ()),
            "frozen_image_rules",
        )
        raw_image_sources = _require_sequence(
            payload.get("image_source_bindings", ()),
            "image_source_bindings",
        )
        raw_attachment_bindings = _require_sequence(
            payload.get("attachment_bindings", ()),
            "attachment_bindings",
        )
        raw_token_evidence = _require_sequence(
            payload.get("token_evidence", ()),
            "token_evidence",
        )
        return cls(
            snapshot_id=str(payload.get("snapshot_id", "") or ""),
            contract_version=MATERIAL_SNAPSHOT_CONTRACT_VERSION,
            field_values=_require_mapping(
                payload.get("field_values", {}),
                "field_values",
            ),
            field_token_bindings=_require_mapping(
                payload.get("field_token_bindings", {}),
                "field_token_bindings",
            ),
            content_bindings=tuple(
                ContentMaterialBinding.from_dict(
                    _require_mapping(item, "content binding")
                )
                for item in raw_bindings
            ),
            content_rules=tuple(
                ContentInsertionRule.from_dict(
                    _require_mapping(item, "content rule")
                )
                for item in raw_content_rules
            ),
            frozen_image_rules=tuple(
                FrozenImageMaterialRule.from_dict(
                    _require_mapping(item, "frozen image rule")
                )
                for item in raw_image_rules
            ),
            image_source_bindings=tuple(
                ImageSourceBinding.from_dict(
                    _require_mapping(item, "image source binding")
                )
                for item in raw_image_sources
            ),
            attachment_bindings=tuple(
                AttachmentBinding.from_dict(
                    _require_mapping(item, "attachment binding")
                )
                for item in raw_attachment_bindings
            ),
            token_evidence=tuple(
                FrozenMaterialTokenEvidence.from_dict(
                    _require_mapping(item, "token evidence")
                )
                for item in raw_token_evidence
            ),
            material_schema_id=str(payload.get("material_schema_id", "") or ""),
            material_schema_version=str(
                payload.get("material_schema_version", "") or ""
            ),
            rule_versions=_require_mapping(
                payload.get("rule_versions", {}),
                "rule_versions",
            ),
            source_revisions=_require_mapping(
                payload.get("source_revisions", {}),
                "source_revisions",
            ),
        )


def _expected_token_resources(
    field_token_bindings: Mapping[str, str],
    content_rules: Sequence[ContentInsertionRule],
    image_rules: Sequence[FrozenImageMaterialRule],
    attachment_bindings: Sequence[AttachmentBinding],
) -> dict[str, tuple[MaterialTokenKind, str]]:
    resources: dict[str, tuple[MaterialTokenKind, str]] = {}

    def add(token_or_key: str, expected_kind: MaterialTokenKind, resource_id: str) -> None:
        ref = parse_material_token(token_or_key)
        ref.validate_kind(expected_kind)
        fact = (expected_kind, str(resource_id or "").strip())
        if not fact[1]:
            raise ValueError("token evidence resource id must not be empty")
        previous = resources.get(ref.token)
        if previous is not None and previous != fact:
            raise ValueError(f"material token has conflicting resources: {ref.token}")
        resources[ref.token] = fact

    for token_key, field_id in field_token_bindings.items():
        add(token_key, MaterialTokenKind.FIELD, field_id)
    for rule in content_rules:
        add(rule.anchor_token, MaterialTokenKind.CONTENT, rule.content_id)
    for rule in image_rules:
        add(rule.anchor_token, MaterialTokenKind.IMAGE, rule.source_role)
    for binding in attachment_bindings:
        add(binding.anchor_token, MaterialTokenKind.ATTACHMENT, binding.role)
    return dict(sorted(resources.items(), key=lambda item: item[0].casefold()))


def _freeze_mapping(value: object, *, path: str) -> Mapping[str, object]:
    mapping = _require_mapping(value, path)
    frozen: dict[str, object] = {}
    for key in sorted(mapping):
        if not isinstance(key, str):
            raise TypeError(f"{path} keys must be strings")
        frozen[key] = _freeze_value(mapping[key], path=f"{path}.{key}")
    return MappingProxyType(frozen)


def _freeze_value(value: object, *, path: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain NaN or infinity")
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value, path=path)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(
            _freeze_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise TypeError(f"{path} contains unsupported value type {type(value).__name__}")


def _plain_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    return value


def _freeze_text_mapping(value: object, field_name: str) -> Mapping[str, str]:
    mapping = _require_mapping(value, field_name)
    frozen: dict[str, str] = {}
    for key in sorted(mapping):
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
        item = mapping[key]
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}.{key} must be a non-empty string")
        frozen[key] = item
    return MappingProxyType(frozen)


def _typed_tuple(values, expected_type, field_name):
    normalized = _require_sequence(values or (), field_name)
    items = tuple(normalized)
    if any(not isinstance(item, expected_type) for item in items):
        raise TypeError(
            f"{field_name} must contain {expected_type.__name__} values"
        )
    return items


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return value


def _require_sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a sequence")
    return value


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_unique(values, label: str) -> None:
    items = tuple(values)
    if len(items) != len(set(items)):
        raise ValueError(f"{label} values must be unique")


__all__ = [
    "MATERIAL_SNAPSHOT_CONTRACT_VERSION",
    "MaterialSnapshot",
]
