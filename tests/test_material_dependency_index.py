from __future__ import annotations

from src.config.content_materials import (
    ContentInsertionRule,
    FileAssetRef,
    content_anchor_token,
)
from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageSourceBinding,
    ResolvedImageWatermark,
)
from src.shared.engine.material_dependency_index import (
    MaterialConsumerKind,
    MaterialConsumerRef,
    build_material_dependency_index,
    scan_material_consumer,
)
from src.shared.engine.material_token_router import MaterialTokenKind, TokenTextBlock


def _rule() -> FrozenImageMaterialRule:
    return FrozenImageMaterialRule(
        rule_id="logo-rule",
        source_role="logo",
        anchor_token="{{@img:LOGO1}}",
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=4,
        ),
        watermark=ResolvedImageWatermark.disabled(),
    )


def _source() -> ImageSourceBinding:
    return ImageSourceBinding(
        role="logo",
        item_id="logo-1",
        sequence=0,
        file_ref=FileAssetRef(
            source_path="C:/materials/logo.png",
            original_name="logo.png",
            media_type="image/png",
            content_sha256="a" * 64,
            byte_size=100,
        ),
    )


def _attachment(item_id: str) -> MaterialConsumerRef:
    return MaterialConsumerRef(
        MaterialConsumerKind.ATTACHMENT_ITEM,
        owner_id="evidence",
        item_id=item_id,
    )


def test_identical_tokens_in_two_files_have_scoped_ids_and_shared_resources() -> None:
    blocks = [
        TokenTextBlock(
            "body-p-1",
            text="{{@text:company}} {{@img:LOGO1}}",
        )
    ]
    first = scan_material_consumer(
        _attachment("item-a"),
        blocks,
        image_rules=(_rule(),),
    )
    second = scan_material_consumer(
        _attachment("item-b"),
        blocks,
        image_rules=(_rule(),),
    )

    index = build_material_dependency_index(
        (first, second),
        field_values={"company_name": "Example"},
        field_token_bindings={
            "@text:company_name": "company_name",
            "@text:company": "company_name",
        },
        image_rules=(_rule(),),
        image_source_bindings=(_source(),),
    )

    assert index.ok
    assert index.consumer_count == 2
    fields = index.occurrences_for_resource(
        MaterialTokenKind.FIELD, "company_name"
    )
    images = index.occurrences_for_resource(MaterialTokenKind.IMAGE, "logo")
    assert len(fields) == len(images) == 2
    assert fields[0].occurrence_id != fields[1].occurrence_id
    assert images[0].occurrence_id != images[1].occurrence_id
    assert images[0].router_occurrence_id == images[1].router_occurrence_id


def test_exactly_one_policy_is_evaluated_per_consumer_not_across_index() -> None:
    scans = tuple(
        scan_material_consumer(
            _attachment(item_id),
            [TokenTextBlock("body-p-1", text="{{@img:LOGO1}}")],
            image_rules=(_rule(),),
        )
        for item_id in ("a", "b")
    )

    index = build_material_dependency_index(
        scans,
        field_values={},
        field_token_bindings={},
        image_rules=(_rule(),),
        image_source_bindings=(_source(),),
    )

    assert index.ok
    assert len(index.occurrences) == 2
    assert not any(
        diagnostic.code == "token_duplicate_occurrence"
        for diagnostic in index.diagnostics
    )


def test_unknown_field_and_attachment_content_tokens_are_blocking_dependencies() -> None:
    scan = scan_material_consumer(
        _attachment("item-a"),
        ["{{@text:unknown}} {{@file:nested}}"],
    )

    index = build_material_dependency_index(
        (scan,),
        field_values={},
        field_token_bindings={},
    )

    assert not index.ok
    assert {item.reason for item in index.occurrences} == {
        "unknown_field_token",
        "content_token_unsupported",
    }
    assert {item.code for item in index.diagnostics} >= {
        "unknown_field_token",
        "content_token_unsupported",
    }


def test_duplicate_content_rules_cannot_produce_a_ready_dependency_index() -> None:
    first = ContentInsertionRule(
        rule_id="route-primary",
        content_id="route",
        anchor_token=content_anchor_token("route"),
    )
    duplicate = ContentInsertionRule(
        rule_id="route-duplicate",
        content_id="route",
        anchor_token=content_anchor_token("route"),
    )
    scan = scan_material_consumer(
        MaterialConsumerRef(MaterialConsumerKind.MAIN_DOCUMENT, "source-docx"),
        [content_anchor_token("route")],
        content_rules=(first, duplicate),
        content_replacement_enabled=True,
    )

    index = build_material_dependency_index(
        (scan,),
        field_values={},
        field_token_bindings={},
    )

    assert not index.ok
    assert "token_duplicate_declaration" in {
        diagnostic.code for diagnostic in index.diagnostics
    }


def test_text_and_image_namespaces_with_same_identifier_do_not_conflict() -> None:
    scan = scan_material_consumer(
        _attachment("item-a"),
        ["{{@text:LOGO1}} {{@img:LOGO1}}"],
        image_rules=(_rule(),),
    )

    index = build_material_dependency_index(
        (scan,),
        field_values={"company_logo_text": "wrong"},
        field_token_bindings={"@text:LOGO1": "company_logo_text"},
        image_rules=(_rule(),),
        image_source_bindings=(_source(),),
    )

    assert index.ok
    assert {item.kind for item in index.occurrences} == {
        MaterialTokenKind.FIELD,
        MaterialTokenKind.IMAGE,
    }
    assert "field_image_token_conflict" not in {
        item.code for item in index.diagnostics
    }
