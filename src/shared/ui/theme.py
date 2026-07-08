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
    from src.qt_api import QApplication, QEvent, QObject, QTimer, Signal
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
    bg_window: str = "#F5F7FA"           # 窗口/页面背景（蓝调极浅灰，衬托白色 Card）
    bg_card: str = "#FFFFFF"             # 卡片/面板背景
    bg_input: str = "#FFFFFF"            # 输入框背景
    bg_hover: str = "#EDF0F8"            # 悬停背景
    bg_selected: str = "#E6F4FF"         # 选中背景
    bg_tooltip: str = "#1E293B"          # 提示框背景
    bg_nav_rail: str = ""                # 导航卡片区背景（空=自动 fallback 到 bg_card）

    # ━━ 文字 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    text_primary: str = "#1E293B"        # 主文字
    text_secondary: str = "#475569"      # 次要文字
    text_hint: str = "#94A3B8"           # 占位/提示文字
    text_disabled: str = "#CBD5E1"       # 禁用文字
    text_on_primary: str = "#FFFFFF"     # 品牌色上的文字
    text_on_accent: str = "#FFFFFF"      # 强调色上的文字
    text_on_tooltip: str = ""            # Tooltip text on bg_tooltip
    text_link: str = "#1677FF"           # 链接文字

    # ━━ 侧边栏 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    bg_sidebar: str = "#EBF0FA"          # 侧边栏+标题栏背景（蓝调浅灰，品牌暗示）
    bg_sidebar_active: str = "#DDE5F5"   # 侧边栏选中项背景
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
    shell_radius: int = 10               # 主窗口/弹窗/外壳统一圆角

    # ── Shared control tokens (px) ──────────────────────────────────────────
    button_radius: int = 6
    button_padding_x: int = 14
    button_padding_y: int = 4
    button_height_md: int = 32
    button_font_weight: int = 700

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
    combo_popup_offset_y: int = 4
    combo_popup_radius: int = 10
    combo_popup_border_width: int = 1
    combo_popup_shell_padding: int = 4
    combo_popup_shadow_blur: int = 12
    combo_popup_shadow_alpha: int = 14
    combo_popup_shadow_offset_y: int = 3

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

    module_summary_tile_min_height: int = 104
    module_summary_tile_padding_x: int = 18
    module_summary_tile_padding_y: int = 13
    module_summary_icon_container_size: int = 52
    module_summary_icon_size: int = 28
    module_summary_icon_bg_alpha: int = 13
    module_summary_icon_text_gap: int = 18
    module_summary_grid_gap: int = 16
    module_summary_content_spacing: int = 4
    module_summary_title_font_size: int = 14
    module_summary_title_line_height: int = 30
    module_summary_body_line_height: int = 20
    module_summary_border_alpha: int = 150
    module_summary_shadow_alpha: int = 8
    module_summary_shadow_offset_y: int = 2

    card_padding_x: int = 16
    card_padding_y: int = 16
    card_padding_top: int = 12
    card_padding_bottom: int = 14
    card_spacing: int = 8
    card_content_spacing: int = 2
    template_detail_section_gap: int = 16

    dialog_icon_container_size: int = 40
    dialog_icon_size: int = 24
    dialog_close_button_size: int = 32

    form_row_label_width: int = 120
    form_row_height: int = 30
    form_grid_column_gap: int = 40
    form_grid_compact_column_gap: int = 12

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
    font_family: str = "'Microsoft YaHei', 'Microsoft YaHei UI', 'Segoe UI Variable', 'Segoe UI', 'Inter', '-apple-system', 'BlinkMacSystemFont', sans-serif"

    font_size_xs: int = 11               # 角标、徽标
    font_size_sm: int = 12               # 辅助文字、脚注
    font_size_md: int = 13               # 正文（基准）
    font_size_lg: int = 15               # 副标题、强调
    font_size_xl: int = 16               # 卡片标题、对话框标题
    font_size_xxl: int = 20              # 页面标题

    font_weight_normal: int = 400
    font_weight_medium: int = 500
    font_weight_emphasis: int = 700
    font_weight_bold: int = 700

    # ━━ 间距 (px) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    spacing_xl: int = 24
    spacing_xxl: int = 32                # 弹窗级大留白
    master_detail_nav_width: int = 260
    master_detail_margin_x: int = 16
    master_detail_margin_top: int = 10
    master_detail_margin_bottom: int = 16
    master_detail_detail_spacing: int = 0

    # ━━ 控件高度 (px) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    control_height_sm: int = 24          # 紧凑型（表格内、工具栏）
    control_height_md: int = 30          # 默认（输入框、按钮）
    control_height_lg: int = 36          # 大号（主操作按钮）

    # ━━ 动画时长 (ms) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    anim_duration_fast: int = 100        # 微交互（hover、toggle）
    anim_duration_normal: int = 200      # 默认过渡
    anim_duration_slow: int = 400        # 面板展开/折叠

    # ── 工具方法 ──

    def __post_init__(self) -> None:
        # bg_nav_rail 智能 fallback：未显式定义时自动取 bg_card
        if not self.bg_nav_rail:
            self.bg_nav_rail = self.bg_card
        if not self.text_on_tooltip:
            try:
                self.text_on_tooltip = "#1A1A1A" if _hex_luminance(self.bg_tooltip) > 0.55 else "#FFFFFF"
            except (TypeError, ValueError, IndexError):
                self.text_on_tooltip = self.text_primary
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
            ('text_on_tooltip', 'bg_tooltip', 35, 'tooltip text vs tooltip background'),
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


def theme_rgba(color_value: str, alpha: float) -> str:
    """Return a QSS rgba() color from a theme hex token.

    ``alpha`` accepts either 0..1 floats or 0..255 integers. Non-hex values are
    returned unchanged so callers can safely pass through transparent tokens.
    """
    normalized = str(color_value or "").strip()
    if not normalized.startswith("#"):
        return normalized
    hex_value = normalized[1:]
    if len(hex_value) == 3:
        hex_value = "".join(ch * 2 for ch in hex_value)
    if len(hex_value) != 6:
        return normalized
    try:
        red = int(hex_value[0:2], 16)
        green = int(hex_value[2:4], 16)
        blue = int(hex_value[4:6], 16)
    except ValueError:
        return normalized
    alpha_value = float(alpha)
    if alpha_value > 1:
        alpha_value = alpha_value / 255.0
    alpha_value = max(0.0, min(1.0, alpha_value))
    return f"rgba({red}, {green}, {blue}, {alpha_value:.3f})"


# 字段名缓存
_FIELD_NAMES = {f.name for f in AppTheme.__dataclass_fields__.values()}


# ━━ 预设配色 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LIGHT = AppTheme()  # 默认浅色

DARK = AppTheme(
    # 深色配色——高质量暗黑模式, inspired by GitHub Dark + Linear
    # 表面层级: sidebar(L0) → window(L0) → nav_rail(L1) → card(L2)
    primary="#1677FF", primary_hover="#4096FF",
    primary_pressed="#0958D9", primary_light="#111A2C",
    accent="#E0993A",       # 柔化橙
    logo_dark="#E2E8F0", logo_light="#94A3B8",
    bg_window="#0D1117", bg_card="#161B22", bg_input="#0D1117",
    bg_hover="#1C2333", bg_selected="#1F2D40", bg_tooltip="#2D3545",
    bg_nav_rail="#161B22",            # L1 导航层
    bg_sidebar="#010409", bg_sidebar_active="#161B22",
    text_sidebar="#64748B", text_sidebar_active="#E2E8F0",
    text_primary="#E2E8F0",    # 柔化白
    text_secondary="#94A3B8",
    text_hint="#64748B", text_disabled="#475569",
    text_on_primary="#FFFFFF", text_on_accent="#FFFFFF",
    text_link="#4096FF",
    window_close_hover_bg="#E81123", window_close_hover_text="#FFFFFF",
    border="#3A4558", border_light="#303846",
    border_focus="#1677FF", border_error="#E07070",
    divider="#303846", overlay="rgba(0, 0, 0, 0.75)",
    success="#6EBC8A",        # 柔化绿
    success_bg="#14532D",
    warning="#D4A843",        # 柔化金
    warning_bg="#78350F",
    error="#E07070",          # 柔化红
    error_hover="#ECA5A5",
    error_pressed="#CC5555",
    error_bg="#7F1D1D",
    info="#6BA3D4",           # 柔化蓝
    info_bg="#0C4A6E",
    switch_on="#1677FF", switch_off="#2D3545",
    switch_thumb="#E2E8F0", switch_disabled="#1E293B",
    progress_track="#21262D", progress_fill="#1677FF",
    scrollbar_track="transparent", scrollbar_thumb="#2D3545",
    scrollbar_thumb_hover="#475569",
    tab_active_text="#4096FF", tab_active_border="#4096FF",
    tab_inactive_text="#64748B",
    icon_primary="#B0BAC9",
    icon_secondary="#64748B",
    icon_accent="#1677FF",
    shadow_color="rgba(0, 0, 0, 0.50)",
)

OCEAN = AppTheme(
    # 海蓝配色 — 全 token 补齐版
    # 表面层级: sidebar(深蓝灰) → window(浅蓝) → nav_rail/card(白)
    primary="#0EA5E9", primary_hover="#38BDF8",
    primary_pressed="#0284C7", primary_light="#E0F2FE",
    accent="#F59E0B", accent_hover="#FBBF24",
    logo_dark="#0369A1", logo_light="#38BDF8",
    bg_window="#EDF5FC", bg_card="#FFFFFF", bg_input="#FFFFFF",
    bg_hover="#E5F3FC", bg_selected="#BAE6FD", bg_tooltip="#0C4A6E",
    bg_nav_rail="#FFFFFF",
    bg_sidebar="#D0E8F7", bg_sidebar_active="#B5DDF5",
    text_sidebar="#0369A1", text_sidebar_active="#0C4A6E",
    text_primary="#0C4A6E", text_secondary="#0369A1",
    text_hint="#38BDF8", text_disabled="#7DD3FC",
    text_on_primary="#FFFFFF", text_on_accent="#FFFFFF",
    text_link="#0EA5E9",
    window_close_hover_bg="#E81123", window_close_hover_text="#FFFFFF",
    icon_primary="#0C4A6E", icon_secondary="#38BDF8",
    icon_accent="#0EA5E9",
    border="#BAE6FD", border_light="#BAE6FD", border_focus="#0EA5E9",
    border_error="#EF4444",
    divider="#BAE6FD",
    overlay="rgba(12, 74, 110, 0.40)",
    success="#22C55E", success_bg="#DCFCE7",
    warning="#F59E0B", warning_bg="#FEF3C7",
    error="#EF4444", error_hover="#F87171", error_pressed="#DC2626",
    error_bg="#FEE2E2",
    info="#0EA5E9", info_bg="#E0F2FE",
    switch_on="#0EA5E9", switch_off="#BAE6FD",
    switch_thumb="#FFFFFF", switch_disabled="#E0F2FE",
    progress_track="#BAE6FD", progress_fill="#0EA5E9",
    scrollbar_track="transparent", scrollbar_thumb="#BAE6FD",
    scrollbar_thumb_hover="#7DD3FC",
    tab_active_text="#0EA5E9", tab_active_border="#0EA5E9",
    tab_inactive_text="#38BDF8",
    shadow_color="rgba(3, 105, 161, 0.12)",
)

EYECARE = AppTheme(
    # 护眼配色 —— 暖色低蓝光暗色主题
    # 表面层级: sidebar(L0最深) → window(L0) → nav_rail(L1) → card(L2)
    primary="#D4915E",            # 暖琥珀色
    primary_hover="#E0A97A",
    primary_pressed="#B87A4A",
    primary_light="#2A2118",      # 品牌浅底（深暖色）
    accent="#C4A35A",             # 暖金色
    accent_hover="#D4B76A",

    logo_dark="#E8DDD0",          # Logo 深色部分
    logo_light="#8B7355",         # Logo 浅色部分

    bg_window="#1A1512",          # 窗口背景：最深棕底色
    bg_card="#2A2320",            # 卡片背景：L2 抬升层，ΔL=6%
    bg_input="#1A1512",           # 输入框底色=window，靠 border 区分
    bg_hover="#342C27",           # 悬停背景
    bg_selected="#3D332E",        # 选中背景
    bg_tooltip="#453B35",         # 提示框背景
    bg_nav_rail="#231E1A",        # L1 导航层，ΔL=4% vs sidebar

    bg_sidebar="#140F0C",         # 侧边栏：最深锚点
    bg_sidebar_active="#2A2320",
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

    border="#4A3E35",             # 默认边框 ΔL≥12% vs bg_card
    border_light="#3D332E",       # 浅边框
    border_focus="#D4915E",       # 聚焦边框
    border_error="#C0392B",       # 错误边框

    divider="#342C27",
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
    switch_off="#3D332E",
    switch_thumb="#E8DDD0",
    switch_disabled="#2A2520",

    progress_track="#342C27",
    progress_fill="#D4915E",

    scrollbar_track="transparent",
    scrollbar_thumb="#453B35",
    scrollbar_thumb_hover="#5C4F45",

    tab_active_text="#D4915E",
    tab_active_border="#D4915E",
    tab_inactive_text="#7A6B55",

    shadow_color="rgba(0, 0, 0, 0.40)",
)


WARM_LIGHT = AppTheme(
    # 护眼暖光 — 暖黄色系浅色主题
    # 表面层级: sidebar(最深暖灰) → window(暖灰) → nav_rail/card(暖白)
    primary="#697A98",            # 蓝灰
    primary_hover="#7D8FAB",
    primary_pressed="#566883",
    primary_light="#E8E5D0",      # 品牌浅底
    accent="#B8860B",             # 暗金色
    accent_hover="#CC9B20",

    logo_dark="#4A3F33",          # Logo 深色部分
    logo_light="#697A98",         # Logo 浅色部分

    bg_window="#E6E2CC",          # 窗口背景：暖灰，ΔL=5% vs card
    bg_card="#F5F0DA",            # 卡片背景：暖白
    bg_input="#EFE9D2",           # 输入框背景：微暗于 Card
    bg_hover="#E3DECC",           # 悬停背景
    bg_selected="#D8D3BD",        # 选中背景
    bg_tooltip="#4A3F33",         # 提示框背景（深色）
    bg_nav_rail="#F5F0DA",        # 导航区：暖白，同 Card

    bg_sidebar="#D9D4BE",         # 侧边栏：最深锚点，ΔL=5% vs window
    bg_sidebar_active="#CEC8B0",
    text_sidebar="#8C7D6C",
    text_sidebar_active="#4A3F33",

    text_primary="#4A3F33",       # 主文字：深棕
    text_secondary="#6B5D4E",     # 次要文字
    text_hint="#9E8E7A",          # 提示文字
    text_disabled="#BFB39E",      # 禁用文字
    text_on_primary="#FFFFFF",
    text_on_accent="#FFFFFF",
    text_link="#697A98",

    window_close_hover_bg="#E81123",
    window_close_hover_text="#FFFFFF",

    icon_primary="#6B5D4E",       # 主图标色
    icon_secondary="#9E8E7A",     # 次要图标色
    icon_accent="#697A98",        # 强调图标色

    border="#C8C2AB",             # 默认边框（加深确保 Card 上可见）
    border_light="#D1CDB8",       # 浅边框
    border_focus="#697A98",       # 聚焦边框
    border_error="#C0392B",       # 错误边框

    divider="#CCC6AF",
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
    switch_thumb="#F5F0DA",
    switch_disabled="#DDD9C5",

    progress_track="#D8D3BD",
    progress_fill="#697A98",

    scrollbar_track="transparent",
    scrollbar_thumb="#CCC6AF",
    scrollbar_thumb_hover="#B8B39E",

    tab_active_text="#697A98",
    tab_active_border="#697A98",
    tab_inactive_text="#8C7D6C",

    shadow_color="rgba(74, 63, 51, 0.20)",
)


GREEN_LIGHT = AppTheme(
    # 浅绿护眼 — 深翠绿浅色主题，参考 WPS 护眼绿
    # primary 用深翠绿 #3D7A56 而非鼠尾草，更沉稳有力
    primary="#3D7A56",            # 深翠绿（参考 WPS）
    primary_hover="#4A8A65",
    primary_pressed="#306A48",
    primary_light="#E0EBE4",      # 极浅灰绿
    accent="#8B6914",             # 暗金强调
    accent_hover="#A07A20",

    logo_dark="#1E3A28",
    logo_light="#3D7A56",

    bg_window="#ECF0ED",          # 灰绿底色（低饱和）
    bg_card="#F5F7F5",            # 近白灰绿
    bg_input="#F5F7F5",
    bg_hover="#DDE4DE",
    bg_selected="#CED8D0",
    bg_tooltip="#1E3A28",
    bg_nav_rail="#F5F7F5",

    bg_sidebar="#D0DCD4",         # 灰绿锚点（更沉）
    bg_sidebar_active="#BED0C4",
    text_sidebar="#2D5040",
    text_sidebar_active="#1A3028",

    text_primary="#1A3028",       # 深绿黑
    text_secondary="#2D5040",
    text_hint="#6E8A78",
    text_disabled="#A0B0A5",
    text_on_primary="#FFFFFF",
    text_on_accent="#FFFFFF",
    text_link="#306A48",

    window_close_hover_bg="#E81123",
    window_close_hover_text="#FFFFFF",

    icon_primary="#2D5040",
    icon_secondary="#6E8A78",
    icon_accent="#3D7A56",

    border="#B0C4B5", border_light="#C5D5CA",
    border_focus="#3D7A56", border_error="#C0392B",
    divider="#BCC8BE",
    overlay="rgba(30, 58, 40, 0.35)",

    success="#306A48", success_bg="#E0EBE4",
    warning="#8B6914", warning_bg="#F0E8D0",
    error="#B33A3A", error_hover="#CC4E4E", error_pressed="#993030",
    error_bg="#F5E0D8",
    info="#4A6A88", info_bg="#DDE5EE",

    switch_on="#3D7A56", switch_off="#B0C4B5",
    switch_thumb="#F5F7F5", switch_disabled="#D0DCD4",
    progress_track="#B0C4B5", progress_fill="#3D7A56",
    scrollbar_track="transparent",
    scrollbar_thumb="#B0C4B5", scrollbar_thumb_hover="#8AA090",
    tab_active_text="#3D7A56", tab_active_border="#3D7A56",
    tab_inactive_text="#6E8A78",
    shadow_color="rgba(30, 58, 40, 0.10)",
)

GREEN_DARK = AppTheme(
    # 深绿暗色护眼 — 深翠绿暗色，低蓝光
    # 绿色用 #5A9E72（比浅色版稍亮确保暗底可读）
    primary="#5A9E72",            # 暗色中的翠绿（稍亮确保可读）
    primary_hover="#6AB882",
    primary_pressed="#4A8A62",
    primary_light="#152218",
    accent="#C4982E",             # 暖金
    accent_hover="#D4AA40",

    logo_dark="#B0C4B5",
    logo_light="#6AB882",

    bg_window="#101A13",          # 深森林底色
    bg_card="#182420",            # L2 卡片层
    bg_input="#101A13",
    bg_hover="#223028",
    bg_selected="#2C3E32",
    bg_tooltip="#3A5040",
    bg_nav_rail="#142018",        # L1 导航层

    bg_sidebar="#0A120C",         # 最深锚点
    bg_sidebar_active="#182420",
    text_sidebar="#5A9E72",
    text_sidebar_active="#B0C4B5",

    text_primary="#B0C4B5",       # 柔白灰绿
    text_secondary="#80A090",
    text_hint="#5A9E72",
    text_disabled="#3A5040",
    text_on_primary="#101A13",
    text_on_accent="#141408",
    text_link="#5A9E72",

    window_close_hover_bg="#E81123",
    window_close_hover_text="#FFFFFF",

    icon_primary="#80A090",
    icon_secondary="#5A9E72",
    icon_accent="#5A9E72",

    border="#304838", border_light="#223028",
    border_focus="#5A9E72", border_error="#D9534F",
    divider="#223028",
    overlay="rgba(0, 0, 0, 0.65)",

    success="#5A9E72", success_bg="#152218",
    warning="#C4982E", warning_bg="#252015",
    error="#D9534F", error_hover="#E8706C", error_pressed="#C0392B",
    error_bg="#3A1A1A",
    info="#5A88B8", info_bg="#152230",

    switch_on="#5A9E72", switch_off="#304838",
    switch_thumb="#B0C4B5", switch_disabled="#223028",
    progress_track="#223028", progress_fill="#5A9E72",
    scrollbar_track="transparent",
    scrollbar_thumb="#304838", scrollbar_thumb_hover="#4A6858",
    tab_active_text="#5A9E72", tab_active_border="#5A9E72",
    tab_inactive_text="#4A6858",
    shadow_color="rgba(0, 0, 0, 0.45)",
)

ROSE = AppTheme(
    # 玫瑰粉 — 降饱和脏粉/灰粉，优雅不刺眼
    # 表面用"Dusty Rose"灰粉调，参考高端设计系统
    primary="#B5708A",            # 降饱和玫粉（Dusty Rose）
    primary_hover="#C4849E",
    primary_pressed="#A05C76",
    primary_light="#F0E6EB",      # 极浅灰粉
    accent="#8B7DA8",             # 灰紫强调
    accent_hover="#9D90BA",

    logo_dark="#6E4A5C",
    logo_light="#B5708A",

    bg_window="#F4F0F2",          # 灰粉底色（S=5%, L=95%）
    bg_card="#FAF8F9",            # 近白灰粉
    bg_input="#FAF8F9",
    bg_hover="#EDE6E9",
    bg_selected="#E3DAE0",
    bg_tooltip="#4A3040",
    bg_nav_rail="#FAF8F9",

    bg_sidebar="#E6DDE2",         # 灰粉锚点
    bg_sidebar_active="#D9CED5",
    text_sidebar="#7A5A6A",
    text_sidebar_active="#4A3040",

    text_primary="#3A2030",       # 深玫瑰棕
    text_secondary="#6E4A5C",
    text_hint="#A08A95",
    text_disabled="#C4B5BD",
    text_on_primary="#FFFFFF",
    text_on_accent="#FFFFFF",
    text_link="#A05C76",

    window_close_hover_bg="#E81123",
    window_close_hover_text="#FFFFFF",

    icon_primary="#6E4A5C",
    icon_secondary="#A08A95",
    icon_accent="#B5708A",

    border="#D0C4CA", border_light="#DDD5D9",
    border_focus="#B5708A", border_error="#C0392B",
    divider="#D9D0D5",
    overlay="rgba(74, 48, 64, 0.35)",

    success="#6B8E4E", success_bg="#E8EFD8",
    warning="#B8860B", warning_bg="#F5ECD0",
    error="#B33A3A", error_hover="#CC4E4E", error_pressed="#993030",
    error_bg="#F5E0D8",
    info="#5A7A98", info_bg="#E0E8F0",

    switch_on="#B5708A", switch_off="#D0C4CA",
    switch_thumb="#FAF8F9", switch_disabled="#E6DDE2",
    progress_track="#D0C4CA", progress_fill="#B5708A",
    scrollbar_track="transparent",
    scrollbar_thumb="#D0C4CA", scrollbar_thumb_hover="#B0A0A8",
    tab_active_text="#B5708A", tab_active_border="#B5708A",
    tab_inactive_text="#A08A95",
    shadow_color="rgba(74, 48, 64, 0.10)",
)


BLUE_GREEN = AppTheme(
    # 蓝绿 — 蓝色 + 绿色双色调
    # 蓝色 → primary（按钮、链接）
    # 绿色 → sidebar + 开关 + 标签（深翠绿 #2D7050）
    primary="#3B6FC2",            # 柔蓝 — 按钮/链接
    primary_hover="#4D82D4",
    primary_pressed="#2F5CA6",
    primary_light="#E4EBF5",
    accent="#2D7050",             # 深翠绿
    accent_hover="#3A8060",

    logo_dark="#2A4A78",          # 蓝色 Logo
    logo_light="#2D7050",         # 绿色 Logo 辅色

    bg_window="#ECF0ED",          # 微绿灰底色
    bg_card="#F5F7F5",
    bg_input="#F5F7F5",
    bg_hover="#DDE4DE",
    bg_selected="#CED8D0",
    bg_tooltip="#1A3028",
    bg_nav_rail="#F5F7F5",

    bg_sidebar="#C8D8CC",         # ★ 深绿调灰 sidebar
    bg_sidebar_active="#B8CABD",
    text_sidebar="#2D5040",       # 深绿文字
    text_sidebar_active="#1A3028",

    text_primary="#1A2828",       # 深蓝绿
    text_secondary="#2D4A48",
    text_hint="#6E8878",
    text_disabled="#A0B0A5",
    text_on_primary="#FFFFFF",
    text_on_accent="#FFFFFF",
    text_link="#2F5CA6",          # 蓝色链接

    window_close_hover_bg="#E81123",
    window_close_hover_text="#FFFFFF",

    icon_primary="#2D5040",       # 深绿图标
    icon_secondary="#6E8878",
    icon_accent="#2D7050",        # ★ 深绿图标强调

    border="#B0C0B5", border_light="#C5D0C8",
    border_focus="#3B6FC2",       # 蓝色聚焦
    border_error="#C0392B",
    divider="#BCC8BE",
    overlay="rgba(26, 48, 40, 0.35)",

    success="#2D7050", success_bg="#E0EBE4",
    warning="#8B6914", warning_bg="#F0E8D0",
    error="#B33A3A", error_hover="#CC4E4E", error_pressed="#993030",
    error_bg="#F5E0D8",
    info="#3B6FC2", info_bg="#E4EBF5",

    switch_on="#2D7050",          # ★ 深绿开关
    switch_off="#B0C0B5",
    switch_thumb="#F5F7F5", switch_disabled="#C8D8CC",
    progress_track="#B0C0B5",
    progress_fill="#3B6FC2",      # 蓝色进度条
    scrollbar_track="transparent",
    scrollbar_thumb="#B0C0B5", scrollbar_thumb_hover="#8A9A90",
    tab_active_text="#2D7050",    # ★ 深绿标签
    tab_active_border="#2D7050",
    tab_inactive_text="#6E8878",
    shadow_color="rgba(26, 48, 40, 0.10)",
)

RED_BLUE = AppTheme(
    # 红蓝 — 蓝色 + 红色双色调
    # 分配策略：
    #   蓝色 → primary（按钮、链接、border_focus、进度条）
    #   红色 → sidebar 色调 + 开关 + 标签高亮 + 图标强调
    # 两色各有"领地"，红色不仅是警示色更是设计元素
    primary="#4A6FA5",            # 柔蓝 — 按钮/链接
    primary_hover="#5C82B8",
    primary_pressed="#3D5E90",
    primary_light="#E4EAF2",
    accent="#B85450",             # 柔砖红
    accent_hover="#CC6A66",

    logo_dark="#2E4468",          # 蓝色 Logo
    logo_light="#B85450",         # 红色 Logo 辅色

    bg_window="#F4F0F0",          # 微暖灰底色（偏红调）
    bg_card="#FAF8F8",            # 微暖白
    bg_input="#FAF8F8",
    bg_hover="#ECE4E4",
    bg_selected="#E2D8D8",
    bg_tooltip="#3A2828",
    bg_nav_rail="#FAF8F8",

    bg_sidebar="#E4D8DA",         # ★ 暖粉灰 — 让红色在 sidebar 可见
    bg_sidebar_active="#D8CACF",
    text_sidebar="#6E4850",       # 红调文字
    text_sidebar_active="#3A2028",

    text_primary="#2E2028",       # 深暖灰
    text_secondary="#584048",
    text_hint="#A08890",
    text_disabled="#C0B0B5",
    text_on_primary="#FFFFFF",
    text_on_accent="#FFFFFF",
    text_link="#3D5E90",          # 蓝色链接

    window_close_hover_bg="#B85450",   # 呼应红色
    window_close_hover_text="#FFFFFF",

    icon_primary="#6E4850",       # 红调图标
    icon_secondary="#A08890",
    icon_accent="#B85450",        # ★ 红色图标强调

    border="#D0C0C4", border_light="#DDD2D5",
    border_focus="#4A6FA5",       # 蓝色聚焦
    border_error="#B85450",
    divider="#D5C8CC",
    overlay="rgba(58, 32, 40, 0.35)",

    success="#5A8A4E", success_bg="#E8EFE2",
    warning="#B8860B", warning_bg="#F5ECD0",
    error="#B85450", error_hover="#CC6A66", error_pressed="#A04540",
    error_bg="#F5E2E0",
    info="#4A6FA5", info_bg="#E4EAF2",

    switch_on="#B85450",          # ★ 红色开关
    switch_off="#D0C0C4",
    switch_thumb="#FAF8F8", switch_disabled="#E4D8DA",
    progress_track="#D0C0C4",
    progress_fill="#4A6FA5",      # 蓝色进度条
    scrollbar_track="transparent",
    scrollbar_thumb="#D0C0C4", scrollbar_thumb_hover="#B0A0A5",
    tab_active_text="#B85450",    # ★ 红色标签高亮
    tab_active_border="#B85450",
    tab_inactive_text="#A08890",
    shadow_color="rgba(58, 32, 40, 0.10)",
)


# ━━ 全局单例 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _ThemeManager:
    """配色管理器（单例）。

    控件不持有颜色常量，而是每次绘制时调 get_theme() 获取当前值。
    切换时通过 Qt 信号通知所有已连接的控件刷新。
    """

    def __init__(self):
        self._theme: AppTheme = LIGHT
        self._notified_theme: AppTheme = LIGHT
        self._pending_notification = False
        self._version: int = 1
        if _HAS_QT:
            self._notifier = _ThemeNotifier()

    @property
    def current(self) -> AppTheme:
        return self._theme

    def set(self, theme: AppTheme) -> None:
        if theme == self._theme:
            return
        self._theme = theme
        self._version += 1
        self._queue_notification()

    def _queue_notification(self) -> None:
        if not (_HAS_QT and hasattr(self, "_notifier")):
            return

        if self._pending_notification:
            return

        if QApplication.instance() is None:
            self.flush()
            return

        self._pending_notification = True
        QTimer.singleShot(0, self.flush)

    def flush(self) -> None:
        self._pending_notification = False
        if self._theme == self._notified_theme:
            return

        if __debug__:
            contrast_warnings = self._theme.validate_contrast()
            if contrast_warnings:
                import sys
                print("[Theme Contrast Warning]", file=sys.stderr)
                for warning in contrast_warnings:
                    print(f"  ! {warning}", file=sys.stderr)

        self._notified_theme = self._theme
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


if _HAS_QT:
    class _ThemeBinding(QObject):
        """Theme subscription that defers hidden widget refresh work."""

        def __init__(self, owner, callback) -> None:
            self._owner = owner
            self._callback = callback
            self._dirty = False
            self._applied_version: int = _manager._version
            super().__init__(owner)
            on_theme_changed(self._on_theme_changed)
            owner.installEventFilter(self)
            self._cleanup_callback = lambda *_args: self._cleanup()
            owner.destroyed.connect(self._cleanup_callback)

        def eventFilter(self, watched, event) -> bool:
            owner = getattr(self, "_owner", None)
            if owner is not None and watched is owner and event.type() in (QEvent.Show, QEvent.ShowToParent):
                self.apply_if_dirty()
            return False

        def _on_theme_changed(self) -> None:
            if getattr(self, "_owner", None) is None:
                self._cleanup()
                return
            if self._is_visible():
                self._dirty = False
                self._do_apply()
                return
            self._dirty = True

        def apply_if_dirty(self) -> None:
            if self._dirty and self._is_visible():
                self._dirty = False
                self._do_apply()

        def _do_apply(self) -> None:
            if self._applied_version == _manager._version:
                return
            self._applied_version = _manager._version
            self._callback()

        def _is_visible(self) -> bool:
            return bool(getattr(self._owner, "isVisible", lambda: True)())

        def _cleanup(self, *_args) -> None:
            off_theme_changed(self._on_theme_changed)
            self._owner = None


_manager = _ThemeManager()


# ━━ 公开 API ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_theme() -> AppTheme:
    """获取当前配色（控件内使用）。"""
    return _manager.current


def on_theme_changed(callback) -> None:
    """注册配色变化回调。"""
    _manager.connect(callback)


def off_theme_changed(callback) -> None:
    """注销配色变化回调。"""
    _manager.disconnect(callback)


def set_theme(theme: AppTheme) -> None:
    """Switch the active theme and coalesce repaint notifications."""
    _manager.set(theme)


def flush_theme_changes() -> None:
    """Apply any coalesced theme notification immediately."""
    _manager.flush()


def bind_theme(owner, callback) -> None:
    """Register a theme callback and auto-disconnect it when the owner dies."""
    if _HAS_QT and hasattr(owner, "installEventFilter") and hasattr(owner, "destroyed"):
        binding = _ThemeBinding(owner, callback)
        bindings = getattr(owner, "_theme_bindings", None)
        if bindings is None:
            bindings = []
            setattr(owner, "_theme_bindings", bindings)
        bindings.append(binding)
        return

    if _HAS_QT and hasattr(owner, "destroyed"):
        on_theme_changed(callback)

        def _cleanup(*_args) -> None:
            off_theme_changed(callback)

        owner.destroyed.connect(_cleanup)
    else:
        on_theme_changed(callback)


def load_theme_from_dict(data: dict) -> AppTheme:
    """从 dict 创建配色（可来自 YAML/JSON）。"""
    return AppTheme(**{k: v for k, v in data.items() if k in _FIELD_NAMES})


def derive_theme_from_core(
    primary: str,
    accent: str,
    bg_window: str,
    bg_card: str,
    bg_sidebar: str,
    text_primary: str,
) -> AppTheme:
    """从 6 个核心色自动推算完整 AppTheme。

    推算策略:
      hover  = 亮度 +12%
      pressed = 亮度 -8%
      secondary = 不透明度 70%（混合 bg_window）
      hint = 不透明度 45%
      disabled = 不透明度 30%
      border = bg 与 text 之间 20% 混合
    """
    from colorsys import rgb_to_hls, hls_to_rgb

    def _hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        return f"#{max(0,min(255,r)):02X}{max(0,min(255,g)):02X}{max(0,min(255,b)):02X}"

    def _mix(c1: str, c2: str, ratio: float) -> str:
        """ratio=0 → c1, ratio=1 → c2"""
        r1, g1, b1 = _hex_to_rgb(c1)
        r2, g2, b2 = _hex_to_rgb(c2)
        return _rgb_to_hex(
            int(r1 + (r2 - r1) * ratio),
            int(g1 + (g2 - g1) * ratio),
            int(b1 + (b2 - b1) * ratio),
        )

    def _shift_lightness(color: str, delta: float) -> str:
        r, g, b = _hex_to_rgb(color)
        h, l, s = rgb_to_hls(r / 255, g / 255, b / 255)
        l = max(0, min(1, l + delta))
        r2, g2, b2 = hls_to_rgb(h, l, s)
        return _rgb_to_hex(int(r2 * 255), int(g2 * 255), int(b2 * 255))

    def _luminance(color: str) -> float:
        r, g, b = _hex_to_rgb(color)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255

    is_dark = _luminance(bg_window) < 0.4

    # 推算所有 token
    primary_hover = _shift_lightness(primary, 0.12 if is_dark else 0.08)
    primary_pressed = _shift_lightness(primary, -0.08 if is_dark else -0.06)
    primary_light = _mix(bg_window, primary, 0.08) if not is_dark else _shift_lightness(bg_window, -0.05)
    accent_hover = _shift_lightness(accent, 0.12 if is_dark else 0.08)

    text_secondary = _mix(text_primary, bg_window, 0.35)
    text_hint = _mix(text_primary, bg_window, 0.55)
    text_disabled = _mix(text_primary, bg_window, 0.72)
    text_on_primary = "#FFFFFF" if _luminance(primary) < 0.5 else "#1A1A1A"
    text_on_accent = "#FFFFFF" if _luminance(accent) < 0.5 else "#1A1A1A"
    text_link = primary_pressed if not is_dark else primary_hover

    bg_input = bg_card
    bg_hover = _mix(bg_window, text_primary, 0.06)
    bg_selected = _mix(bg_window, primary, 0.12)
    bg_tooltip = text_primary if not is_dark else _shift_lightness(bg_window, 0.15)
    bg_nav_rail = bg_card
    bg_sidebar_active = _mix(bg_sidebar, text_primary, 0.08)
    text_sidebar = _mix(text_primary, bg_sidebar, 0.30)
    text_sidebar_active = text_primary

    border = _mix(bg_card, text_primary, 0.18)
    border_light = _mix(bg_card, text_primary, 0.10)

    icon_primary = text_secondary
    icon_secondary = text_hint
    icon_accent = primary

    return AppTheme(
        primary=primary, primary_hover=primary_hover,
        primary_pressed=primary_pressed, primary_light=primary_light,
        accent=accent, accent_hover=accent_hover,

        logo_dark=primary_pressed if not is_dark else _shift_lightness(primary, 0.25),
        logo_light=primary,

        bg_window=bg_window, bg_card=bg_card, bg_input=bg_input,
        bg_hover=bg_hover, bg_selected=bg_selected,
        bg_tooltip=bg_tooltip, bg_nav_rail=bg_nav_rail,

        bg_sidebar=bg_sidebar, bg_sidebar_active=bg_sidebar_active,
        text_sidebar=text_sidebar, text_sidebar_active=text_sidebar_active,

        text_primary=text_primary, text_secondary=text_secondary,
        text_hint=text_hint, text_disabled=text_disabled,
        text_on_primary=text_on_primary, text_on_accent=text_on_accent,
        text_link=text_link,

        window_close_hover_bg="#E81123",
        window_close_hover_text="#FFFFFF",

        icon_primary=icon_primary, icon_secondary=icon_secondary,
        icon_accent=icon_accent,

        border=border, border_light=border_light,
        border_focus=primary, border_error="#C0392B" if not is_dark else "#E8706C",
        divider=border_light,
        overlay=f"rgba({', '.join(str(c) for c in _hex_to_rgb(text_primary))}, {'0.35' if not is_dark else '0.60'})",

        success=_mix("#22C55E", bg_window, 0.15),
        success_bg=_mix(bg_window, "#22C55E", 0.08),
        warning=_mix("#D97706", bg_window, 0.10),
        warning_bg=_mix(bg_window, "#D97706", 0.08),
        error="#C0392B" if not is_dark else "#E8706C",
        error_hover="#E04040" if not is_dark else "#F0908C",
        error_pressed="#993030" if not is_dark else "#C0392B",
        error_bg=_mix(bg_window, "#EF4444", 0.08),
        info=primary, info_bg=primary_light,

        switch_on=primary, switch_off=border,
        switch_thumb=bg_card, switch_disabled=border_light,
        progress_track=border, progress_fill=primary,
        scrollbar_track="transparent",
        scrollbar_thumb=border, scrollbar_thumb_hover=_mix(border, text_primary, 0.20),
        tab_active_text=primary, tab_active_border=primary,
        tab_inactive_text=text_hint,
        shadow_color=f"rgba({', '.join(str(c) for c in _hex_to_rgb(text_primary))}, 0.10)",
    )
