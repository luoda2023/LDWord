import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import SceneWorkspace
from src.config.style_variant_semantics import is_variant_overridden
from src.config.loader import load_compatible_user_template
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QApplication
from src.shared.ui.form_row import FormRow
from src.shared.ui.summary_grid import SummaryGrid
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_panel import ScenePanel
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.template_reference_detail import ReferenceDetail


def _app():
    return QApplication.instance() or QApplication([])


def test_reference_and_caption_details_reuse_shared_controls():
    reference_source = (ROOT / "src/ui/panels/template_reference_detail.py").read_text(encoding="utf-8")
    caption_source = (ROOT / "src/ui/panels/template_caption_detail.py").read_text(encoding="utf-8")

    assert "FontCombo(" in reference_source
    assert "SpacingInput(" in reference_source
    assert "save_requested = Signal()" in reference_source
    assert "apply_template_summary_action_button(self._restore_entry_btn, \"ghost-primary\")" in reference_source
    assert "apply_template_summary_action_button(self._save_btn, \"primary\")" in reference_source
    assert "StyledComboBox(" in caption_source
    assert "ToggleSwitch(" in caption_source


def test_reference_detail_style_sections_use_one_grid_baseline():
    app = _app()
    template = TemplateConfig()
    detail = ReferenceDetail()

    try:
        detail.set_template(template)
        detail.resize(900, 900)
        detail.show()
        app.processEvents()

        assert detail._source_card.isVisible()
        assert detail._rules_card.isVisible()
        assert not detail._style_card.isVisible()
        assert "跟随正文" in detail._source_summary.text()
        assert not hasattr(detail, "_desc")
        assert not hasattr(detail, "_inherit_card")
        assert not hasattr(detail, "_line_spacing_note")
        assert not hasattr(detail, "_special_indent")
        assert not hasattr(detail, "_left_indent")
        assert not hasattr(detail, "_right_indent")

        detail._mode_combo.setCurrentIndex(1)
        app.processEvents()

        assert "references_body" in template.styles
        assert detail._style_card.isVisible()
        assert "独立设置" in detail._source_summary.text()
        assert detail._style_grid._rows == [
            (detail._font_cn_row, detail._size_row),
            (detail._font_en_row, detail._emphasis_row),
            (detail._alignment_row, detail._line_type_row),
            (detail._line_value_row,),
            (detail._space_before_row, detail._space_after_row),
        ]
        assert detail._rules_grid._rows == [
            (detail._hanging_indent_row, detail._rules_space_after_row),
        ]

        detail._font_en.set_font_name("Arial")
        detail._size_combo.set_pt(11)
        detail._bold_switch.click()
        detail._alignment_combo.setCurrentIndex(detail._alignment_combo.findData("left"))
        detail._line_type_combo.setCurrentIndex(detail._line_type_combo.findData("multiple"))
        detail._line_value.set_value(1.2, "pt")
        detail._space_before.set_value(6.0, "pt")
        detail._space_after.set_value(9.0, "pt")
        app.processEvents()

        style = template.styles["references_body"]
        assert style.font_en == "Arial"
        assert style.size_pt == 11
        assert style.bold is True
        assert style.alignment == "left"
        assert style.line_spacing_type == "multiple"
        assert style.line_spacing_pt == 1.2
        assert style.space_before_pt == 6.0
        assert style.space_after_pt == 9.0

        style_rows = {
            row.label_text: row
            for row in detail._style_form.findChildren(FormRow)
            if row.isVisible()
        }
        assert style_rows["字号"].widget.x() == style_rows["中文字体"].widget.x()
        assert style_rows["字形"].widget.x() == style_rows["英文字体"].widget.x()
        assert style_rows["行距类型"].widget.x() == style_rows["对齐"].widget.x()
        assert style_rows["段后"].widget.x() == style_rows["段前"].widget.x()
    finally:
        detail.close()
        app.processEvents()


def test_legacy_reference_typography_is_migrated_to_style_variant(tmp_path):
    app = _app()
    template = TemplateConfig()
    template.styles["body"] = StyleConfig(alignment="right", bold=True)
    payload = asdict(template)
    payload["reference_style"].update(
        {"font_cn": "黑体", "font_en": "Calibri", "size_pt": 11}
    )
    target = tmp_path / "legacy-reference-template.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    template = load_compatible_user_template(target)
    detail = ReferenceDetail()

    try:
        detail.set_template(template)
        app.processEvents()

        assert not hasattr(template.reference_style, "font_cn")
        assert not hasattr(template.reference_style, "font_en")
        assert not hasattr(template.reference_style, "size_pt")
        assert is_variant_overridden(template, "references_body") is True
        assert template.styles["references_body"].alignment == "right"
        assert template.styles["references_body"].bold is True
        assert detail._mode_combo.currentData() == "independent"
        assert detail._font_cn.selected_font() == "黑体"
        assert detail._font_en.selected_font() == "Calibri"
    finally:
        detail.close()
        app.processEvents()


def test_scene_panel_reference_format_is_summary_only_and_routes_to_rules():
    app = _app()
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="thesis", category="thesis", template_id="default")
    bridge.set_current_scene(scene, config_id="thesis", emit_signal=False)
    bridge.set_current_template(TemplateConfig(), config_id="default", emit_signal=False)
    panel = ScenePanel(bridge)

    try:
        reference_row = panel._overview._setting_rows["reference_format"]
        original_indent = scene.reference_style.hanging_indent_cm

        assert f"{original_indent:g}cm" in reference_row.summary_text()
        assert reference_row._target_card_id == "scn_rules"
        assert "_reference" not in panel._DETAIL_ATTR_NAMES

        reference_row._jump_btn.click()
        app.processEvents()

        assert panel._nav_rail.selected_card_id() == "scn_rules"
        assert panel._rules is panel._detail_map["scn_rules"]
        assert scene.reference_style.hanging_indent_cm == original_indent
        assert bridge.is_scene_dirty() is False
        assert bridge.is_template_dirty() is False
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_caption_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        detail = panel._caption_detail
        detail._numbering_type_combo.setCurrentIndex(detail._numbering_type_combo.findData(True))
        detail._auto_insert_combo.setCurrentIndex(detail._auto_insert_combo.findData(False))
        detail._table_break_policy_combo.setCurrentIndex(
            detail._table_break_policy_combo.findData("remove_proven_redundant")
        )
        app.processEvents()

        assert panel._current_template.caption.format_inserted is True
        assert panel._current_template.caption.auto_insert is False
        assert (
            panel._current_template.caption.table_break_policy
            == "remove_proven_redundant"
        )
        assert isinstance(panel._caption_detail._summary_grid, SummaryGrid)
        assert panel._caption_detail._summary_grid._tile_style == "module"
        assert len(panel._caption_detail._summary_grid.items()) == 3
        assert "Word 可更新编号" in panel._caption_detail._summary_grid.detail_for("numbering_rules")
        assert "缺失时不补齐" in panel._caption_detail._summary_grid.detail_for("numbering_rules")
        assert "题注-表格冗余分节" in panel._caption_detail._summary_grid.detail_for("numbering_rules")
        assert "Word 可更新编号" in panel._overview_detail._rows["caption"]._value.text()
        assert "Word 可更新编号" in panel._nav_cards["tpl_caption"]._full_subtitle
        assert "域" not in panel._caption_detail._summary_grid.detail_for("numbering_rules")
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_caption_detail_updates_shared_caption_style():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._caption_detail._font_en_combo.set_font_name("Arial")
        panel._caption_detail._size_combo.set_pt(11)
        panel._caption_detail._bold_switch.click()
        panel._caption_detail._italic_switch.click()
        panel._caption_detail._alignment_combo.setCurrentIndex(
            panel._caption_detail._alignment_combo.findData("left")
        )
        panel._caption_detail._line_type_combo.setCurrentIndex(
            panel._caption_detail._line_type_combo.findData("multiple")
        )
        panel._caption_detail._line_value_input.set_value(1.25, "pt")
        panel._caption_detail._space_before_input.set_value(6.0, "pt")
        panel._caption_detail._space_after_input.set_value(9.0, "pt")
        app.processEvents()

        assert panel._current_template.styles["caption"].font_en == "Arial"
        assert panel._current_template.styles["caption"].size_pt == 11
        assert panel._current_template.styles["caption"].bold is True
        assert panel._current_template.styles["caption"].italic is True
        assert panel._current_template.styles["caption"].alignment == "left"
        assert panel._current_template.styles["caption"].line_spacing_type == "multiple"
        assert panel._current_template.styles["caption"].line_spacing_pt == 1.25
        assert panel._current_template.styles["caption"].space_before_pt == 6.0
        assert panel._current_template.styles["caption"].space_after_pt == 9.0
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()
