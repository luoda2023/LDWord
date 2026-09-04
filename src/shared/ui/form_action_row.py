"""Wrapping action-button row for form fields."""

from __future__ import annotations

from src.qt_api import QPushButton, QSize, QSizePolicy, QWidget, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.sizing import SizeClass, apply_size_class
from src.shared.ui.theme import bind_theme, get_theme


class FormActionButtonRow(QWidget):
    """A form control that keeps action buttons visible and wraps when narrow."""

    def __init__(
        self,
        parent=None,
        *,
        size_class: SizeClass = "md",
        h_spacing: int = 8,
        v_spacing: int = 8,
    ) -> None:
        super().__init__(parent)
        self._size_class = size_class
        self._h_spacing = int(h_spacing)
        self._buttons: list[QPushButton] = []
        self._variants: dict[QPushButton, str] = {}
        self._layout = FlowLayout(self, h_spacing=h_spacing, v_spacing=v_spacing)
        self._layout.setAlignment(Qt.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        bind_theme(self, self.apply_theme)
        self.apply_theme()

    def add_button(self, text: str, variant: str = "secondary") -> QPushButton:
        button = QPushButton(text, self)
        button.setCursor(Qt.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._buttons.append(button)
        self._variants[button] = variant
        self._layout.addWidget(button)
        self._apply_button_theme(button)
        self._sync_height()
        return button

    def buttons(self) -> tuple[QPushButton, ...]:
        return tuple(self._buttons)

    def apply_theme(self) -> None:
        for button in self._buttons:
            self._apply_button_theme(button)
        self._sync_height()
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API contract
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API contract
        return max(0, self._layout.heightForWidth(max(0, int(width or 0))))

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        width = self._preferred_one_line_width()
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        width = max((button.minimumSizeHint().width() for button in self._buttons), default=0)
        return QSize(width, self.heightForWidth(width))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_height()

    def _apply_button_theme(self, button: QPushButton) -> None:
        theme = get_theme()
        button.setStyleSheet(build_button_stylesheet(theme))
        apply_button_variant(button, self._variants.get(button, "secondary"))
        apply_size_class(button, self._size_class)
        button.ensurePolished()
        button.setMinimumWidth(max(button.minimumSizeHint().width(), button.sizeHint().width()))

    def _preferred_one_line_width(self) -> int:
        if not self._buttons:
            return 0
        width = sum(button.sizeHint().width() for button in self._buttons)
        width += self._h_spacing * max(0, len(self._buttons) - 1)
        return width

    def _sync_height(self) -> None:
        width = self.width() if self.width() > 0 else self._preferred_one_line_width()
        height = self.heightForWidth(width)
        if height > 0 and self.minimumHeight() != height:
            self.setMinimumHeight(height)


__all__ = ["FormActionButtonRow"]
