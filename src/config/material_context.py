"""Execution-time material context for entity fields and assets."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.config.materials import (
    AssetInsertionRule,
    AssetItem,
    build_image_insertions,
    missing_required_asset_roles,
)
from src.config.resolved import ImageInsertionItem, ReplacementRule


@dataclass(slots=True)
class MaterialExecutionContext:
    """Runtime payload produced by material/quick-fill UI for one execution."""

    archive_id: str = ""
    profile_id: str = ""
    profile_name: str = ""
    entity_data: dict[str, str] = field(default_factory=dict)
    field_aliases: dict[str, str] = field(default_factory=dict)
    entity_assets_dir: str = ""
    images: list[ImageInsertionItem] = field(default_factory=list)
    replacements: list[ReplacementRule] = field(default_factory=list)
    asset_items: list[AssetItem] = field(default_factory=list)
    image_rules: list[AssetInsertionRule] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> "MaterialExecutionContext":
        if payload is None:
            return cls()

        entity_data = payload.get("entity_data", {})
        if not isinstance(entity_data, Mapping):
            entity_data = {}

        return cls(
            archive_id=str(payload.get("archive_id", "") or ""),
            profile_id=str(payload.get("profile_id", "") or ""),
            profile_name=str(payload.get("profile_name", "") or ""),
            entity_data={
                str(key): str(value)
                for key, value in entity_data.items()
                if str(key or "").strip()
            },
            field_aliases=_normalize_text_mapping(payload.get("field_aliases", {})),
            entity_assets_dir=str(payload.get("entity_assets_dir", "") or ""),
            images=_normalize_image_items(payload.get("images", [])),
            replacements=_normalize_replacement_rules(payload.get("replacements", [])),
            asset_items=_normalize_asset_items(payload.get("asset_items", [])),
            image_rules=_normalize_asset_insertion_rules(payload.get("image_rules", [])),
        )

    def clone(self) -> "MaterialExecutionContext":
        return MaterialExecutionContext(
            archive_id=self.archive_id,
            profile_id=self.profile_id,
            profile_name=self.profile_name,
            entity_data=dict(self.entity_data),
            field_aliases=dict(self.field_aliases),
            entity_assets_dir=self.entity_assets_dir,
            images=copy.deepcopy(self.images),
            replacements=copy.deepcopy(self.replacements),
            asset_items=copy.deepcopy(self.asset_items),
            image_rules=copy.deepcopy(self.image_rules),
        )

    def is_empty(self) -> bool:
        return not (
            self.archive_id
            or self.profile_id
            or self.profile_name
            or self.entity_data
            or self.field_aliases
            or self.entity_assets_dir
            or self.images
            or self.replacements
            or self.asset_items
            or self.image_rules
        )

    def to_resolve_kwargs(self) -> dict[str, object]:
        images = [
            *copy.deepcopy(self.images),
            *build_image_insertions(self.asset_items, self.image_rules),
        ]
        return {
            "entity_data": dict(self.entity_data),
            "field_aliases": dict(self.field_aliases),
            "entity_assets_dir": self.entity_assets_dir,
            "images": images,
            "replacements": copy.deepcopy(self.replacements),
        }

    def missing_required_asset_roles(self) -> list[str]:
        return missing_required_asset_roles(self.asset_items, self.image_rules)


def _normalize_image_items(items: object) -> list[ImageInsertionItem]:
    normalized: list[ImageInsertionItem] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, ImageInsertionItem):
            normalized.append(copy.deepcopy(item))
            continue
        if not isinstance(item, Mapping):
            continue

        try:
            width_cm = float(item.get("width_cm", 14.0))
        except (TypeError, ValueError):
            width_cm = 14.0

        normalized.append(
            ImageInsertionItem(
                path=str(item.get("path", "") or ""),
                position=item.get("position", "end"),
                width_cm=width_cm,
            )
        )
    return normalized


def _normalize_text_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key or "").strip() and str(item or "").strip()
    }


def _normalize_replacement_rules(items: object) -> list[ReplacementRule]:
    normalized: list[ReplacementRule] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, ReplacementRule):
            normalized.append(copy.deepcopy(item))
            continue
        if not isinstance(item, Mapping):
            continue
        normalized.append(
            ReplacementRule(
                old=str(item.get("old", "") or ""),
                new=str(item.get("new", "") or ""),
            )
        )
    return normalized


def _normalize_asset_items(items: object) -> list[AssetItem]:
    normalized: list[AssetItem] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, AssetItem):
            normalized.append(copy.deepcopy(item))
            continue
        if not isinstance(item, Mapping):
            continue
        width = item.get("width_cm")
        try:
            width_cm = float(width) if width is not None else None
        except (TypeError, ValueError):
            width_cm = None
        raw_tags = item.get("tags", [])
        tags = (
            [str(tag) for tag in raw_tags]
            if isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes))
            else []
        )
        role = str(item.get("role", "") or "").strip().lower().replace(" ", "_")
        metadata = item.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        normalized.append(
            AssetItem(
                item_id=str(item.get("item_id", "") or ""),
                label=str(item.get("label", "") or ""),
                role=role,
                path=str(item.get("path", "") or ""),
                mime_type=str(item.get("mime_type", "") or ""),
                tags=tags,
                width_cm=width_cm,
                metadata={
                    str(key): str(value)
                    for key, value in metadata.items()
                    if str(key or "").strip() and str(value or "").strip()
                },
            )
        )
    return normalized


def _normalize_asset_insertion_rules(items: object) -> list[AssetInsertionRule]:
    normalized: list[AssetInsertionRule] = []
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return normalized

    for item in items:
        if isinstance(item, AssetInsertionRule):
            normalized.append(copy.deepcopy(item))
            continue
        if not isinstance(item, Mapping):
            continue
        try:
            width_cm = float(item.get("width_cm", 6.0))
        except (TypeError, ValueError):
            width_cm = 6.0
        normalized.append(
            AssetInsertionRule(
                rule_id=str(item.get("rule_id", "") or ""),
                asset_role=str(item.get("asset_role", "") or ""),
                target=str(item.get("target", "end") or "end"),
                width_cm=width_cm,
                required=bool(item.get("required", True)),
            )
        )
    return normalized


__all__ = ["MaterialExecutionContext"]
