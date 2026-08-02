"""Drawer — 侧滑面板控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.divider import Divider
from src.shared.ui.typography import Typography


class Drawer(QWidget):
    """侧滑面板，带遮罩层和标题栏。

    用法::

        drawer = Drawer(title="设置", width=360, side="right")
        drawer.set_body(my_widget)     # 放入任意内容

        # 打开 / 关闭
        drawer.open()
        drawer.close()

        # 关闭信号
        drawer.closed.connect(lambda: print("关闭了"))
    """

    closed = Signal()

    def __init__(
        self,
        *,
        title: str = "",
        width: int = 360,
        side: str = "right",    # "right" | "left"
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._drawer_width = width
        self._side = side

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.hide()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 遮罩
        self._overlay = QWidget()
        self._overlay.setCursor(Qt.ArrowCursor)
        self._overlay.mousePressEvent = lambda _: self.close()

        # 抽屉面板
        self._panel = QWidget()
        self._panel.setFixedWidth(self._drawer_width)

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # 标题栏
        header = QWidget()
        header.setFixedHeight(52)
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(16, 0, 8, 0)

        self._title_lbl = Typography(self._title, variant="h3")
        header_l.addWidget(self._title_lbl, 1)

        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.close)
        header_l.addWidget(self._close_btn)

        panel_layout.addWidget(header)
        panel_layout.addWidget(Divider())

        # 内容区
        self._body_container = QWidget()
        self._body_layout = QVBoxLayout(self._body_container)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(self._body_container, 1)

        if self._side == "right":
            root.addWidget(self._overlay, 1)
            root.addWidget(self._panel)
        else:
            root.addWidget(self._panel)
            root.addWidget(self._overlay, 1)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._overlay.setStyleSheet(
            f"background: {t.overlay}; border: none;"
        )
        self._panel.setStyleSheet(
            f"""
            QWidget {{
                background: {t.bg_card};
                border: none;
            }}
            """
        )
        self._close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent; border: none;
                color: {t.text_hint}; font-size: 22px; font-weight: bold;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background: {t.bg_hover}; color: {t.text_primary};
            }}
            """
        )

    # ── 公共 API ─────────────────────────────────────────────────────────────

    def set_body(self, widget: QWidget) -> None:
        """设置抽屉内容区域的控件"""
        # 清除旧内容
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)
        self._body_layout.addWidget(widget)

    def take_body(self) -> QWidget | None:
        """Detach and return the current body without deleting it."""

        item = self._body_layout.takeAt(0)
        if item is None:
            return None
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
        return widget

    def set_title(self, title: str) -> None:
        self._title = title
        self._title_lbl.setText(title)

    def open(self) -> None:
        """打开抽屉（相对父窗口全屏展开）"""
        if self.parent():
            geometry = self.parent().rect()
            geometry.moveTopLeft(self.parent().mapToGlobal(geometry.topLeft()))
            self.setGeometry(geometry)
        self.show()
        self.raise_()

    def close(self) -> None:
        self.hide()
        self.closed.emit()
