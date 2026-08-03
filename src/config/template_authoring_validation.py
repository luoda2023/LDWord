"""Template-specific facade over shared strict payload validation."""

from __future__ import annotations

from collections.abc import Mapping

from src.config.special_title_rules import validate_special_title_model
from src.config.strict_payload_validation import (
    StrictPayloadValidationError,
    validate_complete_dataclass_payload,
)
from src.config.template import TemplateConfig


class TemplatePayloadValidationError(ValueError):
    """A payload is not a complete, type-safe ``TemplateConfig`` tree."""


def validate_complete_template_payload(payload: object) -> None:
    """Require a complete current-version ``TemplateConfig`` tree."""

    try:
        validate_complete_dataclass_payload(
            TemplateConfig,
            payload,
            root_label="模板根对象",
        )
    except StrictPayloadValidationError as exc:
        raise TemplatePayloadValidationError(str(exc)) from exc

    if isinstance(payload, Mapping):
        try:
            validate_special_title_model(payload.get("heading_model"))
        except ValueError as exc:
            raise TemplatePayloadValidationError(
                f"heading_model 特殊标题规则无效：{exc}"
            ) from exc


__all__ = [
    "TemplatePayloadValidationError",
    "validate_complete_template_payload",
]
