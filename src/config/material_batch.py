"""Build per-profile material contexts for batch execution."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from src.config.entity import EntityArchive, EntityProfile
from src.config.material_context import MaterialExecutionContext
from src.config.materials import asset_items_from_role_paths, scan_asset_collection


@dataclass(slots=True)
class MaterialBatchItem:
    profile_id: str
    profile_name: str
    output_dir: str
    context: MaterialExecutionContext


@dataclass(slots=True)
class MaterialBatchSelection:
    archive: EntityArchive = field(default_factory=EntityArchive)
    profile_ids: list[str] = field(default_factory=list)
    output_dir_template: str = "{entity_name}"
    base_context: MaterialExecutionContext = field(default_factory=MaterialExecutionContext)

    def clone(self) -> "MaterialBatchSelection":
        return MaterialBatchSelection(
            archive=copy.deepcopy(self.archive),
            profile_ids=list(self.profile_ids),
            output_dir_template=str(self.output_dir_template or "{entity_name}"),
            base_context=self.base_context.clone(),
        )


def build_material_batch_items(
    archive: EntityArchive,
    *,
    profile_ids: Sequence[str] | None = None,
    base_output_dir: str | Path = "",
    output_dir_template: str = "{entity_name}",
    base_context: MaterialExecutionContext | None = None,
) -> list[MaterialBatchItem]:
    selected_profiles = _select_profiles(archive, profile_ids)
    base = Path(base_output_dir) if str(base_output_dir or "").strip() else Path()
    shared_context = (
        base_context.clone()
        if isinstance(base_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    items: list[MaterialBatchItem] = []

    for profile in selected_profiles:
        entity_name = (
            profile.fields.get("entity_name")
            or profile.fields.get("company_name")
            or profile.profile_name
            or profile.profile_id
            or "entity"
        )
        output_dir = output_dir_template.format(
            archive_id=archive.archive_id,
            archive_name=archive.archive_name,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            entity_name=_safe_path_segment(entity_name),
        )
        output_path = base / output_dir if output_dir else base
        assets_dir = profile.assets_dir or shared_context.entity_assets_dir
        scanned_asset_items = (
            scan_asset_collection(assets_dir).items
            if str(assets_dir or "").strip()
            else copy.deepcopy(shared_context.asset_items)
        )
        asset_items = [
            *scanned_asset_items,
            *MaterialExecutionContext.from_payload(
                {"asset_items": profile.asset_items}
            ).asset_items,
            *asset_items_from_role_paths(profile.asset_paths),
        ]
        context = MaterialExecutionContext(
            archive_id=archive.archive_id,
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            entity_data={**shared_context.entity_data, **dict(profile.fields)},
            field_aliases={
                **shared_context.field_aliases,
                **dict(profile.field_aliases),
            },
            entity_assets_dir=assets_dir,
            images=copy.deepcopy(shared_context.images),
            replacements=copy.deepcopy(shared_context.replacements),
            asset_items=asset_items,
            image_rules=copy.deepcopy(shared_context.image_rules),
        )
        items.append(
            MaterialBatchItem(
                profile_id=profile.profile_id,
                profile_name=profile.profile_name,
                output_dir=str(output_path),
                context=context,
            )
        )
    return items


def _select_profiles(archive: EntityArchive, profile_ids: Sequence[str] | None) -> list[EntityProfile]:
    if profile_ids is None:
        return list(archive.profiles)
    if not profile_ids:
        return []
    requested = {str(profile_id) for profile_id in profile_ids}
    return [profile for profile in archive.profiles if profile.profile_id in requested]


def _safe_path_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "entity"


__all__ = ["MaterialBatchItem", "MaterialBatchSelection", "build_material_batch_items"]
