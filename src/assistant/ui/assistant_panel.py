"""LDWord AI document assistant panel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from src.application.materials import ExecutionMaterialSnapshot
from src.assistant.application.document_job_controller import DocumentJobController
from src.assistant.application.preflight_presentation import (
    active_preflight_card_presentation,
)
from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.application.session_recovery import AssistantSessionRecovery
from src.assistant.contracts.messages import (
    BLOCK_ARTIFACT,
    BLOCK_INTERACTION,
    BLOCK_TEXT,
    ROLE_ASSISTANT,
    ROLE_USER,
)
from src.assistant.runtime.cancellation import AssistantCancellationToken
from src.assistant.runtime.providers.profiles import (
    ensure_luoda_official_ready,
)
from src.assistant.runtime.providers.router import (
    ProviderRouter,
)
from src.assistant.runtime.providers.secrets import (
    HybridSecretStore,
)
from src.assistant.runtime.turn_runner import (
    AssistantTurnRunner,
)
from src.assistant.storage.execution_journal import ExecutionJournalStore
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.card_action_mixin import AssistantCardActionMixin
from src.assistant.ui.chapter_rewrite_mixin import (
    AssistantChapterRewriteMixin,
    CHAPTER_OUTLINE_ACTION,
    CHAPTER_REWRITE_ACTION,
)
from src.assistant.ui.chapter_workbench_mixin import AssistantChapterWorkbenchMixin
from src.assistant.ui.chapter_outline_dock import ChapterOutlineDock
from src.assistant.ui.marktext_view import EmbeddedMarkTextView
from src.assistant.ui.conversation_presentation import (
    build_interaction_action_scope,
    interaction_is_active,
)
from src.assistant.ui.cover_field_mapping import (
    resolve_sources as _resolve_cover_sources,
    scene_key_for as _cover_scene_key_for,
    SRC_DOCUMENT_CONTEXT as _SRC_DOCUMENT_CONTEXT,
    SRC_DOCUMENT_FIRST_H1 as _SRC_DOCUMENT_FIRST_H1,
    SRC_NONE as _SRC_NONE,
)
from src.assistant.ui.conversation_view import (
    AssistantConversationMessage,
    AssistantConversationSurface,
)
from src.assistant.ui.creative_home import AssistantCreativeHome, AssistantHeroComposer
from src.assistant.ui.design_tokens import TOKENS
from src.assistant.ui.document_workflow_mixin import AssistantDocumentWorkflowMixin
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.assistant.ui.panel_theme_mixin import AssistantPanelThemeMixin
from src.assistant.ui.provider_selection import ProviderSelectionCoordinator
from src.assistant.ui.session_sidebar import (
    SESSION_ICON_OPTIONS,
    AssistantSessionSidebar,
    session_row_presentation,
)
from src.assistant.ui.turn_flow_mixin import AssistantTurnFlowMixin
from src.assistant.ui.viewport_mixin import AssistantViewportMixin
from src.assistant.ui.workers import (
    AssistantTurnWorker,
    ContentGenerationWorker,
    DocumentExecutionWorker,
    PreflightWorker,
)
from src.qt_api import (
    QComboBox,
    QDesktopServices,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QTimer,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.context_menu import ContextMenu
from src.shared.ui.dialogs import (
    DialogAction,
    decision,
    input_text,
)
from src.shared.ui.dialogs import (
    info as show_info,
)
from src.shared.ui.dialogs import (
    warning as show_warning,
)
from src.shared.ui.drawer import Drawer
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme
from src.ui.base_panel import BasePanel

_COVER_DATE_FORMAT_KEY = "export/cover_date_format"

# Ordered (id, label) list of cover date formats.  The id is what we persist;
# the label carries a live example and is shown in the dialog's combo box.
_COVER_DATE_FORMATS = (
    ("cn_full", "中文年月日（如 2026 年 9 月 7 日）"),
    ("cn_compact", "中文紧凑（如 2026年9月7日）"),
    ("cn_han", "汉字日期（如 二〇二六年九月七日）"),
    ("cn_han_month", "汉字年月（如 二〇二六年九月）"),
    ("iso_dash", "数字短横（如 2026-09-07）"),
    ("iso_dot", "数字点分（如 2026.09.07）"),
)
_DEFAULT_COVER_DATE_FORMAT = "cn_full"

_CN_DIGITS = "〇一二三四五六七八九"


def _load_cover_date_format() -> str:
    """Return the last cover-date format the user picked (id string)."""
    try:
        from src.qt_api import QSettings

        settings = QSettings("LDWord", "LDWord")
        value = str(settings.value(_COVER_DATE_FORMAT_KEY, "") or "").strip()
        if value and any(fmt_id == value for fmt_id, _ in _COVER_DATE_FORMATS):
            return value
    except Exception:  # noqa: BLE001 - never block export on settings errors
        pass
    return _DEFAULT_COVER_DATE_FORMAT


def _save_cover_date_format(fmt_id: str) -> None:
    try:
        from src.qt_api import QSettings

        settings = QSettings("LDWord", "LDWord")
        settings.setValue(_COVER_DATE_FORMAT_KEY, str(fmt_id or ""))
        settings.sync()
    except Exception:  # noqa: BLE001 - preference persistence must never crash
        pass


def _cn_number(value: int) -> str:
    """Return the Chinese-numeral spelling of 0..99 (十/二十… style)."""
    if value < 0:
        return str(value)
    if value < 10:
        return _CN_DIGITS[value]
    tens, unit = divmod(value, 10)
    head = "十" if tens == 1 else _CN_DIGITS[tens] + "十"
    return head + (_CN_DIGITS[unit] if unit else "")


def _cn_year(value: int) -> str:
    """Render a Gregorian year as Chinese numerals (2026 -> 二〇二六)."""
    return "".join(_CN_DIGITS[int(ch)] for ch in str(int(value or 0)))


def _format_cover_date(d, fmt_id: str) -> str:
    """Render a date d (datetime.date-like) using one of the cover formats."""
    year = getattr(d, "year", 0) or 0
    month = getattr(d, "month", 0) or 0
    day = getattr(d, "day", 0) or 0
    fmt = str(fmt_id or "").strip()
    if fmt == "cn_compact":
        return f"{year}年{month}月{day}日"
    if fmt == "cn_han":
        return f"{_cn_year(year)}年{_cn_number(month)}月{_cn_number(day)}日"
    if fmt == "cn_han_month":
        return f"{_cn_year(year)}年{_cn_number(month)}月"
    if fmt == "iso_dash":
        return f"{year:04d}-{month:02d}-{day:02d}"
    if fmt == "iso_dot":
        return f"{year:04d}.{month:02d}.{day:02d}"
    # default: 中文年月日
    return f"{year} 年 {month} 月 {day} 日"

def _load_export_undo_keep() -> bool:
    """Return whether the user wants undo history kept after a successful
    export (True, default) instead of cleared.

    Thin forwarder to :mod:`src.config.app_preferences` so the export dialog
    and the global preferences page share one source of truth.
    """
    from src.config.app_preferences import export_keep_undo_history

    return export_keep_undo_history()


def _save_export_undo_keep(keep: bool) -> None:
    """Persist the export undo-history preference (shared key with preferences)."""
    from src.config.app_preferences import set_export_keep_undo_history

    set_export_keep_undo_history(keep)


def _load_save_undo_keep() -> bool:
    """Return whether the user wants undo history kept after a successful
    save-to-file (non-export), True by default.

    Thin forwarder to :mod:`src.config.app_preferences` so the save action
    and the global preferences page share one source of truth.
    """
    from src.config.app_preferences import save_keep_undo_history

    return save_keep_undo_history()


def _save_save_undo_keep(keep: bool) -> None:
    """Persist the save undo-history preference (shared key with preferences)."""
    from src.config.app_preferences import set_save_keep_undo_history

    set_save_keep_undo_history(keep)


class AssistantPanel(
    AssistantChapterWorkbenchMixin,
    AssistantChapterRewriteMixin,
    AssistantDocumentWorkflowMixin,
    AssistantCardActionMixin,
    AssistantTurnFlowMixin,
    AssistantViewportMixin,
    AssistantPanelThemeMixin,
    BasePanel,
):
    panel_title = "AI 文档助手"
    panel_icon = "sparkles"

    def __init__(
        self,
        bridge,
        parent=None,
        *,
        coordinator: AssistantSessionCoordinator | None = None,
        turn_runner: AssistantTurnRunner | None = None,
        provider_router: ProviderRouter | None = None,
        document_jobs: DocumentJobController | None = None,
        embedded: bool = False,
        first_level: bool = False,
    ) -> None:
        self._embedded = bool(embedded)
        self._first_level = bool(first_level)
        if self._embedded and self._first_level:
            raise ValueError("embedded and first_level assistant shells are mutually exclusive")
        self._coordinator = coordinator or AssistantSessionCoordinator()
        self._fixed_turn_runner = turn_runner
        self._provider_router = provider_router or ProviderRouter()
        if not self._fixed_turn_runner:
            from src.app_meta import LUODA_OFFICIAL_DEFAULT_KEY

            ensure_luoda_official_ready(
                profiles=self._provider_router.profiles,
                secret=LUODA_OFFICIAL_DEFAULT_KEY,
                secret_store=getattr(self._provider_router, "secrets", None)
                or HybridSecretStore(),
            )
        journal = ExecutionJournalStore(self._coordinator.store.root / "executions")
        self._document_jobs = document_jobs or DocumentJobController(journal=journal)
        self._recovery = AssistantSessionRecovery(
            self._coordinator,
            self._document_jobs.journal,
            self._document_jobs.leases,
        )
        self._recovery.reconcile()
        self._active_session: AssistantSession | None = None
        self._active_cancellation: AssistantCancellationToken | None = None
        self._turn_worker: AssistantTurnWorker | None = None
        self._turn_workers: dict[str, AssistantTurnWorker] = {}
        self._turn_previews: dict[str, dict[str, object]] = {}
        self._turn_material_snapshots: dict[
            str, ExecutionMaterialSnapshot | None
        ] = {}
        self._plan_material_snapshots: dict[
            str, ExecutionMaterialSnapshot | None
        ] = {}
        self._content_worker: ContentGenerationWorker | None = None
        self._preflight_worker: PreflightWorker | None = None
        self._execution_worker: DocumentExecutionWorker | None = None
        self._session_rail_requested = True
        self._context_rail_requested = True
        self._responsive_mode = "wide"
        self._session_drawer: Drawer | None = None
        self._context_drawer: Drawer | None = None
        self._loading_draft = False
        self._turn_preview_session_id = ""
        self._turn_preview_turn_id = ""
        self._turn_preview_text = ""
        self._turn_preview_status = ""
        self._turn_preview_widget: AssistantConversationMessage | None = None
        self._rendered_session_id = ""
        self._follow_latest_layout_pending = False
        self._force_follow_latest = False
        super().__init__(bridge, parent)
        self._pending_draft_session_id = ""
        self._draft_save_timer = QTimer(self)
        self._draft_save_timer.setSingleShot(True)
        self._draft_save_timer.setInterval(350)
        self._draft_save_timer.timeout.connect(self._flush_active_draft)
        self._turn_preview_flush_timer = QTimer(self)
        self._turn_preview_flush_timer.setSingleShot(True)
        self._turn_preview_flush_timer.setInterval(16)
        self._turn_preview_flush_timer.timeout.connect(self._flush_active_turn_preview)
        self._follow_latest_settle_timer = QTimer(self)
        self._follow_latest_settle_timer.setSingleShot(True)
        self._follow_latest_settle_timer.setInterval(80)
        self._follow_latest_settle_timer.timeout.connect(
            self._finish_follow_latest_layout_settle
        )
        self._scroll_update_pending = False

    def _setup_ui(self) -> None:
        self.setObjectName("AssistantPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setSizeConstraint(QLayout.SetNoConstraint)
        self._root_layout = root

        self._session_rail = self._build_session_rail()
        self._center = self._build_center()
        self._context_rail = self._build_context_rail()
        self._provider_selection = ProviderSelectionCoordinator(
            router=self._provider_router,
            sessions=self._coordinator,
            provider_combo=self._provider_combo,
            conversation_composer=self._composer,
            home_composer=self._creative_home.composer,
        )
        if self._embedded:
            self._session_rail.hide()
            self._context_rail.hide()
            root.addWidget(self._center, 1)
            self.setMinimumHeight(640)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        elif self._first_level:
            root.addWidget(self._session_rail)
            root.addWidget(self._center, 1)
            self._context_rail.hide()
        else:
            root.addWidget(self._session_rail)
            root.addWidget(self._center, 1)
            root.addWidget(self._context_rail)

        self._refresh_session_list()
        self._refresh_provider_profiles()
        self._show_empty_state()
        self._refresh_context()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        self._session_sidebar.new_session_requested.connect(self.new_session)
        self._session_sidebar.session_selected.connect(self._open_session_by_id)
        self._session_sidebar.session_menu_requested.connect(
            self._show_session_menu_for_session
        )
        self._session_sidebar.session_pin_requested.connect(self._set_session_pinned)
        self._session_sidebar.session_rename_requested.connect(self._rename_session)
        self._session_sidebar.session_delete_requested.connect(
            self._confirm_delete_session
        )
        self._session_sidebar.session_icon_requested.connect(
            self._show_session_icon_menu
        )
        self._session_sidebar.session_order_requested.connect(
            self._reorder_session_section
        )
        self._session_sidebar.session_move_requested.connect(
            self._move_session_to_section
        )
        self._empty_input.set_submission_handler(
            lambda text: self._send_message(text, source=self._empty_input)
        )
        self._composer.set_submission_handler(
            lambda text: self._send_message(text, source=self._composer)
        )
        self._empty_input.text_changed.connect(self._save_active_draft)
        self._composer.text_changed.connect(self._save_active_draft)
        self._creative_home.provider_changed.connect(self._on_home_provider_selected)
        self._creative_home.open_document_requested.connect(
            self._on_open_document_for_chapter_edit
        )
        self._creative_home.typesetting_requested.connect(
            self._open_typesetting_template_dialog
        )
        self._empty_input.document_paths_changed.connect(
            self._on_composer_documents_selected
        )
        self._composer.document_paths_changed.connect(
            self._on_composer_documents_selected
        )
        self.bridge.document_loaded.connect(self._on_workspace_document_loaded)
        self._stop_button.clicked.connect(self.cancel_active_turn)
        self._composer.cancel_requested.connect(self.cancel_active_turn)
        self._header_more_button.clicked.connect(self._show_active_session_menu)
        self._jump_latest_button.clicked.connect(self._scroll_to_bottom)
        if self._embedded:
            self._session_toggle.clicked.connect(self.new_session)
            self._embedded_session_combo.currentIndexChanged.connect(
                self._open_embedded_session
            )
        else:
            self._session_toggle.clicked.connect(self._toggle_session_rail)
            self._context_toggle.clicked.connect(self._toggle_context_rail)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_selected)
        for signal_name in (
            "document_loaded",
            "scene_changed",
            "template_changed",
            "work_mode_changed",
            "material_package_ref_changed",
            "material_run_selection_changed",
            "material_preview_snapshot_changed",
        ):
            signal = getattr(self.bridge, signal_name, None)
            if signal is not None:
                signal.connect(lambda *_args: self._refresh_context())
        self.bridge.assistant_provider_profiles_changed.connect(
            self._refresh_provider_profiles
        )

    def _build_session_rail(self) -> QFrame:
        sidebar = AssistantSessionSidebar(self)
        self._session_sidebar = sidebar
        self._new_session_button = sidebar.new_session_button
        # Compatibility alias for callers that previously opened a concrete
        # QListWidget item. New code must use AssistantSessionSidebar.
        self._session_list = sidebar.recent_list
        return sidebar

    def _build_center(self) -> QFrame:
        center = QFrame(self)
        center.setObjectName("assistant_center")
        center.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._header_widget = QWidget(center)
        self._header_widget.setObjectName("assistant_header")
        self._header_widget.setFixedHeight(56)
        header = QHBoxLayout(self._header_widget)
        header.setContentsMargins(28, 0, 16, 0)
        header.setSpacing(10)
        self._session_toggle = QPushButton(
            "新对话" if self._embedded else "对话",
            self._header_widget,
        )
        self._session_toggle.setObjectName("assistant_session_toggle")
        self._header_icon = QLabel(self._header_widget)
        self._header_icon.setObjectName("assistant_task_header_icon")
        self._header_icon.setFixedSize(28, 28)
        self._conversation_title = QLabel("AI 文档助手", self._header_widget)
        self._conversation_title.setObjectName("assistant_conversation_title")
        self._conversation_title.setVisible(not self._embedded)
        self._embedded_session_combo = QComboBox(self._header_widget)
        self._embedded_session_combo.setObjectName("assistant_session_combo")
        self._embedded_session_combo.setAccessibleName("历史对话")
        self._embedded_session_combo.setMinimumWidth(132)
        # This selector only belongs to the embedded workbench shell.  Merely
        # leaving it out of the layout does not hide a QWidget; in first-level
        # mode it would otherwise remain at (0, 0) and cover the real header.
        self._embedded_session_combo.setVisible(self._embedded)
        self._header_more_button = QToolButton(self._header_widget)
        self._header_more_button.setObjectName("assistant_task_header_more")
        self._header_more_button.setAccessibleName("对话操作")
        self._header_more_button.setToolTip("固定、重命名或删除当前对话")
        self._header_more_button.setFixedSize(32, 32)
        self._header_more_button.setCursor(Qt.PointingHandCursor)
        self._context_toggle = QPushButton("上下文", self._header_widget)
        self._context_toggle.setObjectName("assistant_context_toggle")
        for button in (self._session_toggle, self._context_toggle):
            apply_button_variant(button, "secondary")
        self._context_toggle.setVisible(not self._embedded and not self._first_level)
        header.addWidget(self._session_toggle)
        header.addWidget(self._header_icon)
        header.addWidget(self._conversation_title)
        if self._embedded:
            header.addWidget(self._embedded_session_combo)
        header.addStretch(1)
        # A dedicated, unmistakable red stop control pinned to the top-right of
        # the assistant panel.  It is driven by turn_flow_mixin
        # (_sync_composer_busy_state) and shown only while the active session is
        # actually generating, so it never clutters idle screens.
        self._stop_button = QPushButton("停止生成", self._header_widget)
        self._stop_button.setObjectName("assistant_stop")
        self._stop_button.setCursor(Qt.PointingHandCursor)
        self._stop_button.hide()
        apply_button_variant(self._stop_button, "danger")
        header.addWidget(self._stop_button)
        header.addSpacing(6)
        header.addWidget(self._header_more_button)
        header.addWidget(self._context_toggle)
        layout.addWidget(self._header_widget)

        self._conversation_stack = QStackedWidget(center)
        self._empty_page = self._build_empty_page()
        self._active_page = self._build_active_page()
        self._conversation_stack.addWidget(self._empty_page)
        self._conversation_stack.addWidget(self._active_page)
        layout.addWidget(self._conversation_stack, 1)
        return center

    def _build_empty_page(self) -> QWidget:
        self._creative_home = AssistantCreativeHome(self.bridge, self)
        self._empty_input = self._creative_home.composer
        self._quick_buttons: list[QPushButton] = []
        return self._creative_home

    def _build_active_page(self) -> QWidget:
        page = AssistantConversationSurface(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._message_scroll = QScrollArea(page)
        self._message_scroll.setObjectName("assistant_message_scroll")
        self._message_scroll.setWidgetResizable(True)
        self._message_scroll.setFrameShape(QFrame.NoFrame)
        self._message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Reserve the vertical gutter even before content overflows. Otherwise
        # the viewport becomes narrower as soon as a new card needs scrolling,
        # which makes every centered card jump horizontally by half the gutter.
        self._message_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._message_scroll.viewport().setObjectName("assistant_message_viewport")
        self._message_scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self._message_host = QWidget(self._message_scroll)
        self._message_host.setObjectName("assistant_message_host")
        self._message_layout = QVBoxLayout(self._message_host)
        self._message_layout.setContentsMargins(0, 18, 0, 18)
        self._message_layout.setSpacing(0)
        self._message_layout.addStretch(1)
        self._message_scroll.setWidget(self._message_host)
        self._message_scroll.verticalScrollBar().valueChanged.connect(
            self._sync_jump_to_latest
        )
        self._message_scroll.verticalScrollBar().rangeChanged.connect(
            self._on_message_scroll_range_changed
        )
        # Left dock (目录大纲) + chat share this page.  The dock stays hidden
        # until a multi-chapter engineering outline is present.
        body = QWidget(page)
        body.setObjectName("assistant_chat_body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self._outline_dock = ChapterOutlineDock(body)
        self._outline_dock.hide()
        self._outline_dock.chapter_activated.connect(self._on_outline_dock_activate)
        self._outline_dock.polish_part_requested.connect(self._request_part_polish)
        self._outline_dock.collapse_changed.connect(self._dock_collapse_changed)
        body_layout.addWidget(self._outline_dock, 0)
        body_layout.addWidget(self._message_scroll, 1)
        self._marktext_view = EmbeddedMarkTextView(body)
        self._marktext_view.setObjectName("assistant_marktext_view")
        self._marktext_view.setFixedWidth(560)
        self._marktext_view.hide()
        self._marktext_view.close_requested.connect(
            self._hide_marktext_view
        )
        self._marktext_view.bridge.request_export_docx.connect(
            self._on_marktext_export_docx
        )
        self._marktext_view.bridge.request_save_markdown.connect(
            self._on_marktext_save_markdown
        )
        self._marktext_view.bridge.request_chapter.connect(
            self._on_marktext_chapter_requested
        )
        self._marktext_view.bridge.request_save_chapter.connect(
            self._on_marktext_save_chapter
        )
        self._marktext_view.bridge.request_live_edit.connect(
            self._on_marktext_live_edit
        )
        body_layout.addWidget(self._marktext_view, 0)
        layout.addWidget(body, 1)

        # This control overlays the viewport instead of occupying a layout row.
        # Showing it must not shrink the message viewport and change the range
        # that caused it to appear.
        self._jump_latest_button = QToolButton(self._message_scroll.viewport())
        self._jump_latest_button.setObjectName("assistant_jump_latest")
        self._jump_latest_button.setText("回到最新消息")
        self._jump_latest_button.setIcon(get_icon("chevron-down", 14))
        self._jump_latest_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._jump_latest_button.setCursor(Qt.PointingHandCursor)
        self._jump_latest_button.hide()

        composer_host = QWidget(page)
        composer_host.setObjectName("assistant_composer_host")
        composer_layout = QHBoxLayout(composer_host)
        composer_layout.setContentsMargins(24, 12, 24, 14)
        composer_layout.setSpacing(0)
        composer_layout.addStretch(1)
        self._composer = AssistantHeroComposer(
            self.bridge,
            composer_host,
            mode="compact",
        )
        self._provider_combo = self._composer._model_combo
        self._provider_settings_button = self._composer._model_settings_button
        composer_layout.addWidget(self._composer)
        composer_layout.addStretch(1)
        layout.addWidget(composer_host)
        return page

    # ---- visual typesetting template plugin ------------------------------
    def _open_typesetting_template_dialog(self) -> None:
        from src.assistant.ui.typesetting_template_dialog import (
            TypesettingTemplateDialog,
        )

        dialog = TypesettingTemplateDialog(self)
        dialog.exec()

    # ---- outline dock bridge -------------------------------------------
    def _dock_outline_present(self, titles):
        dock = getattr(self, "_outline_dock", None)
        if dock is None:
            return
        dock.set_outline(list(titles or ()))
        dock.show()
        dock.raise_()
        self._dock_fuse_bench(dock)

    def _dock_clear(self):
        dock = getattr(self, "_outline_dock", None)
        if dock is None:
            return
        dock.clear()
        dock.hide()

    def _dock_sync_state(self, index, state):
        dock = getattr(self, "_outline_dock", None)
        if dock is None or not dock.isVisible():
            return
        dock.set_state(int(index), str(state))

    def _dock_sync_stats(self, index, *, chars=None, score=None, grade=None):
        dock = getattr(self, "_outline_dock", None)
        if dock is None or not dock.isVisible():
            return
        dock.set_stats(int(index), chars=chars, score=score, grade=grade)

    def _dock_sync_entry(
        self, index, *, state=None, chars=None, score=None, grade=None
    ) -> None:
        dock = getattr(self, "_outline_dock", None)
        if dock is None or not dock.isVisible():
            return
        if state is not None:
            dock.set_state(int(index), str(state))
        if chars is not None or score is not None or grade is not None:
            dock.set_stats(
                int(index),
                chars=chars,
                score=score,
                grade=grade,
            )

    def _dock_restore_from_cache(self, session_id: str) -> bool:
        """Populate the dock from the workbench cache (resumed / saved runs).

        Returns True when an outline existed and the dock is now shown; the
        workbench's duplicate navigator is hidden so the dock stays the single
        left chapter index.
        """
        dock = getattr(self, "_outline_dock", None)
        cache = getattr(self, "_cache", None)
        if dock is None or cache is None:
            return False
        try:
            entries = cache.load_outline(str(session_id or ""))
        except (OSError, ValueError, RuntimeError):
            entries = ()
        if not entries:
            if (
                dock.isVisible()
                and getattr(self, "_dock_session_id", "") != str(session_id or "")
            ):
                self._dock_clear()
            return False
        titles = [e.title for e in entries]
        parts = [getattr(e, "part_title", "") or "" for e in entries]
        dock.set_outline(titles, parts=parts)
        for entry in entries:
            if entry.state and entry.state != "pending":
                dock.set_state(entry.index, entry.state)
            if entry.state == "done" and (
                entry.chars or entry.score or entry.grade != "待写"
            ):
                dock.set_stats(
                    entry.index,
                    chars=entry.chars,
                    score=entry.score,
                    grade=entry.grade,
                )
        self._dock_session_id = str(session_id or "")
        dock.show()
        dock.raise_()
        self._dock_fuse_bench(dock)
        return True

    def _dock_fuse_bench(self, dock) -> None:
        """When the workbench overlay is open next to the dock, drop its own
        navigator (the dock already lists the chapters) and re-lay it out so the
        editor sits immediately to the right of the dock."""
        bench = getattr(self, "_chapter_workbench", None)
        if bench is None or not bench.isVisible():
            return
        try:
            if bench.navigator_visible():
                bench.set_navigator_visible(False)
        except (AttributeError, RuntimeError):
            return
        self._reposition_workbench()
        index = max(0, int(getattr(bench, "current_index", 0) or 0))
        if index:
            dock.set_current(index)

    def _dock_collapse_changed(self) -> None:
        """The dock was collapsed/expanded; re-lay any open workbench beside it."""
        self._reposition_workbench()

    def _dock_set_current(self, index: int) -> None:
        dock = getattr(self, "_outline_dock", None)
        if dock is None or not dock.isVisible():
            return
        dock.set_current(int(index or 0))

    def _on_outline_dock_activate(self, index):
        session = getattr(self, "_active_session", None)
        if session is None:
            return
        cache = getattr(self, "_cache", None)
        if cache is None:
            return
        session_id = (
            getattr(self, "_workbench_session_id", "") or session.session_id
        )
        entries = cache.load_outline(session_id)
        titles = [e.title for e in entries]
        if not titles:
            return
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None and bench.isVisible():
            bench.navigate_chapter(int(index))
        else:
            self._open_workbench_document(
                source_path=getattr(self, "_workbench_source_path", "") or "",
                titles=titles,
            )
            bench = getattr(self, "_chapter_workbench", None)
            if bench is not None:
                bench.navigate_chapter(int(index))
        dock = getattr(self, "_outline_dock", None)
        if dock is not None:
            dock.set_current(int(index))
        # The right-side MarkText surface is deliberately NOT auto-shown when a
        # chapter is activated: the streamed body (with tables) already renders
        # live in the left conversation, and an auto-popping dark editor slab
        # only steals the viewport and reads as "useless black space".  It stays
        # collapsed until the user explicitly opens it.

    # ---- embedded MarkText (right-side) view sync ------------------------
    def _show_marktext_view(self) -> None:
        view = getattr(self, "_marktext_view", None)
        if view is None:
            return
        view.show()
        view.raise_()
        self._refresh_marktext_view()

    def _hide_marktext_view(self) -> None:
        view = getattr(self, "_marktext_view", None)
        if view is not None:
            view.flush_now()
            view.hide()

    def _flush_marktext_edits(self) -> None:
        """Persist any pending right-side editor changes before a session switch."""
        view = getattr(self, "_marktext_view", None)
        if view is not None and view.isVisible():
            view.flush_now()

    def _toggle_marktext_view(self) -> None:
        view = getattr(self, "_marktext_view", None)
        if view is None:
            return
        if view.isVisible():
            self._hide_marktext_view()
        else:
            self._show_marktext_view()

    def _marktext_session_id(self) -> str:
        session = getattr(self, "_active_session", None)
        return (
            getattr(self, "_workbench_session_id", "")
            or (session.session_id if session else "")
        )

    def _refresh_marktext_view(self) -> None:
        """Rebuild the right-side view from the cached chapter bodies."""
        view = getattr(self, "_marktext_view", None)
        session = getattr(self, "_active_session", None)
        if view is None or session is None:
            return
        session_id = self._marktext_session_id()
        entries = self._cache.load_outline(session_id)
        if not entries:
            return
        titles = [e.title for e in entries]
        view.set_outline(titles)
        parts: list[str] = []
        chapters: dict[int, str] = {}
        for entry in entries:
            body = self._cache.read_chapter(session_id, entry.index)
            if body.strip():
                chapters[entry.index] = body.strip()
                parts.append(f"## {entry.title}\n\n{body.strip()}")
        view.bridge.set_chapters(chapters)
        view.set_content("\n\n".join(parts))

    def _on_marktext_chapter_requested(self, index: int) -> None:
        index = int(index or 0)
        view = getattr(self, "_marktext_view", None)
        if view is not None:
            view.set_active_chapter(index)
        if index == 0:
            # Whole-document preview: no need to activate a single chapter.
            return
        self._on_outline_dock_activate(index)

    def _on_marktext_save_chapter(self, index: int, markdown: str) -> None:
        """Persist an edited chapter back into the cache and workbench."""
        session = getattr(self, "_active_session", None)
        if session is None or int(index or 0) <= 0:
            return
        index = int(index)
        session_id = self._marktext_session_id()
        try:
            self._cache.replace_chapter(session_id, index, str(markdown or ""))
        except OSError:
            return
        # Update the bridge chapter map so a later full-document preview
        # reflects the edit without re-pushing content over the live editor.
        view = getattr(self, "_marktext_view", None)
        if view is not None:
            view.bridge.set_chapter_content(index, str(markdown or ""))
            # Recompute the whole-document concatenation silently so the next
            # preview shows the edit without disturbing the live editor.
            entries = self._cache.load_outline(session_id)
            parts = []
            for entry in entries:
                body = self._cache.read_chapter(session_id, entry.index)
                if body.strip():
                    parts.append(f"## {entry.title}\n\n{body.strip()}")
            view.bridge.set_content_silently("\n\n".join(parts))
        # Refresh the workbench editor only (does not touch the web view).
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None and bench.isVisible():
            self._render_workbench_chapter(index)

    def _on_marktext_live_edit(self, index: int, markdown: str) -> None:
        """Real-time mirror of a right-side edit into the left workbench editor.

        Fired on every Muya change (no debounce).  Updates only the visible
        workbench editor for the matching chapter; it does not touch the cache,
        which the debounced save path still owns.
        """
        bench = getattr(self, "_chapter_workbench", None)
        if bench is None or not bench.isVisible():
            return
        current = int(getattr(bench, "_current_index", 0) or 0)
        if current != int(index or 0):
            return
        # Live image insertion changed the markdown: re-point the editor's
        # image base dir at the current workbench source and drop stale cached
        # image resources so an image replaced at the same relative path shows
        # the fresh file rather than the old one.
        prepare = getattr(bench, "prepare_for_render", None)
        if prepare is not None:
            prepare()
        from src.assistant.ui.chapter_workbench_mixin import _parse_outline_blocks

        blocks = _parse_outline_blocks(str(markdown or ""))
        blocks = self._resolve_workbench_image_blocks(blocks)
        if blocks:
            bench.editor.set_outline_document(blocks)
        else:
            bench.editor.clear_document()

    def _on_marktext_export_docx(self, markdown: str) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from src.services.markdown_docx_export import (
            PageConfig,
            export_markdown_to_docx,
        )
        from src.shared.engine.markdown_importer import (
            discover_markdown_resource_paths,
        )

        default = str(Path.home() / "文档.docx")
        output_path, _ = QFileDialog.getSaveFileName(
            self, "导出 DOCX", default, "Word 文档 (*.docx)"
        )
        if not output_path:
            return
        page_config = self._ask_page_config(
            markdown=str(markdown or ""), output_path=str(output_path or "")
        )
        if page_config is None:
            return
        resource_paths = self._resolve_marktext_image_paths(markdown)
        # Prefer images materialised from AI inline data-URLs during chapter
        # runs; the workbench-directory resolution fills any remaining gaps.
        accumulated = getattr(self, "_session_resource_paths", None) or {}
        resource_paths = {**resource_paths, **accumulated}
        try:
            path = export_markdown_to_docx(
                str(markdown or ""),
                output_path,
                resource_paths=resource_paths,
                page_config=page_config,
            )
        except Exception as exc:  # noqa: BLE001 - surface to user
            QMessageBox.warning(self, "导出失败", f"无法导出 DOCX：\n{exc}")
            return
        # Export succeeded — apply the single undo-history strategy (keep by
        # default, clear when the user opted out) through undo_policy so the
        # export decision lives in the same place as save / chapter-switch.
        from src.assistant.ui.undo_policy import UndoEvent, apply_to_view

        apply_to_view(getattr(self, "_marktext_view", None), UndoEvent.EXPORT)
        QMessageBox.information(self, "导出完成", f"已导出：\n{path}")

    def _cover_context_prefill(
        self, markdown: str = ""
    ) -> tuple[str, str, str]:
        """Derive cover (title, subtitle, date) defaults from current context.

        The main title prefers the first level-1 heading of the document being
        exported; when the body has no level-1 heading it prefers a real
        project / document-type name from the bound material run over the raw
        file/session name.  The subtitle prefers a real project / company name
        from the bound material run and falls back to the document-type
        context.  Fields stay editable in the dialog; empty results are left for
        the user to fill.
        """
        import datetime

        # The per-scene field mapping decides what feeds each cover role.
        # (cover_title_source, cover_subtitle_source) each hold either a special
        # sentinel (document first H1 / document context / none) or a material
        # role (“project” / “company”) to pull from the bound material run.
        title_src, subtitle_src = self._scene_cover_sources()
        project_name, company_name = self._cover_entity_identity()

        # --- 主标题：按场景映射选择来源 ---------------------------
        title = ""
        if title_src in ("project",):
            title = project_name
        elif title_src in ("company",):
            title = company_name
        elif title_src == _SRC_NONE:
            title = ""
        else:
            # 默认：整篇文档第一行一级标题优先 -------------------
            title = self._cover_first_h1(markdown=markdown)
            if not title:
                # 无一级标题时，优先取资料包里真实项目名作为主标题（把工程文书
                # 的 project_name 拼进封面主标题），而不是只退回文档文件名。
                if project_name:
                    title = project_name
            if not title:
                doc_path = str(
                    getattr(self, "_workbench_source_path", "") or ""
                ).strip()
                if not doc_path:
                    doc_path = str(
                        self.bridge.current_document_path() or ""
                    ).strip()
                if doc_path and Path(doc_path).suffix.casefold() in {
                    ".md",
                    ".markdown",
                    ".docx",
                    ".doc",
                    ".wps",
                }:
                    title = Path(doc_path).stem.strip()
                if not title:
                    session = getattr(self, "_active_session", None)
                    session_title = str(getattr(session, "title", "") or "").strip()
                    if session_title and session_title not in {
                        "新对话",
                        "AI 文档助手",
                    }:
                        title = session_title

        # --- 副标题：按场景映射选择源 ---------------------------
        parts: list[str] = []
        if subtitle_src == "project":
            # 显式映射到“项目/工程名”：只取项目名，不带公司名。
            if project_name:
                parts.append(project_name)
        elif subtitle_src == "company":
            # 显式映射到“单位/公司名”：只取公司名。
            if company_name:
                parts.append(company_name)
        elif subtitle_src == _SRC_NONE:
            parts = []
        else:
            # 默认：真实项目名优先，找不到再退回文档类型 -----------
            # 若主标题已取用了项目名（无一级标题时），副标题不再重复它，只保留
            # 单位名与文档类型上下文，避免封面标题与副标题堆叠同一项目名。
            project_in_title = bool(project_name) and title == project_name
            if project_name and not project_in_title:
                parts.append(project_name)
                if company_name and company_name != project_name:
                    parts.append(company_name)
            elif company_name:
                parts.append(company_name)
            if not parts:
                parts = self._cover_context_fallback_labels()
        subtitle = " · ".join(part for part in parts if part)

        # --- 日期：默认今天，按记住的模板格式输出，用户可改 ---------------
        today = datetime.date.today()
        date_text = _format_cover_date(today, _load_cover_date_format())

        return title, subtitle, date_text

    def _scene_cover_sources(self) -> tuple[str, str]:
        """Return ``(cover_title_source, cover_subtitle_source)`` for the active
        document scene, honoring the user's per-scene field mapping."""
        try:
            scene_key = _cover_scene_key_for(
                self.bridge.current_work_mode_id(),
                self.bridge.current_scene_id(),
            )
            return _resolve_cover_sources(scene_key)
        except Exception:  # noqa: BLE001 - mapping must never block the dialog
            return (_SRC_DOCUMENT_FIRST_H1, _SRC_DOCUMENT_CONTEXT)

    def _edit_cover_field_mapping(self) -> bool:
        """Let the user configure, for the current document scene, which material
        field feeds the cover title and which feeds the cover subtitle.

        Opens a small modal dialog and persists the choice per scene.  Returns
        ``True`` when the user accepted a mapping change so the caller can
        re-run the cover prefill.
        """
        from src.assistant.ui import cover_field_mapping as _cfm
        from src.qt_api import (
            QComboBox,
            QDialog,
            QLabel,
            QPushButton,
            QVBoxLayout,
            QHBoxLayout,
        )

        try:
            mode_id = self.bridge.current_work_mode_id()
            scene_id = self.bridge.current_scene_id()
        except Exception:  # noqa: BLE001 - scene must never block the dialog
            mode_id, scene_id = "", ""
        scene_key = _cover_scene_key_for(mode_id, scene_id)
        title_src, subtitle_src = _resolve_cover_sources(scene_key)

        scene_display = str(scene_id or mode_id or "默认").strip() or "默认"

        dialog = QDialog(self)
        dialog.setWindowTitle("封面字段映射 · 按文档场景保存")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)

        scene_label = QLabel(
            f"当前场景：{scene_display}\n选择资料包里哪个字段填入封面，各场景可不同。"
        )
        scene_label.setWordWrap(True)
        layout.addWidget(scene_label)

        def _add_source_row(label_text, current_src, options):
            combo = QComboBox()
            current_index = 0
            for i, (src_id, label) in enumerate(options):
                combo.addItem(label, src_id)
                if src_id == current_src:
                    current_index = i
            combo.setCurrentIndex(current_index)
            row = QHBoxLayout()
            row_label = QLabel(label_text)
            row_label.setMinimumWidth(86)
            row.addWidget(row_label)
            row.addWidget(combo, 1)
            layout.addLayout(row)
            return combo

        title_combo = _add_source_row(
            "封面标题", title_src, _cfm.TITLE_SOURCE_OPTIONS
        )
        subtitle_combo = _add_source_row(
            "封面副标题", subtitle_src, _cfm.SUBTITLE_SOURCE_OPTIONS
        )

        reset_btn = QPushButton("恢复该场景默认")
        reset_btn.setToolTip("清除当前场景的映射，恢复 主标题=文档一级标题、副标题=文档类型上下文")

        def _apply_choice():
            _cfm.save_role_source(
                scene_key, "cover_title", str(title_combo.currentData() or "")
            )
            _cfm.save_role_source(
                scene_key, "cover_subtitle", str(subtitle_combo.currentData() or "")
            )

        buttons = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        buttons.addWidget(reset_btn)
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        # “恢复该场景默认”：清空并立即关闭（不回填旧选项）。
        def _reset_and_close():
            _cfm.clear_scene_mapping(scene_key)
            dialog.accept()

        reset_btn.clicked.connect(lambda *_a: _reset_and_close())

        if dialog.exec() != QDialog.Accepted:
            return False
        _apply_choice()
        return True

    def _cover_context_fallback_labels(self) -> list[str]:
        """Mode / scene labels used as a last-resort cover subtitle."""
        parts: list[str] = []
        try:
            mode = self.bridge.current_work_mode()
            mode_label = str(getattr(mode, "label", "") or "").strip()
        except Exception:  # noqa: BLE001 - context must never block the dialog
            mode_label = ""
        if mode_label:
            parts.append(mode_label)
        scene = self.bridge.current_scene()
        scene_label = ""
        if scene is not None:
            scene_label = str(
                getattr(scene, "category_label", "")
                or getattr(scene, "name", "")
                or ""
            ).strip()
            if not scene_label or scene_label == "通用文档":
                scene_label = str(getattr(scene, "name", "") or "").strip()
        if scene_label and scene_label != mode_label:
            parts.append(scene_label)
        return parts

    def _cover_first_h1(self, markdown: str = "") -> str:
        """Return the first level-1 heading of the document being authored. Looks first at the exported Markdown body (a '# ' heading line), then at the active source file (md first heading line, or a docx Heading-1 paragraph). Returns empty when no level-1 heading is found."""
        for source in (markdown,):
            if not str(source or "").strip():
                continue
            for raw in str(source).splitlines():
                line = raw.rstrip()
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    return stripped[2:].strip()
        doc_path = str(getattr(self, "_workbench_source_path", "") or "").strip()
        if not doc_path:
            doc_path = str(self.bridge.current_document_path() or "").strip()
        if doc_path and Path(doc_path).is_file():
            suffix = Path(doc_path).suffix.casefold()
            if suffix in {".md", ".markdown"}:
                try:
                    for raw in Path(doc_path).read_text(
                        encoding="utf-8", errors="ignore"
                    ).splitlines():
                        stripped = raw.strip()
                        if stripped.startswith("# ") and not stripped.startswith("## "):
                            return stripped[2:].strip()
                except OSError:
                    return ""
            if suffix in {".docx", ".doc", ".wps"}:
                return self._docx_first_h1(doc_path)
        return ""

    def _docx_first_h1(self, doc_path: str) -> str:
        """Return the text of the first Heading-1 paragraph in a Word document."""
        try:
            from docx import Document

            document = Document(str(doc_path))
        except Exception:  # noqa: BLE001 - never block the cover prefill
            return ""
        for para in document.paragraphs:
            text = str(para.text or "").strip()
            if not text:
                continue
            style = getattr(para, "style", None)
            style_name = str(getattr(style, "name", style) or "").strip()
            lowered = style_name.casefold().replace(" ", "")
            if lowered in {"heading1", "标题1", "heading1章标题", "标题1章标题"}:
                return text
        return ""

    def _cover_entity_identity(self) -> tuple[str, str]:
        """Read the real project / company name from the bound material run. Values may live at package scope or on the material records; the first non-empty, non-placeholder hit wins. Returns a tuple (project_name, company_name)."""
        project_keys = ("project_name", "项目名称", "entity_name", "项目名")
        company_keys = ("company_name", "公司名称", "公司名", "企业名称")
        token_marker = "{{@text:"

        def _scan(values: Mapping[str, object]) -> tuple[str, str]:
            project = ""
            company = ""
            for key, raw in values.items():
                text = str(raw or "").strip()
                if not text or token_marker in text or ("{{" in text and "}}" in text):
                    continue
                if not project and str(key) in project_keys:
                    project = text
                elif not company and str(key) in company_keys:
                    company = text
            return project, company

        project_name = ""
        company_name = ""
        snapshot = self._best_cover_material_snapshot()
        if snapshot is not None:
            project_name, company_name = _scan(
                dict(getattr(snapshot, "package_field_values", {}) or {})
            )
            if not project_name and not company_name:
                for record in getattr(snapshot, "records", ()) or ():
                    record_values = dict(
                        getattr(record, "field_values", {}) or {}
                    )
                    p, c = _scan(record_values)
                    if p or c:
                        project_name, company_name = p, c
                        break
        return project_name, company_name

    def _best_cover_material_snapshot(self):
        """Best-effort, side-effect-free material snapshot for cover prefill. Prefers an already-resolved snapshot cached from the last generation turn; falls back to re-binding the current material run without publishing issues to the UI."""
        try:
            cached = getattr(self, "_turn_material_snapshots", {}) or {}
            for snapshot in cached.values():
                if snapshot is not None:
                    return snapshot
        except Exception:  # noqa: BLE001
            pass
        try:
            selection = self.bridge.current_material_run_selection()
            if selection is None:
                return None
            from src.application.materials import bind_repository_material_run
            from src.config.material_package_library import (
                material_package_repository,
            )

            mode_id = self.bridge.current_work_mode_id()
            result = bind_repository_material_run(
                material_package_repository(),
                selection,
                work_mode_id=mode_id,
                recipe_id="document_batch",
                scene_id=self.bridge.current_scene_id(),
                document_type=(
                    self.bridge.current_official_document_type_id()
                    if mode_id == "official"
                    else ""
                ),
            )
            return result.snapshot if result.ok else None
        except Exception:  # noqa: BLE001 - never block the export dialog
            return None

    def _ask_page_config(self, markdown: str = "", output_path: str = ""):
        """Prompt for page geometry; returns ``None`` when the user cancels.

        ``markdown`` (when provided) enables a live page-count estimate shown
        in the dialog.  ``output_path`` is the target file that will be
        written; it is shown in the dialog so the user confirms where and how
        many pages the export will produce before proceeding.
        """

        from src.qt_api import (
            QCheckBox,
            QComboBox,
            QDialog,
            QDoubleSpinBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QVBoxLayout,
        )
        from src.services.markdown_docx_export import PageConfig, estimate_page_count

        dialog = QDialog(self)
        dialog.setWindowTitle("导出确认 · 页面设置")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)

        if str(output_path or "").strip():
            path_label = QLabel(f"目标文件：{Path(output_path).expanduser()}")
            path_label.setWordWrap(True)
            layout.addWidget(path_label)

        def add_row(label_text, widget):
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setMinimumWidth(72)
            row.addWidget(label)
            row.addWidget(widget, 1)
            layout.addLayout(row)

        def make_spin(default, maximum=100.0):
            spin = QDoubleSpinBox()
            spin.setDecimals(1)
            spin.setRange(0.0, maximum)
            spin.setSuffix(" mm")
            spin.setValue(default)
            return spin

        paper_combo = QComboBox()
        paper_combo.addItems(["A4", "A3"])
        paper_combo.setCurrentText("A4")
        add_row("纸张大小", paper_combo)

        orientation_combo = QComboBox()
        orientation_combo.addItem("竖版", False)
        orientation_combo.addItem("横版", True)
        add_row("方向", orientation_combo)

        columns_combo = QComboBox()
        columns_combo.addItem("1 栏（单栏）", 1)
        columns_combo.addItem("2 栏", 2)
        add_row("分栏", columns_combo)

        # Optional advanced geometry: margins, column gutter, header/footer.
        custom_margin = QCheckBox("自定义页边距")
        layout.addWidget(custom_margin)

        margin_top = make_spin(25.4)
        margin_bottom = make_spin(25.4)
        margin_left = make_spin(31.7)
        margin_right = make_spin(31.7)
        add_row("上边距", margin_top)
        add_row("下边距", margin_bottom)
        add_row("左边距", margin_left)
        add_row("右边距", margin_right)

        def _sync_margins(enabled):
            for spin in (margin_top, margin_bottom, margin_left, margin_right):
                spin.setEnabled(enabled)

        custom_margin.toggled.connect(_sync_margins)
        _sync_margins(False)

        column_spacing = make_spin(12.7)
        add_row("栏间距", column_spacing)

        image_quality_combo = QComboBox()
        image_quality_combo.addItem("压缩（推荐，适度降采样）", "compressed")
        image_quality_combo.addItem("原图（不压缩，文件最大）", "original")
        image_quality_combo.addItem("强压缩（更小体积，牺牲画质）", "high")
        image_quality_combo.setCurrentIndex(0)
        add_row("图片质量", image_quality_combo)

        header_edit = QLineEdit()
        header_edit.setPlaceholderText("留空则不显示页眉")
        add_row("页眉", header_edit)

        footer_edit = QLineEdit()
        footer_edit.setPlaceholderText("留空则不显示页脚")
        add_row("页脚", footer_edit)

        footer_page_number = QCheckBox("显示页码（第 X 页 共 Y 页）")
        footer_page_number.setChecked(False)
        layout.addWidget(footer_page_number)

        footer_page_restart = QCheckBox("每节重新从第 1 页编号")
        footer_page_restart.setChecked(False)
        layout.addWidget(footer_page_restart)

        def _sync_page_number(enabled):
            footer_page_restart.setEnabled(enabled)

        footer_page_number.toggled.connect(_sync_page_number)
        _sync_page_number(False)

        include_cover = QCheckBox("生成封面页")
        include_cover.setChecked(False)
        layout.addWidget(include_cover)

        # 封面标题/副标题/日期从当前文档上下文自动带出（仍可手动修改）。
        # 主标题优先取整篇文档第一行一级标题，需要把全文传进去。
        pre_title, pre_subtitle, pre_date = self._cover_context_prefill(
            markdown=str(markdown or "")
        )

        cover_title = QLineEdit()
        cover_title.setText(pre_title)
        cover_title.setPlaceholderText("已自动带出当前文档名；留空则不显示")
        add_row("封面标题", cover_title)

        cover_subtitle = QLineEdit()
        cover_subtitle.setText(pre_subtitle)
        cover_subtitle.setPlaceholderText("已自动带出文档类型/项目上下文；可修改")
        add_row("封面副标题", cover_subtitle)

        cover_date = QLineEdit()
        cover_date.setText(pre_date)
        cover_date.setPlaceholderText("封面日期（可留空）")
        add_row("封面日期", cover_date)

        import datetime as _datetime

        date_format_combo = QComboBox()
        date_format_combo.addItems([label for _, label in _COVER_DATE_FORMATS])
        date_format_combo.setCurrentIndex(
            next(
                (
                    i
                    for i, (fmt_id, _) in enumerate(_COVER_DATE_FORMATS)
                    if fmt_id == _load_cover_date_format()
                ),
                0,
            )
        )
        date_format_combo.setToolTip(
            "封面日期模板格式；选择后即用今天的日期按该格式重填"
        )
        add_row("日期格式", date_format_combo)

        def _apply_date_format():
            fmt_id = _COVER_DATE_FORMATS[date_format_combo.currentIndex()][0]
            _save_cover_date_format(fmt_id)
            cover_date.setText(
                _format_cover_date(_datetime.date.today(), fmt_id)
            )

        date_format_combo.currentIndexChanged.connect(
            lambda *_: _apply_date_format()
        )

        def _sync_cover(enabled):
            for edit in (cover_title, cover_subtitle, cover_date):
                edit.setEnabled(enabled)

        include_cover.toggled.connect(_sync_cover)
        _sync_cover(False)

        # 封面预览：未导出前就把将生成的封面标题/副标题（含取自资料包的项目名
        # 与公司名）清晰展示，供用户核对。随 include_cover 与字段编辑实时刷新。
        cover_preview_box = QFrame()
        cover_preview_box.setObjectName("cover_preview_box")
        cover_preview_box.setFrameShape(QFrame.Shape.StyledPanel)
        cover_preview_box.setStyleSheet(
            "QFrame#cover_preview_box {"
            "  background: transparent; border: 1px dashed #9aa0a6;"
            "  border-radius: 6px; padding: 4px 8px;"
            "}"
        )
        cover_preview_layout = QVBoxLayout(cover_preview_box)
        cover_preview_layout.setContentsMargins(8, 6, 8, 6)
        cover_preview_layout.setSpacing(3)
        cover_preview_caption = QLabel("封面预览（导出后将生成以下封面文字）：")
        cover_preview_caption.setWordWrap(True)
        cover_preview_layout.addWidget(cover_preview_caption)
        cover_preview_title_label = QLabel("")
        cover_preview_title_label.setWordWrap(True)
        cover_preview_layout.addWidget(cover_preview_title_label)
        cover_preview_subtitle_label = QLabel("")
        cover_preview_subtitle_label.setWordWrap(True)
        cover_preview_layout.addWidget(cover_preview_subtitle_label)
        cover_preview_date_label = QLabel("")
        cover_preview_date_label.setWordWrap(True)
        cover_preview_layout.addWidget(cover_preview_date_label)
        # 明确标注封面副标题里取自资料包的项目/单位名称（若有）。
        cover_preview_source_label = QLabel("")
        cover_preview_source_label.setWordWrap(True)
        cover_preview_source_label.setStyleSheet(
            "color: #5f6368; font-size: 11px;"
        )
        cover_preview_layout.addWidget(cover_preview_source_label)
        layout.addWidget(cover_preview_box)

        # 解析当前资料包里实际用到的项目名/公司名，作为来源标注（仅展示，不改字段）。
        try:
            project_name, company_name = self._cover_entity_identity()
        except Exception:  # noqa: BLE001 - preview must never block the dialog
            project_name, company_name = "", ""

        def _cover_source_labels():
            """Human label describing the per-scene field mapping in use."""
            from src.assistant.ui import cover_field_mapping as _cfm

            try:
                title_src, subtitle_src = self._scene_cover_sources()
            except Exception:  # noqa: BLE001 - never block the preview
                title_src, subtitle_src = "", ""

            def _name(role_src: str, default: str) -> str:
                for fid, label in {
                    "project": "项目/工程名",
                    "company": "单位/公司名",
                    _cfm.SRC_DOCUMENT_FIRST_H1: "文档一级标题",
                    _cfm.SRC_DOCUMENT_CONTEXT: "文档类型/项目上下文",
                    _cfm.SRC_NONE: "留空",
                }.items():
                    if role_src == fid:
                        return label
                return default

            return _name(title_src, "文档一级标题"), _name(
                subtitle_src, "文档类型/项目上下文"
            )

        def _refresh_cover_preview():
            shown = bool(include_cover.isChecked())
            cover_preview_box.setVisible(shown)
            if not shown:
                return
            title_text = str(cover_title.text() or "").strip()
            subtitle_text = str(cover_subtitle.text() or "").strip()
            date_text = str(cover_date.text() or "").strip()
            title_display = title_text or "（未填写，将不显示主标题）"
            cover_preview_title_label.setText(f"主标题：{title_display}")
            cover_preview_subtitle_label.setText(
                f"副标题：{subtitle_text or '（未填写，将不显示副标题）'}"
            )
            cover_preview_date_label.setText(
                f"日期：{date_text or '（未填写，将不显示日期）'}"
            )
            title_src_label, subtitle_src_label = _cover_source_labels()
            source_parts: list[str] = []
            if project_name:
                source_parts.append(f"项目名：{project_name}")
            if company_name:
                source_parts.append(f"单位/公司：{company_name}")
            mapping_note = (
                f"字段映射：主标题←{title_src_label} · 副标题←{subtitle_src_label}"
            )
            if source_parts:
                source_line = (
                    f"取自资料包 · " + "　".join(source_parts) + "　" + mapping_note
                )
            else:
                source_line = mapping_note
            cover_preview_source_label.setText(source_line)
            cover_preview_source_label.setVisible(True)

        include_cover.toggled.connect(lambda *_a: _refresh_cover_preview())
        cover_title.textChanged.connect(lambda *_a: _refresh_cover_preview())
        cover_subtitle.textChanged.connect(lambda *_a: _refresh_cover_preview())
        cover_date.textChanged.connect(lambda *_a: _refresh_cover_preview())
        cover_preview_box.setVisible(False)

        # 「字段映射…」入口：让当前文档场景可配置 项目名→主标题、公司名→副标题。
        def _open_field_mapping():
            if self._edit_cover_field_mapping():
                # 映射变化后重算预填值并回填可编辑字段与预览。
                try:
                    new_title, new_subtitle, new_date = (
                        self._cover_context_prefill(markdown=str(markdown or ""))
                    )
                except Exception:  # noqa: BLE001 - never block the dialog
                    return
                cover_title.setText(new_title)
                cover_subtitle.setText(new_subtitle)
                cover_date.setText(new_date)
                _refresh_cover_preview()

        mapping_btn = QPushButton("字段映射…")
        mapping_btn.setToolTip(
            "配置当前文档场景下：项目名→封面标题、公司名→封面副标题的映射（按场景保存）"
        )
        mapping_btn.setFlat(True)
        mapping_btn.clicked.connect(lambda *_a: _open_field_mapping())
        layout.addWidget(mapping_btn, alignment=Qt.AlignmentFlag.AlignRight)

        chapter_split = QCheckBox("按章节拆分（每章一个分节符、独立分页）")
        chapter_split.setChecked(True)
        layout.addWidget(chapter_split)

        per_chapter_header = QCheckBox("每章独立页眉（页眉显示章节标题）")
        per_chapter_header.setChecked(True)
        layout.addWidget(per_chapter_header)

        estimate_label = QLabel()
        estimate_label.setWordWrap(True)
        layout.addWidget(estimate_label)

        def _current_config():
            return PageConfig(
                paper=paper_combo.currentText(),
                landscape=orientation_combo.currentData(),
                columns=columns_combo.currentData(),
                margin_top_mm=margin_top.value() if custom_margin.isChecked() else None,
                margin_bottom_mm=margin_bottom.value() if custom_margin.isChecked() else None,
                margin_left_mm=margin_left.value() if custom_margin.isChecked() else None,
                margin_right_mm=margin_right.value() if custom_margin.isChecked() else None,
                image_quality=image_quality_combo.currentData(),
                include_cover=include_cover.isChecked(),
                cover_title=cover_title.text().strip() or None,
                cover_subtitle=cover_subtitle.text().strip() or None,
                cover_date=cover_date.text().strip() or None,
                footer_page_number=footer_page_number.isChecked(),
                footer_page_restart=footer_page_restart.isChecked(),
            )

        def _update_estimate():
            if not markdown:
                estimate_label.setText("")
                return
            try:
                pages = estimate_page_count(markdown, _current_config())
            except Exception:  # noqa: BLE001 - estimate must never block the dialog
                estimate_label.setText("")
                return
            estimate_label.setText(f"预估总页数：约 {pages} 页（按字数粗略估算，仅供参考）")

        paper_combo.currentIndexChanged.connect(lambda *_: _update_estimate())
        orientation_combo.currentIndexChanged.connect(lambda *_: _update_estimate())
        columns_combo.currentIndexChanged.connect(lambda *_: _update_estimate())
        custom_margin.toggled.connect(lambda *_: _update_estimate())
        for spin in (margin_top, margin_bottom, margin_left, margin_right):
            spin.valueChanged.connect(lambda *_: _update_estimate())
        _update_estimate()

        hint = QLabel("提示：A3 横版分 2 栏适合超大版面阅读。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        keep_undo = QCheckBox("导出成功后保留撤销历史（可撤销到导出前）")
        keep_undo.setChecked(_load_export_undo_keep())
        layout.addWidget(keep_undo)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        if dialog.exec() != QDialog.Accepted:
            return None
        # Remember the user's undo-history preference and cover-date format for
        # the next export.
        _save_export_undo_keep(keep_undo.isChecked())
        _save_cover_date_format(
            _COVER_DATE_FORMATS[date_format_combo.currentIndex()][0]
        )
        return PageConfig(
            paper=paper_combo.currentText(),
            landscape=orientation_combo.currentData(),
            columns=columns_combo.currentData(),
            margin_top_mm=margin_top.value() if custom_margin.isChecked() else None,
            margin_bottom_mm=margin_bottom.value() if custom_margin.isChecked() else None,
            margin_left_mm=margin_left.value() if custom_margin.isChecked() else None,
            margin_right_mm=margin_right.value() if custom_margin.isChecked() else None,
            column_spacing_mm=column_spacing.value(),
            header_text=header_edit.text().strip() or None,
            footer_text=footer_edit.text().strip() or None,
            chapter_split=chapter_split.isChecked(),
            per_chapter_header=per_chapter_header.isChecked(),
            image_quality=image_quality_combo.currentData(),
            include_cover=include_cover.isChecked(),
            cover_title=cover_title.text().strip() or None if include_cover.isChecked() else None,
            cover_subtitle=cover_subtitle.text().strip() or None if include_cover.isChecked() else None,
            cover_date=cover_date.text().strip() or None if include_cover.isChecked() else None,
            footer_page_number=footer_page_number.isChecked(),
            footer_page_restart=footer_page_restart.isChecked(),
        )

    def _resolve_workbench_image_blocks(
        self, blocks: list[tuple[int, str]]
    ) -> list[tuple[int, str]]:
        """Resolve image-block src paths (kind 4) to absolute paths so the
        workbench editor can render them as pictures."""
        from src.assistant.ui.chapter_workbench_mixin import _IMAGE

        base = Path(getattr(self, "_workbench_source_path", "") or "").parent
        if not base or str(base) == ".":
            base = Path.cwd()
        resolved: list[tuple[int, str]] = []
        for kind, text in blocks:
            if kind != _IMAGE:
                resolved.append((kind, text))
                continue
            src = str(text or "").strip()
            candidate = (base / src).resolve()
            if candidate.is_file():
                resolved.append((kind, str(candidate)))
            else:
                # Keep the raw src so a missing image still shows its markdown
                # reference rather than disappearing silently.
                resolved.append((kind, src))
        return resolved

    def _resolve_marktext_image_paths(self, markdown: str) -> dict[str, str]:
        """Map markdown image paths to real files, relative to the workbench
        source directory (falling back to the current working directory)."""

        from src.shared.engine.markdown_importer import (
            discover_markdown_resource_paths,
        )

        try:
            referenced = discover_markdown_resource_paths(str(markdown or ""))
        except (TypeError, ValueError):
            return {}
        base = Path(getattr(self, "_workbench_source_path", "") or "").parent
        if not base or str(base) == ".":
            base = Path.cwd()
        resolved: dict[str, str] = {}
        for image_path in referenced:
            candidate = (base / image_path).resolve()
            if candidate.is_file():
                resolved[image_path] = str(candidate)
        return resolved

    def _resolve_memory_dir(self, *, source_path: str = "") -> str | None:
        """Return the folder where ``system_memory.json`` should live for the
        current authoring / editing context, honouring the user's storage
        location preference.

        When the preference is ``project`` and a real project / source document
        is bound (the workbench source, the document being rewritten, or the
        bridge's current document), the memory is stored in that document's own
        folder.  Returns ``None`` when the preference is ``internal`` (default)
        or when no bound file exists, in which case callers fall back to the
        app-internal per-session cache.
        """
        from src.config.app_preferences import resolve_memory_project_dir

        candidates: list[str] = []
        explicit = str(source_path or "").strip()
        if explicit:
            candidates.append(explicit)
        bound = str(getattr(self, "_workbench_source_path", "") or "").strip()
        if bound:
            candidates.append(bound)
        try:
            bridge_doc = str(self.bridge.current_document_path() or "").strip()
        except Exception:  # noqa: BLE001 - bridge may be unavailable in tests
            bridge_doc = ""
        if bridge_doc:
            candidates.append(bridge_doc)
        return resolve_memory_project_dir(tuple(candidates))

    def _migrate_session_memory_to_document(self, session_id: str) -> None:
        """When the user has chosen to keep memory next to their documents,
        copy any app-internal session memory to the newly bound source document
        folder so editing passes reading the document-folder file still recall
        what authoring wrote.  Best-effort; never blocks the open.
        """
        folder = self._resolve_memory_dir()
        if not folder:
            return
        from src.assistant.application.system_memory import SystemMemoryStore

        try:
            SystemMemoryStore().migrate_to_dir(session_id, folder)
        except Exception:  # noqa: BLE001 - best-effort copy must not block
            return

    def _on_marktext_save_markdown(self, markdown: str) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        default = str(Path.home() / "文档.md")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown", default, "Markdown 文件 (*.md)"
        )
        if not path:
            return
        try:
            Path(path).write_text(str(markdown or ""), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"无法保存：\n{exc}")
            return
        # Save succeeded — apply the single undo-history strategy for non-export
        # saves (mirrors the DOCX export flow and the chapter-switch policy) via
        # undo_policy so the decision is centralised, not inlined here.
        from src.assistant.ui.undo_policy import UndoEvent, apply_to_view

        apply_to_view(getattr(self, "_marktext_view", None), UndoEvent.SAVE_MARKDOWN)

    def _build_context_rail(self) -> QFrame:
        rail = QFrame(self)
        rail.setObjectName("assistant_context_rail")
        rail.setFixedWidth(TOKENS.context_rail_width)
        rail.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        title = QLabel("当前上下文", rail)
        title.setObjectName("assistant_context_title")
        layout.addWidget(title)
        self._context_document = self._context_value(rail)
        self._context_mode = self._context_value(rail)
        self._context_scene = self._context_value(rail)
        self._context_template = self._context_value(rail)
        for label, value in (
            ("输入文档", self._context_document),
            ("工作模式", self._context_mode),
            ("方案", self._context_scene),
            ("模板", self._context_template),
        ):
            caption = QLabel(label, rail)
            caption.setObjectName("assistant_context_caption")
            layout.addWidget(caption)
            layout.addWidget(value)
        disclosure = QLabel(
            "只添加材料不会上传；点击发送后，附件正文会提供给当前选择的模型。",
            rail,
        )
        disclosure.setObjectName("assistant_context_disclosure")
        disclosure.setWordWrap(True)
        layout.addWidget(disclosure)
        layout.addStretch(1)
        return rail

    @staticmethod
    def _context_value(parent: QWidget) -> QLabel:
        label = QLabel("未选择", parent)
        label.setObjectName("assistant_context_value")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def new_session(self) -> None:
        if not self._flush_active_draft():
            return
        if self._active_session is not None and self._session_is_pristine(
            self._active_session
        ):
            self._session_sidebar.select_session(
                self._active_session.session_id
            )
            self._render_active_session()
            self._sync_composer_busy_state()
            self._empty_input.focus_input()
            self._close_session_drawer_after_navigation()
            return
        profile_id, model_id = self._provider_selection.selected_identity()
        session = None
        try:
            session = self._coordinator.create_session(
                provider_profile_id=profile_id,
                model_id=model_id,
            )
            initial_refs = self._context_refs_for_path(
                str(self.bridge.current_document_path() or "")
            )
            if initial_refs:
                session = self._coordinator.update_state(
                    session,
                    context_refs=initial_refs,
                    touch_activity=False,
                )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            if session is not None:
                try:
                    self._coordinator.delete_session(session.session_id)
                except (OSError, RuntimeError, TypeError, ValueError):
                    pass
            self._show_session_navigation_error(
                "无法新建对话",
                exc,
            )
            return
        self._active_session = session
        self._clear_session_navigation_error()
        self._refresh_session_list(select_session_id=session.session_id)
        self._render_active_session()
        self._load_draft_text("")
        self._sync_session_document_path()
        self._sync_composer_busy_state()
        self._empty_input.focus_input()
        self._close_session_drawer_after_navigation()

    def _session_is_pristine(self, session: AssistantSession) -> bool:
        return (
            not session.messages
            and not session.draft_text
            and not session.active_plan
            and not session.pending_continuation
            and not session.document_job
            and not session.context_refs
            and session.session_id not in self._turn_workers
        )

    def _open_session_item(self, item: QListWidgetItem) -> None:
        session_id = str(item.data(Qt.UserRole) or "")
        self._open_session_by_id(session_id)

    def _open_session_by_id(self, session_id: str) -> None:
        if not str(session_id or ""):
            return
        if (
            self._active_session is not None
            and self._active_session.session_id == session_id
        ):
            self._active_session = self._mark_session_read(
                self._active_session
            )
            self._refresh_session_list(select_session_id=session_id)
            self._close_session_drawer_after_navigation()
            return
        if not self._flush_active_draft():
            return
        corrupt_summary = next(
            (
                summary
                for summary in self._coordinator.list_sessions()
                if summary.session_id == session_id and summary.corrupt
            ),
            None,
        )
        if corrupt_summary is not None:
            self._show_corrupt_session_recovery(
                corrupt_summary.recovery_path
            )
            return
        try:
            loaded_session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError) as exc:
            self._show_session_navigation_error(
                "无法打开该对话",
                exc,
            )
            return
        self._flush_marktext_edits()
        self._active_session = self._mark_session_read(loaded_session)
        self._clear_session_navigation_error()
        self._refresh_session_list(select_session_id=session_id)
        self._provider_selection.select(self._active_session.provider_profile_id)
        self._render_active_session()
        self._load_draft_text(self._active_session.draft_text)
        self._sync_session_document_path()
        self._sync_composer_busy_state()
        self._close_session_drawer_after_navigation()

    def _show_session_navigation_error(
        self,
        message: str,
        exc: BaseException,
    ) -> None:
        reason = f"{message}。错误类型：{type(exc).__name__}"
        self._composer.set_submission_error(reason)
        self._empty_input.set_submission_error(reason)

    def _clear_session_navigation_error(self) -> None:
        self._composer.set_submission_error("")
        self._empty_input.set_submission_error("")

    def _session_snapshot_for_mutation(
        self,
        session_id: str,
    ) -> AssistantSession:
        if (
            self._active_session is not None
            and self._active_session.session_id == session_id
        ):
            return self._active_session
        return self._coordinator.load_session(session_id)

    def _adopt_persisted_session_snapshot(
        self,
        session: AssistantSession,
    ) -> None:
        if (
            self._active_session is None
            or self._active_session.session_id != session.session_id
        ):
            return
        self._active_session = session
        if self._pending_draft_session_id == session.session_id:
            self._draft_save_timer.stop()
            self._pending_draft_session_id = ""

    def _mark_session_read(
        self,
        session: AssistantSession,
    ) -> AssistantSession:
        if not session.unread:
            return session
        try:
            return self._coordinator.set_unread(session, False)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._show_session_state_persistence_error(
                "已读状态",
                exc,
            )
            return session

    def _project_completion_read_state(
        self,
        session: AssistantSession,
    ) -> AssistantSession:
        is_active = (
            self._active_session is not None
            and self._active_session.session_id == session.session_id
        )
        target_unread = not is_active
        if session.unread == target_unread:
            return session
        try:
            return self._coordinator.set_unread(
                session,
                target_unread,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._show_session_state_persistence_error(
                "未读状态",
                exc,
            )
            return session

    def _show_session_state_persistence_error(
        self,
        state_name: str,
        exc: BaseException,
    ) -> None:
        show_warning(
            "会话状态未保存",
            (
                f"{state_name}没有写入本地存储，请检查磁盘后重试。"
                f"\n错误类型：{type(exc).__name__}"
            ),
            parent=self,
        )

    def _show_corrupt_session_recovery(self, recovery_path: str) -> None:
        path = Path(str(recovery_path or "")).expanduser()
        action = decision(
            "会话文件需要恢复",
            "该会话文件无法解析，应用没有删除或覆盖原文件。\n"
            f"原文件：{path}\n"
            "可以打开所在文件夹，备份或交给维护人员修复。",
            actions=(
                DialogAction("close", "关闭", default=True, escape=True),
                DialogAction("open", "打开所在文件夹", variant="primary"),
            ),
            icon_style="warning",
            parent=self,
        )
        if action == "open":
            self._open_corrupt_session_folder(str(path))

    @staticmethod
    def _open_corrupt_session_folder(recovery_path: str) -> None:
        path = Path(str(recovery_path or "")).expanduser()
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(path.parent.resolve(strict=False)))
        )

    def _save_active_draft(self, text: str) -> None:
        if self._loading_draft or self._active_session is None:
            return
        normalized = str(text or "")
        if normalized == self._active_session.draft_text:
            if (
                not normalized
                and self._pending_draft_session_id
                == self._active_session.session_id
            ):
                self._draft_save_timer.stop()
                self._pending_draft_session_id = ""
            return
        self._active_session = self._coordinator.stage_draft(
            self._active_session,
            normalized,
        )
        self._pending_draft_session_id = self._active_session.session_id
        self._draft_save_timer.start()

    def _flush_active_draft(self) -> bool:
        self._draft_save_timer.stop()
        pending_session_id = self._pending_draft_session_id
        if not pending_session_id:
            return True
        session = self._active_session
        if session is None or session.session_id != pending_session_id:
            return False
        try:
            self._active_session = self._coordinator.persist(session)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            reason = (
                "草稿暂未保存到本地；输入内容仍保留在当前窗口。"
                f"错误类型：{type(exc).__name__}"
            )
            self._composer.set_submission_error(reason)
            self._empty_input.set_submission_error(reason)
            return False
        self._pending_draft_session_id = ""
        self._composer.set_submission_error("")
        self._empty_input.set_submission_error("")
        return True

    def _load_draft_text(self, text: str) -> None:
        self._loading_draft = True
        try:
            if self._empty_input.get_text() != text:
                self._empty_input.set_text(text)
            if self._composer.get_text() != text:
                self._composer.set_text(text)
        finally:
            self._loading_draft = False

    def _on_composer_document_selected(self, path: str) -> None:
        """Compatibility adapter for callers that still select one material."""

        self._on_composer_documents_selected((str(path or ""),) if path else ())

    def _on_composer_documents_selected(self, paths: object) -> None:
        """Own the complete composer material set by assistant session."""

        self._composer.set_submission_gate("")
        self._empty_input.set_submission_gate("")
        if self._active_session is None:
            profile_id, model_id = self._provider_selection.selected_identity()
            self._active_session = self._coordinator.create_session(
                provider_profile_id=profile_id,
                model_id=model_id,
            )
        refs = self._context_refs_for_paths(
            tuple(paths) if isinstance(paths, (tuple, list)) else ()
        )
        self._active_session = self._coordinator.update_state(
            self._active_session,
            context_refs=refs,
            touch_activity=False,
        )
        self._sync_session_document_path()
        self._refresh_session_list(
            select_session_id=self._active_session.session_id
        )
        self._refresh_context()

    def _on_workspace_document_loaded(self, path: str) -> None:
        """Adopt global workspace changes only before a session owns context."""

        session = self._active_session
        if session is not None and (session.context_refs or session.messages):
            return
        normalized = str(path or "").strip()
        selected_paths = (normalized,) if normalized else ()
        self._empty_input.set_document_paths(selected_paths)
        self._composer.set_document_paths(selected_paths)
        if session is not None:
            self._active_session = self._coordinator.update_state(
                session,
                context_refs=self._context_refs_for_path(normalized),
                touch_activity=False,
            )
        self._refresh_context()

    def _sync_session_document_path(self) -> None:
        paths: list[str] = []
        if self._active_session is not None:
            for reference in self._active_session.context_refs:
                path = str(
                    reference.get("path")
                    or reference.get("file_path")
                    or reference.get("local_path")
                    or ""
                ).strip()
                if path:
                    paths.append(path)
        selected_paths = tuple(paths)
        self._empty_input.set_document_paths(selected_paths)
        self._composer.set_document_paths(selected_paths)

    def _show_session_menu(self, position) -> None:
        item = self._session_list.itemAt(position)
        if item is None:
            return
        session_id = str(item.data(Qt.UserRole) or "")
        self._show_session_menu_for_session(
            session_id,
            self._session_list.viewport().mapToGlobal(position),
        )

    def _show_session_menu_for_session(self, session_id: str, global_position) -> None:
        if not session_id:
            return
        corrupt_summary = next(
            (
                summary
                for summary in self._coordinator.list_sessions()
                if summary.session_id == session_id and summary.corrupt
            ),
            None,
        )
        if corrupt_summary is not None:
            menu = ContextMenu(parent=self)
            menu.add_action(
                "打开所在文件夹",
                callback=lambda: self._open_corrupt_session_folder(
                    corrupt_summary.recovery_path
                ),
            )
            menu.add_separator()
            menu.add_action(
                "从列表移除",
                callback=lambda: self._session_sidebar.request_delete_confirmation(
                    session_id
                ),
            )
            menu.exec_(global_position)
            return
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法打开菜单",
                "对话无法读取，可刷新列表后重试。",
                parent=self,
            )
            return
        menu = ContextMenu(parent=self)
        menu.add_action(
            "取消固定" if session.pinned else "固定对话",
            callback=lambda: self._set_session_pinned(session_id, not session.pinned),
        )
        menu.add_action("重命名", callback=lambda: self._prompt_rename_session(session_id))
        icon_menu = ContextMenu(parent=menu)
        icon_menu.setTitle("更换图标")
        self._populate_session_icon_menu(
            icon_menu,
            session_id=session_id,
            current_icon=session.icon_name,
        )
        menu.addMenu(icon_menu)
        menu.add_separator()
        menu.add_action(
            "删除",
            callback=lambda: self._session_sidebar.request_delete_confirmation(
                session_id
            ),
        )
        menu.exec_(global_position)

    def _show_active_session_menu(self) -> None:
        if self._active_session is None:
            return
        position = self._header_more_button.mapToGlobal(
            self._header_more_button.rect().bottomLeft()
        )
        self._show_session_menu_for_session(
            self._active_session.session_id,
            position,
        )

    def _prompt_rename_session(self, session_id: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法重命名",
                "对话无法读取，名称没有更改。",
                parent=self,
            )
            return
        title = input_text(
            "重命名对话",
            "对话名称：",
            default=session.title,
            parent=self,
        )
        if title is not None:
            self._rename_session(session_id, title)

    def _rename_session(self, session_id: str, title: str) -> bool:
        normalized = str(title or "").strip()
        if not normalized:
            show_warning(
                "无法重命名",
                "对话名称不能为空。",
                parent=self,
            )
            return False
        try:
            session = self._session_snapshot_for_mutation(session_id)
            updated = self._coordinator.rename(session, normalized)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法重命名",
                "新名称没有保存，请稍后重试。",
                parent=self,
            )
            self._session_sidebar.restore_rename(session_id, normalized)
            return False
        self._adopt_persisted_session_snapshot(updated)
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._conversation_title.setText(updated.title)
        self._refresh_session_list()
        return True

    def _set_session_pinned(self, session_id: str, pinned: bool) -> bool:
        try:
            session = self._session_snapshot_for_mutation(session_id)
            updated = self._coordinator.set_pinned(session, pinned)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法调整固定状态",
                "固定状态没有保存，请稍后重试。",
                parent=self,
            )
            return False
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = updated
        self._refresh_session_list()
        return True

    def _show_session_icon_menu(self, session_id: str, global_position) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法更换图标",
                "对话无法读取，图标没有更改。",
                parent=self,
            )
            return
        menu = ContextMenu(parent=self)
        self._populate_session_icon_menu(
            menu,
            session_id=session_id,
            current_icon=session.icon_name,
        )
        menu.exec_(global_position)

    def _populate_session_icon_menu(
        self,
        menu: ContextMenu,
        *,
        session_id: str,
        current_icon: str,
    ) -> None:
        for icon_name, label in SESSION_ICON_OPTIONS:
            menu.add_action(
                label,
                icon="✓" if current_icon == icon_name else "",
                callback=lambda _checked=False, value=icon_name: (
                    self._set_session_icon(session_id, value)
                ),
            )

    def _set_session_icon(self, session_id: str, icon_name: str) -> bool:
        try:
            session = self._session_snapshot_for_mutation(session_id)
            updated = self._coordinator.set_icon(session, icon_name)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法更换图标",
                "会话图标没有保存，请稍后重试。",
                parent=self,
            )
            return False
        self._adopt_persisted_session_snapshot(updated)
        self._refresh_session_list()
        return True

    def _reorder_session_section(
        self,
        ordered_ids,
        pinned: bool,
    ) -> bool:
        normalized = tuple(str(value or "") for value in ordered_ids)
        try:
            updated = self._coordinator.reorder_sessions(
                normalized,
                pinned=bool(pinned),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            show_warning(
                "无法调整顺序",
                "对话顺序没有保存，列表已恢复到上次保存的状态。",
                parent=self,
            )
            self._refresh_session_list(
                select_session_id=(
                    self._active_session.session_id
                    if self._active_session is not None
                    else ""
                )
            )
            return False
        self._adopt_updated_active_session(updated)
        self._refresh_session_list(
            select_session_id=(
                self._active_session.session_id
                if self._active_session is not None
                else ""
            )
        )
        return True

    def _move_session_to_section(
        self,
        session_id: str,
        pinned: bool,
        target_index: int,
    ) -> bool:
        normalized_id = str(session_id or "")
        try:
            updated = self._coordinator.move_session_to_section(
                normalized_id,
                pinned=bool(pinned),
                target_index=int(target_index),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            show_warning(
                "无法移动对话",
                "对话位置没有保存，列表已恢复到上次保存的状态。",
                parent=self,
            )
            self._refresh_session_list(
                select_session_id=(
                    self._active_session.session_id
                    if self._active_session is not None
                    else ""
                )
            )
            return False
        self._adopt_updated_active_session(updated)
        self._refresh_session_list()
        return True

    def _adopt_updated_active_session(self, sessions) -> None:
        if self._active_session is None:
            return
        active_id = self._active_session.session_id
        replacement = next(
            (
                session
                for session in sessions
                if session.session_id == active_id
            ),
            None,
        )
        if replacement is not None:
            self._active_session = replace(
                self._active_session,
                pinned=replacement.pinned,
                sidebar_order=replacement.sidebar_order,
            )

    def _confirm_delete_session(self, session_id: str) -> None:
        """Handle a deletion that the user already confirmed in the session row."""
        corrupt_summary = next(
            (
                summary
                for summary in self._coordinator.list_sessions()
                if summary.session_id == session_id and summary.corrupt
            ),
            None,
        )
        if corrupt_summary is not None:
            self._confirm_remove_corrupt_session(corrupt_summary)
            return
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            show_warning(
                "无法删除",
                "对话无法读取，因此没有删除任何内容。",
                parent=self,
            )
            return
        job_status = str(session.document_job.get("status") or "")
        if session.turn_status == "provider_running" or job_status in {
            "content_generation_running",
            "preflight_running",
            "execution_running",
        }:
            show_info(
                "任务仍在运行",
                "请先停止当前任务，再删除该对话。文档产物不会随对话删除。",
                parent=self,
            )
            return
        self._delete_session(session_id)

    def _confirm_remove_corrupt_session(self, summary) -> None:
        try:
            self._coordinator.quarantine_corrupt_session(
                summary.recovery_path
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            show_warning(
                "无法移除会话",
                "损坏会话文件未移动，请检查文件是否仍存在或是否可写。",
                parent=self,
            )
            return
        self._refresh_session_list()

    def _delete_session(self, session_id: str) -> bool:
        if session_id in self._turn_workers:
            show_info(
                "任务仍在运行",
                "请先停止当前任务，再删除该对话。",
                parent=self,
            )
            return False
        discard_pending_draft = self._pending_draft_session_id == session_id
        try:
            deleted = self._coordinator.delete_session(session_id)
        except (OSError, RuntimeError, TypeError, ValueError):
            deleted = False
        if not deleted:
            show_warning(
                "无法删除",
                "对话没有被删除，请检查本地存储是否可写。",
                parent=self,
            )
            return False
        if discard_pending_draft:
            self._draft_save_timer.stop()
            self._pending_draft_session_id = ""
        was_active = (
            self._active_session is not None
            and self._active_session.session_id == session_id
        )
        if was_active:
            summaries = self._coordinator.list_sessions()
            self._active_session = None
            for summary in summaries:
                if summary.corrupt:
                    continue
                try:
                    self._active_session = self._coordinator.load_session(
                        summary.session_id
                    )
                except (OSError, ValueError, TypeError):
                    continue
                self._active_session = self._mark_session_read(
                    self._active_session
                )
                break
            if self._active_session is None:
                self._show_empty_state()
                self._load_draft_text("")
            else:
                self._provider_selection.select(
                    self._active_session.provider_profile_id
                )
                self._render_active_session()
                self._load_draft_text(self._active_session.draft_text)
            self._sync_session_document_path()
        self._refresh_session_list(
            select_session_id=(
                self._active_session.session_id
                if self._active_session is not None
                else ""
            )
        )
        return True


    def _render_active_session(self) -> None:
        session = self._active_session
        if session is not None:
            self._activate_turn_preview(session.session_id)
            self._sync_turn_worker_alias()
        if session is None or not session.messages:
            self._show_empty_state()
            return
        same_session = self._rendered_session_id == session.session_id
        previous_scroll = self._message_scroll.verticalScrollBar().value()
        force_follow = self._force_follow_latest
        self._force_follow_latest = False
        follow_latest = (
            force_follow or not same_session or self._is_near_latest()
        )
        self._conversation_stack.setCurrentWidget(self._active_page)
        self._header_widget.setVisible(True)
        self._conversation_title.setText(session.title)
        interaction_card_width = self._interaction_card_available_width()
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._turn_preview_widget = None
        self._chapter_live_widget = None
        latest_recovery_message_id = ""
        for candidate_message in session.messages:
            for candidate_block in candidate_message.blocks:
                if (
                    candidate_block.type == BLOCK_INTERACTION
                    and str(
                        candidate_block.data.get("interaction_type") or ""
                    ).casefold()
                    == "recovery"
                ):
                    latest_recovery_message_id = candidate_message.message_id
        for message in session.messages:
            for block in message.blocks:
                if block.type == BLOCK_TEXT:
                    message_widget = AssistantConversationMessage(
                        text=block.text,
                        role=message.role,
                        message_id=message.message_id,
                        source_refs=message.source_refs,
                        parent=self._message_host,
                    )
                    self._wire_message_widget(message_widget)
                    self._message_layout.insertWidget(
                        self._message_layout.count() - 1,
                        message_widget,
                    )
                elif block.type in {BLOCK_INTERACTION, BLOCK_ARTIFACT}:
                    interaction_type = str(
                        block.data.get("interaction_type") or "info"
                    )
                    card_payload = dict(block.data)
                    card_payload["_is_latest_recovery"] = bool(
                        latest_recovery_message_id
                        and message.message_id == latest_recovery_message_id
                    )
                    card_payload["active"] = interaction_is_active(
                        interaction_type=interaction_type,
                        payload=card_payload,
                        pending_continuation=session.pending_continuation,
                        active_plan=session.active_plan,
                        document_job=session.document_job,
                        turn_status=session.turn_status,
                    )
                    card_payload["action_scope"] = (
                        build_interaction_action_scope(
                            pending_continuation=session.pending_continuation,
                            active_plan=session.active_plan,
                            document_job=session.document_job,
                            turn_status=session.turn_status,
                        )
                        if card_payload["active"]
                        else {}
                    )
                    card_title = str(block.data.get("title") or "需要确认")
                    card_body = block.text
                    if interaction_type in {"preflight", "approval"} and card_payload[
                        "active"
                    ]:
                        active_preflight = active_preflight_card_presentation(
                            active_plan=session.active_plan,
                            document_job=session.document_job,
                        )
                        if active_preflight is not None:
                            interaction_type = active_preflight.interaction_type
                            card_title = active_preflight.title
                            card_body = active_preflight.body
                            card_payload.update(
                                {
                                    "interaction_type": interaction_type,
                                    "title": card_title,
                                    "facts": [
                                        {"label": label, "value": value}
                                        for label, value in active_preflight.facts
                                    ],
                                    "notices": list(active_preflight.notices),
                                    "actions": list(active_preflight.actions),
                                    "presentation_version": 2,
                                }
                            )
                    if (
                        interaction_type == "progress"
                        and bool(card_payload.get("ephemeral"))
                        and not card_payload["active"]
                    ):
                        continue
                    card_host = QWidget(self._message_host)
                    card_host.setObjectName("assistant_interaction_reading_column")
                    card_layout = QHBoxLayout(card_host)
                    # 与 AI 文本消息同轴：卡片贴左缘（16px 呼吸边距），右侧
                    # stretch 吸收剩余宽度，不再双侧居中留下对称空白。
                    card_layout.setContentsMargins(16, 8, 8, 8)
                    card_layout.setSpacing(0)
                    card = AssistantInteractionCard(
                        interaction_type=interaction_type,
                        title=card_title,
                        body=card_body,
                        payload=card_payload,
                        parent=card_host,
                    )
                    card.action_requested.connect(self._handle_card_action)
                    # Apply the final geometry before the card enters a visible
                    # layout. Letting Qt paint its natural width first and then
                    # fixing it on a timer produces a conspicuous center jump.
                    card.setFixedWidth(
                        card.preferred_width(interaction_card_width)
                    )
                    card_layout.addWidget(card)
                    card_layout.addStretch(1)
                    self._message_layout.insertWidget(
                        self._message_layout.count() - 1,
                        card_host,
                    )
        if self._turn_preview_session_id == session.session_id:
            preview = AssistantConversationMessage(
                text=self._turn_preview_text,
                role=ROLE_ASSISTANT,
                live=True,
                status_text=self._turn_preview_status or "正在处理",
                parent=self._message_host,
            )
            self._turn_preview_widget = preview
            self._wire_message_widget(preview)
            self._message_layout.insertWidget(
                self._message_layout.count() - 1,
                preview,
            )
        self._rendered_session_id = session.session_id
        if hasattr(self, "_dock_restore_from_cache"):
            self._dock_restore_from_cache(session.session_id)
        if follow_latest:
            self._begin_follow_latest_layout_settle()
        else:
            self._cancel_follow_latest_layout_settle()
            QTimer.singleShot(
                0,
                lambda value=previous_scroll: self._restore_scroll_value(value),
            )
        QTimer.singleShot(0, self._sync_active_reading_widths)

    def _wire_message_widget(self, message: AssistantConversationMessage) -> None:
        message.source_requested.connect(self._open_message_reference)
        message.link_requested.connect(self._open_message_link)
        message.action_requested.connect(self._handle_message_action)

    def _handle_message_action(self, action_id: str, message_id: str) -> None:
        session = self._active_session
        if session is None:
            return
        index = next(
            (
                item_index
                for item_index, message in enumerate(session.messages)
                if message.message_id == message_id
            ),
            -1,
        )
        if index < 0:
            return
        if action_id == "quote":
            text = session.messages[index].visible_text().strip()
            if not text:
                return
            excerpt = text if len(text) <= 500 else text[:500].rstrip() + "…"
            composer = (
                self._composer
                if self._conversation_stack.currentWidget() is self._active_page
                else self._empty_input
            )
            current = composer.get_text().strip()
            quoted = "\n".join(f"> {line}" for line in excerpt.splitlines())
            composer.set_text(f"{current}\n\n{quoted}\n\n" if current else f"{quoted}\n\n")
            composer.focus_input()
            return
        if action_id == "retry":
            for previous in reversed(session.messages[:index]):
                if previous.role == ROLE_USER and previous.visible_text().strip():
                    self._send_message(previous.visible_text())
                    return

    def _open_message_link(self, target: str) -> None:
        self._open_message_reference({"url": str(target or "")})

    def _open_runtime_reference(self, reference: object) -> None:
        """Open only remote provider references; host artifacts use typed actions."""

        if not isinstance(reference, Mapping):
            return
        if any(
            str(reference.get(key) or "").strip()
            for key in ("path", "file_path", "local_path")
        ):
            show_warning(
                "链接不可用",
                "模型返回的本地路径不会由应用直接打开。",
                parent=self,
            )
            return
        url_text = str(
            reference.get("url")
            or reference.get("href")
            or reference.get("uri")
            or ""
        ).strip()
        url = QUrl(url_text)
        if url_text and url.scheme().casefold() in {"http", "https", "mailto"}:
            QDesktopServices.openUrl(url)
            return
        show_warning(
            "链接不可用",
            "模型建议仅支持 http、https 和 mailto 链接。",
            parent=self,
        )

    def _open_message_reference(self, reference: object) -> None:
        if not isinstance(reference, Mapping):
            return
        target = str(
            reference.get("path")
            or reference.get("file_path")
            or reference.get("local_path")
            or ""
        ).strip()
        if target:
            path = Path(target).expanduser()
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
                return
            show_warning(
                "来源不可用",
                f"找不到本地来源：\n{target}",
                parent=self,
            )
            return
        url_text = str(
            reference.get("url")
            or reference.get("href")
            or reference.get("uri")
            or ""
        ).strip()
        if url_text:
            url = QUrl(url_text)
            if url.scheme().casefold() in {"http", "https", "mailto", "file"}:
                QDesktopServices.openUrl(url)
                return
            show_warning(
                "链接不可用",
                "仅支持 http、https、mailto 和 file 链接。",
                parent=self,
            )
            return
        title = str(reference.get("title") or reference.get("name") or "来源详情")
        snippet = str(
            reference.get("snippet")
            or reference.get("excerpt")
            or reference.get("text")
            or "该来源没有可打开的目标。"
        )
        show_info(title, snippet, parent=self)

    def _provider_data_domain(self, profile_id: str) -> str:
        try:
            profile = self._provider_router.profiles.get(profile_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return f"unknown:{profile_id}"
        if profile.kind == "mock":
            return "local:mock"
        return (
            f"{profile.kind}:"
            f"{str(profile.base_url or '').strip().casefold().rstrip('/')}"
        )

    def _confirm_provider_history_transition(
        self,
        source_profile_id: str,
        target_profile_id: str,
        *,
        message_count: int,
        character_count: int,
    ) -> str:
        return decision(
            "确认历史对话的数据范围",
            f"你正在从 {source_profile_id} 切换到 {target_profile_id}。\n"
            f"当前会话包含 {message_count} 条、约 {character_count} 个字符。"
            "请选择是否把这些历史发送给新的模型服务。",
            actions=(
                DialogAction("cancel", "取消", default=True, escape=True),
                DialogAction("new", "新建空白对话"),
                DialogAction("carry", "携带历史并切换", variant="primary"),
            ),
            icon_style="warning",
            parent=self,
        )

    def _on_home_provider_selected(self, profile_id: str) -> None:
        self._provider_selection.select(profile_id)
        self._on_provider_selected(self._provider_combo.currentIndex())

    def _show_empty_state(self) -> None:
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None and bench.isVisible():
            bench.hide()
        self._workbench_session_id = ""
        dock = getattr(self, "_outline_dock", None)
        if dock is not None:
            dock.clear()
            dock.hide()
        self._conversation_stack.setCurrentWidget(self._empty_page)
        self._header_widget.setVisible(not self._embedded and not self._first_level)
        self._conversation_title.setText(
            self._active_session.title if self._active_session is not None else "AI 文档助手"
        )

    def show_entry(self) -> None:
        """Restore the current conversation, or show the first-level creative home."""

        if self._active_session is not None and self._active_session.messages:
            self._render_active_session()
            self._sync_composer_busy_state()
            self._composer.focus_input()
            return
        self._show_empty_state()
        self._sync_composer_busy_state()
        self._empty_input.focus_input()

    def _refresh_session_list(self, *, select_session_id: str = "") -> None:
        selected = select_session_id or (
            self._active_session.session_id if self._active_session is not None else ""
        )
        summaries = self._coordinator.list_sessions()
        self._session_sidebar.replace_sessions(
            summaries,
            selected_session_id=selected,
        )
        if self._embedded:
            blocked = self._embedded_session_combo.blockSignals(True)
            try:
                self._embedded_session_combo.clear()
                self._embedded_session_combo.addItem("历史对话", "")
                selected_index = 0
                for summary in summaries:
                    status_label = session_row_presentation(
                        summary
                    ).status_label
                    status = (
                        f" · {status_label}"
                        if status_label
                        else ""
                    )
                    self._embedded_session_combo.addItem(
                        f"{'★ ' if summary.pinned else ''}{summary.title}{status}",
                        summary.session_id,
                    )
                    if summary.session_id == selected:
                        selected_index = self._embedded_session_combo.count() - 1
                self._embedded_session_combo.setCurrentIndex(selected_index)
                self._embedded_session_combo.setEnabled(bool(summaries))
            finally:
                self._embedded_session_combo.blockSignals(blocked)

    def _open_embedded_session(self, _index: int) -> None:
        session_id = str(self._embedded_session_combo.currentData() or "")
        if not session_id:
            return
        if (
            self._active_session is not None
            and self._active_session.session_id == session_id
        ):
            self._active_session = self._mark_session_read(
                self._active_session
            )
            self._refresh_session_list(select_session_id=session_id)
            return
        if not self._flush_active_draft():
            self._restore_embedded_session_selection()
            return
        corrupt_summary = next(
            (
                summary
                for summary in self._coordinator.list_sessions()
                if summary.session_id == session_id and summary.corrupt
            ),
            None,
        )
        if corrupt_summary is not None:
            self._restore_embedded_session_selection()
            self._show_corrupt_session_recovery(
                corrupt_summary.recovery_path
            )
            return
        try:
            loaded_session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError) as exc:
            self._restore_embedded_session_selection()
            self._show_session_navigation_error(
                "无法打开该对话",
                exc,
            )
            return
        self._active_session = self._mark_session_read(loaded_session)
        self._clear_session_navigation_error()
        self._refresh_session_list(select_session_id=session_id)
        self._provider_selection.select(self._active_session.provider_profile_id)
        self._render_active_session()
        self._load_draft_text(self._active_session.draft_text)
        self._sync_session_document_path()
        self._sync_composer_busy_state()

    def _restore_embedded_session_selection(self) -> None:
        session_id = (
            self._active_session.session_id
            if self._active_session is not None
            else ""
        )
        index = self._embedded_session_combo.findData(session_id)
        blocked = self._embedded_session_combo.blockSignals(True)
        try:
            self._embedded_session_combo.setCurrentIndex(max(0, index))
        finally:
            self._embedded_session_combo.blockSignals(blocked)

    def _filter_sessions(self, text: str) -> None:
        self._session_sidebar.filter_sessions(text)

    def _refresh_context(self) -> None:
        paths: list[str] = []
        if self._active_session is not None:
            for reference in self._active_session.context_refs:
                path = str(reference.get("path") or "").strip()
                if path:
                    paths.append(path)
        if not paths:
            document_text = "未选择"
        elif len(paths) == 1:
            document_text = Path(paths[0]).name
        else:
            document_text = f"{Path(paths[0]).name} 等 {len(paths)} 份材料"
        self._context_document.setText(document_text)
        self._context_document.setToolTip("\n".join(paths))
        mode = self.bridge.current_work_mode()
        self._context_mode.setText(str(getattr(mode, "label", "") or self.bridge.current_work_mode_id() or "未选择"))
        self._context_scene.setText(self.bridge.current_scene_id() or "未选择")
        self._context_template.setText(self.bridge.current_template_id() or "未选择")

    def _toggle_session_rail(self) -> None:
        if self._responsive_mode == "compact":
            self._open_compact_drawer("session")
            return
        self._session_rail_requested = not self._session_rail.isVisible()
        self._session_rail.setVisible(self._session_rail_requested)

    def _toggle_context_rail(self) -> None:
        if self._responsive_mode in {"compact", "medium"}:
            self._open_compact_drawer("context")
            return
        self._context_rail_requested = not self._context_rail.isVisible()
        self._context_rail.setVisible(self._context_rail_requested)

    def _open_compact_drawer(self, kind: str) -> None:
        if kind == "session":
            if self._session_drawer is None:
                self._session_drawer = Drawer(
                    title="对话",
                    width=min(300, max(240, self.width() - 48)),
                    side="left",
                    parent=self,
                )
            drawer = self._session_drawer
            rail = self._session_rail
        else:
            if self._context_drawer is None:
                self._context_drawer = Drawer(
                    title="当前上下文",
                    width=min(320, max(280, self.width() - 48)),
                    side="right",
                    parent=self,
                )
            drawer = self._context_drawer
            rail = self._context_rail
        if rail.window() is not drawer:
            drawer.set_body(rail)
        rail.setVisible(True)
        drawer.open()

    def _close_session_drawer_after_navigation(self) -> None:
        if self._session_drawer is not None and self._session_drawer.isVisible():
            self._session_drawer.close()

    def _restore_rails_to_layout(self) -> None:
        if self._session_drawer is not None and self._session_rail.window() is self._session_drawer:
            self._session_drawer.take_body()
            self._session_rail.setParent(self)
            self._root_layout.insertWidget(0, self._session_rail)
            self._session_drawer.hide()
        if self._context_drawer is not None and self._context_rail.window() is self._context_drawer:
            self._context_drawer.take_body()
            self._context_rail.setParent(self)
            self._root_layout.addWidget(self._context_rail)
            self._context_drawer.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_active_reading_widths()
        # QScrollArea updates its viewport after the parent resize event. Re-run
        # width projection on the next event-loop turn so cards never retain the
        # previous wide-layout width when entering compact mode.
        QTimer.singleShot(0, self._sync_active_reading_widths)
        QTimer.singleShot(0, self._position_jump_latest_button)
        width = event.size().width()
        if self._embedded:
            self._responsive_mode = "embedded"
            self._session_rail.hide()
            self._context_rail.hide()
            self._session_toggle.show()
            self._header_icon.hide()
            self._context_toggle.hide()
            self._conversation_title.hide()
            self._embedded_session_combo.setVisible(width >= 520)
            self._provider_combo.setVisible(width >= 420)
            self._composer._model_label.setVisible(width >= 420)
            return
        if self._first_level:
            compact = width < TOKENS.compact_breakpoint
            if compact:
                self._responsive_mode = "compact"
                self._session_rail.hide()
            else:
                self._restore_rails_to_layout()
                self._responsive_mode = "first_level"
                self._session_rail.setVisible(self._session_rail_requested)
            self._context_rail.hide()
            self._context_toggle.hide()
            self._header_widget.setVisible(
                compact or self._conversation_stack.currentWidget() is self._active_page
            )
            self._session_toggle.setVisible(compact)
            self._header_icon.setVisible(not compact)
            self._conversation_title.setVisible(not compact and width >= 620)
            self._provider_combo.setVisible(width >= 520)
            self._composer._model_label.setVisible(width >= 520)
            return
        if width < TOKENS.compact_breakpoint:
            mode = "compact"
            session_visible = False
            context_visible = False
        elif width < TOKENS.context_breakpoint:
            mode = "medium"
            session_visible = self._session_rail_requested
            context_visible = False
        else:
            mode = "wide"
            session_visible = self._session_rail_requested
            context_visible = self._context_rail_requested
        if mode != "compact":
            self._restore_rails_to_layout()
        self._responsive_mode = mode
        self._session_toggle.setVisible(mode == "compact")
        self._header_icon.setVisible(mode != "compact")
        self._conversation_title.setVisible(mode != "compact" or width >= 720)
        self._provider_combo.setVisible(mode != "compact" or width >= 540)
        self._composer._model_label.setVisible(mode != "compact" or width >= 540)
        self._session_rail.setVisible(session_visible)
        self._context_rail.setVisible(context_visible)

        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None and bench.isVisible():
            self._reposition_workbench()

    def minimumSizeHint(self) -> QSize:
        """Keep hidden rails from imposing a wide native-window minimum."""

        return QSize(420, 360)

    def prepare_close_pending_changes(self) -> bool:
        return self._flush_active_draft()

    def closeEvent(self, event) -> None:
        if not self._flush_active_draft():
            event.ignore()
            return
        # Closing routes through the single undo strategy: flush any pending
        # right-editor edit, then apply the CLOSE baseline (a non-destructive
        # keep/snapshot — never a history reset on exit).  This keeps close in
        # line with export/save/chapter-switch instead of being an unguarded
        # teardown.
        view = getattr(self, "_marktext_view", None)
        if view is not None:
            view.flush_now()
            from src.assistant.ui.undo_policy import UndoEvent, apply_to_view

            apply_to_view(view, UndoEvent.CLOSE)
        self._restore_rails_to_layout()
        for drawer in (self._session_drawer, self._context_drawer):
            if drawer is not None:
                drawer.close()
                drawer.deleteLater()
        self._session_drawer = None
        self._context_drawer = None
        bench = getattr(self, "_chapter_workbench", None)
        if bench is not None:
            bench.hide()
            bench.deleteLater()
            self._chapter_workbench = None
        super().closeEvent(event)

__all__ = ["AssistantPanel"]