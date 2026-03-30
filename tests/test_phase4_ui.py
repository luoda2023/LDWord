"""
Phase 4 冒烟测试 — UI 控件层 (19 个)

注: PyQt5 控件无法在无头环境实例化，仅测试导入。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── Helper 函数（返回类列表，供 test_all_unique 使用）──

def _get_atomic_classes():
    from src.shared.ui.themed_radio_button import ThemedRadioButton
    from src.shared.ui.themed_slider import ThemedSlider
    from src.shared.ui.toggle_switch import ToggleSwitch
    from src.shared.ui.icon_button import IconButton
    from src.shared.ui.search_input import SearchInput
    from src.shared.ui.status_indicator import StatusIndicator
    from src.shared.ui.confirm_dialog import ConfirmDialog
    from src.shared.ui.form_row import FormRow
    return [
        ThemedRadioButton,
        ThemedSlider,
        ToggleSwitch,
        IconButton,
        SearchInput,
        StatusIndicator,
        ConfirmDialog,
        FormRow,
    ]


def _get_layout_classes():
    from src.shared.ui.collapsible_section import CollapsibleSection
    from src.shared.ui.card import Card
    return [CollapsibleSection, Card]


def _get_domain_classes():
    from src.shared.ui.font_combo import FontCombo
    from src.shared.ui.size_combo import SizeCombo
    from src.shared.ui.color_picker import ColorPicker
    from src.shared.ui.spacing_input import SpacingInput
    from src.shared.ui.folder_picker import FolderPicker
    from src.shared.ui.placeholder_edit import PlaceholderEdit
    from src.shared.ui.override_badge import OverrideBadge
    from src.shared.ui.numbering_preset import NumberingPreset
    from src.shared.ui.module_step_list import ModuleStepList
    from src.shared.ui.progress_indicator import ProgressIndicator
    from src.shared.ui.style_preview import StylePreview
    return [
        FontCombo, SizeCombo, ColorPicker, SpacingInput, FolderPicker,
        PlaceholderEdit, OverrideBadge, NumberingPreset, ModuleStepList,
        ProgressIndicator, StylePreview,
    ]


# ── Test 函数（不返回值，避免 pytest warning）──

def test_atomic_imports():
    """原子层 6 个控件导入"""
    classes = _get_atomic_classes()
    assert len(classes) == 8


def test_layout_imports():
    """布局层 2 个控件导入"""
    classes = _get_layout_classes()
    assert len(classes) == 2


def test_domain_imports():
    """领域层 11 个控件导入"""
    classes = _get_domain_classes()
    assert len(classes) == 11


def test_all_unique():
    """验证 21 个控件类名唯一"""
    all_classes = _get_atomic_classes() + _get_layout_classes() + _get_domain_classes()
    names = [cls.__name__ for cls in all_classes]
    assert len(names) == 21, f"期望 21 个, 实际 {len(names)}"
    assert len(set(names)) == 21, f"类名重复: {names}"


if __name__ == "__main__":
    print("Phase 4 冒烟测试 — 🎨 UI 控件层")
    print("=" * 50)

    test_all_unique()

    print("=" * 50)
    print("✅ UI 控件层 19 个控件全部导入通过！")
