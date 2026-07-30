"""Alavette Design-style first-level creative home for the document assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import random
import time

from src.qt_api import (
    QColor,
    QDesktopServices,
    QEvent,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPainter,
    QPainterPath,
    QPen,
    QPushButton,
    QScrollArea,
    QSettings,
    QSizePolicy,
    QTextCursor,
    QTextEdit,
    QToolButton,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.styled_combo_box import StyledComboBox
from src.assistant.contracts.runtime import (
    MAX_ASSISTANT_USER_MESSAGE_CHARACTERS,
)
from src.assistant.ui.message_components import (
    AssistantAttachmentDropOverlay,
    AssistantComposerAttachmentChip,
)
from src.shared.ui.icons.catalog import get_icon


_GRID_SPACING = 42
_GRID_VERTICAL_TILT = 0.12
_GRID_HORIZONTAL_TILT = -0.08
_GRID_FILL_MIN = 20
_GRID_FILL_MAX = 28
_GRID_FILL_FADE_IN = 0.30
_GRID_FILL_HOLD = 0.18
_GRID_LINE_ALPHA = 20
_GRID_AMBIENT_ALPHA = (5, 8, 6, 7)
_HERO_COMPOSER_HEIGHT = 220
_COMPACT_COMPOSER_HEIGHT = 154
_HERO_STABLE_SLOT_HEIGHT = 240
_HERO_EDIT_HEIGHT = 84
_HERO_EDIT_HEIGHT_WITH_ATTACHMENT = 56
_COMPACT_EDIT_HEIGHT = 52
_COMPACT_EDIT_HEIGHT_WITH_ATTACHMENT = 38
_HERO_ROOT_SPACING = 10
_COMPACT_ROOT_SPACING = 9
_ATTACHMENT_SLOT_HEIGHT = 34
_HERO_SEND_BUTTON_SIZE = 36
_COMPACT_SEND_BUTTON_SIZE = 32
_FOOTER_CONTROL_HEIGHT = 34
_QUICK_TASK_ROW_HEIGHT = 50
_QUICK_TASK_VIEWPORT_HEIGHT = 150
_NEW_TASK_TOP_STRETCH = 3
_NEW_TASK_BOTTOM_STRETCH = 2
_PROVIDER_MODEL_ROLE = int(Qt.UserRole) + 201
_PROVIDER_READY_ROLE = int(Qt.UserRole) + 202
_PROVIDER_REASON_ROLE = int(Qt.UserRole) + 203
_PROVIDER_STATUS_ROLE = int(Qt.UserRole) + 204
_CUSTOM_TASK_SCHEMA_VERSION = "assistant-custom-tasks-v1"
_MAX_CUSTOM_TASK_LABEL_CHARACTERS = 80
_MAX_CUSTOM_TASK_PROMPT_CHARACTERS = 16_000
_MAX_CUSTOM_TASK_TOTAL_CHARACTERS = 100_000


@dataclass
class _GridFill:
    col: int
    row: int
    span_x: int
    span_y: int
    born_at: float
    duration: float
    max_alpha: int


def _grid_origin(width: int, height: int, spacing: int) -> tuple[int, int]:
    del spacing
    overscan = max(width, height)
    return -overscan, -overscan


@dataclass(frozen=True)
class _PromptAction:
    label: str
    description: str
    prompt: str
    icon_name: str
    requires_document: bool = False


_QUICK_START_ACTIONS = (
    _PromptAction(
        "生成文档初稿",
        "根据你的目标或已添加材料生成一份可审阅初稿",
        "请根据我提供的目标和材料生成一份结构清晰的文档初稿，并先给出可审阅的执行计划。",
        "file-text",
    ),
    _PromptAction(
        "检查结构与格式",
        "按优先级列出结构、样式和版式问题",
        "请分析当前文档的结构与格式问题，列出优先级、风险和修改建议。",
        "search",
        True,
    ),
    _PromptAction(
        "检查交付完整性",
        "核对缺失项、潜在风险和下一步动作",
        "请检查当前文档阶段产物，指出缺失项、潜在问题和下一步建议。",
        "circle-check",
        True,
    ),
)

_COMMON_TASKS = (
    _PromptAction(
        "确认文档目标",
        "先澄清读者、结构和交付要求",
        "请先通过必要的问题帮我确认文档目标、读者、结构和交付要求。",
        "crosshair",
    ),
    _PromptAction(
        "生成项目报告",
        "生成进展、风险和下一步报告",
        "请生成一份项目进展报告，先给出结构与执行计划供我确认。",
        "file-text",
    ),
    _PromptAction(
        "整理会议纪要",
        "提取结论、责任人和待办事项",
        "请把当前材料整理成会议纪要，提取结论、责任人和待办事项。",
        "list",
    ),
    _PromptAction(
        "起草通知公文",
        "确认文种、对象和关键事项后起草",
        "请起草一份正式通知公文，并在生成前确认文种、对象和关键事项。",
        "scroll-text",
    ),
    _PromptAction(
        "统一现有格式",
        "检查标题、正文、列表、表格和页码",
        "请检查并统一当前文档的标题、正文、列表、表格和页码格式。",
        "sliders-horizontal",
        True,
    ),
    _PromptAction(
        "套用模板排版",
        "按当前模板生成可审阅排版计划",
        "请基于当前模板重新规划并排版这份文档，先生成可审阅计划。",
        "layout",
        True,
    ),
)


class AssistantHeroComposer(QWidget):
    """Design-aligned task composer shared by home and active conversations."""

    message_sent = Signal(str)
    text_changed = Signal(str)
    provider_changed = Signal(str)
    document_path_changed = Signal(str)
    cancel_requested = Signal()

    def __init__(
        self,
        bridge,
        parent: QWidget | None = None,
        *,
        mode: str = "hero",
    ) -> None:
        super().__init__(parent)
        if mode not in {"hero", "compact"}:
            raise ValueError(f"Unsupported assistant composer mode: {mode!r}")
        self._bridge = bridge
        self._mode = mode
        self._busy = False
        self._interaction_enabled = True
        self._blocking_requirement = ""
        self._input_limit_requirement = ""
        self._submission_gate = ""
        self._submission_error = ""
        self._submission_handler: Callable[[str], bool] | None = None
        self._document_path = ""
        self.setObjectName(
            "assistant_task_composer" if mode == "compact" else "assistant_hero_composer"
        )
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setFixedHeight(
            _COMPACT_COMPOSER_HEIGHT if mode == "compact" else _HERO_COMPOSER_HEIGHT
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            18 if mode == "compact" else 24,
            14 if mode == "compact" else 20,
            20 if mode == "compact" else 24,
            14 if mode == "compact" else 18,
        )
        self._root_layout.setSpacing(
            _COMPACT_ROOT_SPACING if mode == "compact" else _HERO_ROOT_SPACING
        )

        # Keep a zero-height slot in the layout when no file is attached. This
        # preserves Design's editor/footer rhythm without exposing an empty row.
        self._attachment_slot = QWidget(self)
        self._attachment_slot.setObjectName("assistant_hero_attachment_slot")
        self._attachment_slot.setFixedHeight(0)
        attachment_slot_layout = QVBoxLayout(self._attachment_slot)
        attachment_slot_layout.setContentsMargins(0, 0, 0, 0)
        attachment_slot_layout.setSpacing(0)

        self._attachment_row = QWidget(self._attachment_slot)
        self._attachment_row.setObjectName("assistant_hero_attachment_row")
        self._attachment_layout = QHBoxLayout(self._attachment_row)
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(8)
        self._attachment_chip: AssistantComposerAttachmentChip | None = None
        # Kept as a non-visual compatibility alias for existing integration checks.
        self._attachment_label = QLabel(self._attachment_row)
        self._attachment_label.hide()
        self._attachment_disclosure = QLabel(
            "本次发送将读取附件正文",
            self._attachment_row,
        )
        self._attachment_disclosure.setObjectName("assistant_attachment_disclosure")
        self._attachment_disclosure.hide()
        self._remove_attachment = QToolButton(self._attachment_row)
        self._remove_attachment.hide()
        self._attachment_layout.addStretch(1)
        self._attachment_row.hide()
        attachment_slot_layout.addWidget(self._attachment_row)
        self._root_layout.addWidget(self._attachment_slot)

        self._text_edit = QTextEdit(self)
        self._text_edit.setObjectName("assistant_hero_editor")
        self._text_edit.setPlaceholderText(
            (
                "继续补充要求，或说明要如何调整当前文档…"
                if mode == "compact"
                else "上传材料、描述想法，或让我先帮你确认文档目标…"
            )
        )
        self._text_edit.setAcceptRichText(False)
        self._text_edit.setFrameShape(QFrame.NoFrame)
        self._text_edit.setFixedHeight(
            _COMPACT_EDIT_HEIGHT if mode == "compact" else _HERO_EDIT_HEIGHT
        )
        self._text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._text_edit.installEventFilter(self)
        self._text_edit.textChanged.connect(self._on_text_changed)
        self._root_layout.addWidget(self._text_edit)
        if mode == "hero":
            self._root_layout.addStretch(1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        self._attachment_button = self._tool_button(
            "paperclip",
            "添加材料",
            "添加文档材料（当前支持 DOCX）",
        )
        if mode == "compact":
            self._attachment_button.setText("")
            self._attachment_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self._attachment_button.setFixedSize(
                _FOOTER_CONTROL_HEIGHT,
                _FOOTER_CONTROL_HEIGHT,
            )
            self._attachment_button.setMinimumWidth(_FOOTER_CONTROL_HEIGHT)
        self._attachment_button.clicked.connect(self._pick_attachment)
        footer.addWidget(self._attachment_button)

        self._default_keyboard_hint = "Enter 发送 · Shift+Enter 换行"
        self._keyboard_hint = QLabel(self._default_keyboard_hint, self)
        self._keyboard_hint.setObjectName("assistant_hero_keyboard_hint")
        self._keyboard_hint.setProperty("blocking", False)
        footer.addStretch(1)
        footer.addWidget(self._keyboard_hint, 0, Qt.AlignVCenter)

        self._model_label = QLabel("模型", self)
        self._model_label.setObjectName("assistant_hero_model_label")
        footer.addWidget(self._model_label, 0, Qt.AlignVCenter)

        self._model_combo = StyledComboBox(self)
        self._model_combo.setObjectName("assistant_hero_model_combo")
        self._model_combo.set_inline(True)
        self._model_combo.set_outer_height(_FOOTER_CONTROL_HEIGHT)
        self._model_combo.setAccessibleName("AI 模型")
        self._model_combo.setAccessibleDescription("选择本次任务使用的模型")
        self._model_combo.setMinimumWidth(108)
        self._model_combo.setMaximumWidth(190)
        self._model_combo.currentIndexChanged.connect(self._emit_provider_changed)
        footer.addWidget(self._model_combo)

        self._model_settings_button = QToolButton(self)
        self._model_settings_button.setObjectName("assistant_hero_model_settings")
        self._model_settings_button.setAccessibleName("打开 AI 模型设置")
        self._model_settings_button.setToolTip("管理 API 地址、模型 ID 和 API Key")
        self._model_settings_button.setCursor(Qt.PointingHandCursor)
        self._model_settings_button.setFixedSize(
            _FOOTER_CONTROL_HEIGHT,
            _FOOTER_CONTROL_HEIGHT,
        )
        self._model_settings_button.clicked.connect(self._open_model_settings)
        footer.addWidget(self._model_settings_button)

        self._send_btn = QToolButton(self)
        self._send_btn.setObjectName("assistant_hero_send")
        self._send_btn.setAccessibleName("发送")
        self._send_btn.setAccessibleDescription("把当前输入发送到所选模型")
        self._send_btn.setCursor(Qt.PointingHandCursor)
        send_size = (
            _COMPACT_SEND_BUTTON_SIZE
            if mode == "compact"
            else _HERO_SEND_BUTTON_SIZE
        )
        self._send_btn.setFixedSize(send_size, send_size)
        self._send_btn.clicked.connect(self._on_send)
        footer.addWidget(self._send_btn)
        self._root_layout.addLayout(footer)

        self._drop_overlay = AssistantAttachmentDropOverlay(self)
        self.set_document_path(self._bridge.current_document_path())
        self._apply_theme()
        self._update_send_state()
        bind_theme(self, self._apply_theme)

    def _tool_button(
        self,
        icon_name: str,
        text: str,
        tooltip: str,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("assistant_hero_tool")
        button.setText(text)
        button.setAccessibleName(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setFixedHeight(_FOOTER_CONTROL_HEIGHT)
        button.setMinimumWidth(92)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button.setProperty("assistant_icon_name", icon_name)
        return button

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_drop_overlay"):
            self._drop_overlay.setGeometry(self.rect())
        self._sync_keyboard_hint()

    @staticmethod
    def _docx_path_from_drop(event) -> str:
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            return ""
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.casefold() == ".docx":
                return str(path.resolve())
        return ""

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if (
            not self._busy
            and self._interaction_enabled
            and self._docx_path_from_drop(event)
        ):
            self._drop_overlay.setGeometry(self.rect())
            self._drop_overlay.show()
            self._drop_overlay.raise_()
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._drop_overlay.hide()
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: N802
        path = self._docx_path_from_drop(event)
        self._drop_overlay.hide()
        if not path:
            event.ignore()
            return
        self.set_document_path(path)
        self.document_path_changed.emit(path)
        event.acceptProposedAction()

    def _sync_keyboard_hint(self) -> None:
        requirement = (
            self._submission_gate
            or self._input_limit_requirement
            or self._blocking_requirement
            or self._submission_error
        )
        blocking = bool(
            self._submission_gate
            or self._input_limit_requirement
            or self._blocking_requirement
        )
        self._keyboard_hint.setText(requirement if blocking else self._default_keyboard_hint)
        if self._submission_error and not blocking:
            self._keyboard_hint.setText(self._submission_error)
        self._keyboard_hint.setProperty("blocking", blocking)
        self._keyboard_hint.setVisible(
            bool(requirement)
            or (self._mode == "hero" and self.width() >= 720)
        )
        self._keyboard_hint.style().unpolish(self._keyboard_hint)
        self._keyboard_hint.style().polish(self._keyboard_hint)

    def set_blocking_requirement(self, reason: str) -> None:
        self._blocking_requirement = str(reason or "").strip()
        self._sync_keyboard_hint()
        self._update_send_state()

    def set_submission_gate(self, reason: str) -> None:
        """Block submission without disabling editing or discarding the draft."""

        self._submission_gate = str(reason or "").strip()
        self._sync_keyboard_hint()
        self._update_send_state()

    def set_submission_error(self, reason: str) -> None:
        """Show a retryable submission error without discarding the draft."""

        self._submission_error = str(reason or "").strip()
        self._sync_keyboard_hint()
        self._update_send_state()

    def set_submission_handler(
        self,
        handler: Callable[[str], bool] | None,
    ) -> None:
        """Install the transactional submit boundary used by the owning panel."""

        self._submission_handler = handler

    def eventFilter(self, obj, event) -> bool:
        if obj is self._text_edit and event.type() == QEvent.KeyPress:
            if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
                modifiers = event.modifiers()
                if modifiers in {Qt.NoModifier, Qt.KeypadModifier}:
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self) -> None:
        character_count = len(self.get_text())
        self._input_limit_requirement = (
            f"当前输入为 {character_count} 字符，单次最多 "
            f"{MAX_ASSISTANT_USER_MESSAGE_CHARACTERS} 字符；"
            "请精简或拆分后再发送。"
            if character_count > MAX_ASSISTANT_USER_MESSAGE_CHARACTERS
            else ""
        )
        self._sync_keyboard_hint()
        self._update_send_state()
        self.text_changed.emit(self.get_text())

    def _on_send(self) -> None:
        if self._busy:
            self.cancel_requested.emit()
            return
        text = self.get_text().strip()
        if not text or not self._send_btn.isEnabled():
            return
        accepted = True
        if self._submission_handler is not None:
            try:
                accepted = bool(self._submission_handler(text))
            except Exception as exc:
                self.set_submission_error(
                    "需求未写入，当前草稿已保留，可以重试。"
                    f"错误类型：{type(exc).__name__}"
                )
                accepted = False
        if not accepted:
            if not (
                self._submission_gate
                or self._blocking_requirement
                or self._input_limit_requirement
                or self._submission_error
            ):
                self.set_submission_error(
                    "需求未写入，当前草稿已保留；请检查存储空间后重试。"
                )
            self._sync_keyboard_hint()
            self._update_send_state()
            return
        self.set_submission_error("")
        self.message_sent.emit(text)
        self.clear()

    def _update_send_state(self) -> None:
        has_text = bool(self.get_text().strip())
        can_send = (
            self._interaction_enabled
            and has_text
            and not self._blocking_requirement
            and not self._input_limit_requirement
            and not self._submission_gate
        )
        self._send_btn.setEnabled(self._busy or can_send)
        if self._busy:
            tooltip = "停止当前任务"
        elif not self._interaction_enabled:
            tooltip = "当前任务正在处理"
        elif self._submission_gate:
            tooltip = self._submission_gate
        elif self._input_limit_requirement:
            tooltip = self._input_limit_requirement
        elif self._blocking_requirement:
            tooltip = self._blocking_requirement
        elif self._submission_error:
            tooltip = self._submission_error
        elif not has_text:
            tooltip = "输入任务内容后发送"
        else:
            tooltip = "发送任务（Enter）"
        self._send_btn.setToolTip(tooltip)
        theme = get_theme()
        icon_color = theme.text_on_primary if (self._busy or can_send) else theme.text_hint
        self._send_btn.setIcon(
            get_icon("square" if self._busy else "send", 18 if self._busy else 20, icon_color)
        )

    def get_text(self) -> str:
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        self._text_edit.setPlainText(str(text or ""))
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text_edit.setTextCursor(cursor)

    def clear(self) -> None:
        self._text_edit.clear()

    def set_placeholder(self, placeholder: str) -> None:
        self._text_edit.setPlaceholderText(str(placeholder or ""))

    def set_enabled(self, enabled: bool) -> None:
        self._busy = False
        self._interaction_enabled = bool(enabled)
        self._drop_overlay.hide()
        self._text_edit.setEnabled(enabled)
        self._model_combo.setEnabled(enabled)
        self._attachment_button.setEnabled(enabled)
        self._model_settings_button.setEnabled(enabled)
        self._update_send_state()

    def set_busy(self, busy: bool) -> None:
        """Keep cancellation reachable while locking turn-sensitive controls."""

        self._busy = bool(busy)
        self._interaction_enabled = True
        self._drop_overlay.hide()
        self._text_edit.setEnabled(not self._busy)
        self._model_combo.setEnabled(not self._busy)
        self._attachment_button.setEnabled(not self._busy)
        self._model_settings_button.setEnabled(not self._busy)
        self._send_btn.setAccessibleName("停止" if self._busy else "发送")
        self._update_send_state()

    def focus_input(self) -> None:
        self._text_edit.setFocus()

    def set_provider_profiles(
        self,
        profiles: list[tuple[str, str, str, bool, str, str]],
        *,
        selected_id: str = "",
    ) -> None:
        blocked = self._model_combo.blockSignals(True)
        try:
            self._model_combo.clear()
            selected_index = -1
            for label, profile_id, model_id, ready, reason, status in profiles:
                suffix = status if ready else "未就绪"
                display_label = label if not suffix else f"{label} · {suffix}"
                self._model_combo.addItem(display_label, profile_id)
                index = self._model_combo.count() - 1
                self._model_combo.setItemData(index, model_id, _PROVIDER_MODEL_ROLE)
                self._model_combo.setItemData(index, bool(ready), _PROVIDER_READY_ROLE)
                self._model_combo.setItemData(index, reason, _PROVIDER_REASON_ROLE)
                self._model_combo.setItemData(index, status, _PROVIDER_STATUS_ROLE)
                model = self._model_combo.model()
                item = model.item(index) if hasattr(model, "item") else None
                if item is not None:
                    item.setEnabled(bool(ready))
                    item.setToolTip(
                        f"模型 ID：{model_id}\n{reason or status}"
                        if reason
                        else f"模型 ID：{model_id}\n状态：{status or '可用'}"
                    )
                if profile_id == selected_id:
                    selected_index = index
            if self._model_combo.count():
                self._model_combo.setCurrentIndex(max(0, selected_index))
        finally:
            self._model_combo.blockSignals(blocked)
        self._sync_model_tooltip()
        self._sync_keyboard_hint()
        self._update_send_state()

    def select_provider(self, profile_id: str) -> None:
        for index in range(self._model_combo.count()):
            if str(self._model_combo.itemData(index) or "") == str(profile_id or ""):
                blocked = self._model_combo.blockSignals(True)
                self._model_combo.setCurrentIndex(index)
                self._model_combo.blockSignals(blocked)
                self._sync_model_tooltip()
                self._sync_keyboard_hint()
                self._update_send_state()
                return

    def selected_provider_id(self) -> str:
        return str(self._model_combo.currentData() or "")

    def selected_provider_ready(self) -> bool:
        index = self._model_combo.currentIndex()
        return bool(
            index >= 0
            and self._model_combo.itemData(index, _PROVIDER_READY_ROLE) is True
        )

    def _provider_requirement(self) -> str:
        if not hasattr(self, "_model_combo"):
            return ""
        index = self._model_combo.currentIndex()
        if index < 0 or not self.selected_provider_id():
            return "没有可用模型，请先在偏好设置中配置"
        if self.selected_provider_ready():
            return ""
        reason = str(
            self._model_combo.itemData(index, _PROVIDER_REASON_ROLE) or ""
        ).strip()
        return reason or "当前模型配置不可用，请先在偏好设置中处理"

    def _sync_model_tooltip(self) -> None:
        index = self._model_combo.currentIndex()
        if index < 0:
            self._model_combo.setToolTip("没有可用模型，请先在偏好设置中配置")
            return
        model_id = str(
            self._model_combo.itemData(index, _PROVIDER_MODEL_ROLE) or ""
        ).strip()
        reason = self._provider_requirement()
        status = str(
            self._model_combo.itemData(index, _PROVIDER_STATUS_ROLE) or ""
        ).strip()
        if reason:
            self._model_combo.setToolTip(f"{reason}\n模型 ID：{model_id}")
        else:
            self._model_combo.setToolTip(
                f"模型 ID：{model_id}\n状态：{status or '可用'}\n发送后会固定到当前会话"
            )

    def _open_model_settings(self) -> None:
        navigate = getattr(self._bridge, "navigate_to_preferences", None)
        if callable(navigate):
            navigate("ai")

    def _emit_provider_changed(self, _index: int) -> None:
        self._sync_model_tooltip()
        self._sync_keyboard_hint()
        self._update_send_state()
        profile_id = self.selected_provider_id()
        if profile_id:
            self.provider_changed.emit(profile_id)

    def _pick_attachment(self) -> None:
        current = self.document_path()
        start = str(Path(current).parent) if current else ""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "添加文档材料",
            start,
            "Word 文档 (*.docx)",
        )
        if path:
            self.set_document_path(path)
            self.document_path_changed.emit(self._document_path)

    def _clear_attachment(self) -> None:
        self.set_document_path("")
        self.document_path_changed.emit("")

    def set_document_path(self, path: str) -> None:
        normalized = str(path or "").strip()
        self._document_path = normalized
        if self._attachment_chip is not None:
            self._attachment_layout.removeWidget(self._attachment_chip)
            self._attachment_chip.hide()
            self._attachment_chip.deleteLater()
            self._attachment_chip = None
        if normalized:
            self._text_edit.setFixedHeight(
                _COMPACT_EDIT_HEIGHT_WITH_ATTACHMENT
                if self._mode == "compact"
                else _HERO_EDIT_HEIGHT_WITH_ATTACHMENT
            )
            self._attachment_button.setText("" if self._mode == "compact" else "更换材料")
            self._attachment_button.setToolTip("更换当前 DOCX 文档材料")
            self._attachment_label.setText(Path(normalized).name)
            self._attachment_label.setToolTip(normalized)
            self._attachment_chip = AssistantComposerAttachmentChip(
                {
                    "type": "file",
                    "title": Path(normalized).name,
                    "path": normalized,
                },
                self._attachment_row,
            )
            self._attachment_chip.remove_requested.connect(self._clear_attachment)
            self._attachment_chip.reference_requested.connect(
                lambda _reference, target=normalized: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(target)
                )
            )
            self._attachment_layout.insertWidget(0, self._attachment_chip)
            self._attachment_slot.setFixedHeight(_ATTACHMENT_SLOT_HEIGHT)
            self._attachment_row.show()
        else:
            self._text_edit.setFixedHeight(
                _COMPACT_EDIT_HEIGHT
                if self._mode == "compact"
                else _HERO_EDIT_HEIGHT
            )
            self._attachment_button.setText("" if self._mode == "compact" else "添加材料")
            self._attachment_button.setToolTip("添加文档材料（当前支持 DOCX）")
            self._attachment_label.clear()
            self._attachment_label.setToolTip("")
            self._attachment_row.hide()
            self._attachment_slot.setFixedHeight(0)

    def document_path(self) -> str:
        return self._document_path

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#assistant_hero_composer {{
                background: {theme.bg_input};
                border: 2px solid {theme.border_focus};
                border-radius: {theme.radius_lg}px;
            }}
            QWidget#assistant_task_composer {{
                background: {theme.bg_input};
                border: 1px solid {theme.border_focus};
                border-radius: {theme.radius_md}px;
            }}
            QTextEdit#assistant_hero_editor {{
                background: transparent;
                color: {theme.text_primary};
                border: none;
                padding: 2px 4px;
                font-size: {theme.font_size_lg}px;
            }}
            QLabel#assistant_attachment_disclosure {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            QToolButton#assistant_hero_tool,
            QToolButton#assistant_hero_model_settings {{
                color: {theme.text_secondary};
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_sm}px;
                padding: 0 8px;
            }}
            QToolButton#assistant_hero_tool:hover,
            QToolButton#assistant_hero_model_settings:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            QToolButton#assistant_hero_tool:disabled {{
                color: {theme.text_disabled};
                background: transparent;
                border-color: transparent;
            }}
            QLabel#assistant_hero_keyboard_hint {{
                color: {theme.text_hint};
                background: transparent;
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_hero_keyboard_hint[blocking="true"] {{
                color: {theme.warning};
            }}
            QLabel#assistant_hero_model_label {{
                color: {theme.text_secondary};
                background: transparent;
                font-size: {theme.font_size_sm}px;
            }}
            QToolButton#assistant_hero_send {{
                color: {theme.text_on_primary};
                background: {theme.primary};
                border: none;
                border-radius: 22px;
            }}
            QWidget#assistant_task_composer QToolButton#assistant_hero_send {{
                border-radius: 16px;
            }}
            QToolButton#assistant_hero_send:hover {{ background: {theme.primary_hover}; }}
            QToolButton#assistant_hero_send:pressed {{ background: {theme.primary_pressed}; }}
            QToolButton#assistant_hero_send:disabled {{
                color: {theme.text_hint};
                background: {theme.bg_hover};
            }}
            """
        )
        icon_name = str(self._attachment_button.property("assistant_icon_name") or "")
        self._attachment_button.setIcon(get_icon(icon_name, 17, theme.icon_secondary))
        self._model_settings_button.setIcon(get_icon("settings", 16, theme.icon_secondary))
        self._update_send_state()


class _TaskRow(QFrame):
    clicked = Signal(str, str)

    def __init__(self, action: _PromptAction, parent=None) -> None:
        super().__init__(parent)
        self._action = action
        self.setObjectName("assistant_home_task")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(action.label)
        self.setAccessibleDescription(
            f"{action.description}。激活后只填入输入框，不会自动发送。"
        )
        self.setToolTip(
            f"{action.description}\n点击后填入输入框，可修改后再发送。"
        )
        self.setFixedHeight(_QUICK_TASK_ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(12)
        self._icon = QLabel(self)
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(0)
        self._label = QLabel(action.label, self)
        self._label.setObjectName("assistant_home_task_label")
        copy_layout.addWidget(self._label)
        self._description = QLabel(action.description, self)
        self._description.setObjectName("assistant_home_task_description")
        copy_layout.addWidget(self._description)
        layout.addLayout(copy_layout, 1)

        self._arrow = QLabel(self)
        self._arrow.setFixedSize(18, 18)
        self._arrow.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._arrow)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def mouseReleaseEvent(self, event) -> None:
        if (
            self.isEnabled()
            and event.button() == Qt.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self._action.label, self._action.prompt)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.isEnabled() and event.key() in {Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space}:
            self.clicked.emit(self._action.label, self._action.prompt)
            event.accept()
            return
        super().keyPressEvent(event)

    def set_available(self, available: bool) -> None:
        available = bool(available)
        self.setEnabled(available)
        self.setFocusPolicy(Qt.StrongFocus if available else Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor if available else Qt.ForbiddenCursor)
        if available:
            description = self._action.description
            tooltip = (
                f"{description}\n点击后填入输入框，可修改后再发送。"
            )
        else:
            description = f"{self._action.description} · 需先添加 DOCX"
            tooltip = "此任务需要读取现有文档，请先点击“添加材料”。"
        self._description.setText(description)
        self.setToolTip(tooltip)
        self._apply_theme()

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if bool(self.property("selected")) == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#assistant_home_task {{
                background: transparent;
                border: 1px solid transparent;
                border-bottom-color: {theme.divider};
            }}
            QFrame#assistant_home_task:hover {{
                background: {theme.bg_hover};
                border-color: transparent;
                border-bottom-color: {theme.border_light};
                border-radius: {theme.radius_sm}px;
            }}
            QFrame#assistant_home_task:focus {{
                background: {theme.bg_hover};
                border: 1px solid {theme.border_focus};
                border-radius: {theme.radius_sm}px;
            }}
            QFrame#assistant_home_task[selected="true"] {{
                background: {theme.primary_light};
                border-color: transparent;
                border-bottom-color: {theme.border_focus};
                border-radius: {theme.radius_sm}px;
            }}
            QFrame#assistant_home_task:disabled {{
                background: transparent;
                border-color: transparent;
                border-bottom-color: {theme.divider};
            }}
            """
        )
        label_color = theme.text_primary if self.isEnabled() else theme.text_disabled
        description_color = theme.text_hint if self.isEnabled() else theme.text_disabled
        self._label.setStyleSheet(
            f"color:{label_color}; font-size:{theme.font_size_md}px; background:transparent;"
        )
        self._description.setStyleSheet(
            f"color:{description_color}; font-size:{theme.font_size_xs}px; background:transparent;"
        )
        selected = bool(self.property("selected"))
        if not self.isEnabled():
            icon_color = theme.text_disabled
        else:
            icon_color = theme.primary if selected else theme.icon_primary
        self._icon.setPixmap(
            get_icon(self._action.icon_name, 18, icon_color).pixmap(18, 18)
        )
        arrow_name = "circle-check" if selected else "chevron-right"
        if not self.isEnabled():
            arrow_color = theme.text_disabled
        else:
            arrow_color = theme.primary if selected else theme.text_hint
        self._arrow.setPixmap(get_icon(arrow_name, 14, arrow_color).pixmap(14, 14))


class AssistantCreativeHome(QWidget):
    """First-level empty state copied from the Alavette creative-home interaction."""

    message_sent = Signal(str)
    text_changed = Signal(str)
    provider_changed = Signal(str)

    _SETTINGS_KEY = "assistant/custom_document_tasks"
    _MAX_CUSTOM_TASKS = 12

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("assistant_creative_home")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(650)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._custom_task_load_warnings: list[str] = []
        self._custom_tasks = self._load_custom_tasks()
        self._selected_action_label = ""
        self._applying_action_prompt = False
        self._grid_random = random.Random()
        self._grid_fills: list[_GridFill] = []
        self._grid_timer = QTimer(self)
        self._grid_timer.setInterval(90)
        self._grid_timer.timeout.connect(self._tick_grid_fills)
        self._grid_animation_requested = True

        root = QVBoxLayout(self)
        root.setContentsMargins(72, 34, 72, 48)
        root.setSpacing(0)
        root.addStretch(_NEW_TASK_TOP_STRETCH)

        self._center = QWidget(self)
        self._center.setObjectName("assistant_home_center")
        self._center.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        center_layout = QVBoxLayout(self._center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(16)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(16)
        self._title_accent = QWidget(self._center)
        self._title_accent.setObjectName("assistant_home_title_accent")
        self._title_accent.setFixedSize(4, 44)
        title_row.addWidget(self._title_accent, 0, Qt.AlignVCenter)

        title_line = QHBoxLayout()
        title_line.setContentsMargins(0, 0, 0, 0)
        title_line.setSpacing(13)
        self._spark = QLabel(self._center)
        self._spark.setFixedSize(34, 34)
        self._spark.setAlignment(Qt.AlignCenter)
        title_line.addWidget(self._spark)
        self._title = QLabel("今天要创作什么？", self._center)
        self._title.setObjectName("assistant_home_title")
        title_line.addWidget(self._title)
        title_line.addStretch(1)
        title_row.addLayout(title_line, 1)
        center_layout.addLayout(title_row)
        center_layout.addSpacing(14)

        self.composer = AssistantHeroComposer(bridge, self._center)
        self.composer.message_sent.connect(self.message_sent.emit)
        self.composer.text_changed.connect(self._on_composer_text_changed)
        self.composer.provider_changed.connect(self.provider_changed.emit)
        self._composer_slot = QFrame(self._center)
        self._composer_slot.setObjectName("assistant_home_composer_slot")
        self._composer_slot.setAttribute(Qt.WA_StyledBackground, True)
        self._composer_slot.setFixedHeight(_HERO_STABLE_SLOT_HEIGHT)
        composer_slot_layout = QVBoxLayout(self._composer_slot)
        composer_slot_layout.setContentsMargins(0, 0, 0, 0)
        composer_slot_layout.setSpacing(0)
        composer_slot_layout.addWidget(self.composer, 0, Qt.AlignVCenter)
        center_layout.addWidget(self._composer_slot)

        suggestion_row = QHBoxLayout()
        suggestion_row.setContentsMargins(0, 10, 0, 0)
        suggestion_row.setSpacing(8)
        self._suggestion_label = QLabel("快速开始", self._center)
        self._suggestion_label.setObjectName("assistant_home_section_title")
        self._suggestion_label.setToolTip("固定任务入口；点击后只填入输入框，不会自动发送")
        suggestion_row.addWidget(self._suggestion_label)
        self.suggestion_buttons: list[QPushButton] = []
        for action in _QUICK_START_ACTIONS:
            button = QPushButton(action.label, self._center)
            button.setObjectName("assistant_home_suggestion")
            button.setProperty("action_label", action.label)
            button.setProperty("action_icon", action.icon_name)
            button.setProperty("action_description", action.description)
            button.setProperty("requires_document", action.requires_document)
            button.setProperty("selected", False)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(32)
            button.setIcon(get_icon(action.icon_name, 16))
            button.setToolTip(
                f"{action.description}\n点击后填入输入框，可修改后再发送。"
            )
            button.setAccessibleName(action.label)
            button.setAccessibleDescription(
                f"{action.description}。激活后只填入输入框，不会自动发送。"
            )
            button.clicked.connect(
                lambda _checked=False, value=action: self.select_prompt(
                    value.prompt,
                    label=value.label,
                )
            )
            suggestion_row.addWidget(button)
            self.suggestion_buttons.append(button)
        suggestion_row.addStretch(1)
        center_layout.addLayout(suggestion_row)

        task_header = QHBoxLayout()
        task_header.setContentsMargins(2, 18, 2, 6)
        task_header.setSpacing(8)
        self._task_label = QLabel("常用任务", self._center)
        self._task_label.setObjectName("assistant_home_section_title")
        task_header.addWidget(self._task_label)
        task_header.addStretch(1)
        self._manage_button = QPushButton("管理任务", self._center)
        self._manage_button.setObjectName("assistant_home_header_action")
        self._manage_button.setFixedHeight(28)
        self._manage_button.setToolTip("编辑或删除自己新增的常用任务")
        self._manage_button.clicked.connect(self._show_manage_menu)
        task_header.addWidget(self._manage_button)
        self._add_button = QPushButton("新增任务", self._center)
        self._add_button.setObjectName("assistant_home_header_action")
        self._add_button.setFixedHeight(28)
        self._add_button.setToolTip("新增一个可重复使用的提示词任务")
        self._add_button.clicked.connect(self._add_custom_task)
        task_header.addWidget(self._add_button)
        center_layout.addLayout(task_header)

        self._task_scroll = QScrollArea(self._center)
        self._task_scroll.setObjectName("assistant_home_task_scroll")
        self._task_scroll.setWidgetResizable(True)
        self._task_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._task_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._task_scroll.setFrameShape(QFrame.NoFrame)
        self._task_scroll.setFixedHeight(_QUICK_TASK_VIEWPORT_HEIGHT)
        self._task_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._task_host = QWidget(self._task_scroll)
        self._task_host.setObjectName("assistant_home_task_host")
        self._task_grid = QGridLayout(self._task_host)
        self._task_grid.setContentsMargins(0, 0, 0, 0)
        self._task_grid.setHorizontalSpacing(34)
        self._task_grid.setVerticalSpacing(0)
        self._task_grid.setColumnStretch(0, 1)
        self._task_grid.setColumnStretch(1, 1)
        self._task_scroll.setWidget(self._task_host)
        center_layout.addWidget(self._task_scroll)
        self._task_rows: list[_TaskRow] = []
        self._rebuild_tasks()

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch(1)
        center_row.addWidget(self._center)
        center_row.addStretch(1)
        root.addLayout(center_row)
        root.addStretch(_NEW_TASK_BOTTOM_STRETCH)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.composer.document_path_changed.connect(self._sync_action_availability)
        self._sync_action_availability()
        self._update_center_width()

    def select_prompt(self, prompt: str, *, label: str = "") -> None:
        self._set_selected_action(label)
        self._applying_action_prompt = True
        try:
            self.composer.set_text(prompt)
        finally:
            self._applying_action_prompt = False
        self._sync_action_availability()
        self.composer.focus_input()

    def _on_composer_text_changed(self, text: str) -> None:
        if not self._applying_action_prompt:
            self._set_selected_action("")
            self.composer.set_blocking_requirement("")
        self.text_changed.emit(text)

    def _set_selected_action(self, label: str) -> None:
        self._selected_action_label = str(label or "")
        theme = get_theme()
        for button in self.suggestion_buttons:
            selected = str(button.property("action_label") or "") == label
            button.setProperty("selected", selected)
            button.style().unpolish(button)
            button.style().polish(button)
            icon_name = str(button.property("action_icon") or "sparkles")
            icon_color = theme.primary if selected else theme.icon_primary
            button.setIcon(get_icon(icon_name, 16, icon_color))
        for row in getattr(self, "_task_rows", []):
            row.set_selected(row._action.label == label)

    def _sync_action_availability(self, *_args) -> None:
        document_path = self.composer.document_path()
        has_document = bool(document_path) and Path(document_path).is_file()
        for button in self.suggestion_buttons:
            requires_document = bool(button.property("requires_document"))
            available = has_document or not requires_document
            button.setEnabled(available)
            button.setCursor(
                Qt.PointingHandCursor if available else Qt.ForbiddenCursor
            )
            description = str(button.property("action_description") or "")
            button.setToolTip(
                f"{description}\n点击后填入输入框，可修改后再发送。"
                if available
                else "此任务需要读取现有文档，请先点击“添加材料”。"
            )
            button.style().unpolish(button)
            button.style().polish(button)
        for row in getattr(self, "_task_rows", []):
            available = has_document or not row._action.requires_document
            row.set_available(available)
        self._set_selected_action(self._selected_action_label)
        selected_requires_document = any(
            action.label == self._selected_action_label and action.requires_document
            for action in _QUICK_START_ACTIONS + _COMMON_TASKS
        )
        self.composer.set_blocking_requirement(
            "请先添加 DOCX，才能发送当前检查任务"
            if selected_requires_document and not has_document
            else ""
        )

    def focus_input(self) -> None:
        self.composer.focus_input()

    def _rebuild_tasks(self) -> None:
        while self._task_grid.count():
            item = self._task_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._task_rows.clear()
        tasks = [
            *_COMMON_TASKS,
            *(
                _PromptAction(
                    label=label,
                    description="自定义提示词任务",
                    prompt=prompt,
                    icon_name=icon_name,
                )
                for label, prompt, icon_name in self._custom_tasks
            ),
        ]
        for index, action in enumerate(tasks):
            row = _TaskRow(action, self._task_host)
            row.clicked.connect(
                lambda label, prompt: self.select_prompt(prompt, label=label)
            )
            self._task_grid.addWidget(row, index // 2, index % 2)
            self._task_rows.append(row)
        visible_rows = max(1, (len(tasks) + 1) // 2)
        self._task_host.setMinimumHeight(visible_rows * _QUICK_TASK_ROW_HEIGHT)
        self._manage_button.setEnabled(bool(self._custom_tasks))
        self._manage_button.setToolTip(
            (
                "编辑或删除自己新增的常用任务"
                + (
                    f"\n已忽略 {len(self._custom_task_load_warnings)} 个"
                    "不符合当前数据规则的旧任务。"
                    if self._custom_task_load_warnings
                    else ""
                )
            )
            if self._custom_tasks
            else (
                "暂无自定义任务；可先点击“新增任务”"
                + (
                    f"\n已忽略 {len(self._custom_task_load_warnings)} 个"
                    "不符合当前数据规则的旧任务。"
                    if self._custom_task_load_warnings
                    else ""
                )
            )
        )
        can_add = len(self._custom_tasks) < self._MAX_CUSTOM_TASKS
        self._add_button.setEnabled(can_add)
        self._add_button.setToolTip(
            "新增一个可重复使用的提示词任务"
            if can_add
            else f"最多只能保存 {self._MAX_CUSTOM_TASKS} 个自定义任务"
        )
        self._set_selected_action(self._selected_action_label)
        self._sync_action_availability()

    def _add_custom_task(self) -> None:
        if len(self._custom_tasks) >= self._MAX_CUSTOM_TASKS:
            QMessageBox.information(
                self,
                "无法继续新增",
                f"最多只能保存 {self._MAX_CUSTOM_TASKS} 个自定义任务。",
            )
            return
        label, accepted = QInputDialog.getText(self, "新增常用任务", "任务名称")
        label = str(label or "").strip()
        if not accepted or not label:
            return
        if len(label) > _MAX_CUSTOM_TASK_LABEL_CHARACTERS:
            QMessageBox.information(
                self,
                "任务名称过长",
                f"任务名称最多 {_MAX_CUSTOM_TASK_LABEL_CHARACTERS} 个字符。",
            )
            return
        if self._custom_task_name_exists(label):
            QMessageBox.information(self, "名称已存在", "请使用不同的任务名称。")
            return
        prompt, accepted = QInputDialog.getMultiLineText(
            self,
            "新增常用任务",
            "点击任务后填入输入框的提示词（不会自动发送）",
            label,
        )
        prompt = str(prompt or "").strip()
        if not accepted or not prompt:
            return
        if len(prompt) > _MAX_CUSTOM_TASK_PROMPT_CHARACTERS:
            QMessageBox.information(
                self,
                "提示词过长",
                f"单个提示词最多 {_MAX_CUSTOM_TASK_PROMPT_CHARACTERS} 个字符。",
            )
            return
        previous = list(self._custom_tasks)
        self._custom_tasks.append((label, prompt, "sparkles"))
        if self._commit_custom_tasks(previous):
            QTimer.singleShot(
                0,
                lambda: self._task_scroll.verticalScrollBar().setValue(
                    self._task_scroll.verticalScrollBar().maximum()
                ),
            )

    def _show_manage_menu(self) -> None:
        if not self._custom_tasks:
            return
        menu = QMenu(self)
        for index, (label, _prompt, _icon) in enumerate(self._custom_tasks):
            task_menu = QMenu(label, menu)
            task_menu.setIcon(get_icon("sparkles", 14))
            edit_action = task_menu.addAction(get_icon("pencil-line", 14), "编辑")
            edit_action.triggered.connect(
                lambda _checked=False, item=index: self._edit_custom_task(item)
            )
            delete_action = task_menu.addAction(get_icon("trash-2", 14), "删除")
            delete_action.triggered.connect(
                lambda _checked=False, item=index: self._delete_custom_task(item)
            )
            menu.addMenu(task_menu)
        menu.popup(self._manage_button.mapToGlobal(self._manage_button.rect().bottomLeft()))

    def _edit_custom_task(self, index: int) -> None:
        if not 0 <= index < len(self._custom_tasks):
            return
        current_label, current_prompt, icon_name = self._custom_tasks[index]
        label, accepted = QInputDialog.getText(
            self,
            "编辑常用任务",
            "任务名称",
            text=current_label,
        )
        label = str(label or "").strip()
        if not accepted or not label:
            return
        if len(label) > _MAX_CUSTOM_TASK_LABEL_CHARACTERS:
            QMessageBox.information(
                self,
                "任务名称过长",
                f"任务名称最多 {_MAX_CUSTOM_TASK_LABEL_CHARACTERS} 个字符。",
            )
            return
        if self._custom_task_name_exists(label, except_index=index):
            QMessageBox.information(self, "名称已存在", "请使用不同的任务名称。")
            return
        prompt, accepted = QInputDialog.getMultiLineText(
            self,
            "编辑常用任务",
            "点击任务后填入输入框的提示词（不会自动发送）",
            current_prompt,
        )
        prompt = str(prompt or "").strip()
        if not accepted or not prompt:
            return
        if len(prompt) > _MAX_CUSTOM_TASK_PROMPT_CHARACTERS:
            QMessageBox.information(
                self,
                "提示词过长",
                f"单个提示词最多 {_MAX_CUSTOM_TASK_PROMPT_CHARACTERS} 个字符。",
            )
            return
        previous = list(self._custom_tasks)
        self._custom_tasks[index] = (label, prompt, icon_name)
        self._set_selected_action("")
        self._commit_custom_tasks(previous)

    def _delete_custom_task(self, index: int) -> None:
        if not 0 <= index < len(self._custom_tasks):
            return
        label = self._custom_tasks[index][0]
        answer = QMessageBox.question(
            self,
            "删除常用任务",
            f"确定删除“{label}”吗？此操作只删除快捷任务，不会删除已有对话。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        previous = list(self._custom_tasks)
        self._custom_tasks.pop(index)
        self._set_selected_action("")
        self._commit_custom_tasks(previous)

    def _custom_task_name_exists(
        self,
        label: str,
        *,
        except_index: int = -1,
    ) -> bool:
        normalized = str(label or "").strip().casefold()
        return any(
            index != except_index and existing_label.strip().casefold() == normalized
            for index, (existing_label, _prompt, _icon) in enumerate(self._custom_tasks)
        )

    def _commit_custom_tasks(
        self,
        previous: list[tuple[str, str, str]],
    ) -> bool:
        if not self._custom_tasks_are_valid(self._custom_tasks):
            self._custom_tasks = previous
            self._rebuild_tasks()
            QMessageBox.warning(
                self,
                "任务数据超出限制",
                "任务名称、提示词或全部自定义任务总量超出限制，"
                "已恢复修改前的内容。",
            )
            return False
        if self._save_custom_tasks():
            self._rebuild_tasks()
            return True
        self._custom_tasks = previous
        self._rebuild_tasks()
        QMessageBox.warning(
            self,
            "保存失败",
            "常用任务未保存，已恢复修改前的内容。",
        )
        return False

    def _load_custom_tasks(self) -> list[tuple[str, str, str]]:
        raw = QSettings("Alavette", "Lark Formatter").value(self._SETTINGS_KEY, "")
        try:
            payload = json.loads(str(raw or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            if str(raw or "").strip():
                self._custom_task_load_warnings.append(
                    "custom_task_json_invalid"
                )
            return []
        if isinstance(payload, list):
            raw_tasks = payload
        elif (
            isinstance(payload, dict)
            and payload.get("schema_version") == _CUSTOM_TASK_SCHEMA_VERSION
            and isinstance(payload.get("tasks"), list)
        ):
            raw_tasks = payload["tasks"]
        else:
            if payload:
                self._custom_task_load_warnings.append(
                    "custom_task_schema_unsupported"
                )
            return []
        result: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        total_characters = 0
        for item in raw_tasks:
            if not isinstance(item, dict):
                self._custom_task_load_warnings.append(
                    "custom_task_row_invalid"
                )
                continue
            label = str(item.get("label") or "").strip()
            prompt = str(item.get("prompt") or "").strip()
            identity = label.casefold()
            row_size = len(label) + len(prompt)
            if (
                not label
                or not prompt
                or len(label) > _MAX_CUSTOM_TASK_LABEL_CHARACTERS
                or len(prompt) > _MAX_CUSTOM_TASK_PROMPT_CHARACTERS
                or identity in seen
                or total_characters + row_size
                > _MAX_CUSTOM_TASK_TOTAL_CHARACTERS
                or len(result) >= self._MAX_CUSTOM_TASKS
            ):
                self._custom_task_load_warnings.append(
                    "custom_task_row_rejected"
                )
                continue
            seen.add(identity)
            total_characters += row_size
            result.append((label, prompt, "sparkles"))
        return result

    def _save_custom_tasks(self) -> bool:
        if not self._custom_tasks_are_valid(self._custom_tasks):
            return False
        payload = {
            "schema_version": _CUSTOM_TASK_SCHEMA_VERSION,
            "tasks": [
                {"label": label, "prompt": prompt}
                for label, prompt, _icon in self._custom_tasks
            ],
        }
        settings = QSettings("Alavette", "Lark Formatter")
        try:
            settings.setValue(
                self._SETTINGS_KEY,
                json.dumps(payload, ensure_ascii=False),
            )
            settings.sync()
            return settings.status() == QSettings.Status.NoError
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    @staticmethod
    def _custom_tasks_are_valid(
        tasks: list[tuple[str, str, str]],
    ) -> bool:
        if len(tasks) > AssistantCreativeHome._MAX_CUSTOM_TASKS:
            return False
        seen: set[str] = set()
        total_characters = 0
        for label, prompt, _icon in tasks:
            normalized_label = str(label or "").strip()
            normalized_prompt = str(prompt or "").strip()
            identity = normalized_label.casefold()
            if (
                not normalized_label
                or not normalized_prompt
                or len(normalized_label)
                > _MAX_CUSTOM_TASK_LABEL_CHARACTERS
                or len(normalized_prompt)
                > _MAX_CUSTOM_TASK_PROMPT_CHARACTERS
                or identity in seen
            ):
                return False
            seen.add(identity)
            total_characters += len(normalized_label) + len(
                normalized_prompt
            )
        return total_characters <= _MAX_CUSTOM_TASK_TOTAL_CHARACTERS

    def set_grid_animation_active(self, active: bool) -> None:
        self._grid_animation_requested = bool(active)
        self._sync_grid_timer()

    def _sync_grid_timer(self) -> None:
        should_run = self._grid_animation_requested and self.isVisible()
        if should_run and not self._grid_timer.isActive():
            self._grid_timer.start()
        elif not should_run and self._grid_timer.isActive():
            self._grid_timer.stop()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_grid_timer()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._grid_timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_center_width()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        self._paint_slanted_grid()

    def _tick_grid_fills(self) -> None:
        now = time.monotonic()
        self._grid_fills = [
            fill for fill in self._grid_fills if now - fill.born_at < fill.duration
        ]
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        target_count = self._grid_random.randint(_GRID_FILL_MIN, _GRID_FILL_MAX)
        add_budget = min(
            self._grid_random.randint(1, 2),
            target_count - len(self._grid_fills),
        )
        attempts = 0
        added = 0
        while added < add_budget:
            attempts += 1
            fill = self._make_grid_fill(now, width, height)
            bounds = self._grid_fill_bounds(fill, width, height, _GRID_SPACING)
            if self._is_grid_fill_usable(bounds, width, height):
                self._grid_fills.append(fill)
                added += 1
            if attempts > target_count * 12:
                break
        self.update()

    def _make_grid_fill(
        self,
        now: float,
        width: int,
        height: int,
    ) -> _GridFill:
        overscan = max(width, height)
        cols = max(4, (width + (overscan * 2)) // _GRID_SPACING)
        rows = max(4, (height + (overscan * 2)) // _GRID_SPACING)
        span_x = self._grid_random.randint(1, 3)
        span_y = self._grid_random.randint(1, 2)
        return _GridFill(
            col=self._grid_random.randint(0, max(0, cols - span_x)),
            row=self._grid_random.randint(0, max(0, rows - span_y)),
            span_x=span_x,
            span_y=span_y,
            born_at=now,
            duration=self._grid_random.uniform(7.8, 12.0),
            max_alpha=self._grid_random.randint(8, 14),
        )

    def _grid_point(
        self,
        col: int,
        row: int,
        width: int,
        height: int,
        spacing: int,
    ) -> tuple[float, float]:
        origin_x, origin_y = _grid_origin(width, height, spacing)
        x = origin_x + col * spacing
        y = origin_y + row * spacing
        return (
            x + _GRID_VERTICAL_TILT * y,
            y + _GRID_HORIZONTAL_TILT * x,
        )

    def _grid_fill_points(
        self,
        fill: _GridFill,
        width: int,
        height: int,
        spacing: int,
    ) -> tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ]:
        left = fill.col
        top = fill.row
        right = fill.col + fill.span_x
        bottom = fill.row + fill.span_y
        return (
            self._grid_point(left, top, width, height, spacing),
            self._grid_point(right, top, width, height, spacing),
            self._grid_point(right, bottom, width, height, spacing),
            self._grid_point(left, bottom, width, height, spacing),
        )

    def _grid_fill_bounds(
        self,
        fill: _GridFill,
        width: int,
        height: int,
        spacing: int,
    ) -> tuple[float, float, float, float]:
        points = self._grid_fill_points(fill, width, height, spacing)
        return (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )

    def _is_grid_fill_usable(
        self,
        bounds: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> bool:
        min_x, min_y, max_x, max_y = bounds
        margin = _GRID_SPACING
        if (
            min_x < -margin
            or max_x > width + margin
            or min_y < -margin
            or max_y > height + margin
        ):
            return False

        composer_left = self._center.x() + self._composer_slot.x() + self.composer.x()
        composer_top = self._center.y() + self._composer_slot.y() + self.composer.y()
        avoid_left = composer_left - 18
        avoid_top = composer_top - 18
        avoid_right = composer_left + self.composer.width() + 18
        avoid_bottom = composer_top + self.composer.height() + 18
        if not (
            max_x < avoid_left
            or min_x > avoid_right
            or max_y < avoid_top
            or min_y > avoid_bottom
        ):
            return False

        return not any(
            self._bounds_overlap(
                bounds,
                self._grid_fill_bounds(existing, width, height, _GRID_SPACING),
                padding=10,
            )
            for existing in self._grid_fills
        )

    @staticmethod
    def _bounds_overlap(
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
        *,
        padding: int = 0,
    ) -> bool:
        first_min_x, first_min_y, first_max_x, first_max_y = first
        second_min_x, second_min_y, second_max_x, second_max_y = second
        return not (
            first_max_x + padding <= second_min_x
            or first_min_x - padding >= second_max_x
            or first_max_y + padding <= second_min_y
            or first_min_y - padding >= second_max_y
        )

    @staticmethod
    def _grid_fill_alpha_ratio(progress: float) -> float:
        hold_end = _GRID_FILL_FADE_IN + _GRID_FILL_HOLD
        if progress < _GRID_FILL_FADE_IN:
            return progress / _GRID_FILL_FADE_IN
        if progress < hold_end:
            return 1.0
        return max(0.0, 1.0 - ((progress - hold_end) / (1.0 - hold_end)))

    def _paint_slanted_grid(self) -> None:
        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            painter.end()
            return

        spacing = _GRID_SPACING
        self._paint_grid_ambient_panels(painter, width, height)
        self._paint_grid_fills(painter, width, height, spacing)

        grid = QColor(theme.text_hint)
        grid.setAlpha(_GRID_LINE_ALPHA)
        painter.setPen(QPen(grid, 1))
        overscan = max(width, height)
        max_cols = max(4, (width + (overscan * 2)) // spacing)
        max_rows = max(4, (height + (overscan * 2)) // spacing)
        for col in range(max_cols + 1):
            x1, y1 = self._grid_point(col, 0, width, height, spacing)
            x2, y2 = self._grid_point(col, max_rows, width, height, spacing)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        for row in range(max_rows + 1):
            x1, y1 = self._grid_point(0, row, width, height, spacing)
            x2, y2 = self._grid_point(max_cols, row, width, height, spacing)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.end()

    @staticmethod
    def _ambient_panel_points(
        width: int,
        height: int,
        left_ratio: float,
        right_ratio: float,
    ) -> tuple[tuple[float, float], ...]:
        shift = height * _GRID_VERTICAL_TILT
        return (
            (width * left_ratio, 0.0),
            (width * right_ratio, 0.0),
            (width * right_ratio + shift, float(height)),
            (width * left_ratio + shift, float(height)),
        )

    def _paint_grid_ambient_panels(
        self,
        painter: QPainter,
        width: int,
        height: int,
    ) -> None:
        """Keep the Design-style depth visible before animation has advanced."""

        spans = ((-0.10, 0.08), (0.24, 0.39), (0.57, 0.72), (0.90, 1.08))
        painter.setPen(Qt.NoPen)
        for (left, right), alpha in zip(spans, _GRID_AMBIENT_ALPHA):
            color = QColor(get_theme().text_hint)
            color.setAlpha(alpha)
            painter.setBrush(color)
            points = self._ambient_panel_points(width, height, left, right)
            path = QPainterPath()
            path.moveTo(*points[0])
            for point in points[1:]:
                path.lineTo(*point)
            path.closeSubpath()
            painter.drawPath(path)

    def _paint_grid_fills(
        self,
        painter: QPainter,
        width: int,
        height: int,
        spacing: int,
    ) -> None:
        if not self._grid_fills:
            self._tick_grid_fills()
            if not self._grid_fills:
                return

        now = time.monotonic()
        painter.setPen(Qt.NoPen)
        for fill in self._grid_fills:
            progress = (now - fill.born_at) / fill.duration
            if progress < 0.0 or progress >= 1.0:
                continue
            alpha = int(fill.max_alpha * self._grid_fill_alpha_ratio(progress))
            if alpha < 1:
                continue
            color = QColor(get_theme().text_hint)
            color.setAlpha(alpha)
            painter.setBrush(color)
            top_left, top_right, bottom_right, bottom_left = self._grid_fill_points(
                fill,
                width,
                height,
                spacing,
            )
            path = QPainterPath()
            path.moveTo(*top_left)
            path.lineTo(*top_right)
            path.lineTo(*bottom_right)
            path.lineTo(*bottom_left)
            path.closeSubpath()
            painter.drawPath(path)

    def _update_center_width(self) -> None:
        available = max(320, self.width() - 144)
        target = min(1180, max(860, int(available * 0.78)))
        self._center.setFixedWidth(min(target, available))
        self.update()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#assistant_creative_home {{ background: {theme.bg_window}; }}
            QWidget#assistant_home_center {{ background: transparent; }}
            QFrame#assistant_home_composer_slot {{
                background: transparent;
                border: none;
            }}
            QScrollArea#assistant_home_task_scroll,
            QWidget#assistant_home_task_host {{
                background: transparent;
                border: none;
            }}
            QScrollArea#assistant_home_task_scroll QWidget#qt_scrollarea_viewport {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.border};
                border-radius: 2px;
                min-height: 28px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
                border: none;
                height: 0;
            }}
            QWidget#assistant_home_title_accent {{
                background: {theme.primary};
                border-radius: 1px;
            }}
            QLabel#assistant_home_title {{
                color: {theme.text_primary};
                font-size: {theme.font_size_xxl + 6}px;
                font-weight: {theme.font_weight_bold};
                background: transparent;
                border: none;
            }}
            QLabel#assistant_home_section_title {{
                color: {theme.text_primary};
                font-size: {theme.font_size_lg}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QPushButton#assistant_home_suggestion {{
                color: {theme.text_secondary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_full}px;
                padding: 0 12px;
                text-align: left;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_home_suggestion:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border};
            }}
            QPushButton#assistant_home_suggestion:focus {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border_focus};
            }}
            QPushButton#assistant_home_suggestion[selected="true"] {{
                color: {theme.primary};
                background: {theme.primary_light};
                border-color: {theme.border_focus};
            }}
            QPushButton#assistant_home_suggestion:disabled {{
                color: {theme.text_disabled};
                background: {theme.bg_input};
                border-color: {theme.border_light};
            }}
            QPushButton#assistant_home_header_action {{
                color: {theme.text_secondary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 0 10px;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_home_header_action:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border};
            }}
            QPushButton#assistant_home_header_action:disabled {{
                color: {theme.text_disabled};
                background: {theme.bg_input};
            }}
            """
        )
        self._spark.setPixmap(get_icon("sparkles", 29, theme.primary).pixmap(29, 29))
        self._set_selected_action(self._selected_action_label)


__all__ = ["AssistantCreativeHome", "AssistantHeroComposer"]
