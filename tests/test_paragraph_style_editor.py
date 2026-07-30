import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.style_semantics import apply_style_special_indent
from src.config.template import StyleConfig
from src.config.style_field_descriptors import style_field_layout_rows
from src.qt_api import QApplication
from src.shared.ui.form_row import FormRow
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.paragraph_style_editor import (
    ParagraphStyleEditor,
    canonical_paragraph_style_field_id,
)
from src.shared.ui.paragraph_style_surface import (
    StyleControlSurface,
    StyleControlSurfaceState,
)


def _app():
    return QApplication.instance() or QApplication([])


def _set_combo_data(combo, value) -> None:
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def test_paragraph_style_editor_round_trips_style_config():
    app = _app()
    editor = ParagraphStyleEditor(object_name_prefix="test_paragraph_style")
    style = StyleConfig(
        font_cn="宋体",
        font_en="Times New Roman",
        size_pt=12,
        bold=False,
        italic=False,
        alignment="justify",
        left_indent_chars=0,
        left_indent_unit="chars",
        right_indent_chars=0,
        right_indent_unit="chars",
        line_spacing_type="single",
        line_spacing_pt=1.0,
        space_before_pt=0,
        space_before_unit="pt",
        space_after_pt=0,
        space_after_unit="pt",
    )
    apply_style_special_indent(style, "none", 0, "chars")

    try:
        editor.set_style(style)

        assert editor.font_cn.selected_font() == "宋体"
        assert editor.font_en.selected_font() == "Times New Roman"
        assert editor.size_combo.current_pt() == 12
        assert editor.line_type_combo.currentData() == "single"
        assert editor.line_value.isEnabled() is False

        editor.font_cn.set_font_name("黑体")
        editor.font_en.set_font_name("Arial")
        editor.size_combo.set_pt(14.0)
        editor.bold_switch.setChecked(True)
        editor.italic_switch.setChecked(True)
        _set_combo_data(editor.alignment_combo, "center")
        editor.special_indent.set_value("first_line", 2.0, "chars")
        editor.left_indent.set_value(1.0, "cm")
        editor.right_indent.set_value(12.0, "pt")
        _set_combo_data(editor.line_type_combo, "exact")
        editor.line_value.set_value(18.0, "pt")
        editor.space_before.set_value(6.0, "pt")
        editor.space_after.set_value(1.0, "lines")
        app.processEvents()

        target = StyleConfig()
        editor.apply_to_style(target)

        assert target.font_cn == "黑体"
        assert target.font_en == "Arial"
        assert target.size_pt == 14.0
        assert target.size_display == "四号"
        assert target.bold is True
        assert target.italic is True
        assert target.alignment == "center"
        assert target.special_indent_mode == "first_line"
        assert target.special_indent_value == 2.0
        assert target.special_indent_unit == "chars"
        assert target.left_indent_chars == 1.0
        assert target.left_indent_unit == "cm"
        assert target.right_indent_chars == 12.0
        assert target.right_indent_unit == "pt"
        assert target.line_spacing_type == "exact"
        assert target.line_spacing_pt == 18.0
        assert target.space_before_pt == 6.0
        assert target.space_before_unit == "pt"
        assert target.space_after_pt == 1.0
        assert target.space_after_unit == "lines"

        editor.set_editable(False)
        assert editor.font_cn.isEnabled() is False
        assert editor.special_indent.isEnabled() is False
        assert editor.line_value.isEnabled() is False
    finally:
        editor.close()
        app.processEvents()


def test_paragraph_style_editor_resolves_shared_field_contracts():
    app = _app()
    editor = ParagraphStyleEditor(object_name_prefix="test_paragraph_nav")

    try:
        assert canonical_paragraph_style_field_id("body.font_name") == "font_cn"
        assert canonical_paragraph_style_field_id("template.styles.body.font_en") == "font_en"
        assert canonical_paragraph_style_field_id("template.styles.references_body.size_pt") == "size_pt"
        assert canonical_paragraph_style_field_id("template.styles.*.special_indent_value") == "special_indent"
        assert canonical_paragraph_style_field_id("body.space_after_unit") == "space_after"

        assert editor.widget_for_field("body.font_name") is editor.font_cn
        assert editor.widget_for_field("template.styles.body.font_en") is editor.font_en
        assert editor.widget_for_field("template.styles.references_body.size_pt") is editor.size_combo
        assert editor.widget_for_field("template.styles.*.special_indent_value") is editor.special_indent
        assert editor.widget_for_field("body.line_spacing_pt") is editor.line_value
        assert editor.widget_for_field("unknown.field") is None
    finally:
        editor.close()
        app.processEvents()


def test_style_control_surface_projects_descriptor_rows_to_shared_cards():
    app = _app()
    surface = StyleControlSurface(object_name_prefix="test_style_surface")
    style = StyleConfig(font_cn="宋体")

    try:
        assert surface.card_for_group("text") is surface.text_card
        assert surface.card_for_group("alignment_indent") is surface.alignment_indent_card
        assert surface.card_for_group("spacing") is surface.spacing_card
        assert len(surface.findChildren(InspectorForm)) == 3

        expected_labels = [
            item.label
            for group_id in ("text", "alignment_indent", "spacing")
            for row in style_field_layout_rows(group_id)
            for item in row
        ]
        actual_labels = [
            row.label_text
            for row in surface.findChildren(FormRow)
            if row.label_text in expected_labels
        ]

        assert actual_labels == expected_labels
        assert surface.widget_for_field("template.styles.body.font_name") is (
            surface.editor.font_cn
        )
        assert surface.widget_for_layout_item("emphasis") is (
            surface.editor.emphasis_widget
        )
        assert surface.widget_for_layout_item("line_spacing_pt") is (
            surface.editor.line_value
        )

        surface.apply_state(
            StyleControlSurfaceState(
                owner_kind="template_body_style",
                active_label="正文排版",
                source_label="模板默认样式",
                detail="模板样式。",
                editable=False,
                style=style,
                readonly_reason="未选择模板",
            )
        )

        assert surface.state().owner_kind == "template_body_style"
        assert surface.property("style_surface_owner_kind") == "template_body_style"
        assert surface.property("style_surface_active_label") == "正文排版"
        assert surface.property("style_surface_source_label") == "模板默认样式"
        assert surface.property("style_surface_editable") is False
        assert surface.property("style_surface_readonly_reason") == "未选择模板"
        assert surface.editor.font_cn.isEnabled() is False
    finally:
        surface.close()
        app.processEvents()
