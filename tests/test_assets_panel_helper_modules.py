from src.ui.panels import assets_panel
from src.ui.panels.assets import (
    archive_presenter,
    asset_collection_state_presenter,
    asset_file_operations_presenter,
    asset_rows_presenter,
    batch_import,
    batch_output_presenter,
    field_editor_state_presenter,
    fields,
    image_helpers,
    image_inventory_presenter,
    image_preview_presenter,
    items,
    layout_helpers,
    material_context_application_presenter,
    material_repair_navigation_presenter,
    material_settings_presenter,
    preview_table_presenter,
    profile_editor_presenter,
    profile_presenter,
    question_figures_presenter,
    question_figure_repair_actions_presenter,
    question_library_history_presenter,
    question_library_issue_presenter,
    question_library_master_version_presenter,
    question_library_presenter,
    responsive_layout_presenter,
    roles,
    scene_spec_presenter,
    section_summary_presenter,
    text_helpers,
    theme_presenter,
)


def test_assets_panel_keeps_extracted_helpers_in_module_namespace():
    assert assets_panel._parse_fields_text is fields._parse_fields_text
    assert assets_panel._normalized_asset_metadata is items._normalized_asset_metadata
    assert assets_panel._asset_role_min_short_side is image_helpers._asset_role_min_short_side
    assert assets_panel._first_image_path_from_mime is image_helpers._first_image_path_from_mime
    assert assets_panel._image_quality_text is image_helpers._image_quality_text
    assert assets_panel._load_scaled_pixmap is image_helpers._load_scaled_pixmap
    assert assets_panel._chunk_form_rows is layout_helpers._chunk_form_rows
    assert assets_panel._asset_slot_supports_alt_text is roles._asset_slot_supports_alt_text
    assert assets_panel._asset_slot_role_for_token is roles._asset_slot_role_for_token
    assert assets_panel._parse_replacements_text is text_helpers._parse_replacements_text
    assert assets_panel._format_replacements_text is text_helpers._format_replacements_text
    assert assets_panel._format_image_rules_text is text_helpers._format_image_rules_text
    assert assets_panel._profiles_from_table_rows is batch_import._profiles_from_table_rows


def test_assets_panel_uses_image_preview_presenter_mixin():
    moved_methods = {
        "_set_current_image_preview_path",
        "_set_image_preview",
        "_configure_full_image_preview_tool_button",
        "_refresh_full_image_preview_zoom_label",
        "_refresh_full_image_preview_pixmap",
        "_set_full_image_preview_zoom",
        "_zoom_full_image_preview",
        "_reset_full_image_preview_zoom",
        "_fit_full_image_preview_to_window",
        "_selected_full_image_preview_compare_option",
        "_open_full_image_preview_compare",
        "_current_full_image_preview_region_payload",
        "_current_full_image_preview_region_summary",
        "_mark_current_full_image_preview_compare_issue",
        "_open_current_image_preview_dialog",
    }

    assert image_preview_presenter.ImagePreviewPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            image_preview_presenter.ImagePreviewPresenterMixin,
            name,
        )


def test_assets_panel_uses_field_editor_state_presenter_mixin():
    moved_methods = {
        "_on_structured_field_changed",
        "_on_more_fields_changed",
        "_on_required_fields_changed",
        "_required_field_keys",
        "_editor_fields",
        "_set_structured_fields",
    }

    assert field_editor_state_presenter.FieldEditorStatePresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            field_editor_state_presenter.FieldEditorStatePresenterMixin,
            name,
        )


def test_assets_panel_uses_asset_collection_state_presenter_mixin():
    moved_methods = {
        "_asset_items_for_profile",
        "_current_asset_items",
        "_current_asset_metadata",
        "_image_rules_for_asset_items",
    }

    assert (
        asset_collection_state_presenter.AssetCollectionStatePresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            asset_collection_state_presenter.AssetCollectionStatePresenterMixin,
            name,
        )


def test_assets_panel_uses_archive_presenter_mixin():
    moved_methods = {
        "_setup_archive_overview_card",
        "_setup_import_export_card",
        "current_archive",
        "set_archive",
        "save_archive_to_path",
        "load_archive_from_path",
        "_archive_display_name",
        "_sync_archive_selector",
        "_on_archive_selector_changed",
        "_blank_archive",
        "_new_archive",
        "_duplicate_archive",
        "_rename_archive",
        "_open_archive_folder",
        "_delete_archive",
        "_load_archive_dialog",
        "_save_archive_dialog",
    }

    assert archive_presenter.ArchivePresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            archive_presenter.ArchivePresenterMixin,
            name,
        )


def test_assets_panel_uses_asset_rows_presenter_mixin():
    moved_methods = {
        "_build_asset_slot_row",
        "_build_attachment_role_row",
        "_configure_asset_icon_button",
    }

    assert asset_rows_presenter.AssetRowsPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            asset_rows_presenter.AssetRowsPresenterMixin,
            name,
        )


def test_assets_panel_uses_profile_presenter_mixin():
    moved_methods = {
        "_selected_profile",
        "_persist_current_profile_editor",
        "_reload_profile_list",
        "_update_profile_item",
        "_refresh_profile_item_labels",
        "_select_profile_for_repair",
        "_on_profile_row_changed",
        "_on_profile_item_changed",
        "_load_profile_to_editor",
        "_add_profile",
        "_copy_current_profile",
        "_has_only_empty_profile",
        "_normalize_imported_profile",
        "_next_profile_id",
        "_remove_current_profile",
    }

    assert profile_presenter.ProfilePresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            profile_presenter.ProfilePresenterMixin,
            name,
        )


def test_assets_panel_uses_profile_editor_presenter_mixin():
    moved_methods = {
        "_setup_profile_editor_card",
    }

    assert profile_editor_presenter.ProfileEditorPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            profile_editor_presenter.ProfileEditorPresenterMixin,
            name,
        )


def test_assets_panel_uses_asset_file_operations_presenter_mixin():
    moved_methods = {
        "_path_for_asset_slot",
        "_select_asset_file",
        "_select_attachment_file",
        "_attachment_role_spec",
        "_handle_asset_drag_event",
        "_apply_asset_slot_path",
        "_clear_asset_file",
        "_clear_attachment_file",
        "_show_asset_slot_path",
        "_open_asset_slot_path",
        "_open_attachment_path",
        "_open_file_path",
    }

    assert (
        asset_file_operations_presenter.AssetFileOperationsPresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            asset_file_operations_presenter.AssetFileOperationsPresenterMixin,
            name,
        )


def test_assets_panel_uses_batch_output_presenter_mixin():
    moved_methods = {
        "_setup_batch_profile_output_card",
        "_open_batch_generation",
        "material_batch_selection",
        "selected_batch_profile_ids",
        "batch_output_preview",
        "load_batch_profiles_from_path",
        "_load_batch_profiles_dialog",
        "_on_batch_output_template_changed",
        "_on_batch_output_naming_changed",
        "_batch_output_template",
        "_current_batch_output_naming_template",
        "_select_batch_output_naming_for_template",
        "_shared_batch_context",
        "_sync_material_batch_selection",
    }

    assert batch_output_presenter.BatchOutputPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            batch_output_presenter.BatchOutputPresenterMixin,
            name,
        )


def test_assets_panel_uses_material_repair_navigation_mixin():
    moved_methods = {
        "_focus_missing_content",
        "focus_material_repair_target",
        "handle_navigation_intent",
        "_set_return_navigation_intent",
        "_navigate_return_target",
        "focus_material_profile_repair_target",
        "apply_material_profile_question_figure_repair_candidate",
        "_on_material_repair_target_requested",
        "_on_material_profile_repair_target_requested",
        "_on_material_profile_repair_candidate_requested",
        "_focus_pending_material_repair_target",
        "_next_missing_target",
        "_focus_asset_slot",
        "_focus_attachment_role",
        "_attachment_role_for_token",
        "_focus_question_figure_item",
        "_question_figure_item_row_for_target",
        "_question_figure_item_row_for_repair_audit_record",
        "_material_role_label",
        "_show_missing_target",
        "_jump_to_card",
        "_select_section_for_card",
        "_select_section",
        "_highlight_attention_card",
        "_settle_attention_card",
        "_ensure_widget_visible",
    }

    assert (
        material_repair_navigation_presenter.MaterialRepairNavigationMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            material_repair_navigation_presenter.MaterialRepairNavigationMixin,
            name,
        )


def test_assets_panel_uses_preview_table_presenter_mixin():
    moved_methods = {
        "_setup_placeholder_preview_card",
        "_toggle_preview_filter",
        "_on_preview_auto_match",
        "_on_document_loaded",
        "_visible_placeholder_preview_rows",
        "_placeholder_preview_text",
        "_placeholder_source_path",
        "_scanned_placeholders",
        "_current_preview_state",
        "_missing_attachment_roles",
        "_unmatched_placeholders",
        "_placeholder_preview_rows",
        "_refresh_preview_table",
        "_handle_preview_row_action",
    }

    assert preview_table_presenter.PreviewTablePresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            preview_table_presenter.PreviewTablePresenterMixin,
            name,
        )


def test_assets_panel_uses_material_context_application_presenter_mixin():
    moved_methods = {
        "_setup_generation_actions_card",
        "material_context",
        "load_mapping_from_path",
        "_apply_current_profile",
        "_open_document_generation",
        "_load_mapping_dialog",
        "_apply_mapping_payload",
        "_on_material_context_changed",
        "_set_editor_values",
    }

    assert (
        material_context_application_presenter.MaterialContextApplicationPresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            material_context_application_presenter.MaterialContextApplicationPresenterMixin,
            name,
        )


def test_assets_panel_uses_material_settings_presenter_mixin():
    moved_methods = {
        "_setup_material_settings_card",
    }

    assert material_settings_presenter.MaterialSettingsPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            material_settings_presenter.MaterialSettingsPresenterMixin,
            name,
        )


def test_assets_panel_uses_question_figure_repair_actions_presenter_mixin():
    moved_methods = {
        "current_question_figure_repair_audit_records",
        "revert_question_figure_repair_audit_record",
        "_select_question_figure_library_issue_question_row",
        "_select_question_figure_item_file",
        "_replace_question_figure_item_path",
        "apply_question_figure_repair_candidate",
        "_record_question_figure_repair_application",
        "_record_question_figure_repair_rollback",
    }

    assert (
        question_figure_repair_actions_presenter.QuestionFigureRepairActionsPresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            question_figure_repair_actions_presenter.QuestionFigureRepairActionsPresenterMixin,
            name,
        )


def test_assets_panel_does_not_expose_question_figure_shared_cache_helpers():
    assert "_setup_question_figure_shared_cache_tables" not in assets_panel.AssetsPanel.__dict__
    assert not hasattr(assets_panel.AssetsPanel, "_setup_question_figure_shared_cache_tables")


def test_assets_panel_uses_question_figure_master_version_presenter_mixin():
    moved_methods = {
        "_setup_question_figure_library_master_version_table",
    }

    assert (
        question_library_master_version_presenter.QuestionFigureLibraryMasterVersionPresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            question_library_master_version_presenter.QuestionFigureLibraryMasterVersionPresenterMixin,
            name,
        )


def test_assets_panel_uses_question_figure_history_presenter_mixin():
    moved_methods = {
        "_setup_question_figure_library_version_history_table",
    }

    assert (
        question_library_history_presenter.QuestionFigureLibraryHistoryPresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            question_library_history_presenter.QuestionFigureLibraryHistoryPresenterMixin,
            name,
        )


def test_assets_panel_uses_question_figure_issue_presenter_mixin():
    moved_methods = {
        "_setup_question_figure_library_issue_table",
    }

    assert (
        question_library_issue_presenter.QuestionFigureLibraryIssuePresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            question_library_issue_presenter.QuestionFigureLibraryIssuePresenterMixin,
            name,
        )


def test_assets_panel_uses_question_figure_library_presenter_mixin():
    moved_methods = {
        "_setup_question_figure_library_card",
    }

    assert (
        question_library_presenter.QuestionFigureLibraryPresenterMixin
        in assets_panel.AssetsPanel.__mro__
    )
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            question_library_presenter.QuestionFigureLibraryPresenterMixin,
            name,
        )


def test_assets_panel_uses_question_figure_items_presenter_mixin():
    moved_methods = {
        "_setup_question_figure_items_table",
    }

    assert question_figures_presenter.QuestionFigureItemsPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            question_figures_presenter.QuestionFigureItemsPresenterMixin,
            name,
        )


def test_assets_panel_uses_image_inventory_setup_presenter_mixin():
    moved_methods = {
        "_setup_image_inventory_card",
    }

    assert image_inventory_presenter.ImageInventorySetupPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            image_inventory_presenter.ImageInventorySetupPresenterMixin,
            name,
        )


def test_assets_panel_uses_section_summary_presenter_mixin():
    moved_methods = {
        "_refresh_summary",
        "_refresh_section_cards",
        "_refresh_section_summary_cards",
    }

    assert section_summary_presenter.SectionSummaryPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            section_summary_presenter.SectionSummaryPresenterMixin,
            name,
        )


def test_assets_panel_uses_theme_presenter_mixin():
    moved_methods = {
        "_apply_theme",
    }

    assert theme_presenter.ThemePresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            theme_presenter.ThemePresenterMixin,
            name,
        )


def test_assets_panel_uses_responsive_layout_presenter_mixin():
    moved_methods = {
        "resizeEvent",
        "eventFilter",
        "_apply_responsive_layout",
        "_sync_generate_action_button_mode",
        "_sync_archive_action_button_mode",
    }

    assert responsive_layout_presenter.ResponsiveLayoutPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            responsive_layout_presenter.ResponsiveLayoutPresenterMixin,
            name,
        )


def test_assets_panel_uses_scene_spec_presenter_mixin():
    moved_methods = {
        "_on_scene_changed",
        "_default_required_field_keys",
        "_required_fields_from_scene",
        "_required_fields_match_default",
        "_asset_slots_from_scene",
        "_attachment_roles_from_scene",
        "_sync_asset_slot_rows",
        "_sync_attachment_role_rows",
    }

    assert scene_spec_presenter.SceneSpecPresenterMixin in assets_panel.AssetsPanel.__mro__
    for name in moved_methods:
        assert name not in assets_panel.AssetsPanel.__dict__
        assert getattr(assets_panel.AssetsPanel, name) is getattr(
            scene_spec_presenter.SceneSpecPresenterMixin,
            name,
        )


def test_material_repair_navigation_presenter_owns_preview_missing_target_methods():
    presenter_methods = material_repair_navigation_presenter.MaterialRepairNavigationMixin.__dict__

    assert "_focus_missing_content" in presenter_methods
    assert "_next_missing_target" in presenter_methods
    assert "_attachment_role_for_token" in presenter_methods


def test_material_repair_navigation_presenter_owns_asset_focus_methods():
    presenter_methods = material_repair_navigation_presenter.MaterialRepairNavigationMixin.__dict__

    assert "_focus_asset_slot" in presenter_methods
    assert "_focus_attachment_role" in presenter_methods
    assert "_material_role_label" in presenter_methods


def test_material_repair_navigation_presenter_owns_question_figure_target_methods():
    presenter_methods = material_repair_navigation_presenter.MaterialRepairNavigationMixin.__dict__

    assert "_focus_question_figure_item" in presenter_methods
    assert "_question_figure_item_row_for_target" in presenter_methods
    assert "_question_figure_item_row_for_repair_audit_record" in presenter_methods


def test_material_repair_navigation_presenter_owns_bridge_target_consumption_methods():
    presenter_methods = material_repair_navigation_presenter.MaterialRepairNavigationMixin.__dict__

    assert "_focus_pending_material_repair_target" in presenter_methods
    assert "_on_material_repair_target_requested" in presenter_methods
    assert "_on_material_profile_repair_target_requested" in presenter_methods
    assert "_on_material_profile_repair_candidate_requested" in presenter_methods


def test_material_repair_navigation_presenter_owns_focus_card_methods():
    presenter_methods = material_repair_navigation_presenter.MaterialRepairNavigationMixin.__dict__

    assert "_show_missing_target" in presenter_methods
    assert "_jump_to_card" in presenter_methods
    assert "_highlight_attention_card" in presenter_methods
    assert "_ensure_widget_visible" in presenter_methods


def test_batch_import_helper_preserves_fields_assets_and_question_figures():
    profiles = batch_import._profiles_from_table_rows(
        [
            {
                "company_name": "Acme Corp",
                "logo": "assets/logo.png",
                "question_figure1_path": "assets/q1.png",
                "question_figure1_asset_id": "remote-q1",
            }
        ]
    )

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.fields["company_name"] == "Acme Corp"
    assert profile.asset_paths["logo"] == "assets/logo.png"
    assert profile.asset_items == [
        {
            "item_id": "question_figure_1",
            "label": "remote-q1",
            "role": "question_figure",
            "path": "assets/q1.png",
            "metadata": {
                "asset_id": "remote-q1",
                "question_index": "1",
            },
        }
    ]
