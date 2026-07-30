"""Resolve persisted image policy exactly once before the intake Freeze.

The output types contain no field token template and no font lookup input.
Target-DOCX inspection is intentionally absent; that belongs to the later
delivery-variant planning boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImageCardinality,
    ImageMaterialRule,
    ImageSourceBinding,
    ImageSourceItem,
)
from src.services.material_assets.image_transformer import (
    ImageTransformError,
    resolve_image_watermark,
)


@dataclass(frozen=True, slots=True)
class FrozenImagePolicy:
    """Typed output ready to enter :class:`MaterialSnapshot`."""

    rules: tuple[FrozenImageMaterialRule, ...]
    source_bindings: tuple[ImageSourceBinding, ...]

    def __post_init__(self) -> None:
        rules = tuple(self.rules or ())
        sources = tuple(self.source_bindings or ())
        if any(not isinstance(item, FrozenImageMaterialRule) for item in rules):
            raise TypeError("rules must contain FrozenImageMaterialRule values")
        if any(not isinstance(item, ImageSourceBinding) for item in sources):
            raise TypeError("source_bindings must contain ImageSourceBinding values")
        object.__setattr__(
            self,
            "rules",
            tuple(sorted(rules, key=lambda item: item.rule_id.casefold())),
        )
        object.__setattr__(
            self,
            "source_bindings",
            tuple(
                sorted(
                    sources,
                    key=lambda item: (
                        item.role.casefold(),
                        item.sequence,
                        item.item_id.casefold(),
                    ),
                )
            ),
        )


class ImagePolicyFreezeError(ValueError):
    """Stable error raised before an incomplete frozen policy can escape."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        rule_id: str = "",
        source_role: str = "",
        item_id: str = "",
    ) -> None:
        self.code = str(code)
        self.rule_id = str(rule_id)
        self.source_role = str(source_role)
        self.item_id = str(item_id)
        super().__init__(str(message))


class ImagePolicyFreezer:
    """Convert mutable-stage policy/source inputs to execution-safe facts."""

    def freeze(
        self,
        *,
        frozen_field_values: Mapping[str, object],
        rules: Sequence[ImageMaterialRule],
        source_items: Sequence[ImageSourceItem],
        runtime_watermark_text: str = "",
        watermark_font_path: str | Path | None = None,
        watermark_font_identity: str = "",
    ) -> FrozenImagePolicy:
        if not isinstance(frozen_field_values, Mapping):
            raise TypeError("frozen_field_values must be a mapping")
        if not isinstance(runtime_watermark_text, str):
            raise TypeError("runtime_watermark_text must be a string")
        normalized_rules = _typed_sequence(
            rules,
            ImageMaterialRule,
            "rules",
        )
        normalized_sources = _typed_sequence(
            source_items,
            ImageSourceItem,
            "source_items",
        )
        _validate_unique_rules(normalized_rules)
        _validate_sources(normalized_rules, normalized_sources)

        frozen_rules: list[FrozenImageMaterialRule] = []
        for rule in sorted(
            normalized_rules,
            key=lambda item: item.rule_id.casefold(),
        ):
            try:
                watermark = resolve_image_watermark(
                    rule.watermark,
                    frozen_field_values,
                    runtime_text=runtime_watermark_text,
                    font_path=watermark_font_path,
                    font_identity=watermark_font_identity,
                )
            except ImageTransformError as exc:
                raise ImagePolicyFreezeError(
                    f"watermark_{exc.code}",
                    str(exc),
                    rule_id=rule.rule_id,
                    source_role=rule.source_role,
                ) from exc
            frozen_rules.append(
                FrozenImageMaterialRule(
                    rule_id=rule.rule_id,
                    source_role=rule.source_role,
                    anchor_token=rule.anchor_token,
                    placement=rule.placement,
                    watermark=watermark,
                    required=rule.required,
                    occurrence_policy=rule.occurrence_policy,
                    cardinality=rule.cardinality,
                )
            )

        bindings = tuple(
            ImageSourceBinding(
                role=item.role,
                item_id=item.item_id,
                sequence=item.sequence,
                file_ref=item.image_ref,
            )
            for item in normalized_sources
        )
        return FrozenImagePolicy(tuple(frozen_rules), bindings)


def freeze_image_policy(
    *,
    frozen_field_values: Mapping[str, object],
    rules: Sequence[ImageMaterialRule],
    source_items: Sequence[ImageSourceItem],
    runtime_watermark_text: str = "",
    watermark_font_path: str | Path | None = None,
    watermark_font_identity: str = "",
) -> FrozenImagePolicy:
    """Freeze image policy with the default stateless implementation."""

    return ImagePolicyFreezer().freeze(
        frozen_field_values=frozen_field_values,
        rules=rules,
        source_items=source_items,
        runtime_watermark_text=runtime_watermark_text,
        watermark_font_path=watermark_font_path,
        watermark_font_identity=watermark_font_identity,
    )


def _typed_sequence(values, expected_type, field_name):
    if not isinstance(values, Sequence) or isinstance(
        values, (str, bytes, bytearray)
    ):
        raise TypeError(f"{field_name} must be a sequence")
    normalized = tuple(values)
    if any(not isinstance(item, expected_type) for item in normalized):
        raise TypeError(
            f"{field_name} must contain only {expected_type.__name__} values"
        )
    return normalized


def _validate_unique_rules(rules: Sequence[ImageMaterialRule]) -> None:
    for attribute, code in (
        ("rule_id", "duplicate_rule_id"),
        ("source_role", "duplicate_source_role"),
        ("anchor_token", "duplicate_anchor_token"),
    ):
        seen: set[str] = set()
        for rule in rules:
            value = getattr(rule, attribute)
            if value in seen:
                raise ImagePolicyFreezeError(
                    code,
                    f"{attribute} {value!r} is declared more than once",
                    rule_id=rule.rule_id,
                    source_role=rule.source_role,
                )
            seen.add(value)


def _validate_sources(
    rules: Sequence[ImageMaterialRule],
    sources: Sequence[ImageSourceItem],
) -> None:
    rules_by_role = {item.source_role: item for item in rules}
    seen_item_ids: set[str] = set()
    seen_role_sequences: set[tuple[str, int]] = set()
    by_role: dict[str, list[ImageSourceItem]] = {}
    for item in sources:
        if item.item_id in seen_item_ids:
            raise ImagePolicyFreezeError(
                "duplicate_source_item_id",
                f"source item_id {item.item_id!r} is not unique",
                source_role=item.role,
                item_id=item.item_id,
            )
        seen_item_ids.add(item.item_id)
        role_sequence = (item.role, item.sequence)
        if role_sequence in seen_role_sequences:
            raise ImagePolicyFreezeError(
                "duplicate_source_sequence",
                f"role {item.role!r} has duplicate sequence {item.sequence}",
                source_role=item.role,
                item_id=item.item_id,
            )
        seen_role_sequences.add(role_sequence)
        if item.role not in rules_by_role:
            raise ImagePolicyFreezeError(
                "unknown_source_role",
                f"source item {item.item_id!r} uses undeclared role {item.role!r}",
                source_role=item.role,
                item_id=item.item_id,
            )
        by_role.setdefault(item.role, []).append(item)

    for rule in rules:
        selected = by_role.get(rule.source_role, ())
        if rule.required and not selected:
            raise ImagePolicyFreezeError(
                "required_image_source_missing",
                f"required role {rule.source_role!r} has no selected image",
                rule_id=rule.rule_id,
                source_role=rule.source_role,
            )
        if rule.cardinality is ImageCardinality.SINGLE and len(selected) > 1:
            raise ImagePolicyFreezeError(
                "single_image_cardinality_exceeded",
                f"role {rule.source_role!r} permits one image but has {len(selected)}",
                rule_id=rule.rule_id,
                source_role=rule.source_role,
            )


__all__ = [
    "FrozenImagePolicy",
    "ImagePolicyFreezeError",
    "ImagePolicyFreezer",
    "ImageSourceItem",
    "freeze_image_policy",
]
