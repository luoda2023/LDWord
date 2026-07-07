import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.scene import SceneWorkspace
from src.config.style_variant_semantics import (
    build_section_style_comparison_projection,
    build_section_style_override_projection,
    build_section_style_preview_projection,
    disable_section_style_override,
    enable_section_style_override,
)
from src.config.template import StyleConfig


def test_section_style_override_projection_tracks_template_follow_and_diffs():
    template = create_builtin_template("default")
    template.styles["references_body"] = StyleConfig(
        font_cn="黑体",
        font_en="Arial",
        size_pt=10.5,
        line_spacing_type="exact",
        line_spacing_pt=18,
    )
    scene = SceneWorkspace(scene_id="thesis", template_id="default")
    scene.format_scope.sections["references"] = True

    projection = build_section_style_override_projection(
        scene,
        template,
        "references_body",
    )

    assert projection.status_value == "跟随模板"
    assert projection.changed_labels == ()
    assert projection.editable is False
    assert "模板" in projection.editor_hint

    override = enable_section_style_override(scene, template, "references_body")

    assert override.font_cn == "黑体"
    assert override.font_en == "Arial"
    assert override.line_spacing_pt == 18

    projection = build_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    assert projection.status_value == "已开启独立样式"
    assert projection.changed_labels == ()
    assert projection.editable is True
    assert projection.status_detail == "与模板一致。"

    override.font_cn = "仿宋"
    override.size_pt = 12
    override.line_spacing_pt = 20

    projection = build_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    assert projection.status_value == "已调整 3 项"
    assert projection.changed_labels == ("中文字体", "字号", "行距")
    assert projection.status_detail == "不同：中文字体、字号、行距"

    disable_section_style_override(scene, "references_body")
    scene.format_scope.sections["references"] = False
    projection = build_section_style_override_projection(
        scene,
        template,
        "references_body",
    )
    assert projection.status_value == "跟随模板"
    assert projection.editable is False


def test_section_style_comparison_projection_names_template_current_and_diff():
    template = create_builtin_template("default")
    template.styles["references_body"] = StyleConfig(
        font_cn="黑体",
        size_pt=10.5,
        line_spacing_type="exact",
        line_spacing_pt=18,
    )
    scene = SceneWorkspace(scene_id="thesis", template_id="default")
    scene.format_scope.sections["references"] = True

    comparison = build_section_style_comparison_projection(
        scene,
        template,
        "references_body",
    )

    assert comparison.template_status == "模板基线"
    assert comparison.current_status == "跟随模板"
    assert comparison.difference_status == "无差异"
    assert comparison.detail == "当前分区直接使用模板基线。"

    override = enable_section_style_override(scene, template, "references_body")
    comparison = build_section_style_comparison_projection(
        scene,
        template,
        "references_body",
    )

    assert comparison.current_status == "独立样式"
    assert comparison.difference_status == "未改字段"
    assert comparison.detail == "已独立，但字段仍与模板一致。"

    override.font_cn = "仿宋"
    override.size_pt = 12
    comparison = build_section_style_comparison_projection(
        scene,
        template,
        "references_body",
    )

    assert comparison.current_status == "独立样式"
    assert comparison.difference_status == "已调整 2 项"
    assert comparison.detail == "不同：中文字体、字号"

    scene.format_scope.sections["references"] = False
    comparison = build_section_style_comparison_projection(
        scene,
        template,
        "references_body",
    )

    assert comparison.current_status == "独立样式"
    assert comparison.difference_status == "已调整 2 项"
    assert comparison.detail == "不同：中文字体、字号"


def test_section_style_preview_projection_uses_effective_scene_style():
    template = create_builtin_template("default")
    template.styles["references_body"] = StyleConfig(
        font_cn="黑体",
        font_en="Arial",
        size_pt=10.5,
        bold=True,
        italic=False,
        alignment="center",
        special_indent_mode="first_line",
        special_indent_value=2,
        special_indent_unit="chars",
        left_indent_chars=1,
        left_indent_unit="chars",
        right_indent_chars=6,
        right_indent_unit="pt",
        line_spacing_type="exact",
        line_spacing_pt=18,
        space_before_pt=0.5,
        space_before_unit="lines",
        space_after_pt=6,
        space_after_unit="pt",
    )
    scene = SceneWorkspace(scene_id="thesis", template_id="default")
    scene.format_scope.sections["references"] = True

    preview = build_section_style_preview_projection(
        scene,
        template,
        "references_body",
    )

    assert preview.label == "参考文献"
    assert preview.source_label == "跟随模板"
    assert preview.font_cn == "黑体"
    assert preview.font_en == "Arial"
    assert preview.size_pt == 10.5
    assert preview.bold is True
    assert preview.italic is False
    assert preview.alignment == "center"
    assert preview.line_spacing_value == 18
    assert preview.left_indent_pt == 10.5
    assert preview.right_indent_pt == 6
    assert preview.first_indent_pt == 21
    assert preview.hanging_indent_pt == 0
    assert preview.space_before_pt == 9
    assert preview.space_after_pt == 6
    assert "参考文献样式预览" in preview.sample_text

    override = enable_section_style_override(scene, template, "references_body")
    override.font_cn = "仿宋"
    override.italic = True
    override.alignment = "right"
    override.line_spacing_pt = 20
    override.special_indent_mode = "hanging"
    override.special_indent_value = 1
    override.special_indent_unit = "chars"

    preview = build_section_style_preview_projection(
        scene,
        template,
        "references_body",
    )

    assert preview.source_label == "已调整 5 项"
    assert preview.font_cn == "仿宋"
    assert preview.italic is True
    assert preview.alignment == "right"
    assert preview.line_spacing_value == 20
    assert preview.left_indent_pt == 10.5
    assert preview.hanging_indent_pt == 10.5
