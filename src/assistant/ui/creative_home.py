"""LDWord first-level creative home for the document assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import random
import time

from src.qt_api import (
    QColor,
    QDialog,
    QPushButton,
    QDesktopServices,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QScrollArea,
    QSizePolicy,
    QTextCursor,
    QTextEdit,
    QTextOption,
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
from src.assistant.ui.engineering_reference_picker import (
    EngineeringReferencePicker,
)


_GRID_SPACING = 42
_GRID_VERTICAL_TILT = 0.12
_GRID_HORIZONTAL_TILT = -0.08
_GRID_FILL_MIN = 20
_GRID_FILL_MAX = 28
_GRID_FILL_FADE_IN = 0.30
_GRID_FILL_HOLD = 0.18
_GRID_LINE_ALPHA = 20
_GRID_AMBIENT_ALPHA = (5, 8, 6, 7)
_HERO_COMPOSER_HEIGHT = 150
_COMPACT_COMPOSER_HEIGHT = 118
_HERO_STABLE_SLOT_HEIGHT = 240
_HERO_TITLE_HEIGHT = 44
_HERO_TITLE_GAP = 30
_HERO_EDIT_HEIGHT = 44
_HERO_EDIT_HEIGHT_WITH_ATTACHMENT = 30
_COMPACT_EDIT_HEIGHT = 30
_COMPACT_EDIT_HEIGHT_WITH_ATTACHMENT = 24
_HERO_ROOT_SPACING = 10
_COMPACT_ROOT_SPACING = 9
_ATTACHMENT_SLOT_HEIGHT = 34
_MAX_COMPOSER_ATTACHMENTS = 6
_ATTACHMENT_MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".wps": "application/vnd.ms-works",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
_HERO_SEND_BUTTON_SIZE = 36
_COMPACT_SEND_BUTTON_SIZE = 32
_FOOTER_CONTROL_HEIGHT = 34
_PROVIDER_MODEL_ROLE = int(Qt.UserRole) + 201
_PROVIDER_READY_ROLE = int(Qt.UserRole) + 202
_PROVIDER_REASON_ROLE = int(Qt.UserRole) + 203
_PROVIDER_STATUS_ROLE = int(Qt.UserRole) + 204


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


class _AssistantPromptTextEdit(QTextEdit):
    """Text editor that submits only when Enter is not owned by an IME."""

    submit_requested = Signal()
    editing_activity_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._preedit_active = False
        # QFile URLs belong to the composer attachment boundary.  Leaving
        # QTextEdit's default drop handling enabled inserts ``file:///...`` as
        # ordinary prompt text before the parent can turn it into a material.
        self.setAcceptDrops(False)

    def inputMethodEvent(self, event) -> None:  # noqa: N802
        self._preedit_active = bool(event.preeditString())
        super().inputMethodEvent(event)
        self.editing_activity_changed.emit(
            self.hasFocus() or self._preedit_active
        )

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.editing_activity_changed.emit(True)

    def focusOutEvent(self, event) -> None:
        self._preedit_active = False
        super().focusOutEvent(event)
        self.editing_activity_changed.emit(False)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if (
            event.key() in {Qt.Key_Return, Qt.Key_Enter}
            and event.modifiers() in {Qt.NoModifier, Qt.KeypadModifier}
            and not self._preedit_active
        ):
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class AssistantHeroComposer(QWidget):
    """Design-aligned task composer shared by home and active conversations."""

    message_sent = Signal(str)
    text_changed = Signal(str)
    provider_changed = Signal(str)
    document_path_changed = Signal(str)
    document_paths_changed = Signal(object)
    cancel_requested = Signal()
    editing_activity_changed = Signal(bool)

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
        self._document_paths: tuple[str, ...] = ()
        self._document_path = ""
        self._keyboard_hint_state: tuple[str, bool, bool] | None = None
        self._send_visual_state: tuple[object, ...] | None = None
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
        attachment_slot_layout = QHBoxLayout(self._attachment_slot)
        attachment_slot_layout.setContentsMargins(0, 0, 0, 0)
        attachment_slot_layout.setSpacing(4)

        self._attachment_previous = QToolButton(self._attachment_slot)
        self._attachment_previous.setObjectName("assistant_attachment_scroll_button")
        self._attachment_previous.setAccessibleName("查看前面的材料")
        self._attachment_previous.setFixedSize(28, 28)
        self._attachment_previous.setCursor(Qt.PointingHandCursor)
        self._attachment_previous.clicked.connect(
            lambda: self._scroll_attachment_chips(-1)
        )
        self._attachment_previous.hide()
        attachment_slot_layout.addWidget(
            self._attachment_previous,
            0,
            Qt.AlignVCenter,
        )

        self._attachment_scroll = QScrollArea(self._attachment_slot)
        self._attachment_scroll.setObjectName("assistant_attachment_scroll")
        self._attachment_scroll.setFrameShape(QFrame.NoFrame)
        self._attachment_scroll.setWidgetResizable(False)
        self._attachment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._attachment_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._attachment_scroll.setFixedHeight(_ATTACHMENT_SLOT_HEIGHT)
        self._attachment_scroll.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        attachment_slot_layout.addWidget(self._attachment_scroll, 1)

        self._attachment_row = QWidget(self._attachment_scroll)
        self._attachment_row.setObjectName("assistant_hero_attachment_row")
        self._attachment_layout = QHBoxLayout(self._attachment_row)
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(8)
        self._attachment_layout.setSizeConstraint(QLayout.SetFixedSize)
        self._attachment_chips: list[AssistantComposerAttachmentChip] = []
        # Compatibility alias for older integration checks that expect one
        # current chip.  It always points at the first selected material.
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
        self._attachment_scroll.setWidget(self._attachment_row)
        self._attachment_scroll.horizontalScrollBar().rangeChanged.connect(
            self._sync_attachment_scroll_controls
        )
        self._attachment_scroll.horizontalScrollBar().valueChanged.connect(
            lambda _value: self._sync_attachment_scroll_controls()
        )

        self._attachment_next = QToolButton(self._attachment_slot)
        self._attachment_next.setObjectName("assistant_attachment_scroll_button")
        self._attachment_next.setAccessibleName("查看更多材料")
        self._attachment_next.setFixedSize(28, 28)
        self._attachment_next.setCursor(Qt.PointingHandCursor)
        self._attachment_next.clicked.connect(
            lambda: self._scroll_attachment_chips(1)
        )
        self._attachment_next.hide()
        attachment_slot_layout.addWidget(
            self._attachment_next,
            0,
            Qt.AlignVCenter,
        )
        self._root_layout.addWidget(self._attachment_slot)

        self._text_edit = _AssistantPromptTextEdit(self)
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
        self._text_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        # Tall prompts scroll inside the compact editor instead of expanding
        # the composer beyond its reserved slot.
        self._text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._text_edit.setFixedHeight(
            _COMPACT_EDIT_HEIGHT if mode == "compact" else _HERO_EDIT_HEIGHT
        )
        self._text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._text_edit.submit_requested.connect(self._on_send)
        self._text_edit.textChanged.connect(self._on_text_changed)
        self._text_edit.editing_activity_changed.connect(
            self.editing_activity_changed.emit
        )
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
    def _attachment_paths_from_drop(event) -> tuple[str, ...]:
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            return ()
        paths: list[str] = []
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.casefold() in _ATTACHMENT_MEDIA_TYPES:
                normalized = str(path.resolve())
                if normalized.casefold() not in {
                    existing.casefold() for existing in paths
                }:
                    paths.append(normalized)
        return tuple(paths)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if (
            not self._busy
            and self._interaction_enabled
            and self._attachment_paths_from_drop(event)
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
        paths = self._attachment_paths_from_drop(event)
        self._drop_overlay.hide()
        if not paths:
            event.ignore()
            return
        self._add_document_paths(paths)
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
        display_text = requirement if blocking else self._default_keyboard_hint
        if self._submission_error and not blocking:
            display_text = self._submission_error
        visible = bool(requirement) or (self._mode == "hero" and self.width() >= 720)
        state = (display_text, blocking, visible)
        if state == self._keyboard_hint_state:
            return
        self._keyboard_hint_state = state
        self._keyboard_hint.setText(display_text)
        self._keyboard_hint.setProperty("blocking", blocking)
        self._keyboard_hint.setVisible(visible)
        self._keyboard_hint.style().unpolish(self._keyboard_hint)
        self._keyboard_hint.style().polish(self._keyboard_hint)

    def set_blocking_requirement(self, reason: str) -> None:
        normalized = str(reason or "").strip()
        if normalized == self._blocking_requirement:
            return
        self._blocking_requirement = normalized
        self._sync_keyboard_hint()
        self._update_send_state()

    def set_submission_gate(self, reason: str) -> None:
        """Block submission without disabling editing or discarding the draft."""

        normalized = str(reason or "").strip()
        if normalized == self._submission_gate:
            return
        self._submission_gate = normalized
        self._sync_keyboard_hint()
        self._update_send_state()

    def set_submission_error(self, reason: str) -> None:
        """Show a retryable submission error without discarding the draft."""

        normalized = str(reason or "").strip()
        if normalized == self._submission_error:
            return
        self._submission_error = normalized
        self._sync_keyboard_hint()
        self._update_send_state()

    def set_submission_handler(
        self,
        handler: Callable[[str], bool] | None,
    ) -> None:
        """Install the transactional submit boundary used by the owning panel."""

        self._submission_handler = handler

    def _on_text_changed(self) -> None:
        text = self._text_edit.toPlainText()
        character_count = len(text)
        self._input_limit_requirement = (
            f"当前输入为 {character_count} 字符，单次最多 "
            f"{MAX_ASSISTANT_USER_MESSAGE_CHARACTERS} 字符；"
            "请精简或拆分后再发送。"
            if character_count > MAX_ASSISTANT_USER_MESSAGE_CHARACTERS
            else ""
        )
        self._sync_keyboard_hint()
        self._update_send_state(text)
        self.text_changed.emit(text)

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

    def _update_send_state(self, text: str | None = None) -> None:
        current_text = self.get_text() if text is None else text
        has_text = bool(current_text.strip())
        can_send = (
            self._interaction_enabled
            and has_text
            and not self._blocking_requirement
            and not self._input_limit_requirement
            and not self._submission_gate
        )
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
        theme = get_theme()
        icon_color = theme.text_on_primary if (self._busy or can_send) else theme.text_hint
        icon_name = "square" if self._busy else "send"
        icon_size = 18 if self._busy else 20
        state = (
            self._busy,
            can_send,
            tooltip,
            icon_name,
            icon_size,
            icon_color,
        )
        if state == self._send_visual_state:
            return
        self._send_visual_state = state
        self._send_btn.setEnabled(self._busy or can_send)
        self._send_btn.setToolTip(tooltip)
        self._send_btn.setIcon(
            get_icon(icon_name, icon_size, icon_color)
        )

    def get_text(self) -> str:
        return self._text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        normalized = str(text or "")
        if self._text_edit.toPlainText() == normalized:
            return
        self._text_edit.setPlainText(normalized)
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text_edit.setTextCursor(cursor)

    def clear(self) -> None:
        if self._text_edit.toPlainText():
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

        normalized = bool(busy)
        if normalized == self._busy and self._interaction_enabled:
            return
        self._busy = normalized
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
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "添加文档材料",
            start,
            "文档材料 (*.docx *.doc *.wps *.md *.markdown);;Word / WPS 文档 (*.docx *.doc *.wps);;Markdown (*.md *.markdown)",
        )
        if paths:
            self._add_document_paths(tuple(paths))

    def _add_document_paths(self, paths: tuple[str, ...]) -> None:
        merged = list(self._document_paths)
        identities = {path.casefold() for path in merged}
        unsupported: list[str] = []
        overflow = False
        for raw_path in paths:
            path = Path(str(raw_path or "").strip()).expanduser()
            if not path.is_file() or path.suffix.casefold() not in _ATTACHMENT_MEDIA_TYPES:
                unsupported.append(path.name or str(raw_path or ""))
                continue
            normalized = str(path.resolve())
            if normalized.casefold() in identities:
                continue
            if len(merged) >= _MAX_COMPOSER_ATTACHMENTS:
                overflow = True
                self.set_submission_error(
                    f"单次最多添加 {_MAX_COMPOSER_ATTACHMENTS} 份材料；已保留前 "
                    f"{_MAX_COMPOSER_ATTACHMENTS} 份。"
                )
                break
            merged.append(normalized)
            identities.add(normalized.casefold())
        if unsupported:
            self.set_submission_error(
                "暂不支持这些材料："
                + "、".join(name for name in unsupported if name)
                + "。当前支持 DOCX / DOC / WPS 和 Markdown。"
            )
        elif not overflow:
            self.set_submission_error("")
        if tuple(merged) == self._document_paths:
            return
        self.set_document_paths(tuple(merged))
        self._emit_document_paths_changed()

    def _clear_attachment(self, path: str | None = None) -> None:
        if path is None:
            remaining: tuple[str, ...] = ()
        else:
            identity = str(path or "").casefold()
            remaining = tuple(
                item for item in self._document_paths if item.casefold() != identity
            )
        if remaining == self._document_paths:
            return
        self.set_document_paths(remaining)
        self._emit_document_paths_changed()

    def _emit_document_paths_changed(self) -> None:
        self.document_paths_changed.emit(self._document_paths)
        # Preserve the legacy signal as a projection of the first material.
        self.document_path_changed.emit(self.document_path())

    def _scroll_attachment_chips(self, direction: int) -> None:
        bar = self._attachment_scroll.horizontalScrollBar()
        step = max(120, self._attachment_scroll.viewport().width() // 2)
        bar.setValue(bar.value() + (step if direction > 0 else -step))

    def _sync_attachment_scroll_controls(
        self,
        _minimum: int | None = None,
        _maximum: int | None = None,
    ) -> None:
        bar = self._attachment_scroll.horizontalScrollBar()
        overflow = bar.maximum() > bar.minimum()
        self._attachment_previous.setVisible(
            overflow and bool(self._document_paths)
        )
        self._attachment_next.setVisible(
            overflow and bool(self._document_paths)
        )
        self._attachment_previous.setEnabled(bar.value() > bar.minimum())
        self._attachment_next.setEnabled(bar.value() < bar.maximum())

    def set_document_path(self, path: str) -> None:
        normalized = str(path or "").strip()
        self.set_document_paths((normalized,) if normalized else ())

    def set_document_paths(self, paths: tuple[str, ...]) -> None:
        normalized_paths: list[str] = []
        identities: set[str] = set()
        for raw_path in tuple(paths or ())[:_MAX_COMPOSER_ATTACHMENTS]:
            normalized = str(raw_path or "").strip()
            if not normalized or normalized.casefold() in identities:
                continue
            normalized_paths.append(normalized)
            identities.add(normalized.casefold())
        self._document_paths = tuple(normalized_paths)
        self._document_path = self._document_paths[0] if self._document_paths else ""
        for chip in self._attachment_chips:
            self._attachment_layout.removeWidget(chip)
            chip.hide()
            chip.deleteLater()
        self._attachment_chips = []
        self._attachment_chip = None
        if self._document_paths:
            self._text_edit.setFixedHeight(
                _COMPACT_EDIT_HEIGHT_WITH_ATTACHMENT
                if self._mode == "compact"
                else _HERO_EDIT_HEIGHT_WITH_ATTACHMENT
            )
            self._attachment_button.setText("" if self._mode == "compact" else "添加材料")
            self._attachment_button.setToolTip(
                f"继续添加文档材料（{len(self._document_paths)}/{_MAX_COMPOSER_ATTACHMENTS}）"
            )
            self._attachment_label.setText(
                "、".join(Path(path).name for path in self._document_paths)
            )
            self._attachment_label.setToolTip("\n".join(self._document_paths))
            for index, normalized in enumerate(self._document_paths):
                chip = AssistantComposerAttachmentChip(
                    {
                        "type": "file",
                        "title": Path(normalized).name,
                        "path": normalized,
                    },
                    self._attachment_row,
                )
                chip.remove_requested.connect(
                    lambda target=normalized: self._clear_attachment(target)
                )
                chip.reference_requested.connect(
                    lambda _reference, target=normalized: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(target)
                    )
                )
                self._attachment_layout.insertWidget(index, chip)
                self._attachment_chips.append(chip)
            self._attachment_chip = self._attachment_chips[0]
            self._attachment_row.adjustSize()
            self._attachment_slot.setFixedHeight(_ATTACHMENT_SLOT_HEIGHT)
            self._attachment_row.show()
            QTimer.singleShot(
                0,
                lambda: self._attachment_scroll.horizontalScrollBar().setValue(
                    self._attachment_scroll.horizontalScrollBar().maximum()
                ),
            )
        else:
            self._text_edit.setFixedHeight(
                _COMPACT_EDIT_HEIGHT
                if self._mode == "compact"
                else _HERO_EDIT_HEIGHT
            )
            self._attachment_button.setText("" if self._mode == "compact" else "添加材料")
            self._attachment_button.setToolTip("添加文档材料（支持 DOCX、Markdown，最多 6 份）")
            self._attachment_label.clear()
            self._attachment_label.setToolTip("")
            self._attachment_row.hide()
            self._attachment_slot.setFixedHeight(0)
            self._attachment_previous.hide()
            self._attachment_next.hide()

    def document_path(self) -> str:
        return self._document_path

    def document_paths(self) -> tuple[str, ...]:
        return self._document_paths

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
            QScrollArea#assistant_attachment_scroll,
            QWidget#assistant_hero_attachment_row {{
                background: transparent;
                border: none;
            }}
            QToolButton#assistant_attachment_scroll_button {{
                color: {theme.text_secondary};
                background: {theme.bg_hover};
                border: 1px solid {theme.border_light};
                border-radius: 14px;
                padding: 0;
            }}
            QToolButton#assistant_attachment_scroll_button:hover {{
                color: {theme.text_primary};
                border-color: {theme.border_focus};
            }}
            QToolButton#assistant_attachment_scroll_button:disabled {{
                color: {theme.text_disabled};
                background: transparent;
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
        self._attachment_previous.setIcon(
            get_icon("chevron-left", 14, theme.text_secondary)
        )
        self._attachment_next.setIcon(
            get_icon("chevron-right", 14, theme.text_secondary)
        )
        self._model_settings_button.setIcon(get_icon("settings", 16, theme.icon_secondary))
        self._update_send_state()


_STARTER_PROMPTS = (
    "写一份施工组织设计大纲",
    "写一份可研报告（分章节）",
    "按我给的目录写一本手册",
    "排版一份正式公文",
)


class AssistantCreativeHome(QWidget):
    """First-level empty state for the LDWord creative home."""

    message_sent = Signal(str)
    text_changed = Signal(str)
    provider_changed = Signal(str)
    # Emitted when the user asks to open an already-formatted document and edit
    # it chapter by chapter (list outline -> pick a chapter -> AI rewrite).
    open_document_requested = Signal()
    # Emitted when the user wants to manage the visual typesetting templates.
    typesetting_requested = Signal()
    # Emitted when the user wants to manage the visual typesetting templates.
    typesetting_requested = Signal()

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("assistant_creative_home")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(650)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._grid_random = random.Random()
        self._grid_fills: list[_GridFill] = []
        self._grid_static_cache: QPixmap | None = None
        self._grid_static_cache_key: tuple[object, ...] | None = None
        self._grid_timer = QTimer(self)
        self._grid_timer.setInterval(90)
        self._grid_timer.timeout.connect(self._tick_grid_fills)
        self._grid_animation_requested = True
        self._grid_interaction_suspended = False

        root = QVBoxLayout(self)
        root.setContentsMargins(72, 48, 72, 48)
        root.setSpacing(0)

        self._center = QWidget(self)
        self._center.setObjectName("assistant_home_center")
        self._center.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        center_layout = QVBoxLayout(self._center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(16)
        self._title_accent = QWidget(self._center)
        self._title_accent.setObjectName("assistant_home_title_accent")
        self._title_accent.setFixedSize(4, _HERO_TITLE_HEIGHT)
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
        # 工程范本库：从用户登记的工程文档里选一份真实范本，作为附件让 AI
        # 学习它的章节目录与写作惯例，再分章节起草同类工程文件。
        self._library_button = QPushButton("📚 工程范本库", self._center)
        self._library_button.setObjectName("assistant_home_library_button")
        self._library_button.setCursor(Qt.PointingHandCursor)
        self._library_button.setToolTip(
            "从工程范本库选一份真实工程文档，AI 按它的目录与写法生成同类文档"
        )
        self._library_button.clicked.connect(self._open_reference_library)
        title_row.addWidget(self._library_button, 0, Qt.AlignVCenter)
        self._chapter_edit_button = QPushButton("✏️ 打开文档改章节", self._center)
        self._chapter_edit_button.setObjectName("assistant_home_chapter_edit_button")
        self._chapter_edit_button.setCursor(Qt.PointingHandCursor)
        self._chapter_edit_button.setToolTip(
            "打开已排版好的 Word 文档，自动识别章节目录，选中某章让 AI 优化或重写并保留排版"
        )
        self._chapter_edit_button.clicked.connect(self.open_document_requested.emit)
        title_row.addWidget(self._chapter_edit_button, 0, Qt.AlignVCenter)
        self._template_button = QPushButton("🎨 排版模板", self._center)
        self._template_button.setObjectName("assistant_home_chapter_edit_button")
        self._template_button.setCursor(Qt.PointingHandCursor)
        self._template_button.setToolTip(
            "排版模板是可视化的格式插件：可新建/调整字体、表格样式、插图占位规则，"
            "并应用为当前模板，AI 逐章生成与 Word 排版都按它执行"
        )
        self._template_button.clicked.connect(self.typesetting_requested.emit)
        title_row.addWidget(self._template_button, 0, Qt.AlignVCenter)
        center_layout.addLayout(title_row)
        center_layout.addSpacing(_HERO_TITLE_GAP)

        self.composer = AssistantHeroComposer(bridge, self._center)
        self.composer.message_sent.connect(self.message_sent.emit)
        self.composer.text_changed.connect(self._on_composer_text_changed)
        self.composer.provider_changed.connect(self.provider_changed.emit)
        self.composer.editing_activity_changed.connect(
            self._set_grid_interaction_suspended
        )
        self._composer_slot = QFrame(self._center)
        self._composer_slot.setObjectName("assistant_home_composer_slot")
        self._composer_slot.setAttribute(Qt.WA_StyledBackground, True)
        self._composer_slot.setFixedHeight(_HERO_STABLE_SLOT_HEIGHT)
        composer_slot_layout = QVBoxLayout(self._composer_slot)
        composer_slot_layout.setContentsMargins(0, 0, 0, 0)
        composer_slot_layout.setSpacing(0)
        composer_slot_layout.addWidget(self.composer, 0, Qt.AlignVCenter)
        center_layout.addWidget(self._composer_slot)
        # 创作起步提示：示例需求点按即填入输入框，帮助新用户理解能做什么。
        self._starter_label = QLabel("可以这样开始", self._center)
        self._starter_label.setObjectName("assistant_home_starter_label")
        starter_wrap = QHBoxLayout()
        starter_wrap.setContentsMargins(0, 0, 0, 0)
        starter_wrap.setSpacing(8)
        starter_wrap.addWidget(self._starter_label)
        self._starter_buttons: list[QPushButton] = []
        for text in _STARTER_PROMPTS:
            button = QPushButton(text, self._center)
            button.setObjectName("assistant_home_starter")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, prompt=text: self._apply_starter(prompt)
            )
            self._starter_buttons.append(button)
            starter_wrap.addWidget(button)
        starter_wrap.addStretch(1)
        center_layout.addLayout(starter_wrap)
        center_layout.addSpacing(20)

        root.addWidget(self._center, 0, Qt.AlignCenter)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._update_center_width()

    def _apply_starter(self, prompt: str) -> None:
        """Fill a starter prompt into the composer without sending yet."""
        self._fill_starter(str(prompt or ""))

    def _fill_starter(self, prompt: str, *, paths: tuple[str, ...] = ()) -> None:
        """Apply the sample-learn flow into the home composer.

        A reference sample appends its real document as an attachment so the
        turn pipeline resolves the outline from the file (directory authoring)
        instead of guessing from keywords.
        """
        if paths:
            self.composer.set_document_paths(tuple(paths))
        if prompt:
            self.composer.set_text(prompt)
        self.composer.focus_input()

    def _open_reference_library(self) -> None:
        """Pick an engineering reference sample to learn from."""
        from src.config.engineering_reference import (
            list_engineering_reference_samples,
        )

        if not list_engineering_reference_samples():
            from src.shared.ui.dialogs import warning as dialog_warning

            dialog_warning(
                "暂无工程范本",
                "工程范本库还没有可用的范本文件。\n请把真实工程文档放进你的资料文件夹"
                "（例如 H:\\AI-model），并在用户数据目录"
                "config_library/engineering_reference/manifest.json 登记清单后重试。",
                parent=self,
            )
            return
        picker = EngineeringReferencePicker(self)
        if picker.exec() != QDialog.Accepted:
            return
        path = picker.selected_path()
        prompt = picker.selected_prompt()
        if not path:
            return
        self._fill_starter(prompt, paths=(path,))

    def _on_composer_text_changed(self, text: str) -> None:
        self.text_changed.emit(text)

    def focus_input(self) -> None:
        self.composer.focus_input()

    def set_grid_animation_active(self, active: bool) -> None:
        self._grid_animation_requested = bool(active)
        self._sync_grid_timer()

    def _set_grid_interaction_suspended(self, suspended: bool) -> None:
        suspended = bool(suspended)
        if suspended == self._grid_interaction_suspended:
            return
        self._grid_interaction_suspended = suspended
        self._sync_grid_timer()

    def _sync_grid_timer(self) -> None:
        should_run = (
            self._grid_animation_requested
            and not self._grid_interaction_suspended
            and self.isVisible()
        )
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
        self._invalidate_grid_static_cache()
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
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            painter.end()
            return

        spacing = _GRID_SPACING
        painter.drawPixmap(0, 0, self._grid_static_pixmap(width, height))
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._paint_grid_fills(painter, width, height, spacing)
        painter.end()

    def _invalidate_grid_static_cache(self) -> None:
        self._grid_static_cache = None
        self._grid_static_cache_key = None

    def _grid_static_pixmap(self, width: int, height: int) -> QPixmap:
        theme = get_theme()
        dpr = max(1.0, float(self.devicePixelRatioF()))
        cache_key = (width, height, round(dpr, 3), theme.text_hint)
        if (
            self._grid_static_cache is not None
            and self._grid_static_cache_key == cache_key
        ):
            return self._grid_static_cache

        pixmap = QPixmap(
            max(1, round(width * dpr)),
            max(1, round(height * dpr)),
        )
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._paint_grid_ambient_panels(painter, width, height)

        spacing = _GRID_SPACING
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
        self._grid_static_cache = pixmap
        self._grid_static_cache_key = cache_key
        return pixmap

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
        self._invalidate_grid_static_cache()
        self.setStyleSheet(
            f"""
            QWidget#assistant_creative_home {{ background: {theme.bg_window}; }}
            QWidget#assistant_home_center {{ background: transparent; }}
            QFrame#assistant_home_composer_slot {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_home_starter_label {{
                color: {theme.text_hint};
                background: transparent;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_home_starter {{
                color: {theme.text_secondary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
                padding: 5px 12px;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_home_starter:hover {{
                color: {theme.primary};
                background: {theme.bg_hover};
                border-color: {theme.primary};
            }}
            QPushButton#assistant_home_library_button {{
                color: {theme.primary};
                background: {theme.bg_card};
                border: 1px dashed {theme.primary};
                border-radius: {theme.radius_md}px;
                padding: 5px 12px;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_home_library_button:hover {{
                color: {theme.text_on_primary};
                background: {theme.primary};
                border-style: solid;
            }}
            QPushButton#assistant_home_chapter_edit_button {{
                color: {theme.primary};
                background: {theme.bg_card};
                border: 1px solid {theme.primary};
                border-radius: {theme.radius_md}px;
                padding: 5px 12px;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_home_chapter_edit_button:hover {{
                color: {theme.text_on_primary};
                background: {theme.primary};
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
            """
        )
        self._spark.setPixmap(get_icon("sparkles", 29, theme.primary).pixmap(29, 29))


__all__ = ["AssistantCreativeHome", "AssistantHeroComposer"]
