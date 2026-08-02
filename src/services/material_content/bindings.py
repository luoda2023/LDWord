"""Role-level commands for immutable compiled content bindings."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import replace

from src.config.content_artifacts import ContentMaterialBinding


def replace_content_binding(
    bindings: Mapping[str, ContentMaterialBinding] | None,
    binding: ContentMaterialBinding,
) -> dict[str, ContentMaterialBinding]:
    if not isinstance(binding, ContentMaterialBinding):
        raise TypeError("binding must be a ContentMaterialBinding")
    updated = _copy_bindings(bindings)
    updated[binding.content_id] = copy.deepcopy(binding)
    return dict(sorted(updated.items()))


def clear_content_binding(
    bindings: Mapping[str, ContentMaterialBinding] | None,
    content_id: str,
) -> dict[str, ContentMaterialBinding]:
    normalized_id = _required_content_id(content_id)
    updated = _copy_bindings(bindings)
    updated.pop(normalized_id, None)
    return dict(sorted(updated.items()))


def rename_content_binding(
    bindings: Mapping[str, ContentMaterialBinding] | None,
    *,
    content_id: str,
    new_content_id: str,
) -> dict[str, ContentMaterialBinding]:
    current_id = _required_content_id(content_id)
    target_id = _required_content_id(new_content_id)
    updated = _copy_bindings(bindings)
    if target_id != current_id and target_id in updated:
        raise ValueError("content_binding_target_exists")
    binding = updated.pop(current_id, None)
    if binding is not None:
        updated[target_id] = replace(
            binding,
            content_id=target_id,
            label=target_id if binding.label == current_id else binding.label,
        )
    return dict(sorted(updated.items()))


def _copy_bindings(
    bindings: Mapping[str, ContentMaterialBinding] | None,
) -> dict[str, ContentMaterialBinding]:
    copied: dict[str, ContentMaterialBinding] = {}
    for raw_id, binding in dict(bindings or {}).items():
        content_id = _required_content_id(raw_id)
        if not isinstance(binding, ContentMaterialBinding):
            raise TypeError(
                "content bindings must contain ContentMaterialBinding values"
            )
        if binding.content_id != content_id:
            raise ValueError("content_binding_identity_mismatch")
        copied[content_id] = copy.deepcopy(binding)
    return copied


def _required_content_id(value: object) -> str:
    content_id = str(value or "").strip()
    if (
        not content_id
        or any(character.isspace() for character in content_id)
        or any(character in "{}:" for character in content_id)
    ):
        raise ValueError("content_binding_id_invalid")
    return content_id


__all__ = [
    "clear_content_binding",
    "rename_content_binding",
    "replace_content_binding",
]
