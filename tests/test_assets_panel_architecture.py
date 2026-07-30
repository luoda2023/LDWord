import ast
from pathlib import Path

from src.qt_api import QApplication
from src.shared.ui.master_detail_shell import MasterDetailShell
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import OPTIONAL_PANEL_SPECS, create_panel
from src.ui.panels.assets import batch_import, enterprise_boundary, specs
from src.ui.panels.assets.archive_presenter import ArchivePresenterMixin
from src.ui.panels.assets.asset_collection_state_presenter import AssetCollectionStatePresenterMixin
from src.ui.panels.assets.asset_file_operations_presenter import AssetFileOperationsPresenterMixin
from src.ui.panels.assets.asset_slot_status_presenter import AssetSlotStatusPresenterMixin
from src.ui.panels.assets.batch_output_presenter import BatchOutputPresenterMixin
from src.ui.panels.assets.field_editor_state_presenter import FieldEditorStatePresenterMixin
from src.ui.panels.assets.field_status_presenter import FieldStatusPresenterMixin
from src.ui.panels.assets.image_inventory_presenter import ImageInventorySetupPresenterMixin
from src.ui.panels.assets.material_context_application_presenter import (
    MaterialContextApplicationPresenterMixin,
)
from src.ui.panels.assets.material_change_transaction import (
    MaterialChangeTransactionCoordinator,
)
from src.ui.panels.assets.persistence_presenter import MaterialPersistenceCoordinator
from src.ui.panels.assets.preview_table_presenter import PreviewTablePresenterMixin
from src.ui.panels.assets.profile_editor_presenter import ProfileEditorPresenterMixin
from src.ui.panels.assets.profile_presenter import ProfilePresenterMixin
from src.ui.panels.assets.question_figure_repair_actions_presenter import (
    QuestionFigureRepairActionsPresenterMixin,
)
from src.ui.panels.assets.question_figures_presenter import QuestionFigureItemsPresenterMixin
from src.ui.panels.assets.question_library_history_presenter import (
    QuestionFigureLibraryHistoryPresenterMixin,
)
from src.ui.panels.assets.question_library_issue_presenter import (
    QuestionFigureLibraryIssuePresenterMixin,
)
from src.ui.panels.assets.question_library_presenter import (
    QuestionFigureLibraryPresenterMixin,
)
from src.ui.panels.assets.question_library_master_version_presenter import (
    QuestionFigureLibraryMasterVersionPresenterMixin,
)
from src.ui.panels.assets.responsive_layout_presenter import ResponsiveLayoutPresenterMixin
from src.ui.panels.assets.scene_spec_presenter import SceneSpecPresenterMixin
from src.ui.panels.assets.section_shell_presenter import SectionShellPresenterMixin
from src.ui.panels.assets.section_summary_presenter import SectionSummaryPresenterMixin
from src.ui.panels.assets.theme_presenter import ThemePresenterMixin
from src.ui.panels.assets_panel import AssetsPanel


ROOT = Path(__file__).resolve().parents[1]

def _snake(*parts: str) -> str:
    return "_".join(parts)


DELETED_CAPABILITY_TOKENS = (
    _snake("non", "question", "asset", "family"),
    _snake("remote", "writeback"),
    _snake("remote", "asset", "auth"),
    _snake("enterprise", "auth"),
    _snake("signed", "url"),
    _snake("external", "permission"),
    _snake("master", "registry"),
    _snake("registry", "sync"),
    _snake("subscription", "lock"),
    _snake("subscription", "change"),
    _snake("subscription", "drift"),
    _snake("failure", "recovery"),
    _snake("persistent", "worker"),
    _snake("durable", "worker"),
    _snake("sla", "center"),
    _snake("download", "remote", "asset", "preview", "image"),
    "".join(("REMOTE", "_WRITEBACK", "_TASK", "_POLICY", "_KEYS")),
)

DELETED_IMPORT_FIELD_FRAGMENTS = (
    "registrysync",
    "subscriptionlock",
    "subscriptionchange",
    "authrenewal",
    "authrefresh",
    "tokenrefresh",
    "oauthrefresh",
    "ssorefresh",
    "approvalstatus",
    "permissionscope",
    "reneweddownload",
    "refresheddownload",
    "downloadpath",
    "downloadurl",
    "remoteurl",
    "asseturl",
    "sourceurl",
    "originalurl",
    "thumbnailurl",
    "thumbnailremoteurl",
    "remotethumbnailpath",
    "remotethumbnailcachepath",
    "remotethumbnailurl",
    "previewurl",
    "remotepreviewurl",
    "assetpreviewurl",
    "authmode",
    "authtype",
    "authprovider",
    "requiredauth",
    "authentication",
    "remoteauthmode",
)

LOCAL_ASSET_METADATA_KEYS = {
    "asset_id",
    "asset_version",
    "asset_etag",
    "cache_path",
}

SECTION_SHELL_METHODS = {
    "_build_section_navigation",
    "_build_section_pages",
    "_register_detail_cards",
    "_connect_signals",
    "_on_section_selected",
    "_sync_current_section_geometry",
}

FIELD_STATUS_METHODS = {
    "_refresh_field_statuses",
    "_refresh_unknown_field_suggestions",
    "_add_unknown_placeholder_field",
}

FIELD_EDITOR_STATE_METHODS = {
    "_on_structured_field_changed",
    "_on_more_fields_changed",
    "_editor_fields",
    "_set_structured_fields",
}

ASSET_COLLECTION_STATE_METHODS = {
    "_asset_items_for_profile",
    "_current_asset_items",
    "_current_asset_metadata",
    "_image_rules_for_asset_items",
}

ASSET_SLOT_STATUS_METHODS = {
    "_refresh_asset_slot_statuses",
    "_refresh_attachment_role_statuses",
    "_set_asset_thumbnail",
}

ASSET_FILE_OPERATION_METHODS = {
    "_path_for_asset_slot",
    "_select_asset_file",
    "_select_attachment_file",
    "_attachment_role_spec",
    "_apply_asset_slot_path",
    "_clear_asset_file",
    "_clear_attachment_file",
    "_show_asset_slot_path",
    "_open_asset_slot_path",
    "_open_attachment_path",
    "_open_file_path",
}

PREVIEW_STATE_METHODS = {
    "_setup_placeholder_preview_card",
    "_toggle_preview_filter",
    "_on_preview_auto_match",
    "_on_document_loaded",
    "_placeholder_source_path",
    "_scanned_placeholders",
    "_current_preview_state",
    "_missing_attachment_roles",
    "_unmatched_placeholders",
    "_placeholder_preview_rows",
}

MATERIAL_CONTEXT_APPLICATION_METHODS = {
    "_setup_generation_actions_card",
    "material_context",
    "load_mapping_from_path",
    "_apply_current_profile",
    "_open_document_generation",
    "_apply_mapping_payload",
    "_on_material_context_changed",
    "_set_editor_values",
}

ARCHIVE_STATE_METHODS = {
    "current_archive",
    "set_archive",
    "save_archive_to_path",
    "load_archive_from_path",
}

ARCHIVE_SETUP_METHODS = {
    "_setup_archive_overview_card",
}

BATCH_PROFILE_IMPORT_METHODS = {
    "_setup_batch_profile_output_card",
    "load_batch_profiles_from_path",
}

PROFILE_STATE_METHODS = {
    "_selected_profile",
}

PROFILE_EDITOR_SETUP_METHODS = {
    "_setup_profile_editor_card",
}

RESPONSIVE_EVENT_METHODS = {
    "resizeEvent",
    "eventFilter",
}

SCENE_SPEC_APPLICATION_METHODS = {
    "_on_scene_changed",
}

SECTION_SUMMARY_METHODS = {
    "_refresh_summary",
    "_refresh_section_cards",
    "_refresh_section_summary_cards",
}

THEME_METHODS = {
    "_apply_theme",
}

QUESTION_FIGURE_REPAIR_ACTION_METHODS = {
    "current_question_figure_repair_audit_records",
    "revert_question_figure_repair_audit_record",
    "_select_question_figure_library_issue_question_row",
    "_select_question_figure_item_file",
    "_replace_question_figure_item_path",
    "apply_question_figure_repair_candidate",
    "_record_question_figure_repair_application",
    "_record_question_figure_repair_rollback",
}

QUESTION_FIGURE_MASTER_VERSION_METHODS = {
    "_setup_question_figure_library_master_version_table",
}

QUESTION_FIGURE_HISTORY_METHODS = {
    "_setup_question_figure_library_version_history_table",
}

QUESTION_FIGURE_ISSUE_METHODS = {
    "_setup_question_figure_library_issue_table",
}

QUESTION_FIGURE_LIBRARY_METHODS = {
    "_setup_question_figure_library_card",
}

QUESTION_FIGURE_ITEMS_METHODS = {
    "_setup_question_figure_items_table",
}

IMAGE_INVENTORY_SETUP_METHODS = {
    "_setup_image_inventory_card",
}

REMOVED_ASSETS_PANEL_WRAPPER_METHODS = {
    "_add_card_header",
}


def _app():
    return QApplication.instance() or QApplication([])


def _module_identifier_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _class_method_call_names(path: Path, class_name: str, method_name: str) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                names: set[str] = set()
                for child in ast.walk(item):
                    if not isinstance(child, ast.Call):
                        continue
                    if isinstance(child.func, ast.Attribute):
                        names.add(child.func.attr)
                    elif isinstance(child.func, ast.Name):
                        names.add(child.func.id)
                return names
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def _class_methods(path: Path, class_name: str) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
            }
    raise AssertionError(f"{class_name} not found in {path}")


def test_panel_registry_creates_assets_panel_shell():
    _app()
    panel = create_panel("assets", PanelBridge())
    try:
        spec = next(item for item in OPTIONAL_PANEL_SPECS if item.id == "assets")

        assert isinstance(panel, AssetsPanel)
        assert spec.icon == "package"
        assert panel.objectName() == "AssetsPanel"
        assert isinstance(panel._shell, MasterDetailShell)
        assert panel._section_nav.item_count == len(specs.ASSETS_SECTION_SPECS)
        assert "advanced" not in panel._section_nav_cards
        assert "advanced" not in panel._section_pages
        assert not hasattr(panel, "_advanced_card")
        assert "preview" not in panel._section_nav_cards
        assert "batch" not in panel._section_nav_cards
        assert "io" not in panel._section_nav_cards
        assert "io" not in panel._section_pages
    finally:
        panel.close()


def test_images_page_starts_with_rules_then_inventory_and_resets_scroll_offset():
    app = _app()
    panel = create_panel("assets", PanelBridge())
    try:
        panel.resize(1200, 800)
        panel.show()
        app.processEvents()

        images_layout = panel._section_layouts["images"]
        images_summary = panel._section_summary_cards["images"]
        assert images_summary.isHidden()
        assert images_layout.indexOf(images_summary) == -1
        assert images_layout.indexOf(panel._image_rules_card) == 0
        assert images_layout.indexOf(panel._image_card) == 1
        assert panel._image_rules_card._title_label.text() == "图片规则"
        image_actions = panel._material_persistence_actions["images"]
        assert panel._image_rules_card._header_actions_layout.indexOf(image_actions) >= 0
        assert panel._image_card._header_actions_layout.indexOf(image_actions) == -1
        assert panel._image_card._title_label.text() == "图片资料"
        assert panel._card_section_ids[panel._image_rules_card] == "images"
        assert panel._card_section_ids[panel._image_card] == "images"

        scroll_bar = panel._detail_scroll.verticalScrollBar()
        scroll_bar.setRange(0, 500)
        scroll_bar.setValue(180)
        panel._on_section_selected("images")

        assert scroll_bar.value() == 0
        assert panel._asset_slots_layout.contentsMargins().top() >= 6
    finally:
        panel.close()
        app.processEvents()


def test_assets_panel_delegates_section_shell_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/section_shell_presenter.py",
        "SectionShellPresenterMixin",
    )

    assert issubclass(AssetsPanel, SectionShellPresenterMixin)
    assert SECTION_SHELL_METHODS <= presenter_methods
    assert not (SECTION_SHELL_METHODS & panel_methods)


def test_assets_panel_delegates_field_status_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/field_status_presenter.py",
        "FieldStatusPresenterMixin",
    )

    assert issubclass(AssetsPanel, FieldStatusPresenterMixin)
    assert FIELD_STATUS_METHODS <= presenter_methods
    assert not (FIELD_STATUS_METHODS & panel_methods)


def test_assets_panel_delegates_field_editor_state_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/field_editor_state_presenter.py",
        "FieldEditorStatePresenterMixin",
    )

    assert issubclass(AssetsPanel, FieldEditorStatePresenterMixin)
    assert FIELD_EDITOR_STATE_METHODS <= presenter_methods
    assert not (FIELD_EDITOR_STATE_METHODS & panel_methods)


def test_assets_panel_delegates_asset_collection_state_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/asset_collection_state_presenter.py",
        "AssetCollectionStatePresenterMixin",
    )

    assert issubclass(AssetsPanel, AssetCollectionStatePresenterMixin)
    assert ASSET_COLLECTION_STATE_METHODS <= presenter_methods
    assert not (ASSET_COLLECTION_STATE_METHODS & panel_methods)


def test_assets_panel_delegates_asset_slot_status_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/asset_slot_status_presenter.py",
        "AssetSlotStatusPresenterMixin",
    )

    assert issubclass(AssetsPanel, AssetSlotStatusPresenterMixin)
    assert ASSET_SLOT_STATUS_METHODS <= presenter_methods
    assert not (ASSET_SLOT_STATUS_METHODS & panel_methods)


def test_assets_panel_delegates_asset_file_operations_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/asset_file_operations_presenter.py",
        "AssetFileOperationsPresenterMixin",
    )

    assert issubclass(AssetsPanel, AssetFileOperationsPresenterMixin)
    assert ASSET_FILE_OPERATION_METHODS <= presenter_methods
    assert not (ASSET_FILE_OPERATION_METHODS & panel_methods)


def test_assets_panel_delegates_archive_state_to_archive_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/archive_presenter.py",
        "ArchivePresenterMixin",
    )

    assert issubclass(AssetsPanel, ArchivePresenterMixin)
    assert ARCHIVE_STATE_METHODS <= presenter_methods
    assert not (ARCHIVE_STATE_METHODS & panel_methods)


def test_assets_panel_delegates_archive_setup_to_archive_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/archive_presenter.py",
        "ArchivePresenterMixin",
    )

    assert issubclass(AssetsPanel, ArchivePresenterMixin)
    assert ARCHIVE_SETUP_METHODS <= presenter_methods
    assert not (ARCHIVE_SETUP_METHODS & panel_methods)


def test_assets_panel_delegates_batch_profile_import_to_batch_output_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/batch_output_presenter.py",
        "BatchOutputPresenterMixin",
    )

    assert issubclass(AssetsPanel, BatchOutputPresenterMixin)
    assert BATCH_PROFILE_IMPORT_METHODS <= presenter_methods
    assert not (BATCH_PROFILE_IMPORT_METHODS & panel_methods)


def test_assets_panel_delegates_preview_state_to_preview_table_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/preview_table_presenter.py",
        "PreviewTablePresenterMixin",
    )

    assert issubclass(AssetsPanel, PreviewTablePresenterMixin)
    assert PREVIEW_STATE_METHODS <= presenter_methods
    assert not (PREVIEW_STATE_METHODS & panel_methods)


def test_assets_panel_delegates_material_context_application_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/material_context_application_presenter.py",
        "MaterialContextApplicationPresenterMixin",
    )

    assert issubclass(AssetsPanel, MaterialContextApplicationPresenterMixin)
    assert MATERIAL_CONTEXT_APPLICATION_METHODS <= presenter_methods
    assert not (MATERIAL_CONTEXT_APPLICATION_METHODS & panel_methods)


def test_assets_panel_delegates_profile_state_to_profile_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/profile_presenter.py",
        "ProfilePresenterMixin",
    )

    assert issubclass(AssetsPanel, ProfilePresenterMixin)
    assert PROFILE_STATE_METHODS <= presenter_methods
    assert not (PROFILE_STATE_METHODS & panel_methods)


def test_assets_panel_delegates_profile_editor_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/profile_editor_presenter.py",
        "ProfileEditorPresenterMixin",
    )

    assert issubclass(AssetsPanel, ProfileEditorPresenterMixin)
    assert PROFILE_EDITOR_SETUP_METHODS <= presenter_methods
    assert not (PROFILE_EDITOR_SETUP_METHODS & panel_methods)


def test_assets_panel_delegates_responsive_events_to_responsive_layout_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/responsive_layout_presenter.py",
        "ResponsiveLayoutPresenterMixin",
    )

    assert issubclass(AssetsPanel, ResponsiveLayoutPresenterMixin)
    assert RESPONSIVE_EVENT_METHODS <= presenter_methods
    assert not (RESPONSIVE_EVENT_METHODS & panel_methods)


def test_assets_panel_delegates_scene_spec_application_to_scene_spec_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/scene_spec_presenter.py",
        "SceneSpecPresenterMixin",
    )

    assert issubclass(AssetsPanel, SceneSpecPresenterMixin)
    assert SCENE_SPEC_APPLICATION_METHODS <= presenter_methods
    assert not (SCENE_SPEC_APPLICATION_METHODS & panel_methods)


def test_assets_panel_delegates_section_summary_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/section_summary_presenter.py",
        "SectionSummaryPresenterMixin",
    )

    assert issubclass(AssetsPanel, SectionSummaryPresenterMixin)
    assert SECTION_SUMMARY_METHODS <= presenter_methods
    assert not (SECTION_SUMMARY_METHODS & panel_methods)


def test_assets_panel_delegates_theme_application_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/theme_presenter.py",
        "ThemePresenterMixin",
    )

    assert issubclass(AssetsPanel, ThemePresenterMixin)
    assert THEME_METHODS <= presenter_methods
    assert not (THEME_METHODS & panel_methods)


def test_assets_theme_application_stays_grouped_by_widget_family():
    calls = _class_method_call_names(
        ROOT / "src/ui/panels/assets/theme_presenter.py",
        "ThemePresenterMixin",
        "_apply_theme",
    )

    assert {
        "_apply_shell_theme",
        "_apply_generate_action_icons",
        "_apply_text_label_theme",
        "_apply_form_input_theme",
        "_apply_asset_row_theme",
        "_apply_asset_icon_button_sizing",
        "_apply_profile_list_theme",
        "_apply_command_button_theme",
    } <= calls


def test_assets_section_summary_stays_state_driven():
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/section_summary_presenter.py",
        "SectionSummaryPresenterMixin",
    )
    refresh_calls = _class_method_call_names(
        ROOT / "src/ui/panels/assets/section_summary_presenter.py",
        "SectionSummaryPresenterMixin",
        "_refresh_summary",
    )
    summary_card_calls = _class_method_call_names(
        ROOT / "src/ui/panels/assets/section_summary_presenter.py",
        "SectionSummaryPresenterMixin",
        "_refresh_section_summary_cards",
    )

    assert {
        "_build_section_summary_state",
        "_section_summary_item_groups",
        "_generate_summary_items",
        "_field_summary_items",
        "_image_summary_items",
        "_preview_summary_items",
        "_batch_summary_items",
    } <= presenter_methods
    assert "_build_section_summary_state" in refresh_calls
    assert "_section_summary_item_groups" in summary_card_calls


def test_assets_panel_delegates_question_figure_repair_actions_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/question_figure_repair_actions_presenter.py",
        "QuestionFigureRepairActionsPresenterMixin",
    )

    assert issubclass(AssetsPanel, QuestionFigureRepairActionsPresenterMixin)
    assert QUESTION_FIGURE_REPAIR_ACTION_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_REPAIR_ACTION_METHODS & panel_methods)


def test_assets_panel_does_not_reintroduce_question_figure_shared_cache_presenter():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")

    assert not (ROOT / "src/ui/panels/assets/cache_presenter.py").exists()
    assert "_setup_question_figure_shared_cache_tables" not in panel_methods
    assert not any(
        base.__name__ == "QuestionFigureSharedCachePresenterMixin"
        for base in AssetsPanel.__mro__
    )


def test_assets_panel_delegates_master_version_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/question_library_master_version_presenter.py",
        "QuestionFigureLibraryMasterVersionPresenterMixin",
    )

    assert issubclass(AssetsPanel, QuestionFigureLibraryMasterVersionPresenterMixin)
    assert QUESTION_FIGURE_MASTER_VERSION_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_MASTER_VERSION_METHODS & panel_methods)


def test_assets_panel_delegates_version_history_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/question_library_history_presenter.py",
        "QuestionFigureLibraryHistoryPresenterMixin",
    )

    assert issubclass(AssetsPanel, QuestionFigureLibraryHistoryPresenterMixin)
    assert QUESTION_FIGURE_HISTORY_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_HISTORY_METHODS & panel_methods)


def test_assets_panel_delegates_issue_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/question_library_issue_presenter.py",
        "QuestionFigureLibraryIssuePresenterMixin",
    )

    assert issubclass(AssetsPanel, QuestionFigureLibraryIssuePresenterMixin)
    assert QUESTION_FIGURE_ISSUE_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_ISSUE_METHODS & panel_methods)


def test_assets_panel_delegates_library_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/question_library_presenter.py",
        "QuestionFigureLibraryPresenterMixin",
    )

    assert issubclass(AssetsPanel, QuestionFigureLibraryPresenterMixin)
    assert QUESTION_FIGURE_LIBRARY_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_LIBRARY_METHODS & panel_methods)


def test_assets_panel_delegates_question_figure_items_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/question_figures_presenter.py",
        "QuestionFigureItemsPresenterMixin",
    )

    assert issubclass(AssetsPanel, QuestionFigureItemsPresenterMixin)
    assert QUESTION_FIGURE_ITEMS_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_ITEMS_METHODS & panel_methods)


def test_assets_panel_delegates_image_inventory_setup_to_presenter_mixin():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        ROOT / "src/ui/panels/assets/image_inventory_presenter.py",
        "ImageInventorySetupPresenterMixin",
    )

    assert issubclass(AssetsPanel, ImageInventorySetupPresenterMixin)
    assert IMAGE_INVENTORY_SETUP_METHODS <= presenter_methods
    assert not (IMAGE_INVENTORY_SETUP_METHODS & panel_methods)


def test_assets_panel_trivial_wrapper_methods_stay_removed():
    panel_methods = _class_methods(ROOT / "src/ui/panels/assets_panel.py", "AssetsPanel")
    panel_names = _module_identifier_names(ROOT / "src/ui/panels/assets_panel.py")

    assert not (REMOVED_ASSETS_PANEL_WRAPPER_METHODS & panel_methods)
    assert not (REMOVED_ASSETS_PANEL_WRAPPER_METHODS & panel_names)


def test_material_persistence_uses_owned_coordinators_instead_of_an_mro_mixin():
    base_names = {base.__name__ for base in AssetsPanel.__bases__}
    archive_names = _module_identifier_names(
        ROOT / "src/ui/panels/assets/archive_presenter.py"
    )

    assert "PersistencePresenterMixin" not in base_names
    assert len(AssetsPanel.__bases__) == 33
    assert {
        "_current_archive_entry",
        "_current_archive_path",
        "_persisted_archive_snapshot",
        "_prepared_material_changes",
    }.isdisjoint(archive_names)

    panel = AssetsPanel(PanelBridge())
    try:
        assert isinstance(panel._material_persistence, MaterialPersistenceCoordinator)
        assert isinstance(
            panel._material_change_transaction,
            MaterialChangeTransactionCoordinator,
        )
        assert {
            "_current_archive_entry",
            "_current_archive_path",
            "_persisted_archive_snapshot",
            "_prepared_material_changes",
            "_material_persistence_actions",
        }.isdisjoint(panel.__dict__)
        assert panel._current_archive_entry is panel._material_persistence.current_entry
        assert (
            panel._prepared_material_changes
            is panel._material_change_transaction.prepared_state
        )
    finally:
        panel.close()


def test_deleted_enterprise_remote_identifiers_do_not_return_to_assets_panel():
    names = _module_identifier_names(ROOT / "src/ui/panels/assets_panel.py")

    for token in DELETED_CAPABILITY_TOKENS:
        assert all(token not in name for name in names), token


def test_deleted_enterprise_remote_identifiers_do_not_return_to_services():
    service_paths = (
        ROOT / "src/services/material_assets/question_library.py",
        ROOT / "src/services/material_assets/question_figures.py",
        ROOT / "src/services/material_assets/__init__.py",
        ROOT / "src/services/material_assets/word_docx_recovery.py",
    )

    for path in service_paths:
        names = _module_identifier_names(path)
        for token in DELETED_CAPABILITY_TOKENS:
            assert all(token not in name for name in names), f"{path}:{token}"


def test_enterprise_boundary_only_describes_retained_local_or_read_only_groups():
    keys = {boundary.key for boundary in enterprise_boundary.ASSET_CAPABILITY_BOUNDARIES}
    decisions = {boundary.decision for boundary in enterprise_boundary.ASSET_CAPABILITY_BOUNDARIES}

    assert {"local_question_figures", "local_question_audit"} <= keys
    assert "lightweight_shared_cache" not in keys
    assert "remote_preview_download" not in keys
    assert "remote_url_metadata_compatibility" not in keys
    assert "freeze" not in decisions
    assert "delete_candidate" not in decisions
    for token in DELETED_CAPABILITY_TOKENS:
        assert enterprise_boundary.boundary_by_key(token) is None


def test_batch_import_metadata_aliases_reject_deleted_enterprise_remote_fields():
    aliases = {suffix for suffix, _metadata_key in batch_import._ASSET_METADATA_IMPORT_SUFFIXES}
    metadata_keys = {metadata_key for _suffix, metadata_key in batch_import._ASSET_METADATA_IMPORT_SUFFIXES}

    assert LOCAL_ASSET_METADATA_KEYS <= metadata_keys
    for fragment in DELETED_IMPORT_FIELD_FRAGMENTS:
        assert all(fragment not in alias for alias in aliases), fragment


def test_active_remote_preview_auth_is_not_exposed():
    panel_names = _module_identifier_names(ROOT / "src/ui/panels/assets_panel.py")
    service_names = _module_identifier_names(ROOT / "src/services/material_assets/question_figures.py")
    service_source = (ROOT / "src/services/material_assets/question_figures.py").read_text(
        encoding="utf-8"
    )

    assert not hasattr(specs, "REMOTE_ASSET_AUTH_FIELD_KEYS")
    assert not hasattr(specs, "REMOTE_ASSET_PREVIEW_MAX_BYTES")
    assert not (ROOT / "src/ui/panels/assets/auth.py").exists()
    assert all("remote_asset_auth" not in name for name in panel_names)
    assert "download_remote_asset_preview_image" not in service_names
    assert "urlopen" not in service_source


def test_assets_summary_refresh_updates_local_question_figure_projections():
    calls = _class_method_call_names(
        ROOT / "src/ui/panels/assets/section_summary_presenter.py",
        "SectionSummaryPresenterMixin",
        "_refresh_summary",
    )

    assert {
        "_refresh_asset_slot_statuses",
        "_refresh_question_figure_items_table",
        "_refresh_question_figure_library_table",
        "_refresh_question_figure_library_issue_table",
        "_refresh_question_figure_library_version_history_table",
        "_refresh_question_figure_library_master_version_table",
    } <= calls
    assert "_refresh_question_figure_shared_cache_dirs_table" not in calls
