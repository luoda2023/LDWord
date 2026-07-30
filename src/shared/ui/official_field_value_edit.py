"""Compact value editor used by official-material table rows."""

from __future__ import annotations

from src.qt_api import (
    QApplication,
    QEvent,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inline_copy_edit import (
    ConfirmedCopyEmitter,
    InlineEditDismissalGuard,
)
from src.shared.ui.projected_text_edit import (
    EditActivation,
    ProjectedTextEdit,
    TextSurface,
)
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.text_projection import TextElideMode
from src.shared.ui.theme import bind_theme, get_theme


class _AutoGrowTextEdit(QTextEdit):
    """Stay table-row compact and expand only while editing long text."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._collapsed_height = resolved_control_height(get_theme(), "md")
        self._expanded_height = 112
        self.setFixedHeight(self._collapsed_height)
        self.setAcceptRichText(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _set_editor_height(self, height: int) -> None:
        self.setFixedHeight(height)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()

    def focusInEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self.isReadOnly():
            self._set_editor_height(self._expanded_height)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._set_editor_height(self._collapsed_height)
        super().focusOutEvent(event)


class OfficialFieldValueEdit(QWidget):
    """One value surface with a QLineEdit-compatible public API."""

    textChanged = Signal(str)
    copied = Signal(str)

    def __init__(
        self,
        *,
        editor_kind: str = "single_line",
        read_only: bool = False,
        click_copy_double_edit: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editor_kind = str(editor_kind or "single_line")
        self._click_copy_double_edit = bool(click_copy_double_edit)
        self._permanently_read_only = bool(read_only)
        self._editing_from_double_click = False
        self._text_before_double_click = ""
        self._copy_feedback = ConfirmedCopyEmitter(self.copied.emit, self)
        self._dismissal_guard = InlineEditDismissalGuard(
            self,
            self._request_finish_double_click_edit,
            self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._projected: ProjectedTextEdit | None = None
        if self._editor_kind == "multiline":
            editor = _AutoGrowTextEdit(self)
            editor.textChanged.connect(self._emit_text_changed)
            surface: QWidget = editor
        else:
            projected = ProjectedTextEdit(
                "",
                self,
                editable=not read_only,
                activation=(
                    EditActivation.COPY_DOUBLE_EDIT
                    if self._click_copy_double_edit
                    else EditActivation.DIRECT_EDIT
                ),
                surface=TextSurface.FRAMED,
                elide_mode=TextElideMode.RIGHT,
            )
            self._projected = projected
            editor = projected.innerEditor()
            surface = projected
            projected.textChanged.connect(self.textChanged.emit)
            projected.copied.connect(self.copied.emit)
        self._editor = editor
        self._surface = surface
        self._interaction_targets = (
            (self._editor, self._editor.viewport())
            if isinstance(self._editor, QTextEdit)
            else (self._editor,)
        )
        if self._projected is not None:
            # Retain compatibility for callers that historically targeted the
            # nested QLineEdit in tests or automation.  The visible UI targets
            # the projected display surface instead.
            self._editor.installEventFilter(self)
        elif self._click_copy_double_edit:
            for target in self._interaction_targets:
                target.installEventFilter(self)
            if isinstance(self._editor, QLineEdit):
                self._editor.editingFinished.connect(self._finish_double_click_edit)
        self._editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._surface)
        control_height = resolved_control_height(get_theme(), "md")
        self.setMinimumHeight(control_height)
        if self._projected is not None:
            # Preserve the historical native-editor geometry contract used by
            # automation while the projected surface owns idle rendering.
            self._editor.setFixedHeight(control_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setReadOnly(read_only)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _emit_text_changed(self) -> None:
        self.textChanged.emit(self.text())

    def text(self) -> str:
        if self._projected is not None:
            return self._projected.text()
        if isinstance(self._editor, QTextEdit):
            return self._editor.toPlainText()
        return self._editor.text()

    def setText(self, value: object) -> None:  # noqa: N802 - compatibility API
        text = str(value or "")
        if self._projected is not None:
            self._projected.setText(text)
            return
        if isinstance(self._editor, QTextEdit):
            self._editor.setPlainText(text)
        else:
            self._editor.setText(text)

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        if self._projected is not None:
            self._projected.setPlaceholderText(text)
        else:
            self._editor.setPlaceholderText(str(text or ""))

    def displayText(self) -> str:  # noqa: N802
        if self._projected is not None:
            return self._projected.displayText()
        return self.text()

    def displaySurface(self):  # noqa: N802
        """Return the idle projection surface for single-line values."""

        if self._projected is None:
            return None
        return self._projected.displaySurface()

    def innerEditor(self):  # noqa: N802
        """Return the native editor retained by the compatibility adapter."""

        return self._editor

    def setReadOnly(self, read_only: bool) -> None:  # noqa: N802
        if self._projected is not None:
            self._permanently_read_only = bool(read_only)
            self._projected.setReadOnly(read_only)
            self.setProperty("readOnly", self._projected.isReadOnly())
            self._apply_theme()
            return
        if read_only and self._editing_from_double_click:
            self._finish_double_click_edit()
        self._permanently_read_only = bool(read_only)
        effective_read_only = bool(read_only) or (
            self._click_copy_double_edit and not self._editing_from_double_click
        )
        self._editor.setReadOnly(effective_read_only)
        self.setProperty("readOnly", effective_read_only)
        self._apply_theme()

    def isReadOnly(self) -> bool:  # noqa: N802
        if self._projected is not None:
            return self._projected.isReadOnly()
        return bool(self._editor.isReadOnly())

    def hasFocus(self) -> bool:  # noqa: N802
        if self._projected is not None:
            return self._projected.hasFocus()
        return bool(self._editor.hasFocus() or super().hasFocus())

    def setFocus(self, reason=None) -> None:  # noqa: N802
        if self._projected is not None:
            self._projected.setFocus(reason)
            return
        if reason is None:
            self._editor.setFocus()
        else:
            self._editor.setFocus(reason)

    def setToolTip(self, text: str) -> None:  # noqa: N802
        super().setToolTip(text)
        if self._projected is not None:
            self._projected.setToolTip(text)
        self._editor.setToolTip(text)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if self._projected is not None and watched is self._editor:
            event_type = event.type()
            if (
                event_type == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton
                and not self._projected.isInlineEditing()
            ):
                self._projected.activateCopy()
            elif (
                event_type == QEvent.MouseButtonDblClick
                and event.button() == Qt.LeftButton
            ):
                self._copy_feedback.cancel()
                self._projected.beginEdit()
                return True
            elif (
                event_type == QEvent.KeyPress
                and event.key() == Qt.Key_Escape
                and self._projected.isInlineEditing()
            ):
                self._projected.cancelEdit()
                return True
            return super().eventFilter(watched, event)
        if watched in self._interaction_targets and self._click_copy_double_edit:
            event_type = event.type()
            if (
                event_type == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton
                and not self._editing_from_double_click
            ):
                copied_text = self.text()
                QApplication.clipboard().setText(copied_text)
                if copied_text:
                    self._copy_feedback.schedule(copied_text)
            elif (
                event_type == QEvent.MouseButtonDblClick
                and event.button() == Qt.LeftButton
                and not self._permanently_read_only
            ):
                self._copy_feedback.cancel()
                self._begin_double_click_edit()
                return True
            elif (
                event_type == QEvent.KeyPress
                and event.key() == Qt.Key_Escape
                and self._editing_from_double_click
            ):
                self.setText(self._text_before_double_click)
                self._request_finish_double_click_edit()
                return True
            elif event_type == QEvent.FocusOut and self._editing_from_double_click:
                QTimer.singleShot(0, self._finish_double_click_edit)
        return super().eventFilter(watched, event)

    def _begin_double_click_edit(self) -> None:
        if self._projected is not None:
            self._projected.beginEdit()
            return
        self._editing_from_double_click = True
        self._text_before_double_click = self.text()
        self._editor.setReadOnly(False)
        self.setProperty("readOnly", False)
        self._dismissal_guard.start()
        self._apply_theme()
        self._editor.setFocus()
        self._editor.selectAll()

    def _finish_double_click_edit(self) -> None:
        if self._projected is not None:
            self._projected.finishEdit()
            return
        if not self._editing_from_double_click:
            return
        self._editing_from_double_click = False
        self._editor.setReadOnly(True)
        self.setProperty("readOnly", True)
        self._dismissal_guard.stop()
        self._apply_theme()

    def _request_finish_double_click_edit(self) -> None:
        if self._projected is not None:
            self._projected.clearFocus()
            self._projected.finishEdit()
            return
        if not self._editing_from_double_click:
            return
        self._editor.clearFocus()
        if self._editing_from_double_click:
            self._finish_double_click_edit()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._copy_feedback.cancel()
        self._request_finish_double_click_edit()
        super().hideEvent(event)

    def isEditing(self) -> bool:  # noqa: N802 - compatibility API
        if self._projected is not None:
            return self._projected.isInlineEditing()
        return bool(self._editing_from_double_click)

    def _apply_theme(self) -> None:
        if not hasattr(self, "_editor"):
            return
        if self._projected is not None:
            return
        theme = get_theme()
        read_only = self._permanently_read_only
        selector = "QTextEdit" if isinstance(self._editor, QTextEdit) else "QLineEdit"
        background = theme.bg_hover if read_only else theme.bg_input
        self._editor.setStyleSheet(
            build_text_input_stylesheet(
                theme,
                selector=selector,
                background=background,
                focus_border_color=theme.border if read_only else theme.border_focus,
                padding_y=5 if isinstance(self._editor, QTextEdit) else None,
            )
        )


__all__ = ["OfficialFieldValueEdit"]
