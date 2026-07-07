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
    Signal,
)

from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.bridge import NavigationIntent, PanelBridge, navigation_intent_value
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
        self._title = title
        layout = QVBoxLayout(self)
        self._label = QLabel(f"{title}\n\n暂未开放")
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_loading(self, title: str | None = None) -> None:
        label = str(title or self._title or "").strip() or "页面"
        self._label.setText(f"{label}\n\n正在加载...")

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

    startup_status_changed = Signal(str)
    startup_ready = Signal()

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
        self.bridge.navigate_to_intent.connect(self._navigate_intent)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 在 Windows 上安装 DWM 原生框架支持
        if sys.platform == "win32":
            self._install_native_frame()

        # 窗口首次显示后，在事件循环空闲时逐个预加载剩余面板
        preload_priority = {
            "template": 0,
            "theme": 1,
            "scene": 2,
            "assets": 3,
            "pipeline": 4,
            "preferences": 5,
        }
        background_preload_panel_ids = {"template", "theme", "scene"}
        self._preload_queue = sorted(
            [
                i
                for i in range(len(PANEL_SPECS))
                if i not in self._loaded_panel_indexes
                and PANEL_SPECS[i].id in background_preload_panel_ids
            ],
            key=lambda i: preload_priority.get(PANEL_SPECS[i].id, i),
        )
        self._startup_ready_emitted = False
        self._startup_detail_preload_done = False
        self._idle_preload_started = False
        self._idle_preload_delay_ms = 240
        self._async_panel_load_ids = {"assets"}
        self._async_panel_loads_in_progress: set[int] = set()
        QTimer.singleShot(0, self._emit_startup_ready)

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

    def _navigate_intent(self, intent) -> None:
        panel_index = self._panel_index_from_intent(intent)
        if panel_index < 0:
            return
        panel = self._show_panel(panel_index, allow_async=False)
        self.sidebar.select(panel_index)
        if panel is not None and hasattr(panel, "handle_navigation_intent"):
            panel.handle_navigation_intent(intent)

    def _panel_index_from_intent(self, intent) -> int:
        panel_index = int(self._intent_value(intent, "panel_index", -1) or -1)
        if panel_index >= 0:
            return panel_index
        panel_id = str(self._intent_value(intent, "panel_id", "") or "").strip()
        if not panel_id:
            return -1
        for index, spec in enumerate(PANEL_SPECS):
            if spec.id == panel_id:
                return index
        return -1

    @staticmethod
    def _intent_value(intent, key: str, default=None):
        return navigation_intent_value(intent, key, default)

    def _show_panel(self, index: int, *, allow_async: bool = True) -> QWidget | None:
        if not 0 <= index < self.panel_stack.count():
            return None
        if (
            allow_async
            and index not in self._loaded_panel_indexes
            and PANEL_SPECS[index].id in self._async_panel_load_ids
        ):
            placeholder = self.panel_stack.widget(index)
            if hasattr(placeholder, "set_loading"):
                placeholder.set_loading(PANEL_SPECS[index].title)
            self.panel_stack.setCurrentIndex(index)
            if index not in self._async_panel_loads_in_progress:
                self._async_panel_loads_in_progress.add(index)
                QTimer.singleShot(
                    60,
                    lambda panel_index=index: self._finish_async_panel_load(panel_index),
                )
            return placeholder
        panel = self._ensure_panel_loaded(index)
        self.panel_stack.setCurrentIndex(index)
        return panel

    def _finish_async_panel_load(self, index: int) -> None:
        try:
            if not 0 <= index < self.panel_stack.count():
                return
            spec = PANEL_SPECS[index]
            self.startup_status_changed.emit(f"加载{spec.title}")
            QApplication.processEvents()
            should_show_loaded_panel = self.panel_stack.currentIndex() == index
            panel = self._ensure_panel_loaded(index)
            if should_show_loaded_panel:
                self.panel_stack.setCurrentIndex(index)
                panel.updateGeometry()
        finally:
            self._async_panel_loads_in_progress.discard(index)

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
        if self._preload_next_startup_detail():
            self._schedule_idle_preload(self._idle_preload_delay_ms)
            return
        while self._preload_queue:
            index = self._preload_queue.pop(0)
            if index in self._loaded_panel_indexes:
                continue
            spec = PANEL_SPECS[index]
            self.startup_status_changed.emit(f"后台加载{spec.title}")
            QApplication.processEvents()
            self._ensure_panel_loaded(index)
            self._schedule_idle_preload(self._idle_preload_delay_ms)
            return

    def _preload_next_startup_detail(self) -> bool:
        if getattr(self, "_startup_detail_preload_done", False):
            return False
        found_preloader = False
        for index in sorted(self._loaded_panel_indexes):
            panel = self.panel_stack.widget(index)
            preload = getattr(panel, "preload_one_detail_for_startup", None)
            if not callable(preload):
                continue
            found_preloader = True
            if preload(self.startup_status_changed.emit):
                self._startup_detail_preload_done = False
                return True
        if found_preloader:
            self._startup_detail_preload_done = True
        return False

    def _schedule_idle_preload(self, delay_ms: int | None = None) -> None:
        self._idle_preload_started = True
        delay = self._idle_preload_delay_ms if delay_ms is None else int(delay_ms)
        QTimer.singleShot(max(0, delay), self._preload_next)

    def _emit_startup_ready(self) -> None:
        if getattr(self, "_startup_ready_emitted", False):
            return
        self._startup_ready_emitted = True
        self.startup_status_changed.emit("启动完成")
        self.panel_stack.setCurrentIndex(0)
        self._prepare_initial_panel_for_show()
        self.startup_ready.emit()
        self._schedule_idle_preload(900)

    def _prepare_initial_panel_for_show(self) -> None:
        panel = self.panel_stack.widget(0)
        if panel is None:
            return
        self.startup_status_changed.emit("正在整理首页")
        panel.show()
        for widget in (self.centralWidget(), self._container, self.panel_stack, panel):
            if widget is None:
                continue
            widget.updateGeometry()
            layout = widget.layout()
            if layout is not None:
                layout.activate()
        QApplication.processEvents()
        for widget in (self.centralWidget(), self._container, self.panel_stack, panel):
            if widget is None:
                continue
            layout = widget.layout()
            if layout is not None:
                layout.activate()

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
