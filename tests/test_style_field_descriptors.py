import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.style_field_descriptors import (  # noqa: E402
    canonical_paragraph_style_field_id,
    scene_style_field_path,
    scene_style_navigation_target_from_field_id,
    scene_style_policy_key_from_field_id,
    style_field_control_label,
    style_field_descriptor,
    style_field_group_descriptor,
    style_field_label,
    style_field_layout_rows,
    style_field_layout_item_for_field,
    style_field_widget_attr,
    template_style_field_path,
)
from src.shared.ui.paragraph_style_editor import ParagraphStyleEditor  # noqa: E402


def test_style_field_descriptor_normalizes_template_scene_and_contract_paths():
    descriptor = style_field_descriptor("template.styles.body.font_name")

    assert descriptor is not None
    assert descriptor.field_id == "font_cn"
    assert descriptor.label == "中文字体"
    assert descriptor.control_label == "中文字体"
    assert descriptor.widget_attr == "_font_cn"
    assert descriptor.group == "text"
    assert descriptor.group_label == "文字样式"
    assert descriptor.group_icon == "whole-word"
    assert descriptor.layout_slot == "text.primary.1"
    assert descriptor.visible_in_standard_mode is True
    assert descriptor.visible_in_diagnostic_mode is True
    assert descriptor.template_path == "template.styles.body.font_cn"
    assert descriptor.scene_editor_path == "section_style.font_cn"
    assert descriptor.control_contract_key == "body.font_cn"

    assert canonical_paragraph_style_field_id(
        "scene.section_styles.references_body.line_spacing_value"
    ) == "line_spacing_pt"
    assert style_field_label("body.special_indent_mode") == "特殊缩进"
    assert style_field_control_label("body.line_spacing_value") == "行距值"
    assert style_field_widget_attr("section_style.left_indent_chars") == "_left_indent"
    assert (
        template_style_field_path("body.line_spacing_value")
        == "template.styles.body.line_spacing_pt"
    )
    assert (
        scene_style_field_path("references_body", "line_spacing_value")
        == "scene.section_styles.references_body.line_spacing_pt"
    )
    assert style_field_descriptor(
        "template.styles.body.line_spacing_type"
    ).control_contract_key == "body.line_spacing"
    assert style_field_descriptor("line_spacing_value").layout_slot == (
        "spacing.primary.2"
    )
    assert style_field_descriptor("body.bold").control_contract_key == ""

    spacing_group = style_field_group_descriptor("spacing")
    assert spacing_group.label == "行距与段距"
    assert spacing_group.icon_name == "sliders-horizontal"
    assert spacing_group.mode == "standard"


def test_paragraph_style_editor_consumes_shared_field_descriptors(qapp):
    editor = ParagraphStyleEditor(object_name_prefix="descriptor_probe")
    try:
        assert editor.widget_for_field("template.styles.body.font_name") is editor.font_cn
        assert editor.widget_for_field(
            "scene.section_styles.references_body.special_indent_mode"
        ) is editor.special_indent
        assert editor.widget_for_field("section_style.left_indent_chars") is (
            editor.left_indent
        )
        assert editor.widget_for_field("body.not_a_field") is None
    finally:
        editor.close()


def test_scene_style_navigation_target_normalizes_policy_paths():
    assert scene_style_navigation_target_from_field_id(
        "scene.section_styles.references_body.font_cn"
    ) == ("references_body", "font_cn")
    assert scene_style_navigation_target_from_field_id(
        "section_styles.references_body.line_spacing_value"
    ) == ("references_body", "line_spacing_value")
    assert scene_style_navigation_target_from_field_id(
        "references_body.special_indent_mode"
    ) == ("references_body", "special_indent_mode")
    assert scene_style_navigation_target_from_field_id(
        "scene.section_styles.references_body"
    ) == ("references_body", "")
    assert (
        scene_style_policy_key_from_field_id("section_styles.acknowledgment_body")
        == "acknowledgment_body"
    )
    assert scene_style_navigation_target_from_field_id(
        "scene.section_styles.*.font_cn"
    ) == ("", "")
    assert scene_style_policy_key_from_field_id(
        "scene.section_styles.not_a_variant.font_cn"
    ) == ""


def test_style_field_layout_rows_project_editor_information_architecture():
    assert [
        [item.item_id for item in row]
        for row in style_field_layout_rows("text")
    ] == [["font_cn", "size_pt"], ["font_en", "emphasis"]]
    assert [
        [item.item_id for item in row]
        for row in style_field_layout_rows("alignment_indent")
    ] == [["alignment", "special_indent"], ["left_indent", "right_indent"]]
    assert [
        [item.item_id for item in row]
        for row in style_field_layout_rows("spacing")
    ] == [["line_spacing_type", "line_spacing_pt"], ["space_before", "space_after"]]

    text_rows = style_field_layout_rows("text")
    assert text_rows[1][1].label == "字形"
    assert text_rows[1][1].field_ids == ("bold", "italic")
    assert text_rows[1][1].layout_slot == "text.secondary.2"
    assert style_field_layout_item_for_field("template.styles.body.bold").item_id == (
        "emphasis"
    )
    assert style_field_layout_item_for_field("body.italic").label == "字形"
    assert style_field_layout_item_for_field("line_spacing_value").item_id == (
        "line_spacing_pt"
    )


def test_style_navigation_adapter_uses_config_descriptors_not_widget_module():
    source = (ROOT / "src/ui/adapters/workbench_issue_navigation.py").read_text(
        encoding="utf-8"
    )

    assert "src.config.style_field_descriptors" in source
    assert "src.shared.ui.paragraph_style_editor import canonical" not in source
