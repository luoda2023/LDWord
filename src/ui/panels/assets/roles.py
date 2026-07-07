"""Asset role and placeholder helpers for the assets panel."""

from __future__ import annotations

from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids
from src.ui.panels.assets.fields import (
    _asset_role_label,
    _field_alias_for_token,
    _field_label,
    _placeholder_key,
)
from src.ui.panels.assets.specs import (
    COMMON_ASSET_SLOTS,
    AssetSlotSpec,
    AttachmentRoleSpec,
)

def _asset_slot_role_for_token(token: str, slot_specs: tuple[AssetSlotSpec, ...] | None = None) -> str:
    normalized = _placeholder_key(token)
    for spec in slot_specs or ():
        if normalized == spec.role or normalized == _placeholder_key(spec.target):
            return spec.role
    for role, _label, target in COMMON_ASSET_SLOTS:
        if normalized == role or normalized == _placeholder_key(target):
            return role
    return ""


def _asset_slot_target_for_role(role: str) -> str:
    return "{{" + str(role or "").strip() + "}}"


def _accepted_types_include_attachment(accepted_types: tuple[str, ...] | list[str]) -> bool:
    normalized = {str(item or "").strip().lower() for item in accepted_types or ()}
    return bool(normalized - {"image"})


def _material_schema_ids_from_profile(profile) -> tuple[str, ...]:
    return resolve_material_schema_ids(
        getattr(profile, "material_schema_id", ""),
        getattr(profile, "material_schema_ids", ()),
    )


def _material_schemas_from_ids(schema_ids: tuple[str, ...] | list[str]) -> tuple:
    schemas: list = []
    for schema_id in schema_ids:
        try:
            schemas.append(get_material_schema(schema_id))
        except KeyError:
            continue
    return tuple(schemas)


def _schemas_role_accept_attachment(schemas: tuple, role: str) -> bool:
    return any(_schema_role_accepts_attachment(schema, role) for schema in schemas)


def _schema_role_accepts_attachment(schema, role: str) -> bool:
    normalized_role = str(role or "").strip().lower().replace(" ", "_")
    for role_spec in getattr(schema, "asset_roles", ()):
        current_role = str(getattr(role_spec, "role", "") or "").strip().lower().replace(" ", "_")
        if current_role == normalized_role:
            return _accepted_types_include_attachment(getattr(role_spec, "accepted_types", ("image",)))
    return False


def _attachment_file_filter(accepted_types: tuple[str, ...] | list[str]) -> str:
    normalized = {str(item or "").strip().lower() for item in accepted_types or ()}
    filters: list[str] = []
    if "image" in normalized:
        filters.append("Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)")
    if "pdf" in normalized:
        filters.append("PDF Files (*.pdf)")
    filters.append("All Files (*)")
    return ";;".join(filters)


def _asset_slot_supports_alt_text(role: str) -> bool:
    return str(role or "").strip().lower().replace(" ", "_") in {"question_figure"}


def _missing_placeholder_label(
    token: str,
    slot_specs: tuple[AssetSlotSpec, ...] | None = None,
    attachment_specs: tuple[AttachmentRoleSpec, ...] | None = None,
) -> str:
    role = _asset_slot_role_for_token(token, slot_specs)
    if role:
        return _asset_role_label(role, slot_specs)
    normalized = _placeholder_key(token)
    for spec in attachment_specs or ():
        if normalized == spec.role:
            return spec.label
    alias_key = _field_alias_for_token(token)
    if alias_key:
        return _field_label(alias_key)
    return _field_label(token)


__all__ = [
    '_asset_slot_role_for_token',
    '_asset_slot_target_for_role',
    '_accepted_types_include_attachment',
    '_material_schema_ids_from_profile',
    '_material_schemas_from_ids',
    '_schemas_role_accept_attachment',
    '_schema_role_accepts_attachment',
    '_attachment_file_filter',
    '_asset_slot_supports_alt_text',
    '_missing_placeholder_label',
]
