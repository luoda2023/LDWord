import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.loader import load_template, save_template
from src.config.style_semantics import apply_style_special_indent
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QApplication, Qt
from src.shared.ui.card import Card
from src.shared.ui.dashed_separator import DashedSeparator
from src.shared.ui.form_row import FormRow
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.summary_grid import SummaryGrid
from src.shared.ui.template_form_layout import TemplateFormGrid, TemplateSplitColumns
from src.shared.ui.template_summary_header import TemplateSummaryHeader
from src.shared.ui.toast import Toast
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

        assert isinstance(detail._summary_grid, SummaryGrid)
        assert detail._summary_grid._tile_style == "module"
        assert len(detail._summary_grid.items()) == 3
        summary_items = {item.key: item for item in detail._summary_grid.items()}
        assert detail._summary_grid.value_for("text") == "黑体 / Arial"
        assert detail._summary_grid.detail_for("text") == "字号 四号  字形 加粗 / 斜体"
        assert detail._summary_grid.value_for("paragraph") == "居中  悬挂 1.5字"
        assert detail._summary_grid.detail_for("paragraph") == "左缩进 2字  右缩进 12磅"
        assert "1.5" in detail._summary_grid.value_for("spacing")
        assert detail._summary_grid.detail_for("spacing") == "段前 6 磅  段后 4 磅"
        assert summary_items["paragraph"].label == "对齐与缩进"
        assert summary_items["spacing"].label == "行距与段距"
        assert summary_items["text"].detail_emphasis is True
        assert summary_items["paragraph"].detail_emphasis is True
        assert summary_items["spacing"].detail_emphasis is True
        assert summary_items["text"].icon_name == "type-outline"
        assert summary_items["paragraph"].icon_name == "sliders-horizontal"
        assert summary_items["spacing"].icon_name == "sliders-horizontal"
    finally:
        detail.close()


def test_style_detail_syncs_spacing_units_from_template():
    _app()
    detail = StyleDetail()
    template = TemplateConfig()
    body = StyleConfig(
        line_spacing_type="exact",
        line_spacing_pt=20,
        space_before_pt=2.0,
        space_before_unit="lines",
        space_after_pt=1.0,
        space_after_unit="cm",
    )
    template.styles["body"] = body

    try:
        detail.set_template(template)

        assert detail._space_before.value() == 2.0
        assert detail._space_before.unit() == "lines"
        assert detail._space_after.value() == 1.0
        assert detail._space_after.unit() == "cm"
    finally:
        detail.close()


def test_style_detail_reuses_shared_controls():
    source = (ROOT / "src/ui/panels/template_style_detail.py").read_text(encoding="utf-8")
    format_source = (ROOT / "src/ui/panels/template_format.py").read_text(encoding="utf-8")

    assert "SummaryGrid(" in source
    assert "Card(" in source
    assert "FontCombo(" in source
    assert "SizeCombo(" in source
    assert "SpacingInput(" in source
    assert "SpecialIndentInput(" in source
    assert "IndentInput(" in source
    assert "ToggleSwitch(" in source
    assert "InspectorForm(" in source
    assert ".add_grid(" in source
    assert "TemplateSplitColumns(" not in source
    assert "TemplateFormGrid(" not in source
    assert "template_form_row(" in source
    assert "_build_split_form_columns" not in source
    assert "_build_stacked_form_rows" not in source
    assert "_normalize_form_rows" not in source
    assert 'QPushButton("恢复"' in source
    assert 'QPushButton("保存"' in source
    assert "save_requested = Signal()" in source
    assert "_footer_note" not in source
    assert "_summary_hint" not in source
    assert "_build_subsection_header" not in source
    assert "段落结构" not in source
    assert "高级缩进" not in source
    assert "左右缩进（可选）" not in source
    assert "定义正文默认字体族、字号和字形。" not in source
    assert "控制正文对齐方式、特殊缩进和左右缩进。" not in source
    assert "控制行距模式与段前段后间距。" not in source
    assert "“字”会跟随当前字号换算；需要精确版式时可切到“磅”或 “cm”。" not in source
    assert "固定值：直接输入磅值，例如 20 磅。" not in source
    assert "·" not in source
    assert "·" not in format_source


def test_style_detail_organizes_body_controls_into_cards():
    _app()
    detail = StyleDetail()

    try:
        assert isinstance(detail._text_card, Card)
        assert isinstance(detail._alignment_indent_card, Card)
        assert isinstance(detail._spacing_card, Card)
        assert detail.findChild(TemplateSummaryHeader) is not None
        assert detail.findChild(TemplateSummaryHeader).title_label.font().pixelSize() == 20
        assert detail.findChildren(InspectorForm)
        assert detail.findChildren(TemplateFormGrid)
        assert not detail.findChildren(TemplateSplitColumns)
        assert not hasattr(detail, "_paragraph_card")
        assert not detail.findChildren(DashedSeparator)
        assert not hasattr(detail, "_advanced_indent_toggle")
        assert not hasattr(detail, "_advanced_indent_body")
        assert not hasattr(detail, "_indent_note")
        assert not hasattr(detail, "_line_spacing_note")
    finally:
        detail.close()


def test_style_detail_keeps_left_right_indent_visible_without_extra_helper_copy():
    _app()
    detail = StyleDetail()

    try:
        detail.set_template(TemplateConfig())

        assert detail._font_cn.toolTip()
        assert detail._font_cn.lineEdit().placeholderText()
        assert detail._size_combo.toolTip()
        assert detail._size_combo.lineEdit().placeholderText()
        assert detail._left_indent.toolTip()
        assert detail._left_indent.isEnabled() is True
        assert detail._right_indent.isEnabled() is True
        assert not hasattr(detail, "_indent_note")
        assert not hasattr(detail, "_line_spacing_note")

        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("double"))
        assert detail._line_value.isEnabled() is False

        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("exact"))
        assert detail._line_value.isEnabled() is True
    finally:
        detail.close()


def test_style_detail_alignment_indent_rows_share_same_column_starts():
    app = _app()
    detail = StyleDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}

        def label_left(row: FormRow) -> int:
            return row._label.mapTo(detail, row._label.rect().topLeft()).x()

        assert label_left(row_map["中文字体"]) == label_left(row_map["对齐"])
        assert label_left(row_map["字号"]) == label_left(row_map["字形"])
        assert label_left(row_map["对齐"]) == label_left(row_map["左缩进"])
        assert label_left(row_map["特殊缩进"]) == label_left(row_map["右缩进"])
    finally:
        detail.close()
        app.processEvents()


def test_style_detail_sections_keep_left_right_groups_near_equal_width():
    app = _app()
    detail = StyleDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        text_left_row = detail._font_cn.parent()
        text_right_row = detail._size_combo.parent()
        alignment_left_row = detail._alignment_combo.parent()
        alignment_right_row = detail._special_indent.parent()
        spacing_left_row = detail._line_type_combo.parent()
        spacing_right_row = detail._line_value.parent()

        assert isinstance(text_left_row, FormRow)
        assert isinstance(text_right_row, FormRow)
        assert isinstance(alignment_left_row, FormRow)
        assert isinstance(alignment_right_row, FormRow)
        assert isinstance(spacing_left_row, FormRow)
        assert isinstance(spacing_right_row, FormRow)

        assert abs(text_left_row.width() - text_right_row.width()) <= 16
        assert abs(alignment_left_row.width() - alignment_right_row.width()) <= 16
        assert abs(spacing_left_row.width() - spacing_right_row.width()) <= 16
    finally:
        detail.close()
        app.processEvents()


def test_style_detail_field_labels_follow_column_alignment():
    _app()
    detail = StyleDetail()

    try:
        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}

        leading_labels = ("中文字体", "英文字体", "对齐", "左缩进", "行距类型", "段前")
        trailing_labels = ("字号", "字形", "特殊缩进", "右缩进", "行距值", "段后")
        for label in leading_labels:
            assert row_map[label]._label.alignment() & Qt.AlignLeft
            assert not (row_map[label]._label.alignment() & Qt.AlignRight)
        for label in trailing_labels:
            assert row_map[label]._label.alignment() & Qt.AlignRight
            assert not (row_map[label]._label.alignment() & Qt.AlignLeft)
    finally:
        detail.close()


def test_style_detail_text_to_control_gap_stays_compact():
    _app()
    detail = StyleDetail()

    try:
        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}

        for label in ("中文字体", "英文字体", "字号", "字形", "对齐", "特殊缩进", "左缩进", "右缩进", "行距类型", "行距值", "段前", "段后"):
            row = row_map[label]
            layout_gap = row.layout().spacing()
            visible_gap = row.widget.x() - row.label_width
            assert layout_gap == 4
            assert visible_gap <= 20
    finally:
        detail.close()


def test_style_detail_spacing_rows_share_stable_column_starts():
    app = _app()
    detail = StyleDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}

        def label_left(row: FormRow) -> int:
            return row._label.mapTo(detail, row._label.rect().topLeft()).x()

        assert label_left(row_map["行距类型"]) == label_left(row_map["段前"])
        assert label_left(row_map["行距值"]) == label_left(row_map["段后"])
    finally:
        detail.close()
        app.processEvents()
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


def test_style_detail_updates_summary_grid_with_current_body_settings():
    _app()
    detail = StyleDetail()
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(font_cn="宋体", font_en="Times New Roman", size_pt=12)

    try:
        detail.set_template(template)
        detail._font_cn.set_font_name("黑体")
        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("one_half"))

        assert detail._summary_grid.value_for("text") == "黑体 / Times New Roman"
        assert "1.5" in detail._summary_grid.value_for("spacing")
    finally:
        detail.close()


def test_style_detail_save_button_emits_save_request():
    _app()
    detail = StyleDetail()
    emitted: list[bool] = []

    try:
        detail.set_template(TemplateConfig())
        detail.set_save_enabled(True)
        detail.save_requested.connect(lambda: emitted.append(True))

        detail._save_btn.click()

        assert emitted == [True]
    finally:
        detail.close()


def test_style_detail_restore_entry_snapshot_survives_bridge_echo():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    original_font = panel._current_template.styles["body"].font_cn

    try:
        panel._show_detail("tpl_style")
        panel._style_detail._font_cn.set_font_name("黑体")
        app.processEvents()

        assert panel._style_detail._restore_entry_btn.isEnabled() is True

        panel._style_detail._restore_entry_btn.click()
        app.processEvents()

        assert panel._current_template.styles["body"].font_cn == original_font
        assert panel._style_detail._restore_entry_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


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
        assert panel._style_detail._save_btn.isEnabled() is True
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_style_save_overwrites_current_file_and_clears_dirty(tmp_path, monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    monkeypatch.setattr(Toast, "show_success", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(Toast, "show_error", staticmethod(lambda *args, **kwargs: None))

    try:
        target = tmp_path / "style_template.json"
        save_template(panel._current_template, target)
        imported = load_template(target)
        bridge.set_current_template(
            imported,
            config_id=target.stem,
            path=str(target),
            source="file",
        )
        panel._show_detail("tpl_style")
        app.processEvents()

        panel._style_detail._font_cn.set_font_name("黑体")
        app.processEvents()

        assert bridge.is_template_dirty() is True
        assert panel._style_detail._save_btn.isEnabled() is True

        panel._style_detail._save_btn.click()
        app.processEvents()

        reloaded = load_template(target)
        assert reloaded.styles["body"].font_cn == "黑体"
        assert bridge.is_template_dirty() is False
        assert panel._style_detail._save_btn.isEnabled() is False
        assert "已保存" in panel._io_detail._status.text()
    finally:
        panel.close()
        app.processEvents()
