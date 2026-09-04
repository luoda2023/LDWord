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
from pathlib import Path

from src.app_meta import APP_DISPLAY_NAME_FULL
from src.qt_api import (
    QApplication,
    QColor,
    QCursor,
    QEvent,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.theme import bind_theme, get_theme
from src.config.library import (
    get_scene_entry,
    get_template_entry,
    load_scene_from_library,
    load_template_from_library,
)
from src.config.loader import load_template
from src.config.work_mode import get_work_mode
from src.ui.bridge import PanelBridge, navigation_intent_value
from src.ui.panel_loading import PanelLoadState
from src.ui.panel_registry import create_panel
from src.ui.panel_specs import PANEL_SPECS
from src.ui.sidebar import Sidebar
from src.ui.template_import_coordinator import TemplateImportCoordinator
from src.ui.title_bar import TitleBar
from src.ui.workspace_preferences import (
    ModeWorkspacePreferences,
    WorkspacePreferenceStore,
)


logger = logging.getLogger("ldword.gui.main_window")


WORK_MODE_DIRTY_SAVE = "save"
WORK_MODE_DIRTY_DISCARD = "discard"
WORK_MODE_DIRTY_CANCEL = "cancel"


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

    retry_requested = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addStretch()
        self._label = QLabel(f"{title}\n\n暂未开放")
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)
        self._retry_button = QPushButton("重试", self)
        self._retry_button.setFixedWidth(104)
        self._retry_button.setVisible(False)
        self._retry_button.clicked.connect(self.retry_requested.emit)
        layout.addWidget(self._retry_button, 0, Qt.AlignHCenter)
        layout.addStretch()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_loading(self, title: str | None = None) -> None:
        label = str(title or self._title or "").strip() or "页面"
        self._label.setText(f"{label}\n\n正在打开...")
        self._retry_button.setVisible(False)

    def set_unloaded(self) -> None:
        self._label.setText(f"{self._title}\n\n暂未加载")
        self._retry_button.setVisible(False)

    def set_failed(self, error: str = "") -> None:
        self._label.setText(f"{self._title}\n\n打开失败")
        diagnostic = str(error or "").strip()
        self.setToolTip(diagnostic)
        self.setAccessibleDescription(diagnostic)
        self._retry_button.setVisible(True)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"font-size: {t.font_size_xl}px; color: {t.text_hint};"
        )
        self._retry_button.setStyleSheet(
            f"""
            QPushButton {{
                min-height: 32px;
                color: {t.primary};
                background: {t.bg_card};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background: {t.primary_light}; }}
            """
        )
        self.setStyleSheet(
            f"background: {t.bg_window}; border-bottom-right-radius: {t.shell_radius}px;"
        )


class MainWindow(QMainWindow):
    """LDWord V1.0 主窗口。"""

    startup_status_changed = Signal(str)
    startup_ready = Signal()
    panel_load_state_changed = Signal(str, str)

    WINDOW_TITLE = APP_DISPLAY_NAME_FULL
    MIN_WIDTH = 800
    MIN_HEIGHT = 540
    SHADOW_MARGIN = 12

    def __init__(
        self,
        parent=None,
        *,
        enable_background_services: bool = False,
        workspace_preference_store: WorkspacePreferenceStore | None = None,
    ):
        super().__init__(parent)
        self._close_accepted = False
        self._panel_specs = PANEL_SPECS
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
        shell_layout = QGridLayout(shell)
        shell_layout.setContentsMargins(sm, sm, sm, sm)
        shell_layout.setSpacing(0)

        # The shadow source is a background-only sibling. Applying a graphics
        # effect to the content container would rasterize the complete UI tree.
        self._shadow_surface = RoundedSurfaceFrame(parent=shell)
        self._shadow_surface.setObjectName("window_shadow_surface")
        self._shadow_surface.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        shell_layout.addWidget(self._shadow_surface, 0, 0)

        self._container = RoundedSurfaceFrame(parent=shell)
        self._container.setObjectName("window_container")

        self._shadow = QGraphicsDropShadowEffect(self._shadow_surface)
        self._shadow_surface.setGraphicsEffect(self._shadow)

        shell_layout.addWidget(self._container, 0, 0)
        self._shadow_surface.stackUnder(self._container)

        self._workspace_preferences = (
            workspace_preference_store or WorkspacePreferenceStore()
        )
        self._workspace_preference_state = self._workspace_preferences.load()
        self.bridge = PanelBridge(
            self,
            workspace_preference_store=self._workspace_preferences,
        )
        self._restore_persisted_workspace()
        self._background_services_enabled = bool(enable_background_services)
        self._template_import_coordinator = TemplateImportCoordinator(parent=self)
        self._template_import_coordinator.batch_processed.connect(
            self._on_template_import_batch_processed
        )
        self._template_import_coordinator.monitoring_error.connect(
            self._on_template_import_monitoring_error
        )
        self._active_work_mode_id = self.bridge.current_work_mode_id()
        self.title_bar = TitleBar(
            self,
            self._container,
            self.bridge,
            work_mode_change_handler=self._request_work_mode_change,
        )
        self.sidebar = Sidebar(
            self.bridge,
            self._container,
            panel_specs=self._panel_specs,
        )

        self.panel_stack = QStackedWidget(self._container)
        self.panel_stack.setObjectName("main_panel_stack")
        self.panel_stack.setFrameShape(QFrame.NoFrame)
        self._loaded_panel_indexes: set[int] = set()
        self._panel_load_states: dict[int, PanelLoadState] = {}
        self._panel_load_errors: dict[int, str] = {}
        self._pending_panel_intents: dict[int, object] = {}
        self._panel_placeholders: dict[int, _PlaceholderPanel] = {}
        self._panel_load_timers: dict[int, QTimer] = {}
        for index, spec in enumerate(self._panel_specs):
            if index == 0:
                panel = create_panel(spec.id, self.bridge)
                self._loaded_panel_indexes.add(index)
                self._panel_load_states[index] = PanelLoadState.READY
            else:
                panel = _PlaceholderPanel(spec.title)
                panel.set_unloaded()
                panel.retry_requested.connect(
                    lambda _checked=False, target=index: self._request_panel_load(target)
                )
                self._panel_placeholders[index] = panel
                self._panel_load_states[index] = PanelLoadState.UNLOADED
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
        self.bridge.work_mode_changed.connect(self._on_work_mode_changed)
        self.bridge.scene_changed.connect(self._persist_current_scene_preference)
        self.bridge.template_changed.connect(
            self._persist_current_template_preference
        )
        self.bridge.official_document_type_changed.connect(
            self._persist_official_document_type_preference
        )
        self.bridge.material_scope_suspended.connect(
            self._on_material_scope_suspended
        )
        self.bridge.navigate_to_panel.connect(self._navigate)
        self.bridge.navigate_to_intent.connect(self._navigate_intent)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

        # 在 Windows 上安装 DWM 原生框架支持
        if sys.platform == "win32":
            self._install_native_frame()

        self._startup_ready_emitted = False
        self._panel_loads_in_progress: set[int] = set()

        self._startup_ready_timer = QTimer(self)
        self._startup_ready_timer.setSingleShot(True)
        self._startup_ready_timer.timeout.connect(self._emit_startup_ready)

        self._startup_ready_timer.start(0)

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
        if self.panel_stack.currentIndex() == index:
            self.sidebar.select(index)

    def _restore_persisted_workspace(self) -> None:
        """Restore durable identities before the first panel is constructed."""

        state = self._workspace_preference_state
        mode = get_work_mode(state.active_mode_id)
        if mode is None:
            mode = self.bridge.current_work_mode()
        self.bridge.set_current_work_mode(mode, emit_signal=False)
        try:
            self._activate_persisted_mode_state(mode, emit_signal=False)
            self.bridge.commit_pending_work_mode_transition()
        except Exception as exc:
            logger.warning(
                "Main window ignored persisted workspace restore failure for %s: %s",
                getattr(mode, "mode_id", ""),
                exc,
                exc_info=exc,
            )

    def _activate_persisted_mode_state(self, mode, *, emit_signal: bool) -> None:
        mode_id = str(getattr(mode, "mode_id", "") or "").strip()
        preference = self._workspace_preferences.load().for_mode(mode_id)
        scene_id = str(
            getattr(preference, "scene_id", "")
            or getattr(mode, "default_scene_id", "")
            or ""
        ).strip()
        if not scene_id:
            raise ValueError("work mode missing default_scene_id")

        try:
            scene_entry = get_scene_entry(scene_id, mode_id=mode_id)
            scene = load_scene_from_library(scene_id, mode_id=mode_id)
        except Exception:
            fallback_scene_id = str(
                getattr(mode, "default_scene_id", "") or ""
            ).strip()
            if not fallback_scene_id or fallback_scene_id == scene_id:
                raise
            scene_id = fallback_scene_id
            scene_entry = get_scene_entry(scene_id, mode_id=mode_id)
            scene = load_scene_from_library(scene_id, mode_id=mode_id)

        template, template_id, template_path, template_source, template_source_type = (
            self._resolve_persisted_template(mode_id, scene, preference)
        )
        self.bridge.set_current_scene(
            scene,
            config_id=scene_id,
            path=str(scene_entry.path) if scene_entry is not None else "",
            source="library" if scene_entry is not None else "builtin",
            source_type=scene_entry.source_type if scene_entry is not None else "builtin",
            emit_signal=emit_signal,
        )
        self.bridge.set_current_template(
            template,
            config_id=template_id,
            path=template_path,
            source=template_source,
            source_type=template_source_type,
            emit_signal=emit_signal,
        )
        document_type_id = str(
            getattr(preference, "official_document_type_id", "") or "notice"
        ).strip()
        self.bridge.set_current_official_document_type_id(
            document_type_id,
            source="persisted",
            emit_signal=emit_signal,
        )
        self.bridge.clear_scene_dirty(emit_signal=emit_signal)
        if (
            not hasattr(self, "panel_stack")
            or self._loaded_panel_for_id("template") is None
        ):
            self.bridge.clear_template_dirty(emit_signal=emit_signal)

    @staticmethod
    def _empty_mode_preference() -> ModeWorkspacePreferences:
        return ModeWorkspacePreferences()

    def _resolve_persisted_template(self, mode_id: str, scene, preference):
        selected = preference or self._empty_mode_preference()
        template_id = str(
            selected.template_id or getattr(scene, "template_id", "") or ""
        ).strip()
        if template_id:
            entry = get_template_entry(template_id, mode_id=mode_id)
            if entry is not None and entry.is_available:
                return (
                    load_template_from_library(template_id, mode_id=mode_id),
                    template_id,
                    str(entry.path),
                    "library",
                    entry.source_type,
                )

        external_path = Path(str(selected.template_path or "").strip())
        if selected.template_source_type == "external" and external_path.is_file():
            return (
                load_template(external_path),
                template_id or external_path.stem,
                str(external_path),
                selected.template_source or "file",
                "external",
            )

        fallback_id = str(getattr(scene, "template_id", "") or "").strip()
        if not fallback_id:
            raise ValueError(f"plan missing template_id: {getattr(scene, 'scene_id', '')}")
        fallback_entry = get_template_entry(fallback_id, mode_id=mode_id)
        return (
            load_template_from_library(fallback_id, mode_id=mode_id),
            fallback_id,
            str(fallback_entry.path) if fallback_entry is not None else "",
            "library" if fallback_entry is not None else "builtin",
            fallback_entry.source_type if fallback_entry is not None else "builtin",
        )

    def _persist_active_mode_preference(self, mode_id: str) -> None:
        try:
            self._workspace_preference_state = (
                self._workspace_preferences.update_active_mode(mode_id)
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("Could not persist active work mode: %s", exc, exc_info=exc)

    def _persist_current_scene_preference(self, _scene=None) -> None:
        mode_id = self.bridge.current_work_mode_id()
        try:
            self._workspace_preference_state = self._workspace_preferences.update_mode(
                mode_id,
                scene_id=self.bridge.current_scene_id(),
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("Could not persist current plan: %s", exc, exc_info=exc)

    def _persist_current_template_preference(self, _template=None) -> None:
        mode_id = self.bridge.current_work_mode_id()
        try:
            self._workspace_preference_state = self._workspace_preferences.update_mode(
                mode_id,
                template_id=self.bridge.current_template_id(),
                template_path=self.bridge.current_template_path(),
                template_source=self.bridge.current_template_source(),
                template_source_type=self.bridge.current_template_source_type(),
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("Could not persist current template: %s", exc, exc_info=exc)

    def _persist_official_document_type_preference(self, document_type_id: str) -> None:
        mode_id = self.bridge.current_work_mode_id()
        try:
            self._workspace_preference_state = self._workspace_preferences.update_mode(
                mode_id,
                official_document_type_id=str(document_type_id or "").strip()
                or "notice",
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("Could not persist document type: %s", exc, exc_info=exc)

    def _request_work_mode_change(self, mode_id: str) -> bool:
        target_mode_id = str(mode_id or "").strip()
        if not target_mode_id or target_mode_id == self._active_work_mode_id:
            return True
        mode = get_work_mode(target_mode_id)
        if mode is None:
            self.startup_status_changed.emit(
                f"切换工作模式失败: {target_mode_id}"
            )
            return False

        dirty_action = self._resolve_dirty_work_mode_switch_action(mode)
        if dirty_action == WORK_MODE_DIRTY_CANCEL:
            self.startup_status_changed.emit("已取消切换工作模式")
            return False
        if dirty_action == WORK_MODE_DIRTY_SAVE and not self._save_dirty_work_mode_configs():
            return False

        discard_transactions = []
        if dirty_action == WORK_MODE_DIRTY_DISCARD:
            prepared_discard = self._prepare_dirty_work_mode_discard()
            if prepared_discard is None:
                return False
            discard_transactions = prepared_discard

        try:
            self.bridge.set_current_work_mode(mode)
            switched = self.bridge.current_work_mode_id() == target_mode_id
        except Exception as exc:
            self._rollback_edit_transactions(discard_transactions)
            logger.warning(
                "Main window failed to activate work mode %s: %s",
                target_mode_id,
                exc,
                exc_info=exc,
            )
            return False
        if not switched:
            self._rollback_edit_transactions(discard_transactions)
            return False
        self._finalize_edit_transactions(discard_transactions)
        return True

    def _on_work_mode_changed(self, mode) -> None:
        mode_id = str(getattr(mode, "mode_id", "") or "").strip()
        if not mode_id or mode_id == self._active_work_mode_id:
            return

        try:
            self._load_work_mode_defaults(mode)
        except Exception as exc:
            logger.warning(
                "Main window ignored work mode switch failure for %s: %s",
                mode_id,
                exc,
                exc_info=exc,
            )
            if not self.bridge.rollback_pending_work_mode_transition():
                self._restore_active_work_mode()
            self.startup_status_changed.emit(f"切换工作模式失败: {mode_id}")
            return
        self._active_work_mode_id = mode_id
        self.bridge.commit_pending_work_mode_transition()
        self._persist_active_mode_preference(mode_id)
        workbench = self._loaded_panel_for_id("workbench")
        restore_preferences = getattr(
            workbench,
            "restore_workspace_preferences",
            None,
        )
        if callable(restore_preferences):
            restore_preferences()
        if self._template_import_coordinator.is_running:
            self._template_import_coordinator.activate_mode(mode_id)
        self.startup_status_changed.emit(f"已切换到{getattr(mode, 'label', mode_id)}")

    def _on_material_scope_suspended(self, evidence) -> None:
        payload = dict(evidence or {}) if isinstance(evidence, dict) else {}
        reason = str(payload.get("reason") or "scope_changed")
        target = str(
            payload.get("next_scene_id")
            or payload.get("next_mode_id")
            or "当前方案"
        )
        self.startup_status_changed.emit(
            f"旧资料已挂起，未应用到 {target}（{reason}）"
        )

    def _resolve_dirty_work_mode_switch_action(self, mode) -> str:
        scene_panel = self._loaded_panel_for_id("scene")
        pause_autosave = getattr(
            scene_panel,
            "pause_pending_scene_autosave",
            None,
        )
        if self.bridge.is_scene_dirty() and callable(pause_autosave):
            pause_autosave()
        if not self._work_mode_switch_has_dirty():
            return ""
        action = self._prompt_work_mode_dirty_switch_action(mode)
        if action in {WORK_MODE_DIRTY_SAVE, WORK_MODE_DIRTY_DISCARD}:
            return action
        return WORK_MODE_DIRTY_CANCEL

    def _work_mode_switch_has_dirty(self) -> bool:
        if self.bridge.is_scene_dirty():
            return True
        panel = self._loaded_panel_for_id("assets")
        has_pending = getattr(panel, "has_pending_material_changes", None)
        if not callable(has_pending):
            return False
        try:
            return bool(has_pending())
        except Exception as exc:
            logger.warning(
                "Main window failed to inspect pending material changes: %s",
                exc,
                exc_info=exc,
            )
            # A failed dirty check must not permit a potentially destructive
            # switch without user confirmation.
            return True

    def _prompt_work_mode_dirty_switch_action(self, mode) -> str:
        label = str(getattr(mode, "label", "") or "").strip() or "新工作模式"
        dlg = BaseDialog(title="切换工作模式", icon_style="warning", parent=self)
        dlg.add_message(
            f"当前方案或资料包有未保存更改。切换到{label}前，请选择如何处理这些更改。"
        )

        selected = {"action": WORK_MODE_DIRTY_CANCEL}

        cancel_btn = dlg.add_secondary_button("取消")
        cancel_btn.clicked.connect(dlg.reject)

        discard_btn = dlg.add_secondary_button("放弃更改")
        discard_btn.clicked.connect(
            lambda: self._accept_work_mode_dirty_dialog(
                dlg,
                selected,
                WORK_MODE_DIRTY_DISCARD,
            )
        )

        scene_requires_copy = (
            self.bridge.is_scene_dirty()
            and self.bridge.current_scene_source_type() != "user"
        )
        save_btn = dlg.add_primary_button(
            "保存为我的方案并切换" if scene_requires_copy else "保存并切换"
        )
        save_btn.clicked.connect(
            lambda: self._accept_work_mode_dirty_dialog(
                dlg,
                selected,
                WORK_MODE_DIRTY_SAVE,
            )
        )

        dlg.exec()
        return selected["action"]

    @staticmethod
    def _accept_work_mode_dirty_dialog(dialog, selected: dict[str, str], action: str) -> None:
        selected["action"] = action
        dialog.accept()

    def _save_dirty_work_mode_configs(self) -> bool:
        prepared: list[tuple[QWidget, str, str, str, str]] = []
        committed: list[tuple[QWidget, str, str, str, str]] = []
        try:
            assets_panel = self._loaded_panel_for_id("assets")
            has_pending_materials = getattr(
                assets_panel,
                "has_pending_material_changes",
                None,
            )
            if callable(has_pending_materials) and has_pending_materials():
                prepare_materials = getattr(
                    assets_panel,
                    "prepare_pending_material_changes",
                    None,
                )
                if not callable(prepare_materials) or not prepare_materials(
                    WORK_MODE_DIRTY_SAVE
                ):
                    self.startup_status_changed.emit("保存当前资料包失败，已取消切换")
                    return False
                prepared.append(
                    (
                        assets_panel,
                        "commit_prepared_material_changes",
                        "rollback_prepared_material_changes",
                        "finalize_prepared_material_changes",
                        "cancel_prepared_material_changes",
                    )
                )

            save_mode_id = self._active_work_mode_id or self.bridge.current_work_mode_id()
            if self.bridge.is_scene_dirty():
                scene_panel = self._ensure_panel_loaded_for_id("scene")
                prepare_scene = getattr(
                    scene_panel,
                    "prepare_pending_scene_changes",
                    None,
                )
                if not callable(prepare_scene) or not prepare_scene(
                    WORK_MODE_DIRTY_SAVE,
                    mode_id=save_mode_id,
                    save_reason="切换工作模式前保存修改",
                ):
                    self._cancel_prepared_edit_transactions(prepared)
                    self.startup_status_changed.emit("保存当前方案失败，已取消切换")
                    return False
                prepared.append(
                    (
                        scene_panel,
                        "commit_prepared_scene_changes",
                        "rollback_prepared_scene_changes",
                        "finalize_prepared_scene_changes",
                        "cancel_prepared_scene_changes",
                    )
                )

            for transaction in prepared:
                panel, commit_name, _rollback_name, _finalize_name, _cancel_name = transaction
                commit = getattr(panel, commit_name, None)
                if not callable(commit) or not bool(commit()):
                    self._rollback_edit_transactions(committed)
                    self._cancel_prepared_edit_transactions(
                        [item for item in prepared if item not in committed]
                    )
                    self.startup_status_changed.emit("保存当前配置失败，已取消切换")
                    return False
                committed.append(transaction)

            if not self._finalize_edit_transactions(
                committed,
                retain_rollback=True,
            ):
                self._rollback_edit_transactions(committed)
                self.startup_status_changed.emit(
                    "发布已保存配置失败，已回滚并取消切换"
                )
                return False

        except Exception as exc:
            self._rollback_edit_transactions(committed)
            self._cancel_prepared_edit_transactions(
                [item for item in prepared if item not in committed]
            )
            logger.warning(
                "Main window failed to save dirty config before work mode switch: %s",
                exc,
                exc_info=exc,
            )
            self.startup_status_changed.emit(f"保存当前配置失败: {exc}")
            return False

        self.startup_status_changed.emit("当前配置已保存，继续切换工作模式")
        return True

    def _prepare_dirty_work_mode_discard(
        self,
    ) -> list[tuple[QWidget, str, str, str, str]] | None:
        """Keep discarded editor state reversible until target defaults load."""

        prepared: list[tuple[QWidget, str, str, str, str]] = []
        committed: list[tuple[QWidget, str, str, str, str]] = []
        try:
            assets_panel = self._loaded_panel_for_id("assets")
            has_pending_materials = getattr(
                assets_panel,
                "has_pending_material_changes",
                None,
            )
            if callable(has_pending_materials) and has_pending_materials():
                prepare_materials = getattr(
                    assets_panel,
                    "prepare_pending_material_changes",
                    None,
                )
                if not callable(prepare_materials) or not prepare_materials(
                    WORK_MODE_DIRTY_DISCARD
                ):
                    return None
                prepared.append(
                    (
                        assets_panel,
                        "commit_prepared_material_changes",
                        "rollback_prepared_material_changes",
                        "finalize_prepared_material_changes",
                        "cancel_prepared_material_changes",
                    )
                )

            if self.bridge.is_scene_dirty():
                scene_panel = self._ensure_panel_loaded_for_id("scene")
                prepare_scene = getattr(
                    scene_panel,
                    "prepare_pending_scene_changes",
                    None,
                )
                if not callable(prepare_scene) or not prepare_scene(
                    WORK_MODE_DIRTY_DISCARD
                ):
                    self._cancel_prepared_edit_transactions(prepared)
                    return None
                prepared.append(
                    (
                        scene_panel,
                        "commit_prepared_scene_changes",
                        "rollback_prepared_scene_changes",
                        "finalize_prepared_scene_changes",
                        "cancel_prepared_scene_changes",
                    )
                )

            for transaction in prepared:
                panel, commit_name, _rollback_name, _finalize_name, _cancel_name = (
                    transaction
                )
                commit = getattr(panel, commit_name, None)
                if not callable(commit) or not bool(commit()):
                    self._rollback_edit_transactions(committed)
                    self._cancel_prepared_edit_transactions(
                        [item for item in prepared if item not in committed]
                    )
                    return None
                committed.append(transaction)
        except Exception as exc:
            self._rollback_edit_transactions(committed)
            self._cancel_prepared_edit_transactions(
                [item for item in prepared if item not in committed]
            )
            logger.warning(
                "Main window failed to prepare dirty config discard: %s",
                exc,
                exc_info=exc,
            )
            return None
        return committed

    @staticmethod
    def _cancel_prepared_edit_transactions(
        transactions: list[tuple[QWidget, str, str, str, str]],
    ) -> None:
        for panel, _commit_name, _rollback_name, _finalize_name, cancel_name in transactions:
            cancel = getattr(panel, cancel_name, None)
            if callable(cancel):
                try:
                    result = cancel()
                    if result is False:
                        logger.warning(
                            "Edit transaction cancel returned False: %s.%s",
                            type(panel).__name__,
                            cancel_name,
                        )
                except Exception as exc:
                    logger.warning(
                        "Edit transaction cancel failed: %s.%s: %s",
                        type(panel).__name__,
                        cancel_name,
                        exc,
                        exc_info=exc,
                    )

    @staticmethod
    def _rollback_edit_transactions(
        transactions: list[tuple[QWidget, str, str, str, str]],
    ) -> None:
        for panel, _commit_name, rollback_name, _finalize_name, _cancel_name in reversed(
            transactions
        ):
            rollback = getattr(panel, rollback_name, None)
            if callable(rollback):
                try:
                    result = rollback()
                    if result is False:
                        logger.warning(
                            "Edit transaction rollback returned False: %s.%s",
                            type(panel).__name__,
                            rollback_name,
                        )
                except Exception as exc:
                    logger.warning(
                        "Edit transaction rollback failed: %s.%s: %s",
                        type(panel).__name__,
                        rollback_name,
                        exc,
                        exc_info=exc,
                    )

    @staticmethod
    def _finalize_edit_transactions(
        transactions: list[tuple[QWidget, str, str, str, str]],
        *,
        retain_rollback: bool = False,
    ) -> bool:
        # Finalize in reverse commit order.  Scene publication is therefore
        # released before material rollback evidence is discarded; if it
        # fails, the caller can still roll back every committed participant.
        retained_releases: list[tuple[QWidget, object]] = []
        for panel, _commit_name, _rollback_name, finalize_name, _cancel_name in reversed(
            transactions
        ):
            finalize = getattr(panel, finalize_name, None)
            if callable(finalize):
                try:
                    release = getattr(
                        panel,
                        "release_finalized_edit_transaction",
                        None,
                    )
                    result = (
                        finalize(retain_rollback=True)
                        if retain_rollback and callable(release)
                        else finalize()
                    )
                    if result is False:
                        logger.warning(
                            "Edit transaction finalize returned False: %s.%s",
                            type(panel).__name__,
                            finalize_name,
                        )
                        return False
                    if retain_rollback and callable(release):
                        retained_releases.append((panel, release))
                except Exception as exc:
                    logger.warning(
                        "Edit transaction finalize failed: %s.%s: %s",
                        type(panel).__name__,
                        finalize_name,
                        exc,
                        exc_info=exc,
                    )
                    return False
        if retain_rollback:
            for panel, release in retained_releases:
                try:
                    if release() is False:
                        logger.warning(
                            "Edit transaction release returned False: %s",
                            type(panel).__name__,
                        )
                        return False
                except Exception as exc:
                    logger.warning(
                        "Edit transaction release failed: %s: %s",
                        type(panel).__name__,
                        exc,
                        exc_info=exc,
                    )
                    return False
        return True

    def _restore_active_work_mode(self) -> None:
        self.bridge.set_current_work_mode(self._active_work_mode_id or "custom")
        self.bridge.commit_pending_work_mode_transition()

    def _load_work_mode_defaults(self, mode) -> None:
        self._activate_persisted_mode_state(mode, emit_signal=True)

    def _navigate_intent(self, intent) -> None:
        panel_index = self._panel_index_from_intent(intent)
        if panel_index < 0:
            return
        panel = self._show_panel(panel_index, pending_intent=intent)
        if self.panel_stack.currentIndex() != panel_index:
            self.sidebar.select(self.panel_stack.currentIndex())
            return
        self.sidebar.select(panel_index)
        if (
            self._panel_load_states.get(panel_index) is PanelLoadState.READY
            and panel is not None
            and hasattr(panel, "handle_navigation_intent")
        ):
            panel.handle_navigation_intent(intent)

    def _panel_index_from_intent(self, intent) -> int:
        panel_index = int(self._intent_value(intent, "panel_index", -1) or -1)
        if panel_index >= 0:
            return panel_index
        panel_id = str(self._intent_value(intent, "panel_id", "") or "").strip()
        if not panel_id:
            return -1
        for index, spec in enumerate(self._panel_specs):
            if spec.id == panel_id:
                return index
        return -1

    @staticmethod
    def _intent_value(intent, key: str, default=None):
        return navigation_intent_value(intent, key, default)

    def _show_panel(
        self,
        index: int,
        *,
        allow_async: bool = True,
        pending_intent=None,
    ) -> QWidget | None:
        if self._close_accepted:
            return None
        if not 0 <= index < self.panel_stack.count():
            return None
        current_index = self.panel_stack.currentIndex()
        if index != current_index and 0 <= current_index < self.panel_stack.count():
            current_panel = self.panel_stack.widget(current_index)
            leave_guard = getattr(current_panel, "request_leave_pending_changes", None)
            if callable(leave_guard):
                target_title = self._panel_specs[index].title
                if not bool(leave_guard(f"切换到{target_title}")):
                    if getattr(self.sidebar, "_active_index", current_index) != current_index:
                        self.sidebar.select(current_index)
                    return current_panel
        self._cancel_scheduled_panel_loads(except_index=index)
        if allow_async and index not in self._loaded_panel_indexes:
            placeholder = self.panel_stack.widget(index)
            if hasattr(placeholder, "set_loading"):
                placeholder.set_loading(self._panel_specs[index].title)
            self.panel_stack.setCurrentIndex(index)
            self._request_panel_load(index, pending_intent=pending_intent)
            return placeholder
        panel = self._ensure_panel_loaded(index)
        self.panel_stack.setCurrentIndex(index)
        return panel

    def panel_load_state(self, panel_id: str) -> PanelLoadState | None:
        for index, spec in enumerate(self._panel_specs):
            if spec.id == panel_id:
                return self._panel_load_states.get(index, PanelLoadState.UNLOADED)
        return None

    def _set_panel_load_state(
        self,
        index: int,
        state: PanelLoadState,
        *,
        error: str = "",
    ) -> None:
        previous = self._panel_load_states.get(index)
        self._panel_load_states[index] = state
        if error:
            self._panel_load_errors[index] = error
        else:
            self._panel_load_errors.pop(index, None)
        if previous is not state and 0 <= index < len(self._panel_specs):
            self.panel_load_state_changed.emit(self._panel_specs[index].id, state.value)

    def _request_panel_load(self, index: int, *, pending_intent=None) -> None:
        if self._close_accepted or not 0 <= index < self.panel_stack.count():
            return
        if pending_intent is not None:
            self._pending_panel_intents[index] = pending_intent
        if index in self._loaded_panel_indexes:
            return
        if self._panel_load_states.get(index) in {
            PanelLoadState.SCHEDULED,
            PanelLoadState.LOADING,
        }:
            return
        placeholder = self.panel_stack.widget(index)
        if hasattr(placeholder, "set_loading"):
            placeholder.set_loading(self._panel_specs[index].title)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda panel_index=index: self._finish_panel_load(panel_index)
        )
        self._panel_load_timers[index] = timer
        self._set_panel_load_state(index, PanelLoadState.SCHEDULED)
        self._panel_loads_in_progress.add(index)
        # Leave one paint opportunity for the selected navigation state and shell.
        timer.start(16)

    def _cancel_scheduled_panel_loads(self, *, except_index: int) -> None:
        for index, timer in tuple(self._panel_load_timers.items()):
            if index == except_index:
                continue
            if self._panel_load_states.get(index) is not PanelLoadState.SCHEDULED:
                continue
            timer.stop()
            timer.deleteLater()
            self._panel_load_timers.pop(index, None)
            self._pending_panel_intents.pop(index, None)
            self._panel_loads_in_progress.discard(index)
            placeholder = self.panel_stack.widget(index)
            if hasattr(placeholder, "set_unloaded"):
                placeholder.set_unloaded()
            self._set_panel_load_state(index, PanelLoadState.UNLOADED)

    def _loaded_panel_for_id(self, panel_id: str) -> QWidget | None:
        for index, spec in enumerate(self._panel_specs):
            if spec.id != panel_id or index not in self._loaded_panel_indexes:
                continue
            return self.panel_stack.widget(index)
        return None

    def _ensure_panel_loaded_for_id(self, panel_id: str) -> QWidget | None:
        for index, spec in enumerate(self._panel_specs):
            if spec.id == panel_id:
                return self._ensure_panel_loaded(index)
        return None

    def _finish_panel_load(self, index: int) -> None:
        timer = self._panel_load_timers.pop(index, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        if self._panel_load_states.get(index) is not PanelLoadState.SCHEDULED:
            self._panel_loads_in_progress.discard(index)
            return
        try:
            if self._close_accepted:
                return
            if not 0 <= index < self.panel_stack.count():
                return
            spec = self._panel_specs[index]
            self.startup_status_changed.emit(f"加载{spec.title}")
            self._set_panel_load_state(index, PanelLoadState.LOADING)
            should_show_loaded_panel = self.panel_stack.currentIndex() == index
            panel = self._ensure_panel_loaded(index)
        except Exception as exc:
            logger.error(
                "Failed to load panel %s",
                self._panel_specs[index].id
                if 0 <= index < len(self._panel_specs)
                else index,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            self._set_panel_load_state(index, PanelLoadState.FAILED, error=str(exc))
            placeholder = self.panel_stack.widget(index)
            if hasattr(placeholder, "set_failed"):
                placeholder.set_failed(str(exc))
            return
        finally:
            self._panel_loads_in_progress.discard(index)
        if should_show_loaded_panel:
            self.panel_stack.setCurrentIndex(index)
            panel.updateGeometry()
        intent = self._pending_panel_intents.pop(index, None)
        if intent is not None and hasattr(panel, "handle_navigation_intent"):
            try:
                panel.handle_navigation_intent(intent)
            except Exception:
                logger.exception(
                    "Failed to replay navigation intent for panel %s",
                    self._panel_specs[index].id,
                )

    def _ensure_panel_loaded(self, index: int) -> QWidget:
        if index in self._loaded_panel_indexes:
            return self.panel_stack.widget(index)
        if self._close_accepted:
            return self.panel_stack.widget(index)

        spec = self._panel_specs[index]
        panel = create_panel(spec.id, self.bridge)
        return self._install_loaded_panel(index, panel)

    def _install_loaded_panel(self, index: int, panel: QWidget) -> QWidget:
        if index in self._loaded_panel_indexes:
            panel.deleteLater()
            return self.panel_stack.widget(index)
        old = self.panel_stack.widget(index)
        self.panel_stack.removeWidget(old)
        old.deleteLater()
        self.panel_stack.insertWidget(index, panel)
        self._loaded_panel_indexes.add(index)
        self._panel_placeholders.pop(index, None)
        self._set_panel_load_state(index, PanelLoadState.READY)

        return panel

    def _emit_startup_ready(self) -> None:
        if getattr(self, "_close_accepted", False):
            return
        if getattr(self, "_startup_ready_emitted", False):
            return
        self._startup_ready_emitted = True
        self.startup_status_changed.emit("启动完成")
        self.panel_stack.setCurrentIndex(0)
        self._prepare_initial_panel_for_show()
        if self._background_services_enabled:
            self._template_import_coordinator.start(
                self.bridge.current_work_mode_id()
            )
        self.startup_ready.emit()

    def _on_template_import_batch_processed(self, mode_id: str, batch) -> None:
        self.bridge.template_library_events.import_completed.emit(
            str(mode_id or "").strip(),
            batch,
        )
        imported_count = len(getattr(batch, "successes", ()) or ())
        rejection_count = len(getattr(batch, "rejections", ()) or ())
        warning_count = len(getattr(batch, "warnings", ()) or ())
        if imported_count:
            self.startup_status_changed.emit(
                f"{mode_id} 已导入 {imported_count} 个模板"
            )
        if rejection_count:
            self.startup_status_changed.emit(
                f"{mode_id} 有 {rejection_count} 个模板未通过校验"
            )
        if warning_count:
            self.startup_status_changed.emit(
                f"{mode_id} 有 {warning_count} 条导入后处理提醒"
            )

    @staticmethod
    def _on_template_import_monitoring_error(mode_id: str, message: str) -> None:
        scope = str(mode_id or "").strip() or "template_workbench"
        logger.warning("Template import monitoring error [%s]: %s", scope, message)

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
            self._shadow_surface.configure_surface(
                background=t.bg_window,
                radius=t.shell_radius,
            )
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
        self._shadow.setEnabled(False)
        self._shadow_surface.hide()
        cl = self._container.layout()
        if cl is not None:
            cl.setContentsMargins(0, 0, 0, 0)

    def _apply_normal_visuals(self):
        shell = self.centralWidget()
        if shell:
            m = self.SHADOW_MARGIN
            shell.layout().setContentsMargins(m, m, m, m)
        theme = get_theme()
        self._shadow_surface.show()
        self._shadow_surface.configure_surface(
            background=theme.bg_window,
            radius=theme.shell_radius,
        )
        self._shadow.setEnabled(True)
        self._container.configure_surface(
            background=theme.bg_window,
            radius=theme.shell_radius,
            border_color=theme.border,
            border_width=1.0,
        )
        cl = self._container.layout()
        if cl is not None:
            cl.setContentsMargins(1, 1, 1, 1)

    @staticmethod
    def _cancel_prepared_panel_closes(panels: list[QWidget]) -> None:
        for panel in panels:
            cancel = getattr(panel, "cancel_prepared_close", None)
            if callable(cancel):
                cancel()

    def _resume_template_import_after_cancel(self, was_running: bool) -> None:
        if not was_running or self._template_import_coordinator.is_running:
            return
        mode_id = self._active_work_mode_id or self.bridge.current_work_mode_id()
        self._template_import_coordinator.start(mode_id)

    def _cancel_pending_lifecycle_callbacks(self) -> None:
        self._startup_ready_timer.stop()
        for timer in self._panel_load_timers.values():
            timer.stop()
            timer.deleteLater()
        self._panel_load_timers.clear()
        self._panel_loads_in_progress.clear()
        self._pending_panel_intents.clear()

    def _panel_widgets_for_close(self) -> list[QWidget]:
        stack = getattr(self, "panel_stack", None)
        if stack is None:
            return []
        try:
            if self.bridge.is_scene_dirty() and self._loaded_panel_for_id("scene") is None:
                self._ensure_panel_loaded_for_id("scene")
            return [stack.widget(index) for index in range(int(stack.count()))]
        except Exception as exc:
            _log_close_handling_failure("panel stack count", exc)
            return []

    def _prepare_panels_for_close(
        self,
        panels: list[QWidget],
    ) -> tuple[bool, list[QWidget]]:
        prepared: list[QWidget] = []
        for index, panel in enumerate(panels):
            prepare = getattr(panel, "prepare_close_pending_changes", None)
            try:
                if callable(prepare):
                    allowed = bool(prepare())
                    if allowed:
                        prepared.append(panel)
                else:
                    allowed = True
            except Exception as exc:
                _log_close_handling_failure(
                    f"panel close preparation at index {index}",
                    exc,
                )
                allowed = False
            if not allowed:
                return False, prepared
        return True, prepared

    @staticmethod
    def _shutdown_panels_for_close(panels: list[QWidget]) -> bool:
        for index, panel in enumerate(panels):
            shutdown = getattr(panel, "shutdown_active_execution", None)
            if not callable(shutdown):
                continue
            try:
                if bool(shutdown(timeout_ms=1000)):
                    continue
            except Exception as exc:
                _log_close_handling_failure(f"panel shutdown at index {index}", exc)
            return False
        return True

    @classmethod
    def _commit_prepared_panel_closes(cls, panels: list[QWidget]) -> bool:
        # Reversible editors commit first.  A participant without a rollback
        # contract remains last so it cannot strand earlier writes.
        ordered = sorted(
            enumerate(panels),
            key=lambda item: (
                0
                if callable(
                    getattr(item[1], "rollback_close_pending_changes", None)
                )
                else 1,
                item[0],
            ),
        )
        committed: list[tuple[int, QWidget]] = []
        for order_index, (original_index, panel) in enumerate(ordered):
            commit = getattr(panel, "commit_close_pending_changes", None)
            if not callable(commit):
                continue
            try:
                if bool(commit()):
                    committed.append((original_index, panel))
                    continue
            except Exception as exc:
                _log_close_handling_failure(
                    f"panel close commit at prepared index {original_index}",
                    exc,
                )
            failed_rollback = getattr(panel, "rollback_close_pending_changes", None)
            if callable(failed_rollback):
                try:
                    failed_rollback()
                except Exception as exc:
                    _log_close_handling_failure(
                        f"failed panel rollback at prepared index {original_index}",
                        exc,
                    )
            else:
                failed_cancel = getattr(panel, "cancel_prepared_close", None)
                if callable(failed_cancel):
                    failed_cancel()
            cls._rollback_committed_panel_closes(committed)
            cls._cancel_prepared_panel_closes(
                [item[1] for item in ordered[order_index + 1 :]]
            )
            return False

        # Participants that can retain rollback evidence finalize first.  No
        # irreversible close finalizer is allowed to run before a fallible
        # Scene publication has proved it can be released safely.
        finalize_order = sorted(
            committed,
            key=lambda item: (
                0
                if callable(
                    getattr(item[1], "release_finalized_edit_transaction", None)
                )
                else 1,
            ),
        )
        retained_releases: list[tuple[int, QWidget, object]] = []
        for original_index, panel in finalize_order:
            finalize = getattr(panel, "finalize_close_pending_changes", None)
            if not callable(finalize):
                continue
            release = getattr(panel, "release_finalized_edit_transaction", None)
            try:
                result = (
                    finalize(retain_rollback=True)
                    if callable(release)
                    else finalize()
                )
                if result is False:
                    _log_close_handling_failure(
                        f"panel close finalize at prepared index {original_index}",
                        RuntimeError("close finalizer returned False"),
                    )
                    cls._rollback_committed_panel_closes(committed)
                    return False
                if callable(release):
                    retained_releases.append((original_index, panel, release))
            except Exception as exc:
                _log_close_handling_failure(
                    f"panel close finalize at prepared index {original_index}",
                    exc,
                )
                cls._rollback_committed_panel_closes(committed)
                return False

        for original_index, panel, release in retained_releases:
            try:
                if release() is False:
                    _log_close_handling_failure(
                        f"panel close release at prepared index {original_index}",
                        RuntimeError("close release returned False"),
                    )
                    cls._rollback_committed_panel_closes(committed)
                    return False
            except Exception as exc:
                _log_close_handling_failure(
                    f"panel close release at prepared index {original_index}",
                    exc,
                )
                cls._rollback_committed_panel_closes(committed)
                return False
        return True

    @staticmethod
    def _rollback_committed_panel_closes(
        committed: list[tuple[int, QWidget]],
    ) -> None:
        for committed_index, committed_panel in reversed(committed):
            rollback = getattr(
                committed_panel,
                "rollback_close_pending_changes",
                None,
            )
            if not callable(rollback):
                continue
            try:
                if rollback() is False:
                    _log_close_handling_failure(
                        f"panel rollback at prepared index {committed_index}",
                        RuntimeError("close rollback returned False"),
                    )
            except Exception as exc:
                _log_close_handling_failure(
                    f"panel rollback at prepared index {committed_index}",
                    exc,
                )

    def _reject_close(
        self,
        event,
        prepared_panels: list[QWidget],
        *,
        coordinator_was_running: bool,
    ) -> None:
        self._cancel_prepared_panel_closes(prepared_panels)
        self._resume_template_import_after_cancel(coordinator_was_running)
        event.ignore()

    def closeEvent(self, event) -> None:
        coordinator_was_running = bool(self._template_import_coordinator.is_running)
        panels = self._panel_widgets_for_close()
        allowed, prepared_panels = self._prepare_panels_for_close(panels)
        if not allowed or not self._shutdown_panels_for_close(panels):
            self._reject_close(
                event,
                prepared_panels,
                coordinator_was_running=coordinator_was_running,
            )
            return
        if not self._commit_prepared_panel_closes(prepared_panels):
            self._resume_template_import_after_cancel(coordinator_was_running)
            event.ignore()
            return
        workbench = next(
            (
                panel
                for panel in panels
                if callable(
                    getattr(panel, "_persist_workspace_preferences", None)
                )
            ),
            None,
        )
        persist_workbench = getattr(
            workbench,
            "_persist_workspace_preferences",
            None,
        )
        if callable(persist_workbench):
            persist_workbench()
        self._persist_current_scene_preference()
        self._persist_current_template_preference()
        self._persist_official_document_type_preference(
            self.bridge.current_official_document_type_id()
        )
        self._persist_active_mode_preference(
            self.bridge.current_work_mode_id()
        )
        self._close_accepted = True
        self._cancel_pending_lifecycle_callbacks()
        try:
            self._template_import_coordinator.stop()
        except Exception as exc:
            _log_close_handling_failure("template import coordinator stop", exc)
        super().closeEvent(event)

    def register_panel(self, index: int, panel: QWidget) -> None:
        timer = self._panel_load_timers.pop(index, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        self._panel_loads_in_progress.discard(index)
        old = self.panel_stack.widget(index)
        self.panel_stack.removeWidget(old)
        old.deleteLater()
        self.panel_stack.insertWidget(index, panel)
        self._loaded_panel_indexes.add(index)
        self._panel_placeholders.pop(index, None)
        self._set_panel_load_state(index, PanelLoadState.READY)
        intent = self._pending_panel_intents.pop(index, None)
        if intent is not None and hasattr(panel, "handle_navigation_intent"):
            panel.handle_navigation_intent(intent)
