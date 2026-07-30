from __future__ import annotations

from types import SimpleNamespace

from src.config.attachment_materials import (
    AttachmentBinding,
    AttachmentCardinality,
    AttachmentItem,
    AttachmentProcessingMode,
    AttachmentSourceKind,
)
from src.config.content_materials import FileAssetRef
from src.config.image_materials import ImageOccurrencePolicy
from src.shared.engine.material_dependency_index import (
    MaterialConsumerKind,
    MaterialConsumerRef,
    build_material_dependency_index,
    scan_material_consumer,
)
from src.shared.engine.material_dependency_projection import (
    project_attachment_binding,
    project_material_dependency_usage,
)


def _ref(name: str, digest: str) -> FileAssetRef:
    return FileAssetRef(
        source_path=f"C:/sources/{name}",
        original_name=name,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
            if name.endswith(".docx")
            else "application/pdf"
        ),
        content_sha256=digest * 64,
        byte_size=10,
    )


def test_dependency_projection_links_resources_without_changing_attachment_tree() -> None:
    rule = SimpleNamespace(
        rule_id="logo-rule",
        source_role="logo",
        anchor_token="{{@img:LOGO1}}",
        required=True,
        occurrence_policy=ImageOccurrencePolicy.EXACTLY_ONE,
    )
    main = MaterialConsumerRef(MaterialConsumerKind.MAIN_DOCUMENT, "source-docx")
    first = MaterialConsumerRef(
        MaterialConsumerKind.ATTACHMENT_ITEM,
        "evidence",
        "item-a",
    )
    second = MaterialConsumerRef(
        MaterialConsumerKind.ATTACHMENT_ITEM,
        "evidence",
        "item-b",
    )
    scans = (
        scan_material_consumer(
            main,
            ("{{@text:company}}",),
            image_rules=(rule,),
        ),
        scan_material_consumer(
            first,
            ("{{@text:company}} {{@img:LOGO1}}",),
            image_rules=(rule,),
        ),
        scan_material_consumer(second, ("no tokens",), image_rules=(rule,)),
    )
    index = build_material_dependency_index(
        scans,
        field_values={"company": "Example"},
        field_token_bindings={"@text:company": "company"},
        image_rules=(rule,),
        image_source_bindings=(SimpleNamespace(role="logo"),),
    )
    binding = AttachmentBinding(
        role="evidence",
        source_kind=AttachmentSourceKind.DIRECTORY_PACKAGE,
        source_path="C:/sources",
        recursive=True,
        processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
        cardinality=AttachmentCardinality.MULTIPLE,
        items=(
            AttachmentItem(
                "item-a",
                _ref("proof.docx", "a"),
                relative_path="part-a/proof.docx",
            ),
            AttachmentItem(
                "item-b",
                _ref("root.pdf", "b"),
                relative_path="root.pdf",
            ),
        ),
        max_items=None,
    )

    usage = project_material_dependency_usage(index)
    attachment = project_attachment_binding(binding, index)
    company = next(item for item in usage["fields"] if item["resource_key"] == "company")
    logo = next(item for item in usage["images"] if item["resource_key"] == "logo")

    assert company["main_consumer_count"] == 1
    assert company["attachment_consumer_count"] == 1
    assert logo["attachment_consumer_count"] == 1
    assert attachment["file_count"] == 2
    assert attachment["field_occurrence_count"] == 1
    assert attachment["image_occurrence_count"] == 1
    assert attachment["tree"] == [
        {
            "kind": "directory",
            "name": "part-a",
            "path": "part-a",
            "children": [
                {
                    "kind": "file",
                    "name": "proof.docx",
                    "path": "part-a/proof.docx",
                    "children": [],
                }
            ],
        },
        {
            "kind": "file",
            "name": "root.pdf",
            "path": "root.pdf",
            "children": [],
        },
    ]
