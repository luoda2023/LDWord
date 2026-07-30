"""
Override badge with shared button styling.
"""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QLabel, QPushButton, QWidget, Signal, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


ORIGINAL_VALUE_PREFIX = "原值"
RESTORE_BUTTON_TEXT = "恢复"


class OverrideBadge(QWidget):
    """Show that a value has been overridden and allow restoring it."""

    restore_clicked = Signal()

    def __init__(self, *, original_value: str = "", parent=None):
        super().__init__(parent)
        self._original = original_value

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(get_theme().spacing_xs)

        self._badge = self._build_badge_icon()
        layout.addWidget(self._badge)

        self._orig_label = self._build_original_value_label(original_value)
        layout.addWidget(self._orig_label)

        self._restore = self._build_restore_button()
        layout.addWidget(self._restore)
        layout.addStretch()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    @staticmethod
    def _build_badge_icon() -> QLabel:
        badge = QLabel()
        badge.setAlignment(Qt.AlignCenter)
        return badge

    def _build_original_value_label(self, original_value: str) -> QLabel:
        return QLabel(self._format_original_label(original_value))

    def _build_restore_button(self) -> QPushButton:
        button = QPushButton(RESTORE_BUTTON_TEXT)
        button.setObjectName('override_restore')
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(self.restore_clicked.emit)
        apply_button_variant(button, 'ghost-primary')
        return button

    def _apply_theme(self) -> None:
        t = get_theme()
        self.layout().setSpacing(t.spacing_xs)
        self._apply_badge_icon_theme(t)
        self._apply_original_label_theme(t)
        self._apply_restore_button_theme(t)
        self.setFixedHeight(t.override_badge_height)

    def _apply_badge_icon_theme(self, theme) -> None:
        self._badge.setFixedSize(theme.override_badge_icon_size, theme.override_badge_icon_size)
        badge_icon_size = max(10, theme.override_badge_icon_size - 6)
        self._badge.setPixmap(get_icon('zap', badge_icon_size, theme.text_on_primary).pixmap(badge_icon_size, badge_icon_size))
        self._badge.setStyleSheet(f"background: {theme.warning}; border-radius: {theme.override_badge_icon_size // 2}px;")

    def _apply_original_label_theme(self, theme) -> None:
        self._orig_label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")

    def _apply_restore_button_theme(self, theme) -> None:
        self._restore.setFixedHeight(theme.override_badge_restore_height)
        self._restore.setStyleSheet(
            build_button_stylesheet(
                theme,
                '#override_restore',
                min_height=theme.override_badge_restore_height,
                padding_x=theme.spacing_xs,
                padding_y=0,
                font_size=theme.font_size_sm,
            )
        )

    @staticmethod
    def _format_original_label(value: str) -> str:
        return f"{ORIGINAL_VALUE_PREFIX}: {value}"

    def set_original(self, value: str):
        self._original = value
        self._orig_label.setText(self._format_original_label(value))
