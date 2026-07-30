from __future__ import annotations

from dataclasses import asdict

import pytest

from src.config.builtin_templates import create_builtin_template
import src.config.strict_payload_validation as validation_module
from src.config.template_authoring_validation import (
    TemplatePayloadValidationError,
    validate_complete_template_payload,
)


def _payload() -> dict:
    return asdict(create_builtin_template("thesis_gbt"))


def test_complete_canonical_template_payload_is_valid() -> None:
    validate_complete_template_payload(_payload())


def test_missing_nested_dataclass_field_is_rejected() -> None:
    payload = _payload()
    del payload["page_setup"]["margin"]["top_cm"]

    with pytest.raises(TemplatePayloadValidationError, match=r"page_setup\.margin"):
        validate_complete_template_payload(payload)


def test_unknown_nested_dataclass_field_is_rejected() -> None:
    payload = _payload()
    payload["styles"]["body"]["font_cnn"] = "宋体"

    with pytest.raises(TemplatePayloadValidationError, match="font_cnn"):
        validate_complete_template_payload(payload)


def test_numeric_string_is_rejected_without_coercion() -> None:
    payload = _payload()
    payload["page_setup"]["margin"]["top_cm"] = "3.0"

    with pytest.raises(TemplatePayloadValidationError, match="必须是数值"):
        validate_complete_template_payload(payload)


def test_bool_is_not_accepted_as_number() -> None:
    payload = _payload()
    payload["page_setup"]["margin"]["top_cm"] = True

    with pytest.raises(TemplatePayloadValidationError, match="必须是数值"):
        validate_complete_template_payload(payload)


def test_dataclass_default_that_serializes_as_integer_satisfies_float_field() -> None:
    payload = _payload()
    payload["styles"]["body"]["line_spacing_pt"] = 20

    validate_complete_template_payload(payload)


def test_type_hint_resolution_failure_is_not_silently_accepted(monkeypatch) -> None:
    payload = _payload()
    validation_module._resolved_type_hints.cache_clear()

    def fail_type_hint_resolution(_dataclass_type):
        raise NameError("injected unresolved forward reference")

    monkeypatch.setattr(
        validation_module,
        "get_type_hints",
        fail_type_hint_resolution,
    )

    with pytest.raises(TemplatePayloadValidationError, match="拒绝跳过严格校验"):
        validate_complete_template_payload(payload)

    validation_module._resolved_type_hints.cache_clear()
