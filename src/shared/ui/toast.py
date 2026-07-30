"""Toast — 窗口右下角弹出通知控件"""

from __future__ import annotations

from shiboken6 import isValid

from src.qt_api import (
    QApplication,
    QColor,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTimer,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme, theme_rgba
from src.shared.ui.icons.catalog import get_icon


_TOAST_ICON_MAP = {
    "info": "info",
    "success": "circle-check",
    "warning": "alert-triangle",
    "error": "circle-x",
}


class Toast(QWidget):
    """窗口右下角弹出通知，自动消失，支持队列堆叠。

    用法::

        # 显示通知
        Toast.show_info("操作成功")
        Toast.show_success("保存成功")
        Toast.show_warning("请注意")
        Toast.show_error("操作失败")

        # 自定义持续时间
        Toast.show_info("这条消息会显示 5 秒", duration=5000)
    """

    _instance = None
    _toasts = []
    _edge_margin = 24
    _bottom_reserved_margin = 44
    _stack_gap = 10
    _shadow_margin = 10
    _max_width = 460

    def __init__(self, message: str, variant: str = "info", duration: int = 3000):
        """初始化通知。

        Args:
            message: 通知消息
            variant: 类型 (info/success/warning/error)
            duration: 显示时长（毫秒）
        """
        super().__init__()
        self._message = message
        self._variant = variant
        self._duration = duration

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._surface: QFrame
        self._shadow: QGraphicsDropShadowEffect
        self._icon_label: QLabel
        self._message_label: QLabel

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 自动关闭定时器
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(
            self._shadow_margin,
            self._shadow_margin,
            self._shadow_margin,
            self._shadow_margin,
        )
        outer_layout.setSpacing(0)

        self._surface = QFrame(self)
        self._surface.setObjectName("toast_surface")
        self._surface.setAttribute(Qt.WA_StyledBackground)
        outer_layout.addWidget(self._surface)

        self._shadow = QGraphicsDropShadowEffect(self._surface)
        self._surface.setGraphicsEffect(self._shadow)

        layout = QHBoxLayout(self._surface)
        layout.setContentsMargins(16, 12, 18, 12)
        layout.setSpacing(10)

        # 图标使用项目统一的 Lucide SVG 资源，不依赖系统 emoji 字体。
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setFixedSize(22, 22)
        layout.addWidget(self._icon_label)

        # 消息文本
        self._message_label = QLabel(self._message)
        self._message_label.setWordWrap(True)
        self._message_label.setMinimumWidth(120)
        self._message_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        layout.addWidget(self._message_label, 1)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 卡片统一使用半透明的中性玻璃底，状态色只用于图标。
        variant_accents = {
            "info": t.info,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
        }
        accent = variant_accents.get(self._variant, variant_accents["info"])
        glass_bg = theme_rgba(t.bg_card, 0.82)
        icon_name = _TOAST_ICON_MAP.get(self._variant, _TOAST_ICON_MAP["info"])
        self._icon_label.setPixmap(get_icon(icon_name, 20, accent).pixmap(20, 20))

        self.setStyleSheet(
            f"""
            Toast {{
                background: transparent;
                border: none;
            }}
            QFrame#toast_surface {{
                background: {glass_bg};
                border: none;
                border-radius: {t.radius_lg}px;
            }}
            """
        )
        self._shadow.setBlurRadius(max(18, int(t.shadow_blur_md)))
        self._shadow.setColor(QColor(15, 23, 42, 36))
        self._shadow.setOffset(0, max(4, int(t.shadow_offset_y)))

        self._icon_label.setStyleSheet(
            """
            QLabel {{
                background: transparent;
                border: none;
            }}
            """
        )

        self._message_label.setStyleSheet(
            f"""
            QLabel {{
                color: {t.text_primary};
                font-size: {t.font_size_md}px;
                background: transparent;
                border: none;
            }}
            """
        )

    def show_toast(self) -> None:
        """显示通知"""
        anchor = self._anchor_geometry()
        self._constrain_to_anchor(anchor)
        self.adjustSize()
        self._position_toast(anchor)
        self.show()
        self._timer.start(self._duration)

    def _constrain_to_anchor(self, anchor) -> None:
        # QSS font sizes are resolved lazily; polish before measuring or the
        # pre-show default font can make the label a few pixels too narrow.
        self._message_label.ensurePolished()
        available_width = max(180, anchor.width() - self._edge_margin * 2)
        max_width = min(self._max_width, available_width)
        surface_width = max(160, max_width - self._shadow_margin * 2)
        message_max_width = max(120, surface_width - 66)
        text_lines = self._message.splitlines() or [""]
        natural_message_width = max(
            self._message_label.fontMetrics().horizontalAdvance(line)
            for line in text_lines
        ) + 2
        message_width = max(120, min(natural_message_width, message_max_width))
        should_wrap = len(text_lines) > 1 or natural_message_width > message_max_width

        self.setMaximumWidth(max_width)
        self._surface.setMaximumWidth(surface_width)
        self._message_label.setFixedWidth(message_width)
        self._message_label.setWordWrap(should_wrap)

    def _position_toast(self, anchor=None) -> None:
        """定位通知位置"""
        if anchor is None:
            anchor = self._anchor_geometry()
        stack_offset = self._stack_offset()
        x = anchor.x() + anchor.width() - self.width() - self._edge_margin
        y = (
            anchor.y()
            + anchor.height()
            - self.height()
            - self._edge_margin
            - self._bottom_reserved_margin
            - stack_offset
        )
        x = max(anchor.x() + self._edge_margin, x)
        y = max(anchor.y() + self._edge_margin, y)
        self.move(x, y)

    def _stack_offset(self) -> int:
        offset = 0
        for toast in Toast._live_toasts():
            if toast is self:
                break
            if toast.isVisible():
                offset += toast.height() + self._stack_gap
        return offset

    @classmethod
    def _live_toasts(cls) -> tuple["Toast", ...]:
        cls._toasts = [toast for toast in cls._toasts if isValid(toast)]
        return tuple(cls._toasts)

    def _anchor_geometry(self):
        active = QApplication.activeWindow()
        if active is not None and not isinstance(active, Toast) and active.isVisible():
            return active.geometry()

        candidates = [
            widget
            for widget in QApplication.topLevelWidgets()
            if widget.isVisible() and not isinstance(widget, Toast)
        ]
        if candidates:
            host = max(candidates, key=lambda widget: widget.width() * widget.height())
            return host.geometry()

        screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else self.geometry()

    def _on_timeout(self) -> None:
        """超时关闭"""
        self.close()
        self.deleteLater()

    def closeEvent(self, event) -> None:
        """Drop manual closes from the global stack before Qt can delete them."""

        self._timer.stop()
        if self in Toast._toasts:
            Toast._toasts.remove(self)
        super().closeEvent(event)

    @staticmethod
    def show_info(message: str, duration: int = 3000) -> None:
        """显示信息通知"""
        toast = Toast(message, "info", duration)
        Toast._toasts.append(toast)
        toast.show_toast()

    @staticmethod
    def show_success(message: str, duration: int = 3000) -> None:
        """显示成功通知"""
        toast = Toast(message, "success", duration)
        Toast._toasts.append(toast)
        toast.show_toast()

    @staticmethod
    def show_warning(message: str, duration: int = 3000) -> None:
        """显示警告通知"""
        toast = Toast(message, "warning", duration)
        Toast._toasts.append(toast)
        toast.show_toast()

    @staticmethod
    def show_error(message: str, duration: int = 3000) -> None:
        """显示错误通知"""
        toast = Toast(message, "error", duration)
        Toast._toasts.append(toast)
        toast.show_toast()
