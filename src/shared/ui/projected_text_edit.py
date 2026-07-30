"""Composite text controls with separate canonical, display, and edit values."""

from __future__ import annotations

from enum import Enum
import math

from src.qt_api import (
    QApplication,
    QEvent,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPoint,
    QRect,
    QSizePolicy,
    QStackedLayout,
    QTextEdit,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.inline_copy_edit import (
    ConfirmedCopyEmitter,
    InlineEditDismissalGuard,
)
from src.shared.ui.input_metrics import build_input_editor_stylesheet
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.text_projection import ElidedTextLabel, TextElideMode
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.tooltip import set_global_tooltip


FULL_TEXT_TOOLTIP_DELAY_MS = 300
EXPANDED_EDITOR_MIN_WIDTH = 420
EXPANDED_EDITOR_MAX_WIDTH = 560
EXPANDED_EDITOR_SCREEN_MARGIN = 8
EXPANDED_EDITOR_GAP = 4


def _expanded_preview_stylesheet(theme) -> str:
    return (
        "QTextEdit#projected_text_expanded_preview {"
        "background: transparent; border: none; padding: 2px 0;"
        f"color: {theme.text_secondary};"
        "}"
    )


class EditActivation(str, Enum):
    """How a projected text surface enters editing."""

    COPY_DOUBLE_EDIT = "copy_double_edit"
    DIRECT_EDIT = "direct_edit"
    COPY_ONLY = "copy_only"


class TextSurface(str, Enum):
    """Visual role of a projected text surface."""

    PLAIN = "plain"
    FRAMED = "framed"


class _InteractiveProjectionLabel(ElidedTextLabel):
    clicked = Signal()
    double_clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _ExpandedEditorPopup(QWidget):
    """Transparent popup shell around a self-painted rounded card.

    A radius on a top-level QSS background does not shape the native Windows
    popup or its rectangular drop shadow.  Keeping the top-level window fully
    transparent and painting the card in a child surface gives the visible
    card and the real window corners the same geometry.
    """

    dismissed = Signal()

    def __init__(self, parent=None) -> None:
        flags = Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        super().__init__(parent, flags)
        self.setObjectName("projected_text_expanded_popup")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

        shell_layout = QVBoxLayout(self)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.surface = RoundedSurfaceFrame(parent=self)
        self.surface.setObjectName("projected_text_expanded_surface")
        shell_layout.addWidget(self.surface)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().hideEvent(event)
        # Defer until Qt has finished the native Popup hide transition.  The
        # receiver is idempotent, so programmatic closing after a commit is a
        # harmless no-op while native outside-dismissal still commits.
        defer_qt_method(self, "_emit_dismissed")

    def _emit_dismissed(self) -> None:
        self.dismissed.emit()


class _ExpandedPreviewEdit(QTextEdit):
    """Read-only full token preview that can position the editable core."""

    positionRequested = Signal(int)
    heightChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("projected_text_expanded_preview")
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.IBeamCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.document().setDocumentMargin(0)

    def text(self) -> str:
        """QLabel-compatible accessor retained for existing callers/tests."""

        return self.toPlainText()

    def setText(self, text: object) -> None:  # noqa: N802 - compatibility API
        self.setPlainText(str(text or ""))
        self._sync_height()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        defer_qt_method(self, "_sync_height")

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            position = self.cursorForPosition(event.position().toPoint()).position()
            self.positionRequested.emit(position)
            event.accept()
            return
        super().mousePressEvent(event)

    def _sync_height(self) -> None:
        viewport_width = max(1, self.viewport().width())
        self.document().setTextWidth(viewport_width)
        document_height = math.ceil(self.document().size().height())
        margins = self.contentsMargins()
        target = max(
            self.fontMetrics().height(),
            document_height + margins.top() + margins.bottom() + 4,
        )
        if self.height() != target:
            self.setFixedHeight(target)
            self.heightChanged.emit()


class ProjectedTextEdit(QWidget):
    """One canonical value with width-safe display and explicit edit projection.

    Subclasses override ``_split_canonical`` and ``_compose_canonical`` when
    only part of a structured value may be edited.  The displayed elision is
    never assigned back to the canonical value.
    """

    copied = Signal(str)
    textChanged = Signal(str)
    editingFinished = Signal()

    def __init__(
        self,
        text: object = "",
        parent=None,
        *,
        editable: bool = True,
        activation: EditActivation = EditActivation.COPY_DOUBLE_EDIT,
        surface: TextSurface = TextSurface.FRAMED,
        elide_mode: TextElideMode = TextElideMode.RIGHT,
        font_weight: int | None = None,
        show_full_text_tooltip: bool = False,
        expand_editor_on_overflow: bool = False,
    ) -> None:
        super().__init__(parent)
        self._canonical_text = ""
        self._placeholder_text = ""
        self._editable = bool(editable)
        self._activation = EditActivation(activation)
        if self._activation is EditActivation.COPY_ONLY:
            self._editable = False
        self._surface = TextSurface(surface)
        self._elide_mode = TextElideMode(elide_mode)
        self._font_weight = font_weight
        self._show_full_text_tooltip = bool(show_full_text_tooltip)
        self._expand_editor_on_overflow = bool(expand_editor_on_overflow)
        self._editing = False
        self._expanded_editing = False
        self._edit_snapshot = ""
        self._locked_prefix = ""
        self._locked_suffix = ""

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setSpacing(0)

        self._display = _InteractiveProjectionLabel(
            "",
            self,
            mode=self._elide_mode,
        )
        self._display.setObjectName("projected_text_display")
        self._display.clicked.connect(self._on_display_clicked)
        self._display.double_clicked.connect(self._on_display_double_clicked)
        self._display.elisionChanged.connect(self._sync_full_text_tooltip)
        self._stack.addWidget(self._display)

        self._editor_frame = QFrame(self)
        self._editor_frame.setObjectName("projected_text_editor_frame")
        editor_layout = QHBoxLayout(self._editor_frame)
        editor_layout.setContentsMargins(8, 0, 8, 0)
        editor_layout.setSpacing(0)
        self._prefix_label = QLabel(self._editor_frame)
        self._prefix_label.setObjectName("projected_text_locked_prefix")
        self._editor = QLineEdit(self._editor_frame)
        self._editor.setObjectName("projected_text_inner_editor")
        self._editor.setFrame(False)
        self._editor.setReadOnly(True)
        self._editor.setMinimumWidth(0)
        self._editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._suffix_label = QLabel(self._editor_frame)
        self._suffix_label.setObjectName("projected_text_locked_suffix")
        editor_layout.addWidget(self._prefix_label, 0)
        editor_layout.addWidget(self._editor, 1)
        editor_layout.addWidget(self._suffix_label, 0)
        self._stack.addWidget(self._editor_frame)
        self._stack.setCurrentWidget(self._display)

        self._expanded_popup = _ExpandedEditorPopup(self)
        self._expanded_popup.dismissed.connect(self._request_finish_edit)
        self._expanded_surface = self._expanded_popup.surface
        expanded_layout = QVBoxLayout(self._expanded_surface)
        expanded_layout.setContentsMargins(12, 10, 12, 10)
        expanded_layout.setSpacing(8)
        self._expanded_content_layout = expanded_layout
        self._expanded_title = QLabel(
            self._expanded_editor_title(),
            self._expanded_surface,
        )
        self._expanded_title.setObjectName("projected_text_expanded_title")
        self._expanded_preview = _ExpandedPreviewEdit(self._expanded_surface)
        self._expanded_preview.positionRequested.connect(
            self._on_expanded_preview_position
        )
        self._expanded_preview.heightChanged.connect(
            self._on_expanded_preview_height_changed
        )
        self._expanded_preview_core_start = 0
        self._expanded_preview_core_end = 0
        self._expanded_hint = QLabel(
            self._expanded_editor_hint(),
            self._expanded_surface,
        )
        self._expanded_hint.setObjectName("projected_text_expanded_hint")
        self._expanded_hint.setWordWrap(True)
        expanded_layout.addWidget(self._expanded_title)
        expanded_layout.addWidget(self._expanded_preview)
        expanded_layout.addWidget(self._expanded_hint)

        self._copy_feedback = ConfirmedCopyEmitter(self.copied.emit, self)
        self._dismissal_guard = InlineEditDismissalGuard(
            self,
            self._request_finish_edit,
            self,
        )
        self._dismissal_guard.add_inside_root(self._expanded_popup)
        for interaction_target in (
            self._editor,
            self._editor_frame,
            self._prefix_label,
            self._suffix_label,
        ):
            interaction_target.installEventFilter(self)
        self._editor.textChanged.connect(self._on_inner_text_changed)
        self._editor.editingFinished.connect(self._finish_edit)
        self._editor.setClearButtonEnabled(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setText(text)
        self._sync_cursor()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ------------------------------------------------------------------
    # QLineEdit-compatible public contract used by presenters.
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._canonical_text

    def displayText(self) -> str:  # noqa: N802
        return self._display.renderedText()

    def editableText(self) -> str:  # noqa: N802
        return self._editor.text() if self._editing else self._split_canonical(
            self._canonical_text
        )[1]

    def setText(self, text: object) -> None:  # noqa: N802
        canonical = self._canonical_from_input(text)
        changed = canonical != self._canonical_text
        self._canonical_text = canonical
        prefix, core, suffix = self._split_canonical(canonical)
        self._locked_prefix = prefix
        self._locked_suffix = suffix
        if self._editing:
            blocked = self._editor.blockSignals(True)
            self._editor.setText(core)
            self._editor.blockSignals(blocked)
            self._sync_editor_affixes(prefix, suffix)
            self._update_expanded_preview()
        self._refresh_display()
        if changed:
            self.textChanged.emit(canonical)

    def setPlaceholderText(self, text: object) -> None:  # noqa: N802
        self._placeholder_text = str(text or "")
        self._editor.setPlaceholderText(self._placeholder_text)
        self._refresh_display()

    def placeholderText(self) -> str:  # noqa: N802
        return self._placeholder_text

    def setClearButtonEnabled(self, enabled: bool) -> None:  # noqa: N802
        self._editor.setClearButtonEnabled(bool(enabled))

    def clear(self) -> None:
        self.setText("")

    def setReadOnly(self, read_only: bool) -> None:  # noqa: N802
        if read_only and self._editing:
            self._finish_edit()
        self._editable = not bool(read_only)
        if self._activation is EditActivation.COPY_ONLY:
            self._editable = False
        self._sync_cursor()

    def isReadOnly(self) -> bool:  # noqa: N802
        if self._activation is EditActivation.DIRECT_EDIT:
            return not self._editable
        return not self._editing

    def isInlineEditable(self) -> bool:  # noqa: N802
        return self._editable

    def isInlineEditing(self) -> bool:  # noqa: N802
        return self._editing

    def isExpandedEditing(self) -> bool:  # noqa: N802
        return self._editing and self._expanded_editing

    def hasFocus(self) -> bool:  # noqa: N802
        return bool(self._editor.hasFocus() or super().hasFocus())

    def setFocus(self, reason=None) -> None:  # noqa: N802
        if self._editable and not self._editing:
            self._begin_edit()
        if self._editing:
            if reason is None:
                self._editor.setFocus()
            else:
                self._editor.setFocus(reason)
        elif reason is None:
            super().setFocus()
        else:
            super().setFocus(reason)

    def clearFocus(self) -> None:  # noqa: N802
        self._editor.clearFocus()
        super().clearFocus()

    def selectAll(self) -> None:  # noqa: N802
        if self._editing:
            self._editor.selectAll()

    def innerEditor(self) -> QLineEdit:  # noqa: N802
        return self._editor

    def displaySurface(self) -> ElidedTextLabel:  # noqa: N802
        return self._display

    def lockedPrefix(self) -> str:  # noqa: N802
        return self._locked_prefix

    def lockedSuffix(self) -> str:  # noqa: N802
        return self._locked_suffix

    def beginEdit(self) -> None:  # noqa: N802
        """Enter the configured edit projection when editing is allowed."""

        self._begin_edit()

    def finishEdit(self) -> None:  # noqa: N802
        """Commit the active edit projection."""

        self._finish_edit()

    def cancelEdit(self) -> None:  # noqa: N802
        """Restore the value captured when editing began."""

        self._cancel_edit()

    def activateCopy(self) -> None:  # noqa: N802
        """Copy the canonical value, never the elided display projection."""

        self._copy_canonical()

    # ------------------------------------------------------------------
    # Projection hooks.
    # ------------------------------------------------------------------
    def _canonical_from_input(self, value: object) -> str:
        return str(value or "")

    def _split_canonical(self, canonical: str) -> tuple[str, str, str]:
        return "", str(canonical or ""), ""

    def _compose_canonical(
        self,
        prefix: str,
        core: str,
        suffix: str,
    ) -> str:
        return str(core or "")

    def _uses_locked_affix_projection(self) -> bool:
        return bool(self._locked_prefix or self._locked_suffix)

    def _expanded_editor_title(self) -> str:
        return "编辑完整内容"

    def _expanded_editor_hint(self) -> str:
        return "点击卡片外完成修改"

    # ------------------------------------------------------------------
    # Interaction lifecycle.
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if (
            getattr(self, "_editing", False)
            and watched
            in {self._editor_frame, self._prefix_label, self._suffix_label}
            and event.type()
            in {
                QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease,
                QEvent.MouseButtonDblClick,
            }
            and event.button() == Qt.LeftButton
        ):
            if event.type() != QEvent.MouseButtonRelease:
                self._place_editor_cursor(watched, event.position().toPoint())
            event.accept()
            return True
        if watched is getattr(self, "_editor", None) and getattr(self, "_editing", False):
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._cancel_edit()
                    return True
                if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
                    # Consume the editor key event after committing.  If it
                    # bubbles to the now-idle parent, the parent's accessible
                    # Enter-to-copy shortcut would schedule a false copy.
                    self._finish_edit()
                    return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self._editing:
            self._place_editor_cursor(self, event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self._editing:
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and not self._editing:
            self._on_display_clicked()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and not self._editing:
            self._on_display_double_clicked()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            not self._editing
            and event.key() == Qt.Key_C
            and bool(event.modifiers() & Qt.ControlModifier)
        ):
            self._copy_canonical()
            event.accept()
            return
        if not self._editing and event.key() == Qt.Key_F2 and self._editable:
            self._begin_edit()
            event.accept()
            return
        if not self._editing and event.key() in {Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space}:
            if self._activation is EditActivation.DIRECT_EDIT and self._editable:
                self._begin_edit()
            else:
                self._copy_canonical()
            event.accept()
            return
        if self._editing and event.key() == Qt.Key_Escape:
            self._cancel_edit()
            event.accept()
            return
        if self._editing and event.key() in {Qt.Key_Return, Qt.Key_Enter}:
            self._finish_edit()
            event.accept()
            return
        if self._editing and event.key() in {Qt.Key_Tab, Qt.Key_Backtab}:
            forward = event.key() == Qt.Key_Tab
            self._finish_edit()
            self.focusNextPrevChild(forward)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().focusInEvent(event)
        if (
            not self._editing
            and self._editable
            and self._activation is EditActivation.DIRECT_EDIT
        ):
            self._begin_edit()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._copy_feedback.cancel()
        if self._editing:
            self._request_finish_edit()
        super().hideEvent(event)

    def _on_display_clicked(self) -> None:
        if self._editing:
            return
        if self._activation is EditActivation.DIRECT_EDIT and self._editable:
            self._begin_edit()
            return
        self._copy_canonical()

    def _on_display_double_clicked(self) -> None:
        if self._editing:
            return
        self._copy_feedback.cancel()
        if self._editable:
            self._begin_edit()

    def _copy_canonical(self) -> None:
        copied_text = self._canonical_text
        QApplication.clipboard().setText(copied_text)
        if copied_text:
            if self._activation is EditActivation.COPY_ONLY or not self._editable:
                # A copy-only surface has no competing double-click edit, so
                # its semantic activation must remain immediate (timeline
                # nodes use this signal to record that the token was copied).
                self.copied.emit(copied_text)
            else:
                self._copy_feedback.schedule(copied_text)

    def _begin_edit(self) -> None:
        if not self._editable or self._editing:
            return
        self._copy_feedback.cancel()
        self._editing = True
        self._edit_snapshot = self._canonical_text
        prefix, core, suffix = self._split_canonical(self._canonical_text)
        self._locked_prefix = prefix
        self._locked_suffix = suffix
        self._sync_editor_affixes(prefix, suffix)
        self._editor.setReadOnly(False)
        blocked = self._editor.blockSignals(True)
        self._editor.setText(core)
        self._editor.blockSignals(blocked)
        self._sync_full_text_tooltip()
        if self._should_expand_editor(core):
            self._open_expanded_editor()
        else:
            self._stack.setCurrentWidget(self._editor_frame)
        self._dismissal_guard.start()
        # The blue editor frame is one interaction surface.  While its child
        # line edit owns focus, the outer compatibility widget must not steal
        # focus from clicks on locked affixes or frame padding.
        self.setFocusPolicy(Qt.NoFocus)
        self._apply_theme()
        self._editor.setFocus(Qt.MouseFocusReason)
        self._editor.selectAll()

    def _finish_edit(self) -> None:
        if not self._editing:
            return
        previous = self._canonical_text
        self._canonical_text = self._compose_canonical(
            self._locked_prefix,
            self._editor.text(),
            self._locked_suffix,
        )
        self._leave_edit_mode()
        if self._canonical_text != previous:
            self.textChanged.emit(self._canonical_text)
        self.editingFinished.emit()

    def _cancel_edit(self) -> None:
        if not self._editing:
            return
        previous = self._canonical_text
        self._canonical_text = self._edit_snapshot
        self._leave_edit_mode()
        if self._canonical_text != previous:
            self.textChanged.emit(self._canonical_text)
        self.editingFinished.emit()

    def _on_inner_text_changed(self, core: str) -> None:
        """Keep the canonical value live while the editor is active.

        Presenters historically subscribe to ``QLineEdit.textChanged`` and
        expect the current value during typing.  The display projection must
        therefore be separate from storage, but the edit projection must not
        delay the model update until focus leaves the row.
        """

        if not self._editing:
            return
        canonical = self._compose_canonical(
            self._locked_prefix,
            core,
            self._locked_suffix,
        )
        if canonical == self._canonical_text:
            return
        self._canonical_text = canonical
        self._update_expanded_preview()
        self.textChanged.emit(canonical)

    def _request_finish_edit(self) -> None:
        if not self._editing:
            return
        self._editor.clearFocus()
        if self._editing:
            self._finish_edit()

    def _leave_edit_mode(self) -> None:
        self._editing = False
        self._editor.setReadOnly(True)
        self._dismissal_guard.stop()
        self._close_expanded_editor()
        self.setFocusPolicy(Qt.StrongFocus)
        self._stack.setCurrentWidget(self._display)
        prefix, _core, suffix = self._split_canonical(self._canonical_text)
        self._locked_prefix = prefix
        self._locked_suffix = suffix
        self._refresh_display()
        self._sync_cursor()
        self._apply_theme()

    def _inline_editor_available_width(self) -> int:
        layout = self._editor_frame.layout()
        margins = layout.contentsMargins() if layout is not None else None
        margin_width = (
            margins.left() + margins.right()
            if margins is not None
            else 0
        )
        prefix_width = (
            self._prefix_label.sizeHint().width()
            if self._prefix_label.text()
            else 0
        )
        suffix_width = (
            self._suffix_label.sizeHint().width()
            if self._suffix_label.text()
            else 0
        )
        return max(0, self.width() - margin_width - prefix_width - suffix_width)

    def _should_expand_editor(self, core: str) -> bool:
        if not self._expand_editor_on_overflow:
            return False
        required = self._editor.fontMetrics().horizontalAdvance(str(core or ""))
        return required + 8 > self._inline_editor_available_width()

    def _open_expanded_editor(self) -> None:
        if self._expanded_editing:
            return
        self._expanded_editing = True
        self._stack.removeWidget(self._editor_frame)
        self._editor_frame.setParent(self._expanded_surface)
        self._expanded_content_layout.insertWidget(1, self._editor_frame)
        self._editor_frame.show()
        # The full frozen structure remains visible in the live preview below;
        # the wide editor can therefore dedicate its entire width to the only
        # part the user is allowed to rename.
        self._prefix_label.hide()
        self._suffix_label.hide()
        self._update_expanded_preview()
        self._resize_and_position_expanded_popup()
        self._expanded_popup.show()
        self._expanded_popup.raise_()
        # Qt applies a conservative native top-level size before the popup's
        # first layout pass.  Settle once after show so the window shrinks to
        # the wrapped content instead of distributing stale extra height into
        # the title and hint rows.
        defer_qt_method(self, "_settle_expanded_popup_geometry")

    def _close_expanded_editor(self) -> None:
        if not self._expanded_editing:
            return
        self._expanded_content_layout.removeWidget(self._editor_frame)
        self._editor_frame.setParent(self)
        self._stack.addWidget(self._editor_frame)
        self._expanded_popup.hide()
        self._expanded_editing = False
        self._sync_editor_affixes(self._locked_prefix, self._locked_suffix)

    def _update_expanded_preview(self) -> None:
        if not self._expanded_editing:
            return
        canonical = self._compose_canonical(
            self._locked_prefix,
            self._editor.text(),
            self._locked_suffix,
        )
        caption = "完整内容："
        self._expanded_preview_core_start = len(caption) + len(self._locked_prefix)
        self._expanded_preview_core_end = (
            self._expanded_preview_core_start + len(self._editor.text())
        )
        self._expanded_preview.setText(f"{caption}{canonical}")
        self._expanded_preview.setAccessibleName(canonical)
        self._expanded_popup.adjustSize()
        if self._expanded_popup.isVisible():
            self._resize_and_position_expanded_popup()

    def _settle_expanded_popup_geometry(self) -> None:
        if not self._expanded_editing or not self._expanded_popup.isVisible():
            return
        self._expanded_popup.adjustSize()
        self._resize_and_position_expanded_popup()

    def _resize_and_position_expanded_popup(self) -> None:
        anchor_top_left = self.mapToGlobal(self.rect().topLeft())
        anchor_bottom_right = self.mapToGlobal(self.rect().bottomRight())
        anchor = QRect(anchor_top_left, anchor_bottom_right)
        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)
        maximum = max(1, bounds.width() - EXPANDED_EDITOR_SCREEN_MARGIN * 2)
        natural = self._editor.fontMetrics().horizontalAdvance(self._editor.text()) + 48
        popup_width = min(
            maximum,
            max(self.width(), EXPANDED_EDITOR_MIN_WIDTH, min(natural, EXPANDED_EDITOR_MAX_WIDTH)),
        )
        self._expanded_popup.setFixedWidth(popup_width)
        self._expanded_popup.adjustSize()
        popup_height = self._expanded_popup.height()
        x = min(
            max(anchor.left(), bounds.left() + EXPANDED_EDITOR_SCREEN_MARGIN),
            bounds.right() - popup_width - EXPANDED_EDITOR_SCREEN_MARGIN + 1,
        )
        below = anchor.bottom() + EXPANDED_EDITOR_GAP
        above = anchor.top() - popup_height - EXPANDED_EDITOR_GAP
        if below + popup_height <= bounds.bottom() - EXPANDED_EDITOR_SCREEN_MARGIN + 1:
            y = below
        else:
            y = max(bounds.top() + EXPANDED_EDITOR_SCREEN_MARGIN, above)
        self._expanded_popup.move(QPoint(x, y))

    def _sync_editor_affixes(self, prefix: str, suffix: str) -> None:
        self._prefix_label.setText(prefix)
        self._suffix_label.setText(suffix)
        self._prefix_label.setVisible(bool(prefix) and not self._expanded_editing)
        self._suffix_label.setVisible(bool(suffix) and not self._expanded_editing)

    def _on_expanded_preview_position(self, document_position: int) -> None:
        """Map a click in the complete token preview into its editable core."""

        if not self._editing or not self._expanded_editing:
            return
        core_length = len(self._editor.text())
        if document_position <= self._expanded_preview_core_start:
            cursor_position = 0
        elif document_position >= self._expanded_preview_core_end:
            cursor_position = core_length
        else:
            cursor_position = document_position - self._expanded_preview_core_start
        self._editor.setFocus(Qt.MouseFocusReason)
        self._editor.setCursorPosition(cursor_position)
        self._editor.deselect()

    def _on_expanded_preview_height_changed(self) -> None:
        if not self._expanded_editing:
            return
        self._expanded_popup.adjustSize()
        if self._expanded_popup.isVisible():
            self._resize_and_position_expanded_popup()

    def _place_editor_cursor(self, source: QWidget, source_point) -> None:
        """Keep composite-editor clicks inside the active edit session."""

        if not self._editing:
            return
        if source is self._prefix_label:
            cursor_position = 0
        elif source is self._suffix_label:
            cursor_position = len(self._editor.text())
        else:
            # The expanded editor is reparented into a separate top-level
            # popup, so neither widget is guaranteed to share ``self`` as an
            # ancestor.  Global coordinates keep this mapping valid on the
            # native Windows/DPI path as well as in the inline projection.
            click_global = source.mapToGlobal(source_point)
            click_in_editor = self._editor.mapFromGlobal(click_global)
            if click_in_editor.x() <= 0:
                cursor_position = 0
            elif click_in_editor.x() >= self._editor.width():
                cursor_position = len(self._editor.text())
            else:
                cursor_position = self._editor.cursorPositionAt(click_in_editor)
        self._editor.setFocus(Qt.MouseFocusReason)
        self._editor.setCursorPosition(cursor_position)
        self._editor.deselect()

    def _refresh_display(self) -> None:
        prefix, core, suffix = self._split_canonical(self._canonical_text)
        self._locked_prefix = prefix
        self._locked_suffix = suffix
        if self._canonical_text:
            if prefix or suffix:
                self._display.setTokenParts(
                    prefix,
                    core,
                    suffix,
                    canonical=self._canonical_text,
                )
            else:
                self._display.setElideMode(self._elide_mode)
                self._display.setText(self._canonical_text)
        else:
            self._display.setElideMode(TextElideMode.RIGHT)
            self._display.setText(self._placeholder_text)
        self._sync_full_text_tooltip()
        self._apply_theme()

    def _sync_full_text_tooltip(self, *_args) -> None:
        tooltip = (
            self._canonical_text
            if (
                self._show_full_text_tooltip
                and not self._editing
                and self._canonical_text
                and self._display.isElided()
            )
            else ""
        )
        for target in (self, self._display):
            set_global_tooltip(
                target,
                tooltip,
                placement="top",
                role="content",
                delay_ms=FULL_TEXT_TOOLTIP_DELAY_MS,
            )

    def _sync_cursor(self) -> None:
        cursor = (
            Qt.IBeamCursor
            if self._activation is EditActivation.DIRECT_EDIT and self._editable
            else Qt.PointingHandCursor
        )
        self._display.setCursor(cursor)

    # ------------------------------------------------------------------
    # Theme projection.
    # ------------------------------------------------------------------
    def _display_text_color(self, theme) -> str:
        return theme.text_hint if not self._canonical_text else theme.text_primary

    def _apply_theme(self) -> None:
        if not hasattr(self, "_display"):
            return
        theme = get_theme()
        editor_layout = self._editor_frame.layout()
        if editor_layout is not None:
            editor_layout.setContentsMargins(theme.input_padding_x, 0, theme.input_padding_x, 0)
        display_color = self._display_text_color(theme)
        weight = (
            ""
            if self._font_weight is None
            else f"font-weight: {int(self._font_weight)};"
        )
        if self._surface is TextSurface.FRAMED:
            display_style = build_text_input_stylesheet(
                theme,
                selector="QLabel",
                focus_border_color=theme.border,
            )
            display_style += f"\nQLabel {{ color: {display_color}; {weight} }}"
        else:
            display_style = (
                "QLabel { "
                f"color: {display_color}; padding: 0 6px; {weight} }}"
            )
        self._display.setStyleSheet(display_style)

        self._editor_frame.setStyleSheet(
            build_text_input_stylesheet(
                theme,
                selector="QFrame#projected_text_editor_frame",
                background=theme.bg_input,
                focus_border_color=theme.border_focus,
                padding_x=0,
                padding_y=0,
            )
            + f"\nQFrame#projected_text_editor_frame {{ border-color: {theme.border_focus}; }}"
        )
        inner_style = build_input_editor_stylesheet(theme, padding="0")
        self._editor.setStyleSheet(inner_style)
        affix_style = (
            "QLabel { padding: 0; "
            f"color: {theme.text_primary}; {weight} }}"
        )
        self._prefix_label.setStyleSheet(affix_style)
        self._suffix_label.setStyleSheet(affix_style)
        self._expanded_surface.configure_surface(
            background=theme.bg_card,
            radius=theme.radius_md,
            border_color=theme.border,
            border_width=1,
        )
        self._expanded_title.setStyleSheet(
            f"color: {theme.text_primary}; font-weight: {theme.font_weight_emphasis};"
        )
        self._expanded_preview.setStyleSheet(
            _expanded_preview_stylesheet(theme)
        )
        self._expanded_hint.setStyleSheet(
            f"color: {theme.text_hint}; font-size: {theme.font_size_sm}px;"
        )


__all__ = [
    "EditActivation",
    "ProjectedTextEdit",
    "TextSurface",
]
