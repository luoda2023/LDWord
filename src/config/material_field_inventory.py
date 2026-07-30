"""Package-owned material field inventory projection.

Field rows are declared by the selected material package. Plans, masters,
and scanned documents may validate that inventory, but must never populate it.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.entity import EntityProfile


MATERIAL_FIELD_SCOPE_FIXED = "fixed"
MATERIAL_FIELD_SCOPE_FLOATING = "floating"
MATERIAL_FIELD_SCOPE_REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class MaterialFieldInventory:
    fixed_keys: tuple[str, ...] = ()
    floating_keys: tuple[str, ...] = ()
    removed_keys: tuple[str, ...] = ()

    @property
    def active_keys(self) -> tuple[str, ...]:
        return (*self.fixed_keys, *self.floating_keys)


def project_material_field_inventory(profile: EntityProfile) -> MaterialFieldInventory:
    """Project ordered field rows from one package profile without mutation."""

    scopes = {
        str(key or "").strip(): str(scope or "").strip()
        for key, scope in dict(profile.field_scopes or {}).items()
        if str(key or "").strip()
        and str(scope or "").strip()
        in {
            MATERIAL_FIELD_SCOPE_FIXED,
            MATERIAL_FIELD_SCOPE_FLOATING,
            MATERIAL_FIELD_SCOPE_REMOVED,
        }
    }
    removed = tuple(
        key
        for key, scope in scopes.items()
        if scope == MATERIAL_FIELD_SCOPE_REMOVED
    )
    removed_set = set(removed)
    fixed = [
        key
        for key, scope in scopes.items()
        if scope == MATERIAL_FIELD_SCOPE_FIXED and key not in removed_set
    ]
    floating = [
        key
        for key, scope in scopes.items()
        if scope == MATERIAL_FIELD_SCOPE_FLOATING and key not in removed_set
    ]
    assigned = set(fixed) | set(floating) | removed_set

    # Legacy packages used values/declarations as an implicit registry. Keep
    # those rows as fixed fields; a genuinely blank package remains blank.
    legacy_keys = (
        *tuple(profile.declared_field_keys or ()),
        *tuple(dict(profile.fields or {})),
    )
    for raw_key in legacy_keys:
        key = str(raw_key or "").strip()
        if not key or key == "document_type" or key in assigned:
            continue
        fixed.append(key)
        assigned.add(key)

    return MaterialFieldInventory(
        fixed_keys=tuple(fixed),
        floating_keys=tuple(floating),
        removed_keys=removed,
    )


def discard_material_field(profile: EntityProfile, field_key: object) -> bool:
    """Remove one package-owned field and every package-level reference to it.

    Field deletion used to be implemented independently by each presenter.
    Leaving ``declared_field_keys`` or an alias behind makes the legacy
    inventory projection recreate the deleted row on its next refresh.  Keep
    the domain cleanup in the inventory owner so every caller gets the same
    non-resurrecting semantics.
    """

    key = str(field_key or "").strip()
    if not key:
        return False
    existed = bool(
        key in profile.field_scopes
        or key in profile.fields
        or key in profile.declared_field_keys
        or key in profile.field_sources
        or key in profile.field_functions
        or any(
            str(target or "").strip() == key
            for target in dict(profile.field_aliases or {}).values()
        )
    )
    profile.field_scopes.pop(key, None)
    profile.fields.pop(key, None)
    profile.declared_field_keys = [
        item
        for item in profile.declared_field_keys
        if str(item or "").strip() != key
    ]
    profile.field_sources.pop(key, None)
    profile.field_functions.pop(key, None)
    profile.field_aliases = {
        alias: target
        for alias, target in dict(profile.field_aliases or {}).items()
        if str(target or "").strip() != key
    }
    return existed


def rename_material_field(
    profile: EntityProfile,
    old_field_key: object,
    new_field_key: object,
) -> bool:
    """Rename one package-owned field without changing registry order.

    The package inventory is spread across a small set of keyed projections.
    Updating only the editor row leaves the old declaration behind, so the
    next normalization recreates it.  Perform the rename atomically across
    every package-level projection and retarget aliases to the new key.
    """

    old_key = str(old_field_key or "").strip()
    new_key = str(new_field_key or "").strip()
    if not old_key or not new_key or old_key == new_key:
        return False

    old_exists = bool(
        old_key in profile.field_scopes
        or old_key in profile.fields
        or old_key in profile.declared_field_keys
        or old_key in profile.field_sources
        or old_key in profile.field_functions
        or any(
            str(target or "").strip() == old_key
            for target in dict(profile.field_aliases or {}).values()
        )
    )
    if not old_exists:
        return False

    new_exists = bool(
        new_key in profile.field_scopes
        or new_key in profile.fields
        or new_key in profile.declared_field_keys
        or new_key in profile.field_sources
        or new_key in profile.field_functions
        or new_key in profile.field_aliases
    )
    if new_exists:
        return False

    def _renamed_mapping(mapping: dict) -> dict:
        return {
            new_key if str(key or "").strip() == old_key else key: value
            for key, value in mapping.items()
        }

    profile.field_scopes = _renamed_mapping(dict(profile.field_scopes or {}))
    profile.fields = _renamed_mapping(dict(profile.fields or {}))
    profile.field_sources = _renamed_mapping(dict(profile.field_sources or {}))
    profile.field_functions = _renamed_mapping(
        dict(profile.field_functions or {})
    )
    profile.declared_field_keys = list(
        dict.fromkeys(
            new_key if str(key or "").strip() == old_key else key
            for key in profile.declared_field_keys
        )
    )
    profile.field_aliases = {
        alias: (
            new_key if str(target or "").strip() == old_key else target
        )
        for alias, target in dict(profile.field_aliases or {}).items()
    }
    return True


def normalize_material_field_inventory(profile: EntityProfile) -> MaterialFieldInventory:
    """Normalize legacy/tombstone state and persist the package registry."""

    inventory = project_material_field_inventory(profile)
    for removed_key in inventory.removed_keys:
        discard_material_field(profile, removed_key)

    # ``removed`` only prevented the former starter inventory from returning.
    # Absence is now the canonical persisted representation of deletion.
    profile.field_scopes = {
        **{key: MATERIAL_FIELD_SCOPE_FIXED for key in inventory.fixed_keys},
        **{key: MATERIAL_FIELD_SCOPE_FLOATING for key in inventory.floating_keys},
    }
    return MaterialFieldInventory(
        fixed_keys=inventory.fixed_keys,
        floating_keys=inventory.floating_keys,
    )


__all__ = [
    "MATERIAL_FIELD_SCOPE_FIXED",
    "MATERIAL_FIELD_SCOPE_FLOATING",
    "MaterialFieldInventory",
    "discard_material_field",
    "normalize_material_field_inventory",
    "project_material_field_inventory",
    "rename_material_field",
]
