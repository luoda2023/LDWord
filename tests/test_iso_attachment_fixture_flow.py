from hashlib import sha256
from pathlib import Path

from docx import Document

from src.config.attachment_materials import AttachmentProcessingMode
from src.config.material_snapshot import MaterialSnapshot
from src.services.material_attachments import (
    AttachmentBundleBuildRequest,
    build_attachment_binding,
    build_directory_attachment_binding,
    process_attachment_bundle,
    scan_attachment_token_requirements,
)
from src.services.material_execution.dependency_indexer import (
    MaterialDependencyIndexRequest,
    build_material_dependency_index_from_sources,
)
from src.ui.panels.assets.batch_import import (
    _load_batch_excel_rows,
    _profiles_from_table_rows,
)
from tests.iso_attachment_fixture_factory import build_iso_attachment_fixture


def test_generated_iso_fixture_extracts_shared_fields_and_builds_clean_bundle(
    tmp_path: Path,
) -> None:
    fixture = build_iso_attachment_fixture(tmp_path)
    binding = build_directory_attachment_binding(
        role="iso_templates",
        source_directory=fixture.docx_directory,
        accepted_types=("docx",),
        recursive=True,
        processing_mode=AttachmentProcessingMode.SUBSTITUTE_COPY,
        max_items=None,
    )
    requirements = scan_attachment_token_requirements(binding)
    profiles = _profiles_from_table_rows(
        _load_batch_excel_rows(fixture.workbook_path)
    )

    assert requirements.docx_count == 6
    assert requirements.strict_count == 41
    assert requirements.legacy_count == 0
    assert len(profiles) == 18
    assert profiles[0].profile_id == "profile_01"
    assert profiles[0].fields["field_01"] == "fixture-01-field_01"
    assert profiles[0].fields["field_30"] == "fixture-01-field_30"

    fields = dict(profiles[0].fields)
    for requirement in requirements.requirements:
        if not fields.get(requirement.identifier):
            fields[requirement.identifier] = (
                "2026-06-30"
                if requirement.namespace == "time"
                else f"[TEST:{requirement.identifier}]"
            )
    token_bindings = {
        f"@{requirement.namespace}:{requirement.identifier}": requirement.identifier
        for requirement in requirements.requirements
        if requirement.kind.value == "field"
    }
    snapshot = MaterialSnapshot(
        field_values=fields,
        field_token_bindings=token_bindings,
        attachment_bindings=(binding,),
        material_schema_id="iso-real-fixture",
        material_schema_version="1",
        rule_versions={"attachments": "1"},
    )
    main = tmp_path / "main.docx"
    document = Document()
    document.add_paragraph("fixture")
    document.save(main)
    index = build_material_dependency_index_from_sources(
        MaterialDependencyIndexRequest(
            snapshot=snapshot,
            main_document_path=str(main),
        )
    )
    source_hashes = {
        item.relative_path: sha256(
            Path(item.file_ref.source_path).read_bytes()
        ).hexdigest()
        for item in binding.items
    }

    receipt = process_attachment_bundle(
        AttachmentBundleBuildRequest(
            snapshot=snapshot,
            dependency_index=index,
            binding_role=binding.role,
            final_directory=str(tmp_path / "generated"),
        )
    )

    output_paths = tuple(sorted((tmp_path / "generated").glob("*.docx")))
    output_binding = build_attachment_binding(
        role="generated",
        source_paths=output_paths,
        accepted_types=("docx",),
        source_kind="file_set",
        cardinality="multiple",
        max_items=None,
    )
    remaining = scan_attachment_token_requirements(output_binding)
    assert len(receipt.files) == 6
    assert sum(item.field_replacement_count for item in receipt.files) == 114
    assert not [token for item in receipt.files for token in item.unresolved_tokens]
    assert remaining.requirements == ()
    assert source_hashes == {
        item.relative_path: sha256(
            Path(item.file_ref.source_path).read_bytes()
        ).hexdigest()
        for item in binding.items
    }
