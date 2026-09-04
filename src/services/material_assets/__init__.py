"""Material asset service helpers."""

from __future__ import annotations

from importlib import import_module


_QUESTION_FIGURE_EXPORTS = frozenset(
    {
        "asset_item_alt_text",
        "asset_item_cached_path",
        "asset_item_library_asset_id",
        "asset_item_preview_path",
        "asset_item_preview_reference",
        "asset_item_source",
        "asset_item_thumbnail_path",
        "parse_question_figure_repair_target",
        "question_figure_asset_sort_key",
        "question_figure_candidate_list",
        "question_figure_collection_summary",
        "question_figure_compare_display_name",
        "question_figure_compare_index_label",
        "question_figure_compare_options",
        "question_figure_detail_rows",
        "question_figure_item_matches_repair_target",
        "question_figure_item_summary",
        "question_figure_items",
        "question_figure_order_value",
        "question_figure_payload_matches_item",
        "question_figure_target_cache_path",
        "question_figure_target_label",
        "question_figure_target_value",
        "repeated_question_figure_status",
    }
)

_QUESTION_LIBRARY_EXPORTS = frozenset(
    {
        "apply_question_figure_library_metadata",
        "asset_item_payload",
        "asset_items_from_payloads",
        "asset_metadata_etag_value",
        "asset_metadata_package_id_value",
        "asset_metadata_package_label_value",
        "asset_metadata_reference_value",
        "asset_metadata_updated_at_value",
        "asset_metadata_version_value",
        "json_list_from_record_value",
        "normalize_asset_item_payloads",
        "normalized_asset_item_history_records",
        "question_figure_has_library_metadata",
        "question_figure_history_changed_fields",
        "question_figure_history_fields_label",
        "question_figure_history_record_matches_current",
        "question_figure_history_record_question_row",
        "question_figure_library_asset_label",
        "question_figure_library_master_version_entries",
        "question_figure_library_metadata_change_summary",
        "question_figure_library_metadata_history_record",
        "question_figure_library_metadata_issue_entries",
        "question_figure_library_metadata_rollback_record",
        "question_figure_library_reference",
        "question_figure_library_row_entries",
        "question_figure_library_rows",
        "question_figure_library_source_label",
        "question_figure_library_version_history_entries",
        "question_figure_master_version_diff_fields",
        "question_figure_master_version_diff_summary",
        "question_figure_master_version_has_version_statement",
        "question_figure_master_version_package_summary",
        "question_figure_master_version_status_label",
        "question_figure_master_version_summary",
        "question_figure_requires_library_identity",
        "rollback_question_figure_library_metadata",
        "set_optional_metadata_value",
    }
)

_REPAIR_AUDIT_EXPORTS = frozenset(
    {
        "QuestionFigureRepairAuditIntegrityError",
        "append_question_figure_repair_audit_record",
        "build_question_figure_repair_audit_record",
        "build_question_figure_repair_rollback_audit_record",
        "question_figure_repair_audit_id",
        "question_figure_repair_rollback_audit_id",
        "read_question_figure_repair_audit_payload",
        "resolve_question_figure_repair_audit_dir",
    }
)

_WORD_RECOVERY_EXPORTS = frozenset(
    {
        "available_asset_image_paths",
        "deep_repair_docx_xml_media",
        "docx_image_content_type",
        "docx_image_part_kind",
        "docx_image_part_names",
        "docx_part_relationships_path",
        "normalize_docx_relationship_target",
        "scan_docx_xml_media",
        "update_docx_content_types",
    }
)

_EXPORT_MODULES = {
    **dict.fromkeys(
        _QUESTION_FIGURE_EXPORTS,
        "src.services.material_assets.question_figures",
    ),
    **dict.fromkeys(
        _QUESTION_LIBRARY_EXPORTS,
        "src.services.material_assets.question_library",
    ),
    **dict.fromkeys(
        _REPAIR_AUDIT_EXPORTS,
        "src.services.material_assets.repair_audit",
    ),
    **dict.fromkeys(
        _WORD_RECOVERY_EXPORTS,
        "src.services.material_assets.word_docx_recovery",
    ),
}


def __getattr__(name: str):
    """Load optional Assets-workbench helpers only when explicitly requested."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORT_MODULES))

__all__ = [
    "QuestionFigureRepairAuditIntegrityError",
    "append_question_figure_repair_audit_record",
    "asset_item_alt_text",
    "asset_item_cached_path",
    "asset_item_library_asset_id",
    "asset_item_payload",
    "asset_item_preview_path",
    "asset_item_preview_reference",
    "asset_item_source",
    "asset_item_thumbnail_path",
    "asset_metadata_etag_value",
    "asset_metadata_package_id_value",
    "asset_metadata_package_label_value",
    "asset_metadata_reference_value",
    "asset_metadata_updated_at_value",
    "asset_metadata_version_value",
    "asset_items_from_payloads",
    "available_asset_image_paths",
    "build_question_figure_repair_audit_record",
    "build_question_figure_repair_rollback_audit_record",
    "deep_repair_docx_xml_media",
    "docx_image_content_type",
    "docx_image_part_kind",
    "docx_image_part_names",
    "docx_part_relationships_path",
    "apply_question_figure_library_metadata",
    "json_list_from_record_value",
    "normalize_docx_relationship_target",
    "normalize_asset_item_payloads",
    "normalized_asset_item_history_records",
    "parse_question_figure_repair_target",
    "question_figure_asset_sort_key",
    "question_figure_candidate_list",
    "question_figure_collection_summary",
    "question_figure_compare_display_name",
    "question_figure_compare_index_label",
    "question_figure_compare_options",
    "question_figure_detail_rows",
    "question_figure_item_matches_repair_target",
    "question_figure_item_summary",
    "question_figure_items",
    "question_figure_has_library_metadata",
    "question_figure_library_asset_label",
    "question_figure_library_metadata_issue_entries",
    "question_figure_library_master_version_entries",
    "question_figure_library_metadata_change_summary",
    "question_figure_library_metadata_history_record",
    "question_figure_library_metadata_rollback_record",
    "question_figure_library_reference",
    "question_figure_library_row_entries",
    "question_figure_library_rows",
    "question_figure_library_source_label",
    "question_figure_library_version_history_entries",
    "question_figure_history_changed_fields",
    "question_figure_history_fields_label",
    "question_figure_history_record_matches_current",
    "question_figure_history_record_question_row",
    "question_figure_master_version_diff_fields",
    "question_figure_master_version_diff_summary",
    "question_figure_master_version_has_version_statement",
    "question_figure_master_version_package_summary",
    "question_figure_master_version_status_label",
    "question_figure_master_version_summary",
    "question_figure_order_value",
    "question_figure_payload_matches_item",
    "repeated_question_figure_status",
    "question_figure_repair_audit_id",
    "question_figure_repair_rollback_audit_id",
    "question_figure_requires_library_identity",
    "question_figure_target_cache_path",
    "question_figure_target_label",
    "question_figure_target_value",
    "read_question_figure_repair_audit_payload",
    "resolve_question_figure_repair_audit_dir",
    "rollback_question_figure_library_metadata",
    "scan_docx_xml_media",
    "set_optional_metadata_value",
    "update_docx_content_types",
]
