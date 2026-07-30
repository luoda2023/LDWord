from __future__ import annotations

import pytest

from src.config.content_materials import ContentInsertionRule
from src.shared.engine.material_token_router import (
    MaterialTokenKind,
    TokenDeclaration,
    TokenDiagnosticCode,
    TokenOccurrencePolicy,
    TokenTextBlock,
    route_material_tokens,
)


def _codes(result) -> list[TokenDiagnosticCode]:
    return [item.code for item in result.diagnostics]


def test_router_classifies_namespace_registered_images_and_fields() -> None:
    rule = ContentInsertionRule(
        "route-rule", "technical_route", "{{@file:technical_route}}"
    )
    result = route_material_tokens(
        ["{{@text:company_name}} {{@img:LOGO1}} {{@file:technical_route}}"],
        image_tokens=["{{@img:LOGO1}}"],
        content_rules=[rule],
    )

    assert result.ok
    assert [item.kind for item in result.occurrences] == [
        MaterialTokenKind.FIELD,
        MaterialTokenKind.IMAGE,
        MaterialTokenKind.CONTENT,
    ]
    assert result.occurrence_count("@text:company_name") == 1
    assert result.route_for("@img:LOGO1").kind is MaterialTokenKind.IMAGE


def test_router_counts_real_occurrences_including_same_block_duplicates() -> None:
    result = route_material_tokens(
        ["{{@img:LOGO1}} middle {{@img:LOGO1}}"],
        image_tokens=["@img:LOGO1"],
    )

    route = result.route_for("@img:LOGO1")
    assert route is not None
    assert route.occurrence_count == 2
    assert [item.token_ordinal for item in route.occurrences] == [1, 2]
    assert TokenDiagnosticCode.DUPLICATE_OCCURRENCE in _codes(result)


def test_router_joins_runs_and_reports_cross_run_span_once() -> None:
    block = TokenTextBlock.from_runs(
        "body-p-7",
        ("prefix {{@text:comp", "any_name}} suffix"),
        surface="body",
    )
    result = route_material_tokens([block])

    assert result.ok
    assert result.occurrence_count("@text:company_name") == 1
    occurrence = result.field_occurrences[0]
    assert occurrence.start_run_index == 0
    assert occurrence.end_run_index == 1
    assert occurrence.block_id == "body-p-7"


def test_content_all_policy_allows_multiple_stable_occurrences() -> None:
    rule = ContentInsertionRule(
        "route-rule",
        "technical_route",
        "{{@file:technical_route}}",
        occurrence_policy="all",
    )
    blocks = [
        TokenTextBlock("p1", text="{{@file:technical_route}}"),
        TokenTextBlock("p2", runs=("{{@file:", "technical_route}}")),
    ]
    first = route_material_tokens(blocks, content_rules=[rule])
    second = route_material_tokens(blocks, content_rules=[rule])

    assert first.ok
    assert first.occurrence_count("@file:technical_route") == 2
    assert [item.occurrence_id for item in first.occurrences] == [
        item.occurrence_id for item in second.occurrences
    ]


def test_router_reports_missing_and_duplicate_declarations_while_kind_is_structural() -> None:
    content_rule = ContentInsertionRule(
        "route-rule", "technical_route", "{{@file:technical_route}}"
    )
    with pytest.raises(ValueError, match="derives kind=content"):
        TokenDeclaration(
            "{{@file:technical_route}}",
            MaterialTokenKind.IMAGE,
        )
    result = route_material_tokens(
        ["no configured anchors here"],
        image_tokens=[
            "{{@img:MISSING_IMAGE}}",
            "{{@img:MISSING_IMAGE}}",
        ],
        content_rules=[content_rule],
    )

    codes = _codes(result)
    assert TokenDiagnosticCode.DUPLICATE_DECLARATION in codes
    assert codes.count(TokenDiagnosticCode.MISSING_OCCURRENCE) >= 2
    assert not result.ok


def test_unbound_content_namespace_and_invalid_token_are_not_silent_fields() -> None:
    result = route_material_tokens(
        [TokenTextBlock("p1", text="{{@file:route}} {{ field }}")]
    )

    assert result.content_occurrences[0].token == "{{@file:route}}"
    assert TokenDiagnosticCode.MISSING_DECLARATION in _codes(result)
    assert TokenDiagnosticCode.INVALID_TOKEN in _codes(result)
    assert not result.ok


def test_optional_declared_image_may_be_absent_without_error() -> None:
    declaration = TokenDeclaration(
        "{{@img:OPTIONAL_IMAGE}}",
        MaterialTokenKind.IMAGE,
        declaration_id="optional-image",
        required=False,
        occurrence_policy=TokenOccurrencePolicy.EXACTLY_ONE,
    )
    result = route_material_tokens(
        ["{{@text:field}}"],
        image_tokens=[declaration],
    )

    assert result.ok
    assert result.occurrence_count("@img:OPTIONAL_IMAGE") == 0


def test_consumer_scope_separates_identical_document_occurrences() -> None:
    blocks = [TokenTextBlock("body-p-000001", text="{{@img:LOGO1}}")]
    first = route_material_tokens(
        blocks,
        image_tokens=["@img:LOGO1"],
        consumer_id="attachment:evidence:item-a",
    )
    repeated = route_material_tokens(
        blocks,
        image_tokens=["@img:LOGO1"],
        consumer_id="attachment:evidence:item-a",
    )
    second = route_material_tokens(
        blocks,
        image_tokens=["@img:LOGO1"],
        consumer_id="attachment:evidence:item-b",
    )

    assert first.occurrences[0].occurrence_id == repeated.occurrences[0].occurrence_id
    assert first.occurrences[0].occurrence_id != second.occurrences[0].occurrence_id
    assert (
        first.occurrences[0].router_occurrence_id
        == second.occurrences[0].router_occurrence_id
    )
