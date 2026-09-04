"""Strict plain-data helpers used at assistant persistence boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from typing import Any


def plain_data(value: Any, *, path: str = "$") -> Any:
    """Return detached JSON-compatible data or reject live Python objects."""

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"Non-finite number at {path}")
        return float(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"Assistant mapping key must be text at {path}")
            result[key] = plain_data(item, path=f"{path}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [plain_data(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    raise TypeError(
        f"Unsupported assistant payload value at {path}: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def mapping_tuple(value: object) -> tuple[dict[str, Any], ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("Expected a sequence of mappings")
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TypeError(f"Expected mapping at index {index}")
        normalized = plain_data(item, path=f"$[{index}]")
        items.append(dict(normalized))
    return tuple(items)


def text_tuple(value: object) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("Expected a sequence of text values")
    return tuple(str(item or "") for item in value)


def canonical_json(value: object) -> str:
    return json.dumps(
        plain_data(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


__all__ = ["canonical_json", "mapping_tuple", "payload_sha256", "plain_data", "text_tuple"]
