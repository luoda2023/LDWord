"""Shared geometry and painting helpers for themed input controls."""

from __future__ import annotations

from src.qt_api import QColor, QLineF, QPainter, QRect, QRectF, QSizePolicy, Qt
from src.shared.ui.paint_geometry import (
    STROKE_ICON,
    snapped_pen_width,
    snapped_stroke_coordinate,
    stroke_pen,
)
from src.shared.ui.typography_policy import TextRole, apply_text_role


INPUT_EDITOR_TEXT_MARGIN_LEFT = -2


def input_text_rect(width: int, height: int, *, button_width: int, theme) -> QRect:
    left = max(0, int(theme.input_padding_x))
    right = max(0, int(button_width))
    return QRect(left, 0, max(0, int(width) - left - right), max(0, int(height)))


def input_separator_x(width: int, *, button_width: int) -> int:
    return max(0, int(width) - max(0, int(button_width)))


def input_background_color(theme, *, enabled: bool, active: bool) -> QColor:
    if not enabled:
        return QColor(theme.bg_hover)
    if active:
        return QColor(theme.bg_window)
    return QColor(theme.bg_input)


def input_border_color(theme, *, enabled: bool, active: bool) -> tuple[QColor, float]:
    if not enabled:
        return QColor(theme.border), 1.0
    if active:
        return QColor(theme.border_focus), 1.0
    return QColor(theme.border), 1.0


def input_text_color(theme, *, enabled: bool) -> QColor:
    return QColor(theme.text_primary if enabled else theme.text_disabled)


def draw_input_surface(
    painter: QPainter,
    width: int,
    height: int,
    *,
    theme,
    enabled: bool,
    active: bool,
    button_width: int,
) -> None:
    radius = float(theme.input_radius)
    painter.setPen(Qt.NoPen)
    painter.setBrush(input_background_color(theme, enabled=enabled, active=active))
    painter.drawRoundedRect(QRectF(0, 0, max(0, int(width)), max(0, int(height))), radius, radius)

    border_color, border_width = input_border_color(theme, enabled=enabled, active=active)
    rendered_border_width = snapped_pen_width(border_width, painter)
    half_border = rendered_border_width / 2.0
    border_rect = QRectF(
        half_border,
        half_border,
        max(0.0, float(width) - rendered_border_width),
        max(0.0, float(height) - rendered_border_width),
    )
    painter.setPen(stroke_pen(painter, border_color, border_width))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(border_rect, radius, radius)

    separator_color = QColor(theme.border_focus if active else theme.border)
    separator_color.setAlpha(170 if active else 135)
    painter.setPen(stroke_pen(painter, separator_color, 1.0, cap=Qt.FlatCap))
    separator_x = snapped_stroke_coordinate(
        input_separator_x(width, button_width=button_width),
        1.0,
        painter,
    )
    inset = max(4, int(height) // 5)
    painter.drawLine(
        QLineF(
            separator_x,
            float(inset),
            separator_x,
            float(max(inset, int(height) - inset)),
        )
    )


def draw_combo_chevron(
    painter: QPainter,
    width: int,
    height: int,
    *,
    theme,
    enabled: bool,
    active: bool,
) -> None:
    arrow_color = QColor(theme.border_focus if active else theme.text_secondary)
    if not enabled:
        arrow_color = QColor(theme.text_disabled)
    painter.setPen(stroke_pen(painter, arrow_color, STROKE_ICON))
    zone_center_x = int(width) - (int(theme.combo_arrow_zone_width) // 2)
    zone_center_y = int(height) // 2
    half = max(2, int(theme.combo_arrow_size) // 2)
    painter.drawLine(zone_center_x - half, zone_center_y - 1, zone_center_x, zone_center_y + half - 1)
    painter.drawLine(zone_center_x, zone_center_y + half - 1, zone_center_x + half, zone_center_y - 1)


def draw_spin_chevrons(
    painter: QPainter,
    width: int,
    height: int,
    *,
    theme,
    enabled: bool,
    active: bool,
) -> None:
    arrow_color = QColor(theme.border_focus if active else theme.text_secondary)
    if not enabled:
        arrow_color = QColor(theme.text_disabled)
    painter.setPen(stroke_pen(painter, arrow_color, STROKE_ICON))

    zone_cx = int(width) - (int(theme.spin_button_width) // 2)
    mid_y = float(height) / 2.0
    half_chevron = 3

    up_cy = mid_y / 2.0 + 1
    painter.drawLine(int(zone_cx - half_chevron), int(up_cy + 2), int(zone_cx), int(up_cy - 1))
    painter.drawLine(int(zone_cx), int(up_cy - 1), int(zone_cx + half_chevron), int(up_cy + 2))

    down_cy = mid_y + mid_y / 2.0 - 1
    painter.drawLine(int(zone_cx - half_chevron), int(down_cy - 2), int(zone_cx), int(down_cy + 1))
    painter.drawLine(int(zone_cx), int(down_cy + 1), int(zone_cx + half_chevron), int(down_cy - 2))


def configure_input_line_edit(
    line_edit,
    theme,
    *,
    stylesheet: str | None = None,
    text_margin_left: int = INPUT_EDITOR_TEXT_MARGIN_LEFT,
    text_role: TextRole = TextRole.BODY,
) -> None:
    """Apply one semantic font plus geometry-neutral styling to a QLineEdit."""

    apply_text_role(line_edit, text_role)
    line_edit.setFrame(False)
    line_edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    line_edit.setContentsMargins(0, 0, 0, 0)
    line_edit.setTextMargins(int(text_margin_left), 0, 0, 0)
    line_edit.setMinimumHeight(0)
    editor_policy = line_edit.sizePolicy()
    editor_policy.setHorizontalPolicy(QSizePolicy.Expanding)
    editor_policy.setVerticalPolicy(QSizePolicy.Ignored)
    line_edit.setSizePolicy(editor_policy)
    line_edit.setStyleSheet(stylesheet or build_input_editor_stylesheet(theme))


def sync_input_line_edit_geometry(owner, line_edit, *, button_width: int, theme) -> QRect:
    """Place an embedded editor inside the shared input text rect."""

    rect = input_text_rect(
        owner.width(),
        owner.height(),
        button_width=button_width,
        theme=theme,
    )
    line_edit.setMinimumHeight(0)
    if owner.height() > 0:
        line_edit.setMaximumHeight(owner.height())
    line_edit.setGeometry(rect)
    return rect


def build_input_editor_stylesheet(
    theme,
    *,
    font_size: int | None = None,
    padding: str = "0",
    text_color: str | None = None,
    placeholder_color: str | None = None,
) -> str:
    # Font ownership belongs to ``configure_input_line_edit``.  The optional
    # declaration remains only as a compatibility escape hatch for legacy
    # callers that have not migrated their special text role yet.
    font_size_declaration = (
        "" if font_size is None else f"font-size: {int(font_size)}px;"
    )
    resolved_text_color = theme.text_primary if text_color is None else text_color
    resolved_placeholder_color = theme.text_hint if placeholder_color is None else placeholder_color
    return f"""
        QLineEdit {{
            border: none;
            background: transparent;
            color: {resolved_text_color};
            selection-background-color: {theme.primary};
            selection-color: {theme.text_on_primary};
            padding: {padding};
            {font_size_declaration}
        }}
        QLineEdit::placeholder {{
            color: {resolved_placeholder_color};
        }}
    """


def build_framed_input_stylesheet(
    theme,
    selector: str = "QLineEdit",
    *,
    font_family: str | None = None,
    font_size: int | None = None,
    background: str | None = None,
    focus_border_color: str | None = None,
    border_radius: int | None = None,
    padding_x: int | None = None,
    padding_y: int | None = None,
    min_height: int | None = None,
) -> str:
    font_family_declaration = (
        f"font-family: {font_family};" if font_family else ""
    )
    # Default framed inputs inherit the application BODY role.  Explicit
    # family/size declarations are compatibility escape hatches for existing
    # specialized editors; new widgets should set a semantic QFont instead.
    font_size_declaration = (
        "" if font_size is None else f"font-size: {int(font_size)}px;"
    )
    resolved_background = background or theme.bg_input
    resolved_focus_border = focus_border_color or theme.border_focus
    resolved_border_radius = theme.input_radius if border_radius is None else int(border_radius)
    resolved_padding_x = theme.input_padding_x if padding_x is None else padding_x
    resolved_padding_y = theme.input_padding_y if padding_y is None else padding_y
    from src.shared.ui.sizing import control_size_metrics

    metrics = control_size_metrics(
        theme,
        "md",
        vertical_padding=resolved_padding_y,
        border_width=1,
    )
    resolved_outer_height = metrics.outer_height if min_height is None else int(min_height)
    resolved_content_height = max(
        0,
        resolved_outer_height - (resolved_padding_y * 2) - 2,
    )
    size_metrics = {
        size: control_size_metrics(
            theme,
            size,
            vertical_padding=resolved_padding_y,
            border_width=1,
        )
        for size in ("sm", "md", "lg")
    }

    return f"""
        {selector} {{
            background: {resolved_background};
            color: {theme.text_primary};
            border: 1px solid {theme.border};
            border-radius: {resolved_border_radius}px;
            min-height: {resolved_content_height}px;
            max-height: {resolved_content_height}px;
            padding: {resolved_padding_y}px {resolved_padding_x}px;
            {font_size_declaration}
            {font_family_declaration}
            selection-background-color: {theme.primary};
            selection-color: {theme.text_on_primary};
        }}
        {selector}:focus {{
            border-color: {resolved_focus_border};
        }}
        {selector}:disabled {{
            background: {theme.bg_hover};
            color: {theme.text_disabled};
        }}
        {selector}::placeholder {{
            color: {theme.text_hint};
        }}

        /* Size-class tiers via the shared sizeClass dynamic property. */
        {selector}[sizeClass="sm"] {{
            min-height: {size_metrics["sm"].content_height}px;
            max-height: {size_metrics["sm"].content_height}px;
        }}
        {selector}[sizeClass="md"] {{
            min-height: {size_metrics["md"].content_height}px;
            max-height: {size_metrics["md"].content_height}px;
        }}
        {selector}[sizeClass="lg"] {{
            min-height: {size_metrics["lg"].content_height}px;
            max-height: {size_metrics["lg"].content_height}px;
        }}

        QComboBox[sizeClass="sm"] {{
            min-height: {size_metrics["sm"].content_height}px;
            max-height: {size_metrics["sm"].content_height}px;
        }}
        QComboBox[sizeClass="md"] {{
            min-height: {size_metrics["md"].content_height}px;
            max-height: {size_metrics["md"].content_height}px;
        }}

        QSpinBox[sizeClass="sm"] {{
            min-height: {size_metrics["sm"].content_height}px;
            max-height: {size_metrics["sm"].content_height}px;
        }}
        QSpinBox[sizeClass="md"] {{
            min-height: {size_metrics["md"].content_height}px;
            max-height: {size_metrics["md"].content_height}px;
        }}

        QDoubleSpinBox[sizeClass="sm"] {{
            min-height: {size_metrics["sm"].content_height}px;
            max-height: {size_metrics["sm"].content_height}px;
        }}
        QDoubleSpinBox[sizeClass="md"] {{
            min-height: {size_metrics["md"].content_height}px;
            max-height: {size_metrics["md"].content_height}px;
        }}
    """


__all__ = [
    "build_framed_input_stylesheet",
    "build_input_editor_stylesheet",
    "configure_input_line_edit",
    "draw_combo_chevron",
    "draw_input_surface",
    "draw_spin_chevrons",
    "input_separator_x",
    "input_text_color",
    "input_text_rect",
    "sync_input_line_edit_geometry",
]
