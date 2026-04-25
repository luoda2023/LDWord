"""Anchored in-window popup panel used by StyledComboBox."""

from __future__ import annotations

from src.qt_api import (
    QAbstractItemView,
    QEvent,
    QFrame,
    QObject,
    QRect,
    QVBoxLayout,
    QWidget,
    Signal,
    Qt,
)


class ComboPopupPanel(QWidget):
    """Full-window transparent overlay that hosts a single combo popup surface."""

    item_activated = Signal(int)
    dismissed = Signal()

    def __init__(self, combo, view, *, object_name: str, surface_name: str):
        super().__init__(combo.window())
        self._combo = combo
        self._view = view
        self._installed_filter = False

        self.setObjectName(object_name)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        self._surface = QFrame(self)
        self._surface.setObjectName(surface_name)
        self._surface.setAttribute(Qt.WA_StyledBackground, True)

        self._surface_layout = QVBoxLayout(self._surface)
        self._surface_layout.setContentsMargins(0, 0, 0, 0)
        self._surface_layout.setSpacing(0)

        view.setParent(self._surface)
        self._surface_layout.addWidget(view)
        self._view.clicked.connect(self._on_view_clicked)

    def surface(self) -> QFrame:
        return self._surface

    def open_for_combo(self, geometry: QRect) -> None:
        root = self._combo.window()
        if self.parentWidget() is not root:
            self.setParent(root)

        self.setGeometry(root.rect())
        self._surface.setGeometry(geometry)
        self.show()
        self.raise_()
        self._surface.raise_()
        self._install_filter()
        self._sync_current_index()
        self._view.setFocus(Qt.PopupFocusReason)

    def close_panel(self) -> None:
        if not self.isVisible():
            return
        self.hide()
        self._remove_filter()
        # Return focus to the originating combo so it doesn't jump
        # to the next widget in the tab order.  Use OtherFocusReason
        # (not PopupFocusReason) to avoid Qt's default QComboBox
        # behaviour of selecting all text in the lineEdit on focus-in.
        self._combo.setFocus(Qt.OtherFocusReason)
        # For editable combos, clear any text selection so the closed
        # combo doesn't show highlighted text.
        line_edit = self._combo.lineEdit()
        if line_edit is not None:
            line_edit.deselect()
        self.dismissed.emit()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not self.isVisible():
            return False

        event_type = event.type()
        root = self._combo.window()

        if obj in (self._combo, root) and event_type in (QEvent.Move, QEvent.Resize, QEvent.Show):
            self.reposition()

        if obj in (self._combo, root) and event_type in (QEvent.Hide, QEvent.Close):
            self.close_panel()

        if obj is root and event_type == QEvent.WindowDeactivate:
            self.close_panel()

        if event_type == QEvent.KeyPress and hasattr(event, "key"):
            key = event.key()
            if key == Qt.Key_Escape:
                self.close_panel()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter) and self._owns_object(obj):
                index = self._view.currentIndex()
                if index.isValid():
                    self.item_activated.emit(index.row())
                    return True

        return False

    def reposition(self) -> None:
        if not self.isVisible():
            return
        root = self._combo.window()
        self.setGeometry(root.rect())
        self._surface.setGeometry(self._combo._popup_geometry_in_window())

    def mousePressEvent(self, event) -> None:
        if not self._surface.geometry().contains(event.pos()):
            self.close_panel()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        if not self._surface.geometry().contains(event.position().toPoint()):
            event.ignore()
            return
        super().wheelEvent(event)

    def _sync_current_index(self) -> None:
        current = self._combo.currentIndex()
        if 0 <= current < self._combo.count():
            model_index = self._view.model().index(current, 0)
            self._view.setCurrentIndex(model_index)
            self._view.scrollTo(model_index, QAbstractItemView.PositionAtCenter)

    def _install_filter(self) -> None:
        root = self._combo.window()
        if root is not None and not self._installed_filter:
            root.installEventFilter(self)
            self._combo.installEventFilter(self)
            self._installed_filter = True

    def _remove_filter(self) -> None:
        root = self._combo.window()
        if self._installed_filter:
            if root is not None:
                root.removeEventFilter(self)
            self._combo.removeEventFilter(self)
            self._installed_filter = False

    def _on_view_clicked(self, index) -> None:
        if index.isValid():
            self.item_activated.emit(index.row())

    def _owns_object(self, obj: QObject | None) -> bool:
        owned = {
            self,
            self._surface,
            self._view,
            self._view.viewport(),
            self._view.verticalScrollBar(),
            self._view.horizontalScrollBar(),
            self._combo,
            self._combo.lineEdit(),
        }
        current = obj
        while current is not None:
            if current in owned:
                return True
            parent = current.parent() if hasattr(current, "parent") else None
            current = parent
        return False
