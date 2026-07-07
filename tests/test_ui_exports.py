import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui import (
    Badge,
    DetailSummaryCard,
    DetailSummaryHeader,
    DynamicNavigationRail,
    ExecutionFeedbackWidget,
    FeatureToggleRow,
    FileDropZone,
    FontCombo,
    GlobalTooltipController,
    FlowSection,
    InspectorForm,
    LogStreamWidget,
    ModuleStatusList,
    NavigationCard,
    NumberingPreset,
    OptionToggleChip,
    SearchInput,
    SizeCombo,
    StyleDifferenceSummarySlot,
    StyleManagementContentPlan,
    StyleObjectProjection,
    StylePresentationEnvelope,
    StylePolicyActionProjection,
    StylePolicyControlDeck,
    StylePolicyProjection,
    StylePolicyToggleList,
    StylePolicyToggleOption,
    StylePolicyToggleProjection,
    style_policy_control_protocol,
    StylePreviewSurface,
    StyleReceiptSlotFrame,
    StyleSourceSlot,
    style_management_content_plan,
    style_preview_renderer_protocol,
    style_preview_slot_protocol,
    StyledComboBox,
    TemplateFormGrid,
    TemplateSplitColumns,
    ThemedRadioButton,
    ThemedSlider,
    apply_detail_summary_action_button,
    apply_button_variant,
    build_button_stylesheet,
    build_checkbox_stylesheet,
    install_global_tooltip,
    set_global_tooltip,
    template_form_row,
    tooltip_position_for,
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
    assert DetailSummaryCard.__name__ == "DetailSummaryCard"
    assert DetailSummaryHeader.__name__ == "DetailSummaryHeader"
    assert NavigationCard.__name__ == "NavigationCard"
    assert OptionToggleChip.__name__ == "OptionToggleChip"
    assert InspectorForm.__name__ == "InspectorForm"
    assert DynamicNavigationRail.__name__ == "DynamicNavigationRail"
    assert GlobalTooltipController.__name__ == "GlobalTooltipController"
    assert ExecutionFeedbackWidget.__name__ == "ExecutionFeedbackWidget"
    assert StyleDifferenceSummarySlot.__name__ == "StyleDifferenceSummarySlot"
    assert StyleManagementContentPlan.__name__ == "StyleManagementContentPlan"
    assert StyleObjectProjection.__name__ == "StyleObjectProjection"
    assert StylePresentationEnvelope.__name__ == "StylePresentationEnvelope"
    assert StylePolicyActionProjection.__name__ == "StylePolicyActionProjection"
    assert StylePolicyControlDeck.__name__ == "StylePolicyControlDeck"
    assert StylePolicyProjection.__name__ == "StylePolicyProjection"
    assert style_policy_control_protocol(None) == "none"
    assert StylePolicyToggleList.__name__ == "StylePolicyToggleList"
    assert StylePolicyToggleOption.__name__ == "StylePolicyToggleOption"
    assert StylePolicyToggleProjection.__name__ == "StylePolicyToggleProjection"
    assert StylePreviewSurface.__name__ == "StylePreviewSurface"
    assert StyleReceiptSlotFrame.__name__ == "StyleReceiptSlotFrame"
    assert StyleSourceSlot.__name__ == "StyleSourceSlot"
    assert style_management_content_plan("template_baseline_edit").sections() == (
        "source",
        "scope",
        "editor",
    )
    assert style_management_content_plan("template_overview_preview").sections() == (
        "preview",
    )
    assert style_management_content_plan("execution_receipt_review").sections() == (
        "receipt",
    )
    assert style_preview_slot_protocol(None) == "none"
    assert style_preview_renderer_protocol(None) == "none"
    assert FlowSection.__name__ == "FlowSection"
    assert FileDropZone.__name__ == "FileDropZone"
    assert FeatureToggleRow.__name__ == "FeatureToggleRow"
    assert ModuleStatusList.__name__ == "ModuleStatusList"
    assert LogStreamWidget.__name__ == "LogStreamWidget"
    assert callable(apply_detail_summary_action_button)
    assert callable(apply_button_variant)
    assert callable(build_button_stylesheet)
    assert callable(build_checkbox_stylesheet)
    assert callable(install_global_tooltip)
    assert callable(set_global_tooltip)
    assert callable(template_form_row)
    assert callable(tooltip_position_for)
