import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.loader import load_template, save_template
from src.config.style_variant_semantics import enable_variant_override
from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.shared.ui.form_row import FormRow
from src.shared.ui.toast import Toast
from src.ui.bridge import PanelBridge
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
    assert "apply_button_variant(self._restore_entry_btn, \"ghost-primary\")" in reference_source
    assert "apply_button_variant(self._save_btn, \"primary\")" in reference_source
    assert "StyledComboBox(" in caption_source
    assert "ToggleSwitch(" in caption_source


def test_reference_detail_style_sections_use_one_grid_baseline():
    app = _app()
    template = TemplateConfig()
    enable_variant_override(template, "references_body")
    detail = ReferenceDetail()

    try:
        detail.set_template(template)
        detail.resize(900, 900)
        detail.show()
        app.processEvents()

        text_rows = {
            row.label_text: row
            for row in detail._text_section.findChildren(FormRow)
            if row.isVisible()
        }
        assert text_rows["字号"].widget.x() == text_rows["中文字体"].widget.x()
        assert text_rows["字形"].widget.x() == text_rows["英文字体"].widget.x()

        spacing_rows = {
            row.label_text: row
            for row in detail._spacing_section.findChildren(FormRow)
            if row.isVisible()
        }
        assert spacing_rows["段前"].widget.x() == spacing_rows["行距类型"].widget.x()
        assert spacing_rows["段后"].widget.x() == spacing_rows["行距值"].widget.x()
    finally:
        detail.close()
        app.processEvents()


def test_template_panel_reference_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._reference_detail._hanging_indent.set_value(1.2, "cm")
        app.processEvents()

        assert panel._current_template.reference_style.hanging_indent_cm == 1.2
        assert "1.2cm" in panel._overview_detail._rows["reference"]._value.text()
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_reference_detail_restore_entry_snapshot_survives_bridge_echo():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    original_indent = panel._current_template.reference_style.hanging_indent_cm

    try:
        panel._show_detail("tpl_reference")
        panel._reference_detail._hanging_indent.set_value(original_indent + 0.4, "cm")
        app.processEvents()

        assert panel._reference_detail._restore_entry_btn.isEnabled() is True

        panel._reference_detail._restore_entry_btn.click()
        app.processEvents()

        assert panel._current_template.reference_style.hanging_indent_cm == original_indent
        assert panel._reference_detail._restore_entry_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_reference_save_overwrites_current_file_and_clears_dirty(tmp_path, monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    monkeypatch.setattr(Toast, "show_success", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(Toast, "show_error", staticmethod(lambda *args, **kwargs: None))

    try:
        target = tmp_path / "reference_template.json"
        save_template(panel._current_template, target)
        imported = load_template(target)
        bridge.set_current_template(
            imported,
            config_id=target.stem,
            path=str(target),
            source="file",
        )
        panel._show_detail("tpl_reference")
        app.processEvents()

        panel._reference_detail._hanging_indent.set_value(1.6, "cm")
        app.processEvents()

        assert bridge.is_template_dirty() is True
        assert panel._reference_detail._save_btn.isEnabled() is True

        panel._reference_detail._save_btn.click()
        app.processEvents()

        reloaded = load_template(target)
        assert reloaded.reference_style.hanging_indent_cm == 1.6
        assert bridge.is_template_dirty() is False
        assert panel._reference_detail._save_btn.isEnabled() is False
        assert "reference_template.json" in panel._io_detail._status.text()
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_caption_detail_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)

    try:
        panel._caption_detail._format_inserted_toggle.click()
        app.processEvents()

        assert panel._current_template.caption.format_inserted is True
        assert "域编号" in panel._overview_detail._rows["caption"]._value.text()
        assert "域编号" in panel._nav_cards["tpl_caption"]._full_subtitle
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
        app.processEvents()

        assert panel._current_template.styles["caption"].font_en == "Arial"
        assert panel._current_template.styles["caption"].size_pt == 11
        assert panel._current_template.styles["caption"].bold is True
        assert panel._current_template.styles["caption"].italic is True
        assert panel._current_template.styles["caption"].alignment == "left"
        assert bridge.is_template_dirty() is True
    finally:
        panel.close()
        app.processEvents()
