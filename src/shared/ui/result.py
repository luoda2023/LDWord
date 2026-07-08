"""Result — 操作结果页控件"""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography import Typography


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

        icon_map = {
            "success": "✓",
            "error": "✕",
            "warning": "⚠",
            "info": "ℹ",
        }
        icon_char = icon_map.get(self._status, icon_map["info"])

        # 大图标
        self._icon_lbl = QLabel(icon_char)
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

        self._icon_lbl.setStyleSheet(
            f"""
            QLabel {{
                color: {color}; font-size: 36px; font-weight: bold;
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
        t = get_theme()
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(t.button_height_md)
        btn.setProperty("_result_primary", bool(primary))
        self._style_action_button(btn, primary)

        if callback:
            btn.clicked.connect(callback)

        self._btn_row.addWidget(btn)
        self._action_buttons.append(btn)
        return btn

    def _style_action_button(self, button: QPushButton, primary: bool) -> None:
        t = get_theme()
        if primary:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background:{t.primary}; color:{t.text_on_primary};
                    border:none; border-radius:{t.button_radius}px;
                    padding:{t.button_padding_y}px {t.button_padding_x}px;
                    font-size:{t.font_size_md}px; font-weight:{t.button_font_weight};
                }}
                QPushButton:hover {{ background:{t.primary_hover}; }}
                QPushButton:pressed {{ background:{t.primary_pressed}; }}
                """
            )
            return
        button.setStyleSheet(
            f"""
            QPushButton {{
                background:{t.bg_card}; color:{t.text_primary};
                border:1px solid {t.border}; border-radius:{t.button_radius}px;
                padding:{t.button_padding_y}px {t.button_padding_x}px;
                font-size:{t.font_size_md}px;
            }}
            QPushButton:hover {{ background:{t.bg_hover}; border-color:{t.border_focus}; }}
            """
        )

    def set_status(self, status: str) -> None:
        self._status = status
        self._apply_theme()
