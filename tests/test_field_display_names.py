import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.adapters.field_display_names import (  # noqa: E402
    field_display_context,
    field_display_name,
    navigation_issue_hint,
    replace_field_keys_with_display_names,
)


def test_field_display_name_translates_scene_and_template_paths():
    assert (
        field_display_name("scene.section_styles.references_body.font_cn")
        == "参考文献正文中文字体"
    )
    assert field_display_name("scene.section_styles.references_body") == "参考文献正文"
    assert (
        field_display_name("scene.section_styles.*.line_spacing_pt")
        == "所有处理分区行距"
    )
    assert (
        field_display_name("format_scope.sections.references")
        == "处理范围：参考文献"
    )
    assert (
        field_display_name("template.page_setup.margin.left_cm")
        == "左页边距"
    )
    assert (
        field_display_name("template.styles.body.special_indent_mode")
        == "正文特殊缩进"
    )
    assert field_display_name("template.styles.body.bold") == "正文字形"
    assert (
        field_display_name("scene.section_styles.references_body.italic")
        == "参考文献正文字形"
    )
    assert field_display_name("input_source_profile.material_schema_id") == "主资料规则"
    assert field_display_name("filename_template") == "文件名规则"


def test_navigation_issue_hint_prefers_issue_title_and_formats_schema_ids():
    assert (
        navigation_issue_hint(
            "",
            "signature_assets_v2",
            issue_type="schema",
        )
        == "资料规则：signature_assets_v2"
    )
    assert (
        navigation_issue_hint(
            "模板字体不一致",
            "template.styles.body.font_cn",
            issue_type="template_style_field",
        )
        == "模板字体不一致"
    )


def test_field_display_context_exposes_style_layout_group_for_action_copy():
    context = field_display_context("template.styles.body.bold")

    assert context.label == "正文字形"
    assert context.group_label == "文字样式"
    assert context.label_with_group() == "文字样式：正文字形"
    assert context.raw_key == "template.styles.body.bold"
    assert context.layout_item_id == "emphasis"
    assert context.field_ids == ("bold", "italic")
    assert context.control_contract_key == ""
    assert context.diagnostic_summary() == (
        "template.styles.body.bold / 布局项：emphasis"
    )

    line_spacing_context = field_display_context(
        "template.styles.body.line_spacing_value"
    )
    assert line_spacing_context.label == "正文行距"
    assert line_spacing_context.group_label == "行距与段距"
    assert line_spacing_context.label_with_group() == "行距与段距：正文行距"
    assert line_spacing_context.layout_item_id == "line_spacing_pt"
    assert line_spacing_context.field_ids == ("line_spacing_pt",)
    assert line_spacing_context.control_contract_key == "body.line_spacing"
    assert line_spacing_context.diagnostic_summary() == (
        "template.styles.body.line_spacing_value / "
        "布局项：line_spacing_pt / 控件契约：body.line_spacing"
    )

    plain_context = field_display_context("company_name")
    assert plain_context.label == "公司名称"
    assert plain_context.group_label == ""
    assert plain_context.label_with_group() == "公司名称"
    assert plain_context.diagnostic_summary() == "company_name"


def test_replace_field_keys_with_display_names_translates_embedded_keys():
    assert replace_field_keys_with_display_names(
        "控件契约缺失：body.special_indent"
    ) == "控件契约缺失：正文特殊缩进（body.special_indent）"
    assert replace_field_keys_with_display_names(
        "控件契约缺失：body.special_indent",
        include_raw_key=False,
    ) == "控件契约缺失：正文特殊缩进"
    assert replace_field_keys_with_display_names(
        "参数：scene.section_styles.references_body.font_cn"
    ) == (
        "参数：参考文献正文中文字体"
        "（scene.section_styles.references_body.font_cn）"
    )
    assert replace_field_keys_with_display_names(
        "参数：template.styles.body.bold",
        include_raw_key=False,
    ) == "参数：正文字形"
    assert replace_field_keys_with_display_names(
        "证据：src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput"
    ) == "证据：src/shared/ui/paragraph_style_inputs.py:120#class SpecialIndentInput"
