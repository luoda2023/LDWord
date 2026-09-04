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
from src.assistant.runtime.providers.router import (
    ProviderRouter,
)
from src.assistant.runtime.turn_runner import (
    AssistantTurnRunner,
)
from src.assistant.storage.execution_journal import ExecutionJournalStore
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.card_action_mixin import AssistantCardActionMixin
from src.assistant.ui.conversation_presentation import (
    build_interaction_action_scope,
    interaction_is_active,
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


class AssistantPanel(
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
        layout.addWidget(self._message_scroll, 1)

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

        # Kept as a hidden compatibility target for older callers. Cancellation
        # now lives in the composer's circular send/stop control.
        self._stop_button = QPushButton("停止", composer_host)
        self._stop_button.setObjectName("assistant_stop")
        self._stop_button.hide()
        apply_button_variant(self._stop_button, "secondary")
        layout.addWidget(composer_host)
        return page

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
        follow_latest = not same_session or self._is_near_latest()
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
                    card_layout.setContentsMargins(20, 8, 20, 8)
                    card_layout.setSpacing(0)
                    card_layout.addStretch(1)
                    card = AssistantInteractionCard(
                        interaction_type=interaction_type,
                        title=card_title,
                        body=card_body,
                        payload=card_payload,
                        parent=card_host,
                    )
                    card.action_requested.connect(self._handle_card_action)
                    card.setMaximumWidth(TOKENS.assistant_message_max_width)
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

    def minimumSizeHint(self) -> QSize:
        """Keep hidden rails from imposing a wide native-window minimum."""

        return QSize(420, 360)

    def prepare_close_pending_changes(self) -> bool:
        return self._flush_active_draft()

    def closeEvent(self, event) -> None:
        if not self._flush_active_draft():
            event.ignore()
            return
        self._restore_rails_to_layout()
        for drawer in (self._session_drawer, self._context_drawer):
            if drawer is not None:
                drawer.close()
                drawer.deleteLater()
        self._session_drawer = None
        self._context_drawer = None
        super().closeEvent(event)

__all__ = ["AssistantPanel"]
