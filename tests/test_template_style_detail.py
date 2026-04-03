import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.style_semantics import apply_style_special_indent
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.template_style_detail import StyleDetail


def _app():
    return QApplication.instance() or QApplication([])


def test_style_detail_syncs_widget_values_from_template():
    _app()
    detail = StyleDetail()
    template = TemplateConfig()
    body = StyleConfig(
        font_cn="黑体",
        font_en="Arial",
        size_pt=14,
        size_display="四号",
        bold=True,
        italic=True,
        alignment="center",
        left_indent_chars=2,
        left_indent_unit="chars",
        right_indent_chars=12,
        right_indent_unit="pt",
        line_spacing_type="multiple",
        line_spacing_pt=1.5,
        space_before_pt=6,
        space_after_pt=4,
    )
    apply_style_special_indent(body, "hanging", 1.5, "chars")
    template.styles["body"] = body

    try:
        detail.set_template(template)

        assert detail._font_cn.selected_font() == "黑体"
        assert detail._font_en.selected_font() == "Arial"
        assert detail._size_combo.current_pt() == 14
        assert detail._bold_switch.isChecked() is True
        assert detail._italic_switch.isChecked() is True
        assert detail._alignment_combo.currentData() == "center"
        assert detail._special_indent.mode() == "hanging"
        assert detail._special_indent.value() == 1.5
        assert detail._left_indent.value() == 2
        assert detail._left_indent.unit() == "chars"
        assert detail._right_indent.value() == 12
        assert detail._right_indent.unit() == "pt"
        assert detail._line_type_combo.currentData() == "multiple"
        assert detail._line_value.value() == 1.5
    finally:
        detail.close()


def test_style_detail_reuses_shared_controls():
    source = (ROOT / "src/ui/panels/template_style_detail.py").read_text(encoding="utf-8")

    assert "FontCombo(" in source
    assert "SizeCombo(" in source
    assert "SpacingInput(" in source
    assert "SpecialIndentInput(" in source
    assert "IndentInput(" in source
    assert "ToggleSwitch(" in source


def test_style_detail_exposes_hints_for_font_size_indent_and_line_spacing():
    _app()
    detail = StyleDetail()

    try:
        assert detail._font_cn.toolTip()
        assert detail._font_cn.lineEdit().placeholderText()
        assert detail._size_combo.toolTip()
        assert detail._size_combo.lineEdit().placeholderText()
        assert detail._left_indent.toolTip()
        assert "缩进支持" in detail._indent_note.text()

        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("double"))
        assert "快捷预设" in detail._line_spacing_note.text()
        assert detail._line_value.isEnabled() is False

        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("exact"))
        assert "固定值" in detail._line_spacing_note.text()
        assert detail._line_value.isEnabled() is True
    finally:
        detail.close()


def test_style_detail_restores_line_spacing_presets_as_locked_values():
    _app()
    detail = StyleDetail()
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(
        line_spacing_type="double",
        line_spacing_pt=2.0,
    )

    try:
        detail.set_template(template)

        assert detail._line_type_combo.currentData() == "double"
        assert detail._line_value.value() == 2.0
        assert detail._line_value.isEnabled() is False

        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("multiple"))
        assert detail._line_value.isEnabled() is True

        detail._line_value.set_value(1.8, "pt")
        body = template.styles["body"]
        assert body.line_spacing_type == "multiple"
        assert body.line_spacing_pt == 1.8
    finally:
        detail.close()


def test_style_detail_updates_footer_summary_with_current_body_settings():
    _app()
    detail = StyleDetail()
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(font_cn="宋体", font_en="Times New Roman", size_pt=12)

    try:
        detail.set_template(template)
        detail._font_cn.set_font_name("黑体")
        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("one_half"))

        text = detail._footer_note.text()
        assert "当前正文:" in text
        assert "黑体" in text
        assert "1.5" in text or "1.5 倍" in text
    finally:
        detail.close()


def test_template_panel_style_edit_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._style_detail._font_cn.set_font_name("黑体")
        panel._style_detail._special_indent.set_value("hanging", 1.5, "chars")
        app.processEvents()

        body = panel._current_template.styles["body"]
        assert body.font_cn == "黑体"
        assert body.hanging_indent_chars == 1.5
        assert "黑体" in panel._overview_detail._rows["style"]._value.text()
        assert "悬挂" in panel._overview_detail._rows["style"]._value.text()
        assert "黑体" in panel._nav_cards["tpl_style"]._full_subtitle
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()
