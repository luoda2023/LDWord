"""
Config dataclass helpers.

Keep "dict -> dataclass" materialization and deep-merge behavior in one place
so loader and resolver share the same rules.
"""

from __future__ import annotations

import copy
from dataclasses import fields, is_dataclass
from functools import lru_cache
from typing import Any, Mapping, MutableMapping, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")


def dict_to_dataclass(cls: type[T], data: Mapping[str, Any] | None) -> T:
    """Recursively materialize a dataclass from a mapping payload."""
    if data is None or not isinstance(data, Mapping):
        return cls()

    kwargs: dict[str, Any] = {}
    cls_fields = {f.name: f for f in fields(cls)}

    # Forward-reference resolution is part of the materialization contract.
    # Falling back to ``Field.type`` under ``from __future__ import annotations``
    # would leave nested mappings as raw dictionaries and create a delayed,
    # much harder-to-diagnose runtime break.
    hints = _resolved_type_hints(cls)

    for name, field_def in cls_fields.items():
        if name not in data:
            continue

        value = data[name]
        field_type = hints.get(name, field_def.type)
        kwargs[name] = _materialize_value(field_type, value)

    return cls(**kwargs)


@lru_cache(maxsize=None)
def _resolved_type_hints(dataclass_type: type) -> dict[str, Any]:
    """Resolve immutable class annotations once per process.

    Template and plan loading materializes the same nested dataclass types many
    times while a mode switch refreshes selectors.  ``get_type_hints``
    recompiles forward references on every call, so leaving it uncached turns a
    mode switch into tens of thousands of redundant annotation evaluations.
    Exceptions intentionally propagate and are not cached, preserving the
    fail-closed materialization contract.
    """

    return get_type_hints(dataclass_type)


def deep_merge_dict(
    base: MutableMapping[str, Any],
    patch: Mapping[str, Any] | None,
) -> MutableMapping[str, Any]:
    """Deep-merge patch into base and return base."""
    if not isinstance(patch, Mapping):
        return base

    for key, value in patch.items():
        if isinstance(value, Mapping):
            existing = base.get(key)
            target = dict(existing) if isinstance(existing, Mapping) else {}
            base[key] = deep_merge_dict(target, value)
        else:
            base[key] = copy.deepcopy(value)

    return base


def merge_dict_layers(*layers: Mapping[str, Any] | None) -> dict[str, Any]:
    """Deep-merge multiple mapping layers from left to right."""
    merged: dict[str, Any] = {}
    for layer in layers:
        deep_merge_dict(merged, layer)
    return merged


def _materialize_value(type_hint: Any, value: Any) -> Any:
    dataclass_type = _resolve_dataclass_type(type_hint)
    if dataclass_type is not None and isinstance(value, Mapping):
        return dict_to_dataclass(dataclass_type, value)

    list_item_type = _resolve_list_item_dataclass_type(type_hint)
    if list_item_type is not None and isinstance(value, list):
        return [
            dict_to_dataclass(list_item_type, item)
            if isinstance(item, Mapping)
            else item
            for item in value
        ]

    dict_value_type = _resolve_dict_value_dataclass_type(type_hint)
    if dict_value_type is not None and isinstance(value, Mapping):
        return {
            key: dict_to_dataclass(dict_value_type, item)
            if isinstance(item, Mapping)
            else item
            for key, item in value.items()
        }

    return value


def _resolve_dataclass_type(type_hint: Any) -> type | None:
    if type_hint is None or isinstance(type_hint, str):
        return None

    if isinstance(type_hint, type) and is_dataclass(type_hint):
        return type_hint

    origin = get_origin(type_hint)
    if origin is None:
        return None

    args = [arg for arg in get_args(type_hint) if arg is not type(None)]
    if len(args) != 1:
        return None

    candidate = args[0]
    if isinstance(candidate, type) and is_dataclass(candidate):
        return candidate
    return None


def _resolve_dict_value_dataclass_type(type_hint: Any) -> type | None:
    origin = get_origin(type_hint)
    if origin is not dict:
        return None

    args = get_args(type_hint)
    if len(args) != 2:
        return None

    value_type = args[1]
    if isinstance(value_type, type) and is_dataclass(value_type):
        return value_type
    return None


def _resolve_list_item_dataclass_type(type_hint: Any) -> type | None:
    origin = get_origin(type_hint)
    if origin is not list:
        return None

    args = get_args(type_hint)
    if len(args) != 1:
        return None

    item_type = args[0]
    if isinstance(item_type, type) and is_dataclass(item_type):
        return item_type
    return None
