from __future__ import annotations

from importlib import import_module


_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "Badge": (".badge", "Badge"),
    "AdaptivePairRow": (".adaptive_pair_row", "AdaptivePairRow"),
    "CalendarMonth": (".calendar_month", "CalendarMonth"),
    "ChatBubble": (".chat_bubble", "ChatBubble"),
    "CommandPalette": (".command_palette", "CommandPalette"),
    "ConfigListWidget": (".config_list_widget", "ConfigListWidget"),
    "ContextMenu": (".context_menu", "ContextMenu"),
    "DataTable": (".data_table", "DataTable"),
    "DesignSystemCard": (".design_system_card", "DesignSystemCard"),
    "DashedSeparator": (".dashed_separator", "DashedSeparator"),
    "DatePicker": (".date_picker", "DatePicker"),
    "Descriptions": (".descriptions", "Descriptions"),
    "Divider": (".divider", "Divider"),
    "Drawer": (".drawer", "Drawer"),
    "DynamicNavigationRail": (".dynamic_navigation_rail", "DynamicNavigationRail"),
    "EmptyState": (".empty_state", "EmptyState"),
    "ExecutionFeedbackWidget": (".execution_feedback_widget", "ExecutionFeedbackWidget"),
    "ExecutionProgressWidget": (".execution_progress_widget", "ExecutionProgressWidget"),
    "FeatureToggleRow": (".feature_toggle_row", "FeatureToggleRow"),
    "FileDropZone": (".file_drop_zone", "FileDropZone"),
    "Form": (".form", "Form"),
    "FlowSection": (".flow_section", "FlowSection"),
    "FlowLayout": (".flow_layout", "FlowLayout"),
    "FontCombo": (".font_combo", "FontCombo"),
    "InlineAlert": (".inline_alert", "InlineAlert"),
    "InspectorForm": (".inspector_form", "InspectorForm"),
    "LogStreamWidget": (".log_stream_widget", "LogStreamWidget"),
    "MarkdownPreview": (".markdown_preview", "MarkdownPreview"),
    "MasterDetailShell": (".master_detail_shell", "MasterDetailShell"),
    "MessageInput": (".message_input", "MessageInput"),
    "ModuleStatusList": (".module_status_list", "ModuleStatusList"),
    "NavigationCard": (".navigation_card", "NavigationCard"),
    "NumberingPreset": (".numbering_preset", "NumberingPreset"),
    "OptionToggleChip": (".option_toggle_chip", "OptionToggleChip"),
    "Pagination": (".pagination", "Pagination"),
    "Result": (".result", "Result"),
    "SearchInput": (".search_input", "SearchInput"),
    "SegmentedControl": (".segmented_control", "SegmentedControl"),
    "SizeCombo": (".size_combo", "SizeCombo"),
    "SpacingInput": (".spacing_input", "SpacingInput"),
    "Spin": (".spin", "Spin"),
    "SplitPane": (".split_pane", "SplitPane"),
    "StyledComboBox": (".styled_combo_box", "StyledComboBox"),
    "StyledSpinBox": (".styled_spin_box", "StyledSpinBox"),
    "SummaryGrid": (".summary_grid", "SummaryGrid"),
    "SummaryGridItem": (".summary_grid", "SummaryGridItem"),
    "SurfaceCard": (".surface_card", "SurfaceCard"),
    "TabBar": (".tab_bar", "TabBar"),
    "TagChip": (".tag_chip", "TagChip"),
    "TemplateFormGrid": (".template_form_layout", "TemplateFormGrid"),
    "TemplateFormStack": (".template_form_layout", "TemplateFormStack"),
    "TemplateSplitColumns": (".template_form_layout", "TemplateSplitColumns"),
    "template_form_pair_row": (".template_form_layout", "template_form_pair_row"),
    "TextArea": (".text_area", "TextArea"),
    "ThemedRadioButton": (".themed_radio_button", "ThemedRadioButton"),
    "ThemedSlider": (".themed_slider", "ThemedSlider"),
    "Toast": (".toast", "Toast"),
    "GlobalTooltipController": (".tooltip", "GlobalTooltipController"),
    "Typography": (".typography", "Typography"),
    "TypingIndicator": (".typing_indicator", "TypingIndicator"),
    "apply_button_variant": (".button_style", "apply_button_variant"),
    "bind_theme": (".theme", "bind_theme"),
    "build_button_stylesheet": (".button_style", "build_button_stylesheet"),
    "build_checkbox_stylesheet": (".selection_control_style", "build_checkbox_stylesheet"),
    "build_text_input_stylesheet": (".input_style", "build_text_input_stylesheet"),
    "install_global_tooltip": (".tooltip", "install_global_tooltip"),
    "normalize_form_control_heights": (".sizing", "normalize_form_control_heights"),
    "resolved_control_height": (".sizing", "resolved_control_height"),
    "set_global_tooltip": (".tooltip", "set_global_tooltip"),
    "template_form_row": (".template_form_layout", "template_form_row"),
    "tooltip_position_for": (".tooltip", "tooltip_position_for"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(__all__))
