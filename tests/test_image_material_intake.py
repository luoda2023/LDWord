from __future__ import annotations

from hashlib import sha256

from PIL import Image
import pytest

from src.config.image_materials import (
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
)
from src.config.materials import AssetItem
from src.services.material_assets.intake import (
    ImageMaterialIntakeError,
    build_image_source_items,
)


def _rule(role: str = "qualification") -> ImageMaterialRule:
    return ImageMaterialRule(
        rule_id=f"image:{role}",
        source_role=role,
        anchor_token="{{@img:qualification1}}",
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=10,
        ),
    )


def test_image_intake_builds_deterministic_content_addressed_sources(tmp_path):
    second = tmp_path / "b.png"
    first = tmp_path / "a.png"
    Image.new("RGB", (4, 4), "blue").save(second)
    Image.new("RGB", (4, 4), "red").save(first)
    items = [
        AssetItem(role="attachment", path=str(tmp_path / "ignored.docx")),
        AssetItem(role="qualification", item_id="b", path=str(second)),
        AssetItem(role="qualification", item_id="a", path=str(first)),
    ]

    sources = build_image_source_items(items, [_rule()])

    assert [(item.item_id, item.sequence) for item in sources] == [
        ("a", 0),
        ("b", 1),
    ]
    assert sources[0].image_ref.content_sha256 == sha256(first.read_bytes()).hexdigest()
    assert sources[0].image_ref.media_type == "image/png"


def test_image_intake_rejects_docx_pollution_for_an_owned_image_role(tmp_path):
    polluted = tmp_path / "qualification.docx"
    polluted.write_bytes(b"PK\x03\x04not-an-image")

    with pytest.raises(ImageMaterialIntakeError) as caught:
        build_image_source_items(
            [AssetItem(role="qualification", path=str(polluted))],
            [_rule()],
        )

    assert caught.value.code == "image_extension_not_allowed"


def test_image_intake_rejects_declared_hash_drift(tmp_path):
    image = tmp_path / "qualification.png"
    Image.new("RGB", (4, 4), "red").save(image)

    with pytest.raises(ImageMaterialIntakeError) as caught:
        build_image_source_items(
            [
                AssetItem(
                    role="qualification",
                    path=str(image),
                    content_hash="0" * 64,
                )
            ],
            [_rule()],
        )

    assert caught.value.code == "image_source_hash_mismatch"
