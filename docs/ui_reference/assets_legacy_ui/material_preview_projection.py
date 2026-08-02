"""Pure projection from an Assets editor draft to a workbench preview."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from src.config.material_preview_snapshot import (
    MaterialPreviewSnapshot,
    build_material_preview_snapshot,
)


@dataclass(frozen=True, slots=True)
class MaterialPreviewDraft:
    """Typed boundary between the Assets editor and cross-panel preview state."""

    mode_id: str = ""
    archive_id: str = ""
    archive_name: str = ""
    entry_package_id: str = ""
    entry_source_type: str = ""
    profile_id: str = ""
    profile_name: str = ""
    field_values: Mapping[object, object] = field(default_factory=dict)
    profile_field_scopes: Mapping[object, object] = field(default_factory=dict)
    official_fixed_keys: Sequence[object] = ()
    official_floating_keys: Sequence[object] = ()
    asset_items: Sequence[object] = ()
    image_count: int = 0
    content_count: int = 0
    attachment_bindings: Mapping[object, object] = field(default_factory=dict)
    conflicts: Sequence[object] = ()


def build_assets_material_preview_snapshot(
    draft: MaterialPreviewDraft,
) -> MaterialPreviewSnapshot:
    """Normalize one editor draft without reading widgets or mutating a bridge."""

    archive_id = _text(draft.archive_id)
    entry_package_id = _text(draft.entry_package_id)
    package_id = archive_id or entry_package_id
    source_type = (
        _text(draft.entry_source_type)
        if not archive_id
        or not entry_package_id
        or entry_package_id == archive_id
        else ""
    )
    if not source_type and package_id:
        source_type = "user"

    scopes = {
        key: value
        for key, value in (
            (_text(raw_key), _text(raw_value))
            for raw_key, raw_value in dict(draft.profile_field_scopes).items()
        )
        if key and value
    }
    scopes.update(
        {
            key: "fixed"
            for key in (_text(raw_key) for raw_key in draft.official_fixed_keys)
            if key
        }
    )
    scopes.update(
        {
            key: "floating"
            for key in (_text(raw_key) for raw_key in draft.official_floating_keys)
            if key
        }
    )

    return build_material_preview_snapshot(
        mode_id=draft.mode_id,
        package_id=package_id,
        archive_id=archive_id,
        archive_name=draft.archive_name,
        package_source_type=source_type,
        profile_id=draft.profile_id,
        profile_name=draft.profile_name,
        field_values=draft.field_values,
        field_scopes=scopes,
        asset_roles=_bound_asset_roles(draft.asset_items),
        image_count=draft.image_count,
        content_count=draft.content_count,
        attachment_count=_attachment_count(draft.attachment_bindings),
        valid=not tuple(draft.conflicts),
        issues=draft.conflicts,
    )


def _bound_asset_roles(items: Sequence[object]) -> tuple[str, ...]:
    roles: list[str] = []
    for item in items:
        if isinstance(item, Mapping):
            role = _text(item.get("role", ""))
            path = _text(item.get("path", "") or item.get("source_path", ""))
        else:
            role = _text(getattr(item, "role", ""))
            path = _text(
                getattr(item, "path", "") or getattr(item, "source_path", "")
            )
        if role and path:
            roles.append(role)
    return tuple(dict.fromkeys(roles))


def _attachment_count(bindings: Mapping[object, object]) -> int:
    count = 0
    for binding in dict(bindings).values():
        if isinstance(binding, Mapping):
            items = tuple(binding.get("items", ()) or ())
            source_path = _text(binding.get("source_path", ""))
        else:
            items = tuple(getattr(binding, "items", ()) or ())
            source_path = _text(getattr(binding, "source_path", ""))
        count += len(items) if items else int(bool(source_path))
    return count


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


__all__ = [
    "MaterialPreviewDraft",
    "build_assets_material_preview_snapshot",
]
