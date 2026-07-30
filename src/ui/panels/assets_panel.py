"""Assets panel for execution-time entity fields and material context."""

from __future__ import annotations

from collections.abc import Mapping
import weakref


from src.config.entity import EntityArchive, EntityProfile
from src.config.material_package_library import MaterialPackageLibraryEntry
from src.qt_api import (
    QFileSystemWatcher,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.card import Card
from src.shared.ui.master_detail_shell import MasterDetailShell
from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.official_field_value_edit import OfficialFieldValueEdit
from src.shared.ui.preview_dialog import ImagePreviewDialog
from src.shared.ui.projected_text_edit import ProjectedTextEdit
from src.shared.ui.detail_geometry import ScrollableDetailGeometrySync
from src.shared.ui.template_summary_card import TemplateSummaryCard
from src.shared.ui.theme import bind_theme
from src.ui.base_panel import BasePanel
from src.ui.panels.assets.archive_presenter import ArchivePresenterMixin
from src.ui.panels.assets.attachment_inventory_presenter import (
    AttachmentInventorySetupPresenterMixin,
)
from src.ui.panels.assets.attachment_preparation_presenter import (
    AttachmentPreparationPresenterMixin,
)
from src.ui.panels.assets.asset_collection_state_presenter import AssetCollectionStatePresenterMixin
from src.ui.panels.assets.asset_group_rows_presenter import AssetGroupRowsPresenterMixin
from src.ui.panels.assets.asset_file_operations_presenter import AssetFileOperationsPresenterMixin
from src.ui.panels.assets.asset_slot_status_presenter import AssetSlotStatusPresenterMixin
from src.ui.panels.assets.asset_rows_presenter import AssetRowsPresenterMixin
from src.ui.panels.assets.batch_output_presenter import BatchOutputPresenterMixin
from src.ui.panels.assets.content_materials_presenter import (
    ContentMaterialsPresenterMixin,
)
from src.ui.panels.assets.field_editor_state_presenter import FieldEditorStatePresenterMixin
from src.ui.panels.assets.field_status_presenter import FieldStatusPresenterMixin
from src.ui.panels.assets.image_inventory_presenter import ImageInventorySetupPresenterMixin
from src.ui.panels.assets.image_preview_presenter import ImagePreviewPresenterMixin
from src.ui.panels.assets.image_rules_presenter import ImageRulesPresenterMixin
from src.ui.panels.assets.material_context_application_presenter import (
    MaterialContextApplicationPresenterMixin,
)
from src.ui.panels.assets.material_repair_navigation_presenter import MaterialRepairNavigationMixin
from src.ui.panels.assets.material_change_transaction import (
    MaterialChangeTransactionCoordinator,
    MaterialChangeTransactionPort,
)
from src.ui.panels.assets.preview_table_presenter import PreviewTablePresenterMixin
from src.ui.panels.assets.persistence_presenter import (
    MaterialPersistenceCoordinator,
    MaterialPersistencePort,
)
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
from src.ui.panels.assets.timeline_presenter import TimelinePresenterMixin
from src.ui.panels.assets.profile_presenter import ProfilePresenterMixin

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
    AttachmentInventorySetupPresenterMixin,
    AttachmentPreparationPresenterMixin,
    AssetCollectionStatePresenterMixin,
    AssetGroupRowsPresenterMixin,
    AssetFileOperationsPresenterMixin,
    AssetSlotStatusPresenterMixin,
    AssetRowsPresenterMixin,
    BatchOutputPresenterMixin,
    ContentMaterialsPresenterMixin,
    FieldEditorStatePresenterMixin,
    FieldStatusPresenterMixin,
    ImageInventorySetupPresenterMixin,
    ImagePreviewPresenterMixin,
    ImageRulesPresenterMixin,
    MaterialContextApplicationPresenterMixin,
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
    TimelinePresenterMixin,
    ThemePresenterMixin,
    BasePanel,
):
    """Manage the current entity/profile payload used by quick fill execution."""

    panel_title = "资料包"
    panel_icon = "package"

    @property
    def _current_archive_entry(self) -> MaterialPackageLibraryEntry | None:
        return self._material_persistence.current_entry

    @property
    def _current_archive_path(self) -> str:
        return self._material_persistence.current_path

    @property
    def _persisted_archive_snapshot(self) -> EntityArchive | None:
        return self._material_persistence.persisted_snapshot

    @property
    def _prepared_material_changes(self) -> Mapping[str, object] | None:
        return self._material_change_transaction.prepared_state

    @property
    def _material_persistence_actions(self):
        return self._material_persistence.actions

    def _setup_material_persistence_actions(self) -> None:
        self._material_persistence.setup_actions(
            {
                "fields": self._profile_card,
                "content": self._content_card,
                "timeline": self._timeline_card,
                # Image rules and inventory are one persistence domain.
                "images": self._image_rules_card,
                "attachments": self._attachment_card,
            }
        )

    def _capture_material_persistence_snapshot(
        self,
        archive: EntityArchive | None = None,
    ) -> None:
        self._material_persistence.capture_snapshot(archive)

    def _restore_material_section(self, section_id: str) -> bool:
        return self._material_persistence.restore_section(section_id)

    def prepare_pending_material_changes(self, action: str) -> bool:
        return self._material_change_transaction.prepare(action)

    def commit_prepared_material_changes(self) -> bool:
        return self._material_change_transaction.commit()

    def rollback_prepared_material_changes(self) -> bool:
        return self._material_change_transaction.rollback()

    def finalize_prepared_material_changes(self) -> None:
        self._material_change_transaction.finalize()

    def cancel_prepared_material_changes(self) -> bool:
        return self._material_change_transaction.cancel()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._assets_panel_closing = True
        timer = getattr(self, "_material_package_library_refresh_timer", None)
        if timer is not None:
            timer.stop()
        self._material_package_library_refresh_pending = False
        super().closeEvent(event)

    def _setup_ui(self) -> None:
        self.setObjectName("AssetsPanel")
        panel_ref = weakref.ref(self)

        def owner() -> AssetsPanel:
            panel = panel_ref()
            if panel is None:
                raise RuntimeError("assets_panel_owner_unavailable")
            return panel

        self._material_change_transaction = MaterialChangeTransactionCoordinator(
            MaterialChangeTransactionPort(
                persistence=lambda: owner()._material_persistence,
                persist_current_profile_editor=(
                    lambda: owner()._persist_current_profile_editor()
                ),
                current_archive=lambda: owner().current_archive(),
                current_profile_index=lambda: int(owner()._current_profile_index),
                set_archive=(
                    lambda archive, index: owner().set_archive(
                        archive,
                        select_index=index,
                    )
                ),
                save_pending_changes=lambda: owner().save_pending_material_changes(),
                capture_persistence_snapshot=(
                    lambda: owner()._capture_material_persistence_snapshot()
                ),
                refresh_archive_selector=(
                    lambda: owner()._refresh_archive_selector_from_library()
                ),
            )
        )
        self._material_persistence = MaterialPersistenceCoordinator(
            MaterialPersistencePort(
                current_archive=lambda: owner().current_archive(),
                persist_current_profile_editor=(
                    lambda: owner()._persist_current_profile_editor()
                ),
                set_archive=(
                    lambda archive, index: owner().set_archive(
                        archive,
                        select_index=index,
                    )
                ),
                activate_archive_entry=(
                    lambda entry: owner()._activate_archive_entry(entry)
                ),
                capture_persistence_snapshot=(
                    lambda archive=None: owner()._capture_material_persistence_snapshot(
                        archive,
                    )
                ),
                refresh_archive_selector=(
                    lambda: owner()._refresh_archive_selector_from_library()
                ),
                current_mode_id=(
                    lambda: str(
                        owner().bridge.current_work_mode_id() or ""
                    ).strip()
                ),
                current_profile_index=lambda: int(owner()._current_profile_index),
                field_conflicts=lambda: bool(owner()._field_conflicts),
                publication_transaction=lambda: owner()._material_change_transaction,
            )
        )
        self._archive_entries_by_path = {}
        self._material_package_library_refresh_pending = False
        self._assets_panel_closing = False
        self._material_package_library_refresh_timer = QTimer(self)
        self._material_package_library_refresh_timer.setSingleShot(True)
        self._material_package_library_refresh_timer.setInterval(50)
        self._material_package_library_refresh_timer.timeout.connect(
            lambda: owner()._refresh_material_package_library_after_change()
        )
        self._material_package_library_watcher = QFileSystemWatcher(self)
        self._profiles: list[EntityProfile] = [EntityProfile()]
        self._current_profile_index = 0
        self._syncing_profile_list = False
        self._syncing_output_naming = False
        self._suppress_material_context_sync = False
        self._field_inputs: dict[str, QLineEdit] = {}
        self._template_field_inputs: dict[
            str, QLineEdit | ProjectedTextEdit | OfficialFieldValueEdit
        ] = {}
        self._template_field_key_inputs: dict[str, ProjectedTextEdit] = {}
        self._unknown_field_rows: dict[str, QFrame] = {}
        self._unknown_field_remove_buttons: dict[str, QPushButton] = {}
        self._unknown_fields_controller = None
        self._template_field_values: dict[str, str] = {}
        # Runtime values entered in the workbench are an execution overlay.
        # They must never become package/profile fields merely because the
        # shared MaterialExecutionContext changed.
        self._task_field_values: dict[str, str] = {}
        self._official_fixed_field_keys: list[str] = []
        self._official_floating_field_keys: list[str] = []
        self._official_fixed_field_inputs: dict[str, OfficialFieldValueEdit] = {}
        self._official_floating_field_previews: dict[
            str, OfficialFieldValueEdit
        ] = {}
        self._official_field_name_labels: dict[str, QLabel] = {}
        self._official_function_buttons: dict[str, QPushButton] = {}
        self._official_field_rows: dict[str, QFrame] = {}
        self._official_field_index_labels: dict[str, QLabel] = {}
        self._official_field_row_scopes: dict[str, str] = {}
        self._official_fixed_fields_controller = None
        self._official_floating_fields_controller = None
        self._rendered_official_fixed_field_keys: tuple[str, ...] = ()
        self._rendered_official_floating_field_keys: tuple[str, ...] = ()
        self._last_removed_official_field: dict[str, object] | None = None
        self._manual_field_keys: list[str] = []
        self._declared_field_keys: set[str] = set()
        self._material_field_draft_counter = 0
        self._document_field_keys: set[str] = set()
        self._document_field_order: list[str] = []
        self._field_conflicts: tuple[str, ...] = ()
        self._last_received_material_context = None
        self._imported_field_keys: set[str] = set()
        self._preserve_import_sources = False
        self._asset_paths: dict[str, str] = {}
        self._asset_bindings = {}
        self._asset_metadata: dict[str, dict[str, str]] = {}
        self._asset_item_payloads: list[dict[str, object]] = []
        self._content_bindings = {}
        self._content_rules = []
        self._content_material_rows: dict[str, QFrame] = {}
        self._content_material_path_edits: dict[str, ProjectedTextEdit] = {}
        self._content_material_status_labels: dict[str, QLabel] = {}
        self._content_material_choose_buttons: dict[str, QPushButton] = {}
        self._content_material_clear_buttons: dict[str, QPushButton] = {}
        self._attachment_bindings = {}
        self._attachment_legacy_errors: dict[str, str] = {}
        self._image_material_rules = {}
        self._syncing_image_material_rules = False
        self._question_figure_repair_audit_records: list[dict[str, object]] = []
        self._asset_slot_rows: dict[str, QFrame] = {}
        self._asset_slot_index_labels: dict[str, QLabel] = {}
        self._asset_slot_target_edits: dict[str, ProjectedTextEdit] = {}
        self._asset_slot_name_edits: dict[str, ProjectedTextEdit] = {}
        self._asset_slot_path_edits: dict[str, ProjectedTextEdit] = {}
        self._asset_slot_path_widgets: dict[str, QWidget] = {}
        self._asset_slot_action_cells: dict[str, QWidget] = {}
        self._asset_slot_column_layouts = {}
        self._asset_slot_choose_buttons: dict[str, QPushButton] = {}
        self._asset_slot_thumbnail_labels: dict[str, QLabel] = {}
        self._asset_slot_status_labels: dict[str, QLabel] = {}
        self._asset_slot_alt_text_inputs: dict[str, ProjectedTextEdit] = {}
        self._asset_slot_open_buttons: dict[str, QPushButton] = {}
        self._asset_slot_clear_buttons: dict[str, QPushButton] = {}
        self._asset_slot_add_buttons: dict[str, QPushButton] = {}
        self._asset_slot_remove_buttons: dict[str, QPushButton] = {}
        self._asset_slots_controller = None
        self._asset_group_rows: dict[str, QFrame] = {}
        self._asset_group_index_labels: dict[str, QLabel] = {}
        self._asset_group_thumbnail_labels: dict[str, QLabel] = {}
        self._asset_group_token_edits: dict[str, ProjectedTextEdit] = {}
        self._asset_group_name_edits: dict[str, ProjectedTextEdit] = {}
        self._asset_group_path_labels: dict[str, ProjectedTextEdit] = {}
        self._asset_group_path_widgets: dict[str, QWidget] = {}
        self._asset_group_action_cells: dict[str, QWidget] = {}
        self._asset_group_column_layouts = {}
        self._asset_group_status_labels: dict[str, QLabel] = {}
        self._asset_group_tables = {}
        self._asset_group_choose_buttons: dict[str, QPushButton] = {}
        self._asset_group_refresh_buttons: dict[str, QPushButton] = {}
        self._asset_group_open_buttons: dict[str, QPushButton] = {}
        self._asset_group_clear_buttons: dict[str, QPushButton] = {}
        self._asset_group_add_buttons: dict[str, QPushButton] = {}
        self._asset_group_remove_buttons: dict[str, QPushButton] = {}
        self._asset_groups_controller = None
        self._attachment_role_rows: dict[str, QFrame] = {}
        self._attachment_role_index_labels: dict[str, QLabel] = {}
        self._attachment_role_preview_labels: dict[str, QLabel] = {}
        self._attachment_role_token_edits: dict[str, QWidget] = {}
        self._attachment_role_name_edits: dict[str, QWidget] = {}
        self._attachment_role_path_edits: dict[str, QWidget] = {}
        self._attachment_role_source_widgets: dict[str, QWidget] = {}
        self._attachment_role_action_cells: dict[str, QWidget] = {}
        self._attachment_role_column_layouts = {}
        self._attachment_role_status_labels: dict[str, QLabel] = {}
        self._attachment_role_choose_buttons: dict[str, QPushButton] = {}
        self._attachment_role_open_buttons: dict[str, QPushButton] = {}
        self._attachment_role_clear_buttons: dict[str, QPushButton] = {}
        self._attachment_role_add_buttons: dict[str, QPushButton] = {}
        self._attachment_role_remove_buttons: dict[str, QPushButton] = {}
        self._attachment_role_refresh_buttons: dict[str, QPushButton] = {}
        self._attachment_role_action_strips = {}
        self._attachment_preparation_summaries = {}
        self._current_image_preview_path = ""
        self._current_image_preview_display_name = ""
        self._image_preview_dialog: ImagePreviewDialog | None = None
        self._current_image_preview_question_figure_row = -1
        self._current_image_preview_compare_reference = ""
        self._current_image_preview_compare_source = ""
        self._current_image_preview_compare_display_name = ""
        self._current_image_preview_compare_options: list[dict[str, str]] = []
        self._preview_action_buttons: dict[str, QPushButton] = {}
        self._preview_only_issues = False
        self._current_document_path = self.bridge.current_document_path()
        self._execution_target = (
            self.bridge.current_execution_target()
            if hasattr(self.bridge, "current_execution_target")
            else None
        )
        self._placeholder_cache_path = ""
        self._placeholder_cache_mtime: float | None = None
        self._placeholder_cache_tokens: list[str] = []
        self._active_attention_card: Card | None = None
        self._attention_pulse_card: Card | None = None
        self._active_section_id = "generate"
        self._asset_slot_specs = self._asset_slots_from_scene(self.bridge.current_scene())
        self._asset_group_specs = self._asset_groups_from_scene(self.bridge.current_scene())
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

        self._title = QLabel("资料包", self._detail_shell)
        self._title.setVisible(False)
        self._summary = QLabel(self._detail_shell)
        self._summary.setWordWrap(True)
        self._summary.setVisible(False)

        self._return_bar = QWidget(self._detail_shell)
        self._return_bar.setObjectName("assets_return_bar")
        return_layout = QHBoxLayout(self._return_bar)
        return_layout.setContentsMargins(10, 6, 10, 6)
        return_layout.setSpacing(8)
        self._return_label = QLabel("从执行问题进入", self._return_bar)
        self._return_btn = QPushButton("返回执行", self._return_bar)
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

        self._setup_profile_editor_card()

        self._setup_content_materials_card()

        self._setup_timeline_cards()

        self._setup_image_rules_card()

        self._setup_image_inventory_card()

        self._setup_attachment_inventory_card()

        self._setup_material_persistence_actions()

        self._setup_placeholder_preview_card()

        self._setup_batch_profile_output_card()

        for layout in self._section_layouts.values():
            layout.addStretch(1)
        self._register_detail_cards()
        self._section_nav.select_card("generate")

        self._reload_profile_list(select_index=0)
        self._initialize_archive_library()
        self._refresh_summary()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
