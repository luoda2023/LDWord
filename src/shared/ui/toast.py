"""Toast — 右上角弹出通知控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.tag_chip import TagChip


class Toast(QWidget):
    """右上角弹出通知，自动消失，支持队列堆叠。

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

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 自动关闭定时器
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 图标
        icon_map = {
            "info": "ℹ️",
            "success": "✓",
            "warning": "⚠️",
            "error": "✕",
        }
        self._icon_label = QLabel(icon_map.get(self._variant, "ℹ️"))
        self._icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_label)

        # 消息文本
        self._message_label = QLabel(self._message)
        self._message_label.setWordWrap(False)
        layout.addWidget(self._message_label)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 根据类型选择颜色
        variant_colors = {
            "info": (t.info, t.info_bg),
            "success": (t.success, t.success_bg),
            "warning": (t.warning, t.warning_bg),
            "error": (t.error, t.error_bg),
        }
        accent, bg = variant_colors.get(self._variant, variant_colors["info"])

        self.setStyleSheet(
            f"""
            Toast {{
                background: {bg};
                border: 1px solid {accent};
                border-radius: {t.radius_md}px;
            }}
            """
        )

        self._icon_label.setStyleSheet(
            f"""
            QLabel {{
                color: {accent};
                font-size: 18px;
                font-weight: bold;
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
        self.adjustSize()
        self._position_toast()
        self.show()
        self._timer.start(self._duration)

    def _position_toast(self) -> None:
        """定位通知位置"""
        from src.qt_api import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = 20 + len(Toast._toasts) * (self.height() + 10)
        self.move(x, y)

    def _on_timeout(self) -> None:
        """超时关闭"""
        self.close()
        if self in Toast._toasts:
            Toast._toasts.remove(self)
        self.deleteLater()

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
