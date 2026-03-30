"""
UI 控件样式全览 (Style Gallery)

独立运行脚本 — 展示项目全部自定义控件 + 原生控件在五套主题下的实际效果。
用于设计审阅和样式迭代。

用法::

    python demo_style_gallery.py
"""
import sys
from pathlib import Path
import faulthandler
faulthandler.enable()

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.qt_api import (
    QApplication, QAbstractSpinBox, QBrush, QButtonGroup, QCheckBox, QDoubleSpinBox,
    QEvent, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QObject, QPoint,
    QProgressBar, QPropertyAnimation, QPushButton, QScrollArea,
    QSize, QSizePolicy, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout,
    QWidget, Qt, QFont,
)

# ── Hi-DPI ──
try:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
except AttributeError:
    pass

# ── 导入项目模块 ──
from src.shared.ui.theme import (
    get_theme, set_theme, on_theme_changed,
    LIGHT, DARK, OCEAN, EYECARE, WARM_LIGHT, AppTheme,
)
from src.shared.ui.card import Card
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.collapsible_section import CollapsibleSection
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui import ThemedRadioButton, ThemedSlider
from src.shared.ui.form_row import FormRow
from src.shared.ui.search_input import SearchInput
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.icon_button import IconButton
from src.shared.ui.progress_indicator import ProgressIndicator
from src.shared.ui.status_indicator import StatusIndicator
from src.shared.ui.color_picker import ColorPicker
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.size_combo import SizeCombo
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.style_preview import StylePreview
from src.shared.ui.override_badge import OverrideBadge
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.module_step_list import ModuleStepList
from src.shared.ui.placeholder_edit import PlaceholderEdit
from src.shared.ui.numbering_preset import NumberingPreset
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.dialogs import info, success, warning, error, confirm, input_text
from src.ui.icons.catalog import get_icon, get_icon_names, invalidate_icon_cache


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  工具函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _section_title(text: str) -> QLabel:
    """区段大标题。"""
    lbl = QLabel(text)
    lbl.setObjectName("section_title")
    return lbl

def _subsection_title(text: str) -> QLabel:
    """区段子标题。"""
    lbl = QLabel(text)
    lbl.setObjectName("subsection_title")
    return lbl

def _desc(text: str) -> QLabel:
    """控件描述标签。"""
    lbl = QLabel(text)
    lbl.setObjectName("desc_label")
    lbl.setWordWrap(True)
    return lbl

def _hline() -> QFrame:
    """水平分割线。"""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setObjectName("gallery_hline")
    return line

def _hbox(*widgets, spacing=8) -> QWidget:
    """将多个控件水平排列（垂直居中对齐）。"""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(spacing)
    for wg in widgets:
        if isinstance(wg, str) and wg == "stretch":
            h.addStretch()
        elif isinstance(wg, str):
            lbl = QLabel(wg)
            h.addWidget(lbl, 0, Qt.AlignVCenter)
        else:
            h.addWidget(wg, 0, Qt.AlignVCenter)
    return w

def _vbox(*widgets, spacing=6) -> QWidget:
    """将多个控件垂直排列。"""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(spacing)
    for wg in widgets:
        if isinstance(wg, str) and wg == "stretch":
            v.addStretch()
        elif isinstance(wg, str):
            v.addWidget(QLabel(wg))
        else:
            v.addWidget(wg)
    return w


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  色块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━



_BUTTON_SHOWCASE_SPECS = (
    ("Primary 主按钮", "primary", True),
    ("Secondary 次按钮", "secondary", True),
    ("Danger 危险", "danger", True),
    ("Disabled 禁用", "secondary", False),
)


def _make_variant_button(text: str, variant: str, *, enabled: bool = True) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(get_theme().button_height_md)
    apply_button_variant(btn, variant)
    btn.setEnabled(enabled)
    return btn


def _make_showcase_search_input(placeholder: str, *, height: int | None = None) -> SearchInput:
    search = SearchInput(placeholder=placeholder)
    if height is not None:
        search.setFixedHeight(height)
    return search


def _make_showcase_combo(items: list[str], *, height: int | None = None) -> StyledComboBox:
    combo = StyledComboBox()
    combo.addItems(items)
    if height is not None:
        combo.setFixedHeight(height)
    return combo


def _build_selection_showcase_row() -> QWidget:
    cb1 = QCheckBox("默认未选")
    cb2 = QCheckBox("已选中")
    cb2.setChecked(True)
    cb3 = QCheckBox("禁用")
    cb3.setEnabled(False)
    cb4 = QCheckBox("禁用且已选")
    cb4.setChecked(True)
    cb4.setEnabled(False)

    rb1 = ThemedRadioButton("选项 A")
    rb2 = ThemedRadioButton("选项 B")
    rb2.setChecked(True)
    rb3 = ThemedRadioButton("禁用")
    rb3.setEnabled(False)
    rb4 = ThemedRadioButton("禁用且已选")
    rb4.setChecked(True)
    rb4.setEnabled(False)

    return _hbox(cb1, cb2, cb3, cb4, "stretch", rb1, rb2, rb3, rb4)


def _build_slider_showcase_row() -> QWidget:
    slider = ThemedSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(60)
    slider.setFixedHeight(get_theme().control_height_md)

    pb = QProgressBar()
    pb.setRange(0, 100)
    pb.setValue(75)
    pb.setFixedHeight(16)
    return _hbox(slider, pb)

class ColorSwatch(QWidget):
    """单个色块 + 标签。"""
    def __init__(self, token_name: str, parent=None):
        super().__init__(parent)
        self._token = token_name
        self.setFixedSize(72, 60)
        self._swatch = QLabel()
        self._swatch.setFixedSize(48, 28)
        self._label = QLabel(token_name)
        self._label.setObjectName("swatch_label")
        self._label.setAlignment(Qt.AlignCenter)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.addWidget(self._swatch, 0, Qt.AlignCenter)
        v.addWidget(self._label)
        self._apply()
        on_theme_changed(self._apply)

    def _apply(self):
        t = get_theme()
        color = getattr(t, self._token, "#CCC")
        if isinstance(color, str) and color.startswith("#"):
            self._swatch.setStyleSheet(
                f"background:{color}; border:1px solid {t.border}; "
                f"border-radius:{t.radius_sm}px;")
        else:
            self._swatch.setStyleSheet(
                f"background:{color}; border:1px solid {t.border}; "
                f"border-radius:{t.radius_sm}px;")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  带搜索图标的输入框 (demo 专用增强控件)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StyleGallery(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lark Formatter — UI 控件样式全览")
        self.resize(1080, 740)
        self.setMinimumSize(800, 500)
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 顶部工具栏 ──
        toolbar = QWidget()
        toolbar.setObjectName("gallery_toolbar")
        toolbar.setFixedHeight(48)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(12)

        logo = QLabel("🎨")
        logo.setStyleSheet("font-size: 20px;")
        tb_layout.addWidget(logo)

        title = QLabel("UI 控件样式全览")
        title.setObjectName("gallery_title")
        tb_layout.addWidget(title)
        tb_layout.addStretch()

        # 主题切换按钮组
        self._theme_btns = {}
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        for i, (name, label, theme) in enumerate([
            ("light",   "☀ Light",  LIGHT),
            ("dark",    "🌙 Dark",   DARK),
            ("ocean",   "🌊 Ocean",  OCEAN),
            ("eyecare",    "🍵 咖啡",     EYECARE),
            ("warm_light", "☕ 暖光",     WARM_LIGHT),
        ]):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(90)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName(f"theme_btn_{name}")
            self._theme_group.addButton(btn, i)
            self._theme_btns[name] = (btn, theme)
            tb_layout.addWidget(btn)
            btn.clicked.connect(lambda checked, t=theme: self._switch_theme(t))

        self._theme_btns["light"][0].setChecked(True)
        outer.addWidget(toolbar)

        # ── 滚动区域 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("gallery_scroll")

        container = QWidget()
        container.setObjectName("gallery_container")
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(24, 20, 24, 24)
        self._main_layout.setSpacing(20)

        # ── 当前重构焦点预览区 ──
        self._build_focus_preview()
        self._main_layout.addWidget(_hline())

        # 构建各区段
        self._build_section_tokens()
        self._build_section_native()
        self._build_section_inputs()
        self._build_section_selectors()
        self._build_section_containers()
        self._build_section_feedback()
        self._build_section_display()
        self._build_section_dialogs()

        self._main_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        self._apply_theme()
        on_theme_changed(self._apply_theme)

    # ── 主题切换 ──
    def _switch_theme(self, theme: AppTheme):
        invalidate_icon_cache()
        set_theme(theme)

    # ── 焦点预览区 ──
    def _build_focus_preview(self):
        t = get_theme()
        lbl = _section_title("🔍 Phase 2 · 原生控件主题化 (Focus Preview)")
        lbl.setStyleSheet("color: #E26A2C; font-size: 18px; font-weight: bold;")
        self._main_layout.addWidget(lbl)

        self._main_layout.addWidget(_subsection_title("✅ QPushButton（共享 variant）"))
        focus_buttons = [
            _make_variant_button(text, variant, enabled=enabled)
            for text, variant, enabled in _BUTTON_SHOWCASE_SPECS
        ]
        self._main_layout.addWidget(_hbox(*focus_buttons, "stretch"))

        self._main_layout.addWidget(_subsection_title("✅ SearchInput（shared/ui 正式实现）"))
        search = _make_showcase_search_input("请输入关键词...", height=t.control_height_md)
        self._main_layout.addWidget(_hbox(search, "stretch"))

        self._main_layout.addWidget(_subsection_title("✅ StyledComboBox / QSpinBox"))
        combo = _make_showcase_combo(["默认选项", "选项 A", "选项 B"], height=t.control_height_md)
        spin = QSpinBox()
        spin.setRange(1, 100)
        spin.setValue(53)
        spin.setFixedHeight(t.control_height_md)
        dspin = QDoubleSpinBox()
        dspin.setRange(0, 100)
        dspin.setValue(3.14)
        dspin.setFixedHeight(t.control_height_md)
        self._main_layout.addWidget(_hbox(combo, spin, dspin, "stretch"))

        self._main_layout.addWidget(_subsection_title("✅ QCheckBox / QRadioButton（共享 selection theme）"))
        self._main_layout.addWidget(_build_selection_showcase_row())

        self._main_layout.addWidget(_subsection_title("🔧 QSlider / QProgressBar (待主题化)"))
        self._main_layout.addWidget(_build_slider_showcase_row())

        self._main_layout.addWidget(_subsection_title("🔧 QTabWidget (待主题化)"))
        tab = QTabWidget()
        t1_w = QLabel("标签页 1 内容")
        t1_w.setAlignment(Qt.AlignCenter)
        t2_w = QLabel("标签页 2 内容")
        t2_w.setAlignment(Qt.AlignCenter)
        tab.addTab(t1_w, "配置")
        tab.addTab(t2_w, "高级")
        tab.setFixedHeight(80)
        self._main_layout.addWidget(tab)

    def _build_section_tokens(self):
        self._main_layout.addWidget(_section_title("Section 1 · 品牌色 & Token 概览"))

        # 色块矩阵
        self._main_layout.addWidget(_subsection_title("色彩 Tokens"))
        color_tokens = [
            "primary", "primary_hover", "primary_pressed", "primary_light",
            "accent", "accent_hover",
            "success", "warning", "error", "info",
            "bg_window", "bg_card", "bg_input", "bg_hover", "bg_selected",
            "text_primary", "text_secondary", "text_hint", "text_disabled",
            "border", "border_light", "border_focus", "border_error",
            "switch_on", "switch_off", "switch_thumb",
        ]
        # 分行展示，每行 8 个
        row_w = QWidget()
        flow = QHBoxLayout(row_w)
        flow.setContentsMargins(0, 0, 0, 0)
        flow.setSpacing(4)
        for i, token in enumerate(color_tokens):
            if i > 0 and i % 8 == 0:
                flow.addStretch()
                self._main_layout.addWidget(row_w)
                row_w = QWidget()
                flow = QHBoxLayout(row_w)
                flow.setContentsMargins(0, 0, 0, 0)
                flow.setSpacing(4)
            flow.addWidget(ColorSwatch(token))
        flow.addStretch()
        self._main_layout.addWidget(row_w)

        # 字号阶梯
        self._main_layout.addWidget(_subsection_title("字号阶梯"))
        sizes = [("xs·11", 11), ("sm·12", 12), ("md·13", 13),
                 ("lg·15", 15), ("xl·16", 16), ("xxl·20", 20)]
        size_row = QWidget()
        sr = QHBoxLayout(size_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(16)
        for label, px in sizes:
            lbl = QLabel(f"{label}px 示例文字")
            lbl.setObjectName("font_sample")
            lbl.setProperty("fontpx", px)
            sr.addWidget(lbl)
        sr.addStretch()
        self._main_layout.addWidget(size_row)
        self._font_samples = size_row

        # 圆角阶梯
        self._main_layout.addWidget(_subsection_title("圆角阶梯"))
        radii = [("xs·2", 2), ("sm·4", 4), ("md·8", 8),
                 ("lg·12", 12), ("xl·16", 16), ("full", 9999)]
        radius_row = QWidget()
        rr = QHBoxLayout(radius_row)
        rr.setContentsMargins(0, 0, 0, 0)
        rr.setSpacing(12)
        for label, r in radii:
            box = QLabel(label)
            box.setFixedSize(64, 40)
            box.setAlignment(Qt.AlignCenter)
            box.setObjectName("radius_sample")
            box.setProperty("radiuspx", r)
            rr.addWidget(box)
        rr.addStretch()
        self._main_layout.addWidget(radius_row)
        self._radius_samples = radius_row

        self._main_layout.addWidget(_hline())

    # ── Section 2: 原生控件 ──
    def _build_section_native(self):
        t = get_theme()
        self._main_layout.addWidget(_section_title("Section 2 · 原生 Qt 控件"))

        self._main_layout.addWidget(_subsection_title("QPushButton（共享 variant）"))
        native_buttons = [
            _make_variant_button(text, variant, enabled=enabled)
            for text, variant, enabled in _BUTTON_SHOWCASE_SPECS
        ]
        self._main_layout.addWidget(_hbox(*native_buttons, "stretch"))

        self._main_layout.addWidget(_subsection_title("QCheckBox / QRadioButton（共享 selection theme）"))
        self._main_layout.addWidget(_build_selection_showcase_row())

        self._main_layout.addWidget(_subsection_title("SearchInput / StyledComboBox / QSpinBox / QDoubleSpinBox"))
        search = _make_showcase_search_input("请输入文本…", height=t.control_height_md)
        combo = _make_showcase_combo(["选项一", "选项二", "选项三"], height=t.control_height_md)
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(42)
        spin.setFixedHeight(t.control_height_md)

        dspin = QDoubleSpinBox()
        dspin.setRange(0, 100)
        dspin.setValue(3.14)
        dspin.setFixedHeight(t.control_height_md)

        self._main_layout.addWidget(_hbox(search, combo, spin, dspin))

        self._main_layout.addWidget(_subsection_title("QSlider / QProgressBar"))
        self._main_layout.addWidget(_build_slider_showcase_row())

        self._main_layout.addWidget(_subsection_title("QTextEdit"))
        te = QTextEdit()
        te.setPlaceholderText("多行文本编辑…")
        te.setFixedHeight(80)
        self._main_layout.addWidget(te)

        self._main_layout.addWidget(_subsection_title("QTabWidget"))
        tab = QTabWidget()
        t1 = QLabel("Tab 1 内容区")
        t1.setAlignment(Qt.AlignCenter)
        t2 = QLabel("Tab 2 内容区")
        t2.setAlignment(Qt.AlignCenter)
        tab.addTab(t1, "标签页 1")
        tab.addTab(t2, "标签页 2")
        tab.setFixedHeight(100)
        self._main_layout.addWidget(tab)

        self._main_layout.addWidget(_hline())

    def _build_section_inputs(self):
        self._main_layout.addWidget(_section_title("Section 3 · 自定义输入控件"))

        # ToggleSwitch
        self._main_layout.addWidget(_subsection_title("ToggleSwitch — 胶囊开关"))
        ts_on = ToggleSwitch(checked=True)
        ts_off = ToggleSwitch(checked=False)
        ts_disabled = ToggleSwitch(checked=True)
        ts_disabled.setEnabled(False)
        self._main_layout.addWidget(_hbox(
            _desc("ON"), ts_on,
            _desc("OFF"), ts_off,
            _desc("Disabled"), ts_disabled,
            "stretch"
        ))

        # SearchInput
        self._main_layout.addWidget(_subsection_title("SearchInput — 搜索输入"))
        si = SearchInput(placeholder="输入关键词搜索…")
        self._main_layout.addWidget(si)

        # ColorPicker
        self._main_layout.addWidget(_subsection_title("ColorPicker — 颜色拾取器"))
        cp = ColorPicker(initial="#4C8BF5")
        self._main_layout.addWidget(cp)

        # SpacingInput
        self._main_layout.addWidget(_subsection_title("SpacingInput — 间距输入"))
        spi = SpacingInput(unit="cm", min_val=0, max_val=10, step=0.5)
        self._main_layout.addWidget(spi)

        # PlaceholderEdit
        self._main_layout.addWidget(_subsection_title("PlaceholderEdit — 占位符编辑器"))
        pe = PlaceholderEdit(placeholder="{{字段名}}")
        pe.set_value("{nn}. {title}")
        self._main_layout.addWidget(pe)

        # FolderPicker
        self._main_layout.addWidget(_subsection_title("FolderPicker — 文件夹选择器"))
        fp = FolderPicker(placeholder="选择输出文件夹…")
        self._main_layout.addWidget(fp)

        self._main_layout.addWidget(_hline())

    # ── Section 4: 选择器控件 ──
    def _build_section_selectors(self):
        self._main_layout.addWidget(_section_title("Section 4 · 选择器控件"))

        # FontCombo
        self._main_layout.addWidget(_subsection_title("FontCombo — 字体选择器"))
        fc_cn = FontCombo(lang="cn")
        fc_en = FontCombo(lang="en")
        self._main_layout.addWidget(_hbox(_desc("中文"), fc_cn, _desc("英文"), fc_en, "stretch"))

        # SizeCombo
        self._main_layout.addWidget(_subsection_title("SizeCombo — 字号选择器"))
        sc = SizeCombo()
        self._main_layout.addWidget(sc)

        # NumberingPreset
        self._main_layout.addWidget(_subsection_title("NumberingPreset — 编号预设下拉"))
        np_ = NumberingPreset()
        self._main_layout.addWidget(np_)

        self._main_layout.addWidget(_hline())

    # ── Section 5: 容器与布局 ──
    def _build_section_containers(self):
        self._main_layout.addWidget(_section_title("Section 5 · 容器与布局控件"))

        # Card
        self._main_layout.addWidget(_subsection_title("Card — 卡片容器"))
        card = Card("卡片标题示例")
        inner = QLabel("卡片内容区域 — 圆角 + 阴影 + 标题栏")
        inner.setAlignment(Qt.AlignCenter)
        inner.setFixedHeight(60)
        card.add_widget(inner)
        self._main_layout.addWidget(card)

        # FormRow
        self._main_layout.addWidget(_subsection_title("FormRow — 表单行"))
        fr1 = FormRow("字体大小:", QSpinBox())
        fr2 = FormRow("启用水印:", ToggleSwitch())
        fr3 = FormRow("输出路径:", QLineEdit())
        self._main_layout.addWidget(fr1)
        self._main_layout.addWidget(fr2)
        self._main_layout.addWidget(fr3)

        # CollapsibleSection
        self._main_layout.addWidget(_subsection_title("CollapsibleSection — 折叠面板"))
        cs = CollapsibleSection("点击展开/收起", expanded=True)
        cs_inner = QLabel("折叠区域内的内容，支持任意子控件。")
        cs_inner.setFixedHeight(50)
        cs_inner.setAlignment(Qt.AlignCenter)
        cs.add_widget(cs_inner)
        self._main_layout.addWidget(cs)

        self._main_layout.addWidget(_hline())

    # ── Section 6: 反馈 & 状态 ──
    def _build_section_feedback(self):
        t = get_theme()
        self._main_layout.addWidget(_section_title("Section 5 · 提示与状态 (Feedback)"))

        # StatusIndicator
        self._main_layout.addWidget(_subsection_title("StatusIndicator — 状态指示器"))
        statuses = ["success", "warning", "error", "skipped", "running", "pending"]
        status_widgets = []
        for s in statuses:
            si = StatusIndicator(status=s, size=20)
            status_widgets.append(_desc(s))
            status_widgets.append(si)
        status_widgets.append("stretch")
        self._main_layout.addWidget(_hbox(*status_widgets))

        # OverrideBadge
        self._main_layout.addWidget(_subsection_title("OverrideBadge — 覆盖标记"))
        ob = OverrideBadge(original_value="宋体 12pt")
        self._main_layout.addWidget(ob)

        # ProgressIndicator
        self._main_layout.addWidget(_subsection_title("ProgressIndicator — 执行进度条"))
        pi = ProgressIndicator()
        pi.set_progress(7, 10, "正在处理段落样式…")
        self._main_layout.addWidget(pi)

        # ModuleStepList
        self._main_layout.addWidget(_subsection_title("ModuleStepList — 模块步骤列表"))
        msl = ModuleStepList()
        msl.setFixedHeight(120)
        msl.add_module("heading", "标题编号", checked=True)
        msl.add_module("font", "字体统一", checked=True)
        msl.add_module("spacing", "段距调整", checked=False)
        msl.add_module("toc", "目录生成", checked=True)
        msl.set_status("heading", "check-circle", t.success)
        msl.set_status("font", "loader", t.primary)
        msl.set_status("table", "square", t.text_hint)
        self._main_layout.addWidget(msl)

        self._main_layout.addWidget(_hline())

    # ── Section 7: 展示控件 ──
    def _build_section_display(self):
        self._main_layout.addWidget(_section_title("Section 7 · 展示控件"))

        # StylePreview
        self._main_layout.addWidget(_subsection_title("StylePreview — 样式预览"))
        sp = StylePreview()
        sp.update_preview(font_cn="微软雅黑", size_pt=14, bold=True)
        self._main_layout.addWidget(sp)

        # IconButton (三种变体)
        self._main_layout.addWidget(_subsection_title("IconButton — 图标按钮 (ghost / circle / square)"))
        self._icon_btns = []
        for variant, tip in [("ghost", "ghost"), ("circle", "circle"), ("square", "square")]:
            ib = IconButton(variant=variant, tooltip=tip, size=36)
            ib.setIcon(get_icon("settings", 20))
            ib.setIconSize(QSize(20, 20))
            self._icon_btns.append(ib)
        self._main_layout.addWidget(_hbox(
            _desc("ghost"), self._icon_btns[0],
            _desc("circle"), self._icon_btns[1],
            _desc("square"), self._icon_btns[2],
            "stretch"
        ))

        # Lucide 图标一览
        self._main_layout.addWidget(_subsection_title("Lucide 图标库"))
        icon_names = get_icon_names()
        icon_row = QWidget()
        ir = QHBoxLayout(icon_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.setSpacing(8)
        for name in icon_names:
            lbl = QLabel()
            icon = get_icon(name, 20)
            lbl.setPixmap(icon.pixmap(20, 20))
            lbl.setToolTip(name)
            lbl.setFixedSize(28, 28)
            lbl.setAlignment(Qt.AlignCenter)
            ir.addWidget(lbl)
        ir.addStretch()
        self._main_layout.addWidget(icon_row)
        self._icon_row = icon_row

        self._main_layout.addWidget(_hline())

    # ── Section 8: 弹窗对话框 ──
    def _build_section_dialogs(self):
        self._main_layout.addWidget(_section_title("Section 8 · 弹窗对话框"))
        self._main_layout.addWidget(_desc(
            "点击按钮弹出对应对话框，验证弹窗在当前主题下的渲染效果。"
        ))

        for text, fn in [
            ("ℹ 信息 info()", lambda: info("操作完成", "文件已成功保存到 output/ 目录。")),
            ("✓ 成功 success()", lambda: success("格式化完成", "共处理 42 个段落，0 个错误。")),
            ("⚠ 警告 warning()", lambda: warning("覆盖警告", "目标文件已存在，继续操作将覆盖原有内容。")),
            ("✕ 错误 error()", lambda: error(
                "格式化失败", "处理文档时发生错误。",
                detail="Traceback:\n  File \"pipeline.py\", line 42\n"
                       "    result = module.execute(doc)\n"
                       "ValueError: 无法解析样式")),
            ("❓ 确认 confirm()", lambda: confirm("保存更改", "当前模板已修改，是否保存？")),
            ("❗ 危险确认 confirm(destructive)", lambda: confirm(
                "删除模板", "确定要删除？此操作不可撤销。",
                confirm_text="删除", destructive=True)),
            ("✏ 输入 input_text()", lambda: input_text(
                "新建模板", "请输入模板名称:", placeholder="thesis-v2")),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            apply_button_variant(btn, "secondary")
            btn.clicked.connect(fn)
            btn.setObjectName("dialog_trigger_btn")
            self._main_layout.addWidget(btn)

    # ── 全局主题 ──
    def _apply_theme(self):
        t = get_theme()
        
        # 预渲染控件用 SVG 箭头 (转存为文件以修复 Qt/PySide QSS 对 data URI 的解析 Bug)
        # 风险防护: 缓存路径 + 清理旧文件，防止主题切换时临时文件泄漏
        import tempfile, os
        c = t.text_secondary
        
        # 清理上一轮主题切换遗留的 SVG 临时文件
        for old_path in getattr(self, '_svg_temp_files', []):
            try:
                os.remove(old_path)
            except OSError:
                pass
        self._svg_temp_files = []
        
        def _make_svg(is_up: bool) -> str:
            pts = "18 15 12 9 6 15" if is_up else "6 9 12 15 18 9"
            svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{c}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='{pts}'/></svg>"
            fd, path = tempfile.mkstemp(suffix=".svg", text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(svg)
            self._svg_temp_files.append(path)
            return path.replace('\\', '/')

        url_down = f"url({_make_svg(False)})"
        url_up = f"url({_make_svg(True)})"
        button_qss = build_button_stylesheet(t)
        selection_qss = build_checkbox_stylesheet(t)

        self.setStyleSheet(f"""
            StyleGallery {{
                background: {t.bg_window};
            }}

            /* 工具栏 */
            #gallery_toolbar {{
                background: {t.bg_sidebar};
                border-bottom: 1px solid {t.border_light};
            }}
            #gallery_title {{
                font-size: {t.font_size_xl}px;
                font-weight: {t.font_weight_bold};
                color: {t.text_primary};
            }}

            /* 主题按钮 */
            QPushButton[objectName^="theme_btn"] {{
                background: {t.bg_card};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                font-size: {t.font_size_sm}px;
                padding: 0 12px;
            }}
            QPushButton[objectName^="theme_btn"]:checked {{
                background: {t.primary};
                color: {t.text_on_primary};
                border-color: {t.primary};
            }}
            QPushButton[objectName^="theme_btn"]:hover {{
                border-color: {t.primary};
            }}

            /* Section 标题 */
            #section_title {{
                font-size: {t.font_size_xxl}px;
                font-weight: {t.font_weight_bold};
                color: {t.text_primary};
                padding: 4px 0;
            }}
            #subsection_title {{
                font-size: {t.font_size_lg}px;
                font-weight: {t.font_weight_bold};
                color: {t.text_secondary};
                padding: 2px 0;
            }}
            #desc_label {{
                font-size: {t.font_size_sm}px;
                color: {t.text_hint};
            }}

            /* 分割线 */
            #gallery_hline {{
                background: {t.border_light};
                max-height: 1px;
                margin: 8px 0;
            }}

            /* 滚动区域 */
            #gallery_scroll {{
                border: none;
                background: {t.bg_window};
            }}
            #gallery_container {{
                background: {t.bg_window};
            }}
            QScrollBar:vertical {{
                background: {t.scrollbar_track};
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.scrollbar_thumb};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.scrollbar_thumb_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            {button_qss}
            #dialog_trigger_btn {{
                text-align: left;
            }}

            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background: {t.bg_input};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.input_radius}px;
                padding: {t.input_padding_y}px {t.input_padding_x}px;
                font-size: {t.font_size_md}px;
                selection-background-color: {t.primary};
                selection-color: {t.text_on_primary};
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {t.border_focus};
                background: {t.bg_window};
            }}
            QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                background: {t.bg_hover};
                color: {t.text_disabled};
            }}

            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background: transparent;
                border: none;
                width: {t.spin_button_width}px;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background: {t.bg_hover};
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: {url_up};
                width: 14px;
                height: 14px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: {url_down};
                width: 14px;
                height: 14px;
            }}

            QProgressBar {{
                background: {t.progress_track};
                border: none;
                border-radius: 3px;
                text-align: center;
                color: transparent;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background: {t.progress_fill};
                border-radius: 3px;
            }}

            QTextEdit {{
                background: {t.bg_input};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                padding: 8px;
                font-size: {t.font_size_md}px;
            }}

            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {t.border};
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {t.tab_inactive_text};
                padding: 6px 16px;
                border: none;
                border-bottom: 2px solid transparent;
                margin-right: 4px;
                font-size: {t.font_size_md}px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                color: {t.tab_active_text};
                border-bottom: 2px solid {t.primary};
            }}
            QTabBar::tab:hover:!selected {{
                color: {t.text_primary};
                border-bottom: 2px solid {t.border_light};
            }}
            {selection_qss}

            QLabel {{
                color: {t.text_primary};
                font-size: {t.font_size_md}px;
            }}

            QGroupBox {{
                border: 1px solid {t.border};
                border-radius: {t.radius_md}px;
                margin-top: 8px;
                padding-top: 16px;
                font-size: {t.font_size_md}px;
                color: {t.text_primary};
            }}
        """)

        # 字号样本动态刷新
        for child in self._font_samples.findChildren(QLabel):
            px = child.property("fontpx")
            if px:
                child.setStyleSheet(
                    f"font-size: {px}px; color: {t.text_primary}; "
                    f"padding: 4px 8px; background: {t.bg_card}; "
                    f"border: 1px solid {t.border}; border-radius: {t.radius_sm}px;")

        # 圆角样本动态刷新
        for child in self._radius_samples.findChildren(QLabel):
            r = child.property("radiuspx")
            if r is not None:
                child.setStyleSheet(
                    f"background: {t.primary_light}; color: {t.text_primary}; "
                    f"border: 1px solid {t.border}; border-radius: {min(r, 20)}px; "
                    f"font-size: 10px; padding: 4px;")

        # 重新渲染 Lucide 图标行
        if hasattr(self, '_icon_row'):
            icon_names = get_icon_names()
            for i, child in enumerate(self._icon_row.findChildren(QLabel)):
                if i < len(icon_names):
                    icon = get_icon(icon_names[i], 20)
                    child.setPixmap(icon.pixmap(20, 20))

        # 图标按钮刷新
        if hasattr(self, '_icon_btns'):
            for ib in self._icon_btns:
                ib.setIcon(get_icon("settings", 20))
                ib.setIconSize(QSize(20, 20))


# ── 启动 ──
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 全局输入守卫（滚轮防劫持 + SpinBox Enter/Click 行为修正）
    from src.shared.ui.input_guard import install_global_input_guard
    _input_guard = install_global_input_guard(app)  # noqa: F841

    t = get_theme()
    font = QFont(t.font_family.split(",")[0].strip("' "))
    font.setPointSize(10)
    app.setFont(font)

    win = StyleGallery()
    win.show()
    sys.exit(app.exec())
