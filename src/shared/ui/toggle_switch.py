"""Primitive capsule ON/OFF switch."""

from __future__ import annotations

from src.qt_api import (
    QAbstractAnimation,
    QAbstractButton,
    QBrush,
    QColor,
    QPainter,
    QPen,
    QPropertyAnimation,
    QRectF,
    QSize,
    Signal,
    Property,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme


class ToggleSwitch(QAbstractButton):
    """Primitive switch control.

    Use this directly only when the switch is the whole control. For a labelled
    boolean field inside a form row, wrap it in ``OptionToggleChip``. For a
    feature/module row with a config action, use ``FeatureToggleRow``.
    """

    toggled_signal = Signal(bool)

    TRACK_W = 44
    TRACK_H = 24
    THUMB_D = 18
    THUMB_MARGIN = 3
    OFF_TRACK_BORDER_W = 1.0
    ANIMATION_DURATION_MS = 160

    def __init__(self, parent=None, *, checked: bool = False):
        super().__init__(parent)
        self._checked_track_color: str | None = None
        self.setCheckable(True)
        self.setChecked(checked)
        self._thumb_x = float(
            self.TRACK_W - self.THUMB_D - self.THUMB_MARGIN
            if checked
            else self.THUMB_MARGIN
        )

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(self.ANIMATION_DURATION_MS)

        self.clicked.connect(self._on_click)
        self.setFixedSize(self.sizeHint())

        bind_theme(self, self.update)

    @Property(float)
    def thumb_position(self) -> float:
        return self._thumb_x

    @thumb_position.setter
    def thumb_position(self, val: float) -> None:
        self._thumb_x = val
        self.update()

    def set_checked_track_color(self, color: str | None) -> None:
        self._checked_track_color = str(color).strip() if color else None
        self.update()

    def set_checked(self, checked: bool, *, animate: bool = False) -> None:
        """Synchronize the checked state and thumb position without fighting clicks.

        User clicks own the animated transition. Programmatic state projection should
        use this method with ``animate=False`` so it can avoid snapping the thumb while
        a user-started animation is already travelling to the same target.
        """

        checked = bool(checked)
        target = self._thumb_target_for_checked(checked)
        if animate:
            if self.isChecked() != checked:
                self.setChecked(checked)
            self._animate_thumb_to(target)
            return

        if self.isChecked() == checked and self._animation_targets(target):
            return

        self._anim.stop()
        if self.isChecked() != checked:
            self.setChecked(checked)
        self.thumb_position = target

    def _on_click(self) -> None:
        checked = self.isChecked()
        self._animate_thumb_to(self._thumb_target_for_checked(checked))
        self.toggled_signal.emit(checked)

    def _thumb_target_for_checked(self, checked: bool) -> float:
        return float(
            self.TRACK_W - self.THUMB_D - self.THUMB_MARGIN
            if checked
            else self.THUMB_MARGIN
        )

    def _animate_thumb_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._thumb_x)
        self._anim.setEndValue(float(target))
        self._anim.start()

    def _animation_targets(self, target: float) -> bool:
        if self._anim.state() != QAbstractAnimation.Running:
            return False
        try:
            return abs(float(self._anim.endValue()) - float(target)) < 0.5
        except (TypeError, ValueError):
            return False

    def _has_off_track_border(self) -> bool:
        return (not self.isChecked()) and self.isEnabled()

    def _track_pen_width(self) -> float:
        return self.OFF_TRACK_BORDER_W if self._has_off_track_border() else 0.0

    def _track_rect(self) -> QRectF:
        pen_width = self._track_pen_width()
        if pen_width <= 0:
            return QRectF(0.0, 0.0, float(self.width()), float(self.height()))

        # Keep the OFF-state border fully inside the widget bounds.
        inset = pen_width / 2.0
        return QRectF(
            inset,
            inset,
            float(self.width()) - pen_width,
            float(self.height()) - pen_width,
        )

    def _thumb_y(self, track_rect: QRectF) -> float:
        return track_rect.y() + (track_rect.height() - self.THUMB_D) / 2.0

    def paintEvent(self, event) -> None:
        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.isEnabled():
            track_color = QColor(theme.switch_disabled)
        elif self.isChecked():
            track_color = QColor(self._checked_track_color or theme.success)
        else:
            track_color = QColor(theme.switch_off)

        painter.setBrush(QBrush(track_color))
        track_rect = self._track_rect()
        if self._has_off_track_border():
            painter.setPen(QPen(QColor(theme.border), self.OFF_TRACK_BORDER_W))
        else:
            painter.setPen(Qt.NoPen)

        radius = track_rect.height() / 2.0
        painter.drawRoundedRect(track_rect, radius, radius)

        painter.setPen(Qt.NoPen)
        thumb_y = self._thumb_y(track_rect)

        painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
        painter.drawEllipse(QRectF(self._thumb_x, thumb_y + 1, self.THUMB_D, self.THUMB_D))
        painter.setBrush(QBrush(QColor(0, 0, 0, 10)))
        painter.drawEllipse(QRectF(self._thumb_x, thumb_y + 2, self.THUMB_D, self.THUMB_D))
        painter.setBrush(QBrush(QColor(0, 0, 0, 5)))
        painter.drawEllipse(QRectF(self._thumb_x, thumb_y + 3, self.THUMB_D, self.THUMB_D))

        painter.setBrush(QBrush(QColor(theme.switch_thumb)))
        painter.drawEllipse(QRectF(self._thumb_x, thumb_y, self.THUMB_D, self.THUMB_D))

    def sizeHint(self) -> QSize:
        return QSize(self.TRACK_W, self.TRACK_H)
