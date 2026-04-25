"""Tests for heading numbering logic + panel architecture after refactoring.

Tests are grouped into:
  1. Pure logic tests (heading_numbering_logic.py) — unchanged from before.
  2. Adapter capability tests — new per-level override/inherit helpers.
  3. Panel architecture tests — verify the new fixed-layout structure.
"""

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.adapters.heading_numbering_adapter import HeadingNumberingAdapter
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Pure logic tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

    # Parameter renamed: is_custom_mode → is_binding_overridden
    locked = build_editor_enable_state(is_binding_overridden=False, use_raw_template=False)
    assert all(value is False for value in locked.__dict__.values())

    custom_plain = build_editor_enable_state(is_binding_overridden=True, use_raw_template=False)
    assert custom_plain.prefix is True
    assert custom_plain.core_style is True
    assert custom_plain.suffix is True
    assert custom_plain.chain is True
    assert custom_plain.chain_separator is True
    assert custom_plain.reference_core_style is True
    assert custom_plain.title_separator is True
    assert custom_plain.use_raw_toggle is True
    assert custom_plain.raw_template is False

    custom_raw = build_editor_enable_state(is_binding_overridden=True, use_raw_template=True)
    assert custom_raw.prefix is False
    assert custom_raw.core_style is False
    assert custom_raw.suffix is False
    assert custom_raw.chain is True
    assert custom_raw.chain_separator is True
    assert custom_raw.reference_core_style is True
    assert custom_raw.title_separator is True
    assert custom_raw.use_raw_toggle is True
    assert custom_raw.raw_template is True

    assert build_expert_toggle_text(False) == "▾ 展开表达式编辑"
    assert build_expert_toggle_text(True) == "▴ 收起表达式编辑"
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
    assert "should_show_chain_separator" in panel_source
    assert "parse_csv_items" in panel_source
    assert "format_csv_items" in panel_source

    assert "from src.ui.heading_numbering_logic import" in adapter_module_source
    assert "default_chain_value" in adapter_source

    assert "STYLE_OPTIONS" in helper_source
    assert "def compose_display_template" in helper_source
    assert "def split_display_template" in helper_source
    assert "def default_chain_value" in helper_source
    assert "def build_chain_options" in helper_source
    assert "def build_detail_state" in helper_source
    assert "def build_editor_enable_state" in helper_source
    assert "def should_show_chain_separator" in helper_source
    assert "def parse_csv_items" in helper_source
    assert "def format_csv_items" in helper_source


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. New panel architecture tests (fixed three-section layout)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_panel_has_fixed_three_section_layout():
    """Panel must have summary, scheme, level-editor, and nn sections — no QStackedWidget."""
    panel_source = inspect.getsource(HeadingNumberingPanel)
    module_source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    # Must have these four sections
    assert "_build_summary_card" in panel_source
    assert "_build_scheme_section" in panel_source
    assert "_build_level_editor" in panel_source
    assert "_build_non_numbered_section" in panel_source

    # Must NOT have old mode-switching infrastructure
    assert "QStackedWidget" not in module_source
    assert "_MODE_SIMPLE" not in module_source
    assert "_MODE_ADVANCED" not in module_source
    assert "_is_custom_mode" not in module_source
    assert "_mode_segment" not in module_source
    assert "_format_jump_btn" not in module_source
    assert "_activate_custom_mode" not in module_source
    assert "_activate_preset_mode" not in module_source


def test_panel_has_inspector_structure_without_override_actions():
    """Panel should use inspector summaries + expandable detail areas, not override actions."""
    panel_source = inspect.getsource(HeadingNumberingPanel)

    # Old override/inherit elements must be absent
    assert "_numbering_source_label" not in panel_source
    assert "_numbering_action_btn" not in panel_source
    assert "_numbering_inherit_summary" not in panel_source
    assert "_on_numbering_action_clicked" not in panel_source
    assert "_style_action_btn" not in panel_source
    assert "_style_inherit_summary" not in panel_source
    assert "_on_style_action_clicked" not in panel_source

    # Inspector structure should be present
    assert "_build_detail_panel_inspector" in panel_source
    assert "_build_result_strip" in panel_source
    assert "_build_numbering_block" in panel_source
    assert "_build_output_block" in panel_source
    assert "_build_style_inspector" in panel_source
    assert "_build_expert_inspector" in panel_source
    assert "_style_toggle_btn" in panel_source
    assert "_expert_toggle_btn" in panel_source


def test_panel_no_minipage_preview():
    """MiniPagePreview should have been removed."""
    module_source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    assert "_HeadingMiniPagePreview" not in module_source
    assert "_ClickablePreviewRow" not in module_source
    assert "_page_preview" not in module_source


def test_panel_uses_inline_preview_in_format_card():
    """InlineHeadingPreview should exist inside the heading format card."""
    panel_source = inspect.getsource(HeadingNumberingPanel)

    assert "_InlineHeadingPreview" in panel_source or "_inline_preview" in panel_source
    assert "_refresh_inline_preview" in panel_source


def test_panel_sidebar_is_pure_navigation():
    """Sidebar should not have per-level enable/disable checkboxes."""
    panel_source = inspect.getsource(HeadingNumberingPanel)
    module_source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    # Enable toggle is in the numbering card, not in sidebar
    assert "_level_enabled_switch" in panel_source
    assert "_build_level_row" in panel_source

    # Sidebar row builder should not create checkboxes
    row_source = inspect.getsource(HeadingNumberingPanel._build_level_row)
    assert "QCheckBox" not in row_source


def test_adapter_has_per_level_override_methods():
    """Adapter must expose per-level override query/mutation methods."""
    adapter_source = inspect.getsource(HeadingNumberingAdapter)

    assert "def has_heading_style_override" in adapter_source
    assert "def remove_heading_style_override" in adapter_source
    assert "def is_level_binding_from_preset" in adapter_source
    assert "def reset_level_binding_to_preset" in adapter_source
    assert "def numbering_source_text" in adapter_source
    assert "_last_applied_preset_key" in adapter_source


def test_heading_style_semantics_has_remove():
    """heading_style_semantics module must export remove_heading_style_override."""
    from src.config.heading_style_semantics import (
        ensure_heading_style_override,
        remove_heading_style_override,
        resolve_heading_style,
        resolve_heading_style_source,
    )

    assert callable(remove_heading_style_override)
