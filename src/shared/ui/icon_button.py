"""
Themed icon button.
"""

from __future__ import annotations

from src.qt_api import QIcon, QPushButton, QSize, Qt

from src.shared.ui.theme import bind_theme, get_theme


class IconButton(QPushButton):
    """Icon button with circle/square/ghost visual variants."""

    def __init__(
        self,
        icon_path: str = "",
        *,
        variant: str = "ghost",
        tooltip: str = "",
        size: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._variant = variant
        self._icon_path = icon_path
        self._explicit_size = size

        if icon_path:
            self.setIcon(QIcon(icon_path))

        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self._apply_style()
        bind_theme(self, self._apply_style)

    def _apply_style(self) -> None:
        t = get_theme()
        size = self._explicit_size or t.icon_button_size
        icon_size = min(t.icon_button_icon_size, size)

        if self._icon_path:
            self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(size, size)

        if self._variant == "circle":
            background = t.bg_hover
            radius = size // 2
        elif self._variant == "square":
            background = t.bg_hover
            radius = t.radius_sm
        else:
            background = "transparent"
            radius = t.radius_sm

        self.setStyleSheet(
            f"""
            QPushButton {{
                border: none;
                padding: 0;
                background-color: {background};
                border-radius: {radius}px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
            }}
            QPushButton:pressed {{
                background-color: {t.border};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
            """
        )

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._apply_style()
