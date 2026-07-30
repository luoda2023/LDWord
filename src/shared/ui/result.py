"""Result — 操作结果页控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.typography import Typography
from src.shared.ui.icons.catalog import get_icon


class Result(QWidget):
    """操作结果页，展示成功 / 失败 / 警告等结果状态。

    用法::

        res = Result(
            status="success",
            title="提交成功",
            description="您的文档已完成排版，请查收",
        )
        res.add_action("查看结果", primary=True, callback=open_file)
        res.add_action("返回首页", callback=go_home)
    """

    def __init__(
        self,
        *,
        status: str = "success",   # success | error | warning | info
        title: str = "",
        description: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._status = status
        self._title = title
        self._description = description
        self._action_buttons: list[QPushButton] = []

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignCenter)

        # 大图标
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setFixedSize(72, 72)
        layout.addWidget(self._icon_lbl, 0, Qt.AlignCenter)

        # 标题
        self._title_lbl = Typography(self._title, variant="h2")
        self._title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title_lbl, 0, Qt.AlignCenter)

        # 描述
        if self._description:
            self._desc_lbl = Typography(self._description, variant="body")
            self._desc_lbl.setAlignment(Qt.AlignCenter)
            self._desc_lbl.setWordWrap(True)
            layout.addWidget(self._desc_lbl, 0, Qt.AlignCenter)

        # 按钮区
        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(12)
        self._btn_row.setAlignment(Qt.AlignCenter)
        layout.addLayout(self._btn_row)

    def _apply_theme(self) -> None:
        t = get_theme()
        icon_color_map = {
            "success": t.success,
            "error":   t.error,
            "warning": t.warning,
            "info":    t.info,
        }
        bg_color_map = {
            "success": t.success_bg,
            "error":   t.error_bg,
            "warning": t.warning_bg,
            "info":    t.info_bg,
        }
        color = icon_color_map.get(self._status, t.info)
        bg = bg_color_map.get(self._status, t.info_bg)
        icon_name = {
            "success": "circle-check",
            "error": "circle-x",
            "warning": "alert-triangle",
            "info": "info",
        }.get(self._status, "info")
        self._icon_lbl.setPixmap(get_icon(icon_name, 36, color).pixmap(36, 36))

        self._icon_lbl.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                border-radius: 36px;
                border: none;
            }}
            """
        )
        for button in self._action_buttons:
            self._style_action_button(button, bool(button.property("_result_primary")))

    # ── 公共 API ─────────────────────────────────────────────────────────────

    def add_action(
        self,
        text: str,
        *,
        primary: bool = False,
        callback=None,
    ) -> QPushButton:
        """添加操作按钮"""
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        apply_size_class(btn, "md")
        btn.setProperty("_result_primary", bool(primary))
        self._style_action_button(btn, primary)

        if callback:
            btn.clicked.connect(callback)

        self._btn_row.addWidget(btn)
        self._action_buttons.append(btn)
        return btn

    def _style_action_button(self, button: QPushButton, primary: bool) -> None:
        t = get_theme()
        apply_button_variant(button, "primary" if primary else "secondary")
        apply_size_class(button, "md")
        button.setStyleSheet(build_button_stylesheet(t))

    def set_status(self, status: str) -> None:
        self._status = status
        self._apply_theme()
