"""Reusable, exact-type JSON wire validation primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields as dataclass_fields
import math
import types
from typing import Any, Union, get_args, get_origin, get_type_hints


def first_payload_difference(
    actual: object,
    canonical: object,
    *,
    path: str = "<profile>",
) -> str:
    """Return the first deterministic, type-sensitive payload difference."""

    if type(actual) is not type(canonical):
        return path
    if isinstance(actual, dict) and isinstance(canonical, dict):
        keys = sorted(set(actual) | set(canonical))
        for key in keys:
            child_path = f"{path}.{key}"
            if key not in actual or key not in canonical:
                return child_path
            difference = first_payload_difference(
                actual[key],
                canonical[key],
                path=child_path,
            )
            if difference:
                return difference
        return ""
    if isinstance(actual, list) and isinstance(canonical, list):
        if len(actual) != len(canonical):
            return path
        for index, (actual_item, canonical_item) in enumerate(
            zip(actual, canonical, strict=True)
        ):
            difference = first_payload_difference(
                actual_item,
                canonical_item,
                path=f"{path}[{index}]",
            )
            if difference:
                return difference
        return ""
    return "" if actual == canonical else path


def validate_typed_mapping(
    value: dict[str, object],
    contract_type: type,
    *,
    path: str,
) -> None:
    for key, item in value.items():
        validate_wire_dataclass(item, contract_type, path=f"{path}.{key}")


def validate_typed_items(
    value: list[object],
    contract_type: type,
    *,
    path: str,
) -> None:
    for index, item in enumerate(value):
        validate_wire_dataclass(item, contract_type, path=f"{path}[{index}]")


def validate_wire_dataclass(
    value: object,
    contract_type: type,
    *,
    path: str,
) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"material_package_field_type_invalid:{path}:dict")
    field_names = [field.name for field in dataclass_fields(contract_type)]
    expected = set(field_names)
    actual = set(value)
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(
            f"material_package_nested_fields_missing:{path}:{','.join(missing)}"
        )
    unknown = sorted(actual - expected)
    if unknown:
        raise ValueError(
            f"material_package_nested_fields_unknown:{path}:{','.join(unknown)}"
        )
    hints = get_type_hints(contract_type)
    for name in field_names:
        validate_exact_type(hints[name], value[name], path=f"{path}.{name}")


def validate_exact_type(type_hint: object, value: object, *, path: str) -> None:
    if type_hint is Any:
        validate_json_value(value, path=path)
        return
    if isinstance(type_hint, type) and hasattr(type_hint, "__dataclass_fields__"):
        validate_wire_dataclass(value, type_hint, path=path)
        return
    origin = get_origin(type_hint)
    args = get_args(type_hint)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                validate_exact_type(candidate, value, path=path)
            except ValueError:
                continue
            return
        raise ValueError(f"material_package_field_type_invalid:{path}:union")
    if origin is list:
        if type(value) is not list:
            raise ValueError(f"material_package_field_type_invalid:{path}:list")
        item_type = args[0] if args else Any
        for index, item in enumerate(value):
            validate_exact_type(item_type, item, path=f"{path}[{index}]")
        return
    if origin in (dict, Mapping):
        if type(value) is not dict:
            raise ValueError(f"material_package_field_type_invalid:{path}:dict")
        key_type, item_type = args if len(args) == 2 else (Any, Any)
        for key, item in value.items():
            validate_exact_type(key_type, key, path=f"{path}.<key>")
            validate_exact_type(item_type, item, path=f"{path}.{key}")
        return
    if type_hint is float:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError(f"material_package_field_type_invalid:{path}:finite_float")
        return
    if type_hint in (bool, int, str):
        if type(value) is not type_hint:
            raise ValueError(
                f"material_package_field_type_invalid:{path}:{type_hint.__name__}"
            )
        return
    if type_hint is type(None):
        if value is not None:
            raise ValueError(f"material_package_field_type_invalid:{path}:null")
        return
    if isinstance(type_hint, type) and not isinstance(value, type_hint):
        raise ValueError(
            f"material_package_field_type_invalid:{path}:{type_hint.__name__}"
        )


def validate_exact_string_mapping(
    value: object,
    fields: set[str],
    *,
    path: str,
) -> None:
    if type(value) is not dict:
        raise ValueError(f"material_package_field_type_invalid:{path}:dict")
    require_exact_fields(value, fields, path=path)
    for key, item in value.items():
        validate_exact_type(str, item, path=f"{path}.{key}")


def require_exact_fields(value: dict, fields: set[str], *, path: str) -> None:
    missing = sorted(fields - set(value))
    if missing:
        raise ValueError(
            f"material_package_nested_fields_missing:{path}:{','.join(missing)}"
        )
    unknown = sorted(set(value) - fields)
    if unknown:
        raise ValueError(
            f"material_package_nested_fields_unknown:{path}:{','.join(unknown)}"
        )


def validate_json_value(value: object, *, path: str) -> None:
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"material_package_nonfinite_number:{path}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            validate_json_value(item, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"material_package_json_key_invalid:{path}")
            validate_json_value(item, path=f"{path}.{key}")
        return
    raise ValueError(
        f"material_package_json_value_invalid:{path}:{type(value).__name__}"
    )


__all__ = [
    "first_payload_difference",
    "require_exact_fields",
    "validate_exact_string_mapping",
    "validate_exact_type",
    "validate_json_value",
    "validate_typed_items",
    "validate_typed_mapping",
]
