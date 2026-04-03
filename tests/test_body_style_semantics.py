import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.style_semantics import apply_style_special_indent
from src.config.template import StyleConfig, TemplateConfig
from src.modules.basic.paragraph_style import _apply_indent
from src.qt_api import QApplication
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.size_combo import SizeCombo
from src.ui.panels.template_format import build_template_preview_groups


def _app():
    return QApplication.instance() or QApplication([])


def test_size_combo_parses_named_size_and_pt_suffix():
    _app()
    combo = SizeCombo()
    try:
        combo.setEditText("小四")
        assert combo.current_pt() == 12.0

        combo.setEditText("12磅")
        assert combo.current_pt() == 12.0
    finally:
        combo.close()


def test_font_combo_preserves_custom_font_name():
    _app()
    combo = FontCombo(lang="cn")
    try:
        combo.set_font_name("思源宋体")
        assert combo.selected_font() == "思源宋体"
    finally:
        combo.close()


def test_paragraph_style_applies_pt_indent_units_as_points():
    document = Document()
    para = document.add_paragraph("正文")
    style = StyleConfig(
        size_pt=12,
        left_indent_chars=24,
        left_indent_unit="pt",
        right_indent_chars=12,
        right_indent_unit="pt",
    )
    apply_style_special_indent(style, "first_line", 18, "pt")

    _apply_indent(para, style, style.size_pt)

    assert round(para.paragraph_format.left_indent.pt, 2) == 24.0
    assert round(para.paragraph_format.right_indent.pt, 2) == 12.0
    assert round(para.paragraph_format.first_line_indent.pt, 2) == 18.0


def test_style_preview_summary_reflects_hanging_indent():
    cfg = TemplateConfig()
    body = StyleConfig()
    cfg.styles["body"] = body
    body.font_cn = "黑体"
    body.font_en = "Arial"
    body.size_pt = 12
    body.line_spacing_type = "multiple"
    body.line_spacing_pt = 1.5
    apply_style_special_indent(body, "hanging", 1.5, "chars")

    groups = build_template_preview_groups(cfg)
    style_group = next(group for group in groups if group.group_id == "style")

    assert "悬挂" in style_group.summary
    assert "1.5倍" in style_group.summary


def test_style_preview_summary_preserves_named_line_spacing_presets():
    cfg = TemplateConfig()
    body = StyleConfig()
    cfg.styles["body"] = body
    body.line_spacing_type = "double"
    body.line_spacing_pt = 2.0

    groups = build_template_preview_groups(cfg)
    style_group = next(group for group in groups if group.group_id == "style")

    assert "双倍" in style_group.summary
