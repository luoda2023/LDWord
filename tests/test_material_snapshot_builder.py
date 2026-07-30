from dataclasses import replace
from hashlib import sha256
import inspect
from pathlib import Path

from PIL import Image
import pytest

from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentCardinality,
    AttachmentItem,
    AttachmentSourceKind,
)
from src.config.content_artifacts import ContentMaterialBinding
from src.config.content_materials import (
    ContentInsertionRule,
    FileAssetRef,
    content_anchor_token,
)
from src.config.entity import EntityProfile
from src.config.image_materials import (
    FrozenImageMaterialRule,
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageSourceBinding,
    ResolvedImageWatermark,
)
from src.services.material_execution.material_snapshot_builder import (
    MaterialSnapshotBuildError,
    MaterialSnapshotBuildRequest,
    MaterialSnapshotBuilder,
    build_material_snapshot,
)
from src.services.material_content.artifact_repository import ContentArtifactRepository
from src.services.material_content.compiler import compile_content_material
from src.shared.engine.material_timeline import (
    default_timeline_segment,
    timeline_owned_field_keys,
)
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    MaterialTokenProducer,
)


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _file_ref(path: Path, media_type: str) -> FileAssetRef:
    return FileAssetRef(
        source_path=str(path),
        original_name=path.name,
        media_type=media_type,
        content_sha256=_hash(path),
        byte_size=path.stat().st_size,
    )


def _watermark(text: str = "示例水印") -> ResolvedImageWatermark:
    return ResolvedImageWatermark(
        enabled=True,
        resolved_text=text,
        resolved_text_sha256=sha256(text.encode()).hexdigest(),
        resolved_font_identity="test-font",
        resolved_font_sha256="f" * 64,
        style_version="diagonal_tiled_v1",
        transform_contract="image-transform-v1",
    )


def _frozen_rule(*, role="qualification", required=True):
    return FrozenImageMaterialRule(
        rule_id=f"{role}-rule",
        source_role=role,
        anchor_token=f"{{{{@img:{role}1}}}}",
        required=required,
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=10,
        ),
        watermark=_watermark(),
    )


def _image_binding(path: Path, *, role="qualification", item_id="iso-1"):
    return ImageSourceBinding(
        role=role,
        item_id=item_id,
        sequence=0,
        file_ref=_file_ref(path, "image/png"),
    )


def _content_binding(
    markdown: Path,
    repository: ContentArtifactRepository,
) -> ContentMaterialBinding:
    result = compile_content_material(markdown, repository)
    assert not result.blocked, result.findings
    assert result.artifact_ref is not None
    return ContentMaterialBinding(
        content_id="technical_route",
        label="技术路线",
        artifact_ref=result.artifact_ref,
    )


def _content_rule(content_id="technical_route"):
    return ContentInsertionRule(
        rule_id=f"insert-{content_id}",
        content_id=content_id,
        anchor_token=content_anchor_token(content_id),
    )


def _attachment_binding(path: Path):
    return AttachmentBinding(
        role="supporting",
        source_kind=AttachmentSourceKind.FILE_SET,
        cardinality=AttachmentCardinality.MULTIPLE,
        items=(
            AttachmentItem(
                item_id="supporting-1",
                file_ref=_file_ref(path, "application/pdf"),
            ),
        ),
        required=True,
        min_items=1,
        accepted_media_types=("application/pdf",),
        accepted_extensions=(".pdf",),
    )


def _fixture(tmp_path: Path):
    content_dir = tmp_path / "content"
    content_dir.mkdir(exist_ok=True)
    markdown = content_dir / "route.md"
    markdown.write_text("# Route\n\n![](images/route.png)\n", encoding="utf-8")
    resource = content_dir / "images" / "route.png"
    resource.parent.mkdir(exist_ok=True)
    Image.new("RGB", (8, 8), "red").save(resource)
    attachment = tmp_path / "attachments" / "evidence.pdf"
    attachment.parent.mkdir(exist_ok=True)
    attachment.write_bytes(b"%PDF-1.7\nattachment")
    image = tmp_path / "images" / "iso.png"
    image.parent.mkdir(exist_ok=True)
    Image.new("RGB", (16, 12), "blue").save(image)

    repository = ContentArtifactRepository(tmp_path / "content-artifacts")
    content = _content_binding(markdown, repository)
    profile = EntityProfile(
        profile_id="supplier-a",
        profile_name="Supplier A",
        content_bindings={content.content_id: content},
        content_rules=[_content_rule()],
        attachment_bindings={"supporting": _attachment_binding(attachment)},
    )
    return profile, markdown, resource, attachment, image


def _request(tmp_path: Path, **overrides):
    profile, _markdown, _resource, _attachment, image = _fixture(tmp_path)
    values = {
        "profile": profile,
        "frozen_field_values": {"company_name": "Supplier A"},
        "material_schema_id": "bid-materials",
        "material_schema_version": "3",
        "rule_versions": {"content": "content-ir-v2", "image": "image-v1"},
        "frozen_image_rules": (_frozen_rule(),),
        "image_source_bindings": (_image_binding(image),),
        "source_root": tmp_path,
        "content_artifact_root": tmp_path / "content-artifacts",
    }
    values.update(overrides)
    return MaterialSnapshotBuildRequest(**values)


def test_build_is_deterministic_and_normalizes_all_source_paths(tmp_path):
    request = _request(tmp_path)
    first = build_material_snapshot(request).require_snapshot()
    second = MaterialSnapshotBuilder().build_or_raise(request)

    assert first.snapshot_id == second.snapshot_id
    assert first.content_bindings[0].artifact_ref.artifact_id
    assert Path(first.image_source_bindings[0].file_ref.source_path).is_absolute()
    assert first.source_revisions["image:qualification:iso-1"] == _hash(
        Path(first.image_source_bindings[0].file_ref.source_path)
    )


def test_snapshot_builder_has_no_variant_or_resolved_plan_inputs():
    parameters = inspect.signature(MaterialSnapshotBuildRequest).parameters
    assert "variant_id" not in parameters
    assert "variant_version" not in parameters
    assert "resolved_image_plans" not in parameters
    assert "image_config" not in parameters


def test_all_domains_remain_isolated_and_deep_frozen(tmp_path):
    request = _request(tmp_path)
    snapshot = build_material_snapshot(request).require_snapshot()
    request.profile.content_rules.clear()
    request.profile.attachment_bindings.clear()

    assert len(snapshot.content_rules) == 1
    assert {binding.role for binding in snapshot.attachment_bindings} == {
        "supporting"
    }
    assert snapshot.image_source_bindings[0].file_ref.original_name == "iso.png"
    assert "evidence.pdf" not in str(snapshot.image_source_bindings[0].to_dict())
    assert set(snapshot.source_revisions) >= {
        "attachment:supporting:supporting-1",
        "image:qualification:iso-1",
    }


def test_snapshot_evidence_records_external_namespace_engine_kind_and_producer(
    tmp_path,
):
    request = _request(tmp_path)
    request.profile.field_functions = {"generated_code": {"type": "constant"}}
    request.profile.timeline_plans = {
        "phase_1": default_timeline_segment(
            1,
            node_count=1,
            start_value="2026-07-01",
            end_value="2026-07-02",
        )
    }
    time_field = timeline_owned_field_keys(
        request.profile.timeline_plans,
        include_inactive=True,
    )[0]
    request = replace(
        request,
        frozen_field_values={
            **request.frozen_field_values,
            "generated_code": "AUTO-001",
            time_field: "2026-07-01",
        },
    )

    snapshot = build_material_snapshot(request).require_snapshot()
    evidence = {item.token: item for item in snapshot.token_evidence}

    assert evidence["{{@text:company_name}}"].kind is MaterialTokenKind.FIELD
    assert evidence["{{@text:company_name}}"].producer is MaterialTokenProducer.MANUAL
    assert evidence["{{@text:generated_code}}"].producer is MaterialTokenProducer.FUNCTION
    assert evidence[f"{{{{@time:{time_field}}}}}"].producer is MaterialTokenProducer.TIMELINE
    assert evidence["{{@file:technical_route}}"].producer is MaterialTokenProducer.FILE_BINDING
    assert evidence["{{@img:qualification1}}"].producer is MaterialTokenProducer.IMAGE_BINDING
    assert evidence["{{@attach:supporting}}"].producer is MaterialTokenProducer.ATTACHMENT_BINDING


def test_field_content_attachment_and_image_changes_change_intake_id(tmp_path):
    request = _request(tmp_path)
    base = build_material_snapshot(request).require_snapshot()
    changed_field = build_material_snapshot(
        replace(request, frozen_field_values={"company_name": "Supplier B"})
    ).require_snapshot()

    markdown = tmp_path / "content" / "route.md"
    _resource = tmp_path / "content" / "images" / "route.png"
    attachment = tmp_path / "attachments" / "evidence.pdf"
    image = tmp_path / "images" / "iso.png"
    markdown.write_text("# Changed\n", encoding="utf-8")
    attachment.write_bytes(b"%PDF changed")
    Image.new("RGB", (16, 12), "green").save(image)
    content = _content_binding(
        markdown,
        ContentArtifactRepository(request.content_artifact_root),
    )
    changed_profile = EntityProfile(
        content_bindings={content.content_id: content},
        content_rules=[_content_rule()],
        attachment_bindings={"supporting": _attachment_binding(attachment)},
    )
    changed_sources = (_image_binding(image),)
    changed_all = build_material_snapshot(
        replace(
            request,
            profile=changed_profile,
            image_source_bindings=changed_sources,
        )
    ).require_snapshot()

    assert len({base.snapshot_id, changed_field.snapshot_id, changed_all.snapshot_id}) == 3


def test_source_outside_root_blocks_atomic_result(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF outside")
    profile = EntityProfile(
        attachment_bindings={"supporting": _attachment_binding(outside)}
    )
    result = build_material_snapshot(
        MaterialSnapshotBuildRequest(
            profile=profile,
            frozen_field_values={},
            material_schema_id="schema",
            material_schema_version="1",
            rule_versions={"freeze": "v1"},
            source_root=inside,
        )
    )

    assert result.snapshot is None
    assert "source_path_escape" in {item.code for item in result.diagnostics}
    with pytest.raises(MaterialSnapshotBuildError):
        result.require_snapshot()


def test_unfrozen_policy_is_rejected_at_request_boundary(tmp_path):
    bad_rule = ImageMaterialRule(
        rule_id="qualification-rule",
        source_role="qualification",
        anchor_token="{{@img:qualification1}}",
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=10,
        ),
    )
    with pytest.raises(TypeError, match="FrozenImageMaterialRule"):
        _request(tmp_path, frozen_image_rules=(bad_rule,))


def test_fake_png_bytes_and_stale_image_hash_are_blocked(tmp_path):
    request = _request(tmp_path)
    image = tmp_path / "images" / "iso.png"
    original = request.image_source_bindings[0]
    image.write_bytes(b"PK fake docx pollution")
    fake_ref = _file_ref(image, "image/png")
    fake_result = build_material_snapshot(
        replace(request, image_source_bindings=(replace(original, file_ref=fake_ref),))
    )
    stale_result = build_material_snapshot(request)

    assert "image_payload_invalid" in {item.code for item in fake_result.diagnostics}
    assert "source_size_mismatch" in {item.code for item in stale_result.diagnostics}


def test_empty_profile_and_no_image_policy_builds_valid_snapshot(tmp_path):
    snapshot = build_material_snapshot(
        MaterialSnapshotBuildRequest(
            profile=EntityProfile(),
            frozen_field_values={},
            material_schema_id="empty",
            material_schema_version="1",
            rule_versions={"freeze": "v1"},
            source_root=tmp_path,
        )
    ).require_snapshot()
    assert snapshot.frozen_image_rules == ()
    assert snapshot.image_source_bindings == ()
    assert snapshot.source_revisions == {}


def test_field_alias_chains_are_resolved_once_at_snapshot_boundary(tmp_path):
    request = _request(tmp_path)
    request.profile.field_aliases = {
        "企业名称": "company_name",
        "投标人名称": "企业名称",
        "{{供应商名称}}": "${投标人名称}",
    }

    snapshot = build_material_snapshot(request).require_snapshot()

    assert snapshot.field_token_bindings == {
        "@text:company_name": "company_name",
        "@text:企业名称": "company_name",
        "@text:投标人名称": "company_name",
        "@text:供应商名称": "company_name",
    }


@pytest.mark.parametrize(
    ("aliases", "expected_code"),
    [
        ({"A": "B", "B": "A"}, "field_alias_cycle"),
        ({"企业名称": "missing_field"}, "field_alias_target_missing"),
        ({"company_name": "other", "other": "company_name"}, "field_alias_cycle"),
    ],
)
def test_invalid_field_alias_graph_blocks_snapshot(tmp_path, aliases, expected_code):
    request = _request(tmp_path)
    request.profile.field_aliases = aliases

    result = build_material_snapshot(request)

    assert result.snapshot is None
    assert expected_code in {item.code for item in result.diagnostics}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object()])
def test_non_json_field_values_block_snapshot(tmp_path, bad):
    result = build_material_snapshot(_request(tmp_path, frozen_field_values={"bad": bad}))
    assert result.snapshot is None
    assert {item.code for item in result.diagnostics} & {
        "non_finite_value",
        "unsupported_value_type",
    }


def test_content_binding_must_have_rule_and_image_rule_must_have_required_source(
    tmp_path,
):
    request = _request(tmp_path)
    request.profile.content_rules.clear()
    result = build_material_snapshot(
        replace(request, image_source_bindings=())
    )
    codes = {item.code for item in result.diagnostics}
    assert {"content_binding_rule_missing", "required_image_source_missing"} <= codes


def test_duplicate_content_rules_fail_closed_at_freeze_boundary(tmp_path):
    request = _request(tmp_path)
    duplicate = replace(
        request.profile.content_rules[0],
        rule_id="insert-technical-route-duplicate",
    )
    request.profile.content_rules.append(duplicate)

    result = build_material_snapshot(request)

    assert result.snapshot is None
    assert {
        "binding_rule_cardinality_invalid",
        "duplicate_content_rules",
    } <= {item.code for item in result.diagnostics}
    with pytest.raises(MaterialSnapshotBuildError):
        result.require_snapshot()


def test_duplicate_frozen_rules_are_reported_without_snapshot(tmp_path):
    request = _request(tmp_path)
    result = build_material_snapshot(
        replace(request, frozen_image_rules=(request.frozen_image_rules[0],) * 2)
    )
    assert result.snapshot is None
    assert {
        "image_rule_id_duplicate",
        "image_rule_role_duplicate",
        "image_rule_anchor_duplicate",
    } <= {item.code for item in result.diagnostics}
