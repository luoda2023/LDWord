"""Assets panel for execution-time entity fields and material context."""

from __future__ import annotations

import base64
import json
import posixpath
import shutil
from datetime import datetime, timezone
import re
from typing import Any, Sequence
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, unquote, urlparse
import zipfile

from docx import Document

from src.config.entity import EntityProfile
from src.config.materials import (
    AssetItem,
)
from src.qt_api import (
    QCheckBox,
    QDialog,
    QFrame,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPixmap,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.dialogs import confirm, input_text
from src.shared.ui.master_detail_shell import MasterDetailShell
from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.detail_geometry import ScrollableDetailGeometrySync
from src.shared.ui.template_summary_card import TemplateSummaryCard
from src.shared.ui.theme import bind_theme
from src.shared.ui.toast import Toast
from src.ui.adapters.field_display_names import navigation_issue_hint
from src.ui.base_panel import BasePanel
from src.ui.bridge import navigation_intent_value
from src.ui.panels.assets.archive_presenter import ArchivePresenterMixin
from src.ui.panels.assets.asset_collection_state_presenter import AssetCollectionStatePresenterMixin
from src.ui.panels.assets.asset_file_operations_presenter import AssetFileOperationsPresenterMixin
from src.ui.panels.assets.asset_slot_status_presenter import AssetSlotStatusPresenterMixin
from src.ui.panels.assets.asset_rows_presenter import AssetRowsPresenterMixin
from src.ui.panels.assets.batch_output_presenter import BatchOutputPresenterMixin
from src.ui.panels.assets.field_editor_state_presenter import FieldEditorStatePresenterMixin
from src.ui.panels.assets.field_status_presenter import FieldStatusPresenterMixin
from src.ui.panels.assets.image_inventory_presenter import ImageInventorySetupPresenterMixin
from src.ui.panels.assets.image_preview_presenter import ImagePreviewPresenterMixin
from src.ui.panels.assets.material_context_application_presenter import (
    MaterialContextApplicationPresenterMixin,
)
from src.ui.panels.assets.material_repair_navigation_presenter import MaterialRepairNavigationMixin
from src.ui.panels.assets.material_settings_presenter import MaterialSettingsPresenterMixin
from src.ui.panels.assets.preview_table_presenter import PreviewTablePresenterMixin
from src.ui.panels.assets.profile_editor_presenter import ProfileEditorPresenterMixin
from src.ui.panels.assets.question_figures_presenter import QuestionFigureItemsPresenterMixin
from src.ui.panels.assets.question_figure_repair_actions_presenter import (
    QuestionFigureRepairActionsPresenterMixin,
)
from src.ui.panels.assets.question_library_history_presenter import (
    QuestionFigureLibraryHistoryPresenterMixin,
)
from src.ui.panels.assets.question_library_issue_presenter import (
    QuestionFigureLibraryIssuePresenterMixin,
)
from src.ui.panels.assets.question_library_master_version_presenter import (
    QuestionFigureLibraryMasterVersionPresenterMixin,
)
from src.ui.panels.assets.question_library_presenter import QuestionFigureLibraryPresenterMixin
from src.ui.panels.assets.responsive_layout_presenter import ResponsiveLayoutPresenterMixin
from src.ui.panels.assets.scene_spec_presenter import SceneSpecPresenterMixin
from src.ui.panels.assets.section_shell_presenter import SectionShellPresenterMixin
from src.ui.panels.assets.section_summary_presenter import SectionSummaryPresenterMixin
from src.ui.panels.assets.theme_presenter import ThemePresenterMixin
from src.ui.panels.assets.profile_presenter import ProfilePresenterMixin
from src.ui.panels.assets import (
    FIELD_SOURCE_IMPORTED_MAPPING,
    AssetsSectionSpec,
    AttachmentRoleSpec,
)
from src.ui.panels.assets.batch_import import (
    _asset_metadata_role_for_import_key,
    _asset_role_for_import_key,
    _cell_text,
    _load_batch_csv_rows,
    _load_batch_excel_rows,
    _load_batch_profiles_from_json,
    _mapping_value,
    _normalized_asset_paths,
    _normalized_profile_fields,
    _parse_question_figure_suffix,
    _profile_from_mapping,
    _profile_item_label,
    _profile_label,
    _profile_role_label,
    _profiles_from_table_rows,
    _question_figure_import_sort_key,
    _question_figure_index_from_base,
    _question_figure_key_from_base,
    _repeated_asset_item_key,
    _repeated_question_figure_metadata_key,
    _repeated_question_figure_path_index,
    _repeated_question_figure_path_key,
    _row_asset_item_payloads,
    _row_asset_metadata,
    _row_asset_paths,
    _row_fields,
    _row_has_values,
    _row_value,
)
from src.ui.panels.assets.fields import (
    _field_key_from_user_text,
    _field_sources_from_imported_keys,
    _looks_like_date,
    _normalized_field_sources,
    _normalized_import_key,
    _parse_fields_text,
)
from src.ui.panels.assets.image_helpers import (
    _asset_role_min_short_side,
    _first_image_path_from_mime,
    _image_quality_text,
    _load_scaled_pixmap,
)
from src.ui.panels.assets.layout_helpers import _chunk_form_rows
from src.ui.panels.assets.items import (
    _normalized_asset_metadata,
)
from src.ui.panels.assets.roles import (
    _asset_slot_supports_alt_text,
    _asset_slot_role_for_token,
)

from src.ui.panels.assets.common import (
    _first_non_empty,
    _metric_float,
    _metric_int,
    _metric_time_label,
    _ui_utc_now_iso,
)
from src.ui.panels.assets.text_helpers import (
    _format_image_rules_text,
    _format_replacements_text,
    _parse_replacements_text,
)
from src.services.material_assets import (
    append_question_figure_repair_audit_record,
    asset_item_alt_text,
    asset_item_cached_path,
    asset_item_library_asset_id,
    asset_item_preview_path,
    asset_item_preview_reference,
    asset_item_source,
    asset_item_thumbnail_path,
    asset_metadata_etag_value,
    asset_metadata_package_id_value,
    asset_metadata_package_label_value,
    asset_metadata_reference_value,
    asset_metadata_updated_at_value,
    asset_metadata_version_value,
    build_question_figure_repair_audit_record,
    build_question_figure_repair_rollback_audit_record,
    available_asset_image_paths,
    deep_repair_docx_xml_media,
    docx_image_content_type,
    docx_image_part_kind,
    docx_image_part_names,
    docx_part_relationships_path,
    json_list_from_record_value,
    parse_question_figure_repair_target,
    question_figure_asset_sort_key,
    question_figure_candidate_list,
    question_figure_collection_summary,
    question_figure_compare_display_name,
    question_figure_compare_index_label,
    question_figure_compare_options,
    question_figure_detail_rows,
    question_figure_item_matches_repair_target,
    question_figure_item_summary,
    question_figure_items,
    question_figure_library_asset_label,
    question_figure_library_metadata_issue_entries,
    question_figure_library_master_version_entries,
    question_figure_library_metadata_change_summary,
    question_figure_library_metadata_history_record,
    question_figure_library_metadata_rollback_record,
    question_figure_library_reference,
    question_figure_library_row_entries,
    question_figure_library_rows,
    question_figure_library_source_label,
    question_figure_library_version_history_entries,
    question_figure_has_library_metadata,
    question_figure_history_changed_fields,
    question_figure_history_fields_label,
    question_figure_history_record_matches_current,
    question_figure_history_record_question_row,
    normalize_docx_relationship_target,
    normalized_asset_item_history_records,
    question_figure_order_value,
    question_figure_payload_matches_item,
    question_figure_master_version_diff_fields,
    question_figure_master_version_diff_summary,
    question_figure_master_version_has_version_statement,
    question_figure_master_version_package_summary,
    question_figure_master_version_status_label,
    question_figure_master_version_summary,
    question_figure_repair_audit_id,
    question_figure_repair_rollback_audit_id,
    question_figure_requires_library_identity,
    question_figure_target_cache_path,
    question_figure_target_label,
    question_figure_target_value,
    read_question_figure_repair_audit_payload,
    resolve_question_figure_repair_audit_dir,
    scan_docx_xml_media,
    set_optional_metadata_value,
    update_docx_content_types,
)

# Legacy module-level exports retained for older tests and imports. New
# assets-panel code should use the public service names imported above.
_append_question_figure_repair_audit_record = append_question_figure_repair_audit_record
_question_figure_repair_audit_dir = resolve_question_figure_repair_audit_dir
_question_figure_repair_audit_id = question_figure_repair_audit_id
_question_figure_repair_audit_record = build_question_figure_repair_audit_record
_question_figure_repair_rollback_audit_id = question_figure_repair_rollback_audit_id
_question_figure_repair_rollback_audit_record = (
    build_question_figure_repair_rollback_audit_record
)
_read_question_figure_repair_audit_payload = read_question_figure_repair_audit_payload
_asset_item_alt_text = asset_item_alt_text
_asset_item_cached_path = asset_item_cached_path
_asset_item_library_asset_id = asset_item_library_asset_id
_asset_item_preview_path = asset_item_preview_path
_asset_item_preview_reference = asset_item_preview_reference
_asset_item_source = asset_item_source
_asset_item_thumbnail_path = asset_item_thumbnail_path
_question_figure_asset_items = question_figure_items
_question_figure_asset_sort_key = question_figure_asset_sort_key
_question_figure_candidate_list = question_figure_candidate_list
_question_figure_collection_summary = question_figure_collection_summary
_question_figure_compare_display_name = question_figure_compare_display_name
_question_figure_compare_index_label = question_figure_compare_index_label
_question_figure_compare_options = question_figure_compare_options
_question_figure_detail_rows = question_figure_detail_rows
_question_figure_item_matches_repair_target = question_figure_item_matches_repair_target
_question_figure_item_summary = question_figure_item_summary
_question_figure_library_asset_label = question_figure_library_asset_label
_question_figure_library_metadata_issue_entries = (
    question_figure_library_metadata_issue_entries
)
_question_figure_library_master_version_entries = (
    question_figure_library_master_version_entries
)
_question_figure_has_library_metadata = question_figure_has_library_metadata
_question_figure_library_reference = question_figure_library_reference
_question_figure_library_row_entries = question_figure_library_row_entries
_question_figure_library_rows = question_figure_library_rows
_question_figure_library_metadata_change_summary = (
    question_figure_library_metadata_change_summary
)
_question_figure_library_metadata_history_record = (
    question_figure_library_metadata_history_record
)
_question_figure_history_changed_fields = question_figure_history_changed_fields
_question_figure_history_fields_label = question_figure_history_fields_label
_question_figure_history_record_matches_current = (
    question_figure_history_record_matches_current
)
_question_figure_history_record_question_row = question_figure_history_record_question_row
_asset_metadata_package_id_value = asset_metadata_package_id_value
_asset_metadata_package_label_value = asset_metadata_package_label_value
_asset_metadata_version_value = asset_metadata_version_value
_asset_metadata_etag_value = asset_metadata_etag_value
_asset_metadata_updated_at_value = asset_metadata_updated_at_value
_asset_metadata_reference_value = asset_metadata_reference_value
_set_optional_metadata_value = set_optional_metadata_value
_question_figure_master_version_diff_fields = question_figure_master_version_diff_fields
_question_figure_master_version_has_version_statement = (
    question_figure_master_version_has_version_statement
)
_question_figure_master_version_package_summary = (
    question_figure_master_version_package_summary
)
_question_figure_master_version_summary = question_figure_master_version_summary
_question_figure_master_version_diff_summary = (
    question_figure_master_version_diff_summary
)
_question_figure_master_version_status_label = (
    question_figure_master_version_status_label
)
_json_list_from_record_value = json_list_from_record_value
_question_figure_library_metadata_rollback_record = (
    question_figure_library_metadata_rollback_record
)
_question_figure_library_source_label = question_figure_library_source_label
_question_figure_library_version_history_entries = (
    question_figure_library_version_history_entries
)
_normalized_asset_item_history_records = normalized_asset_item_history_records
_question_figure_order_value = question_figure_order_value
_question_figure_payload_matches_item = question_figure_payload_matches_item
_question_figure_repair_target_payload = parse_question_figure_repair_target
_question_figure_requires_library_identity = question_figure_requires_library_identity
_question_figure_target_cache_path = question_figure_target_cache_path
_question_figure_target_label = question_figure_target_label
_question_figure_target_value = question_figure_target_value


class _CurrentPageStack(QStackedWidget):
    """QStackedWidget that lets the active detail page define the shell width."""

    def sizeHint(self):  # noqa: N802
        current = self.currentWidget()
        if current is not None:
            return current.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):  # noqa: N802
        current = self.currentWidget()
        if current is not None:
            return current.minimumSizeHint()
        return super().minimumSizeHint()


class AssetsPanel(
    ArchivePresenterMixin,
    AssetCollectionStatePresenterMixin,
    AssetFileOperationsPresenterMixin,
    AssetSlotStatusPresenterMixin,
    AssetRowsPresenterMixin,
    BatchOutputPresenterMixin,
    FieldEditorStatePresenterMixin,
    FieldStatusPresenterMixin,
    ImageInventorySetupPresenterMixin,
    ImagePreviewPresenterMixin,
    MaterialContextApplicationPresenterMixin,
    MaterialSettingsPresenterMixin,
    MaterialRepairNavigationMixin,
    PreviewTablePresenterMixin,
    ProfileEditorPresenterMixin,
    ProfilePresenterMixin,
    QuestionFigureItemsPresenterMixin,
    QuestionFigureRepairActionsPresenterMixin,
    QuestionFigureLibraryPresenterMixin,
    QuestionFigureLibraryHistoryPresenterMixin,
    QuestionFigureLibraryIssuePresenterMixin,
    QuestionFigureLibraryMasterVersionPresenterMixin,
    ResponsiveLayoutPresenterMixin,
    SceneSpecPresenterMixin,
    SectionShellPresenterMixin,
    SectionSummaryPresenterMixin,
    ThemePresenterMixin,
    BasePanel,
):
    """Manage the current entity/profile payload used by quick fill execution."""

    panel_title = "璧勬枡鍖?"
    panel_icon = "package"

    def _setup_ui(self) -> None:
        self.setObjectName("AssetsPanel")
        self._profiles: list[EntityProfile] = [EntityProfile()]
        self._current_profile_index = 0
        self._syncing_profile_list = False
        self._syncing_output_naming = False
        self._suppress_material_context_sync = False
        self._field_inputs: dict[str, QLineEdit] = {}
        self._field_status_labels: dict[str, QLabel] = {}
        self._imported_field_keys: set[str] = set()
        self._preserve_import_sources = False
        self._asset_paths: dict[str, str] = {}
        self._asset_metadata: dict[str, dict[str, str]] = {}
        self._asset_item_payloads: list[dict[str, object]] = []
        self._question_figure_repair_audit_records: list[dict[str, object]] = []
        self._asset_slot_rows: dict[str, QFrame] = {}
        self._asset_slot_choose_buttons: dict[str, QPushButton] = {}
        self._asset_slot_thumbnail_labels: dict[str, QLabel] = {}
        self._asset_slot_status_labels: dict[str, QLabel] = {}
        self._asset_slot_alt_text_inputs: dict[str, QLineEdit] = {}
        self._asset_slot_view_buttons: dict[str, QPushButton] = {}
        self._asset_slot_open_buttons: dict[str, QPushButton] = {}
        self._asset_slot_clear_buttons: dict[str, QPushButton] = {}
        self._attachment_role_rows: dict[str, QFrame] = {}
        self._attachment_role_status_labels: dict[str, QLabel] = {}
        self._attachment_role_choose_buttons: dict[str, QPushButton] = {}
        self._attachment_role_open_buttons: dict[str, QPushButton] = {}
        self._attachment_role_clear_buttons: dict[str, QPushButton] = {}
        self._current_image_preview_path = ""
        self._current_image_preview_display_name = ""
        self._full_image_preview_dialog: QDialog | None = None
        self._full_image_preview_label: QLabel | None = None
        self._full_image_preview_scroll: QScrollArea | None = None
        self._full_image_preview_original_pixmap: QPixmap | None = None
        self._full_image_preview_zoom = 1.0
        self._full_image_preview_zoom_label: QLabel | None = None
        self._full_image_preview_zoom_out_btn: QPushButton | None = None
        self._full_image_preview_zoom_in_btn: QPushButton | None = None
        self._full_image_preview_zoom_reset_btn: QPushButton | None = None
        self._full_image_preview_fit_btn: QPushButton | None = None
        self._full_image_preview_compare_btn: QPushButton | None = None
        self._full_image_preview_mark_issue_btn: QPushButton | None = None
        self._full_image_preview_compare_panel: QWidget | None = None
        self._full_image_preview_compare_scroll: QScrollArea | None = None
        self._full_image_preview_compare_label: QLabel | None = None
        self._full_image_preview_compare_title: QLabel | None = None
        self._full_image_preview_compare_combo: QComboBox | None = None
        self._current_image_preview_question_figure_row = -1
        self._current_image_preview_compare_reference = ""
        self._current_image_preview_compare_source = ""
        self._current_image_preview_compare_display_name = ""
        self._current_image_preview_compare_options: list[dict[str, str]] = []
        self._unknown_placeholder_buttons: dict[str, QPushButton] = {}
        self._preview_action_buttons: dict[str, QPushButton] = {}
        self._preview_only_issues = False
        self._current_document_path = self.bridge.current_document_path()
        self._placeholder_cache_path = ""
        self._placeholder_cache_mtime: float | None = None
        self._placeholder_cache_tokens: list[str] = []
        self._active_attention_card: Card | None = None
        self._attention_pulse_card: Card | None = None
        self._active_section_id = "generate"
        self._default_required_fields = self._required_fields_from_scene(
            self.bridge.current_scene()
        )
        self._asset_slot_specs = self._asset_slots_from_scene(self.bridge.current_scene())
        self._attachment_role_specs = self._attachment_roles_from_scene(self.bridge.current_scene())
        self._section_nav_cards: dict[str, NavigationCard] = {}
        self._section_scrolls: dict[str, QScrollArea] = {}
        self._section_contents: dict[str, QWidget] = {}
        self._section_layouts: dict[str, QVBoxLayout] = {}
        self._section_pages: dict[str, QWidget] = {}
        self._section_summary_cards: dict[str, TemplateSummaryCard] = {}
        self._card_section_ids: dict[Card, str] = {}
        self._return_navigation_intent: dict[str, object] | None = None

        self._shell = MasterDetailShell(
            self,
            panel_name="AssetsPanel",
            nav_object_name="assets_section_rail",
            detail_object_name="assets_detail_scroll",
            detail_content_object_name="assets_detail_content",
        )
        self._outer_layout = self._shell.layout
        self._section_nav = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_shell = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout
        self._detail_geometry = ScrollableDetailGeometrySync(
            self._detail_shell,
            self._detail_layout,
            self._detail_scroll,
            parent=self,
        )

        self._title = QLabel("璧勬枡鍖?", self._detail_shell)
        self._title.setVisible(False)
        self._summary = QLabel(self._detail_shell)
        self._summary.setWordWrap(True)
        self._summary.setVisible(False)

        self._return_bar = QWidget(self._detail_shell)
        self._return_bar.setObjectName("assets_return_bar")
        return_layout = QHBoxLayout(self._return_bar)
        return_layout.setContentsMargins(10, 6, 10, 6)
        return_layout.setSpacing(8)
        self._return_label = QLabel("浠庢墽琛岄棶棰樿繘鍏?", self._return_bar)
        self._return_btn = QPushButton("杩斿洖鎵ц", self._return_bar)
        self._return_btn.setCursor(Qt.PointingHandCursor)
        self._return_btn.clicked.connect(self._navigate_return_target)
        return_layout.addWidget(self._return_label, 1)
        return_layout.addWidget(self._return_btn, 0)
        self._return_bar.setVisible(False)
        self._detail_layout.addWidget(self._return_bar)

        self._detail_stack = _CurrentPageStack(self._detail_shell)
        self._detail_stack.setObjectName("assets_detail_stack")
        self._detail_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._detail_layout.addWidget(self._detail_stack, 1)

        self._build_section_navigation()
        self._build_section_pages()

        self._setup_archive_overview_card()

        self._setup_generation_actions_card()

        self._setup_import_export_card()

        self._setup_profile_editor_card()

        self._setup_image_inventory_card()

        self._setup_placeholder_preview_card()

        self._setup_batch_profile_output_card()

        self._setup_material_settings_card()
        for layout in self._section_layouts.values():
            layout.addStretch(1)
        self._register_detail_cards()
        self._section_nav.select_card("generate")

        self._reload_profile_list(select_index=0)
        self._refresh_summary()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
