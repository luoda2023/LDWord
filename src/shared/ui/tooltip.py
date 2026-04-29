"""Global themed tooltip controller."""

from __future__ import annotations

from dataclasses import dataclass

from src.qt_api import (
    QApplication,
    QColor,
    QEasingCurve,
    QEvent,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    QTimer,
    QToolTip,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme


TOOLTIP_PLACEMENT_PROPERTY = "_alavette_tooltip_placement"
TOOLTIP_ROLE_PROPERTY = "_alavette_tooltip_role"
TOOLTIP_DELAY_PROPERTY = "_alavette_tooltip_delay_ms"
TOOLTIP_ENABLED_PROPERTY = "_alavette_tooltip_enabled"

DEFAULT_DELAY_MS = 120
NAV_DELAY_MS = 80
DEFAULT_GAP = 4
SCREEN_MARGIN = 8
OUTER_MARGIN = 4


def _qcolor_from_theme_shadow(value: str, fallback: str) -> QColor:
    color = QColor(value)
    if color.isValid():
        return color

    normalized = str(value or "").strip().lower()
    if normalized.startswith("rgba(") and normalized.endswith(")"):
        parts = [part.strip() for part in normalized[5:-1].split(",")]
        if len(parts) == 4:
            try:
                red, green, blue = (int(float(channel)) for channel in parts[:3])
                raw_alpha = float(parts[3])
                alpha = int(raw_alpha * 255) if raw_alpha <= 1 else int(raw_alpha)
                return QColor(
                    max(0, min(255, red)),
                    max(0, min(255, green)),
                    max(0, min(255, blue)),
                    max(0, min(255, alpha)),
                )
            except ValueError:
                pass

    fallback_color = QColor(fallback)
    if not fallback_color.isValid():
        fallback_color = QColor(0, 0, 0)
    fallback_color.setAlpha(28)
    return fallback_color


@dataclass(frozen=True)
class TooltipOptions:
    """Resolved display options for a widget tooltip."""

    text: str
    placement: str = "auto"
    role: str = "default"
    delay_ms: int = DEFAULT_DELAY_MS


def set_global_tooltip(
    widget: QWidget,
    text: str,
    *,
    placement: str = "auto",
    role: str = "default",
    delay_ms: int | None = None,
) -> QWidget:
    """Assign tooltip metadata consumed by the global controller."""

    widget.setToolTip(str(text or ""))
    widget.setProperty(TOOLTIP_ENABLED_PROPERTY, True)
    widget.setProperty(TOOLTIP_PLACEMENT_PROPERTY, placement)
    widget.setProperty(TOOLTIP_ROLE_PROPERTY, role)
    if delay_ms is None:
        widget.setProperty(TOOLTIP_DELAY_PROPERTY, None)
    else:
        widget.setProperty(TOOLTIP_DELAY_PROPERTY, int(max(0, delay_ms)))
    return widget


def tooltip_position_for(
    anchor: QWidget,
    popup_size: QSize,
    *,
    placement: str = "auto",
    gap: int = DEFAULT_GAP,
    screen_margin: int = SCREEN_MARGIN,
) -> QPoint:
    """Return a screen position for a tooltip anchored to a widget."""

    anchor_rect = QRect(
        anchor.mapToGlobal(anchor.rect().topLeft()),
        anchor.mapToGlobal(anchor.rect().bottomRight()),
    )
    screen = QApplication.screenAt(anchor_rect.center()) or QApplication.primaryScreen()
    bounds = screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)
    safe_bounds = bounds.adjusted(screen_margin, screen_margin, -screen_margin, -screen_margin)

    placements = _placement_order(placement)
    first_pos = _raw_position(anchor_rect, popup_size, placements[0], gap)
    for candidate in placements:
        pos = _raw_position(anchor_rect, popup_size, candidate, gap)
        if safe_bounds.contains(QRect(pos, popup_size)):
            return pos
    return _clamp_position(first_pos, popup_size, safe_bounds)


def install_global_tooltip(app: QApplication) -> "GlobalTooltipController":
    """Install the shared tooltip controller once for the QApplication."""

    existing = getattr(app, "_alavette_global_tooltip_controller", None)
    if existing is not None:
        return existing
    controller = GlobalTooltipController(app)
    app.installEventFilter(controller)
    app._alavette_global_tooltip_controller = controller
    return controller


class TooltipPopup(QWidget):
    """Small top-level popup surface with theme-aware styling."""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN, OUTER_MARGIN)
        layout.setSpacing(0)

        self._surface = QFrame(self)
        self._surface.setObjectName("global_tooltip_surface")
        self._surface.setAttribute(Qt.WA_StyledBackground, True)
        layout.addWidget(self._surface)

        surface_layout = QHBoxLayout(self._surface)
        surface_layout.setContentsMargins(10, 6, 10, 6)
        surface_layout.setSpacing(0)

        self._label = QLabel()
        self._label.setObjectName("global_tooltip_label")
        self._label.setWordWrap(False)
        surface_layout.addWidget(self._label)

        self._shadow = QGraphicsDropShadowEffect(self._surface)
        self._surface.setGraphicsEffect(self._shadow)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.hide()

    def show_text(self, text: str, anchor: QWidget, placement: str) -> None:
        self._apply_theme()
        self._label.setText(str(text).replace("\r", " ").replace("\n", " "))
        self.adjustSize()
        self.move(tooltip_position_for(anchor, self.size(), placement=placement))
        self.show()
        self.raise_()

        t = get_theme()
        self._fade.stop()
        self._fade.setDuration(max(40, min(140, int(t.anim_duration_fast))))
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def hide_popup(self) -> None:
        self._fade.stop()
        self._opacity.setOpacity(0.0)
        self.hide()

    def reposition(self, anchor: QWidget, placement: str) -> None:
        if self.isVisible():
            self.move(tooltip_position_for(anchor, self.size(), placement=placement))

    def _apply_theme(self) -> None:
        t = get_theme()
        tooltip_bg = t.bg_tooltip
        tooltip_border = t.border
        tooltip_text = t.text_on_tooltip
        self._surface.setStyleSheet(
            f"""
            #global_tooltip_surface {{
                background: {tooltip_bg};
                border: 1px solid {tooltip_border};
                border-radius: {t.radius_sm}px;
            }}
            #global_tooltip_label {{
                background: transparent;
                border: none;
                color: {tooltip_text};
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_medium};
            }}
            """
        )
        self._shadow.setBlurRadius(max(6, min(12, int(t.shadow_blur_sm))))
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(_qcolor_from_theme_shadow(t.shadow_color, t.bg_tooltip))


class GlobalTooltipController(QObject):
    """Application-level tooltip event filter."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._app = app
        self._popup = TooltipPopup()
        self._pending_widget: QWidget | None = None
        self._current_widget: QWidget | None = None
        self._current_options: TooltipOptions | None = None
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_pending)

    @property
    def popup(self) -> TooltipPopup:
        return self._popup

    def options_for(self, widget: QWidget) -> TooltipOptions | None:
        if widget.property(TOOLTIP_ENABLED_PROPERTY) is not True:
            return None

        text = str(widget.toolTip() or "").strip()
        if not text:
            return None

        placement = str(widget.property(TOOLTIP_PLACEMENT_PROPERTY) or "auto")
        role = str(widget.property(TOOLTIP_ROLE_PROPERTY) or "default")
        raw_delay = widget.property(TOOLTIP_DELAY_PROPERTY)
        try:
            delay_ms = int(raw_delay) if raw_delay is not None else _default_delay_for_role(role)
        except (TypeError, ValueError):
            delay_ms = _default_delay_for_role(role)
        return TooltipOptions(text=text, placement=placement, role=role, delay_ms=max(0, delay_ms))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        event_type = event.type()

        if event_type == QEvent.ToolTip and isinstance(obj, QWidget):
            if self.options_for(obj) is not None:
                QToolTip.hideText()
                self._schedule(obj)
                return True

        if not isinstance(obj, QWidget):
            return False

        if event_type == QEvent.Enter:
            self._schedule(obj)
            return False

        if event_type in (QEvent.Leave, QEvent.Hide, QEvent.Close, QEvent.Destroy):
            if obj is self._pending_widget or obj is self._current_widget:
                self.hide_tooltip()
            return False

        if event_type in (QEvent.Move, QEvent.Resize, QEvent.Show):
            if obj is self._current_widget and self._current_options is not None:
                self._popup.reposition(obj, self._current_options.placement)
            return False

        if event_type in (QEvent.MouseButtonPress, QEvent.Wheel, QEvent.KeyPress, QEvent.WindowDeactivate):
            self.hide_tooltip()

        return False

    def hide_tooltip(self) -> None:
        self._show_timer.stop()
        self._pending_widget = None
        self._current_widget = None
        self._current_options = None
        self._popup.hide_popup()
        QToolTip.hideText()

    def _schedule(self, widget: QWidget) -> None:
        options = self.options_for(widget)
        if options is None or not widget.isEnabled() or not widget.isVisible():
            return
        self._pending_widget = widget
        self._current_options = options
        self._show_timer.start(options.delay_ms)

    def _show_pending(self) -> None:
        widget = self._pending_widget
        options = self._current_options
        if widget is None or options is None:
            return
        if not widget.isEnabled() or not widget.isVisible():
            self.hide_tooltip()
            return
        self._current_widget = widget
        self._pending_widget = None
        self._popup.show_text(options.text, widget, options.placement)


def _default_delay_for_role(role: str) -> int:
    return NAV_DELAY_MS if role == "nav" else DEFAULT_DELAY_MS


def _placement_order(placement: str) -> list[str]:
    normalized = placement if placement in {"right", "left", "top", "bottom"} else "auto"
    if normalized == "auto":
        return ["right", "bottom", "left", "top"]
    fallbacks = [p for p in ("right", "bottom", "left", "top") if p != normalized]
    return [normalized, *fallbacks]


def _raw_position(anchor_rect: QRect, popup_size: QSize, placement: str, gap: int) -> QPoint:
    if placement == "left":
        return QPoint(anchor_rect.left() - popup_size.width() - gap, anchor_rect.center().y() - popup_size.height() // 2)
    if placement == "top":
        return QPoint(anchor_rect.center().x() - popup_size.width() // 2, anchor_rect.top() - popup_size.height() - gap)
    if placement == "bottom":
        return QPoint(anchor_rect.center().x() - popup_size.width() // 2, anchor_rect.bottom() + gap)
    return QPoint(anchor_rect.right() + gap, anchor_rect.center().y() - popup_size.height() // 2)


def _clamp_position(pos: QPoint, popup_size: QSize, bounds: QRect) -> QPoint:
    x = min(max(pos.x(), bounds.left()), max(bounds.left(), bounds.right() - popup_size.width() + 1))
    y = min(max(pos.y(), bounds.top()), max(bounds.top(), bounds.bottom() - popup_size.height() + 1))
    return QPoint(x, y)

__all__ = [
    "GlobalTooltipController",
    "TooltipOptions",
    "TooltipPopup",
    "install_global_tooltip",
    "set_global_tooltip",
    "tooltip_position_for",
]
