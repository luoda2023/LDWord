"""
template_panel — 模板管理面板（Master-Detail 架构）

与工作台同构：左侧导航卡片 + 右侧可切换详情面板。
信息分层:
  Layer 1: 模板概览 (主操作)
  Layer 2: 页面设置 / 排版样式 / 标题编号 (参数细节)
"""

from __future__ import annotations

from pathlib import Path

from src.config.library import (
    default_template_entry,
    get_template_entry,
    is_template_library_path,
    load_template_from_library,
    template_dependent_scene_descriptors,
)
from src.config.resolver import resolve_config, resolve_template_baseline
from src.config.template import TemplateConfig
from src.qt_api import (
    QDesktopServices,  # noqa: F401 - compatibility seam for integrations/tests
    QFileSystemWatcher,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui import (
    DetailPaneController,
    MasterDetailShell,
    NavigationCard,
    Toast,  # noqa: F401 - compatibility seam shared with the library mixin
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.dialogs import confirm, input_text
from src.shared.ui.theme import bind_theme, get_theme
from src.modules.registry import create_all_modules
from src.pipeline.module_selection import (
    ModuleDisposition,
    ModuleSelectionPlan,
    build_module_selection_plan,
)
from src.ui.base_panel import BasePanel
from src.ui.template_library_controller import TemplateLibraryController
from src.ui.template_edit_session import TemplateDraftStore
from src.ui.template_close_prompt import TemplateClosePrompt
from src.ui.template_close_transaction import (
    TEMPLATE_EDIT_CANCEL,  # noqa: F401 - compatibility export
    TEMPLATE_EDIT_DISCARD,  # noqa: F401 - compatibility export
    TEMPLATE_EDIT_SAVE,  # noqa: F401 - compatibility export
    TemplateCloseTransaction,
)
from src.ui.template_draft_save_coordinator import (
    TemplateDraftSaveCoordinator,
)
from src.ui.panels.template_feature_specs import (
    TEMPLATE_CARD_DEFINITIONS,
    TEMPLATE_DETAIL_CARD_IDS,
    TEMPLATE_FEATURE_BY_CARD_ID,
    feature_module_names,
    module_control_switch_updates,
)
from src.ui.panels.template_detail_lifecycle import (
    TemplateDetailLifecycleMixin,
)
from src.ui.panels.template_close_lifecycle_mixin import TemplateCloseLifecycleMixin
from src.ui.panels.template_library_management_mixin import (
    TemplateLibraryManagementMixin,
)
from src.ui.panels.template_navigation_context_mixin import (
    TemplateNavigationContextMixin,
)
from src.ui.panels.template_overview_projection_mixin import (
    TemplateOverviewProjectionMixin,
)
from src.ui.panels.template_session_persistence_mixin import (
    TemplateSessionPersistenceMixin,
)
from src.ui.panels.template_builtin_save_mixin import TemplateBuiltinSaveMixin
from src.ui.panels.template_overview_detail import TemplateOverviewDetail
from src.ui.panels.template_overview_projection import (
    TemplateOverviewProjection,
)
from src.ui.panels.template_participation_controls import CompactModuleControls
from src.ui.panels.template_preview.model import TemplatePreviewMode
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_caption_detail import CaptionDetail
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.template_table_detail import TableCaptionDetail
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_style_detail import StyleDetail


def _confirm_template_persistence(*args, **kwargs) -> bool:
    """Late-bind the panel confirmation seam for tests and integrations."""

    return bool(confirm(*args, **kwargs))


def _request_template_text(*args, **kwargs):
    """Late-bind the panel text-input seam for tests and integrations."""

    return input_text(*args, **kwargs)


def _resolve_template_preview_config(*args, **kwargs):
    return resolve_config(*args, **kwargs)


def _resolve_template_preview_baseline(*args, **kwargs):
    return resolve_template_baseline(*args, **kwargs)


def _resolve_template_dependents(template_id: str, *, mode_id: str):
    """Late-bind shared-template dependency lookup at the panel boundary."""

    return template_dependent_scene_descriptors(
        template_id,
        mode_id=mode_id,
    )


def _is_template_persistence_library_path(path: str | Path) -> bool:
    return is_template_library_path(path)


# ═══════════════════════════════════════════════════════════════════════
#  Card definitions (Layer 1 → 2 → 3)
# ═══════════════════════════════════════════════════════════════════════

class _PlaceholderDetail(QWidget):
    """Placeholder for future parameter editing panes."""

    def __init__(self, title: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card = Card(parent=self)

        hdr = QWidget()
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(0, 0, 0, 6)
        h_lay.setSpacing(6)
        self._hdr_icon = QLabel()
        self._hdr_icon.setFixedSize(18, 18)
        h_lay.addWidget(self._hdr_icon)
        t_lbl = QLabel(title)
        t_lbl.setObjectName("tpl_card_title")
        h_lay.addWidget(t_lbl)
        h_lay.addStretch(1)
        card.add_widget(hdr)

        desc = QLabel(f"「{title}」暂未开放。")
        desc.setObjectName("tpl_placeholder_desc")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        card.add_widget(desc)

        layout.addWidget(card)
        layout.addStretch(1)

    def apply_theme(self) -> None:
        t = get_theme()
        for w in self.findChildren(QLabel, "tpl_card_title"):
            w.setStyleSheet(
                f"font-size: {t.font_size_lg}px; font-weight: {t.font_weight_emphasis}; color: {t.primary}; background: transparent;"
            )
        for w in self.findChildren(QLabel, "tpl_placeholder_desc"):
            w.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_hint}; padding: 40px 20px;"
            )
        try:
            from src.shared.ui.icons.catalog import get_icon
            self._hdr_icon.setPixmap(get_icon(self._icon_name, 18, t.primary).pixmap(18, 18))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  Main Panel (Master-Detail)
# ═══════════════════════════════════════════════════════════════════════

class TemplatePanel(
    TemplateCloseLifecycleMixin,
    TemplateDetailLifecycleMixin,
    TemplateLibraryManagementMixin,
    TemplateNavigationContextMixin,
    TemplateOverviewProjectionMixin,
    TemplateBuiltinSaveMixin,
    TemplateSessionPersistenceMixin,
    BasePanel,
):
    """Master-detail template management panel."""

    panel_title = "模板管理"
    panel_icon = "file-text"

    def _current_work_mode_id(self) -> str:
        if hasattr(self.bridge, "current_work_mode_id"):
            return str(self.bridge.current_work_mode_id() or "").strip()
        return "custom"

    def _setup_ui(self) -> None:
        self._initialize_template_panel_state()
        self._resolve_initial_template()
        self._activate_initial_template_draft()
        self._build_template_shell()
        self._build_template_detail_registry()
        self._build_template_context_bars()
        self._build_template_navigation()
        self._initialize_template_view()

    def _initialize_template_panel_state(self) -> None:
        self.setObjectName("TemplatePanel")
        self._template_library_controller = TemplateLibraryController()
        self._draft_store = TemplateDraftStore()
        self._template_persistence_confirm = _confirm_template_persistence
        self._template_text_request = _request_template_text
        self._template_preview_config_resolver = _resolve_template_preview_config
        self._template_preview_baseline_resolver = (
            _resolve_template_preview_baseline
        )
        self._template_dependency_resolver = _resolve_template_dependents
        self._template_library_path_predicate = (
            _is_template_persistence_library_path
        )
        self._draft_save_coordinator = TemplateDraftSaveCoordinator(
            self._draft_store,
            confirm_overwrite=self._confirm_template_save_overwrite,
        )
        self._close_prompt = TemplateClosePrompt(self)
        self._close_transaction = TemplateCloseTransaction(self)
        self._current_template_id = self.bridge.current_template_id()
        self._current_template_path = self.bridge.current_template_path()
        self._current_template_source = self.bridge.current_template_source()
        self._current_template_source_type = self.bridge.current_template_source_type()
        self._overview_projection: TemplateOverviewProjection | None = None
        self._preview_mode = TemplatePreviewMode.TEMPLATE_BASELINE
        self._module_selection = None
        self._overview_projection_stale = False
        self._projection_refresh_count = 0
        self._publishing_template = False
        self._preview_modules = tuple(create_all_modules())
        self._last_template_management_status = ""
        self._template_library_refresh_running = False
        self._template_library_refresh_again = False
        self._template_library_watcher = QFileSystemWatcher(self)
        self._template_library_refresh_timer = QTimer(self)
        self._template_library_refresh_timer.setSingleShot(True)

    def _resolve_initial_template(self) -> None:
        current_template = self.bridge.current_template()
        if current_template is not None:
            self._current_template = current_template
        else:
            scene = self.bridge.current_scene()
            scene_template_id = ""
            if scene is not None:
                scene_template_id = str(
                    getattr(scene, "template_id", "") or ""
                ).strip()

            if scene_template_id:
                entry = get_template_entry(scene_template_id, mode_id=self._current_work_mode_id())
                self._current_template = load_template_from_library(
                    scene_template_id,
                    mode_id=self._current_work_mode_id(),
                )
                self._current_template_id = scene_template_id
                self._current_template_path = str(entry.path) if entry is not None else ""
                self._current_template_source = "library" if entry is not None else "builtin"
                self._current_template_source_type = (
                    entry.source_type if entry is not None else "builtin"
                )
            else:
                default_entry = default_template_entry(mode_id=self._current_work_mode_id())
                if default_entry is not None:
                    self._current_template = load_template_from_library(
                        default_entry.config_id,
                        mode_id=self._current_work_mode_id(),
                    )
                    self._current_template_id = default_entry.config_id
                    self._current_template_path = str(default_entry.path)
                    self._current_template_source = "library"
                    self._current_template_source_type = default_entry.source_type
                else:
                    raise FileNotFoundError(
                        "default_template_ref_unresolved:"
                        f" mode={self._current_work_mode_id()}"
                    )

    def _activate_initial_template_draft(self) -> None:
        self._draft_context = self._draft_store.activate(
            self._current_template,
            mode_id=self._current_work_mode_id(),
            template_id=self._current_template_id or "default",
            path=self._current_template_path,
            source=self._current_template_source,
            source_type=self._current_template_source_type,
        )
        self._edit_session = self._draft_context.session
        self._current_template = self._edit_session.draft

    def _build_template_shell(self) -> None:
        self._shell = MasterDetailShell(
            self,
            panel_name="TemplatePanel",
            nav_object_name="tpl_navigation",
            detail_object_name="tpl_detail",
            detail_content_object_name="tpl_detail_content",
        )
        self._layout = self._shell.layout
        self._nav_rail = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_container = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout

    def _build_template_detail_registry(self) -> None:
        self._overview_detail = TemplateOverviewDetail()
        self._detail_factories = {
            "tpl_page": PageSetupDetail,
            "tpl_style": StyleDetail,
            "tpl_heading": lambda: HeadingNumberingPanel(self.bridge),
            "tpl_table": TableCaptionDetail,
            "tpl_header_footer": lambda: ElementsDetail(scope="header_footer"),
            "tpl_toc": lambda: ElementsDetail(scope="toc"),
            "tpl_caption": CaptionDetail,
        }
        self._detail_attr_names = {
            "_page_detail": "tpl_page",
            "_style_detail": "tpl_style",
            "_heading_detail": "tpl_heading",
            "_table_detail": "tpl_table",
            "_header_footer_detail": "tpl_header_footer",
            "_toc_detail": "tpl_toc",
            "_caption_detail": "tpl_caption",
        }
        self._loaded_detail_ids: set[str] = {"tpl_overview"}
        self._participation_sections: dict[str, CompactModuleControls] = {}
        self._initialize_detail_lifecycle_state()

        self._detail_map: dict[str, QWidget] = {
            "tpl_overview": self._overview_detail,
        }
        for card_id in TEMPLATE_DETAIL_CARD_IDS:
            title, icon = TEMPLATE_CARD_DEFINITIONS[card_id]
            self._detail_map[card_id] = _PlaceholderDetail(title, icon)
        self._details = DetailPaneController(
            self._detail_container,
            self._detail_layout,
            self._detail_scroll,
        )
        self._details.register_details(self._detail_map)
        self._current_detail: QWidget | None = self._details.current_detail
        self._current_detail_card_id: str | None = None
        self._return_navigation_intent: dict[str, object] | None = None

    def _build_template_context_bars(self) -> None:
        self._entry_context_bar = QWidget(self._detail_container)
        self._entry_context_bar.setObjectName("tpl_entry_context_bar")
        entry_layout = QVBoxLayout(self._entry_context_bar)
        entry_layout.setContentsMargins(10, 8, 10, 8)
        entry_layout.setSpacing(3)
        self._entry_context_title = QLabel("", self._entry_context_bar)
        self._entry_context_title.setObjectName("tpl_entry_context_title")
        self._entry_context_title.setWordWrap(True)
        self._entry_context_detail = QLabel("", self._entry_context_bar)
        self._entry_context_detail.setObjectName("tpl_entry_context_detail")
        self._entry_context_detail.setWordWrap(True)
        entry_layout.addWidget(self._entry_context_title)
        entry_layout.addWidget(self._entry_context_detail)
        self._entry_context_bar.setVisible(False)
        self._detail_layout.addWidget(self._entry_context_bar)

        self._return_bar = QWidget(self._detail_container)
        self._return_bar.setObjectName("tpl_return_bar")
        return_layout = QHBoxLayout(self._return_bar)
        return_layout.setContentsMargins(0, 0, 0, 8)
        return_layout.setSpacing(8)
        self._return_label = QLabel("从执行问题进入", self._return_bar)
        self._return_btn = QPushButton("返回执行", self._return_bar)
        self._return_btn.clicked.connect(self._navigate_return_target)
        return_layout.addWidget(self._return_label)
        return_layout.addStretch(1)
        return_layout.addWidget(self._return_btn)
        self._return_bar.setVisible(False)
        self._detail_layout.addWidget(self._return_bar)

    def _build_template_navigation(self) -> None:
        self._nav_cards: dict[str, NavigationCard] = {}

        # Layer 1 + 2: Fixed cards
        for card_id in ("tpl_overview",):
            title, icon = TEMPLATE_CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

        # Section header between Layer 2 and Layer 3
        self._nav_rail.add_section_header("参数编辑")

        # Layer 3: Detail cards
        for card_id in TEMPLATE_DETAIL_CARD_IDS:
            title, icon = TEMPLATE_CARD_DEFINITIONS[card_id]
            card = NavigationCard(card_id, title, icon_name=icon, parent=self._nav_rail)
            self._nav_cards[card_id] = card
            self._nav_rail.add_card(card_id, card)

    def _initialize_template_view(self) -> None:
        self._refresh_template_selector_options()
        self._set_detail_templates(self._current_template)
        self._sync_template_file_status()
        self._refresh_overview_projection(reason="initial")
        self._sync_template_dirty_state()
        self._set_detail_save_enabled(self._edit_session.is_dirty())
        if self.bridge.current_template() is None:
            self._publish_current_template(emit_signal=False)
        # Manually show initial detail (signals not yet connected)
        self._show_detail("tpl_overview")
        self._nav_rail.select_card("tpl_overview")
        self._apply_theme()
        self._setup_template_library_watcher()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        # Navigation
        self._nav_rail.card_selected.connect(self._show_detail)

        # Overview interactions
        self._overview_detail.template_selected.connect(self._on_template_selected)
        self._overview_detail.edit_navigate.connect(self._nav_rail.select_card)
        self._overview_detail.preview_mode_requested.connect(
            self._on_preview_mode_requested
        )
        self._overview_detail.new_template_requested.connect(
            self._on_new_template_requested
        )
        self._overview_detail.duplicate_template_requested.connect(
            self._on_duplicate_template_requested
        )
        self._overview_detail.rename_template_requested.connect(
            self._on_rename_template_requested
        )
        self._overview_detail.open_template_folder_requested.connect(self._on_open_template_folder_requested)
        self._overview_detail.delete_template_requested.connect(
            self._on_delete_template_requested
        )
        self._overview_detail.selector_open_requested.connect(self._refresh_template_library_from_disk)
        self._template_library_watcher.directoryChanged.connect(self._on_template_library_path_changed)
        self._template_library_watcher.fileChanged.connect(self._on_template_library_path_changed)
        self._template_library_refresh_timer.timeout.connect(
            self._refresh_template_library_from_disk
        )

        # Bridge
        self.bridge.scene_changed.connect(self.on_scene_changed)
        self.bridge.template_changed.connect(self.on_template_changed)
        template_events = getattr(self.bridge, "template_library_events", None)
        if template_events is not None:
            template_events.import_completed.connect(
                self._on_template_import_completed
            )
        if hasattr(self.bridge, "work_mode_changed"):
            self.bridge.work_mode_changed.connect(self._on_work_mode_changed)

    def _attach_participation_section(
        self,
        card_id: str,
        detail: QWidget,
    ) -> None:
        feature = TEMPLATE_FEATURE_BY_CARD_ID.get(card_id)
        if feature is None or card_id in self._participation_sections:
            return
        summary_card = getattr(detail, "_summary_card", None)
        if summary_card is None:
            summary_card = getattr(detail, "_header_card", None)
        add_control = getattr(summary_card, "add_control", None)
        if not callable(add_control):
            return
        section = CompactModuleControls(
            feature,
            parent=summary_card,
        )
        section.participation_changed.connect(
            self._on_participation_changed
        )
        add_control(section)
        self._participation_sections[card_id] = section
        section.apply_selection(
            self._module_selection,
            has_scene=self.bridge.current_scene() is not None,
        )

    def _apply_module_selection(
        self,
        selection: ModuleSelectionPlan | None,
    ) -> None:
        has_scene = self.bridge.current_scene() is not None
        for feature in TEMPLATE_FEATURE_BY_CARD_ID.values():
            card_id = feature.card_id
            decisions = (
                tuple(
                    selection.decision_for(module_name)
                    for module_name in feature_module_names(feature)
                )
                if has_scene and selection is not None
                else ()
            )
            nav_card = self._nav_cards.get(card_id)
            if nav_card is not None:
                if not feature.show_execution_badge or not has_scene:
                    nav_card.set_badge("", "neutral")
                elif any(
                    decision.disposition is ModuleDisposition.AUTO_PRUNED
                    for decision in decisions
                ):
                    nav_card.set_badge("受限", "warning")
                elif decisions and all(
                    decision.effectively_enabled for decision in decisions
                ):
                    nav_card.set_badge("执行", "success")
                elif any(decision.effectively_enabled for decision in decisions):
                    nav_card.set_badge("部分", "warning")
                else:
                    nav_card.set_badge("跳过", "neutral")
            section = self._participation_sections.get(card_id)
            if section is not None:
                section.apply_selection(
                    selection,
                    has_scene=has_scene,
                )

    def _on_participation_changed(
        self,
        module_name: str,
        enabled: bool,
    ) -> None:
        changed = self.bridge.update_current_scene_module_switches(
            module_control_switch_updates(module_name, enabled)
        )
        if not changed:
            self._apply_module_selection(self._module_selection)

    def _apply_participation_scene_update(self, scene) -> None:
        """Project a switch-only scene update without rebuilding hidden UI."""

        if scene is None:
            self._module_selection = None
            self._apply_module_selection(None)
        else:
            selection = build_module_selection_plan(
                self._preview_modules,
                is_requested=scene.is_module_enabled,
            )
            self._module_selection = selection
            self._apply_module_selection(selection)
        self._overview_projection_stale = True

    def _request_overview_projection_refresh(self, *, reason: str) -> None:
        if self._current_detail_card_id == "tpl_overview":
            self._refresh_overview_projection(reason=reason)
        else:
            self._overview_projection_stale = True

    def _on_detail_shown(self, card_id: str) -> None:
        if card_id == "tpl_overview" and self._overview_projection_stale:
            self._refresh_overview_projection(reason="deferred_detail_change")

    def _wire_parameter_detail_signals(self, card_id: str, detail: QWidget) -> None:
        del card_id
        if hasattr(detail, "template_edited"):
            detail.template_edited.connect(self._on_template_edited)
        if hasattr(detail, "save_requested"):
            detail.save_requested.connect(self._save_current_template)

    def _apply_detail_context(
        self,
        detail: QWidget,
        template: TemplateConfig,
    ) -> None:
        if hasattr(detail, "set_scene"):
            detail.set_scene(self.bridge.current_scene())
        if hasattr(detail, "set_template"):
            detail.set_template(template)
        elif hasattr(detail, "on_template_changed"):
            detail.on_template_changed(template)

    def _sync_detail_state(self, detail: QWidget) -> None:
        self._apply_detail_context(detail, self._current_template)
        if hasattr(detail, "set_save_enabled"):
            detail.set_save_enabled(self._has_pending_template_edits())
        if hasattr(detail, "apply_theme"):
            detail.apply_theme()
        elif hasattr(detail, "_apply_theme"):
            detail._apply_theme()

    def _parameter_details(self) -> list[QWidget]:
        return [
            self._detail_map[card_id]
            for card_id in TEMPLATE_DETAIL_CARD_IDS
            if card_id in self._loaded_detail_ids
        ]

    def _set_detail_templates(self, template: TemplateConfig) -> None:
        for detail in self._parameter_details():
            self._apply_detail_context(detail, template)

    def _set_detail_scenes(self, scene) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_scene"):
                detail.set_scene(scene)

    def _set_detail_save_enabled(self, enabled: bool) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "set_save_enabled"):
                detail.set_save_enabled(enabled)

    def _set_template_management_status(self, text: str) -> None:
        self._last_template_management_status = str(text or "")

    def _on_preview_mode_requested(self, value: str) -> None:
        try:
            requested = TemplatePreviewMode(value)
        except ValueError:
            return
        if (
            requested is TemplatePreviewMode.CURRENT_PLAN
            and self.bridge.current_scene() is None
        ):
            return
        if requested is self._preview_mode:
            return
        self._preview_mode = requested
        self._refresh_overview_projection(reason="preview_mode_changed")

    def _on_template_edited(self, template: TemplateConfig) -> None:
        editing_detail = self.sender()
        draft = self._edit_session.replace_draft(template)
        self._current_template = draft
        if draft is not template:
            self._set_detail_templates(draft)
        elif editing_detail is getattr(self, "_heading_detail", None):
            header_footer_detail = getattr(self, "_header_footer_detail", None)
            if header_footer_detail is not None:
                self._apply_detail_context(header_footer_detail, draft)
        self._sync_template_dirty_state()
        self._sync_template_file_status()
        self._request_overview_projection_refresh(
            reason="template_draft_changed"
        )

    def on_scene_changed(self, scene) -> None:
        if self._close_transaction.is_restoring_snapshot:
            return
        if self.bridge.scene_change_reason() == "module_switches":
            self._apply_participation_scene_update(scene)
            return
        self._set_detail_scenes(scene)
        self._refresh_overview_projection(reason="scene_changed")

    def on_template_changed(self, template: TemplateConfig) -> None:
        if (
            template is None
            or self._publishing_template
            or self._close_transaction.is_restoring_snapshot
        ):
            return
        self._activate_template(
            template,
            template_id=self.bridge.current_template_id(),
            path=self.bridge.current_template_path(),
            source=self.bridge.current_template_source(),
            source_type=self.bridge.current_template_source_type(),
            publish=False,
        )

    def _apply_theme(self) -> None:
        t = get_theme()
        self._shell.apply_theme(t)

        if hasattr(self, "_return_label"):
            self._return_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
            )
            apply_button_variant(self._return_btn, "secondary")
        if hasattr(self, "_entry_context_bar"):
            self._entry_context_bar.setStyleSheet(
                f"background: {t.bg_selected}; border: 1px solid {t.border_light}; "
                f"border-radius: {t.radius_sm}px;"
            )
            self._entry_context_title.setStyleSheet(
                f"font-size: {t.font_size_sm}px; font-weight: {t.font_weight_emphasis}; "
                f"color: {t.text_primary}; background: transparent;"
            )
            self._entry_context_detail.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary}; background: transparent;"
            )

        # Propagate to details
        self._overview_detail.apply_theme()
        show_refresh = self._prepare_detail_feedback_theme()
        for detail in self._parameter_details():
            if hasattr(detail, "apply_theme"):
                detail.apply_theme()
            elif hasattr(detail, "_apply_theme"):
                detail._apply_theme()
        self._finish_detail_feedback_theme(show_refresh)
