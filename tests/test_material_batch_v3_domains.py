from __future__ import annotations

import json
from pathlib import Path

from src.config.attachment_materials import AttachmentBinding
from src.config.content_materials import (
    ContentInsertionRule,
    content_anchor_token,
)
from content_artifact_test_utils import dummy_content_binding
from src.config.entity import EntityArchive, EntityProfile
from src.config.image_materials import (
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
)
from src.config.material_batch import build_material_batch_items
from src.config.material_context import MaterialExecutionContext
from src.services.production_runtime.material_assembly_runtime import (
    material_assembly_is_active,
)
from src.ui.panels.assets.batch_import import _load_batch_profiles_from_path


def _content(content_id: str):
    return dummy_content_binding(content_id, label=content_id)


def _rule(content_id: str) -> ContentInsertionRule:
    return ContentInsertionRule(
        rule_id=f"content:{content_id}",
        content_id=content_id,
        anchor_token=content_anchor_token(content_id),
    )


def _image_rule(rule_id: str, role: str, token: str, width: float) -> ImageMaterialRule:
    return ImageMaterialRule(
        rule_id=rule_id,
        source_role=role,
        anchor_token=token,
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=width,
        ),
    )


def test_batch_context_keeps_profile_content_and_attachments_separate_from_images():
    shared_content = _content("shared")
    profile_content = _content("profile")
    shared_attachment = AttachmentBinding(role="shared_attachment")
    profile_attachment = AttachmentBinding(role="profile_attachment")
    base = MaterialExecutionContext(
        content_bindings={"shared": shared_content},
        content_rules=[_rule("shared")],
        attachment_bindings={"shared_attachment": shared_attachment},
    )
    profile = EntityProfile(
        profile_id="p1",
        content_bindings={"profile": profile_content},
        content_rules=[_rule("profile")],
        attachment_bindings={"profile_attachment": profile_attachment},
    )

    item = build_material_batch_items(
        EntityArchive(archive_id="a", profiles=[profile]),
        base_context=base,
    )[0]

    assert set(item.context.content_bindings) == {"shared", "profile"}
    assert {rule.rule_id for rule in item.context.content_rules} == {
        "content:shared",
        "content:profile",
    }
    assert set(item.context.attachment_bindings) == {
        "shared_attachment",
        "profile_attachment",
    }
    assert item.context.asset_items == []
    assert item.context.to_resolve_kwargs()["images"] == []


def test_batch_merges_image_material_rules_by_id_without_legacy_execution():
    shared_alpha = _image_rule("alpha", "alpha-role", "{{@img:alpha1}}", 10.0)
    shared_override = _image_rule(
        "override", "shared-role", "{{@img:shared1}}", 11.0
    )
    profile_override = _image_rule(
        "override", "profile-role", "{{@img:profile1}}", 12.0
    )
    profile_zulu = _image_rule("zulu", "zulu-role", "{{@img:zulu1}}", 13.0)
    base = MaterialExecutionContext(
        image_watermark_text="批次运行时水印",
        image_material_rules={
            "override": shared_override,
            "alpha": shared_alpha,
        }
    )
    profile = EntityProfile(
        profile_id="p1",
        image_material_rules={
            "zulu": profile_zulu,
            "override": profile_override,
        },
    )

    item = build_material_batch_items(
        EntityArchive(archive_id="a", profiles=[profile]),
        base_context=base,
    )[0]

    assert list(item.context.image_material_rules) == ["alpha", "override", "zulu"]
    assert item.context.image_material_rules["override"] == profile_override
    assert item.context.image_material_rules["alpha"] == shared_alpha
    assert item.context.image_material_rules["zulu"] == profile_zulu
    assert item.context.image_material_rules["alpha"] is not shared_alpha
    assert item.context.image_material_rules["zulu"] is not profile_zulu
    assert item.context.image_rules == []
    assert item.context.image_watermark_text == "批次运行时水印"
    assert item.context.to_resolve_kwargs()["images"] == []


def test_json_batch_alias_rules_remain_active_for_every_unopened_profile(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "logo.png"
    image_path.write_bytes(b"image-source")
    raw_rule = _image_rule(
        "image:logo",
        "logo",
        "{{@img:LOGO1}}",
        6.0,
    ).to_dict()
    raw_rule["source_role"] = "品牌标志"
    source = tmp_path / "profiles.json"
    source.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "profile_id": profile_id,
                        "profile_name": profile_id,
                        "asset_paths": {"LOGO": str(image_path)},
                        "image_material_rules": {"image:logo": raw_rule},
                    }
                    for profile_id in ("first", "second")
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profiles = _load_batch_profiles_from_path(source)
    items = build_material_batch_items(EntityArchive(archive_id="a", profiles=profiles))

    assert [item.profile_id for item in items] == ["first", "second"]
    for item in items:
        assert item.context.image_material_rules["image:logo"].source_role == "logo"
        assert item.context.asset_items[0].role == "logo"
        assert material_assembly_is_active(item.context) is True
