"""
AppTheme — 全局配色与样式系统

设计原则：
1. 单例 + 运行时可换：所有控件通过 get_theme() 读值，不硬编码
2. 预设配色：内置多套配色方案（LIGHT / DARK / OCEAN），均为平等的配色预设
3. 信号通知：配色切换时触发 theme_changed 信号，控件自动刷新

命名规则：
- 颜色：{语义}_{层级}，如 text_primary, bg_card, border_focus
- 尺寸：{属性}_{级别}，级别统一用 xs/sm/md/lg/xl/xxl
- 组件色：{组件}_{状态}，如 switch_on, tab_active_text

用法::

    from src.shared.ui.theme import get_theme, set_theme, DARK, OCEAN

    # 读取（控件内部）
    color = get_theme().primary

    # 切换配色
    set_theme(DARK)

    # 自定义配色
    set_theme(AppTheme(primary="#FF6B35"))
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import warnings

try:
    from src.qt_api import QObject, Signal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False


@dataclass
class AppTheme:
    """全局配色与样式参数。

    所有颜色值为 hex 字符串，控件使用时通过 QColor(theme.xxx) 转换。
    尺寸值为 int (px)，直接用于 setFixedHeight / border-radius 等。
    """

    # ━━ 品牌色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    primary: str = "#1677FF"
    primary_hover: str = "#4096FF"
    primary_pressed: str = "#0958D9"
    primary_light: str = "#E6F4FF"       # 品牌浅底（选中行、高亮背景）
    accent: str = "#FA8C16"
    accent_hover: str = "#FFA940"

    # ━━ Logo 双色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 跟随主题色调: 蓝色主题→深蓝+浅蓝, 深色主题→亮白+浅灰, 海洋主题→深青+浅青
    logo_dark: str = "#1E293B"            # Logo 深色部分
    logo_light: str = "#4096FF"           # Logo 浅色部分

    # ━━ 表面色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    bg_window: str = "#F8FAFC"           # 窗口/页面背景
    bg_card: str = "#FFFFFF"             # 卡片/面板背景
    bg_input: str = "#FFFFFF"            # 输入框背景
    bg_hover: str = "#F1F5F9"            # 悬停背景
    bg_selected: str = "#E6F4FF"         # 选中背景
    bg_tooltip: str = "#1E293B"          # 提示框背景

    # ━━ 文字 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    text_primary: str = "#1E293B"        # 主文字
    text_secondary: str = "#475569"      # 次要文字
    text_hint: str = "#94A3B8"           # 占位/提示文字
    text_disabled: str = "#CBD5E1"       # 禁用文字
    text_on_primary: str = "#FFFFFF"     # 品牌色上的文字
    text_on_accent: str = "#FFFFFF"      # 强调色上的文字
    text_link: str = "#1677FF"           # 链接文字

    # ━━ 侧边栏 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    bg_sidebar: str = "#F1F5F9"          # 侧边栏背景（浅灰）
    bg_sidebar_active: str = "#E2E8F0"   # 侧边栏选中项背景
    text_sidebar: str = "#64748B"        # 侧边栏图标默认色
    text_sidebar_active: str = "#0F172A" # 侧边栏选中文字

    # ━━ 窗口控制 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    window_close_hover_bg: str = "#E81123"    # 关闭按钮 hover 背景
    window_close_hover_text: str = "#FFFFFF"  # 关闭按钮 hover 文字

    # ━━ 图标 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    icon_primary: str = "#475569"         # 主图标色
    icon_secondary: str = "#94A3B8"       # 次要图标色
    icon_accent: str = "#1677FF"          # 强调图标色（选中/激活）

    # ━━ 边框 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    border: str = "#CBD5E1"              # 默认边框（ΔL ≥12% vs bg_card #FFFFFF）
    border_light: str = "#D8DEE8"        # 浅边框（ΔL ≥10% vs bg_card #FFFFFF）
    border_focus: str = "#1677FF"        # 聚焦边框
    border_error: str = "#FF4D4F"        # 错误边框

    border_width_sm: int = 1             # 细边框 1px
    border_width_md: int = 1             # 默认边框 1px
    border_width_lg: int = 2             # 粗边框 2px

    # ━━ 分割线 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    divider: str = "#E2E8F0"             # 水平/垂直分割线

    # ━━ 遮罩 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    overlay: str = "rgba(0, 0, 0, 0.45)" # 弹窗蒙版

    # ━━ 状态色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    success: str = "#52C41A"
    success_bg: str = "#F6FFED"
    warning: str = "#FAAD14"
    warning_bg: str = "#FFFBE6"
    error: str = "#FF4D4F"
    error_hover: str = "#FF7875"          # 危险按钮 hover
    error_pressed: str = "#D9363E"        # 危险按钮 pressed
    error_bg: str = "#FFF2F0"
    info: str = "#1677FF"
    info_bg: str = "#E6F4FF"

    # ━━ 开关 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    switch_on: str = "#1677FF"
    switch_off: str = "#CBD5E1"
    switch_thumb: str = "#FFFFFF"
    switch_disabled: str = "#E2E8F0"

    # ━━ 进度条 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    progress_track: str = "#F1F5F9"
    progress_fill: str = "#1677FF"

    # ━━ 滚动条 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    scrollbar_track: str = "transparent"
    scrollbar_thumb: str = "#CBD5E1"
    scrollbar_thumb_hover: str = "#94A3B8"

    # ━━ 标签页 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    tab_active_text: str = "#1677FF"
    tab_active_border: str = "#1677FF"
    tab_inactive_text: str = "#64748B"
    tab_bg: str = "transparent"

    # ━━ 圆角 (px) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    radius_xs: int = 4                   # 微圆角（徽标）
    radius_sm: int = 6                   # 小圆角（按钮、输入框）
    radius_md: int = 10                  # 默认圆角（卡片）
    radius_lg: int = 14                  # 大圆角（对话框）
    radius_xl: int = 20                  # 超大圆角（浮层）
    radius_full: int = 9999              # 全圆（胶囊按钮）

    # ── Shared control tokens (px) ──────────────────────────────────────────
    button_radius: int = 6
    button_padding_x: int = 14
    button_padding_y: int = 4
    button_height_md: int = 32
    button_font_weight: int = 500

    input_radius: int = 6
    input_padding_x: int = 8
    input_padding_y: int = 4
    input_icon_size: int = 16
    input_clear_button_size: int = 20
    input_separator_width: int = 1
    input_separator_height: int = 16

    checkbox_size: int = 18
    checkbox_radius: int = 5
    checkbox_border_width: int = 1
    checkbox_border_color: str = ""
    checkbox_hover_border_color: str = ""
    checkbox_focus_border_color: str = ""
    checkbox_bg: str = ""
    checkbox_checked_bg: str = ""
    checkbox_checked_border_color: str = ""
    checkbox_checkmark_color: str = ""
    checkbox_disabled_bg: str = ""
    checkbox_disabled_border_color: str = ""
    checkbox_disabled_checkmark_color: str = ""
    checkbox_label_gap: int = 8

    radio_size: int = 18
    radio_ring_width: int = 1
    radio_border_color: str = ""
    radio_hover_border_color: str = ""
    radio_focus_border_color: str = ""
    radio_bg: str = ""
    radio_checked_ring_color: str = ""
    radio_dot_size: int = 7
    radio_dot_color: str = ""
    radio_disabled_bg: str = ""
    radio_disabled_border_color: str = ""
    radio_disabled_dot_color: str = ""
    radio_label_gap: int = 8

    selection_label_color: str = ""
    selection_label_checked_color: str = ""
    selection_label_disabled_color: str = ""

    radio_indicator_diameter: int = 18
    radio_dot_diameter: int = 7
    radio_hit_padding_x: int = 6
    radio_hit_padding_y: int = 4
    radio_color_ring: str = ""
    radio_color_ring_hover: str = ""
    radio_color_ring_checked: str = ""
    radio_color_ring_disabled: str = ""
    radio_color_dot: str = ""
    radio_color_dot_disabled: str = ""
    radio_color_bg: str = ""
    radio_color_bg_disabled: str = ""
    radio_focus_ring_color: str = ""
    radio_focus_ring_width: int = 2

    slider_track_height: int = 4
    slider_handle_diameter: int = 20
    slider_handle_ring_width: int = 1
    slider_active_track_color: str = ""
    slider_inactive_track_color: str = ""
    slider_handle_color: str = ""
    slider_handle_border_color: str = ""
    slider_handle_hover_border_color: str = ""
    slider_handle_pressed_border_color: str = ""
    slider_handle_disabled_color: str = ""
    slider_focus_ring_color: str = ""
    slider_focus_ring_width: int = 2
    slider_hit_extra_radius: int = 6

    combo_arrow_zone_width: int = 28
    combo_arrow_size: int = 10
    combo_popup_padding: int = 4
    combo_popup_item_padding_x: int = 12
    combo_popup_item_padding_y: int = 6
    combo_popup_offset_y: int = 2
    combo_popup_radius: int = 10

    spin_button_width: int = 24

    color_picker_swatch_size: int = 28
    color_picker_height: int = 32

    progress_bar_height: int = 8
    progress_cancel_min_width: int = 50
    progress_indicator_height: int = 60

    dialog_detail_min_height: int = 100
    dialog_detail_max_height: int = 180
    dialog_path_icon_width: int = 20

    icon_button_size: int = 36
    icon_button_icon_size: int = 20

    override_badge_height: int = 24
    override_badge_icon_size: int = 16
    override_badge_restore_height: int = 20

    module_step_item_height: int = 32
    module_step_status_size: int = 16

    collapsible_toggle_height: int = 32
    collapsible_toggle_padding_x: int = 8
    collapsible_content_indent: int = 12
    collapsible_content_padding_y: int = 8

    style_preview_min_height: int = 60
    style_preview_padding: int = 12

    card_padding_x: int = 20
    card_padding_y: int = 20
    card_padding_top: int = 16
    card_padding_bottom: int = 20
    card_spacing: int = 12
    card_content_spacing: int = 4

    dialog_icon_container_size: int = 40
    dialog_icon_size: int = 24
    dialog_close_button_size: int = 32

    form_row_label_width: int = 120
    form_row_height: int = 36

    spacing_input_unit_width: int = 60

    heading_panel_levels_width: int = 100
    heading_panel_sidebar_width: int = 200
    heading_panel_preset_width: int = 220
    heading_panel_preview_row_height: int = 40
    heading_panel_preview_tag_width: int = 45
    heading_panel_editor_combo_width: int = 180
    heading_panel_reference_combo_width: int = 160
    heading_panel_raw_template_width: int = 150
    heading_panel_short_input_width: int = 80
    heading_panel_tiny_input_width: int = 40

    # ━━ 阴影 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    shadow_color: str = "rgba(0, 0, 0, 0.08)"
    shadow_color_dialog_alpha: int = 20   # 弹窗阴影透明度 (0-255)
    shadow_blur_sm: int = 8              # 轻阴影
    shadow_blur_md: int = 16             # 默认阴影
    shadow_blur_lg: int = 32             # 重阴影（悬浮面板）
    shadow_blur_xl: int = 48             # 弹窗阴影
    shadow_offset_y: int = 4             # Y 偏移
    shadow_offset_y_lg: int = 16         # 弹窗 Y 偏移

    # ━━ 字体 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    font_family: str = "'Segoe UI', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'Microsoft YaHei', sans-serif"

    font_size_xs: int = 11               # 角标、徽标
    font_size_sm: int = 12               # 辅助文字、脚注
    font_size_md: int = 13               # 正文（基准）
    font_size_lg: int = 15               # 副标题、强调
    font_size_xl: int = 16               # 卡片标题、对话框标题
    font_size_xxl: int = 20              # 页面标题

    font_weight_normal: int = 400
    font_weight_bold: int = 700

    # ━━ 间距 (px) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    spacing_xl: int = 24
    spacing_xxl: int = 32                # 弹窗级大留白

    # ━━ 控件高度 (px) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    control_height_sm: int = 28          # 紧凑型（表格内、工具栏）
    control_height_md: int = 36          # 默认（输入框、按钮）
    control_height_lg: int = 44          # 大号（主操作按钮）

    # ━━ 动画时长 (ms) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    anim_duration_fast: int = 100        # 微交互（hover、toggle）
    anim_duration_normal: int = 200      # 默认过渡
    anim_duration_slow: int = 400        # 面板展开/折叠

    # ── 工具方法 ──

    def __post_init__(self) -> None:
        if not self.checkbox_border_color:
            self.checkbox_border_color = self.border
        if not self.checkbox_hover_border_color:
            self.checkbox_hover_border_color = self.border_focus
        if not self.checkbox_focus_border_color:
            self.checkbox_focus_border_color = self.primary
        if not self.checkbox_bg:
            self.checkbox_bg = self.bg_input
        if not self.checkbox_checked_bg:
            self.checkbox_checked_bg = self.primary
        if not self.checkbox_checked_border_color:
            self.checkbox_checked_border_color = self.primary
        if not self.checkbox_checkmark_color:
            self.checkbox_checkmark_color = self.text_on_primary
        if not self.checkbox_disabled_bg:
            self.checkbox_disabled_bg = self.bg_hover
        if not self.checkbox_disabled_border_color:
            self.checkbox_disabled_border_color = self.border_light
        if not self.checkbox_disabled_checkmark_color:
            self.checkbox_disabled_checkmark_color = self.text_disabled

        if not self.radio_border_color:
            self.radio_border_color = self.border
        if not self.radio_hover_border_color:
            self.radio_hover_border_color = self.border_focus
        if not self.radio_focus_border_color:
            self.radio_focus_border_color = self.primary
        if not self.radio_bg:
            self.radio_bg = self.bg_input
        if not self.radio_checked_ring_color:
            self.radio_checked_ring_color = self.primary
        if not self.radio_dot_color:
            self.radio_dot_color = self.primary
        if not self.radio_disabled_bg:
            self.radio_disabled_bg = self.bg_hover
        if not self.radio_disabled_border_color:
            self.radio_disabled_border_color = self.border_light
        if not self.radio_disabled_dot_color:
            self.radio_disabled_dot_color = self.text_disabled

        if not self.selection_label_color:
            self.selection_label_color = self.text_secondary
        if not self.selection_label_checked_color:
            self.selection_label_checked_color = self.text_primary
        if not self.selection_label_disabled_color:
            self.selection_label_disabled_color = self.text_disabled

        if not self.radio_color_ring:
            self.radio_color_ring = self.radio_border_color or self.border
        if not self.radio_color_ring_hover:
            self.radio_color_ring_hover = self.radio_hover_border_color or self.border_focus
        if not self.radio_color_ring_checked:
            self.radio_color_ring_checked = self.radio_checked_ring_color or self.primary
        if not self.radio_color_ring_disabled:
            self.radio_color_ring_disabled = self.radio_disabled_border_color or self.border_light
        if not self.radio_color_dot:
            self.radio_color_dot = self.radio_dot_color or self.primary
        if not self.radio_color_dot_disabled:
            self.radio_color_dot_disabled = self.radio_disabled_dot_color or self.text_disabled
        if not self.radio_color_bg:
            self.radio_color_bg = self.radio_bg or self.bg_input
        if not self.radio_color_bg_disabled:
            self.radio_color_bg_disabled = self.radio_disabled_bg or self.bg_hover
        if not self.radio_focus_ring_color:
            self.radio_focus_ring_color = self.radio_focus_border_color or self.primary

        if not self.slider_active_track_color:
            self.slider_active_track_color = self.primary
        if not self.slider_inactive_track_color:
            self.slider_inactive_track_color = self.progress_track
        if not self.slider_handle_color:
            self.slider_handle_color = self.bg_card
        if not self.slider_handle_border_color:
            self.slider_handle_border_color = self.border
        if not self.slider_handle_hover_border_color:
            self.slider_handle_hover_border_color = self.border_focus
        if not self.slider_handle_pressed_border_color:
            self.slider_handle_pressed_border_color = self.primary_pressed
        if not self.slider_handle_disabled_color:
            self.slider_handle_disabled_color = self.bg_hover
        if not self.slider_focus_ring_color:
            self.slider_focus_ring_color = self.primary

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def merge(self, overrides: dict[str, Any]) -> AppTheme:
        """返回新配色，用 overrides 覆盖当前值。"""
        data = self.to_dict()
        data.update(overrides)
        return AppTheme(**{k: v for k, v in data.items() if k in _FIELD_NAMES})

    def validate_contrast(self) -> list[str]:
        """检查关键 Token 对的亮度对比度，返回警告列表。

        用于新增主题时的自动化检查。对比度阈值基于
        UI 可用性标准（非 WCAG AA/AAA，仅亮度差）。
        """
        pairs = [
            ('text_on_primary', 'primary',   40, '按钮/图标前景 vs 品牌色'),
            ('text_on_accent',  'accent',    30, '强调色上的文字 vs 强调色'),
            ('text_primary',    'bg_card',   40, '主文字 vs 卡片背景'),
            ('border_light',    'bg_card',   10, '浅边框 vs 卡片背景'),
            ('border',          'bg_card',   12, '默认边框 vs 卡片背景'),
        ]
        warnings = []
        for fg_tok, bg_tok, threshold, desc in pairs:
            fg = getattr(self, fg_tok, '')
            bg = getattr(self, bg_tok, '')
            if not fg.startswith('#') or not bg.startswith('#'):
                continue
            fl = _hex_luminance(fg)
            bl = _hex_luminance(bg)
            delta = abs(fl - bl) * 100
            if delta < threshold:
                warnings.append(
                    f'{fg_tok}({fg}) vs {bg_tok}({bg}): '
                    f'ΔL={delta:.0f}% < {threshold}% — {desc}'
                )
        return warnings


def _hex_luminance(h: str) -> float:
    """HEX 颜色 → 感知亮度 (0~1)。"""
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


# 字段名缓存
_FIELD_NAMES = {f.name for f in AppTheme.__dataclass_fields__.values()}


# ━━ 预设配色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LIGHT = AppTheme()  # 默认浅色

DARK = AppTheme(
    # 深色配色——高质量暗黑模式, inspired by Vercel/Linear
    # 降低饱和度以减少视觉疲劳
    primary="#1677FF", primary_hover="#4096FF",
    primary_pressed="#0958D9", primary_light="#111A2C",
    accent="#E0993A",       # 柔化橙（原 #FA8C16 太刺眼）
    logo_dark="#E2E8F0", logo_light="#94A3B8",
    bg_window="#0B0F19", bg_card="#111827", bg_input="#1F2937",
    bg_hover="#1F2937", bg_selected="#1E293B", bg_tooltip="#334155",
    bg_sidebar="#111827", bg_sidebar_active="#1E293B",
    text_sidebar="#64748B", text_sidebar_active="#E2E8F0",
    text_primary="#E2E8F0",    # 柔化白（原 #F8FAFC 太亮）
    text_secondary="#94A3B8",
    text_hint="#64748B", text_disabled="#475569",
    text_on_primary="#FFFFFF", text_on_accent="#FFFFFF",
    text_link="#4096FF",
    window_close_hover_bg="#E81123", window_close_hover_text="#FFFFFF",
    border="#334155", border_light="#293548",  # ΔL ≥12% vs bg_card #111827
    border_focus="#1677FF", border_error="#E07070",
    divider="#1E293B", overlay="rgba(0, 0, 0, 0.75)",
    success="#6EBC8A",        # 柔化绿（原 #4ADE80 太刺眼）
    success_bg="#14532D",
    warning="#D4A843",        # 柔化金（原 #FBBF24 太刺眼）
    warning_bg="#78350F",
    error="#E07070",          # 柔化红（原 #F87171 太刺眼）
    error_hover="#ECA5A5",
    error_pressed="#CC5555",
    error_bg="#7F1D1D",
    info="#6BA3D4",           # 柔化蓝（原 #38BDF8 太刺眼）
    info_bg="#0C4A6E",
    switch_on="#1677FF", switch_off="#334155",
    switch_thumb="#E2E8F0", switch_disabled="#1E293B",
    progress_track="#1E293B", progress_fill="#1677FF",
    scrollbar_track="transparent", scrollbar_thumb="#334155",
    scrollbar_thumb_hover="#475569",
    tab_active_text="#4096FF", tab_active_border="#4096FF",
    tab_inactive_text="#64748B",
    icon_primary="#B0BAC9",   # 柔化图标色（原 #CBD5E1 太亮）
    icon_secondary="#64748B",
    icon_accent="#1677FF",
    shadow_color="rgba(0, 0, 0, 0.50)",
)

OCEAN = AppTheme(
    # 海蓝配色
    primary="#0EA5E9", primary_hover="#38BDF8",
    primary_pressed="#0284C7", primary_light="#E0F2FE",
    accent="#F59E0B", accent_hover="#FBBF24",
    logo_dark="#0369A1", logo_light="#38BDF8",
    bg_window="#F0F9FF", bg_card="#FFFFFF", bg_input="#FFFFFF",
    bg_hover="#E0F2FE", bg_selected="#BAE6FD", bg_tooltip="#0c4a6e",
    bg_sidebar="#E0F2FE", bg_sidebar_active="#BAE6FD",
    text_sidebar="#0369A1", text_sidebar_active="#0C4A6E",
    text_primary="#0c4a6e", text_secondary="#0369a1",
    text_hint="#38bdf8", text_link="#0ea5e9",
    border="#bae6fd", border_light="#BAE6FD", border_focus="#0ea5e9",  # border_light 同 border
    divider="#bae6fd",
    error="#EF4444", error_hover="#F87171", error_pressed="#DC2626",
    switch_on="#0ea5e9", progress_fill="#0ea5e9",
    tab_active_text="#0ea5e9", tab_active_border="#0ea5e9",
    icon_primary="#0c4a6e", icon_secondary="#38bdf8",
    icon_accent="#0ea5e9",
)

EYECARE = AppTheme(
    # 护眼配色 —— 暖色低蓝光暗色主题，灵感来源于 Antigravity 配色
    # 使用温暖的棕褐色系，减少蓝光刺激，适合长时间编辑场景
    primary="#D4915E",            # 暖琥珀色
    primary_hover="#E0A97A",
    primary_pressed="#B87A4A",
    primary_light="#2A2118",      # 品牌浅底（深暖色）
    accent="#C4A35A",             # 暖金色
    accent_hover="#D4B76A",

    logo_dark="#E8DDD0",          # Logo 深色部分（用亮色因为底色深）
    logo_light="#8B7355",         # Logo 浅色部分

    bg_window="#1C1816",          # 窗口背景：深棕
    bg_card="#231F1B",            # 卡片背景：略浅棕
    bg_input="#2A2520",           # 输入框背景
    bg_hover="#332D26",           # 悬停背景
    bg_selected="#3D3429",        # 选中背景
    bg_tooltip="#3D3429",         # 提示框背景

    bg_sidebar="#211D19",         # 侧边栏
    bg_sidebar_active="#332D26",
    text_sidebar="#8B7355",
    text_sidebar_active="#E8DDD0",

    text_primary="#E8DDD0",       # 主文字：暖奶油色
    text_secondary="#A89880",     # 次要文字
    text_hint="#7A6B55",          # 提示文字
    text_disabled="#5A4D3E",      # 禁用文字
    text_on_primary="#1C1816",    # 品牌色上的文字（深色）
    text_on_accent="#1C1816",
    text_link="#D4915E",          # 链接

    window_close_hover_bg="#C0392B",
    window_close_hover_text="#FFFFFF",

    icon_primary="#C4B5A0",       # 主图标色
    icon_secondary="#8B7355",     # 次要图标色
    icon_accent="#D4915E",        # 强调图标色

    border="#4D4237",             # 默认边框（ΔL ≥12% vs bg_card #231F1B）
    border_light="#453A2E",       # 浅边框（ΔL ≥10% vs bg_card #231F1B）
    border_focus="#D4915E",       # 聚焦边框
    border_error="#C0392B",       # 错误边框

    divider="#332D26",
    overlay="rgba(0, 0, 0, 0.65)",

    success="#7FB069",            # 柔和绿
    success_bg="#2A3326",
    warning="#D4A843",            # 柔和金
    warning_bg="#332D1A",
    error="#C0392B",              # 柔和红
    error_hover="#D9534F",
    error_pressed="#A33025",
    error_bg="#3D2420",
    info="#6B9BD2",               # 柔和蓝
    info_bg="#1A2A3D",

    switch_on="#D4915E",
    switch_off="#3D3429",
    switch_thumb="#E8DDD0",
    switch_disabled="#2A2520",

    progress_track="#332D26",
    progress_fill="#D4915E",

    scrollbar_track="transparent",
    scrollbar_thumb="#3D3429",
    scrollbar_thumb_hover="#5A4D3E",

    tab_active_text="#D4915E",
    tab_active_border="#D4915E",
    tab_inactive_text="#7A6B55",

    shadow_color="rgba(0, 0, 0, 0.40)",
)


WARM_LIGHT = AppTheme(
    # 护眼暖光 —— 基于 Antigravity IDE 实际配色采集
    # 暖黄色系浅色主题，L=88-91%，H≈50°，降低白光刺激
    primary="#697A98",            # 蓝灰（Antigravity Tab 高亮色）
    primary_hover="#7D8FAB",
    primary_pressed="#566883",
    primary_light="#E8E5D0",      # 品牌浅底
    accent="#B8860B",             # 暗金色
    accent_hover="#CC9B20",

    logo_dark="#4A3F33",          # Logo 深色部分
    logo_light="#697A98",         # Logo 浅色部分

    bg_window="#ECE9D6",          # 窗口背景：暖米色（采集值）
    bg_card="#F7F1D8",            # 卡片/编辑器背景：暖黄白（采集值）
    bg_input="#F2EDD8",           # 输入框背景
    bg_hover="#E3DFC8",           # 悬停背景
    bg_selected="#D8D4BA",        # 选中背景
    bg_tooltip="#4A3F33",         # 提示框背景（深色）

    bg_sidebar="#E5E2CE",         # 侧边栏
    bg_sidebar_active="#D8D4BA",
    text_sidebar="#8C7D6C",       # 侧边栏图标（采集值）
    text_sidebar_active="#4A3F33",

    text_primary="#4A3F33",       # 主文字：深棕
    text_secondary="#6B5D4E",     # 次要文字
    text_hint="#9E8E7A",          # 提示文字
    text_disabled="#BFB39E",      # 禁用文字
    text_on_primary="#FFFFFF",    # 品牌色上的文字（必须纯白确保高对比度）
    text_on_accent="#FFFFFF",
    text_link="#697A98",

    window_close_hover_bg="#E81123",
    window_close_hover_text="#FFFFFF",

    icon_primary="#6B5D4E",       # 主图标色
    icon_secondary="#9E8E7A",     # 次要图标色
    icon_accent="#697A98",        # 强调图标色

    border="#D1CCB8",             # 默认边框（采集 Tab 栏色）
    border_light="#C8C3AC",       # 浅边框（ΔL ≥12% vs bg_card #F7F1D8）
    border_focus="#697A98",       # 聚焦边框
    border_error="#C0392B",       # 错误边框

    divider="#D1CCB8",
    overlay="rgba(74, 63, 51, 0.45)",

    success="#6B8E4E",            # 柔和森绿
    success_bg="#E8EFD8",
    warning="#B8860B",            # 暗金色
    warning_bg="#F5ECD0",
    error="#B33A3A",              # 柔和暖红
    error_hover="#CC4E4E",
    error_pressed="#993030",
    error_bg="#F5E0D8",
    info="#697A98",               # 蓝灰
    info_bg="#E0E4EC",

    switch_on="#697A98",
    switch_off="#D1CCB8",
    switch_thumb="#F7F1D8",
    switch_disabled="#DDD9C5",

    progress_track="#D8D4BA",
    progress_fill="#697A98",

    scrollbar_track="transparent",
    scrollbar_thumb="#CCC7B0",
    scrollbar_thumb_hover="#B8B39E",

    tab_active_text="#697A98",
    tab_active_border="#697A98",
    tab_inactive_text="#8C7D6C",

    shadow_color="rgba(74, 63, 51, 0.20)",  # 暖色浅底需更强阴影
)


# ━━ 全局单例 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _ThemeManager:
    """配色管理器（单例）。

    控件不持有颜色常量，而是每次绘制时调 get_theme() 获取当前值。
    切换时通过 Qt 信号通知所有已连接的控件刷新。
    """

    def __init__(self):
        self._theme: AppTheme = LIGHT
        if _HAS_QT:
            self._notifier = _ThemeNotifier()

    @property
    def current(self) -> AppTheme:
        return self._theme

    def set(self, theme: AppTheme) -> None:
        self._theme = theme
        if _HAS_QT and hasattr(self, "_notifier"):
            self._notifier.theme_changed.emit()

    def connect(self, callback) -> None:
        """连接配色变化回调。"""
        if _HAS_QT and hasattr(self, "_notifier"):
            self._notifier.theme_changed.connect(callback)

    def disconnect(self, callback) -> None:
        if _HAS_QT and hasattr(self, "_notifier"):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    self._notifier.theme_changed.disconnect(callback)
            except Exception:
                pass


if _HAS_QT:
    class _ThemeNotifier(QObject):
        theme_changed = Signal()


_manager = _ThemeManager()


# ━━ 公开 API ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_theme() -> AppTheme:
    """获取当前配色（控件内使用）。"""
    return _manager.current


def set_theme(theme: AppTheme) -> None:
    """切换配色方案（运行时生效）。"""
    # 开发模式下自动检查对比度（不阻塞运行）
    if __debug__:
        warnings = theme.validate_contrast()
        if warnings:
            import sys
            print("[Theme Contrast Warning]", file=sys.stderr)
            for w in warnings:
                print(f"  ⚠ {w}", file=sys.stderr)
    _manager.set(theme)


def on_theme_changed(callback) -> None:
    """注册配色变化回调。"""
    _manager.connect(callback)


def off_theme_changed(callback) -> None:
    """注销配色变化回调。"""
    _manager.disconnect(callback)


def bind_theme(owner, callback) -> None:
    """Register a theme callback and auto-disconnect it when the owner dies."""
    on_theme_changed(callback)

    if _HAS_QT and hasattr(owner, "destroyed"):
        def _cleanup(*_args) -> None:
            off_theme_changed(callback)

        owner.destroyed.connect(_cleanup)


def load_theme_from_dict(data: dict) -> AppTheme:
    """从 dict 创建配色（可来自 YAML/JSON）。"""
    return AppTheme(**{k: v for k, v in data.items() if k in _FIELD_NAMES})
