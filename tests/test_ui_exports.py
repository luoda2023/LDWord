import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import (
    Badge,
    DynamicNavigationRail,
    ExecutionFeedbackWidget,
    FeatureToggleRow,
    FileDropZone,
    FontCombo,
    FlowSection,
    LogStreamWidget,
    ModuleStatusList,
    NavigationCard,
    NumberingPreset,
    SearchInput,
    SizeCombo,
    StyledComboBox,
    TemplateFormGrid,
    TemplateSplitColumns,
    ThemedRadioButton,
    ThemedSlider,
    apply_button_variant,
    build_button_stylesheet,
    build_checkbox_stylesheet,
    template_form_row,
)


def test_shared_ui_exports_include_unified_controls():
    assert SearchInput.__name__ == "SearchInput"
    assert StyledComboBox.__name__ == "StyledComboBox"
    assert TemplateFormGrid.__name__ == "TemplateFormGrid"
    assert TemplateSplitColumns.__name__ == "TemplateSplitColumns"
    assert FontCombo.__name__ == "FontCombo"
    assert SizeCombo.__name__ == "SizeCombo"
    assert NumberingPreset.__name__ == "NumberingPreset"
    assert ThemedRadioButton.__name__ == "ThemedRadioButton"
    assert ThemedSlider.__name__ == "ThemedSlider"
    assert Badge.__name__ == "Badge"
    assert NavigationCard.__name__ == "NavigationCard"
    assert DynamicNavigationRail.__name__ == "DynamicNavigationRail"
    assert ExecutionFeedbackWidget.__name__ == "ExecutionFeedbackWidget"
    assert FlowSection.__name__ == "FlowSection"
    assert FileDropZone.__name__ == "FileDropZone"
    assert FeatureToggleRow.__name__ == "FeatureToggleRow"
    assert ModuleStatusList.__name__ == "ModuleStatusList"
    assert LogStreamWidget.__name__ == "LogStreamWidget"
    assert callable(apply_button_variant)
    assert callable(build_button_stylesheet)
    assert callable(build_checkbox_stylesheet)
    assert callable(template_form_row)
