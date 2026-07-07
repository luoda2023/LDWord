import ast
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.config.materials import AssetItem
from src.services import material_assets
from src.services.material_assets import (
    common,
    question_figures,
    question_library,
    repair_audit,
    word_docx_recovery,
)
from src.ui.panels.assets import question_audit as ui_question_audit
from src.ui.panels.assets import question_figures as ui_question_figures


def test_material_asset_service_exposes_public_question_figure_api(tmp_path):
    q2_path = tmp_path / "q2.png"
    q1_path = tmp_path / "q1.png"
    q2_path.write_bytes(b"q2")
    q1_path.write_bytes(b"q1")
    q2 = AssetItem(
        item_id="q2",
        label="Question 2",
        role="question_figure",
        path=str(q2_path),
        metadata={"question_index": "2", "asset_id": "library-q2"},
    )
    q1 = AssetItem(
        item_id="q1",
        label="Question 1",
        role="question_figure",
        path=str(q1_path),
        metadata={"question_index": "1", "asset_id": "library-q1"},
    )

    items = material_assets.question_figure_items([q2, q1])
    detail_rows = material_assets.question_figure_detail_rows([q2, q1])
    library_entries = material_assets.question_figure_library_row_entries([q2, q1])

    assert [item.item_id for item in items] == ["q1", "q2"]
    assert len(detail_rows) == 2
    assert len(library_entries) == 2
    assert material_assets.asset_item_library_asset_id(q2) == "library-q2"
    assert material_assets.question_figure_items is question_figures._question_figure_asset_items
    repeated_status = material_assets.repeated_question_figure_status(
        "question_figure",
        [q2, q1],
    )
    assert repeated_status
    assert "2" in repeated_status
    assert material_assets.repeated_question_figure_status("logo", [q2, q1]) == ""
    assert (
        material_assets.repeated_question_figure_status
        is question_figures.repeated_question_figure_status
    )
    assert (
        material_assets.parse_question_figure_repair_target("question_figure:3")
        == {"role": "question_figure", "question_index": "3"}
    )


def test_material_asset_service_does_not_expose_remote_url_preview_helpers():
    assert not hasattr(material_assets, "download_remote_asset_preview_image")
    assert not hasattr(question_figures, "download_remote_asset_preview_image")
    assert not hasattr(material_assets, "is_remote_asset_preview_url")
    assert not hasattr(material_assets, "remote_asset_url_name")
    assert not hasattr(question_figures, "is_remote_asset_preview_url")
    assert not hasattr(question_figures, "remote_asset_url_name")


def test_material_asset_service_updates_question_library_metadata_and_history():
    item = AssetItem(
        item_id="q1",
        label="Question 1",
        role="question_figure",
        path="C:/materials/q1.png",
        metadata={
            "question_index": "1",
            "source": "local",
            "asset_id": "old-q1",
            "alt_text": "old alt",
        },
    )
    payloads = [
        {
            "item_id": "q1",
            "label": "Question 1",
            "role": "question_figure",
            "path": "C:/materials/q1.png",
            "metadata": {
                "question_index": "1",
                "source": "local",
                "assetId": "old-q1",
                "alt": "old alt",
            },
        }
    ]

    result = material_assets.apply_question_figure_library_metadata(
        payloads,
        item,
        source="remote-library",
        asset_id="new-q1",
        alt_text="new alt",
    )

    assert result["updated"] is True
    updated_payload = result["payloads"][0]
    metadata = updated_payload["metadata"]
    assert metadata["source"] == "remote-library"
    assert metadata["asset_id"] == "new-q1"
    assert metadata["alt_text"] == "new alt"
    assert "assetId" not in metadata
    assert "alt" not in metadata
    history_record = result["history_record"]
    assert history_record["action"] == "question_figure_library_metadata_update"
    assert history_record["changed_fields"] == "source,asset_id,alt_text"
    assert history_record["source_before"] == "local"
    assert history_record["source_after"] == "remote-library"
    assert history_record["asset_id_before"] == "old-q1"
    assert history_record["asset_id_after"] == "new-q1"
    assert history_record["alt_text_before"] == "old alt"
    assert history_record["alt_text_after"] == "new alt"
    assert (
        material_assets.normalized_asset_item_history_records(
            [history_record, "ignored", {"action": "", "changed_at": ""}]
        )[0]["action"]
        == "question_figure_library_metadata_update"
    )
    assert (
        material_assets.apply_question_figure_library_metadata
        is question_library.apply_question_figure_library_metadata
    )


def test_material_asset_service_rolls_back_question_library_metadata():
    current_item = AssetItem(
        item_id="q1",
        label="Question 1",
        role="question_figure",
        path="C:/materials/q1.png",
        metadata={
            "question_index": "1",
            "source": "remote-library",
            "asset_id": "new-q1",
            "alt_text": "new alt",
        },
    )
    history_record = material_assets.question_figure_library_metadata_history_record(
        current_item,
        {
            "question_index": "1",
            "source": "local",
            "asset_id": "old-q1",
            "alt_text": "old alt",
        },
        dict(current_item.metadata),
    )
    assert history_record is not None
    payloads = [material_assets.asset_item_payload(current_item)]

    result = material_assets.rollback_question_figure_library_metadata(
        payloads,
        [history_record],
        [current_item],
        0,
    )

    assert result["status"] == "rolled_back"
    assert result["updated"] is True
    assert result["question_row"] == 0
    metadata = result["payloads"][0]["metadata"]
    assert metadata["source"] == "local"
    assert metadata["asset_id"] == "old-q1"
    assert metadata["alt_text"] == "old alt"
    records = result["records"]
    assert len(records) == 2
    rollback_record = records[-1]
    assert rollback_record["action"] == "question_figure_library_metadata_rollback"
    assert rollback_record["rollback_from_changed_at"] == history_record["changed_at"]
    assert rollback_record["source_before"] == "remote-library"
    assert rollback_record["source_after"] == "local"
    entries = material_assets.question_figure_library_version_history_entries(
        records,
        [
            AssetItem(
                item_id=current_item.item_id,
                label=current_item.label,
                role=current_item.role,
                path=current_item.path,
                metadata=dict(metadata),
            )
        ],
    )
    assert [entry[0] for entry in entries] == [1, 0]
    assert all(entry[1] == 0 for entry in entries)
    assert (
        material_assets.rollback_question_figure_library_metadata
        is question_library.rollback_question_figure_library_metadata
    )


def test_material_asset_service_projects_question_library_metadata_issues():
    q1 = AssetItem(
        item_id="q1",
        label="Question 1",
        role="question_figure",
        path="C:/materials/q1.png",
        metadata={
            "question_index": "1",
            "source": "school_bank",
            "asset_id": "shared-asset",
            "alt_text": "第一题图",
        },
    )
    q2 = AssetItem(
        item_id="q2",
        label="Question 2",
        role="question_figure",
        path="C:/materials/q2.png",
        metadata={
            "question_index": "2",
            "source": "school_bank",
            "asset_id": "shared-asset",
        },
    )
    q3 = AssetItem(
        item_id="missing-source",
        label="Question 3",
        role="question_figure",
        path="",
        metadata={
            "question_index": "3",
            "asset_id": "missing-source",
            "alt_text": "第三题图",
        },
    )

    issue_rows = material_assets.question_figure_library_metadata_issue_entries(
        [q1, q2, q3]
    )
    assert (1, ("缺图片说明", "题2", "school_bank", "shared-asset")) in issue_rows
    assert (2, ("缺库来源", "题3", "缺来源", "missing-source")) in issue_rows
    assert (0, ("重复素材ID", "题1", "school_bank", "shared-asset")) in issue_rows
    assert (1, ("重复素材ID", "题2", "school_bank", "shared-asset")) in issue_rows
    assert (
        material_assets.question_figure_library_metadata_issue_entries
        is question_library.question_figure_library_metadata_issue_entries
    )
    for name in (
        "question_figure_library_bulk_governance_entries",
        "question_figure_bulk_governance_scope",
        "question_figure_bulk_governance_next_step",
    ):
        assert not hasattr(material_assets, name), name
        assert not hasattr(question_library, name), name


def test_material_asset_service_projects_master_version_entries():
    profile_a = SimpleNamespace(
        profile_id="pack_a",
        profile_name="Package A",
        asset_items=[
            {
                "item_id": "q1-a",
                "label": "Question 1",
                "role": "question_figure",
                "path": "",
                "metadata": {
                    "question_index": "1",
                    "source": "school_bank",
                    "asset_id": "shared-asset",
                    "library_package_id": "package-a",
                    "library_package_name": "Package A",
                    "asset_version": "v1",
                    "asset_etag": "etag-a",
                    "asset_updated_at": "2026-06-01",
                    "alt_text": "Figure A",
                },
            }
        ],
        asset_item_history=[],
    )
    profile_b = SimpleNamespace(
        profile_id="pack_b",
        profile_name="Package B",
        asset_items=[
            {
                "item_id": "q1-b",
                "label": "Question 1",
                "role": "question_figure",
                "path": "",
                "metadata": {
                    "question_index": "1",
                    "source": "school_bank",
                    "asset_id": "shared-asset",
                    "library_package_id": "package-b",
                    "library_package_name": "Package B",
                    "asset_version": "v2",
                    "asset_etag": "etag-b",
                    "asset_updated_at": "2026-06-02",
                    "alt_text": "Figure B",
                },
            }
        ],
        asset_item_history=[],
    )

    entries = material_assets.question_figure_library_master_version_entries(
        [profile_a, profile_b]
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry["master_key"] == "school_bank/shared-asset"
    assert "Package A" in entry["package_summary"]
    assert "Package B" in entry["package_summary"]
    assert "v1" in entry["version_summary"]
    assert "v2" in entry["version_summary"]
    assert "asset_version" in entry["diff_fields"]
    assert "asset_etag" in entry["diff_fields"]
    assert "ETag" in entry["diff_summary"]
    assert entry["status_label"] == "版本不一致"
    assert "plan_recorded" not in entry
    assert "promotion_executed" not in entry

    profile_a.asset_item_history = [
        {
            "action": "question_figure_library_cross_package_master_version_governance_plan",
            "changed_at": "2026-07-06T00:00:00Z",
            "master_data_key": "school_bank/shared-asset",
        }
    ]
    profile_b.asset_item_history = [
        {
            "action": "question_figure_library_cross_package_master_version_promotion_execution",
            "changed_at": "2026-07-06T00:01:00Z",
            "master_data_key": "school_bank/shared-asset",
        }
    ]
    legacy_record_entry = material_assets.question_figure_library_master_version_entries(
        [profile_a, profile_b]
    )[0]

    assert legacy_record_entry["status_label"] == "版本不一致"
    assert "plan_recorded" not in legacy_record_entry
    assert "promotion_executed" not in legacy_record_entry
    assert (
        material_assets.question_figure_library_master_version_entries
        is question_library.question_figure_library_master_version_entries
    )


def test_material_asset_service_master_version_execution_api_is_not_public():
    removed_names = (
        "asset_metadata_reference_patch",
        "build_question_figure_library_master_version_plan_record",
        "build_question_figure_library_master_version_promotion_record",
        "natural_version_sort_key",
        "promote_question_figure_master_version_to_profile",
        "question_figure_library_master_version_plan_for",
        "question_figure_library_master_version_promotion_for",
        "question_figure_master_version_canonical_occurrence",
        "question_figure_master_version_canonical_sort_key",
        "question_figure_master_version_changed_fields",
        "question_figure_master_version_promoted_metadata",
        "question_figure_payload_index_for_question_row",
        "record_question_figure_library_master_version_plan",
    )
    for name in removed_names:
        assert not hasattr(material_assets, name), name
        assert not hasattr(question_library, name), name


def test_material_asset_service_reads_master_version_metadata_aliases():
    metadata = {
        "assetVersion": "v3",
        "assetEtag": "etag-c",
        "assetUpdatedAt": "2026-06-03T00:00:00Z",
        "cachedPath": "C:/cache/c.png",
    }

    assert material_assets.asset_metadata_version_value(metadata) == "v3"
    assert material_assets.asset_metadata_etag_value(metadata) == "etag-c"
    assert (
        material_assets.asset_metadata_updated_at_value(metadata)
        == "2026-06-03T00:00:00Z"
    )
    assert (
        material_assets.asset_metadata_reference_value(metadata)
        == "C:/cache/c.png"
    )
    assert material_assets.asset_metadata_package_id_value(
        {"libraryPackageId": "pack-1"}
    ) == "pack-1"
    assert material_assets.asset_metadata_package_label_value(
        {"packageName": "Pack A"}
    ) == "Pack A"
    assert (
        material_assets.asset_metadata_version_value
        is question_library.asset_metadata_version_value
    )
    assert (
        material_assets.asset_metadata_reference_value
        is question_library.asset_metadata_reference_value
    )


def test_material_asset_service_optional_metadata_setter_cleans_extended_aliases():
    metadata = {
        "assetVersion": "v1",
        "version": "legacy-v",
        "remoteEtag": "old-etag",
        "hash": "old-hash",
        "updatedAt": "old-time",
        "lastModified": "old-last-modified",
        "previewUrl": "https://cdn.test/old-preview.png",
        "fullPreviewUrl": "https://cdn.test/full-preview.png",
        "cachedPath": "C:/cache/old.png",
        "localPath": "C:/cache/local.png",
    }

    material_assets.set_optional_metadata_value(metadata, "asset_version", "v2")
    material_assets.set_optional_metadata_value(metadata, "asset_etag", "etag-2")
    material_assets.set_optional_metadata_value(
        metadata,
        "asset_updated_at",
        "2026-06-04T00:00:00Z",
    )
    material_assets.set_optional_metadata_value(
        metadata,
        "preview_url",
        "https://cdn.test/new-preview.png",
    )
    material_assets.set_optional_metadata_value(metadata, "cache_path", "")

    assert metadata["asset_version"] == "v2"
    assert metadata["asset_etag"] == "etag-2"
    assert metadata["asset_updated_at"] == "2026-06-04T00:00:00Z"
    assert "preview_url" not in metadata
    assert "assetVersion" not in metadata
    assert "version" not in metadata
    assert "remoteEtag" not in metadata
    assert "hash" not in metadata
    assert "updatedAt" not in metadata
    assert "lastModified" not in metadata
    assert "previewUrl" not in metadata
    assert "fullPreviewUrl" not in metadata
    assert "cache_path" not in metadata
    assert "cachedPath" not in metadata
    assert "localPath" not in metadata
    assert (
        material_assets.set_optional_metadata_value
        is question_library.set_optional_metadata_value
    )


def test_material_asset_service_does_not_expose_shared_cache_projection_api():
    assert not hasattr(material_assets, "question_figure_shared_cache_dir_rows")
    assert not hasattr(material_assets, "question_figure_shared_cache_entry_rows")
    assert not hasattr(material_assets, "asset_item_shared_cache_dir")
    assert not hasattr(material_assets, "asset_item_cache_status")


def test_material_asset_service_exposes_public_docx_recovery_api(tmp_path):
    docx_path = tmp_path / "question-output.docx"
    document_xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<w:body><w:p><w:r><w:drawing><a:blip r:embed="rId1"/>'
        "</w:drawing></w:r></w:p></w:body></w:document>"
    )
    relationships_xml = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        'Target="media/image1.png"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", relationships_xml)
        archive.writestr("word/media/image1.png", b"image")

    scan = material_assets.scan_docx_xml_media(docx_path)

    assert scan["status"] == "xml_media_consistent"
    assert scan["relationship_status"] == "relationship_consistent"
    assert scan["media_status"] == "media_consistent"
    assert scan["document_image_reference_ids"] == ["rId1"]
    assert scan["relationship_media_paths"] == ["word/media/image1.png"]
    assert material_assets.normalize_docx_relationship_target(
        "../media/header.png",
        source_part_path="word/header1.xml",
    ) == "media/header.png"
    assert (
        material_assets.docx_part_relationships_path("word/header1.xml")
        == "word/_rels/header1.xml.rels"
    )
    assert material_assets.docx_image_part_kind("word/footer1.xml") == "footer"

    broken_docx_path = tmp_path / "question-output-broken.docx"
    with zipfile.ZipFile(broken_docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", relationships_xml)

    broken_scan = material_assets.scan_docx_xml_media(broken_docx_path)

    assert broken_scan["status"] == "xml_media_repair_required"
    assert broken_scan["media_status"] == "media_repair_required"
    assert broken_scan["missing_media_paths"] == ["word/media/image1.png"]
    replacement_image = tmp_path / "replacement.png"
    replacement_image.write_bytes(b"replacement")
    output_docx_path = tmp_path / "question-output-repaired.docx"
    repair_result = material_assets.deep_repair_docx_xml_media(
        broken_docx_path,
        output_docx_path,
        [{"image_path": str(replacement_image)}],
    )

    assert repair_result["status"] == "deep_repair_completed"
    assert repair_result["media_repair_status"] == "media_deep_repair_verified"
    assert repair_result["missing_media_repaired_count"] == 1
    assert output_docx_path.exists()
    assert (
        material_assets.scan_docx_xml_media(output_docx_path)["status"]
        == "xml_media_consistent"
    )
    assert material_assets.available_asset_image_paths(
        [{"image_path": str(replacement_image)}]
    ) == [replacement_image]
    assert material_assets.update_docx_content_types(None, ["png"])
    assert material_assets.docx_image_content_type("png") == "image/png"
    assert material_assets.scan_docx_xml_media is word_docx_recovery.scan_docx_xml_media
    assert (
        material_assets.deep_repair_docx_xml_media
        is word_docx_recovery.deep_repair_docx_xml_media
    )


def test_ui_question_helpers_are_compatibility_exports_for_services():
    assert (
        ui_question_figures._question_figure_asset_items
        is question_figures._question_figure_asset_items
    )
    assert ui_question_figures.question_figure_items is question_figures.question_figure_items
    assert (
        ui_question_audit._question_figure_repair_audit_record
        is repair_audit._question_figure_repair_audit_record
    )
    assert (
        ui_question_audit.build_question_figure_repair_audit_record
        is repair_audit.build_question_figure_repair_audit_record
    )
    assert not (Path("src/ui/panels/assets/question_cache.py")).exists()


def test_material_asset_services_do_not_import_ui_panel_layer():
    question_source = Path(question_figures.__file__).read_text(encoding="utf-8")
    library_source = Path(question_library.__file__).read_text(encoding="utf-8")
    audit_source = Path(repair_audit.__file__).read_text(encoding="utf-8")
    common_source = Path(common.__file__).read_text(encoding="utf-8")

    assert "src.ui.panels" not in question_source
    assert "src.ui.panels" not in library_source
    assert "src.ui.panels" not in audit_source
    assert "src.ui.panels" not in common_source
    assert "assets_panel" not in question_source
    assert "assets_panel" not in library_source
    assert "assets_panel" not in audit_source
    assert "assets_panel" not in common_source


def test_assets_panel_uses_material_asset_services_for_local_question_helpers():
    panel_path = Path("src/ui/panels/assets_panel.py")
    module = ast.parse(panel_path.read_text(encoding="utf-8"))
    imports = [
        node
        for node in module.body
        if isinstance(node, ast.ImportFrom)
    ]
    legacy_modules = {
        "src.ui.panels.assets.question_figures",
        "src.ui.panels.assets.question_audit",
    }
    legacy_call_names = {
        "_append_question_figure_repair_audit_record",
        "_asset_item_alt_text",
        "_asset_item_cached_path",
        "_asset_item_library_asset_id",
        "_asset_item_preview_path",
        "_asset_item_preview_reference",
        "_asset_item_source",
        "_asset_item_thumbnail_path",
        "_question_figure_asset_items",
        "_question_figure_asset_sort_key",
        "_question_figure_candidate_list",
        "_question_figure_collection_summary",
        "_question_figure_compare_display_name",
        "_question_figure_compare_index_label",
        "_question_figure_compare_options",
        "_question_figure_detail_rows",
        "_question_figure_item_matches_repair_target",
        "_question_figure_item_summary",
        "_question_figure_order_value",
        "_question_figure_payload_matches_item",
        "_question_figure_repair_audit_dir",
        "_question_figure_repair_audit_id",
        "_question_figure_repair_audit_record",
        "_question_figure_repair_rollback_audit_id",
        "_question_figure_repair_rollback_audit_record",
        "_question_figure_repair_target_payload",
        "_question_figure_target_cache_path",
        "_question_figure_target_label",
        "_question_figure_target_value",
        "_read_question_figure_repair_audit_payload",
    }
    legacy_calls = [
        node.func.id
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in legacy_call_names
    ]

    assert any(node.module == "src.services.material_assets" for node in imports)
    assert not any(node.module in legacy_modules for node in imports)
    assert legacy_calls == []
