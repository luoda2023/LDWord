"""
theme_panel — 主题外观选择面板

FlowLayout 自适应布局 + 升级版预览卡片 + 自定义主题支持。
支持任意数量的预设/自定义主题，卡片自动按可用宽度排列换行。
"""

from __future__ import annotations

from src.qt_api import (
    QColor, QColorDialog, QDialog, QFont, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPainter, QPainterPath,
    QPushButton, QRect, QRectF, QVBoxLayout, QWidget, Qt, Signal,
)

from src.shared.ui.theme import (
    AppTheme, LIGHT, DARK, OCEAN, EYECARE, WARM_LIGHT,
    GREEN_LIGHT, GREEN_DARK, ROSE,
    BLUE_GREEN, RED_BLUE,
    derive_theme_from_core,
    get_theme, set_theme, bind_theme,
)
from src.shared.ui.custom_themes import CustomThemeStore, CustomThemeStoreError
from src.shared.ui.divider import Divider
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.input_metrics import build_framed_input_stylesheet
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.typography_policy import TextRole, apply_text_role
from src.ui.base_panel import BasePanel

# ── 预设注册表 ──────────────────────────────────────

_PRESETS: list[tuple[str, str, AppTheme]] = [
    ("light",       "蔚蓝",     LIGHT),
    ("dark",        "暗夜",     DARK),
    ("ocean",       "海蓝",     OCEAN),
    ("blue_green",  "蓝绿",     BLUE_GREEN),
    ("red_blue",    "红蓝",     RED_BLUE),
    ("green_light", "薄荷护眼", GREEN_LIGHT),
    ("green_dark",  "森林暗夜", GREEN_DARK),
    ("eyecare",     "暖夜护眼", EYECARE),
    ("warm_light",  "暖光护眼", WARM_LIGHT),
    ("rose",        "玫瑰粉",   ROSE),
]




def _theme_signature(theme: AppTheme) -> tuple[tuple[str, object], ...]:
    return tuple(sorted(theme.to_dict().items()))


def _themes_match(left: AppTheme, right: AppTheme) -> bool:
    return _theme_signature(left) == _theme_signature(right)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ThemeSwatchCard — 预览卡片
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _ThemeSwatchCard(RoundedSurfaceFrame):
    """配色方案预览卡片：色彩条 + 迷你 UI + 名称。"""

    clicked = Signal(str)

    CARD_W = 180
    CARD_H = 148
    COLOR_STRIP_H = 28
    PREVIEW_H = 78
    LABEL_H = 42
    SIDEBAR_RATIO = 0.18

    def __init__(self, key: str, label: str, preset: AppTheme, parent=None):
        super().__init__(parent=parent)
        self._key = key
        self._label = label
        self._preset = preset
        self._selected = False
        self._hovered = False

        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName(f"swatch_{key}")
        self._apply_style()
        bind_theme(self, self._apply_style)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_style()
        self.update()

    def set_preview_theme(self, preset: AppTheme) -> None:
        self._preset = preset
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = get_theme()
        pre = self._preset
        w, h = self.width(), self.height()

        # 1. 色彩条：5 个关键色圆点
        strip_y = 8
        dot_colors = [pre.primary, pre.accent, pre.bg_sidebar, pre.bg_window, pre.bg_card]
        dot_r = 7
        total_dots_w = len(dot_colors) * dot_r * 2 + (len(dot_colors) - 1) * 6
        dot_start_x = (w - total_dots_w) // 2

        for i, color_hex in enumerate(dot_colors):
            cx = dot_start_x + i * (dot_r * 2 + 6) + dot_r
            cy = strip_y + dot_r
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.border_light))
            p.drawEllipse(QRectF(cx - dot_r - 0.5, cy - dot_r - 0.5,
                                  dot_r * 2 + 1, dot_r * 2 + 1))
            p.setBrush(QColor(color_hex))
            p.drawEllipse(QRectF(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2))

        # 2. 迷你 UI 预览
        preview_y = self.COLOR_STRIP_H
        preview_w = w - 16
        preview_h = self.PREVIEW_H
        preview_x = 8

        preview_clip = QPainterPath()
        preview_clip.addRoundedRect(QRectF(preview_x, preview_y, preview_w, preview_h), t.radius_sm, t.radius_sm)
        p.setClipPath(preview_clip)

        sidebar_w = int(preview_w * self.SIDEBAR_RATIO)
        p.fillRect(QRect(preview_x, preview_y, sidebar_w, preview_h), QColor(pre.bg_sidebar))

        dot_s = 3
        dot_cx = preview_x + sidebar_w // 2
        for i in range(4):
            dy = preview_y + 8 + i * 8
            if i == 0:
                p.fillRect(QRectF(preview_x + 2, dy - 1, sidebar_w - 4, dot_s + 3),
                            QColor(pre.primary))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(pre.text_sidebar))
                p.drawEllipse(dot_cx - dot_s // 2, dy, dot_s, dot_s)

        detail_x = preview_x + sidebar_w
        detail_w = preview_w - sidebar_w
        p.fillRect(QRect(detail_x, preview_y, detail_w, preview_h), QColor(pre.bg_window))

        mc_margin = 5
        mc_x = detail_x + mc_margin
        mc_w = detail_w - mc_margin * 2
        mc_h = int((preview_h - mc_margin * 3) / 2)
        mc_radius = t.radius_xs

        for i in range(2):
            mc_y = preview_y + mc_margin + i * (mc_h + mc_margin)
            cp = QPainterPath()
            cp.addRoundedRect(QRectF(mc_x, mc_y, mc_w, mc_h), mc_radius, mc_radius)
            p.fillPath(cp, QColor(pre.bg_card))

            ly = mc_y + mc_h * 0.3
            p.fillRect(QRectF(mc_x + 5, ly, mc_w * 0.55, 2.5), QColor(pre.text_primary))
            ly2 = mc_y + mc_h * 0.55
            p.fillRect(QRectF(mc_x + 5, ly2, mc_w * 0.35, 2), QColor(pre.text_secondary))

            if i == 0:
                btn_w, btn_h = int(mc_w * 0.2), 6
                btn_x = mc_x + mc_w - btn_w - 5
                btn_y = mc_y + mc_h - btn_h - 4
                bp = QPainterPath()
                bp.addRoundedRect(QRectF(btn_x, btn_y, btn_w, btn_h), t.radius_xs, t.radius_xs)
                p.fillPath(bp, QColor(pre.primary))

        p.setClipping(False)

        # 3. 底部名称区域
        label_y = self.COLOR_STRIP_H + self.PREVIEW_H
        label_rect = QRect(0, label_y, w, self.LABEL_H)

        font = p.font()
        font.setPixelSize(12)
        font.setWeight(QFont.DemiBold if self._selected else QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(t.text_primary if self._selected else t.text_secondary))
        p.drawText(label_rect.adjusted(12, 0, -30, 0),
                    Qt.AlignVCenter | Qt.AlignLeft, self._label)

        if self._selected:
            ck_s = 16
            ck_x = w - ck_s - 10
            ck_y = label_y + (self.LABEL_H - ck_s) // 2
            ck_rect = QRectF(ck_x, ck_y, ck_s, ck_s)
            p.setBrush(QColor(t.primary))
            p.setPen(Qt.NoPen)
            p.drawEllipse(ck_rect)
            pen2 = p.pen()
            p.setPen(QColor("#FFFFFF"))
            pen2 = p.pen()
            pen2.setWidth(2)
            p.setPen(pen2)
            cx2, cy2 = int(ck_rect.center().x()), int(ck_rect.center().y())
            p.drawLine(cx2 - 3, cy2, cx2 - 1, cy2 + 2)
            p.drawLine(cx2 - 1, cy2 + 2, cx2 + 3, cy2 - 2)

        if self._hovered and not self._selected:
            p.setClipping(False)
            overlay = QColor(t.primary)
            overlay.setAlpha(15)
            rp = QPainterPath()
            rp.addRoundedRect(QRectF(0, 0, w, h), t.radius_md, t.radius_md)
            p.fillPath(rp, overlay)

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)

    def _apply_style(self) -> None:
        t = get_theme()
        self.configure_surface(
            background=t.bg_card,
            radius=t.radius_md,
            border_color=t.primary if self._selected else t.border_light,
            border_width=2.0 if self._selected else 1.0,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CustomThemeCard — 可删除的自定义主题卡片
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _CustomThemeCard(_ThemeSwatchCard):
    """自定义主题卡片，hover 时显示 × 删除按钮。"""

    delete_clicked = Signal(str)  # theme_id

    def __init__(self, key: str, label: str, preset: AppTheme, parent=None):
        super().__init__(key, label, preset, parent)

    def paintEvent(self, event):
        super().paintEvent(event)

        # hover 时在右上角画 × 删除按钮
        if self._hovered:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)

            btn_size = 18
            btn_x = self.width() - btn_size - 6
            btn_y = 6
            btn_rect = QRectF(btn_x, btn_y, btn_size, btn_size)

            # 圆形红色背景
            p.setBrush(QColor("#E04040"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(btn_rect)

            # 白色 ×
            p.setPen(QColor("#FFFFFF"))
            pen = p.pen()
            pen.setWidth(2)
            p.setPen(pen)
            m = 5
            p.drawLine(int(btn_x + m), int(btn_y + m),
                        int(btn_x + btn_size - m), int(btn_y + btn_size - m))
            p.drawLine(int(btn_x + btn_size - m), int(btn_y + m),
                        int(btn_x + m), int(btn_y + btn_size - m))

            p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 检查是否点击了删除按钮区域
            btn_size = 18
            btn_x = self.width() - btn_size - 6
            btn_y = 6
            btn_rect = QRectF(btn_x, btn_y, btn_size, btn_size)
            if btn_rect.contains(event.position()):
                self.delete_clicked.emit(self._key)
                return
        super().mousePressEvent(event)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AddThemeCard — "+" 新建卡片
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _AddThemeCard(RoundedSurfaceFrame):
    """虚线边框 + "＋" 图标的新建主题卡片。"""

    clicked = Signal()

    CARD_W = 180
    CARD_H = 148

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("add_theme_card")
        self._hovered = False
        self._apply_style()
        bind_theme(self, self._apply_style)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_style()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = get_theme()
        w, h = self.width(), self.height()

        # "＋" 号
        plus_size = 28
        cx, cy = w // 2, h // 2 - 10
        p.setPen(QColor(t.primary if self._hovered else t.text_hint))
        pen = p.pen()
        pen.setWidth(3)
        p.setPen(pen)
        p.drawLine(cx - plus_size // 2, cy, cx + plus_size // 2, cy)
        p.drawLine(cx, cy - plus_size // 2, cx, cy + plus_size // 2)

        # "新建" 文字
        font = p.font()
        font.setPixelSize(12)
        p.setFont(font)
        p.setPen(QColor(t.primary if self._hovered else t.text_hint))
        text_rect = QRect(0, cy + plus_size // 2 + 8, w, 20)
        p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, "新建配色")

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _apply_style(self) -> None:
        t = get_theme()
        self.configure_surface(
            background="rgba(0, 0, 0, 0)",
            radius=t.radius_md,
            border_color=t.primary if self._hovered else t.border,
            border_width=2.0,
            border_style=Qt.DashLine,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ThemeEditorDialog — 颜色编辑器弹窗
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _ColorButton(QFrame):
    """可点击的颜色选取圆形按钮。"""

    color_changed = Signal(str)

    def __init__(self, initial_color: str, parent=None):
        super().__init__(parent)
        self._color = initial_color
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    @property
    def color(self) -> str:
        return self._color

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            c = QColorDialog.getColor(QColor(self._color), self, "选择颜色")
            if c.isValid():
                self._color = c.name().upper()
                self._update_style()
                self.color_changed.emit(self._color)
        super().mousePressEvent(event)

    def _update_style(self):
        t = get_theme()
        self.setStyleSheet(f"""
            _ColorButton {{
                background: {self._color};
                border: 2px solid rgba(0,0,0,0.15);
                border-radius: {t.radius_full}px;
            }}
            _ColorButton:hover {{
                border: 2px solid rgba(0,0,0,0.35);
            }}
        """)


class _ThemeEditorDialog(QDialog):
    """自定义主题颜色编辑器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建自定义配色")
        self.setFixedSize(420, 460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._core_colors: dict[str, str] = {
            "primary": "#4A7FC5",
            "accent": "#D4883A",
            "bg_window": "#F2F4F6",
            "bg_card": "#FFFFFF",
            "bg_sidebar": "#E2E6EA",
            "text_primary": "#1A2030",
        }
        self._result_name = ""

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 名称输入
        name_label = QLabel("配色名称")
        name_label.setObjectName("editor_label")
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("例如：我的蓝色主题")
        apply_text_role(self._name_input, TextRole.BODY)
        from src.shared.ui.sizing import apply_size_class
        apply_size_class(self._name_input, "md")
        layout.addWidget(name_label)
        layout.addWidget(self._name_input)

        layout.addSpacing(4)

        # 颜色选取器
        color_defs = [
            ("primary",      "主色",     "按钮、链接、开关等"),
            ("accent",       "强调色",   "徽标、辅助标记"),
            ("bg_window",    "窗口背景", "页面底色"),
            ("bg_card",      "卡片背景", "内容卡片"),
            ("bg_sidebar",   "侧栏背景", "左侧导航"),
            ("text_primary", "主文字",   "标题和正文"),
        ]

        self._color_btns: dict[str, _ColorButton] = {}
        for key, label_text, desc in color_defs:
            row = QHBoxLayout()
            row.setSpacing(8)

            btn = _ColorButton(self._core_colors[key], self)
            btn.color_changed.connect(lambda c, k=key: self._on_color_changed(k, c))
            self._color_btns[key] = btn

            lbl_container = QVBoxLayout()
            lbl_container.setSpacing(1)
            lbl = QLabel(label_text)
            lbl.setObjectName("color_label")
            desc_lbl = QLabel(desc)
            desc_lbl.setObjectName("color_desc")
            lbl_container.addWidget(lbl)
            lbl_container.addWidget(desc_lbl)

            row.addWidget(btn)
            row.addLayout(lbl_container, 1)
            layout.addLayout(row)

        layout.addSpacing(8)

        # 预览
        self._preview_card = _ThemeSwatchCard(
            "preview", "预览",
            derive_theme_from_core(**self._core_colors),
            self,
        )
        preview_row = QHBoxLayout()
        preview_row.addStretch()
        preview_row.addWidget(self._preview_card)
        preview_row.addStretch()
        layout.addLayout(preview_row)

        layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setFixedSize(80, 34)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)

        self._confirm_btn = QPushButton("确定")
        self._confirm_btn.setObjectName("confirm_btn")
        self._confirm_btn.setFixedSize(80, 34)
        self._confirm_btn.setCursor(Qt.PointingHandCursor)
        self._confirm_btn.clicked.connect(self._on_confirm)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._confirm_btn)
        layout.addLayout(btn_row)

    def _on_color_changed(self, key: str, color: str):
        self._core_colors[key] = color
        # 更新预览
        new_theme = derive_theme_from_core(**self._core_colors)
        self._preview_card.set_preview_theme(new_theme)

    def _on_confirm(self):
        name = self._name_input.text().strip()
        if not name:
            name = "自定义主题"
        self._result_name = name
        self.accept()

    def get_result(self) -> tuple[str, dict[str, str]]:
        """返回 (name, core_colors)。"""
        return self._result_name, dict(self._core_colors)

    def _apply_theme(self):
        t = get_theme()
        input_qss = build_framed_input_stylesheet(
            t,
            background=t.bg_card,
            focus_border_color=t.primary,
            border_radius=t.radius_sm,
            padding_x=10,
            padding_y=0,
        )
        apply_text_role(self._name_input, TextRole.BODY)
        self.setStyleSheet(f"""
            _ThemeEditorDialog {{
                background: {t.bg_window};
            }}
            #editor_label {{
                font-size: 14px; font-weight: bold;
                color: {t.text_primary}; background: transparent;
            }}
            #color_label {{
                font-size: 13px; font-weight: {t.font_weight_emphasis};
                color: {t.text_primary}; background: transparent;
            }}
            #color_desc {{
                font-size: 11px;
                color: {t.text_hint}; background: transparent;
            }}
            {input_qss}
            QPushButton {{
                background: {t.bg_card};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                font-size: 13px;
                color: {t.text_primary};
            }}
            QPushButton:hover {{
                background: {t.bg_hover};
                border-color: {t.primary};
            }}
            #confirm_btn {{
                background: {t.primary};
                color: {t.text_on_primary};
                border: none;
            }}
            #confirm_btn:hover {{
                background: {t.primary_hover};
            }}
        """)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ThemePanel — 主题配色面板
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ThemePanel(BasePanel):
    """主题外观设置面板。"""

    def _setup_ui(self) -> None:
        self.setObjectName("ThemePanel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # ── 标题 ──
        self._title = QLabel("外观")
        self._subtitle = QLabel("选择界面配色方案，所有更改即时生效")
        outer.addWidget(self._title)
        outer.addSpacing(4)
        outer.addWidget(self._subtitle)
        outer.addSpacing(24)

        # ── 内置预设区 ──
        preset_container = QWidget(self)
        self._preset_flow = FlowLayout(preset_container, h_spacing=14, v_spacing=14)

        self._cards: dict[str, _ThemeSwatchCard] = {}
        for key, label, preset in _PRESETS:
            card = _ThemeSwatchCard(key, label, preset, preset_container)
            card.clicked.connect(self._on_preset_clicked)
            self._cards[key] = card
            self._preset_flow.addWidget(card)

        outer.addWidget(preset_container)
        outer.addSpacing(20)

        # ── 分隔线 + 自定义区标题 ──
        self._custom_divider = Divider(parent=self)
        outer.addWidget(self._custom_divider)
        outer.addSpacing(14)

        self._custom_title = QLabel("自定义配色")
        outer.addWidget(self._custom_title)
        self._custom_theme_error = QLabel("", self)
        self._custom_theme_error.setObjectName("custom_theme_load_error")
        self._custom_theme_error.setWordWrap(True)
        self._custom_theme_error.setVisible(False)
        outer.addWidget(self._custom_theme_error)
        outer.addSpacing(14)

        # ── 自定义主题区 ──
        custom_container = QWidget(self)
        self._custom_flow = FlowLayout(custom_container, h_spacing=14, v_spacing=14)

        # 加载已保存的自定义主题
        self._store = CustomThemeStore()
        self._custom_theme_load_failed = False
        try:
            self._store.load()
        except CustomThemeStoreError as exc:
            self._custom_theme_load_failed = True
            self._custom_theme_error.setText(
                "自定义主题文件加载失败，已停止自定义主题写入以保护原文件。\n"
                f"{exc}"
            )
            self._custom_theme_error.setVisible(True)
        self._custom_cards: dict[str, _CustomThemeCard] = {}
        for entry in self._store.entries:
            self._add_custom_card(entry.id, entry.name, entry.to_app_theme(), custom_container)

        # "+" 新建卡片
        self._add_card = _AddThemeCard(custom_container)
        self._add_card.clicked.connect(self._on_add_clicked)
        self._add_card.setEnabled(not self._custom_theme_load_failed)
        if self._custom_theme_load_failed:
            self._add_card.setToolTip("请先修复自定义主题 JSON 文件，再新建主题。")
        self._custom_flow.addWidget(self._add_card)

        outer.addWidget(custom_container)
        outer.addStretch()

        # ── 底部提示 ──
        self._hint = QLabel("配色切换后所有面板即时刷新，无需重启。")
        outer.addWidget(self._hint)

        # 初始选中
        self._sync_selection()
        self._apply_theme()
        bind_theme(self, self._on_theme_changed)

    def _connect_signals(self) -> None:
        pass

    # ── 内置预设点击 ──

    def _on_preset_clicked(self, key: str) -> None:
        for preset_key, _, preset in _PRESETS:
            if preset_key == key:
                set_theme(preset)
                break

    # ── 自定义主题点击 ──

    def _on_custom_clicked(self, theme_id: str) -> None:
        entry = self._store.get_by_id(theme_id)
        if entry:
            set_theme(entry.to_app_theme())

    # ── 删除自定义主题 ──

    def _on_delete_clicked(self, theme_id: str) -> None:
        # 如果当前正在使用这个主题，先切回 LIGHT
        entry = self._store.get_by_id(theme_id)
        if entry:
            current = get_theme()
            entry_theme = entry.to_app_theme()
            if _themes_match(current, entry_theme):
                set_theme(LIGHT)

        if self._store.delete(theme_id):
            self._remove_custom_card(theme_id)
            self._sync_selection()

    # ── 新建自定义主题 ──

    def _on_add_clicked(self) -> None:
        dlg = _ThemeEditorDialog(self)
        if dlg.exec() == QDialog.Accepted:
            name, core = dlg.get_result()
            entry = self._store.add(name, core)
            self._insert_custom_card_before_add(
                entry.id,
                entry.name,
                entry.to_app_theme(),
            )
            # 立即切换到新主题
            set_theme(entry.to_app_theme())

    # ── 自定义卡片增量变更 ──

    def _insert_custom_card_before_add(
        self,
        theme_id: str,
        name: str,
        theme: AppTheme,
    ) -> _CustomThemeCard:
        """在末尾的“新建”卡前增量插入一张主题卡。

        已存在的卡片和“新建”卡都保留原对象，避免因全量重建导致
        FlowLayout 再次换行和画面跳动。
        """
        container = self._add_card.parentWidget()
        self._custom_flow.removeWidget(self._add_card)
        card = self._add_custom_card(theme_id, name, theme, container)
        self._custom_flow.addWidget(self._add_card)
        container.updateGeometry()
        return card

    def _remove_custom_card(self, theme_id: str) -> bool:
        """只移除指定主题卡，不触碰其他卡片对象。"""
        card = self._custom_cards.pop(theme_id, None)
        if card is None:
            return False

        self._custom_flow.removeWidget(card)
        card.deleteLater()
        container = self._add_card.parentWidget()
        container.updateGeometry()
        return True

    def _add_custom_card(
        self,
        theme_id: str,
        name: str,
        theme: AppTheme,
        parent: QWidget,
    ) -> _CustomThemeCard:
        """创建一张自定义主题卡片并加入布局。"""
        card = _CustomThemeCard(theme_id, name, theme, parent)
        card.clicked.connect(self._on_custom_clicked)
        card.delete_clicked.connect(self._on_delete_clicked)
        self._custom_cards[theme_id] = card
        self._custom_flow.addWidget(card)
        return card

    # ── 主题变化回调 ──

    def _on_theme_changed(self) -> None:
        self._sync_selection()
        self._apply_theme()

    def _sync_selection(self) -> None:
        current = get_theme()

        # 检查内置预设
        for key, card in self._cards.items():
            matching = any(
                pk == key
                and _themes_match(current, preset)
                for pk, _, preset in _PRESETS
            )
            card.set_selected(matching)

        # 检查自定义主题
        for theme_id, card in self._custom_cards.items():
            entry = self._store.get_by_id(theme_id)
            if entry:
                entry_theme = entry.to_app_theme()
                card.set_selected(_themes_match(current, entry_theme))
            else:
                card.set_selected(False)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(f"""
            #ThemePanel {{
                background: {t.bg_window};
                border-bottom-right-radius: {t.shell_radius}px;
            }}
        """)
        self._title.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {t.text_primary}; "
            f"background: transparent;"
        )
        self._subtitle.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_secondary}; "
            f"background: transparent;"
        )
        self._custom_title.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {t.text_secondary}; "
            f"background: transparent;"
        )
        self._custom_theme_error.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.error}; "
            f"background: transparent; padding: 6px 0;"
        )
        self._hint.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint}; "
            f"background: transparent; padding-top: 8px;"
        )
