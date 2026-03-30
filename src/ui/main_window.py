"""
main_window — 主窗口壳

职责：布局 + 面板注册 + 生命周期。不超过 200 行。
"""

from __future__ import annotations

from src.qt_api import QApplication, QCursor, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget, Qt

from src.shared.ui.theme import get_theme, bind_theme
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import PANEL_SPECS, create_panel
from src.ui.sidebar import Sidebar
from src.ui.title_bar import TitleBar


def _set_title_bar_color(hwnd: int, color_hex: str) -> None:
    """Windows DWM API — 设置标题栏颜色 (Win11+)。

    静默失败，兼容非 Windows 和旧系统。
    """
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwmapi = ctypes.windll.dwmapi

        # 解析颜色: "#RRGGBB" → Windows COLORREF (0x00BBGGRR)
        r = int(color_hex[1:3], 16)
        g = int(color_hex[3:5], 16)
        b = int(color_hex[5:7], 16)
        colorref = r | (g << 8) | (b << 16)

        # DWMWA_CAPTION_COLOR = 35 (Windows 11 22000+)
        color_val = ctypes.c_int(colorref)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(color_val), ctypes.sizeof(color_val))

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        # 当背景较暗时启用暗色标题栏文字
        is_dark = (r * 0.299 + g * 0.587 + b * 0.114) < 128
        dark_val = ctypes.c_int(1 if is_dark else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(dark_val), ctypes.sizeof(dark_val))
    except Exception:
        pass


class _PlaceholderPanel(QWidget):
    """占位面板 — 面板未实现时显示。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._label = QLabel(f"{title}\n\n面板开发中...")
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"font-size: {t.font_size_xl}px; color: {t.text_hint};")
        self.setStyleSheet(
            f"background: {t.bg_window};")


class MainWindow(QMainWindow):
    """Lark Formatter V1.0 主窗口。

    三栏布局::

        ┌──────┬──────────────────────────────────┐
        │      │                                  │
        │ 侧边 │        面板区域                   │
        │ 导航 │     (QStackedWidget)              │
        │      │                                  │
        │ 48px │          stretch                  │
        └──────┴──────────────────────────────────┘
    """

    WINDOW_TITLE = "Lark Formatter V1.0"
    MIN_WIDTH = 800
    MIN_HEIGHT = 540

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setWindowFlags(Qt.FramelessWindowHint)

        # ── 屏幕自适应尺寸（按当前光标所在屏幕）──
        target_screen = QApplication.screenAt(QCursor.pos())
        if target_screen is None:
            target_screen = QApplication.primaryScreen()
        screen = target_screen.availableGeometry()
        w = min(1200, int(screen.width() * 0.6))
        h = min(800, int(screen.height() * 0.7))
        self.setMinimumSize(
            min(self.MIN_WIDTH, screen.width() - 100),
            min(self.MIN_HEIGHT, screen.height() - 100),
        )
        self.resize(w, h)
        self.move(
            screen.x() + (screen.width() - w) // 2,
            screen.y() + (screen.height() - h) // 2,
        )

        # ── 核心对象 ──
        self.bridge = PanelBridge(self)
        self.title_bar = TitleBar(self)
        self.sidebar = Sidebar(self.bridge, self)

        # ── 面板栏 — 从 panel_registry 读取 ──
        self.panel_stack = QStackedWidget()
        for spec in PANEL_SPECS:
            panel = create_panel(spec.id, self.bridge) or _PlaceholderPanel(spec.title)
            self.panel_stack.addWidget(panel)

        # ── 布局: 标题栏(40px) + 下方主体(sidebar | panels) ──
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.panel_stack, 1)
        outer.addWidget(body, 1)

        # ── 信号连接 ──
        self.sidebar.panel_selected.connect(self.panel_stack.setCurrentIndex)
        self.bridge.navigate_to_panel.connect(self._navigate)

        # ── 主题 ──
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _navigate(self, index: int) -> None:
        """通过 bridge 导航到指定面板。"""
        self.panel_stack.setCurrentIndex(index)
        self.sidebar.select(index)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(f"QMainWindow {{ background: {t.bg_window}; }}")
        # 标题栏颜色与侧边栏一致
        _set_title_bar_color(int(self.winId()), t.bg_sidebar)

    def closeEvent(self, event) -> None:
        """Try to shut down active executions owned by panels before allowing the window to close."""
        stack = getattr(self, "panel_stack", None)
        if stack is not None:
            try:
                count = int(stack.count())
            except Exception:
                count = 0
            for index in range(count):
                panel = stack.widget(index)
                shutdown = getattr(panel, "shutdown_active_execution", None)
                if not callable(shutdown):
                    continue
                try:
                    ok = bool(shutdown(timeout_ms=1000))
                except TypeError:
                    # Be tolerant of panels that implement a no-arg shutdown method.
                    try:
                        ok = bool(shutdown())
                    except Exception:
                        ok = False
                except Exception:
                    ok = False
                if not ok:
                    event.ignore()
                    return
        super().closeEvent(event)

    def register_panel(self, index: int, panel: QWidget) -> None:
        """用真实面板替换占位面板。"""
        old = self.panel_stack.widget(index)
        self.panel_stack.removeWidget(old)
        old.deleteLater()
        self.panel_stack.insertWidget(index, panel)
