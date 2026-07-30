from __future__ import annotations

from hashlib import sha256

import pytest

from src.config.content_artifacts import (
    ArtifactFileRef,
    CONTENT_COMPILER_CONTRACT,
    CONTENT_IR_CONTRACT,
    ContentArtifactManifest,
    ContentArtifactResource,
    ContentMaterialBinding,
    ContentSourceProvenance,
)
from src.services.material_content.import_contract import (
    ContentCompileReceipt,
    ContentImportDisposition,
    ContentImportFinding,
    ContentSemanticInventory,
    aggregate_content_findings,
)


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def test_artifact_manifest_and_binding_are_canonical_and_path_free() -> None:
    source_payload = b"docx"
    fragment_payload = b'{"blocks":[]}'
    receipt_payload = b'{"findings":[]}'
    resource_payload = b"png"
    source_file = ArtifactFileRef(
        "source/input.docx",
        _digest(source_payload),
        len(source_payload),
    )
    manifest = ContentArtifactManifest(
        source=ContentSourceProvenance(
            format="docx",
            original_name="input.docx",
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            sha256=source_file.sha256,
            byte_size=source_file.byte_size,
            blob=source_file,
        ),
        fragment=ArtifactFileRef(
            "fragment.json",
            _digest(fragment_payload),
            len(fragment_payload),
        ),
        receipt=ArtifactFileRef(
            "compile-receipt.json",
            _digest(receipt_payload),
            len(receipt_payload),
        ),
        resources=(
            ContentArtifactResource(
                "sha256/image.png",
                "image/png",
                ArtifactFileRef(
                    "resources/sha256/image.png",
                    _digest(resource_payload),
                    len(resource_payload),
                ),
            ),
        ),
    )

    restored = ContentArtifactManifest.from_dict(manifest.to_dict())
    binding = ContentMaterialBinding("content1", "正文", manifest.ref)

    assert restored == manifest
    assert restored.artifact_id == manifest.artifact_id
    assert restored.manifest_sha256 == manifest.manifest_sha256
    assert ContentMaterialBinding.from_dict(binding.to_dict()) == binding
    assert "C:\\" not in manifest.to_json()
    assert "content1" not in manifest.to_json()


@pytest.mark.parametrize(
    "path",
    ("../escape", "/absolute", "C:/absolute", "folder/../escape"),
)
def test_artifact_file_paths_must_be_relative_and_contained(path: str) -> None:
    with pytest.raises(ValueError, match="artifact-relative"):
        ArtifactFileRef(path, "a" * 64, 1)


def test_findings_aggregate_by_root_cause_and_receipt_rejects_blockers() -> None:
    nested = tuple(
        ContentImportFinding(
            code="vml_node",
            disposition=ContentImportDisposition.WARNING,
            scope="main_body",
            object_id=f"node-{index}",
            cause_id="image-rId4",
            message_key="content.image.normalized",
            user_message="图片已规范化",
            technical_context=(("part", "word/document.xml"),),
        )
        for index in range(6)
    )
    aggregated = aggregate_content_findings(nested)

    assert len(aggregated) == 1
    assert aggregated[0].count == 1
    assert aggregated[0].grouping_id == "image-rId4"

    receipt = ContentCompileReceipt(
        compiler_contract=CONTENT_COMPILER_CONTRACT,
        parser_contract=CONTENT_IR_CONTRACT,
        source_sha256="b" * 64,
        inventory=ContentSemanticInventory.empty(),
        findings=aggregated,
    )
    assert ContentCompileReceipt.from_dict(receipt.to_dict()) == receipt

    blocker = ContentImportFinding(
        code="unsafe_object",
        disposition=ContentImportDisposition.BLOCKER,
        scope="main_body",
        object_id="object-1",
        message_key="content.object.unsupported",
        user_message="对象无法安全转换",
    )
    with pytest.raises(ValueError, match="cannot contain blockers"):
        ContentCompileReceipt(
            compiler_contract=CONTENT_COMPILER_CONTRACT,
            parser_contract=CONTENT_IR_CONTRACT,
            source_sha256="c" * 64,
            inventory=ContentSemanticInventory.empty(),
            findings=(blocker,),
        )
