"""
StyledSpinBox — themed QDoubleSpinBox matching the StyledComboBox visual design.

Replaces the native OS spin-box chrome with custom-painted borders,
separator, and up/down chevrons that harmonize with the rest of the
design system.

Usage::

    from src.shared.ui.styled_spin_box import StyledSpinBox

    spin = StyledSpinBox(parent)
    spin.setRange(0.0, 20.0)
    spin.setSingleStep(0.5)
    spin.setDecimals(1)
"""

from __future__ import annotations

from src.qt_api import (
    QColor,
    QDoubleSpinBox,
    QPainter,
    QPen,
    QRectF,
    Qt,
)

from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme


class StyledSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox with custom-painted border and up/down chevrons.

    The visual language mirrors ``StyledComboBox``:
    - Rounded rect border (normal / focus / disabled states)
    - Internal vertical separator before the button zone
    - Chevron arrows drawn with anti-aliased QPainter strokes
    """

    _id_counter = 0

    def __init__(self, parent=None):
        super().__init__(parent)

        StyledSpinBox._id_counter += 1
        spin_id = StyledSpinBox._id_counter
        self.setObjectName(f"styled_spin_{spin_id}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        apply_size_class(self, "md")

        self._refresh_style()
        bind_theme(self, self._refresh_style)

    # ------------------------------------------------------------------
    # QSS
    # ------------------------------------------------------------------

    @staticmethod
    def build_spin_stylesheet(object_name: str, theme) -> str:
        """Generate QSS that hides native buttons and applies themed colours."""
        return f"""
            #{object_name} {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: none;
                border-radius: {theme.input_radius}px;
                padding: {theme.input_padding_y}px {theme.input_padding_x}px;
                padding-right: {theme.spin_button_width}px;
                font-size: {theme.font_size_md}px;
                font-family: {theme.font_family};
                selection-background-color: {theme.primary};
                selection-color: {theme.text_on_primary};
            }}
            #{object_name}:focus {{
                background: {theme.bg_window};
            }}
            #{object_name}:disabled {{
                background: {theme.bg_hover};
                color: {theme.text_disabled};
            }}
            #{object_name}::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: {theme.spin_button_width}px;
                border: none;
                background: transparent;
            }}
            #{object_name}::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: {theme.spin_button_width}px;
                border: none;
                background: transparent;
            }}
            #{object_name}::up-arrow,
            #{object_name}::down-arrow {{
                width: 0; height: 0;
                image: none;
            }}
            #{object_name}[sizeClass="sm"] {{
                min-height: {theme.control_height_sm}px;
                max-height: {theme.control_height_sm}px;
            }}
            #{object_name}[sizeClass="md"] {{
                min-height: {theme.control_height_md}px;
                max-height: {theme.control_height_md}px;
            }}
            #{object_name}[sizeClass="lg"] {{
                min-height: {theme.control_height_lg}px;
                max-height: {theme.control_height_lg}px;
            }}
        """

    # ------------------------------------------------------------------
    # Custom paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)

        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # ── Border ──
        if not self.isEnabled():
            border_color = QColor(theme.border)
            border_width = 1.0
        elif self.hasFocus():
            border_color = QColor(theme.border_focus)
            border_width = 1.5
        else:
            border_color = QColor(theme.text_hint)
            border_width = 1.25

        radius = float(theme.input_radius)
        half = border_width / 2.0
        border_rect = QRectF(half, half, self.width() - border_width, self.height() - border_width)
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(border_rect, radius, radius)

        # ── Separator ──
        separator_color = QColor(theme.border_focus if self.hasFocus() else theme.border)
        separator_color.setAlpha(170 if self.hasFocus() else 135)
        painter.setPen(QPen(separator_color, 1.0))
        sep_x = self.width() - theme.spin_button_width
        inset = max(4, self.height() // 5)
        painter.drawLine(sep_x, inset, sep_x, self.height() - inset)

        # ── Up / Down chevrons ──
        arrow_color = QColor(theme.border_focus if self.hasFocus() else theme.text_secondary)
        if not self.isEnabled():
            arrow_color = QColor(theme.text_disabled)
        painter.setPen(QPen(arrow_color, 1.6))

        zone_cx = self.width() - (theme.spin_button_width // 2)
        mid_y = self.height() / 2.0
        half_chevron = 3  # half-width of the chevron

        # Up arrow: centered in top half of button zone
        up_cy = mid_y / 2.0 + 1
        painter.drawLine(
            int(zone_cx - half_chevron), int(up_cy + 2),
            int(zone_cx), int(up_cy - 1),
        )
        painter.drawLine(
            int(zone_cx), int(up_cy - 1),
            int(zone_cx + half_chevron), int(up_cy + 2),
        )

        # Down arrow: centered in bottom half of button zone
        dn_cy = mid_y + mid_y / 2.0 - 1
        painter.drawLine(
            int(zone_cx - half_chevron), int(dn_cy - 2),
            int(zone_cx), int(dn_cy + 1),
        )
        painter.drawLine(
            int(zone_cx), int(dn_cy + 1),
            int(zone_cx + half_chevron), int(dn_cy - 2),
        )

        painter.end()

    # ------------------------------------------------------------------
    # Theme sync
    # ------------------------------------------------------------------

    def _refresh_style(self) -> None:
        theme = get_theme()
        self.setStyleSheet(self.build_spin_stylesheet(self.objectName(), theme))
        self.updateGeometry()
        self.update()
