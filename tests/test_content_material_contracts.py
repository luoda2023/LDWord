from dataclasses import FrozenInstanceError

import pytest

from content_artifact_test_utils import dummy_content_binding
from src.config.content_materials import (
    ContentInsertionRule,
    DocumentFragment,
    FileAssetRef,
    HeadingBlock,
    ImageBlock,
    InlineContent,
    InlineKind,
    ParagraphBlock,
    content_anchor_token,
    normalize_content_resource_path,
)
from src.config.image_materials import (
    ImageAnchorRef,
    ImagePlacementPolicy,
    ImageWatermarkPolicy,
    ResolvedImageInsertionPlan,
    ResolvedImageWatermark,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


def test_content_binding_is_immutable_and_round_trips() -> None:
    binding = dummy_content_binding(label="技术路线")
    assert type(binding).from_dict(binding.to_dict()) == binding
    with pytest.raises(FrozenInstanceError):
        binding.label = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("path", ["../escape.png", "C:/absolute.png", "/root.png"])
def test_content_resource_rejects_paths_outside_artifact(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_content_resource_path(path)


def test_content_insertion_rule_enforces_reserved_canonical_anchor() -> None:
    rule = ContentInsertionRule(
        rule_id="route-rule",
        content_id="technical_route",
        anchor_token="{{@file:technical_route}}",
        occurrence_policy="all",
        heading_policy="relative_to_anchor",
        page_break_policy="preserve_explicit",
    )
    assert rule.anchor_token == content_anchor_token("technical_route")
    assert ContentInsertionRule.from_dict(rule.to_dict()) == rule
    with pytest.raises(ValueError, match="canonical token"):
        ContentInsertionRule("bad", "technical_route", "{{technical_route}}")


def test_document_fragment_is_pure_source_neutral_ir() -> None:
    fragment = DocumentFragment(
        blocks=(
            HeadingBlock(2, (InlineContent(text="技术路线", bold=True),)),
            ParagraphBlock(
                (
                    InlineContent(text="投标人："),
                    InlineContent(kind=InlineKind.FIELD_TOKEN, field_key="@text:company_name"),
                )
            ),
            ImageBlock("sha256/diagram.png", alt_text="路线图", width_px=800, height_px=600),
        )
    )
    assert DocumentFragment.from_dict(fragment.to_dict()) == fragment
    assert set(fragment.to_dict()) == {"blocks"}


def test_image_config_and_resolved_contracts_do_not_mix() -> None:
    configured = ImageWatermarkPolicy(True, "投标人：{{@text:company_name}}")
    assert configured.to_dict()["text_template"] == "投标人：{{@text:company_name}}"
    resolved = ResolvedImageWatermark(
        True,
        "投标人：示例公司",
        SHA_A,
        "Microsoft YaHei|regular",
        SHA_B,
        "diagonal_tiled_v1",
        "image-transform-v1",
    )
    assert "text_template" not in resolved.to_dict()
    with pytest.raises(ValueError, match="resolved_text"):
        ResolvedImageWatermark(
            True, "", SHA_A, "Microsoft YaHei|regular", SHA_B,
            "diagonal_tiled_v1", "image-transform-v1"
        )


def test_strict_anchor_page_policy_freezes_non_movement_invariants() -> None:
    policy = ImagePlacementPolicy(
        mode="fit_remaining_anchor_page",
        max_width_cm=16.0,
        co_location_guard="preceding_nonempty_paragraph",
    )
    with pytest.raises(ValueError, match="forbids"):
        ImagePlacementPolicy(mode="fit_remaining_anchor_page", allow_page_break=True)
    plan = ResolvedImageInsertionPlan(
        job_id="qualification-1",
        image_ref=FileAssetRef(
            "C:/materials/iso.png", "iso.png", "image/png", SHA_A, 1024
        ),
        anchor=ImageAnchorRef(
            "material_token", "anchor-iso-1", "{{资质证书1}}", "guard-iso-1"
        ),
        occurrence_id="tokocc-1",
        watermark=ResolvedImageWatermark.disabled(),
        placement=policy,
        source_role="qualification_certificate",
        sequence=0,
    )
    assert ResolvedImageInsertionPlan.from_dict(plan.to_dict()) == plan
    with pytest.raises(ValueError, match="guard_marker_id"):
        ResolvedImageInsertionPlan(
            job_id="qualification-2",
            image_ref=plan.image_ref,
            anchor=ImageAnchorRef("material_token", "anchor-iso-2", "{{资质证书2}}"),
            occurrence_id="tokocc-2",
            watermark=plan.watermark,
            placement=policy,
            source_role="qualification_certificate",
            sequence=1,
        )
