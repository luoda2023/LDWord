from __future__ import annotations

from src.qt_api import QLayout, QLayoutItem, QPoint, QRect, QSize


class FlowLayout(QLayout):
    """A small wrapping layout for chips, swatches, and inline option groups."""

    def __init__(self, parent=None, h_spacing: int = 14, v_spacing: int = 14):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = int(h_spacing)
        self._v_spacing = int(v_spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        right_edge = rect.x() + rect.width()

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._h_spacing

            if next_x - self._h_spacing > right_edge and line_height > 0:
                x = rect.x()
                y += line_height + self._v_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x += item_size.width() + self._h_spacing
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y()


__all__ = ["FlowLayout"]
