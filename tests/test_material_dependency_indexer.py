from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from docx import Document

from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentCardinality,
    AttachmentItem,
    AttachmentProcessingMode,
    AttachmentSourceKind,
)
from src.config.content_artifacts import ContentMaterialBinding
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
from src.config.material_snapshot import MaterialSnapshot
from src.services.material_execution.dependency_indexer import (
    MaterialDependencyIndexer,
    MaterialDependencyIndexRequest,
)
from src.services.material_content.artifact_repository import ContentArtifactRepository
from src.services.material_content.compiler import compile_content_material
from src.shared.engine.material_dependency_index import (
    DependencyDiagnosticSeverity,
)
from src.shared.engine.material_token_router import MaterialTokenKind


def _docx(path: Path, text: str) -> Path:
    document = Document()
    document.add_paragraph(text)
    document.save(path)
    return path


def _ref(path: Path, media_type: str) -> FileAssetRef:
    raw = path.read_bytes()
    return FileAssetRef(
        source_path=str(path.resolve()),
        original_name=path.name,
        media_type=media_type,
        content_sha256=sha256(raw).hexdigest(),
        byte_size=len(raw),
    )


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


def test_indexer_scans_main_content_and_attachment_consumers_once(tmp_path: Path) -> None:
    main = _docx(tmp_path / "main.docx", "{{@text:main_alias}}")
    markdown = tmp_path / "content.md"
    markdown.write_text("{{@text:content_field}}", encoding="utf-8")
    substituted = _docx(
        tmp_path / "substituted.docx",
        "{{@text:attachment_field}} {{@img:LOGO1}}",
    )
    passthrough = _docx(
        tmp_path / "passthrough.docx",
        "{{@text:unknown_passthrough}}",
    )
    image = tmp_path / "logo.png"
    image.write_bytes(b"image")
    content_repository = ContentArtifactRepository(tmp_path / "content-artifacts")
    compiled = compile_content_material(markdown, content_repository)
    assert not compiled.blocked, compiled.findings
    assert compiled.artifact_ref is not None
    substituted_ref = _ref(
        substituted,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    passthrough_ref = _ref(
        passthrough,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    snapshot = MaterialSnapshot(
        field_values={
            "main_field": "Main",
            "content_field": "Content",
            "attachment_field": "Attachment",
        },
        field_token_bindings={
            "@text:main_field": "main_field",
            "@text:main_alias": "main_field",
            "@text:content_field": "content_field",
            "@text:attachment_field": "attachment_field",
        },
        content_bindings=(
            ContentMaterialBinding(
                content_id="route",
                label="Route",
                artifact_ref=compiled.artifact_ref,
            ),
        ),
        content_rules=(
            ContentInsertionRule(
                rule_id="insert-route",
                content_id="route",
                anchor_token=content_anchor_token("route"),
            ),
        ),
        frozen_image_rules=(_rule(),),
        image_source_bindings=(
            ImageSourceBinding(
                role="logo",
                item_id="logo-1",
                sequence=0,
                file_ref=_ref(image, "image/png"),
            ),
        ),
        attachment_bindings=(
            AttachmentBinding(
                role="substituted",
                source_kind=AttachmentSourceKind.FILE_SET,
                processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
                cardinality=AttachmentCardinality.MULTIPLE,
                items=(AttachmentItem("substituted-1", substituted_ref),),
                max_items=None,
            ),
            AttachmentBinding(
                role="passthrough",
                source_kind=AttachmentSourceKind.FILE_SET,
                processing_mode=AttachmentProcessingMode.PASSTHROUGH,
                cardinality=AttachmentCardinality.MULTIPLE,
                items=(AttachmentItem("passthrough-1", passthrough_ref),),
                max_items=None,
            ),
        ),
        material_schema_id="test",
        material_schema_version="1",
        rule_versions={"freeze": "1"},
    )

    index = MaterialDependencyIndexer(
        content_repository=content_repository,
    ).build(
        MaterialDependencyIndexRequest(
            snapshot=snapshot,
            main_document_path=str(main),
        )
    )

    assert index.ok
    assert {item.consumer.consumer_id for item in index.occurrences} == {
        "main:source-docx",
        "content:route",
        "attachment:substituted:substituted-1",
        "attachment:passthrough:passthrough-1",
    }
    assert len(
        index.occurrences_for_resource(MaterialTokenKind.FIELD, "main_field")
    ) == 1
    assert len(
        index.occurrences_for_resource(MaterialTokenKind.FIELD, "content_field")
    ) == 1
    assert len(
        index.occurrences_for_resource(MaterialTokenKind.IMAGE, "logo")
    ) == 1
    passthrough_occurrence = next(
        item
        for item in index.occurrences
        if item.consumer.owner_id == "passthrough"
    )
    assert passthrough_occurrence.replaceable is False
    assert any(
        item.code == "unknown_field_token"
        and item.severity is DependencyDiagnosticSeverity.WARNING
        for item in index.diagnostics
    )
    assert index.declaration_revision
    assert set(index.source_revisions) == {
        "main:source-docx",
        "content:route",
        "attachment:substituted:substituted-1",
        "attachment:passthrough:passthrough-1",
    }
