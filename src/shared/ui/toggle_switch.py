"""
toggle_switch — 胶囊开关控件

ON/OFF 自定义绘制的胶囊形状开关。
颜色从全局主题动态读取，主题切换时自动刷新。
"""

from __future__ import annotations

from src.qt_api import QAbstractButton, QBrush, QColor, QPainter, QPen, QPropertyAnimation, QRectF, QSize, Signal, Property, Qt

from src.shared.ui.theme import get_theme, bind_theme


class ToggleSwitch(QAbstractButton):
    """胶囊形状的 ON/OFF 开关控件。

    Signals:
        toggled(bool): 状态变化信号
    """

    toggled_signal = Signal(bool)

    # ── 尺寸 ──
    TRACK_W = 44
    TRACK_H = 24
    THUMB_D = 18
    THUMB_MARGIN = 3

    def __init__(self, parent=None, *, checked: bool = False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._thumb_x = float(self.TRACK_W - self.THUMB_D - self.THUMB_MARGIN if checked
                              else self.THUMB_MARGIN)

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(250)

        self.clicked.connect(self._on_click)
        self.setFixedSize(self.sizeHint())

        # 主题切换时自动刷新
        bind_theme(self, self.update)

    # ── 动画属性 ──
    @Property(float)
    def thumb_position(self) -> float:
        return self._thumb_x

    @thumb_position.setter
    def thumb_position(self, val: float) -> None:
        self._thumb_x = val
        self.update()

    # ── 事件 ──
    def _on_click(self) -> None:
        checked = self.isChecked()
        end = (self.TRACK_W - self.THUMB_D - self.THUMB_MARGIN
               if checked else self.THUMB_MARGIN)
        self._anim.stop()
        self._anim.setStartValue(self._thumb_x)
        self._anim.setEndValue(end)
        self._anim.start()
        self.toggled_signal.emit(checked)

    # ── 绘制 ──
    def paintEvent(self, event) -> None:
        t = get_theme()  # 每次绘制时动态取色
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # 轨道
        if not self.isEnabled():
            track_color = QColor(t.switch_disabled)
        elif self.isChecked():
            track_color = QColor(t.success)  # macOS uses green for switches
        else:
            track_color = QColor(t.switch_off)

        p.setBrush(QBrush(track_color))
        # OFF 状态增加极其轻微的边框勾勒
        if not self.isChecked() and self.isEnabled():
            p.setPen(QPen(QColor(t.border), 1))
        else:
            p.setPen(Qt.NoPen)
            
        p.drawRoundedRect(QRectF(0, 0, self.TRACK_W, self.TRACK_H),
                          self.TRACK_H / 2, self.TRACK_H / 2)

        p.setPen(Qt.NoPen)
        # 滑块和柔软阴影 (Soft Shadow)
        thumb_y = (self.TRACK_H - self.THUMB_D) / 2
        
        p.setBrush(QBrush(QColor(0, 0, 0, 20)))
        p.drawEllipse(QRectF(self._thumb_x, thumb_y + 1, self.THUMB_D, self.THUMB_D))
        p.setBrush(QBrush(QColor(0, 0, 0, 10)))
        p.drawEllipse(QRectF(self._thumb_x, thumb_y + 2, self.THUMB_D, self.THUMB_D))
        p.setBrush(QBrush(QColor(0, 0, 0, 5)))
        p.drawEllipse(QRectF(self._thumb_x, thumb_y + 3, self.THUMB_D, self.THUMB_D))
        
        p.setBrush(QBrush(QColor(t.switch_thumb)))
        p.drawEllipse(QRectF(self._thumb_x, thumb_y, self.THUMB_D, self.THUMB_D))

    def sizeHint(self) -> QSize:
        return QSize(self.TRACK_W, self.TRACK_H)

