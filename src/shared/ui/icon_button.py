"""
Themed icon button.
"""

from __future__ import annotations

from src.qt_api import QPushButton, QSize, Qt

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


def build_icon_button_stylesheet(theme, *, variant: str = "secondary", radius: int | None = None) -> str:
    """Return padding-free chrome for a square icon-only button."""
    resolved_radius = theme.radius_sm if radius is None else max(0, int(radius))
    if variant == "primary":
        background, foreground, border = theme.primary, theme.text_on_primary, "transparent"
        hover_background = theme.primary_hover
    elif variant == "danger":
        background, foreground, border = theme.error, theme.text_on_primary, "transparent"
        hover_background = theme.error_hover
    elif variant == "ghost-danger":
        background, foreground, border = "transparent", theme.error, "transparent"
        hover_background = theme.error_bg
    elif variant == "ghost-primary":
        background, foreground, border = "transparent", theme.primary, "transparent"
        hover_background = theme.primary_light
    elif variant == "ghost":
        background, foreground, border = "transparent", theme.icon_primary, "transparent"
        hover_background = theme.bg_hover
    else:
        background, foreground, border = theme.bg_card, theme.icon_primary, theme.border
        hover_background = theme.bg_hover
    return f"""
        QPushButton {{
            padding: 0px;
            background: {background};
            color: {foreground};
            border: 1px solid {border};
            border-radius: {resolved_radius}px;
        }}
        QPushButton:hover {{
            background: {hover_background};
        }}
        QPushButton:pressed {{
            background: {theme.bg_selected};
        }}
        QPushButton:disabled {{
            background: {theme.bg_input};
            color: {theme.text_disabled};
            border-color: {theme.border_light};
        }}
    """


def apply_icon_button_style(
    button: QPushButton,
    *,
    variant: str = "secondary",
    size: int | None = None,
    icon_size: int | None = None,
) -> QPushButton:
    """Apply the dedicated icon-button geometry and visual contract."""
    theme = get_theme()
    resolved_size = max(1, int(size or theme.icon_button_size))
    resolved_icon_size = max(
        1,
        min(resolved_size, int(icon_size or theme.icon_button_icon_size)),
    )
    button.setProperty("iconButton", True)
    button.setProperty("iconButtonVariant", variant)
    button.setStyleSheet(build_icon_button_stylesheet(theme, variant=variant))
    # Apply the explicit outer geometry after QSS polishing; QSS min/max
    # declarations otherwise overwrite QWidget's fixed bounds.
    button.setFixedSize(resolved_size, resolved_size)
    button.setIconSize(QSize(resolved_icon_size, resolved_icon_size))
    button.updateGeometry()
    return button


class IconButton(QPushButton):
    """Icon button with circle/square/ghost visual variants."""

    def __init__(
        self,
        icon_name: str = "",
        *,
        variant: str = "ghost",
        tooltip: str = "",
        size: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._variant = variant
        self._icon_name = str(icon_name or "")
        self._explicit_size = size

        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self._apply_style()
        bind_theme(self, self._apply_style)

    def _apply_style(self) -> None:
        t = get_theme()
        size = self._explicit_size or t.icon_button_size
        icon_size = min(t.icon_button_icon_size, size)

        if self._icon_name:
            if self._variant in {"primary", "danger"}:
                icon_color = t.text_on_primary
            elif self._variant == "ghost-danger":
                icon_color = t.error
            elif self._variant == "ghost-primary":
                icon_color = t.primary
            else:
                icon_color = t.icon_primary
            self.setIcon(get_icon(self._icon_name, icon_size, icon_color))
            self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(size, size)

        if self._variant == "circle":
            radius = size // 2
        elif self._variant == "square":
            radius = t.radius_sm
        else:
            radius = t.radius_sm

        apply_icon_button_style(
            self,
            variant="ghost" if self._variant == "ghost" else "secondary",
            size=size,
            icon_size=icon_size,
        )
        if self._variant in {"circle", "square"}:
            self.setStyleSheet(
                build_icon_button_stylesheet(
                    t,
                    variant="secondary",
                    radius=radius,
                )
            )

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._apply_style()


__all__ = [
    "IconButton",
    "apply_icon_button_style",
    "build_icon_button_stylesheet",
]
