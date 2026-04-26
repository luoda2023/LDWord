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
        content_heights = [
            t.form_row_height,
            self._label.sizeHint().height(),
            self._widget.sizeHint().height(),
            self._widget.minimumSizeHint().height(),
        ]
        if self._suffix is not None:
            content_heights.append(self._suffix.sizeHint().height())
            content_heights.append(self._suffix.minimumSizeHint().height())
        margins = self._layout.contentsMargins()
        self._label.setFixedWidth(self._label_width or t.form_row_label_width)
        self.setMinimumHeight(max(content_heights) + margins.top() + margins.bottom())
        self._label.setStyleSheet(f'font-size: {t.font_size_md}px; color: {t.text_primary};')
        self.updateGeometry()

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
