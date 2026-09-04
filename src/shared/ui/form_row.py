"""
Standard form row widget.
"""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QSizePolicy, QWidget, Qt

from src.shared.ui.theme import bind_theme, get_theme


class FormRow(QWidget):
    """Label + control + optional suffix row."""

    def __init__(
        self,
        label: str,
        widget: QWidget,
        *,
        suffix_widget: QWidget | None = None,
        label_width: int | None = None,
        label_alignment=None,
        parent=None,
    ):
        super().__init__(parent)
        self._label_width = label_width
        self._label_alignment = label_alignment or (Qt.AlignRight | Qt.AlignVCenter)
        self._minimum_row_height: int | None = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 2, 0, 2)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._label = QLabel(label)
        self._label.setAlignment(self._label_alignment)
        self._layout.addWidget(self._label)

        self._widget = widget
        widget_policy = widget.sizePolicy()
        widget_policy.setHorizontalPolicy(QSizePolicy.Expanding)
        if widget_policy.verticalPolicy() == QSizePolicy.Fixed:
            widget_policy.setVerticalPolicy(QSizePolicy.Preferred)
        widget.setSizePolicy(widget_policy)
        self._layout.addWidget(widget, 1)

        self._suffix = suffix_widget
        if suffix_widget:
            self._layout.addWidget(suffix_widget)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setFixedWidth(self._label_width or t.form_row_label_width)
        row_height = self._row_height_for_width(self.width() if self.width() > 0 else None)
        self.setMinimumHeight(row_height)
        self._label.setStyleSheet(f'font-size: {t.font_size_md}px; color: {t.text_primary};')
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API contract
        return bool(self._widget.hasHeightForWidth())

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API contract
        return self._row_height_for_width(max(0, int(width or 0)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.hasHeightForWidth():
            self.setMinimumHeight(self.heightForWidth(self.width()))

    def _row_height_for_width(self, width: int | None) -> int:
        t = get_theme()
        margins = self._layout.contentsMargins()
        content_heights = [
            t.form_row_height,
            self._label.sizeHint().height(),
        ]
        if width is not None and self._widget.hasHeightForWidth():
            content_heights.append(
                self._bounded_height(
                    self._widget,
                    self._widget.heightForWidth(
                        self._available_widget_width(width)
                    ),
                )
            )
        else:
            content_heights.append(
                self._bounded_height(self._widget, self._widget.sizeHint().height())
            )
            content_heights.append(
                self._bounded_height(
                    self._widget,
                    self._widget.minimumSizeHint().height(),
                )
            )
        if self._suffix is not None:
            content_heights.append(
                self._bounded_height(self._suffix, self._suffix.sizeHint().height())
            )
            content_heights.append(
                self._bounded_height(
                    self._suffix,
                    self._suffix.minimumSizeHint().height(),
                )
            )
        row_height = max(content_heights) + margins.top() + margins.bottom()
        if self._minimum_row_height is not None:
            row_height = max(row_height, self._minimum_row_height)
        return row_height

    @staticmethod
    def _bounded_height(widget: QWidget, height: int) -> int:
        """Match the height that Qt's layout can actually assign to a child."""

        return max(
            widget.minimumHeight(),
            min(max(0, int(height)), widget.maximumHeight()),
        )

    def _available_widget_width(self, width: int) -> int:
        margins = self._layout.contentsMargins()
        available = max(0, int(width or 0) - margins.left() - margins.right())
        available -= self._label.width() if self._label.width() > 0 else self._label.sizeHint().width()
        available -= self._layout.spacing()
        if self._suffix is not None:
            available -= self._suffix.sizeHint().width()
            available -= self._layout.spacing()
        return max(0, available)

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def label_text(self) -> str:
        return self._label.text()

    def preferred_label_width(self) -> int:
        return self._label.fontMetrics().horizontalAdvance(self._label.text())

    @property
    def label_width(self) -> int | None:
        return self._label_width

    def set_label(self, text: str) -> None:
        self._label.setText(text)

    def set_label_alignment(self, alignment) -> None:
        self._label_alignment = alignment
        self._label.setAlignment(alignment)

    def set_label_width(self, width: int | None) -> None:
        self._label_width = width
        self._apply_theme()

    def set_minimum_row_height(self, height: int | None) -> None:
        self._minimum_row_height = None if height is None else max(0, int(height))
        self._apply_theme()
