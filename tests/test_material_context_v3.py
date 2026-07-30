import json
from hashlib import sha256
from pathlib import Path

from docx import Document
from PIL import Image
import pytest

from content_artifact_test_utils import compile_content_binding
from src.config.attachment_materials import AttachmentBinding, AttachmentItem
from src.config.content_artifacts import ContentArtifactRef, ContentMaterialBinding
from src.config.content_materials import (
    ContentInsertionRule,
    FileAssetRef,
    content_anchor_token,
)
from src.config.material_context import (
    MaterialExecutionContext,
    MaterialFieldResolution,
)
from src.config.image_materials import (
    ImageMaterialRule,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageWatermarkPolicy,
    ImageWatermarkTextSource,
)
from src.config.materials import AssetInsertionRule, AssetItem
from src.config.scene import SceneWorkspace
from src.services.material_content.artifact_repository import ContentArtifactRepository
from src.services.production_runtime.material_artifacts import (
    _material_manifest_payload,
    material_package_path_map,
    write_material_manifest,
    write_material_package_artifacts,
)
from src.services.production_runtime.material_preflight import (
    image_anchor_diagnostics,
    material_context_asset_roles,
    material_requirement_diagnostics,
)


def _file_ref(path: Path, media_type: str) -> FileAssetRef:
    payload = path.read_bytes()
    return FileAssetRef(
        source_path=str(path),
        original_name=path.name,
        media_type=media_type,
        content_sha256=sha256(payload).hexdigest(),
        byte_size=len(payload),
    )


def test_execution_context_reuses_one_frozen_field_resolution(monkeypatch):
    context = MaterialExecutionContext(
        entity_data={"company_name": "before"},
        field_functions={"company_name": {"function": "current_datetime"}},
    )
    frozen = context.with_frozen_field_resolution(
        MaterialFieldResolution(values={"company_name": "frozen"})
    )

    def _must_not_resolve_again(*_args, **_kwargs):
        raise AssertionError("field functions must not run after Freeze")

    monkeypatch.setattr(
        "src.config.material_context.resolve_field_functions",
        _must_not_resolve_again,
    )

    assert frozen.resolved_entity_data() == {"company_name": "frozen"}
    assert frozen.to_resolve_kwargs()["entity_data"] == {
        "company_name": "frozen"
    }
    cloned = frozen.clone()
    assert cloned.field_values_frozen is True
    assert cloned.frozen_field_values == {"company_name": "frozen"}


def test_frozen_field_payload_requires_explicit_freeze_marker():
    with pytest.raises(ValueError, match="field_values_frozen=True"):
        MaterialExecutionContext(frozen_field_values={"company_name": "x"})

    restored = MaterialExecutionContext.from_payload(
        {
            "frozen_field_values": {"company_name": "x"},
            "field_values_frozen": True,
        }
    )
    assert restored.resolved_entity_data() == {"company_name": "x"}


def _content_binding(markdown: Path, image: Path) -> ContentMaterialBinding:
    artifact_id = sha256(markdown.read_bytes() + image.read_bytes()).hexdigest()
    return ContentMaterialBinding(
        content_id="technical_route",
        label="Technical route",
        artifact_ref=ContentArtifactRef(
            artifact_id=artifact_id,
            manifest_sha256=artifact_id,
        ),
    )


def _content_rule() -> ContentInsertionRule:
    return ContentInsertionRule(
        rule_id="insert-technical-route",
        content_id="technical_route",
        anchor_token=content_anchor_token("technical_route"),
    )


def _attachment_binding(path: Path, *, role: str = "certificate") -> AttachmentBinding:
    return AttachmentBinding(
        role=role,
        items=(
            AttachmentItem(
                item_id=f"{role}-1",
                file_ref=_file_ref(path, "application/pdf"),
            ),
        ),
        required=True,
        min_items=1,
        accepted_media_types=("application/pdf",),
        accepted_extensions=(".pdf",),
    )


def _image_material_rule(
    *,
    rule_id: str = "qualification-rule",
    source_role: str = "qualification",
    anchor_token: str = "{{@img:qualification1}}",
) -> ImageMaterialRule:
    return ImageMaterialRule(
        rule_id=rule_id,
        source_role=source_role,
        anchor_token=anchor_token,
        placement=ImagePlacementPolicy(
            mode=ImagePlacementMode.FIXED_BOX_FLOW,
            fixed_width_cm=15.0,
        ),
    )


def _sources(tmp_path: Path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    markdown = content_dir / "route.md"
    markdown.write_text("# Route\n\n![](images/route.png)\n", encoding="utf-8")
    resource = content_dir / "images" / "route.png"
    resource.parent.mkdir()
    Image.new("RGB", (8, 6), "navy").save(resource)
    attachment = tmp_path / "evidence.pdf"
    attachment.write_bytes(b"%PDF-1.7\nevidence")
    inline_image = tmp_path / "logo.png"
    inline_image.write_bytes(b"inline-image")
    return markdown, resource, attachment, inline_image


def test_v3_context_payload_clone_and_empty_semantics_preserve_typed_domains(
    tmp_path: Path,
):
    markdown, resource, attachment, _inline_image = _sources(tmp_path)
    content = _content_binding(markdown, resource)
    attachment_binding = _attachment_binding(attachment)
    context = MaterialExecutionContext.from_payload(
        {
            "profile_id": "supplier-a",
            "content_bindings": {content.content_id: content.to_dict()},
            "content_rules": [_content_rule().to_dict()],
            "attachment_bindings": {
                attachment_binding.role: attachment_binding.to_dict()
            },
            "image_material_rules": {
                "qualification-rule": _image_material_rule().to_dict()
            },
            "image_watermark_text": "本次工作台水印",
        }
    )
    cloned = context.clone()
    cloned.content_bindings.clear()
    cloned.content_rules.clear()
    cloned.attachment_bindings.clear()
    cloned.image_material_rules.clear()

    assert isinstance(
        context.content_bindings["technical_route"], ContentMaterialBinding
    )
    assert isinstance(context.content_rules[0], ContentInsertionRule)
    assert isinstance(
        context.attachment_bindings["certificate"], AttachmentBinding
    )
    assert isinstance(
        context.image_material_rules["qualification-rule"], ImageMaterialRule
    )
    assert context.image_watermark_text == "本次工作台水印"
    assert cloned.image_watermark_text == "本次工作台水印"
    assert cloned.image_material_rules == {}
    assert context.image_material_rules == {
        "qualification-rule": _image_material_rule()
    }
    assert not context.is_empty()
    assert MaterialExecutionContext(content_bindings={content.content_id: content}).is_empty() is False
    assert MaterialExecutionContext(content_rules=[_content_rule()]).is_empty() is False
    assert MaterialExecutionContext(
        attachment_bindings={"certificate": attachment_binding}
    ).is_empty() is False
    assert MaterialExecutionContext(
        image_material_rules={"qualification-rule": _image_material_rule()}
    ).is_empty() is False
    assert MaterialExecutionContext(image_watermark_text="运行时水印").is_empty() is False


def test_typed_attachment_satisfies_schema_role_but_never_becomes_inline_image(
    tmp_path: Path,
):
    _markdown, _resource, attachment, _inline_image = _sources(tmp_path)
    context = MaterialExecutionContext(
        entity_data={
            "organization": "Example Co",
            "package_name": "Qualification package",
        },
        attachment_bindings={"certificate": _attachment_binding(attachment)},
    )
    scene = SceneWorkspace()
    scene.input_source_profile.material_schema_id = (
        "qualification_archive_assets_v1"
    )
    scene.input_source_profile.failure_policy = "warn"

    diagnostics = material_requirement_diagnostics(scene, context)
    missing_role_diagnostics = [
        item
        for item in diagnostics
        if item["change_type"] == "preflight_missing_material_assets"
    ]

    assert "certificate" in material_context_asset_roles(context)
    assert context.image_rules == []
    assert context.asset_items == []
    assert context.to_resolve_kwargs()["images"] == []
    assert missing_role_diagnostics[0]["missing_asset_roles"] == [
        "business_license"
    ]
    assert not any(
        item["target"] == "certificate"
        and item["change_type"] == "preflight_asset_group_below_min_items"
        for item in diagnostics
    )


def test_workbench_content_closure_diagnostics_reuse_freeze_builder(
    tmp_path: Path,
):
    markdown, resource, _attachment, _inline_image = _sources(tmp_path)
    binding = _content_binding(markdown, resource)
    scene = SceneWorkspace()

    orphan_binding = material_requirement_diagnostics(
        scene,
        MaterialExecutionContext(
            content_bindings={binding.content_id: binding},
        ),
    )
    missing_binding = material_requirement_diagnostics(
        scene,
        MaterialExecutionContext(content_rules=[_content_rule()]),
    )

    assert any(
        item["rule_name"] == "material_freeze"
        and item["diagnostic_code"] == "content_binding_rule_missing"
        for item in orphan_binding
    )
    assert any(
        item["rule_name"] == "material_freeze"
        and item["diagnostic_code"] == "content_rule_binding_missing"
        for item in missing_binding
    )


def test_manifest_and_package_separate_content_image_and_attachment_domains(
    tmp_path: Path,
):
    markdown, resource, attachment, inline_image = _sources(tmp_path)
    content_repository = ContentArtifactRepository(tmp_path / "content_artifacts")
    content = compile_content_binding(markdown, content_repository)
    attachment_binding = _attachment_binding(attachment, role="evidence")
    logo_rule = _image_material_rule(
        source_role="logo",
        anchor_token="{{@img:logo1}}",
    )
    context = MaterialExecutionContext(
        profile_name="Supplier A",
        content_bindings={content.content_id: content},
        content_rules=[_content_rule()],
        attachment_bindings={"evidence": attachment_binding},
        asset_items=[
            AssetItem(
                item_id="logo-1",
                role="logo",
                path=str(inline_image),
                mime_type="image/png",
            )
        ],
        image_material_rules={
            "qualification-rule": logo_rule,
        },
    )
    config = SceneWorkspace()
    artifacts = config.default_delivery_preset().artifacts
    artifacts.material_manifest = True
    artifacts.material_package = True
    source = tmp_path / "target.docx"
    source.write_bytes(b"target")
    payload = _material_manifest_payload(
        input_path=source,
        config=config,
        material_context=context,
        material_diagnostics=[],
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
    )

    assert payload["visibility"] == "local_diagnostic_only"
    assert payload["external_distribution"] == "never"
    domains = payload["material_domains"]
    assert domains["content"]["bindings"][0]["content_id"] == "technical_route"
    assert domains["image"]["items"][0]["role"] == "logo"
    assert domains["image"]["material_rules"] == [
        {
            "contract": "image_material_rule_v1",
            **logo_rule.to_dict(),
        }
    ]
    assert domains["image"]["legacy_insertion_rules"] == []
    assert "rules" not in domains["image"]
    assert domains["attachment"]["items"][0]["role"] == "evidence"
    assert payload["asset_items"] == domains["image"]["items"]
    assert all(item["role"] != "evidence" for item in payload["asset_items"])
    assert all(
        item["asset_role"] != "evidence" for item in payload["image_rules"]
    )
    assert payload["summary"]["image_rule_count"] == 0
    assert payload["summary"]["image_material_rule_count"] == 1
    evidence_role = next(
        item for item in payload["asset_roles"] if item["role"] == "evidence"
    )
    assert evidence_role["material_domain"] == "attachment"
    assert evidence_role["package_subdir"] == "attachments/evidence"

    output_dir = tmp_path / "output"
    manifest_paths = write_material_manifest(
        input_path=source,
        output_dir=output_dir,
        config=config,
        material_context=context,
        material_diagnostics=[],
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
    )
    package_result = write_material_package_artifacts(
        input_path=source,
        output_dir=output_dir,
        config=config,
        material_manifest_paths=manifest_paths,
        material_context=context,
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
        content_artifact_root=content_repository.root,
    )
    package_paths = material_package_path_map(package_result)
    package_manifest = json.loads(
        Path(package_paths["package_manifest"]).read_text(encoding="utf-8")
    )
    category_paths = {
        (item["category"], item["path"])
        for item in package_manifest["files"]
    }

    assert any(
        category == "content_artifact"
        and path.startswith("content_artifacts/sha256/")
        for category, path in category_paths
    )
    assert (
        "attachment",
        "attachments/evidence/evidence.pdf",
    ) in category_paths
    assert ("asset", "assets/logo/logo.png") in category_paths


def test_legacy_context_payload_without_v3_domains_remains_compatible():
    context = MaterialExecutionContext.from_payload(
        {"entity_data": {"company_name": "Legacy Co"}}
    )

    assert context.content_bindings == {}
    assert context.content_rules == []
    assert context.attachment_bindings == {}
    assert context.image_material_rules == {}
    assert context.clone().resolved_entity_data() == {"company_name": "Legacy Co"}
    assert MaterialExecutionContext.from_payload(None).is_empty()


def test_new_image_rules_reject_every_legacy_image_execution_domain(
    tmp_path: Path,
):
    image = tmp_path / "qualification.png"
    image.write_bytes(b"image")
    item = AssetItem(
        item_id="qualification-1",
        role="qualification",
        path=str(image),
        mime_type="image/png",
    )
    new_only = MaterialExecutionContext(
        asset_items=[item],
        image_material_rules={"qualification-rule": _image_material_rule()},
    )
    assert new_only.to_resolve_kwargs()["images"] == []

    with pytest.raises(ValueError, match="material_image_domain_conflict:image_rules"):
        MaterialExecutionContext(
            asset_items=[item],
            image_rules=[
                AssetInsertionRule(
                    rule_id="legacy-qualification",
                    asset_role="qualification",
                    target="{{legacy_qualification}}",
                )
            ],
            image_material_rules={"qualification-rule": _image_material_rule()},
        )

    logo = tmp_path / "logo.png"
    logo.write_bytes(b"logo")
    with pytest.raises(ValueError, match="material_image_domain_conflict:image_rules"):
        MaterialExecutionContext(
            asset_items=[
                item,
                AssetItem(
                    item_id="logo-1",
                    role="logo",
                    path=str(logo),
                    mime_type="image/png",
                ),
            ],
            image_rules=[
                AssetInsertionRule(
                    rule_id="legacy-logo",
                    asset_role="logo",
                    target="{{legacy_logo}}",
                )
            ],
            image_material_rules={"qualification-rule": _image_material_rule()},
        )

    target = tmp_path / "target.docx"
    document = Document()
    document.add_paragraph("No image material token")
    document.save(target)
    scene = SceneWorkspace()
    scene.module_switches["image_insertion"] = True
    assert image_anchor_diagnostics(target, scene, new_only) == []


def test_image_rule_contract_is_reused_for_direct_and_preflight_diagnostics():
    first = _image_material_rule()
    duplicate_role = _image_material_rule(
        rule_id="duplicate-role",
        anchor_token="{{@img:other1}}",
    )
    with pytest.raises(ValueError, match="source_role_duplicate"):
        MaterialExecutionContext(
            image_material_rules={
                first.rule_id: first,
                duplicate_role.rule_id: duplicate_role,
            }
        )

    context = MaterialExecutionContext(
        image_material_rules={first.rule_id: first}
    )
    # Simulate a stale adapter mutating the typed container after construction.
    context.image_material_rules = {"wrong-key": first}
    diagnostics = material_requirement_diagnostics(SceneWorkspace(), context)
    contract = next(
        item
        for item in diagnostics
        if item.get("diagnostic_code") == "image_material_rule_contract_invalid"
    )
    assert contract["material_domain"] == "image"
    assert "image_rule_id_mismatch" in contract["reason"]


def test_free_watermark_requires_workbench_runtime_text_before_execution():
    base_rule = _image_material_rule()
    free_rule = ImageMaterialRule(
        rule_id=base_rule.rule_id,
        source_role=base_rule.source_role,
        anchor_token=base_rule.anchor_token,
        placement=base_rule.placement,
        watermark=ImageWatermarkPolicy(
            enabled=True,
            text_source=ImageWatermarkTextSource.WORKBENCH_FREE_FIELD,
        ),
    )
    context = MaterialExecutionContext(
        image_material_rules={free_rule.rule_id: free_rule}
    )

    missing = material_requirement_diagnostics(SceneWorkspace(), context)
    assert any(
        item.get("diagnostic_code") == "runtime_image_watermark_text_missing"
        for item in missing
    )

    context.image_watermark_text = "本次项目专用"
    ready = material_requirement_diagnostics(SceneWorkspace(), context)
    assert not any(
        item.get("diagnostic_code") == "runtime_image_watermark_text_missing"
        for item in ready
    )


def test_legacy_non_image_asset_stays_attachment_domain(tmp_path: Path):
    attachment = tmp_path / "legacy.xlsx"
    attachment.write_bytes(b"legacy spreadsheet")
    context = MaterialExecutionContext(
        asset_items=[
            AssetItem(
                item_id="legacy-sheet",
                role="budget_sheet",
                path=str(attachment),
                mime_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )
        ]
    )
    payload = _material_manifest_payload(
        input_path=tmp_path / "target.docx",
        config=SceneWorkspace(),
        material_context=context,
        material_diagnostics=[],
        output_paths={},
        compare_paths={},
        report_paths=[],
        intermediate_paths={},
    )

    assert payload["material_domains"]["image"]["items"] == []
    attachment_items = payload["material_domains"]["attachment"]["items"]
    assert attachment_items[0]["item_id"] == "legacy-sheet"
    assert attachment_items[0]["material_domain"] == "attachment"
