"""Strict wire-shape validation for generic v5 material packages."""

from __future__ import annotations

from src.config.entity_archive_wire_contracts import (
    ASSET_ITEM_FIELD_TYPES,
    ASSET_ITEM_REQUIRED_FIELDS,
    HISTORY_ALLOWED_FIELDS,
    AssetBindingWire,
    AssetTokenSpecWire,
    AttachmentBindingWire,
    AttachmentRoleSpecWire,
    ContentInsertionRuleWire,
    ContentMaterialBindingWire,
    EntityArchiveWirePayload,
    ImageMaterialRuleWire,
)
from src.config.entity_timeline_wire_validation import validate_timeline_plans
from src.config.entity_wire_validation import (
    first_payload_difference,
    validate_exact_type,
    validate_json_value,
    validate_typed_items,
    validate_typed_mapping,
)
from src.config.strict_payload_validation import (
    StrictPayloadValidationError,
    validate_complete_dataclass_payload,
)


def validate_entity_archive_wire_payload(payload: object) -> None:
    """Reject every current-version structural omission or implicit repair."""

    try:
        validate_complete_dataclass_payload(
            EntityArchiveWirePayload,
            payload,
            root_label="material package v5",
        )
    except StrictPayloadValidationError as exc:
        raise ValueError(f"material_package_v5_structure_invalid:{exc}") from exc

    if not isinstance(payload, dict):
        raise AssertionError("strict validator accepted a non-object archive")
    validate_json_value(payload, path="<archive>")
    for profile_index, profile in enumerate(payload["profiles"]):
        if not isinstance(profile, dict):
            raise AssertionError("strict validator accepted a non-object profile")
        root = f"profile_{profile_index}"
        validate_timeline_plans(
            profile["timeline_plans"],
            path=f"{root}.timeline_plans",
        )
        validate_typed_mapping(
            profile["asset_bindings"],
            AssetBindingWire,
            path=f"{root}.asset_bindings",
        )
        for role, binding in profile["asset_bindings"].items():
            _validate_asset_items(
                binding["items"],
                path=f"{root}.asset_bindings.{role}.items",
            )
        validate_typed_items(
            profile["asset_token_specs"],
            AssetTokenSpecWire,
            path=f"{root}.asset_token_specs",
        )
        _validate_asset_items(
            profile["asset_items"],
            path=f"{root}.asset_items",
        )
        _validate_asset_item_history(
            profile["asset_item_history"],
            path=f"{root}.asset_item_history",
        )
        validate_typed_mapping(
            profile["image_material_rules"],
            ImageMaterialRuleWire,
            path=f"{root}.image_material_rules",
        )
        validate_typed_mapping(
            profile["content_bindings"],
            ContentMaterialBindingWire,
            path=f"{root}.content_bindings",
        )
        validate_typed_items(
            profile["content_rules"],
            ContentInsertionRuleWire,
            path=f"{root}.content_rules",
        )
        validate_typed_items(
            profile["attachment_role_specs"],
            AttachmentRoleSpecWire,
            path=f"{root}.attachment_role_specs",
        )
        validate_typed_mapping(
            profile["attachment_bindings"],
            AttachmentBindingWire,
            path=f"{root}.attachment_bindings",
        )


def _validate_asset_items(value: object, *, path: str) -> None:
    if type(value) is not list:
        raise ValueError(f"material_package_field_type_invalid:{path}:list")
    allowed = set(ASSET_ITEM_FIELD_TYPES)
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if type(item) is not dict:
            raise ValueError(f"material_package_field_type_invalid:{item_path}:dict")
        missing = sorted(ASSET_ITEM_REQUIRED_FIELDS - set(item))
        if missing:
            raise ValueError(
                f"material_package_nested_fields_missing:{item_path}:"
                f"{','.join(missing)}"
            )
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise ValueError(
                f"material_package_nested_fields_unknown:{item_path}:"
                f"{','.join(unknown)}"
            )
        for key, item_value in item.items():
            validate_exact_type(
                ASSET_ITEM_FIELD_TYPES[key],
                item_value,
                path=f"{item_path}.{key}",
            )
        for key in ASSET_ITEM_REQUIRED_FIELDS:
            if not item[key].strip():
                raise ValueError(
                    f"material_package_asset_item_identity_invalid:"
                    f"{item_path}.{key}"
                )


def _validate_asset_item_history(value: object, *, path: str) -> None:
    if type(value) is not list:
        raise ValueError(f"material_package_field_type_invalid:{path}:list")
    for index, record in enumerate(value):
        record_path = f"{path}[{index}]"
        if type(record) is not dict:
            raise ValueError(f"material_package_field_type_invalid:{record_path}:dict")
        missing = sorted({"action", "changed_at"} - set(record))
        if missing:
            raise ValueError(
                f"material_package_nested_fields_missing:{record_path}:"
                f"{','.join(missing)}"
            )
        unknown = sorted(set(record) - HISTORY_ALLOWED_FIELDS)
        if unknown:
            raise ValueError(
                f"material_package_nested_fields_unknown:{record_path}:"
                f"{','.join(unknown)}"
            )
        for key, item in record.items():
            validate_exact_type(str, item, path=f"{record_path}.{key}")
        if not record["action"].strip() or not record["changed_at"].strip():
            raise ValueError(f"material_package_history_identity_invalid:{record_path}")


__all__ = [
    "first_payload_difference",
    "validate_entity_archive_wire_payload",
]
