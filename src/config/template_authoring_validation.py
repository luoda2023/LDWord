"""Template-specific facade over shared strict payload validation."""

from __future__ import annotations

from src.config.template import TemplateConfig
from src.config.strict_payload_validation import (
    StrictPayloadValidationError,
    validate_complete_dataclass_payload,
)


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


__all__ = [
    "TemplatePayloadValidationError",
    "validate_complete_template_payload",
]
