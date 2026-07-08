"""Shared navigation card primitive.

Provides a selectable card with "icon-left + text-right" layout for the
navigation rail.  The icon area uses the project's Lucide SVG catalog so
every card has a clear visual anchor.
"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.badge import Badge
from src.shared.ui.card import Card
from src.shared.ui.theme import bind_theme, get_theme, theme_rgba


class NavigationCard(Card):
    """Selectable card used by navigation rail.

    Layout::

        ┌──────────────────────────────────┐
        │ ┌──────┐  Title           Badge  │
        │ │ ICON │  Subtitle               │
        │ └──────┘                         │
        └──────────────────────────────────┘

    The icon area renders a Lucide SVG icon via QLabel/QPixmap.  When no
    icon_name is given the icon column is hidden, preserving backward
    compatibility.
    """

    clicked = Signal()

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------

    _ICON_BOX_SIZE = 36          # logical-pixel square for icon container
    _ICON_RENDER_SIZE = 20       # logical-pixel SVG render target
    _DISABLED_OPACITY = 0.45

    def __init__(
        self,
        key: str,
        title: str,
        *,
        icon_name: str = "",
        badge: Badge | None = None,
        parent=None,
    ):
        super().__init__(parent=parent)
        self._key = key
        self._selected = False
        self._hovered = False
        self._disabled = False
        self._icon_name = icon_name
        self._full_subtitle = ""
        self._solid_background = False

        # --- Icon area ---
        self._icon_container = QLabel()
        self._icon_container.setFixedSize(self._ICON_BOX_SIZE, self._ICON_BOX_SIZE)
        self._icon_container.setAlignment(Qt.AlignCenter)
        self._icon_container.setObjectName("nav_card_icon")
        if not icon_name:
            self._icon_container.hide()

        # --- Text area ---
        self._title = QLabel(title)
        self._title.setObjectName("nav_card_title")
        self._title.setAutoFillBackground(False)
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("nav_card_subtitle")
        self._subtitle.setAutoFillBackground(False)
        self._subtitle.setWordWrap(False)
        self._subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # --- Badge ---
        self._badge = badge or Badge("")
        self._badge.setObjectName("nav_card_badge")
        self._title_action: QWidget | None = None

        # --- Assemble layout ---
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        row.addWidget(self._icon_container, 0, Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._title_row = QHBoxLayout()
        self._title_row.setContentsMargins(0, 0, 0, 0)
        self._title_row.setSpacing(10)
        self._title_row.addWidget(self._title, 1)
        self._title_row.addWidget(self._badge, 0, Qt.AlignRight | Qt.AlignVCenter)

        text_col.addLayout(self._title_row)
        text_col.addWidget(self._subtitle)

        row.addLayout(text_col, 1)

        self.add_layout(row)

        # Initial paint
        self._render_icon()
        self._apply_navigation_theme()
        bind_theme(self, self._on_theme_changed)

    # ------------------------------------------------------------------
    # Theme / style
    # ------------------------------------------------------------------

    def _on_theme_changed(self) -> None:
        self._render_icon()
        self._apply_navigation_theme()

    def _apply_navigation_theme(self) -> None:
        t = get_theme()

        if self._selected:
            bg = t.primary
            border = t.primary
        elif self._hovered:
            bg = t.bg_hover
            border = t.border
        elif self._solid_background:
            bg = t.bg_card
            border = t.border_light
        else:
            # Paint the rail background explicitly so stale selected-state pixels
            # cannot survive when a blue card returns to its idle state.
            bg = t.bg_nav_rail
            border = "transparent"

        self.set_card_surface(
            background=bg,
            border_color=border,
            border_width=1.0 if self._solid_background else 0.0,
            shadow=False,
        )
        self.setStyleSheet("")

        if self._selected:
            icon_bg = theme_rgba(t.text_on_primary, 0.20)
        else:
            icon_bg = t.bg_hover
        self._icon_container.setStyleSheet(
            f"""
            #nav_card_icon {{
                background: {icon_bg};
                border-radius: {t.radius_sm}px;
            }}
            """
        )

        # --- Title ---
        title_color = t.text_on_primary if self._selected else t.text_primary
        self._title.setStyleSheet(
            f"""
            QLabel#nav_card_title {{
                background: transparent;
                border: none;
                padding: 0px;
                font-size: {t.font_size_md}px;
                font-weight: {t.font_weight_emphasis if self._selected else t.font_weight_normal};
                color: {title_color};
            }}
            """
        )

        # --- Subtitle ---
        sub_color = theme_rgba(t.text_on_primary, 0.85) if self._selected else t.text_secondary
        self._subtitle.setStyleSheet(
            f"""
            QLabel#nav_card_subtitle {{
                background: transparent;
                border: none;
                padding: 0px;
                font-size: {t.font_size_sm}px;
                color: {sub_color};
            }}
            """
        )
        self._subtitle.setVisible(bool(self._subtitle.text()))

        # --- Badge (switch to on-primary mode when card is selected) ---
        self._badge.set_on_primary(self._selected)

    def _render_icon(self) -> None:
        """Render the Lucide SVG icon into the icon container."""
        if not self._icon_name:
            self._icon_container.hide()
            return

        self._icon_container.show()
        try:
            from src.ui.icons.catalog import get_icon
            # Selected → white icon; Normal → theme icon color
            color = get_theme().text_on_primary if self._selected else get_theme().icon_primary
            icon = get_icon(self._icon_name, size=self._ICON_RENDER_SIZE, color=color)
            pixmap = icon.pixmap(self._ICON_RENDER_SIZE, self._ICON_RENDER_SIZE)
            self._icon_container.setPixmap(pixmap)
        except Exception:
            # Graceful fallback — show first char of key
            self._icon_container.setText(self._key[:1].upper())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def key(self) -> str:
        return self._key

    @property
    def icon_name(self) -> str:
        return self._icon_name

    def set_icon(self, icon_name: str) -> None:
        """Change the icon dynamically."""
        self._icon_name = icon_name
        self._render_icon()
        self._apply_navigation_theme()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._render_icon()
        self._apply_navigation_theme()

    def is_selected(self) -> bool:
        return self._selected

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = bool(disabled)
        self.setEnabled(not disabled)
        self._apply_navigation_theme()

    def is_disabled(self) -> bool:
        return self._disabled

    def set_solid_background(self, enabled: bool) -> None:
        self._solid_background = bool(enabled)
        self._apply_navigation_theme()

    def has_solid_background(self) -> bool:
        return self._solid_background

    def set_subtitle(self, text: str) -> None:
        self._full_subtitle = str(text or "").strip()
        self._subtitle.setToolTip(self._full_subtitle)
        self._subtitle.setVisible(bool(self._full_subtitle))
        self._update_elided_subtitle()

    def _update_elided_subtitle(self) -> None:
        if not self._full_subtitle:
            self._subtitle.setText("")
            return
        metrics = self._subtitle.fontMetrics()
        # Leave room for icon, padding, and spacing (approx 80px)
        available = max(10, self.width() - 80) if self.width() > 80 else max(10, self._subtitle.width())
        elided = metrics.elidedText(self._full_subtitle, Qt.ElideMiddle, available)
        self._subtitle.setText(elided)

    def set_badge(self, text: str, variant: str = "neutral") -> None:
        self._badge.set_text(text)
        self._badge.set_variant(variant)

    def set_title_action(self, widget: QWidget | None) -> None:
        if self._title_action is widget:
            return
        if self._title_action is not None:
            self._title_row.removeWidget(self._title_action)
            self._title_action.setParent(None)
        self._title_action = widget
        if widget is not None:
            self._title_row.addWidget(widget, 0, Qt.AlignRight | Qt.AlignVCenter)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_subtitle()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and not self._disabled:
            self.clicked.emit()
        return super().mousePressEvent(event)

    def enterEvent(self, event):  # noqa: N802
        if not self._disabled:
            self._hovered = True
            self.setCursor(Qt.PointingHandCursor)
            self._apply_navigation_theme()
        return super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hovered = False
        self.unsetCursor()
        self._apply_navigation_theme()
        return super().leaveEvent(event)
