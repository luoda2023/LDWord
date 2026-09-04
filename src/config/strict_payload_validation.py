"""Strict structural validation for canonical dataclass payloads.

Canonical configuration is executable product data.  Missing fields must not
be repaired from Python defaults and unknown fields must not be discarded.
This module owns the shared JSON-shape contract used by both templates and
plans; migration code stays at explicit import boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from functools import lru_cache
import math
import types
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints


class StrictPayloadValidationError(ValueError):
    """A payload is not a complete, type-safe dataclass tree."""


def validate_complete_dataclass_payload(
    dataclass_type: type,
    payload: object,
    *,
    root_label: str = "配置根对象",
) -> None:
    """Require every modeled field and validate its JSON value type.

    Unknown fields are rejected at every dataclass level.  ``float`` fields
    accept JSON integers because canonical defaults may serialize that way;
    booleans are never treated as integers.
    """

    if not isinstance(dataclass_type, type) or not is_dataclass(dataclass_type):
        raise TypeError("dataclass_type must be a dataclass type")
    _validate_dataclass_payload(
        dataclass_type,
        payload,
        path="",
        root_label=root_label,
    )


def _validate_dataclass_payload(
    dataclass_type: type,
    value: object,
    *,
    path: str,
    root_label: str,
) -> None:
    if not isinstance(value, Mapping):
        raise _type_error(path, "对象", value, root_label=root_label)

    field_defs = {field.name: field for field in fields(dataclass_type)}
    raw_keys = {str(key) for key in value}
    expected_keys = set(field_defs)

    unknown = sorted(raw_keys - expected_keys)
    if unknown:
        raise StrictPayloadValidationError(
            f"{_display_path(path, root_label)} 存在未支持字段：{'、'.join(unknown[:12])}"
        )

    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise StrictPayloadValidationError(
            f"{_display_path(path, root_label)} 缺少字段：{'、'.join(missing[:12])}"
        )

    hints = _resolved_type_hints(dataclass_type)
    for name, field_def in field_defs.items():
        field_path = f"{path}.{name}" if path else name
        _validate_value(
            hints.get(name, field_def.type),
            value[name],
            path=field_path,
            root_label=root_label,
        )


def _validate_value(
    type_hint: Any,
    value: object,
    *,
    path: str,
    root_label: str,
) -> None:
    if type_hint is Any:
        return

    if isinstance(type_hint, type) and is_dataclass(type_hint):
        _validate_dataclass_payload(
            type_hint,
            value,
            path=path,
            root_label=root_label,
        )
        return

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return
        candidates = tuple(arg for arg in args if arg is not type(None))
        errors: list[StrictPayloadValidationError] = []
        for candidate in candidates:
            try:
                _validate_value(
                    candidate,
                    value,
                    path=path,
                    root_label=root_label,
                )
                return
            except StrictPayloadValidationError as exc:
                errors.append(exc)
        if errors:
            raise errors[0]
        raise _type_error(
            path,
            "合同允许的类型",
            value,
            root_label=root_label,
        )

    if origin is Literal:
        if value not in args:
            allowed = "、".join(repr(item) for item in args)
            raise StrictPayloadValidationError(
                f"{_display_path(path, root_label)} 必须是以下值之一：{allowed}"
            )
        return

    if origin is list:
        if not isinstance(value, list):
            raise _type_error(path, "数组", value, root_label=root_label)
        item_type = args[0] if args else Any
        for index, item in enumerate(value):
            _validate_value(
                item_type,
                item,
                path=f"{path}[{index}]",
                root_label=root_label,
            )
        return

    if origin is tuple:
        if not isinstance(value, list):
            raise _type_error(path, "数组", value, root_label=root_label)
        if len(args) == 2 and args[1] is Ellipsis:
            for index, item in enumerate(value):
                _validate_value(
                    args[0],
                    item,
                    path=f"{path}[{index}]",
                    root_label=root_label,
                )
            return
        if args and len(value) != len(args):
            raise StrictPayloadValidationError(
                f"{_display_path(path, root_label)} 数组长度应为 {len(args)}，"
                f"实际为 {len(value)}"
            )
        for index, (item_type, item) in enumerate(zip(args, value)):
            _validate_value(
                item_type,
                item,
                path=f"{path}[{index}]",
                root_label=root_label,
            )
        return

    if origin in (dict, Mapping):
        if not isinstance(value, Mapping):
            raise _type_error(path, "对象", value, root_label=root_label)
        key_type, item_type = args if len(args) == 2 else (Any, Any)
        for key, item in value.items():
            _validate_value(
                key_type,
                key,
                path=f"{path}.<key>",
                root_label=root_label,
            )
            item_path = f"{path}.{key}" if path else str(key)
            _validate_value(
                item_type,
                item,
                path=item_path,
                root_label=root_label,
            )
        return

    if type_hint is bool:
        if type(value) is not bool:
            raise _type_error(path, "布尔值", value, root_label=root_label)
        return

    if type_hint is int:
        if type(value) is not int:
            raise _type_error(path, "整数", value, root_label=root_label)
        return

    if type_hint is float:
        if type(value) not in (int, float):
            raise _type_error(path, "数值", value, root_label=root_label)
        if type(value) is float and not math.isfinite(value):
            raise StrictPayloadValidationError(
                f"{_display_path(path, root_label)} must be a finite number"
            )
        return

    if type_hint is str:
        if type(value) is not str:
            raise _type_error(path, "文本", value, root_label=root_label)
        return

    if type_hint is type(None):
        if value is not None:
            raise _type_error(path, "null", value, root_label=root_label)
        return

    if isinstance(type_hint, type) and not isinstance(value, type_hint):
        raise _type_error(
            path,
            type_hint.__name__,
            value,
            root_label=root_label,
        )


@lru_cache(maxsize=None)
def _resolved_type_hints(dataclass_type: type) -> dict[str, Any]:
    try:
        return get_type_hints(dataclass_type)
    except Exception as exc:
        raise StrictPayloadValidationError(
            f"无法解析 `{dataclass_type.__name__}` 的类型约束，拒绝跳过严格校验"
        ) from exc


def _display_path(path: str, root_label: str) -> str:
    return f"字段 `{path}`" if path else root_label


def _type_error(
    path: str,
    expected: str,
    value: object,
    *,
    root_label: str,
) -> StrictPayloadValidationError:
    actual = _json_type_name(value)
    return StrictPayloadValidationError(
        f"{_display_path(path, root_label)} 必须是{expected}，实际为{actual}"
    )


def _json_type_name(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "布尔值"
    if type(value) is int:
        return "整数"
    if type(value) is float:
        return "数值"
    if isinstance(value, str):
        return "文本"
    if isinstance(value, list):
        return "数组"
    if isinstance(value, Mapping):
        return "对象"
    return type(value).__name__


__all__ = [
    "StrictPayloadValidationError",
    "validate_complete_dataclass_payload",
]
