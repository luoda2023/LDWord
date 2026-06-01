"""
main_window — 主窗口壳

职责：布局 + 面板注册 + 生命周期。
圆角 + 边框 + 阴影（参照 Card 组件的 QSS + Shadow 实现）。

在 Windows 上使用 WM_NCCALCSIZE 实现真正的无边框窗口，
保留 DWM 原生最大化/还原动画和系统快捷键。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys

from src.app_meta import APP_DISPLAY_NAME_FULL
from src.qt_api import (
    QApplication,
    QColor,
    QCursor,
    QEvent,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.bridge import PanelBridge
from src.ui.panel_registry import PANEL_SPECS, create_panel
from src.ui.sidebar import Sidebar
from src.ui.title_bar import TitleBar


logger = logging.getLogger(__name__)


def _log_close_handling_failure(action: str, exc: Exception) -> None:
    logger.warning(
        "Main window ignored %s failure during close handling: %s",
        action,
        exc,
        exc_info=exc,
    )

# ── Win32 常量 ──
if sys.platform == "win32":
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi

    GWL_STYLE = -16
    WS_THICKFRAME = 0x00040000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    WS_CAPTION = 0x00C00000
    WM_NCCALCSIZE = 0x0083
    WM_NCHITTEST = 0x0084
    SWP_FRAMECHANGED = 0x0020
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004

    # DWM 属性
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWCP_DONOTROUND = 1

    class MARGINS(ctypes.Structure):
        _fields_ = [
            ("cxLeftWidth", ctypes.c_int),
            ("cxRightWidth", ctypes.c_int),
            ("cyTopHeight", ctypes.c_int),
            ("cyBottomHeight", ctypes.c_int),
        ]


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
            f"font-size: {t.font_size_xl}px; color: {t.text_hint};"
        )
        self.setStyleSheet(
            f"background: {t.bg_window}; border-bottom-right-radius: {t.shell_radius}px;"
        )


class MainWindow(QMainWindow):
    """Alavette Form V1.0 主窗口。"""

    WINDOW_TITLE = APP_DISPLAY_NAME_FULL
    MIN_WIDTH = 800
    MIN_HEIGHT = 540
    SHADOW_MARGIN = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        target_screen = QApplication.screenAt(QCursor.pos())
        if target_screen is None:
            target_screen = QApplication.primaryScreen()
        screen = target_screen.availableGeometry()
        w = min(1200, int(screen.width() * 0.6))
        h = min(800, int(screen.height() * 0.7))
        sm = self.SHADOW_MARGIN
        self.setMinimumSize(
            min(self.MIN_WIDTH, screen.width() - 100),
            min(self.MIN_HEIGHT, screen.height() - 100),
        )
        self.resize(w + sm * 2, h + sm * 2)
        self.move(
            screen.x() + (screen.width() - w) // 2 - sm,
            screen.y() + (screen.height() - h) // 2 - sm,
        )

        shell = QWidget()
        shell.setObjectName("main_shell")
        self.setCentralWidget(shell)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(sm, sm, sm, sm)
        shell_layout.setSpacing(0)

        self._container = RoundedSurfaceFrame(parent=shell)
        self._container.setObjectName("window_container")

        self._shadow = QGraphicsDropShadowEffect(self._container)
        self._container.setGraphicsEffect(self._shadow)

        shell_layout.addWidget(self._container)

        self.bridge = PanelBridge(self)
        self.title_bar = TitleBar(self, self._container)
        self.sidebar = Sidebar(self.bridge, self._container)

        self.panel_stack = QStackedWidget(self._container)
        self.panel_stack.setObjectName("main_panel_stack")
        self.panel_stack.setFrameShape(QFrame.NoFrame)
        self._loaded_panel_indexes: set[int] = set()
        for index, spec in enumerate(PANEL_SPECS):
            if index == 0:
                panel = create_panel(spec.id, self.bridge) or _PlaceholderPanel(spec.title)
                self._loaded_panel_indexes.add(index)
            else:
                panel = _PlaceholderPanel(spec.title)
            self.panel_stack.addWidget(panel)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        container_layout.addWidget(self.title_bar)

        body = QWidget(self._container)
        body.setObjectName("main_body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.panel_stack, 1)
        container_layout.addWidget(body, 1)

        self.sidebar.panel_selected.connect(self._show_panel)
        self.bridge.navigate_to_panel.connect(self._navigate)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 在 Windows 上安装 DWM 原生框架支持
        if sys.platform == "win32":
            self._install_native_frame()

        # 窗口首次显示后，在事件循环空闲时逐个预加载剩余面板
        self._preload_queue = [i for i in range(len(PANEL_SPECS)) if i not in self._loaded_panel_indexes]
        QTimer.singleShot(0, self._preload_next)

    def _install_native_frame(self) -> None:
        """恢复 WS_THICKFRAME 等原生窗口样式以获得 DWM 动画。"""
        hwnd = int(self.winId())

        # 读取当前样式，加上厚边框 + 最大/最小化 + 标题栏（供 DWM 识别）
        style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        style |= WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_CAPTION
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)

        # 扩展客户区到整个窗口 — 这让 DWM 认为窗口有框架但实际不绘制
        margins = MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        # 通知系统框架已改变
        user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )

        # Win11: 禁用系统圆角（我们自己管理圆角）
        try:
            corner_pref = ctypes.c_int(DWMWCP_DONOTROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner_pref), ctypes.sizeof(corner_pref),
            )
        except Exception:
            pass  # Win10 不支持此属性

    def nativeEvent(self, event_type, message):
        """处理 WM_NCCALCSIZE：让客户区覆盖整个窗口。"""
        if sys.platform != "win32":
            return super().nativeEvent(event_type, message)

        msg = wt.MSG.from_address(int(message))

        if msg.message == WM_NCCALCSIZE:
            # 返回 0 + 不修改 RECT = 客户区 == 窗口区（无标题栏/边框）
            return True, 0

        return super().nativeEvent(event_type, message)

    def changeEvent(self, event):
        """窗口状态变化时刷新视觉样式。"""
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._refresh_window_visuals()

    def _refresh_window_visuals(self):
        """根据当前是否最大化来切换视觉样式。"""
        if self.isMaximized():
            self._apply_maximized_visuals()
        else:
            self._apply_normal_visuals()
        # 通知标题栏更新图标
        if hasattr(self, 'title_bar'):
            self.title_bar._update_icons()

    def _navigate(self, index: int) -> None:
        self._show_panel(index)
        self.sidebar.select(index)

    def _show_panel(self, index: int) -> None:
        if not 0 <= index < self.panel_stack.count():
            return
        self._ensure_panel_loaded(index)
        self.panel_stack.setCurrentIndex(index)

    def _ensure_panel_loaded(self, index: int) -> QWidget:
        if index in self._loaded_panel_indexes:
            return self.panel_stack.widget(index)

        spec = PANEL_SPECS[index]
        panel = create_panel(spec.id, self.bridge)
        self._loaded_panel_indexes.add(index)
        if panel is None:
            return self.panel_stack.widget(index)

        old = self.panel_stack.widget(index)
        self.panel_stack.removeWidget(old)
        old.deleteLater()
        self.panel_stack.insertWidget(index, panel)

        # 从预加载队列中移除（如果还在的话）
        if hasattr(self, "_preload_queue") and index in self._preload_queue:
            self._preload_queue.remove(index)

        return panel

    def _preload_next(self) -> None:
        """在事件循环空闲时逐个创建面板，避免切换时卡顿。"""
        if not hasattr(self, "_preload_queue"):
            return
        while self._preload_queue:
            index = self._preload_queue.pop(0)
            if index in self._loaded_panel_indexes:
                continue
            self._ensure_panel_loaded(index)
            # 强制面板完成首次布局和渲染，避免用户切换时才触发
            self._warmup_panel(index)
            QTimer.singleShot(0, self._preload_next)
            return

    def _warmup_panel(self, index: int) -> None:
        """让面板做一次完整的 show→layout→hide，刷掉首次渲染开销。"""
        panel = self.panel_stack.widget(index)
        if panel is None:
            return
        saved_index = self.panel_stack.currentIndex()
        self.panel_stack.setCurrentIndex(index)
        panel.show()
        QApplication.processEvents()
        if saved_index != index:
            self.panel_stack.setCurrentIndex(saved_index)

    def _apply_theme(self) -> None:
        t = get_theme()

        self.setStyleSheet(
            """
            QMainWindow { background: transparent; }
            #main_shell { background: transparent; }
            """
        )

        if self.isMaximized():
            self._apply_maximized_visuals()
        else:
            self._container.configure_surface(
                background=t.bg_window,
                radius=t.shell_radius,
                border_color=t.border,
                border_width=1.0,
            )
            cl = self._container.layout()
            if cl is not None:
                cl.setContentsMargins(1, 1, 1, 1)
        self._shadow.setBlurRadius(16)
        self._shadow.setColor(QColor(0, 0, 0, 35))
        self._shadow.setOffset(0, 2)

    def _apply_maximized_visuals(self):
        shell = self.centralWidget()
        if shell:
            shell.layout().setContentsMargins(0, 0, 0, 0)
        self._container.configure_surface(
            background=get_theme().bg_window,
            radius=0,
        )
        cl = self._container.layout()
        if cl is not None:
            cl.setContentsMargins(0, 0, 0, 0)

    def _apply_normal_visuals(self):
        shell = self.centralWidget()
        if shell:
            m = self.SHADOW_MARGIN
            shell.layout().setContentsMargins(m, m, m, m)
        theme = get_theme()
        self._container.configure_surface(
            background=theme.bg_window,
            radius=theme.shell_radius,
            border_color=theme.border,
            border_width=1.0,
        )
        cl = self._container.layout()
        if cl is not None:
            cl.setContentsMargins(1, 1, 1, 1)

    def closeEvent(self, event) -> None:
        stack = getattr(self, "panel_stack", None)
        if stack is not None:
            try:
                count = int(stack.count())
            except Exception as exc:
                _log_close_handling_failure("panel stack count", exc)
                count = 0
            for index in range(count):
                panel = stack.widget(index)
                shutdown = getattr(panel, "shutdown_active_execution", None)
                if not callable(shutdown):
                    continue
                try:
                    ok = bool(shutdown(timeout_ms=1000))
                except TypeError:
                    try:
                        ok = bool(shutdown())
                    except Exception as exc:
                        _log_close_handling_failure(f"panel shutdown fallback at index {index}", exc)
                        ok = False
                except Exception as exc:
                    _log_close_handling_failure(f"panel shutdown at index {index}", exc)
                    ok = False
                if not ok:
                    event.ignore()
                    return
        super().closeEvent(event)

    def register_panel(self, index: int, panel: QWidget) -> None:
        old = self.panel_stack.widget(index)
        self.panel_stack.removeWidget(old)
        old.deleteLater()
        self.panel_stack.insertWidget(index, panel)
        if hasattr(self, "_loaded_panel_indexes"):
            self._loaded_panel_indexes.add(index)
