import inspect
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def test_heading_numbering_logic_module_exposes_pure_template_chain_and_state_helpers():
    from src.ui.heading_numbering_logic import (
        STYLE_OPTIONS,
        build_chain_options,
        build_detail_state,
        build_editor_enable_state,
        build_expert_toggle_text,
        build_non_numbered_toggle_text,
        compose_display_template,
        default_chain_value,
        format_csv_items,
        parse_csv_items,
        should_show_chain_separator,
        split_display_template,
    )

    assert STYLE_OPTIONS
    assert split_display_template("第{cn}章") == ("第", "chinese_lower", "章")
    assert split_display_template("") == ("", "arabic", "")
    assert compose_display_template("第", "roman_upper", "章") == "第{RN}章"
    assert compose_display_template("", "arabic", "") == "{nn}"

    assert default_chain_value(1) == "current_only"
    assert default_chain_value(2) == "parent.current"
    assert default_chain_value(3) == "parent.parent.current"

    assert build_chain_options(1) == [("不包含 (仅显示当前级别)", "current_only")]
    assert build_chain_options(2) == [
        ("不包含 (仅显示当前级别)", "current_only"),
        ("包含上一级 (如 1.1)", "parent.current"),
    ]
    assert build_chain_options(3) == [
        ("不包含 (仅显示当前级别)", "current_only"),
        ("包含上一级 (如 1.1)", "parent.current"),
        ("包含所有上级 (如 1.1.1)", "parent.parent.current"),
    ]

    state = build_detail_state(
        2,
        SimpleNamespace(
            display_template="第{cn}章",
            include_in_toc=False,
            chain="parent.current",
            chain_separator="-",
            reference_core_style="roman_upper",
            title_separator="　",
        ),
    )
    assert state.title == "级别 2 编号设置"
    assert state.raw_template == "第{cn}章"
    assert state.prefix == "第"
    assert state.core_style == "chinese_lower"
    assert state.suffix == "章"
    assert state.include_in_toc is False
    assert state.chain_options == build_chain_options(2)
    assert state.chain_value == "parent.current"
    assert state.chain_separator == "-"
    assert state.reference_core_style == "roman_upper"
    assert state.title_separator == "　"

    assert should_show_chain_separator("current_only") is False
    assert should_show_chain_separator("parent.current") is True
    assert parse_csv_items(" 参考文献, 致谢 ,, 摘要 ") == ["参考文献", "致谢", "摘要"]
    assert format_csv_items(["参考文献", "致谢", "摘要"]) == "参考文献, 致谢, 摘要"
    assert format_csv_items([]) == ""

    locked = build_editor_enable_state(is_custom_mode=False, use_raw_template=False)
    assert all(value is False for value in locked.__dict__.values())

    custom_plain = build_editor_enable_state(is_custom_mode=True, use_raw_template=False)
    assert custom_plain.prefix is True
    assert custom_plain.core_style is True
    assert custom_plain.suffix is True
    assert custom_plain.chain is True
    assert custom_plain.chain_separator is True
    assert custom_plain.reference_core_style is True
    assert custom_plain.title_separator is True
    assert custom_plain.use_raw_toggle is True
    assert custom_plain.raw_template is False

    custom_raw = build_editor_enable_state(is_custom_mode=True, use_raw_template=True)
    assert custom_raw.prefix is False
    assert custom_raw.core_style is False
    assert custom_raw.suffix is False
    assert custom_raw.chain is True
    assert custom_raw.chain_separator is True
    assert custom_raw.reference_core_style is True
    assert custom_raw.title_separator is True
    assert custom_raw.use_raw_toggle is True
    assert custom_raw.raw_template is True

    assert build_expert_toggle_text(False) == "▾ 显示更多高级选项"
    assert build_expert_toggle_text(True) == "▴ 隐藏高级选项"
    assert build_non_numbered_toggle_text(False) == "▸ 非编号标题 (忽略以下列表中的内容)"
    assert build_non_numbered_toggle_text(True) == "▾ 非编号标题 (忽略以下列表中的内容)"


def test_panel_and_adapter_delegate_heading_numbering_pure_logic_to_shared_module():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    adapter_source = inspect.getsource(HeadingNumberingAdapter)
    panel_module_source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")
    adapter_module_source = (ROOT / "src/ui/adapters/heading_numbering_adapter.py").read_text(encoding="utf-8")
    helper_source = (ROOT / "src/ui/heading_numbering_logic.py").read_text(encoding="utf-8")

    assert "from src.ui.heading_numbering_logic import" in panel_module_source
    assert "compose_display_template" in panel_source
    assert "build_detail_state" in panel_source
    assert "build_editor_enable_state" in panel_source
    assert "build_expert_toggle_text" in panel_source
    assert "build_non_numbered_toggle_text" in panel_source
    assert "should_show_chain_separator" in panel_source
    assert "parse_csv_items" in panel_source
    assert "format_csv_items" in panel_source
    assert "_CORE_TO_PH" not in panel_source
    assert "_PH_TO_CORE" not in panel_source
    assert "def _split_template" not in panel_source
    assert 'text.split(",")' not in panel_source
    assert '", ".join(' not in panel_source
    assert '!= "current_only"' not in panel_source
    assert '.setEnabled(not checked)' not in panel_source
    assert '.setEnabled(is_custom)' not in panel_source
    assert 'if is_custom and not self._use_raw_cb.isChecked()' not in panel_source
    assert '显示更多高级选项" if not vis else "▴ 隐藏高级选项"' not in panel_source
    assert '"▾" if vis else "▸"' not in panel_source

    assert "from src.ui.heading_numbering_logic import" in adapter_module_source
    assert "default_chain_value" in adapter_source
    assert '".join(["parent"] * (lv - 1)) + ".current"' not in adapter_source

    assert "STYLE_OPTIONS" in helper_source
    assert "def compose_display_template" in helper_source
    assert "def split_display_template" in helper_source
    assert "def default_chain_value" in helper_source
    assert "def build_chain_options" in helper_source
    assert "def build_detail_state" in helper_source
    assert "def build_editor_enable_state" in helper_source
    assert "def build_expert_toggle_text" in helper_source
    assert "def build_non_numbered_toggle_text" in helper_source
    assert "def should_show_chain_separator" in helper_source
    assert "def parse_csv_items" in helper_source
    assert "def format_csv_items" in helper_source


def test_heading_numbering_panel_decomposes_professional_editor_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    editor_builder_source = inspect.getsource(HeadingNumberingPanel._build_professional_editor)

    assert "def _build_editor_number_style_row" in panel_source
    assert "def _build_editor_affix_row" in panel_source
    assert "def _build_editor_chain_row" in panel_source
    assert "def _build_editor_toc_row" in panel_source
    assert "def _build_editor_expert_section" in panel_source

    assert "self._build_editor_number_style_row" in editor_builder_source
    assert "self._build_editor_affix_row" in editor_builder_source
    assert "self._build_editor_chain_row" in editor_builder_source
    assert "self._build_editor_toc_row" in editor_builder_source
    assert "self._build_editor_expert_section" in editor_builder_source

    assert "StyledComboBox()" not in editor_builder_source
    assert 'QCheckBox("此级别在目录中显示")' not in editor_builder_source


def test_heading_numbering_panel_further_decomposes_professional_editor_shell():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    editor_builder_source = inspect.getsource(HeadingNumberingPanel._build_professional_editor)

    assert "def _build_editor_detail_header" in panel_source
    assert "def _build_editor_form_container" in panel_source
    assert "def _build_editor_divider" in panel_source

    assert "self._build_editor_detail_header" in editor_builder_source
    assert "self._build_editor_form_container" in editor_builder_source
    assert "self._build_editor_divider" in editor_builder_source

    assert 'QLabel("级别配置")' not in editor_builder_source
    assert "QWidget()" not in editor_builder_source
    assert "QFrame()" not in editor_builder_source


def test_heading_numbering_panel_decomposes_detail_sync_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    detail_sync_source = inspect.getsource(HeadingNumberingPanel._sync_detail_pane)

    assert "def _sync_detail_basic_fields" in panel_source
    assert "def _sync_detail_chain_fields" in panel_source
    assert "def _sync_detail_advanced_fields" in panel_source
    assert "def _reset_detail_raw_toggle" in panel_source

    assert "self._sync_detail_basic_fields" in detail_sync_source
    assert "self._sync_detail_chain_fields" in detail_sync_source
    assert "self._sync_detail_advanced_fields" in detail_sync_source
    assert "self._reset_detail_raw_toggle" in detail_sync_source

    assert "self._chain_cb.clear()" not in detail_sync_source
    assert "self._use_raw_cb.setChecked(False)" not in detail_sync_source


def test_heading_numbering_panel_decomposes_advanced_list_rebuild_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    rebuild_source = inspect.getsource(HeadingNumberingPanel._rebuild_advanced_list)

    assert "def _append_advanced_level_item" in panel_source
    assert "def _build_advanced_level_row" in panel_source
    assert "def _sync_advanced_list_current_row" in panel_source

    assert "self._append_advanced_level_item" in rebuild_source
    assert "self._sync_advanced_list_current_row" in rebuild_source

    assert "QListWidgetItem()" not in rebuild_source
    assert "QCheckBox()" not in rebuild_source


def test_heading_numbering_panel_source_keeps_readable_utf8_literals():
    panel_module_source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    assert 'QLabel("级别配置")' in panel_module_source
    assert 'QCheckBox("此级别在目录中显示")' in panel_module_source
    assert 'QPushButton("▸ 显示更多高级选项")' in panel_module_source
    assert 'self._small_label("作为被引用的父级时显示形式:")' in panel_module_source
    assert 'self._small_label("编号后跟随的缩进字符:")' in panel_module_source
    assert 'QCheckBox("覆盖上方逻辑，直接编辑原始编号字符串模式")' in panel_module_source
    assert 'QLabel(f"级别 {level}")' in panel_module_source
    assert '"—"' in panel_module_source


def test_heading_numbering_panel_decomposes_simple_preview_rebuild_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    preview_source = inspect.getsource(HeadingNumberingPanel._rebuild_simple_preview)

    assert "def _append_simple_preview_row" in panel_source
    assert "def _build_simple_preview_row" in panel_source
    assert "def _apply_simple_preview_disabled_state" in panel_source

    assert "self._append_simple_preview_row" in preview_source

    assert 'QCheckBox("生成到 TOC 目录")' not in preview_source
    assert 'QFrame()' not in preview_source


def test_heading_numbering_panel_decomposes_expert_section_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    expert_builder_source = inspect.getsource(HeadingNumberingPanel._build_editor_expert_section)

    assert "def _build_editor_reference_style_row" in panel_source
    assert "def _build_editor_title_separator_row" in panel_source
    assert "def _build_editor_raw_template_row" in panel_source

    assert "self._build_editor_reference_style_row" in expert_builder_source
    assert "self._build_editor_title_separator_row" in expert_builder_source
    assert "self._build_editor_raw_template_row" in expert_builder_source

    assert 'QCheckBox("覆盖上方逻辑，直接编辑原始编号字符串模式")' not in expert_builder_source
    assert 'self._small_label("作为被引用的父级时显示形式:")' not in expert_builder_source


def test_heading_numbering_panel_decomposes_advanced_view_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    advanced_view_source = inspect.getsource(HeadingNumberingPanel._build_advanced_view)

    assert "def _build_advanced_list_sidebar" in panel_source
    assert "def _build_advanced_detail_panel" in panel_source

    assert "self._build_advanced_list_sidebar" in advanced_view_source
    assert "self._build_advanced_detail_panel" in advanced_view_source
    assert "get_theme()" in advanced_view_source

    assert 'QLabel("要修改的级别")' not in advanced_view_source
    assert 'self._build_professional_editor(self._adv_detail_layout)' not in advanced_view_source


def test_heading_numbering_panel_decomposes_preset_header_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    preset_header_source = inspect.getsource(HeadingNumberingPanel._build_preset_header)

    assert "def _build_preset_selector_group" in panel_source
    assert "def _build_levels_selector_group" in panel_source

    assert "self._build_preset_selector_group" in preset_header_source
    assert "self._build_levels_selector_group" in preset_header_source

    assert 'self._label("编号库 (预设):")' not in preset_header_source
    assert 'self._label("控制最大级数:")' not in preset_header_source


def test_heading_numbering_panel_decomposes_mode_switcher_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    mode_switcher_source = inspect.getsource(HeadingNumberingPanel._build_mode_switcher)
    panel_module_source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    assert "def _build_mode_button_container" in panel_source
    assert "def _build_mode_buttons" in panel_source

    assert "self._build_mode_button_container" in mode_switcher_source
    assert "self._build_mode_buttons" in mode_switcher_source
    assert "ThemedRadioButton" in panel_module_source

    assert 'QPushButton("快速应用")' not in mode_switcher_source
    assert 'QPushButton("自定义多级列表")' not in mode_switcher_source


def test_heading_numbering_panel_decomposes_simple_preview_row_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    preview_row_source = inspect.getsource(HeadingNumberingPanel._build_simple_preview_row)

    assert "def _build_simple_preview_labels" in panel_source
    assert "def _build_simple_preview_checkbox" in panel_source
    assert "def _layout_simple_preview_row" in panel_source

    assert "self._build_simple_preview_labels" in preview_row_source
    assert "self._build_simple_preview_checkbox" in preview_row_source
    assert "self._layout_simple_preview_row" in preview_row_source

    assert 'QCheckBox("生成到 TOC 目录")' not in preview_row_source
    assert 'QLabel("这是一个示例标题内容")' not in preview_row_source


def test_heading_numbering_panel_decomposes_non_numbered_section_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    non_numbered_source = inspect.getsource(HeadingNumberingPanel._build_non_numbered_section)

    assert "def _build_non_numbered_toggle_button" in panel_source
    assert "def _build_non_numbered_content_frame" in panel_source
    assert "def _build_non_numbered_texts_input" in panel_source
    assert "def _build_non_numbered_prefix_input" in panel_source

    assert "self._build_non_numbered_toggle_button" in non_numbered_source
    assert "self._build_non_numbered_content_frame" in non_numbered_source

    assert 'QPushButton(build_non_numbered_toggle_text(False))' not in non_numbered_source
    assert 'self._small_label("跳过包含以下完整文本的标题 (使用逗号分隔):")' not in non_numbered_source


def test_heading_numbering_panel_decomposes_setup_ui_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    setup_source = inspect.getsource(HeadingNumberingPanel._setup_ui)

    assert "def _initialize_panel_state" in panel_source
    assert "def _build_scroll_content_host" in panel_source
    assert "def _build_mode_stack_views" in panel_source

    assert "self._initialize_panel_state" in setup_source
    assert "self._build_scroll_content_host" in setup_source
    assert "self._build_mode_stack_views" in setup_source

    assert "self._adapter = HeadingNumberingAdapter(parent=self)" not in setup_source
    assert "self._stack = QStackedWidget()" not in setup_source


def test_heading_numbering_panel_decomposes_advanced_level_row_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    level_row_source = inspect.getsource(HeadingNumberingPanel._build_advanced_level_row)

    assert "def _build_advanced_level_checkbox" in panel_source
    assert "def _build_advanced_level_labels" in panel_source
    assert "def _layout_advanced_level_row" in panel_source

    assert "self._build_advanced_level_checkbox" in level_row_source
    assert "self._build_advanced_level_labels" in level_row_source
    assert "self._layout_advanced_level_row" in level_row_source

    assert "QCheckBox()" not in level_row_source
    assert 'QLabel(f"级别 {level}")' not in level_row_source


def test_heading_numbering_panel_decomposes_editor_chain_row_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    chain_row_source = inspect.getsource(HeadingNumberingPanel._build_editor_chain_row)

    assert "def _build_editor_chain_selector" in panel_source
    assert "def _build_editor_chain_separator_fields" in panel_source
    assert "def _layout_editor_chain_row" in panel_source

    assert "self._build_editor_chain_selector" in chain_row_source
    assert "self._build_editor_chain_separator_fields" in chain_row_source
    assert "self._layout_editor_chain_row" in chain_row_source

    assert "StyledComboBox()" not in chain_row_source
    assert 'self._small_label("分隔符:")' not in chain_row_source


def test_heading_numbering_panel_decomposes_editor_affix_row_build_into_small_helpers():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    affix_row_source = inspect.getsource(HeadingNumberingPanel._build_editor_affix_row)

    assert "def _build_editor_prefix_field" in panel_source
    assert "def _build_editor_suffix_field" in panel_source
    assert "def _layout_editor_affix_row" in panel_source

    assert "self._build_editor_prefix_field" in affix_row_source
    assert "self._build_editor_suffix_field" in affix_row_source
    assert "self._layout_editor_affix_row" in affix_row_source

    assert 'self._small_label("前缀:")' not in affix_row_source
    assert 'self._small_label("后缀:")' not in affix_row_source


def test_heading_numbering_panel_further_decomposes_expert_section_shell():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    expert_source = inspect.getsource(HeadingNumberingPanel._build_editor_expert_section)

    assert "def _build_editor_expert_toggle" in panel_source
    assert "def _build_editor_expert_frame" in panel_source

    assert "self._build_editor_expert_toggle" in expert_source
    assert "self._build_editor_expert_frame" in expert_source

    assert 'QPushButton("▸ 显示更多高级选项")' not in expert_source
    assert 'QFrame()' not in expert_source


def test_heading_numbering_panel_further_decomposes_detail_sync_flow():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    detail_sync_source = inspect.getsource(HeadingNumberingPanel._sync_detail_pane)

    assert "def _resolve_selected_detail_binding" in panel_source
    assert "def _finish_detail_sync" in panel_source

    assert "self._resolve_selected_detail_binding" in detail_sync_source
    assert "self._finish_detail_sync" in detail_sync_source

    assert "self._adv_list.currentItem()" not in detail_sync_source
    assert "self._sync_lock_state()" not in detail_sync_source


def test_heading_numbering_panel_further_decomposes_simple_preview_row_shell():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    preview_row_source = inspect.getsource(HeadingNumberingPanel._build_simple_preview_row)

    assert "def _build_simple_preview_row_shell" in panel_source
    assert "def _build_simple_preview_spacer" in panel_source

    assert "self._build_simple_preview_row_shell" in preview_row_source
    assert "self._build_simple_preview_spacer" in preview_row_source

    assert "QFrame()" not in preview_row_source
    assert "QWidget()" not in preview_row_source


def test_heading_numbering_panel_further_decomposes_simple_preview_row_state():
    panel_source = inspect.getsource(HeadingNumberingPanel)
    preview_row_source = inspect.getsource(HeadingNumberingPanel._build_simple_preview_row)

    assert "def _apply_simple_preview_row_state" in panel_source

    assert "self._apply_simple_preview_row_state" in preview_row_source

    assert "self._apply_simple_preview_disabled_state" not in preview_row_source
