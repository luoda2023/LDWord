"""
heading_numbering_panel — 标题编号配置面板 (Professional Dual-Mode Redesign)
"""

from __future__ import annotations

from src.qt_api import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.config.heading_presets import get_preset_labels
from src.shared.ui import ThemedRadioButton, ThemedSlider
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme, bind_theme
from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.base_panel import BasePanel
from src.ui.heading_numbering_logic import (
    STYLE_OPTIONS,
    build_detail_state,
    build_editor_enable_state,
    build_expert_toggle_text,
    build_non_numbered_toggle_text,
    compose_display_template,
    format_csv_items,
    parse_csv_items,
    should_show_chain_separator,
)
from src.ui.panels.heading_numbering_styles import build_heading_numbering_panel_stylesheet

_MODE_SIMPLE = 0
_MODE_ADVANCED = 1




class HeadingNumberingPanel(BasePanel):
    """标题编号配置面板 (专业双轨制)。"""

    panel_title = "标题编号"
    panel_icon = "hash"

    def _setup_ui(self) -> None:
        self._initialize_panel_state()
        self._build_scroll_content_host()

        self._build_mode_switcher()
        self._build_preset_header()
        self._build_mode_stack_views()

        self._build_non_numbered_section()
        self._main_layout.addStretch(1)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _initialize_panel_state(self) -> None:
        self.setObjectName("HeadingNumberingPanel")
        self._adapter = HeadingNumberingAdapter(parent=self)
        self._current_mode = _MODE_SIMPLE
        self._selected_adv_level = 1
        self._is_syncing_ui = False
        self._is_custom_mode = False

    def _build_scroll_content_host(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self._main_layout = QVBoxLayout(content)
        self._main_layout.setContentsMargins(20, 20, 20, 20)
        self._main_layout.setSpacing(20)

    def _build_mode_stack_views(self) -> None:
        self._stack = QStackedWidget()
        self._main_layout.addWidget(self._stack)

        self._simple_widget = QWidget()
        self._build_simple_view(self._simple_widget)
        self._stack.addWidget(self._simple_widget)

        self._advanced_widget = QWidget()
        self._build_advanced_view(self._advanced_widget)
        self._stack.addWidget(self._advanced_widget)

    # ━━ 1. 顶部模式切换 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_mode_switcher(self) -> None:
        t = get_theme()
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)
        
        lbl = self._label("配置模式:")
        h.addWidget(lbl)

        mode_container, mode_layout = self._build_mode_button_container(t)
        self._build_mode_buttons(mode_layout)
        h.addWidget(mode_container)
        h.addStretch(1)
        self._main_layout.addWidget(row)

    def _build_mode_button_container(self, theme):
        self._mode_container = QFrame()
        self._mode_container.setObjectName("hn_mode_container")
        self._mode_container.setFixedHeight(theme.control_height_md + 4)
        layout = QHBoxLayout(self._mode_container)
        layout.setContentsMargins(theme.spacing_xs, theme.spacing_xs, theme.spacing_xs, theme.spacing_xs)
        layout.setSpacing(theme.spacing_xs + theme.spacing_sm)
        return self._mode_container, layout

    def _build_mode_buttons(self, layout: QHBoxLayout) -> None:
        self._mode_btn_simple = ThemedRadioButton("快速应用")
        self._mode_btn_simple.setAutoExclusive(True)
        self._mode_btn_simple.setChecked(True)
        self._mode_btn_simple.setCursor(Qt.PointingHandCursor)

        self._mode_btn_adv = ThemedRadioButton("自定义多级列表")
        self._mode_btn_adv.setAutoExclusive(True)
        self._mode_btn_adv.setCursor(Qt.PointingHandCursor)

        layout.addWidget(self._mode_btn_simple)
        layout.addWidget(self._mode_btn_adv)

        self._mode_btn_simple.clicked.connect(lambda *args: self._switch_mode(_MODE_SIMPLE))
        self._mode_btn_adv.clicked.connect(lambda *args: self._switch_mode(_MODE_ADVANCED))

    def _build_preset_header(self) -> None:
        t = get_theme()
        
        preset_frame = QFrame()
        preset_frame.setObjectName("hn_preset_frame")
        h = QHBoxLayout(preset_frame)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(16)

        self._build_preset_selector_group(h, t)
        h.addSpacing(32)
        self._build_levels_selector_group(h, t)
        
        h.addStretch(1)
        self._main_layout.addWidget(preset_frame)

    def _build_preset_selector_group(self, layout: QHBoxLayout, theme) -> None:
        layout.addWidget(self._label("编号库 (预设):"))
        self._preset_cb = StyledComboBox()
        self._preset_cb.setFixedHeight(theme.control_height_md)
        self._preset_cb.setMinimumWidth(theme.heading_panel_preset_width)
        for key, label in get_preset_labels():
            self._preset_cb.addItem(label, key)
        self._preset_cb.addItem("⚙️ 开启自定义模式 (允许修改参数)", "__custom__")
        
        # User MUST explicitly select Custom to unlock the panel.
        model = self._preset_cb.model()
        last = model.item(self._preset_cb.count() - 1)
        last.setEnabled(True) 
        layout.addWidget(self._preset_cb)

    def _build_levels_selector_group(self, layout: QHBoxLayout, theme) -> None:
        layout.addWidget(self._label("控制最大级数:"))
        self._levels_slider = ThemedSlider(Qt.Horizontal)
        self._levels_slider.setRange(1, 8)
        self._levels_slider.setValue(4)
        self._levels_slider.setFixedWidth(theme.heading_panel_levels_width)
        layout.addWidget(self._levels_slider)
        self._levels_value_label = self._small_label("4 级")
        self._levels_value_label.setAlignment(Qt.AlignCenter)
        self._levels_value_label.setFixedWidth(theme.heading_panel_short_input_width)
        layout.addWidget(self._levels_value_label)

    # ━━ 2. 傻瓜模式视图 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_simple_view(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self._simple_frame = QFrame()
        self._simple_frame.setObjectName("hn_simple_frame")
        self._simple_layout = QVBoxLayout(self._simple_frame)
        self._simple_layout.setContentsMargins(16, 16, 16, 16)
        self._simple_layout.setSpacing(0)
        
        layout.addWidget(self._simple_frame)
        self._simple_rows = []

    def _rebuild_simple_preview(self) -> None:
        _clear_layout(self._simple_layout)
        self._simple_rows.clear()
        
        if not self._adapter.has_template:
            return
            
        t = get_theme()
        levels = self._adapter.max_levels
        
        for level in range(1, levels + 1):
            self._append_simple_preview_row(level, t)

    def _append_simple_preview_row(self, level: int, theme) -> None:
        binding = self._adapter.get_binding(level)
        row, preview_label, checkbox = self._build_simple_preview_row(level, binding, theme)
        self._simple_layout.addWidget(row)
        self._simple_rows.append({"level": level, "label": preview_label, "checkbox": checkbox})

    def _build_simple_preview_row(self, level: int, binding, theme):
        is_enabled = binding.enabled if binding else True

        row, layout = self._build_simple_preview_row_shell(level, theme)
        tag, preview_label, demo = self._build_simple_preview_labels(level, is_enabled, theme)
        spacer = self._build_simple_preview_spacer()
        checkbox = self._build_simple_preview_checkbox(level, binding)
        self._apply_simple_preview_row_state(row, tag, preview_label, demo, checkbox, is_enabled)

        self._layout_simple_preview_row(layout, tag, preview_label, demo, spacer, checkbox)
        return row, preview_label, checkbox

    def _build_simple_preview_row_shell(self, level: int, theme):
        row = QFrame()
        row.setObjectName("hn_preview_row")
        row.setFixedHeight(theme.heading_panel_preview_row_height)

        layout = QHBoxLayout(row)
        indent_space = (level - 1) * 24
        layout.setContentsMargins(16 + indent_space, 0, 16, 0)
        layout.setSpacing(12)
        return row, layout

    @staticmethod
    def _build_simple_preview_spacer() -> QWidget:
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return spacer

    def _apply_simple_preview_row_state(
        self,
        row: QFrame,
        tag: QLabel,
        preview_label: QLabel,
        demo: QLabel,
        checkbox: QCheckBox,
        is_enabled: bool,
    ) -> None:
        self._apply_simple_preview_disabled_state(
            row=row,
            tag=tag,
            preview_label=preview_label,
            demo=demo,
            checkbox=checkbox,
            is_enabled=is_enabled,
        )

    def _build_simple_preview_labels(self, level: int, is_enabled: bool, theme):
        tag = QLabel(f"级别 {level}")
        tag.setObjectName("hn_preview_tag")
        tag.setFixedWidth(theme.heading_panel_preview_tag_width)

        preview_text = self._adapter.preview_number(level)
        preview_label = QLabel(preview_text if is_enabled else "— (未启用)")
        preview_label.setObjectName("hn_preview_num")

        demo = QLabel("这是一个示例标题内容")
        demo.setObjectName("hn_preview_demo")
        return tag, preview_label, demo

    def _build_simple_preview_checkbox(self, level: int, binding) -> QCheckBox:
        checkbox = QCheckBox("生成到 TOC 目录")
        checkbox.setObjectName("hn_preview_cb")
        checkbox.setChecked(binding.include_in_toc if binding else True)
        checkbox.toggled.connect(lambda checked, lv=level: self._on_toc_changed(lv, checked))
        return checkbox

    def _layout_simple_preview_row(
        self,
        layout: QHBoxLayout,
        tag: QLabel,
        preview_label: QLabel,
        demo: QLabel,
        spacer: QWidget,
        checkbox: QCheckBox,
    ) -> None:
        layout.addWidget(tag)
        layout.addWidget(preview_label)
        layout.addWidget(demo)
        layout.addWidget(spacer)
        layout.addWidget(checkbox)

    def _apply_simple_preview_disabled_state(
        self,
        *,
        row: QFrame,
        tag: QLabel,
        preview_label: QLabel,
        demo: QLabel,
        checkbox: QCheckBox,
        is_enabled: bool,
    ) -> None:
        row.setProperty("disabled_visual", not is_enabled)
        for widget in [tag, preview_label, demo]:
            _set_disabled_visual(widget, not is_enabled, strikeout=True)
        if not is_enabled:
            checkbox.setEnabled(False)

    # ━━ 3. 进阶模式视图 (Master-Detail) ━━━━━━━━━━━

    def _build_advanced_view(self, parent: QWidget) -> None:
        t = get_theme()
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_advanced_list_sidebar(t))
        layout.addWidget(self._build_advanced_detail_panel(), 1)

    def _build_advanced_list_sidebar(self, theme) -> QFrame:
        left_frame = QFrame()
        left_frame.setObjectName("hn_list_frame")
        left_frame.setFixedWidth(theme.heading_panel_sidebar_width)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        list_header = QLabel("要修改的级别")
        list_header.setObjectName("hn_list_header")
        list_header.setFixedHeight(theme.control_height_md)
        list_header.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(list_header)

        self._adv_list = QListWidget()
        self._adv_list.setObjectName("hn_level_list")
        self._adv_list.currentRowChanged.connect(self._on_adv_level_selected)
        left_layout.addWidget(self._adv_list)
        return left_frame

    def _build_advanced_detail_panel(self) -> QFrame:
        self._adv_detail_frame = QFrame()
        self._adv_detail_frame.setObjectName("hn_detail_frame")
        self._adv_detail_layout = QVBoxLayout(self._adv_detail_frame)
        self._adv_detail_layout.setContentsMargins(24, 20, 24, 20)
        self._adv_detail_layout.setAlignment(Qt.AlignTop)

        self._build_professional_editor(self._adv_detail_layout)
        return self._adv_detail_frame

    def _build_professional_editor(self, parent_layout: QVBoxLayout) -> None:
        t = get_theme()

        self._build_editor_detail_header(parent_layout)
        form_w, form_l = self._build_editor_form_container()
        self._build_editor_number_style_row(form_l, t)
        self._build_editor_affix_row(form_l, t)
        self._build_editor_chain_row(form_l, t)

        parent_layout.addWidget(form_w)
        parent_layout.addSpacing(24)

        parent_layout.addWidget(self._build_editor_divider())
        parent_layout.addSpacing(12)

        self._build_editor_toc_row(parent_layout)
        parent_layout.addSpacing(12)
        self._build_editor_expert_section(parent_layout, t)
        parent_layout.addStretch(1)

    def _build_editor_detail_header(self, parent_layout: QVBoxLayout) -> None:
        self._detail_title = QLabel("级别配置")
        self._detail_title.setObjectName("hn_detail_title")
        parent_layout.addWidget(self._detail_title)
        parent_layout.addSpacing(16)

    @staticmethod
    def _build_editor_form_container() -> tuple[QWidget, QVBoxLayout]:
        form_w = QWidget()
        form_l = QVBoxLayout(form_w)
        form_l.setContentsMargins(0, 0, 0, 0)
        form_l.setSpacing(20)
        return form_w, form_l

    @staticmethod
    def _build_editor_divider() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("hn_divider")
        return sep

    def _build_editor_number_style_row(self, form_layout: QVBoxLayout, theme) -> None:
        row = QHBoxLayout()
        row.addWidget(self._form_label("此级别的编号样式:"))

        self._core_style_cb = StyledComboBox()
        self._core_style_cb.setFixedHeight(theme.control_height_md)
        self._core_style_cb.setMinimumWidth(theme.heading_panel_editor_combo_width)
        for key, desc in STYLE_OPTIONS:
            self._core_style_cb.addItem(desc, key)
        self._core_style_cb.currentIndexChanged.connect(self._on_editor_changed)
        row.addWidget(self._core_style_cb)
        row.addStretch(1)
        form_layout.addLayout(row)

    def _build_editor_affix_row(self, form_layout: QVBoxLayout, theme) -> None:
        row = QHBoxLayout()
        row.addWidget(self._form_label("编号附加文本:"))

        prefix_label, prefix_edit = self._build_editor_prefix_field(theme)
        suffix_label, suffix_edit = self._build_editor_suffix_field(theme)
        self._layout_editor_affix_row(row, prefix_label, prefix_edit, suffix_label, suffix_edit)
        form_layout.addLayout(row)

    def _build_editor_prefix_field(self, theme):
        prefix_label = self._small_label("前缀:")
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText("如: 第")
        self._prefix_edit.setFixedWidth(theme.heading_panel_short_input_width)
        self._prefix_edit.setFixedHeight(theme.control_height_md)
        self._prefix_edit.textEdited.connect(self._on_editor_changed)
        return prefix_label, self._prefix_edit

    def _build_editor_suffix_field(self, theme):
        suffix_label = self._small_label("后缀:")
        self._suffix_edit = QLineEdit()
        self._suffix_edit.setPlaceholderText("如: 章")
        self._suffix_edit.setFixedWidth(theme.heading_panel_short_input_width)
        self._suffix_edit.setFixedHeight(theme.control_height_md)
        self._suffix_edit.textEdited.connect(self._on_editor_changed)
        return suffix_label, self._suffix_edit

    def _layout_editor_affix_row(
        self,
        row: QHBoxLayout,
        prefix_label: QLabel,
        prefix_edit: QLineEdit,
        suffix_label: QLabel,
        suffix_edit: QLineEdit,
    ) -> None:
        row.addWidget(prefix_label)
        row.addWidget(prefix_edit)
        row.addSpacing(12)
        row.addWidget(suffix_label)
        row.addWidget(suffix_edit)
        row.addStretch(1)

    def _build_editor_chain_row(self, form_layout: QVBoxLayout, theme) -> None:
        row = QHBoxLayout()
        row.addWidget(self._form_label("包含的级别号:"))

        chain_selector = self._build_editor_chain_selector(theme)
        chain_sep_lbl, chain_sep_edit = self._build_editor_chain_separator_fields(theme)
        self._layout_editor_chain_row(row, chain_selector, chain_sep_lbl, chain_sep_edit)
        form_layout.addLayout(row)

    def _build_editor_chain_selector(self, theme) -> StyledComboBox:
        self._chain_cb = StyledComboBox()
        self._chain_cb.setFixedHeight(theme.control_height_md)
        self._chain_cb.setMinimumWidth(theme.heading_panel_editor_combo_width)
        self._chain_cb.currentIndexChanged.connect(self._on_chain_selected)
        return self._chain_cb

    def _build_editor_chain_separator_fields(self, theme):
        self._chain_sep_lbl = self._small_label("分隔符:")
        self._chain_sep_edit = QLineEdit()
        self._chain_sep_edit.setFixedWidth(theme.heading_panel_tiny_input_width)
        self._chain_sep_edit.setAlignment(Qt.AlignCenter)
        self._chain_sep_edit.setFixedHeight(theme.control_height_md)
        self._chain_sep_edit.textEdited.connect(self._on_chain_sep_edited)
        return self._chain_sep_lbl, self._chain_sep_edit

    def _layout_editor_chain_row(
        self,
        row: QHBoxLayout,
        chain_selector: StyledComboBox,
        chain_sep_label: QLabel,
        chain_sep_edit: QLineEdit,
    ) -> None:
        row.addWidget(chain_selector)
        row.addSpacing(12)
        row.addWidget(chain_sep_label)
        row.addWidget(chain_sep_edit)
        row.addStretch(1)

    def _build_editor_toc_row(self, parent_layout: QVBoxLayout) -> None:
        opt_lay = QHBoxLayout()
        self._toc_checkbox = QCheckBox("此级别在目录中显示")
        self._toc_checkbox.toggled.connect(self._on_detail_toc_changed)
        opt_lay.addWidget(self._toc_checkbox)
        opt_lay.addStretch(1)
        parent_layout.addLayout(opt_lay)

    def _build_editor_expert_section(self, parent_layout: QVBoxLayout, theme) -> None:
        parent_layout.addWidget(self._build_editor_expert_toggle())
        ex_layout = self._build_editor_expert_frame()

        self._build_editor_reference_style_row(ex_layout, theme)
        self._build_editor_title_separator_row(ex_layout, theme)
        self._build_editor_raw_template_row(ex_layout, theme)
        
        self._expert_frame.setVisible(False)
        parent_layout.addWidget(self._expert_frame)

    def _build_editor_expert_toggle(self) -> QPushButton:
        self._expert_toggle = QPushButton("▸ 显示更多高级选项")
        self._expert_toggle.setObjectName("hn_section_toggle")
        self._expert_toggle.setFlat(True)
        self._expert_toggle.setCursor(Qt.PointingHandCursor)
        self._expert_toggle.clicked.connect(self._toggle_expert_hatch)
        return self._expert_toggle

    def _build_editor_expert_frame(self) -> QVBoxLayout:
        self._expert_frame = QFrame()
        self._expert_frame.setObjectName("hn_expert_frame")
        ex_layout = QVBoxLayout(self._expert_frame)
        ex_layout.setContentsMargins(12, 12, 12, 12)
        ex_layout.setSpacing(12)
        return ex_layout

    def _build_editor_reference_style_row(self, layout: QVBoxLayout, theme) -> None:
        row = QHBoxLayout()
        row.addWidget(self._small_label("作为被引用的父级时显示形式:"))
        self._ref_style_cb = StyledComboBox()
        self._ref_style_cb.setMinimumWidth(theme.heading_panel_reference_combo_width)
        for key, desc in STYLE_OPTIONS:
            self._ref_style_cb.addItem(desc, key)
        self._ref_style_cb.currentIndexChanged.connect(self._on_ref_style_edited)
        row.addWidget(self._ref_style_cb)
        row.addStretch(1)
        layout.addLayout(row)

    def _build_editor_title_separator_row(self, layout: QVBoxLayout, theme) -> None:
        row = QHBoxLayout()
        row.addWidget(self._small_label("编号后跟随的缩进字符:"))
        self._title_sep_edit = QLineEdit()
        self._title_sep_edit.setPlaceholderText("留空为默认")
        self._title_sep_edit.setFixedWidth(theme.heading_panel_short_input_width)
        self._title_sep_edit.textEdited.connect(self._on_title_sep_edited)
        row.addWidget(self._title_sep_edit)
        row.addStretch(1)
        layout.addLayout(row)

    def _build_editor_raw_template_row(self, layout: QVBoxLayout, theme) -> None:
        row = QHBoxLayout()
        self._use_raw_cb = QCheckBox("覆盖上方逻辑，直接编辑原始编号字符串模式")
        self._use_raw_cb.toggled.connect(self._on_use_raw_toggled)
        row.addWidget(self._use_raw_cb)

        self._raw_template_edit = QLineEdit()
        self._raw_template_edit.setPlaceholderText("例如: {parent.nn}-{cn}")
        self._raw_template_edit.setEnabled(False)
        self._raw_template_edit.setMinimumWidth(theme.heading_panel_raw_template_width)
        self._raw_template_edit.textEdited.connect(self._on_raw_template_edited)
        row.addWidget(self._raw_template_edit)
        row.addStretch(1)
        layout.addLayout(row)

    def _rebuild_advanced_list(self) -> None:
        t = get_theme()
        self._adv_list.blockSignals(True)
        self._adv_list.clear()
        
        if not self._adapter.has_template:
            self._adv_list.blockSignals(False)
            return
            
        levels = self._adapter.max_levels
        for level in range(1, levels + 1):
            self._append_advanced_level_item(level, t)

        self._sync_advanced_list_current_row(levels)
        self._adv_list.blockSignals(False)
        self._sync_detail_pane()

    def _append_advanced_level_item(self, level: int, theme) -> None:
        binding = self._adapter.get_binding(level)
        preview_text = self._adapter.preview_number(level)
        item = QListWidgetItem()
        item.setSizeHint(QSize(theme.heading_panel_sidebar_width, theme.control_height_md))
        item.setData(Qt.UserRole, level)
        self._adv_list.addItem(item)
        self._adv_list.setItemWidget(item, self._build_advanced_level_row(level, binding, preview_text))

    def _build_advanced_level_row(self, level: int, binding, preview_text: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 0, 8, 0)

        en_cb = self._build_advanced_level_checkbox(level, binding)
        lv_lbl, txt_lbl = self._build_advanced_level_labels(level, preview_text)

        _set_disabled_visual(txt_lbl, bool(binding and not binding.enabled))

        self._layout_advanced_level_row(layout, en_cb, lv_lbl, txt_lbl)
        return widget

    def _build_advanced_level_checkbox(self, level: int, binding) -> QCheckBox:
        en_cb = QCheckBox()
        en_cb.setChecked(binding.enabled if binding else True)
        en_cb.setToolTip("启用/禁用此级别的编号")
        en_cb.toggled.connect(lambda checked, lv=level: self._on_level_enabled_changed(lv, checked))
        return en_cb

    def _build_advanced_level_labels(self, level: int, preview_text: str):
        lv_lbl = QLabel(f"级别 {level}")
        lv_lbl.setObjectName("hn_list_lv")
        txt_lbl = QLabel(preview_text if preview_text else "—")
        txt_lbl.setObjectName("hn_list_txt")
        txt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return lv_lbl, txt_lbl

    def _layout_advanced_level_row(
        self,
        layout: QHBoxLayout,
        checkbox: QCheckBox,
        level_label: QLabel,
        text_label: QLabel,
    ) -> None:
        layout.addWidget(checkbox)
        layout.addWidget(level_label)
        layout.addWidget(text_label)

    def _sync_advanced_list_current_row(self, levels: int) -> None:
        cur_row = max(0, min(self._selected_adv_level - 1, levels - 1))
        self._adv_list.setCurrentRow(cur_row)

    def _on_adv_level_selected(self, idx: int) -> None:
        self._sync_detail_pane()
        
    def _sync_detail_pane(self) -> None:
        if not self._adapter.has_template: return

        resolved = self._resolve_selected_detail_binding()
        if not resolved:
            return

        level, binding = resolved
        
        self._is_syncing_ui = True
        state = build_detail_state(level, binding)

        self._sync_detail_basic_fields(state)
        self._sync_detail_chain_fields(state)
        self._sync_detail_advanced_fields(state)
        self._reset_detail_raw_toggle()

        self._finish_detail_sync()

    def _resolve_selected_detail_binding(self):
        item = self._adv_list.currentItem()
        if not item:
            return None

        level = item.data(Qt.UserRole)
        self._selected_adv_level = level

        binding = self._adapter.get_binding(level)
        if not binding:
            return None
        return level, binding

    def _finish_detail_sync(self) -> None:
        self._sync_chain_sep_visibility()
        self._is_syncing_ui = False
        self._sync_lock_state()

    def _sync_detail_basic_fields(self, state) -> None:
        self._detail_title.setText(state.title)
        self._prefix_edit.setText(state.prefix)
        self._suffix_edit.setText(state.suffix)
        _select(self._core_style_cb, state.core_style)
        self._toc_checkbox.setChecked(state.include_in_toc)

    def _sync_detail_chain_fields(self, state) -> None:
        self._chain_cb.blockSignals(True)
        self._chain_cb.clear()
        for label, value in state.chain_options:
            self._chain_cb.addItem(label, value)

        _select(self._chain_cb, state.chain_value)
        self._chain_cb.blockSignals(False)
        self._chain_sep_edit.setText(state.chain_separator)

    def _sync_detail_advanced_fields(self, state) -> None:
        _select(self._ref_style_cb, state.reference_core_style)
        self._title_sep_edit.setText(state.title_separator)
        self._raw_template_edit.setText(state.raw_template)

    def _reset_detail_raw_toggle(self) -> None:
        self._use_raw_cb.blockSignals(True)
        self._use_raw_cb.setChecked(False)
        self._use_raw_cb.blockSignals(False)

    def _sync_chain_sep_visibility(self):
        val = self._chain_cb.currentData()
        visible = should_show_chain_separator(val)
        self._chain_sep_lbl.setVisible(visible)
        self._chain_sep_edit.setVisible(visible)

    def _toggle_expert_hatch(self):
        vis = not self._expert_frame.isVisible()
        self._expert_frame.setVisible(vis)
        self._expert_toggle.setText(build_expert_toggle_text(vis))

    def _on_use_raw_toggled(self, checked: bool):
        if self._is_syncing_ui:
            return
        self._apply_editor_enable_state(
            build_editor_enable_state(
                is_custom_mode=self._is_custom_mode,
                use_raw_template=checked,
            )
        )
        if checked:
            self._on_raw_template_edited(self._raw_template_edit.text())
        else:
            self._on_editor_changed()

    # ━━ 4. 非编号标题 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_non_numbered_section(self) -> None:
        t = get_theme()

        self._main_layout.addWidget(self._build_non_numbered_toggle_button(t))
        self._main_layout.addWidget(self._build_non_numbered_content_frame(t))

    def _build_non_numbered_toggle_button(self, theme) -> QPushButton:
        self._nn_toggle = QPushButton(build_non_numbered_toggle_text(False))
        self._nn_toggle.setObjectName("hn_section_toggle")
        self._nn_toggle.setFixedHeight(theme.control_height_md)
        self._nn_toggle.setFlat(True)
        self._nn_toggle.setCursor(Qt.PointingHandCursor)
        self._nn_toggle.clicked.connect(self._toggle_non_numbered)
        return self._nn_toggle

    def _build_non_numbered_content_frame(self, theme) -> QFrame:
        self._nn_frame = QFrame()
        self._nn_frame.setObjectName("hn_nn_frame")
        nn_layout = QVBoxLayout(self._nn_frame)
        nn_layout.setContentsMargins(16, 12, 16, 12)
        nn_layout.setSpacing(8)

        self._build_non_numbered_texts_input(nn_layout, theme)
        nn_layout.addSpacing(4)
        self._build_non_numbered_prefix_input(nn_layout, theme)

        self._nn_frame.setVisible(False)
        return self._nn_frame

    def _build_non_numbered_texts_input(self, layout: QVBoxLayout, theme) -> None:
        layout.addWidget(self._small_label("跳过包含以下完整文本的标题 (使用逗号分隔):"))
        self._nn_texts_edit = QLineEdit()
        self._nn_texts_edit.setFixedHeight(theme.control_height_md)
        self._nn_texts_edit.setPlaceholderText("如: 参考文献, 致谢, 摘要")
        layout.addWidget(self._nn_texts_edit)

    def _build_non_numbered_prefix_input(self, layout: QVBoxLayout, theme) -> None:
        layout.addWidget(self._small_label("跳过以此文本开头的标题 (使用逗号分隔):"))
        self._nn_prefix_edit = QLineEdit()
        self._nn_prefix_edit.setFixedHeight(theme.control_height_md)
        self._nn_prefix_edit.setPlaceholderText("如: 附录, 附件, Appendix")
        layout.addWidget(self._nn_prefix_edit)

    def _toggle_non_numbered(self) -> None:
        vis = not self._nn_frame.isVisible()
        self._nn_frame.setVisible(vis)
        self._nn_toggle.setText(build_non_numbered_toggle_text(vis))

    def _sync_non_numbered_ui(self) -> None:
        if not self._adapter.has_template: return
        self._nn_texts_edit.blockSignals(True)
        self._nn_texts_edit.setText(format_csv_items(self._adapter.get_non_numbered_texts()))
        self._nn_texts_edit.blockSignals(False)
        
        self._nn_prefix_edit.blockSignals(True)
        self._nn_prefix_edit.setText(format_csv_items(self._adapter.get_non_numbered_prefixes()))
        self._nn_prefix_edit.blockSignals(False)

    # ━━ 逻辑: 数据更新与交互 ━━━━━━━━━━━━━━━━━━━━━━━

    def _switch_mode(self, mode: int) -> None:
        self._current_mode = mode
        if mode == _MODE_SIMPLE:
            self._mode_btn_simple.setChecked(True)
            self._mode_btn_adv.setChecked(False)
            self._stack.setCurrentWidget(self._simple_widget)
        else:
            self._mode_btn_simple.setChecked(False)
            self._mode_btn_adv.setChecked(True)
            self._stack.setCurrentWidget(self._advanced_widget)
            self._rebuild_advanced_list()

    def _on_levels_changed(self, value: int) -> None:
        self._sync_levels_display(value)
        if self._adapter.has_template:
            self._adapter.set_max_levels(value)
            self._mark_dirty()
            self._refresh_views()

    def _sync_levels_display(self, value: int) -> None:
        self._levels_value_label.setText(f"{value} 级")

    def _on_preset_changed(self, index: int) -> None:
        key = self._preset_cb.itemData(index)
        if not key or not self._adapter.has_template:
            return
            
        if key == "__custom__":
            self._is_custom_mode = True
        else:
            self._is_custom_mode = False
            self._adapter.apply_preset(key)
            
        self._sync_lock_state()
        self._refresh_views()
        
    def _sync_lock_state(self) -> None:
        """Lock or unlock configuration fields based on whether Custom mode is active.
        
        锁定范围: 仅锁定“编号格式参数”。
        永远开放: TOC 勾选 (SPEC: 所有模式可编辑), 最大级数, 非编号例外。
        """
        self._apply_editor_enable_state(
            build_editor_enable_state(
                is_custom_mode=self._is_custom_mode,
                use_raw_template=self._use_raw_cb.isChecked(),
            )
        )

    def _on_level_enabled_changed(self, level: int, checked: bool) -> None:
        if self._adapter.has_template:
            self._adapter.set_binding_field(level, "enabled", checked)
            self._refresh_views()

    def _on_toc_changed(self, level: int, checked: bool) -> None:
        if self._adapter.has_template:
            self._adapter.set_binding_field(level, "include_in_toc", checked)
            self._mark_dirty()
            
    def _on_detail_toc_changed(self, checked: bool) -> None:
        if self._is_syncing_ui: return
        self._adapter.set_binding_field(self._selected_adv_level, "include_in_toc", checked)
        self._mark_dirty()

    def _on_editor_changed(self):
        if self._is_syncing_ui: return
        prefix = self._prefix_edit.text()
        suffix = self._suffix_edit.text()
        core_key = self._core_style_cb.currentData()  # 已经是 core_style key
        tmpl = compose_display_template(prefix, core_key, suffix)
        
        self._adapter.set_binding_field(self._selected_adv_level, "display_template", tmpl)
        self._adapter.set_binding_field(self._selected_adv_level, "display_core_style", core_key)
        
        self._raw_template_edit.setText(tmpl)
        self._mark_dirty()
        self._rebuild_advanced_list()

    def _on_raw_template_edited(self, text: str):
        if self._is_syncing_ui: return
        self._adapter.set_binding_field(self._selected_adv_level, "display_template", text)
        self._mark_dirty()
        self._rebuild_advanced_list()

    def _on_chain_selected(self):
        if self._is_syncing_ui: return
        val = self._chain_cb.currentData()
        self._adapter.set_binding_field(self._selected_adv_level, "chain", val)
        self._sync_chain_sep_visibility()
        self._mark_dirty()
        self._rebuild_advanced_list()
        
    def _on_chain_sep_edited(self, text: str):
        if self._is_syncing_ui: return
        self._adapter.set_binding_field(self._selected_adv_level, "chain_separator", text)
        self._mark_dirty()
        self._rebuild_advanced_list()

    def _on_ref_style_edited(self):
        if self._is_syncing_ui: return
        core_key = self._ref_style_cb.currentData()  # 已经是 core_style key
        self._adapter.set_binding_field(self._selected_adv_level, "reference_core_style", core_key)
        self._mark_dirty()
        
    def _on_title_sep_edited(self, text: str):
        if self._is_syncing_ui: return
        self._adapter.set_binding_field(self._selected_adv_level, "title_separator", text)
        self._mark_dirty()

    def _on_nn_texts_changed(self, text: str) -> None:
        if self._adapter.has_template:
            items = parse_csv_items(text)
            self._adapter.set_non_numbered_texts(items)
            self._mark_dirty()

    def _on_nn_prefix_changed(self, text: str) -> None:
        if self._adapter.has_template:
            items = parse_csv_items(text)
            self._adapter.set_non_numbered_prefixes(items)
            self._mark_dirty()

    def _mark_dirty(self):
        # We don't magically switch the combobox to Custom anymore.
        # The user MUST have already selected Custom to edit and make it dirty,
        # because the UI locks them out otherwise!
        pass

    def _refresh_views(self) -> None:
        if self._current_mode == _MODE_SIMPLE:
            self._rebuild_simple_preview()
        else:
            self._rebuild_advanced_list()

    def _sync_preset_display(self) -> None:
        if not self._adapter.has_template:
            return
        key = self._adapter.detect_active_preset()
        
        self._preset_cb.blockSignals(True)
        if key:
            self._is_custom_mode = False
            for i in range(self._preset_cb.count()):
                if self._preset_cb.itemData(i) == key:
                    self._preset_cb.setCurrentIndex(i)
                    break
        else:
            self._is_custom_mode = True
            self._preset_cb.setCurrentIndex(self._preset_cb.count() - 1) # Custom
            
        self._preset_cb.blockSignals(False)
        self._sync_lock_state()

    # ━━ 生命周期 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _connect_signals(self) -> None:
        self.bridge.template_changed.connect(self.on_template_changed)
        self._levels_slider.valueChanged.connect(self._on_levels_changed)
        self._preset_cb.currentIndexChanged.connect(self._on_preset_changed)
        self._nn_texts_edit.textChanged.connect(self._on_nn_texts_changed)
        self._nn_prefix_edit.textChanged.connect(self._on_nn_prefix_changed)

    def on_template_changed(self, template) -> None:
        self._adapter.set_template(template)
        self._levels_slider.blockSignals(True)
        self._levels_slider.setValue(max(1, min(self._adapter.max_levels, 8)))
        self._levels_slider.blockSignals(False)
        self._sync_levels_display(self._adapter.max_levels)
        self._sync_preset_display()
        self._rebuild_simple_preview()
        self._rebuild_advanced_list()
        self._sync_non_numbered_ui()

    # ━━ 样式引擎 (Professional QSS) ━━━━━━━━━━━━━━

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("hn_label")
        return lbl
        
    @staticmethod
    def _form_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("hn_form_label")
        return lbl

    @staticmethod
    def _small_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("hn_small_label")
        return lbl

    def _apply_editor_enable_state(self, state) -> None:
        self._prefix_edit.setEnabled(state.prefix)
        self._core_style_cb.setEnabled(state.core_style)
        self._suffix_edit.setEnabled(state.suffix)
        self._chain_cb.setEnabled(state.chain)
        self._chain_sep_edit.setEnabled(state.chain_separator)
        self._ref_style_cb.setEnabled(state.reference_core_style)
        self._title_sep_edit.setEnabled(state.title_separator)
        self._use_raw_cb.setEnabled(state.use_raw_toggle)
        self._raw_template_edit.setEnabled(state.raw_template)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet(build_heading_numbering_panel_stylesheet(t))

# ── 工具函数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _set_disabled_visual(widget, muted: bool, *, strikeout: bool = False) -> None:
    widget.setProperty("muted", muted)
    font = widget.font()
    font.setStrikeOut(muted and strikeout)
    widget.setFont(font)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.blockSignals(True)
            w.setParent(None)

def _select(combo: StyledComboBox, value) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return

