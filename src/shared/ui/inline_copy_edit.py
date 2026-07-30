"""Shared click-to-copy and double-click-to-edit line edit behavior."""

from __future__ import annotations

from collections.abc import Callable

from src.qt_api import (
    QApplication,
    QEvent,
    QLineEdit,
    QObject,
    QTimer,
    Qt,
    QWidget,
    Signal,
)


class ConfirmedCopyEmitter(QObject):
    """Emit copy feedback only after the double-click window has elapsed."""

    def __init__(self, emit: Callable[[str], object], parent=None) -> None:
        super().__init__(parent)
        self._emit = emit
        self._pending_text = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._emit_pending)

    def schedule(self, text: object) -> None:
        self._pending_text = str(text or "")
        if not self._pending_text:
            self.cancel()
            return
        app = QApplication.instance()
        interval = app.doubleClickInterval() if app is not None else 400
        self._timer.start(max(1, int(interval)))

    def cancel(self) -> None:
        self._timer.stop()
        self._pending_text = ""

    def _emit_pending(self) -> None:
        copied_text = self._pending_text
        self._pending_text = ""
        if copied_text:
            self._emit(copied_text)


class InlineEditDismissalGuard(QObject):
    """Finish an edit session on outside clicks or window deactivation."""

    def __init__(
        self,
        root: QWidget,
        finish: Callable[[], object],
        parent=None,
    ) -> None:
        super().__init__(parent or root)
        self._root = root
        self._finish = finish
        self._installed = False
        self._additional_roots: list[QWidget] = []

    def add_inside_root(self, widget: QWidget) -> None:
        """Treat a related top-level popup as part of the edit session."""

        if widget not in self._additional_roots:
            self._additional_roots.append(widget)

    def start(self) -> None:
        if self._installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._installed = True

    def stop(self) -> None:
        if not self._installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._installed = False

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        try:
            self._root.objectName()
        except RuntimeError:
            self._installed = False
            return False
        event_type = event.type()
        if event_type == QEvent.MouseButtonPress:
            roots = (self._root, *self._additional_roots)
            inside_editor = isinstance(watched, QWidget) and any(
                watched is root or root.isAncestorOf(watched)
                for root in roots
            )
            if not inside_editor:
                self._finish()
        elif event_type in {
            QEvent.ApplicationDeactivate,
            QEvent.WindowDeactivate,
        }:
            self._finish()
        return super().eventFilter(watched, event)


class InlineCopyEdit(QLineEdit):
    """Read-only text surface that enters inline editing on double-click.

    The interaction contract intentionally lives below material-specific
    styling so tokens and display names cannot drift apart:

    * single left-click copies the exact displayed text;
    * double left-click enters editing when enabled;
    * Escape restores the value captured before editing;
    * editing completion returns to the read-only display state.
    """

    copied = Signal(str)

    def __init__(
        self,
        text: object = "",
        parent=None,
        *,
        editable: bool = True,
    ) -> None:
        super().__init__(str(text or ""), parent)
        self._inline_editable = bool(editable)
        self._editing_inline = False
        self._text_before_edit = self.text()
        self._copy_feedback = ConfirmedCopyEmitter(self.copied.emit, self)
        self._dismissal_guard = InlineEditDismissalGuard(
            self,
            self._request_finish_inline_edit,
            self,
        )
        self.setReadOnly(True)
        self.setCursor(Qt.PointingHandCursor)
        self.editingFinished.connect(self._finish_inline_edit)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        should_copy = event.button() == Qt.LeftButton and not self._editing_inline
        super().mouseReleaseEvent(event)
        if should_copy:
            copied_text = self.text()
            QApplication.clipboard().setText(copied_text)
            if copied_text:
                # The clipboard can update immediately, but visual feedback is
                # deferred until Qt's double-click window closes.  A real
                # double-click starts with one release; emitting here would
                # show a false "copied" toast immediately before rename mode.
                self._copy_feedback.schedule(copied_text)
            self.deselect()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() != Qt.LeftButton or not self._inline_editable:
            super().mouseDoubleClickEvent(event)
            return
        self._copy_feedback.cancel()
        self._editing_inline = True
        self._text_before_edit = self.text()
        self.setReadOnly(False)
        self.setCursor(Qt.IBeamCursor)
        self._dismissal_guard.start()
        self._apply_interaction_style()
        super().mouseDoubleClickEvent(event)
        self.selectAll()

    def focusOutEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._editing_inline:
            super().focusOutEvent(event)
            return
        # QLineEdit does not guarantee an editingFinished emission for every
        # programmatic/non-focusable outside-click path.  Suppress its implicit
        # signal here and publish exactly one deterministic completion event.
        blocked = self.blockSignals(True)
        super().focusOutEvent(event)
        self.blockSignals(blocked)
        self._leave_inline_edit()
        self.editingFinished.emit()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._copy_feedback.cancel()
        if self._editing_inline:
            self._request_finish_inline_edit()
        super().hideEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._editing_inline and event.key() == Qt.Key_Escape:
            self.setText(self._text_before_edit)
            self._leave_inline_edit()
            self.clearFocus()
            return
        super().keyPressEvent(event)

    def isInlineEditable(self) -> bool:  # noqa: N802
        return self._inline_editable

    def isInlineEditing(self) -> bool:  # noqa: N802
        return self._editing_inline

    def _finish_inline_edit(self) -> None:
        if self._editing_inline:
            self._leave_inline_edit()

    def _request_finish_inline_edit(self) -> None:
        """Finish editing even when the clicked target cannot accept focus."""

        if not self._editing_inline:
            return
        self.clearFocus()
        if self._editing_inline:
            # Defensive fallback for a hidden/non-focused editor: preserve the
            # same public completion signal that presenters already consume.
            self._leave_inline_edit()
            self.editingFinished.emit()

    def _leave_inline_edit(self) -> None:
        self._editing_inline = False
        self.setReadOnly(True)
        self.setCursor(Qt.PointingHandCursor)
        self.deselect()
        self._dismissal_guard.stop()
        self._apply_interaction_style()

    def _apply_interaction_style(self) -> None:
        """Hook for subclasses whose appearance depends on edit state."""


__all__ = [
    "ConfirmedCopyEmitter",
    "InlineCopyEdit",
    "InlineEditDismissalGuard",
]
