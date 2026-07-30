from __future__ import annotations

import pytest

from src.shared.engine.material_token_contract import (
    MATERIAL_TOKEN_NAMESPACE_REGISTRY,
    MaterialTokenKind,
    MaterialTokenNamespace,
    MaterialTokenProducer,
    material_token,
    normalize_material_token,
    parse_material_token,
)


@pytest.mark.parametrize(
    ("namespace", "kind", "producer"),
    (
        (MaterialTokenNamespace.TEXT, MaterialTokenKind.FIELD, MaterialTokenProducer.MANUAL),
        (MaterialTokenNamespace.TIME, MaterialTokenKind.FIELD, MaterialTokenProducer.TIMELINE),
        (MaterialTokenNamespace.FILE, MaterialTokenKind.CONTENT, MaterialTokenProducer.FILE_BINDING),
        (MaterialTokenNamespace.IMAGE, MaterialTokenKind.IMAGE, MaterialTokenProducer.IMAGE_BINDING),
        (
            MaterialTokenNamespace.ATTACHMENT,
            MaterialTokenKind.ATTACHMENT,
            MaterialTokenProducer.ATTACHMENT_BINDING,
        ),
    ),
)
def test_namespace_registry_is_the_only_kind_source(namespace, kind, producer):
    spec = MATERIAL_TOKEN_NAMESPACE_REGISTRY[namespace]
    ref = parse_material_token(material_token(namespace, "technical_route"))

    assert ref.namespace is namespace
    assert ref.identifier == "technical_route"
    assert ref.kind is kind
    assert ref.default_producer is producer
    assert ref.validate_kind(kind) is kind
    assert ref.validate_producer(producer) is producer


def test_text_namespace_allows_manual_or_function_producers():
    ref = parse_material_token("{{@text:company_name}}")

    assert ref.validate_producer("manual") is MaterialTokenProducer.MANUAL
    assert ref.validate_producer("function") is MaterialTokenProducer.FUNCTION


def test_kind_and_producer_conflicts_are_blocked():
    ref = parse_material_token("{{@file:technical_route}}")

    with pytest.raises(ValueError, match="conflicts"):
        ref.validate_kind(MaterialTokenKind.FIELD)
    with pytest.raises(ValueError, match="not valid"):
        ref.validate_producer(MaterialTokenProducer.MANUAL)


@pytest.mark.parametrize(
    "value",
    ("company_name", "{{company_name}}", "{{@content:route}}", "{{@img:}}", "{{@text:a:b}}"),
)
def test_unnamespaced_unknown_or_malformed_tokens_are_rejected(value):
    with pytest.raises(ValueError):
        parse_material_token(value)


def test_normalizer_can_apply_an_explicit_namespace_to_an_identifier():
    assert normalize_material_token(
        "签发日期", namespace=MaterialTokenNamespace.TIME
    ) == "{{@time:签发日期}}"
