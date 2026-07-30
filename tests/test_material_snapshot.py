from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import inspect

import pytest

from src.config.attachment_materials import AttachmentBinding, AttachmentItem
from src.config.content_artifacts import ContentArtifactRef, ContentMaterialBinding
from src.config.content_materials import (
    ContentInsertionRule,
    FileAssetRef,
    content_anchor_token,
)
from src.config.image_materials import (
    DeliveryVariantPlan,
    FrozenImageMaterialRule,
    ImageAnchorOrigin,
    ImageAnchorRef,
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageSourceBinding,
    ResolvedImageInsertionPlan,
    ResolvedImageWatermark,
)
from src.config.material_snapshot import (
    MATERIAL_SNAPSHOT_CONTRACT_VERSION,
    MaterialSnapshot,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _watermark(text: str = "示例水印123") -> ResolvedImageWatermark:
    return ResolvedImageWatermark(
        enabled=True,
        resolved_text=text,
        resolved_text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        resolved_font_identity="test-font",
        resolved_font_sha256=HASH_C,
        style_version="diagonal_tiled_v1",
        transform_contract="image-transform-v1",
    )


def _image_ref(digest: str = HASH_A) -> FileAssetRef:
    return FileAssetRef(
        source_path="assets/qualification/iso.png",
        original_name="iso.png",
        media_type="image/png",
        content_sha256=digest,
        byte_size=2048,
    )


def _frozen_rule(*, width: float = 15.0, watermark=None):
    return FrozenImageMaterialRule(
        rule_id="qualification-rule",
        source_role="qualification",
        anchor_token="{{@img:资质证书1}}",
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=width,
        ),
        watermark=watermark or _watermark(),
    )


def _source(*, digest: str = HASH_A):
    return ImageSourceBinding(
        role="qualification",
        item_id="qualification-1",
        sequence=0,
        file_ref=_image_ref(digest),
    )


def _content_binding() -> ContentMaterialBinding:
    return ContentMaterialBinding(
        content_id="technical_route",
        label="技术路线",
        artifact_ref=ContentArtifactRef(
            artifact_id=HASH_A,
            manifest_sha256=HASH_B,
        ),
    )


def _attachment_binding(path: str = "attachments/a.pdf") -> AttachmentBinding:
    return AttachmentBinding(
        role="supporting",
        items=(
            AttachmentItem(
                item_id="supporting-1",
                file_ref=FileAssetRef(
                    source_path=path,
                    original_name="a.pdf",
                    media_type="application/pdf",
                    content_sha256=HASH_B,
                    byte_size=256,
                ),
            ),
        ),
    )


def _snapshot(**overrides) -> MaterialSnapshot:
    binding = _content_binding()
    values = {
        "field_values": {"company": "示例公司", "nested": {"tags": ["A", "B"]}},
        "field_token_bindings": {
            "@text:company": "company",
            "@text:企业名称": "company",
        },
        "content_bindings": (binding,),
        "content_rules": (
            ContentInsertionRule(
                rule_id="technical-route-rule",
                content_id=binding.content_id,
                anchor_token=content_anchor_token(binding.content_id),
            ),
        ),
        "frozen_image_rules": (_frozen_rule(),),
        "image_source_bindings": (_source(),),
        "attachment_bindings": (_attachment_binding(),),
        "material_schema_id": "bid-materials",
        "material_schema_version": "3",
        "rule_versions": {"content": "content-ir-v2", "image": "image-v1"},
        "source_revisions": {
            "image:qualification:qualification-1": HASH_A,
        },
    }
    values.update(overrides)
    return MaterialSnapshot(**values)


def _resolved_plan(job_id: str = "qualification-job"):
    return ResolvedImageInsertionPlan(
        job_id=job_id,
        image_ref=_image_ref(),
        anchor=ImageAnchorRef(
            origin=ImageAnchorOrigin.MATERIAL_TOKEN,
            stable_marker_id="image-anchor-1",
            source_token="{{@img:资质证书1}}",
        ),
        occurrence_id="qualification:1",
        watermark=_watermark(),
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=15.0,
        ),
        source_role="qualification",
        sequence=0,
    )


def test_snapshot_is_deterministic_and_has_no_delivery_variant_or_plan_fields():
    first = _snapshot()
    second = _snapshot()

    assert first.snapshot_id == second.snapshot_id
    assert first.snapshot_id == sha256(first.canonical_json().encode()).hexdigest()
    assert first.contract_version == MATERIAL_SNAPSHOT_CONTRACT_VERSION
    parameters = inspect.signature(MaterialSnapshot).parameters
    assert "variant_id" not in parameters
    assert "variant_version" not in parameters
    assert "resolved_image_plans" not in parameters


def test_snapshot_deep_freezes_open_values_and_strong_image_inputs():
    fields = {"nested": {"items": ["original"]}}
    snapshot = _snapshot(
        field_values=fields,
        field_token_bindings={"@text:nested": "nested"},
        attachment_bindings=(_attachment_binding(),),
    )
    fields["nested"]["items"].append("mutated")

    assert snapshot.field_values["nested"]["items"] == ("original",)
    assert snapshot.attachment_bindings[0].items[0].file_ref.source_path == (
        "attachments/a.pdf"
    )
    assert isinstance(snapshot.attachment_bindings[0], AttachmentBinding)
    assert isinstance(snapshot.frozen_image_rules[0], FrozenImageMaterialRule)
    assert isinstance(snapshot.image_source_bindings[0], ImageSourceBinding)
    with pytest.raises(TypeError):
        snapshot.field_values["new"] = "value"
    with pytest.raises(FrozenInstanceError):
        snapshot.snapshot_id = HASH_B


def test_snapshot_round_trip_preserves_resolved_policy_and_identity():
    snapshot = _snapshot()
    restored = MaterialSnapshot.from_dict(snapshot.to_dict())

    assert restored == snapshot
    assert restored.snapshot_id == snapshot.snapshot_id
    assert restored.frozen_image_rules[0].watermark.resolved_text == "示例水印123"
    assert "text_template" not in restored.canonical_json()


def test_old_snapshot_contract_is_rejected_without_migration():
    current = _snapshot()
    payload = current.to_dict()
    payload["contract_version"] = "material-snapshot-v2"
    with pytest.raises(ValueError, match="unsupported material snapshot contract"):
        MaterialSnapshot.from_dict(payload)


def test_snapshot_rejects_token_evidence_that_conflicts_with_namespace_contract():
    payload = _snapshot().to_dict()
    file_evidence = next(
        item for item in payload["token_evidence"] if item["token"].startswith("{{@file:")
    )
    file_evidence["kind"] = "field"

    with pytest.raises(ValueError, match="derives kind=content"):
        MaterialSnapshot.from_dict(payload)


def test_snapshot_rejects_unfrozen_image_rule_type():
    unfrozen = ImageMaterialRule(
        rule_id="qualification-rule",
        source_role="qualification",
        anchor_token="{{@img:资质证书1}}",
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=15,
        ),
    )
    with pytest.raises(TypeError, match="FrozenImageMaterialRule"):
        _snapshot(frozen_image_rules=(unfrozen,))


def test_snapshot_rejects_multiple_rules_for_one_content_binding():
    binding = _content_binding()
    first = ContentInsertionRule(
        rule_id="technical-route-rule",
        content_id=binding.content_id,
        anchor_token=content_anchor_token(binding.content_id),
    )
    duplicate = replace(first, rule_id="technical-route-rule-duplicate")

    with pytest.raises(ValueError, match="binding_rule_cardinality_invalid"):
        _snapshot(content_rules=(first, duplicate))


def test_rule_field_font_and_source_identity_change_snapshot_id():
    base = _snapshot()
    changed_field = _snapshot(field_values={"company": "另一家公司"})
    changed_rule = _snapshot(frozen_image_rules=(_frozen_rule(width=12),))
    changed_font = _snapshot(
        frozen_image_rules=(
            _frozen_rule(
                watermark=replace(_watermark(), resolved_font_identity="other-font")
            ),
        )
    )
    changed_source = _snapshot(
        image_source_bindings=(_source(digest=HASH_B),),
        source_revisions={"image:qualification:qualification-1": HASH_B},
    )

    assert len(
        {
            base.snapshot_id,
            changed_field.snapshot_id,
            changed_rule.snapshot_id,
            changed_font.snapshot_id,
            changed_source.snapshot_id,
        }
    ) == 5


def test_delivery_variant_plan_hashes_variant_staged_docx_and_jobs_one_way():
    snapshot = _snapshot()
    plan = DeliveryVariantPlan(
        snapshot_id=snapshot.snapshot_id,
        variant_id="submission",
        variant_version="1",
        staged_docx_sha256=HASH_B,
        staged_docx_byte_size=4096,
        resolved_image_plans=(_resolved_plan(),),
    )

    assert DeliveryVariantPlan.from_dict(plan.to_dict()) == plan
    assert plan.plan_id != replace(plan, plan_id="", variant_id="review").plan_id
    assert plan.plan_id != replace(
        plan, plan_id="", staged_docx_sha256=HASH_C
    ).plan_id
    assert plan.snapshot_id == snapshot.snapshot_id
    assert "delivery" not in snapshot.canonical_json()

    with pytest.raises(ValueError, match="job_id.*unique"):
        DeliveryVariantPlan(
            snapshot_id=snapshot.snapshot_id,
            variant_id="submission",
            variant_version="1",
            staged_docx_sha256=HASH_B,
            staged_docx_byte_size=4096,
            resolved_image_plans=(_resolved_plan(), _resolved_plan()),
        )


def test_tampered_snapshot_and_delivery_plan_ids_are_rejected():
    snapshot_payload = _snapshot().to_dict()
    snapshot_payload["material_schema_version"] = "4"
    with pytest.raises(ValueError, match="snapshot_id does not match"):
        MaterialSnapshot.from_dict(snapshot_payload)

    plan = DeliveryVariantPlan(
        snapshot_id=_snapshot().snapshot_id,
        variant_id="submission",
        variant_version="1",
        staged_docx_sha256=HASH_B,
        staged_docx_byte_size=4096,
    )
    payload = plan.to_dict()
    payload["variant_version"] = "2"
    with pytest.raises(ValueError, match="plan_id does not match"):
        DeliveryVariantPlan.from_dict(payload)
