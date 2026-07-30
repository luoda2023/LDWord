"""Alavette Design-aligned AI document assistant panel."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.assistant.adapters.content_generation_adapter import (
    AssistantContentGenerationAdapter,
    generated_draft_source_ref,
    is_generated_draft,
)
from src.assistant.adapters.production_adapter import public_execution_result
from src.assistant.application.content_generation_service import (
    AssistantContentGenerationService,
    ContentGenerationRequest,
)
from src.assistant.application.document_job_controller import DocumentJobController
from src.assistant.application.generated_draft_binding import bind_generated_draft
from src.assistant.application.plan_presentation import present_document_plan
from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.application.session_recovery import AssistantSessionRecovery
from src.assistant.contracts.document_plan import DocumentPlan
from src.assistant.contracts.execution import PreflightReceipt
from src.assistant.contracts.material_snapshot import MaterialContextSnapshot
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.contracts.messages import (
    BLOCK_ARTIFACT,
    BLOCK_INTERACTION,
    BLOCK_TEXT,
    ROLE_ASSISTANT,
    ROLE_USER,
    AssistantMessage,
)
from src.assistant.contracts.runtime import (
    TURN_COMPLETED,
    TURN_WAITING_DATA_PERMISSION,
)
from src.assistant.runtime.cancellation import AssistantCancellationToken
from src.assistant.runtime.providers.router import ProviderResolutionError, ProviderRouter
from src.assistant.runtime.providers.profiles import default_mock_profile
from src.assistant.runtime.turn_runner import AssistantTurnRunner
from src.assistant.runtime.turn_runner import (
    attachment_fingerprints,
    history_fingerprint,
)
from src.assistant.storage.models import AssistantSession
from src.assistant.storage.execution_journal import ExecutionJournalStore
from src.assistant.ui.design_tokens import TOKENS
from src.assistant.ui.conversation_presentation import (
    interaction_is_active,
    project_output_references,
)
from src.assistant.ui.conversation_view import (
    AssistantConversationMessage,
    AssistantConversationSurface,
)
from src.assistant.ui.creative_home import AssistantCreativeHome, AssistantHeroComposer
from src.assistant.ui.card_action_mixin import AssistantCardActionMixin
from src.assistant.ui.interaction_card import AssistantInteractionCard
from src.assistant.ui.provider_presentation import (
    provider_connection_badge,
)
from src.assistant.ui.provider_selection import ProviderSelectionCoordinator
from src.assistant.ui.session_sidebar import AssistantSessionSidebar
from src.assistant.ui.panel_theme_mixin import AssistantPanelThemeMixin
from src.assistant.ui.turn_flow_mixin import AssistantTurnFlowMixin
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QLayout,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    QStackedWidget,
    QTimer,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.context_menu import ContextMenu
from src.shared.ui.drawer import Drawer
from src.shared.ui.theme import bind_theme
from src.config.material_context import MaterialExecutionContext
from src.ui.base_panel import BasePanel
from src.shared.ui.icons.catalog import get_icon


class AssistantPanel(
    AssistantCardActionMixin,
    AssistantTurnFlowMixin,
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
        self._turn_previews: dict[str, dict[str, str]] = {}
        self._turn_material_snapshots: dict[str, MaterialExecutionContext] = {}
        self._plan_material_snapshots: dict[str, MaterialExecutionContext] = {}
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
        super().__init__(bridge, parent)

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
        self._empty_input.set_submission_handler(
            lambda text: self._send_message(text, source=self._empty_input)
        )
        self._composer.set_submission_handler(
            lambda text: self._send_message(text, source=self._composer)
        )
        self._empty_input.text_changed.connect(self._save_active_draft)
        self._composer.text_changed.connect(self._save_active_draft)
        self._creative_home.provider_changed.connect(self._on_home_provider_selected)
        self._empty_input.document_path_changed.connect(
            self._on_composer_document_selected
        )
        self._composer.document_path_changed.connect(
            self._on_composer_document_selected
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
            "material_context_changed",
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
        self._new_session_button = sidebar._new_button
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
            lambda _minimum, _maximum: self._sync_jump_to_latest(
                self._message_scroll.verticalScrollBar().value()
            )
        )
        layout.addWidget(self._message_scroll, 1)

        self._jump_latest_button = QToolButton(page)
        self._jump_latest_button.setObjectName("assistant_jump_latest")
        self._jump_latest_button.setText("回到最新消息")
        self._jump_latest_button.setIcon(get_icon("chevron-down", 14))
        self._jump_latest_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._jump_latest_button.setCursor(Qt.PointingHandCursor)
        self._jump_latest_button.hide()
        jump_row = QHBoxLayout()
        jump_row.setContentsMargins(0, 0, 0, 4)
        jump_row.addStretch(1)
        jump_row.addWidget(self._jump_latest_button)
        jump_row.addStretch(1)
        layout.addLayout(jump_row)

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
        profile_id, model_id = self._provider_selection.selected_identity()
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
            )
        self._active_session = session
        self._refresh_session_list(select_session_id=session.session_id)
        self._render_active_session()
        self._load_draft_text("")
        self._sync_session_document_path()
        self._sync_composer_busy_state()
        self._empty_input.focus_input()

    def _open_session_item(self, item: QListWidgetItem) -> None:
        session_id = str(item.data(Qt.UserRole) or "")
        self._open_session_by_id(session_id)

    def _open_session_by_id(self, session_id: str) -> None:
        if not str(session_id or ""):
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
            self._active_session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            return
        self._session_sidebar.select_session(session_id)
        self._provider_selection.select(self._active_session.provider_profile_id)
        self._render_active_session()
        self._load_draft_text(self._active_session.draft_text)
        self._sync_session_document_path()
        self._sync_composer_busy_state()

    def _show_corrupt_session_recovery(self, recovery_path: str) -> None:
        path = Path(str(recovery_path or "")).expanduser()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("会话文件需要恢复")
        box.setText("该会话文件无法解析，应用没有删除或覆盖原文件。")
        box.setInformativeText(
            f"原文件：{path}\n"
            "可以打开所在文件夹，备份或交给维护人员修复。"
        )
        open_button = box.addButton(
            "打开所在文件夹",
            QMessageBox.ButtonRole.ActionRole,
        )
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(path.parent.resolve(strict=False)))
            )

    def _save_active_draft(self, text: str) -> None:
        if self._loading_draft or self._active_session is None:
            return
        try:
            self._active_session = self._coordinator.update_draft(
                self._active_session,
                text,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            reason = (
                "草稿暂未保存到本地；输入内容仍保留在当前窗口。"
                f"错误类型：{type(exc).__name__}"
            )
            self._composer.set_submission_error(reason)
            self._empty_input.set_submission_error(reason)
            return
        self._composer.set_submission_error("")
        self._empty_input.set_submission_error("")
        source = self.sender()
        peer = self._composer if source is self._empty_input else self._empty_input
        if peer.get_text() != text:
            self._loading_draft = True
            try:
                peer.set_text(text)
            finally:
                self._loading_draft = False

    def _load_draft_text(self, text: str) -> None:
        self._loading_draft = True
        try:
            self._empty_input.set_text(text)
            self._composer.set_text(text)
        finally:
            self._loading_draft = False

    def _on_composer_document_selected(self, path: str) -> None:
        """Own assistant attachments by session instead of the global bridge."""

        self._composer.set_submission_gate("")
        self._empty_input.set_submission_gate("")
        if self._active_session is None:
            profile_id, model_id = self._provider_selection.selected_identity()
            self._active_session = self._coordinator.create_session(
                provider_profile_id=profile_id,
                model_id=model_id,
            )
        refs = self._context_refs_for_path(path)
        self._active_session = self._coordinator.update_state(
            self._active_session,
            context_refs=refs,
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
        self._empty_input.set_document_path(normalized)
        self._composer.set_document_path(normalized)
        self._creative_home._sync_action_availability()
        if session is not None:
            self._active_session = self._coordinator.update_state(
                session,
                context_refs=self._context_refs_for_path(normalized),
            )
        self._refresh_context()

    def _sync_session_document_path(self) -> None:
        path = ""
        if self._active_session is not None:
            for reference in self._active_session.context_refs:
                path = str(
                    reference.get("path")
                    or reference.get("file_path")
                    or reference.get("local_path")
                    or ""
                ).strip()
                if path:
                    break
        self._empty_input.set_document_path(path)
        self._composer.set_document_path(path)
        self._creative_home._sync_action_availability()

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
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            return
        menu = ContextMenu(parent=self)
        menu.add_action(
            "取消固定" if session.pinned else "固定对话",
            callback=lambda: self._set_session_pinned(session_id, not session.pinned),
        )
        menu.add_action("重命名", callback=lambda: self._prompt_rename_session(session_id))
        menu.add_separator()
        menu.add_action("删除", callback=lambda: self._confirm_delete_session(session_id))
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
            return
        title, accepted = QInputDialog.getText(
            self,
            "重命名对话",
            "对话名称：",
            QLineEdit.Normal,
            session.title,
        )
        if accepted:
            self._rename_session(session_id, title)

    def _rename_session(self, session_id: str, title: str) -> bool:
        normalized = str(title or "").strip()
        if not normalized:
            return False
        try:
            session = self._coordinator.load_session(session_id)
            updated = self._coordinator.rename(session, normalized)
        except (OSError, ValueError, TypeError):
            return False
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = updated
            self._conversation_title.setText(updated.title)
        self._refresh_session_list(select_session_id=session_id)
        return True

    def _set_session_pinned(self, session_id: str, pinned: bool) -> bool:
        try:
            session = self._coordinator.load_session(session_id)
            updated = self._coordinator.set_pinned(session, pinned)
        except (OSError, ValueError, TypeError):
            return False
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = updated
        self._refresh_session_list(select_session_id=session_id)
        return True

    def _confirm_delete_session(self, session_id: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            return
        job_status = str(session.document_job.get("status") or "")
        if session.turn_status == "provider_running" or job_status in {
            "content_generation_running",
            "preflight_running",
            "execution_running",
        }:
            QMessageBox.information(
                self,
                "任务仍在运行",
                "请先停止当前任务，再删除该对话。文档产物不会随对话删除。",
            )
            return
        answer = QMessageBox.question(
            self,
            "删除对话",
            f"确定删除“{session.title}”吗？已生成的文档不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._delete_session(session_id)

    def _delete_session(self, session_id: str) -> bool:
        if session_id in self._turn_workers:
            return False
        if not self._coordinator.delete_session(session_id):
            return False
        was_active = (
            self._active_session is not None
            and self._active_session.session_id == session_id
        )
        if was_active:
            summaries = self._coordinator.list_sessions()
            if summaries:
                try:
                    self._active_session = self._coordinator.load_session(
                        summaries[0].session_id
                    )
                except (OSError, ValueError, TypeError):
                    self._active_session = None
            else:
                self._active_session = None
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
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._turn_preview_widget = None
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
                    card_payload["active"] = interaction_is_active(
                        interaction_type=interaction_type,
                        payload=card_payload,
                        pending_continuation=session.pending_continuation,
                        active_plan=session.active_plan,
                        document_job=session.document_job,
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
                        title=str(block.data.get("title") or "需要确认"),
                        body=block.text,
                        payload=card_payload,
                        parent=card_host,
                    )
                    card.action_requested.connect(self._handle_card_action)
                    card.setMaximumWidth(TOKENS.assistant_message_max_width)
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
            QTimer.singleShot(0, self._scroll_to_bottom)
        else:
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
            QMessageBox.warning(self, "来源不可用", f"找不到本地来源：\n{target}")
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
            QMessageBox.warning(self, "链接不可用", "仅支持 http、https、mailto 和 file 链接。")
            return
        title = str(reference.get("title") or reference.get("name") or "来源详情")
        snippet = str(
            reference.get("snippet")
            or reference.get("excerpt")
            or reference.get("text")
            or "该来源没有可打开的目标。"
        )
        QMessageBox.information(self, title, snippet)

    def _plan_message(self, plan: DocumentPlan) -> AssistantMessage:
        presentation = present_document_plan(plan)
        return AssistantMessage.interaction(
            role=ROLE_ASSISTANT,
            interaction_type="plan",
            title=presentation.title,
            body=presentation.body,
            payload={
                "plan_id": plan.plan_id,
                "revision": plan.revision,
                "actions": list(presentation.actions),
                "facts": [
                    {"label": label, "value": value}
                    for label, value in presentation.facts
                ],
                "notices": list(presentation.notices),
            },
        )

    def _open_provider_settings(self) -> None:
        navigate = getattr(self.bridge, "navigate_to_preferences", None)
        if callable(navigate):
            navigate("ai")

    def _provider_disclosure_facts(
        self,
        session: AssistantSession,
    ) -> list[dict[str, str]]:
        profile_label = session.provider_profile_id or "当前所选服务"
        profile_model_id = ""
        try:
            profile = self._provider_router.profiles.get(
                session.provider_profile_id
            )
        except (KeyError, OSError, TypeError, ValueError):
            pass
        else:
            profile_label = profile.label
            profile_model_id = profile.model_id
        return [
            {"label": "服务", "value": profile_label},
            {
                "label": "模型",
                "value": (
                    session.model_id
                    or profile_model_id
                    or "当前所选模型"
                ),
            },
        ]

    def _queue_content_generation_disclosure(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        context_documents: tuple[dict[str, object], ...],
    ) -> None:
        disclosure_id = uuid4().hex
        continuation = {
            "kind": "local_content_disclosure",
            "disclosure_id": disclosure_id,
            "plan_id": plan.plan_id,
            "plan_revision": plan.revision,
            "context_refs": [dict(item) for item in context_documents],
        }
        job = {
            **dict(session.document_job),
            "status": "needs_data_disclosure",
            "disclosure_id": disclosure_id,
            "disclosure_purpose": "content_generation",
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation=continuation,
            document_job=job,
            turn_status=TURN_WAITING_DATA_PERMISSION,
        )
        names = "、".join(
            str(item.get("name") or item.get("title") or "DOCX 材料")
            for item in context_documents
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="disclosure",
                title="确认用于内容生成的材料",
                body=(
                    "确认后，材料正文仅用于本次内容生成；本地路径、资料包结构化字段、"
                    "Logo 和公章不会发送给模型。"
                ),
                payload={
                    "disclosure_id": disclosure_id,
                    "facts": [
                        {"label": "材料", "value": names or "DOCX 材料"},
                        {"label": "发送内容", "value": "附件正文"},
                        {"label": "用途", "value": "生成并校验文档内容"},
                        *self._provider_disclosure_facts(session),
                    ],
                    "actions": [
                        {
                            "id": "approve_content_disclosure",
                            "label": "同意并生成",
                            "variant": "primary",
                        },
                        {
                            "id": "deny_content_disclosure",
                            "label": "不发送",
                            "variant": "secondary",
                        },
                    ],
                },
            ),
            turn_status=TURN_WAITING_DATA_PERMISSION,
        )
        self._active_session = session
        self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)

    def _resolve_content_disclosure(
        self,
        payload: Mapping[str, object],
        *,
        approved: bool,
    ) -> None:
        session = self._active_session
        if session is None:
            return
        continuation = dict(session.pending_continuation)
        if continuation.get("kind") != "local_content_disclosure":
            return
        expected_id = str(continuation.get("disclosure_id") or "")
        submitted_id = str(payload.get("disclosure_id") or "")
        if not expected_id or submitted_id != expected_id:
            return
        try:
            plan = DocumentPlan.from_dict(session.active_plan)
        except (TypeError, ValueError):
            return
        if (
            plan.plan_id != str(continuation.get("plan_id") or "")
            or plan.revision != int(continuation.get("plan_revision") or 0)
        ):
            return
        job = {
            **dict(session.document_job),
            "status": "plan_ready" if not approved else "content_generation_ready",
            "disclosure_decision": "approved" if approved else "denied",
        }
        session = self._coordinator.update_state(
            session,
            pending_continuation={},
            document_job=job,
            turn_status=TURN_COMPLETED if not approved else "local_processing",
        )
        self._active_session = session
        if not approved:
            session = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="boundary",
                    title="已取消材料发送",
                    body="未向模型发送材料正文；当前计划仍保留，可调整后重新发起。",
                    payload={"actions": []},
                ),
                turn_status=TURN_COMPLETED,
            )
            self._active_session = session
            self._render_active_session()
            self._refresh_session_list(select_session_id=session.session_id)
            return
        self._start_content_generation(
            session,
            plan,
            approved_disclosure=True,
        )

    def _start_content_generation(
        self,
        session: AssistantSession,
        plan: DocumentPlan,
        *,
        approved_disclosure: bool = False,
    ) -> None:
        if self._content_worker is not None and self._content_worker.is_running:
            return
        if not plan.generation_required or plan.blocking_issues:
            return
        context_documents = tuple(dict(item) for item in plan.material_refs)
        if context_documents and not approved_disclosure:
            self._queue_content_generation_disclosure(
                session,
                plan,
                context_documents,
            )
            return
        try:
            gateway = (
                self._fixed_turn_runner.gateway
                if self._fixed_turn_runner is not None
                else self._provider_router.resolve(session.provider_profile_id)
            )
        except ProviderResolutionError as exc:
            self._append_content_generation_failure(session.session_id, str(exc))
            return
        context_ref_ids = tuple(
            str(item.get("path") or item.get("artifact_id") or item.get("name") or "")
            for item in context_documents
            if str(item.get("path") or item.get("artifact_id") or item.get("name") or "")
        )
        context_fingerprints = attachment_fingerprints(context_documents)
        disclosure_grant = (
            DisclosureGrant(
                grant_id=uuid4().hex,
                session_id=session.session_id,
                provider_id=session.provider_profile_id,
                model_id=session.model_id,
                allowed_refs=context_ref_ids,
                allowed_fields=("document_text",),
                created_at=datetime.now(timezone.utc).isoformat(),
                scope="once",
                content_fingerprints=context_fingerprints,
            )
            if context_documents
            else None
        )
        request = ContentGenerationRequest(
            session_id=session.session_id,
            turn_id=plan.created_by_turn_id,
            prompt=plan.intent,
            provider_id=session.provider_profile_id,
            model_id=session.model_id,
            context_documents=context_documents,
            context_refs=context_ref_ids,
            context_fields=(("document_text",) if context_documents else ()),
            context_fingerprints=tuple(context_fingerprints.items()),
            disclosure_grant=disclosure_grant,
            capability_id=plan.capability_ref.capability_id,
            artifact_kind=plan.generation_contract.artifact_kind,
            prompt_profile_id=plan.generation_contract.prompt_profile_id,
        )
        adapter = AssistantContentGenerationAdapter(self._coordinator.store.root)
        service = AssistantContentGenerationService(adapter)
        worker = ContentGenerationWorker(service, request, gateway, parent=self)
        self._content_worker = worker
        job = {
            **dict(session.document_job),
            "status": "content_generation_running",
            "content_generation_turn_id": plan.created_by_turn_id,
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="progress",
                title="正在起草文档内容",
                body=(
                    (
                        "已按你的确认把材料正文提供给当前模型。"
                        if context_documents
                        else ""
                    )
                    + "模型只负责生成能力契约要求的 Markdown；完成后将由 Form 的"
                    "领域校验器确认结构，再绑定到对应生产链路。"
                ),
                payload={"actions": [], "ephemeral": True},
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session.session_id:
            self._active_session = session
            self._render_active_session()
        self._composer.set_busy(True)
        worker.finished.connect(self._on_content_generation_finished)
        worker.failed.connect(
            lambda error, session_id=session.session_id: self._append_content_generation_failure(
                session_id,
                error,
            )
        )
        worker.start()
        self._sync_composer_busy_state()

    def _on_content_generation_finished(self, draft: object) -> None:
        worker = self._content_worker
        if worker is None or not is_generated_draft(draft):
            return
        origin_session_id = worker.request.session_id
        try:
            session = self._coordinator.load_session(origin_session_id)
            plan = DocumentPlan.from_dict(session.active_plan)
        except (OSError, ValueError, TypeError):
            self._finish_content_generation_ui()
            return
        try:
            updated_plan = bind_generated_draft(plan, draft)
        except ValueError as exc:
            self._append_content_generation_failure(origin_session_id, str(exc))
            return
        source_ref = generated_draft_source_ref(draft)
        preview_path = str(draft.preview_path)
        production_input_path = str(draft.production_input_path)
        job = {
            **dict(session.document_job),
            "status": "content_draft_ready",
            "plan_id": updated_plan.plan_id,
            "plan_revision": updated_plan.revision,
            "generated_content_draft_id": draft.draft_id,
            "generated_content_markdown_path": draft.markdown_path,
            "generated_content_document_path": preview_path,
            "generated_content_preview_path": preview_path,
            "generated_content_production_input_path": production_input_path,
            "generated_content_artifact_kind": draft.artifact_kind,
            "generated_content_schema_id": source_ref.schema_id,
        }
        session = self._coordinator.update_state(
            session,
            active_plan=updated_plan.to_dict(),
            document_job=job,
            turn_status=TURN_COMPLETED,
        )
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="artifact",
                title="内容草稿已生成",
                body=(
                    "内容已通过当前能力对应的本地结构校验，并绑定到唯一生产入口。"
                    "你可以先打开草稿审阅，再进行生产执行前检查。"
                ),
                payload={
                    "draft_id": draft.draft_id,
                    "artifact_kind": draft.artifact_kind,
                    "schema_id": source_ref.schema_id,
                    "reference": {
                        "type": "file",
                        "title": Path(preview_path).name,
                        "path": preview_path,
                    },
                    "actions": [
                        {"id": "runtime_open_reference", "label": "打开内容草稿"},
                        {"id": "generate_content_draft", "label": "重新生成"},
                        {"id": "preflight", "label": "在本地检查并继续"},
                    ],
                },
            ),
        )
        if self._active_session is not None and self._active_session.session_id == origin_session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list(select_session_id=origin_session_id)
        self._finish_content_generation_ui()

    def _append_content_generation_failure(self, session_id: str, error: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            self._finish_content_generation_ui()
            return
        cancelled = "cancel" in str(error or "").casefold()
        job = {
            **dict(session.document_job),
            "status": "cancelled" if cancelled else "failed",
            "error_text": str(error or "content_generation_failed"),
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="内容起草已取消" if cancelled else "内容草稿未生成",
                body=(
                    "没有创建或覆盖正式输出文件。可以检查模型配置后重试。"
                    f"\n原因：{error}"
                ),
                payload={
                    "actions": [
                        {"id": "generate_content_draft", "label": "重新生成内容草稿"}
                    ]
                },
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list(select_session_id=session_id)
        self._finish_content_generation_ui()

    def _finish_content_generation_ui(self) -> None:
        worker = self._content_worker
        if worker is not None:
            worker.deleteLater()
        self._content_worker = None
        self._sync_composer_busy_state()
        if self._execution_worker is None or not self._execution_worker.is_running:
            self._stop_button.setVisible(False)

    @staticmethod
    def _material_context_for_plan(
        session: AssistantSession,
        plan: DocumentPlan,
    ) -> MaterialExecutionContext:
        raw = session.document_job.get("material_snapshot")
        if not isinstance(raw, Mapping):
            raise ValueError("assistant_material_snapshot_missing")
        snapshot = MaterialContextSnapshot.from_dict(raw)
        expected = str(plan.material_snapshot_ref.get("digest") or "")
        if not expected or expected != snapshot.digest:
            raise ValueError("assistant_material_snapshot_plan_mismatch")
        return snapshot.restore()

    def _run_preflight(self, session: AssistantSession, plan: DocumentPlan) -> None:
        if self._preflight_worker is not None and self._preflight_worker.is_running:
            return
        try:
            material_context = self._material_context_for_plan(session, plan)
        except (TypeError, ValueError):
            self._on_preflight_failed(
                session.session_id,
                "assistant_material_snapshot_unavailable",
            )
            return
        job = {
            **dict(session.document_job),
            "status": "preflight_running",
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="progress",
                title="正在进行本地执行前检查",
                body="正在校验输入文件、方案、模板和输出目录的完整性；不会上传正文。",
                payload={"actions": [], "ephemeral": True},
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session.session_id:
            self._active_session = session
            self._render_active_session()
        worker = PreflightWorker(
            self._document_jobs,
            session_id=session.session_id,
            plan=plan,
            material_context=material_context,
            parent=self,
        )
        self._preflight_worker = worker
        self._composer.set_busy(True)
        worker.finished.connect(self._on_preflight_finished)
        worker.failed.connect(
            lambda error, session_id=session.session_id: self._on_preflight_failed(
                session_id,
                error,
            )
        )
        worker.start()
        self._sync_composer_busy_state()

    def _on_preflight_finished(self, preflight: object) -> None:
        worker = self._preflight_worker
        if worker is None or not isinstance(preflight, PreflightReceipt):
            return
        try:
            session = self._coordinator.load_session(worker.session_id)
            current_plan = DocumentPlan.from_dict(session.active_plan)
        except (OSError, ValueError, TypeError):
            self._finish_preflight_ui()
            return
        if current_plan.fingerprint != preflight.plan_fingerprint:
            self._on_preflight_failed(worker.session_id, "assistant_preflight_became_stale")
            return
        job = {
            **dict(session.document_job),
            "status": "needs_execution_approval" if preflight.ready else "preflight_failed",
            "preflight": preflight.to_dict(),
        }
        session = self._coordinator.update_state(session, document_job=job)
        if preflight.ready:
            plan_presentation = present_document_plan(current_plan)
            approval_labels = {
                "任务",
                "操作",
                "输入",
                "方案",
                "模板",
                "资料",
                "交付",
                "输出",
                "数据范围",
            }
            approval_facts = [
                {"label": label, "value": value}
                for label, value in plan_presentation.facts
                if label in approval_labels
            ]
            approval_facts.append(
                {
                    "label": "原文件",
                    "value": (
                        "允许覆盖（已要求再次确认）"
                        if current_plan.output_policy.overwrite
                        else "保留，不覆盖"
                    ),
                }
            )
            body = (
                "请确认本次实际生产范围。输入、方案、模板、资料和输出位置已由本地预检绑定；"
                "确认后才会创建交付文件。"
            )
            actions = [{"id": "approve_execute", "label": "确认并生成文档"}]
            interaction_type = "approval"
            title = "执行前检查已通过"
        else:
            body = "\n".join(f"• {item}" for item in preflight.issues)
            actions = [{"id": "open_workbench", "label": "返回工作台处理"}]
            approval_facts = [
                {"label": "输出目录", "value": Path(preflight.output_root).name}
            ]
            interaction_type = "preflight"
            title = "执行前检查未通过"
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type=interaction_type,
                title=title,
                body=body,
                payload={
                    "preflight_id": preflight.preflight_id,
                    "facts": approval_facts,
                    "evidence": {
                        "input_hash": preflight.input_hash,
                        "material_context_digest": (
                            preflight.material_context_digest
                        ),
                        "plan_fingerprint": preflight.plan_fingerprint,
                        "resource_fingerprints": dict(
                            preflight.resource_fingerprints
                        ),
                    },
                    "notices": list(preflight.warnings),
                    "actions": actions,
                },
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session.session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list(select_session_id=session.session_id)
        self._finish_preflight_ui()

    def _on_preflight_failed(self, session_id: str, error: str) -> None:
        try:
            session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            self._finish_preflight_ui()
            return
        cancelled = "cancel" in str(error or "").casefold()
        job = {
            **dict(session.document_job),
            "status": "cancelled" if cancelled else "preflight_failed",
            "error_text": str(error or "assistant_preflight_failed"),
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="recovery",
                title="本地检查已取消" if cancelled else "本地检查未完成",
                body=f"未执行文档生产，也未覆盖任何文件。\n原因：{error}",
                payload={
                    "actions": [
                        {"id": "retry_preflight", "label": "重新检查"},
                        {"id": "open_workbench", "label": "返回工作台"},
                    ]
                },
            ),
        )
        if self._active_session is not None and self._active_session.session_id == session_id:
            self._active_session = session
            self._render_active_session()
        self._refresh_session_list(select_session_id=session_id)
        self._finish_preflight_ui()

    def _finish_preflight_ui(self) -> None:
        worker = self._preflight_worker
        if worker is not None:
            worker.deleteLater()
        self._preflight_worker = None
        self._sync_composer_busy_state()
        if (
            (self._content_worker is None or not self._content_worker.is_running)
            and (self._execution_worker is None or not self._execution_worker.is_running)
        ):
            self._stop_button.setVisible(False)

    def _start_execution(self, session: AssistantSession, plan: DocumentPlan) -> None:
        raw_preflight = session.document_job.get("preflight")
        if not isinstance(raw_preflight, dict):
            return
        try:
            preflight = PreflightReceipt.from_dict(raw_preflight)
            approval = self._document_jobs.approve(
                session_id=session.session_id,
                plan=plan,
                preflight=preflight,
            )
        except (ValueError, TypeError):
            return
        execution_id = uuid4().hex
        try:
            material_context = self._material_context_for_plan(session, plan)
        except (TypeError, ValueError):
            self._on_preflight_failed(
                session.session_id,
                "assistant_material_snapshot_unavailable",
            )
            return
        job = {
            **dict(session.document_job),
            "status": "execution_running",
            "execution_id": execution_id,
            "approval": approval.to_dict(),
        }
        session = self._coordinator.update_state(session, document_job=job)
        session = self._coordinator.append_message(
            session,
            AssistantMessage.interaction(
                role=ROLE_ASSISTANT,
                interaction_type="progress",
                title="正在生成文档",
                body="任务已交给 Form 本地生产引擎。可以切换对话，任务仍归属于当前会话。",
                payload={
                    "execution_id": execution_id,
                    "actions": [],
                    "ephemeral": True,
                },
            ),
        )
        self._active_session = session
        self._render_active_session()
        worker = DocumentExecutionWorker(
            self._document_jobs,
            session_id=session.session_id,
            plan=plan,
            preflight=preflight,
            approval=approval,
            material_context=material_context,
            execution_id=execution_id,
            parent=self,
        )
        self._execution_worker = worker
        worker.progress.connect(self._on_execution_progress)
        worker.finished.connect(self._on_execution_finished)
        self._composer.set_busy(True)
        worker.start()
        self._sync_composer_busy_state()

    def _on_execution_progress(self, current: int, total: int, message: str) -> None:
        worker = self._execution_worker
        if (
            worker is None
            or self._active_session is None
            or self._active_session.session_id != worker.session_id
        ):
            return
        text = str(message or "正在生成文档")
        if total > 0:
            text = f"{text}（{current}/{total}）"
        self._conversation_title.setText(text)

    def _on_execution_finished(self, result: object) -> None:
        worker = self._execution_worker
        if worker is None or not isinstance(result, dict):
            return
        origin_session_id = worker.session_id
        try:
            session = self._coordinator.load_session(origin_session_id)
        except (OSError, ValueError, TypeError):
            session = None
        if session is not None:
            status = str(result.get("status") or "failed")
            public = public_execution_result(result)
            primary_path = str(result.get("output_path") or "")
            output_references = project_output_references(result)
            if not primary_path and output_references:
                primary_path = str(output_references[0].get("path") or "")
            job = {
                **dict(session.document_job),
                "status": status,
                "result": dict(result),
                "primary_output_path": primary_path,
            }
            session = self._coordinator.update_state(session, document_job=job)
            successful = status in {"success", "partial_success"}
            if status == "success":
                body = "全部产物已通过交付完整性检查，可直接打开审阅。"
            elif status == "partial_success":
                body = "部分产物已生成；缺失项没有被静默忽略，请处理后重试。"
            else:
                body = "没有形成可确认的完整交付结果。"
            if public.get("error_text"):
                body += f"\n原因：{public['error_text']}"
            actions = []
            if successful and primary_path:
                actions.append({"id": "runtime_open_reference", "label": "打开文档"})
            if status in {"partial_success", "failed", "cancelled"}:
                actions.append({"id": "retry_preflight", "label": "重新检查后重试"})
            session = self._coordinator.append_message(
                session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="artifact" if successful else "recovery",
                    title="文档已生成" if status == "success" else ("部分文档已生成" if status == "partial_success" else "文档生成未完成"),
                    body=body,
                    payload={
                        "execution_id": worker.execution_id,
                        "actions": actions,
                        "reference": {
                            "type": "file",
                            "title": Path(primary_path).name if primary_path else "",
                            "path": primary_path,
                        },
                        "references": list(output_references),
                    },
                ),
            )
            if self._active_session is not None and self._active_session.session_id == origin_session_id:
                self._active_session = session
                self._render_active_session()
        worker.deleteLater()
        self._execution_worker = None
        self._sync_composer_busy_state()
        if (
            (self._turn_worker is None or not self._turn_worker.is_running)
            and (self._content_worker is None or not self._content_worker.is_running)
            and (self._preflight_worker is None or not self._preflight_worker.is_running)
        ):
            self._stop_button.setVisible(False)
        self._refresh_session_list(select_session_id=origin_session_id)

    def _runner_for_session(self, session: AssistantSession) -> AssistantTurnRunner:
        if self._fixed_turn_runner is not None:
            return self._fixed_turn_runner
        return AssistantTurnRunner(self._provider_router.resolve(session.provider_profile_id))

    def _refresh_provider_profiles(self) -> None:
        if self._active_session is not None:
            self._active_session = self._provider_selection.synchronize_session(
                self._active_session
            )
        selected = (
            self._active_session.provider_profile_id
            if self._active_session is not None
            else (
                self._creative_home.composer.selected_provider_id()
                or str(self._provider_combo.currentData() or "")
                or "mock-default"
            )
        )
        projected_profiles: list[tuple[str, str, str, bool, str, str]] = []
        try:
            profiles = self._provider_router.profiles.list_profiles()
        except (OSError, RuntimeError, TypeError, ValueError):
            profiles = (default_mock_profile(),)
        for profile in profiles:
            readiness = self._provider_router.readiness(profile.profile_id)
            status = provider_connection_badge(profile, ready=readiness.ready)
            projected_profiles.append(
                (
                    profile.label,
                    profile.profile_id,
                    profile.model_id,
                    readiness.ready,
                    readiness.message,
                    status,
                )
            )
        self._composer.set_provider_profiles(
            projected_profiles,
            selected_id=selected,
        )
        self._creative_home.composer.set_provider_profiles(
            projected_profiles,
            selected_id=selected,
        )
        self._provider_selection.select(selected)

    def _on_provider_selected(self, _index: int) -> None:
        profile_id = str(self._provider_combo.currentData() or "")
        if profile_id:
            self._creative_home.composer.select_provider(profile_id)
        if self._active_session is None:
            return
        profile_id, model_id = self._provider_selection.selected_identity()
        previous_profile_id = self._active_session.provider_profile_id
        if profile_id == previous_profile_id:
            self._active_session = self._coordinator.update_state(
                self._active_session,
                model_id=model_id,
            )
            return
        previous_domain = self._provider_data_domain(previous_profile_id)
        target_domain = self._provider_data_domain(profile_id)
        visible_history = tuple(
            message
            for message in self._active_session.messages
            if message.visible_text()
        )
        history_grant: dict[str, object] = {}
        if visible_history and previous_domain != target_domain:
            decision = self._confirm_provider_history_transition(
                previous_profile_id,
                profile_id,
                message_count=len(visible_history),
                character_count=sum(
                    len(message.visible_text())
                    for message in visible_history
                ),
            )
            if decision == "cancel":
                self._provider_selection.select(previous_profile_id)
                return
            if decision == "new":
                self.new_session()
                return
            history_grant = {
                "schema_version": "assistant-provider-history-grant-v1",
                "grant_id": uuid4().hex,
                "session_id": self._active_session.session_id,
                "source_profile_id": previous_profile_id,
                "source_domain": previous_domain,
                "target_profile_id": profile_id,
                "target_domain": target_domain,
                "history_message_count": len(visible_history),
                "history_character_count": sum(
                    len(message.visible_text())
                    for message in visible_history
                ),
                "history_fingerprint": history_fingerprint(
                    self._active_session.messages
                ),
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        self._active_session = self._coordinator.update_state(
            self._active_session,
            provider_profile_id=profile_id,
            model_id=model_id,
            provider_history_grant=history_grant,
        )
        if history_grant:
            self._active_session = self._coordinator.append_message(
                self._active_session,
                AssistantMessage.interaction(
                    role=ROLE_ASSISTANT,
                    interaction_type="disclosure",
                    title="已确认携带历史并切换模型服务",
                    body=(
                        f"已按你的确认，把当前会话的 "
                        f"{history_grant['history_message_count']} 条可见消息"
                        f"授权给 {profile_id}。附件仍需按每次请求单独确认。"
                    ),
                    payload={
                        "active": False,
                        "facts": [
                            {
                                "label": "来源服务",
                                "value": previous_profile_id,
                            },
                            {
                                "label": "目标服务",
                                "value": profile_id,
                            },
                            {
                                "label": "历史字符",
                                "value": str(
                                    history_grant[
                                        "history_character_count"
                                    ]
                                ),
                            },
                        ],
                        "actions": [],
                    },
                ),
            )
            self._render_active_session()
            self._refresh_session_list(
                select_session_id=self._active_session.session_id
            )

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
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("确认历史对话的数据范围")
        box.setText(
            f"你正在从 {source_profile_id} 切换到 {target_profile_id}。"
        )
        box.setInformativeText(
            f"当前会话包含 {message_count} 条、约 {character_count} 个字符。"
            "请选择是否把这些历史发送给新的模型服务。"
        )
        carry_button = box.addButton(
            "携带历史并切换",
            QMessageBox.ButtonRole.AcceptRole,
        )
        new_button = box.addButton(
            "新建空白对话",
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_button = box.addButton(
            QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is carry_button:
            return "carry"
        if clicked is new_button:
            return "new"
        return "cancel"

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

    def _scroll_to_bottom(self) -> None:
        bar = self._message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self._jump_latest_button.hide()

    def _restore_scroll_value(self, value: int) -> None:
        bar = self._message_scroll.verticalScrollBar()
        bar.setValue(min(max(0, int(value)), bar.maximum()))
        self._sync_jump_to_latest(bar.value())

    def _is_near_latest(self) -> bool:
        bar = self._message_scroll.verticalScrollBar()
        return bar.maximum() - bar.value() <= 64

    def _sync_jump_to_latest(self, _value: int) -> None:
        if self._conversation_stack.currentWidget() is not self._active_page:
            self._jump_latest_button.hide()
            return
        self._jump_latest_button.setVisible(not self._is_near_latest())

    def _sync_active_reading_widths(self) -> None:
        page_width = max(0, self._active_page.width())
        if page_width > 48:
            self._composer.setFixedWidth(page_width - 48)
        viewport_width = max(0, self._message_scroll.viewport().width())
        card_width = min(
            TOKENS.assistant_message_max_width,
            max(260, viewport_width - 96),
        )
        for card in self._message_host.findChildren(AssistantInteractionCard):
            card.setFixedWidth(card_width)

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
                    status = " · 运行中" if summary.turn_status == "provider_running" else ""
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
        try:
            self._active_session = self._coordinator.load_session(session_id)
        except (OSError, ValueError, TypeError):
            return
        self._provider_selection.select(self._active_session.provider_profile_id)
        self._render_active_session()
        self._load_draft_text(self._active_session.draft_text)
        self._sync_session_document_path()
        self._sync_composer_busy_state()

    def _filter_sessions(self, text: str) -> None:
        self._session_sidebar.filter_sessions(text)

    def _refresh_context(self) -> None:
        path = ""
        if self._active_session is not None:
            for reference in self._active_session.context_refs:
                path = str(reference.get("path") or "").strip()
                if path:
                    break
        self._context_document.setText(Path(path).name if path else "未选择")
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

    def closeEvent(self, event) -> None:
        self._restore_rails_to_layout()
        for drawer in (self._session_drawer, self._context_drawer):
            if drawer is not None:
                drawer.close()
                drawer.deleteLater()
        self._session_drawer = None
        self._context_drawer = None
        super().closeEvent(event)

__all__ = ["AssistantPanel"]
