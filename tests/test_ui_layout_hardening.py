import sys
from pathlib import Path

from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication, Qt, QVBoxLayout, QWidget
from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.form_row import FormRow
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.qt_api import QLabel
from src.shared.ui.sizing import resolved_control_height
from src.shared.ui.theme import get_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.ui.panels.template_style_detail import StyleDetail


def _app():
    return QApplication.instance() or QApplication([])


def test_shared_form_controls_follow_md_height_contract():
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    combo.addItems(["A4", "A5"])
    spin = StyledSpinBox(host)
    spacing = SpacingInput(unit="cm", units=("cm",), show_unit=False, parent=host)
    row = FormRow("纸张", combo, parent=host)

    layout.addWidget(combo)
    layout.addWidget(spin)
    layout.addWidget(spacing)
    layout.addWidget(row)

    host.resize(640, 320)
    host.show()
    app.processEvents()

    theme = get_theme()
    expected_height = resolved_control_height(theme, "md")
    assert combo.height() == expected_height
    assert spin.height() == expected_height
    assert spacing.height() == expected_height
    assert spacing.spin_box.height() == expected_height
    assert row.height() >= combo.height()

    host.close()
    app.processEvents()


def test_interaction_panels_delegate_fixed_heights_to_shared_controls():
    panel_sources = (ROOT / "src/ui/panels").rglob("*.py")

    offenders = [
        str(path.relative_to(ROOT))
        for path in panel_sources
        if "setFixedHeight(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_form_row_exposes_label_width_without_private_field_access():
    _app()
    combo = StyledComboBox()
    row = FormRow("字段", combo, label_width=72)

    try:
        assert row.label_width == 72
        row.set_label_width(96)
        assert row.label_width == 96
    finally:
        row.close()


def test_spacing_input_shows_labels_but_returns_unit_values():
    _app()
    widget = SpacingInput(
        unit="pt",
        units=(("pt", "磅"), ("lines", "行"), ("auto", "自动")),
        parent=None,
    )
    try:
        widget.set_value(2.0, "lines")

        assert widget.unit() == "lines"
        assert widget.unit_combo.currentText() == "行"
    finally:
        widget.close()


def test_spacing_input_inline_unit_mode_matches_indent_unit_combo_style():
    _app()
    widget = SpacingInput(
        unit="pt",
        units=(("pt", "磅"), ("lines", "行"), ("cm", "cm")),
        unit_inline=True,
        parent=None,
    )
    try:
        widget.set_value(1.0, "pt")

        assert widget.unit_combo.property("inline") == "true"
        assert widget.unit_combo.currentText() == "磅"
        assert widget.unit() == "pt"
    finally:
        widget.close()


def test_heading_panel_fixed_layout_shows_all_sections():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    panel.on_template_changed(TemplateConfig())
    panel.resize(1280, 900)
    panel.show()
    app.processEvents()

    # All sections visible — no mode switching
    assert panel._summary_card.isVisible()
    assert panel._scheme_section.isVisible()
    assert panel._level_editor_card.isVisible()
    assert panel._nn_section is not None

    panel.close()
    app.processEvents()


def test_heading_panel_non_numbered_heading_style_source_can_be_customized():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()
        panel._nn_section.set_expanded(True)
        app.processEvents()

        custom_index = panel._nn_style_mode_combo.findData("custom")
        panel._nn_style_mode_combo.setCurrentIndex(custom_index)
        app.processEvents()

        assert panel._adapter.get_non_numbered_heading_style_mode() == "custom"
        assert panel._adapter.has_non_numbered_heading_style_override() is True
        assert panel._nn_style_editor.isHidden() is False
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_level_selection_syncs_detail_pane():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    panel.on_template_changed(TemplateConfig())
    panel.resize(1280, 900)
    panel.show()
    app.processEvents()

    # Select level 2
    if panel._adv_list.count() >= 2:
        panel._adv_list.setCurrentRow(1)
        app.processEvents()
        assert panel._selected_adv_level == 2
        assert "级别 2" in panel._detail_title.text()

    panel.close()
    app.processEvents()


def test_heading_panel_inspector_defaults_to_summaries_with_expandable_editors():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    panel.on_template_changed(TemplateConfig())
    panel.resize(1280, 900)
    panel.show()
    app.processEvents()

    assert panel._result_heading_label.isVisible()
    assert panel._style_summary_primary.isVisible()
    assert panel._expert_summary_primary.isVisible()
    assert panel._core_style_cb.isVisible()
    assert not panel._style_editor_container.isVisible()
    assert not panel._expert_editor_container.isVisible()

    panel._style_toggle_btn.click()
    app.processEvents()
    assert panel._style_editor_container.isVisible()

    panel._expert_toggle_btn.click()
    app.processEvents()
    assert panel._expert_editor_container.isVisible()

    # No override action buttons should exist
    assert not hasattr(panel, '_numbering_action_btn')
    assert not hasattr(panel, '_style_action_btn')

    panel.close()
    app.processEvents()


def test_heading_panel_detail_rows_keep_text_to_control_gap_compact():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        row_map = {row.widget: row for row in panel.findChildren(FormRow)}
        widgets = [
            panel._level_enabled_switch,
            panel._core_style_cb,
            panel._prefix_edit,
            panel._suffix_edit,
            panel._chain_cb,
            panel._chain_sep_edit,
            panel._toc_switch,
            panel._start_at_input,
            panel._ref_style_cb,
            panel._title_sep_edit,
        ]

        for widget in widgets:
            row = row_map[widget]
            layout_gap = row.layout().spacing()
            text_width = row.preferred_label_width()
            visible_gap = row.widget.x() - text_width
            assert layout_gap == 4
            assert visible_gap <= 20
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_uses_shared_template_form_row_baseline():
    source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    assert "from src.shared.ui.form_row import FormRow" not in source
    assert "FormRow(" not in source
    assert "InspectorForm(" in source
    assert "template_form_row(" in source
    assert "template_form_pair_row(" in source
    assert "_build_pair_row(" not in source


def test_heading_panel_combo_and_input_controls_share_same_height():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        assert panel._preset_cb.height() == panel._levels_input.height()
        assert panel._levels_input.spin_box.height() == panel._levels_input.height()
        assert panel._ref_style_cb.height() == panel._title_sep_edit.height()
        assert panel._core_style_cb.height() == panel._prefix_edit.height()
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_scheme_rows_share_inspector_form_label_scope():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        assert panel._preset_row.label_width == panel._levels_row.label_width
        assert panel._preset_row.widget.x() == panel._levels_row.widget.x()
        assert panel._levels_row.label_width >= panel._levels_row.preferred_label_width()
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_title_separator_reuses_visible_whitespace_preset_control():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        # Default template uses full-width space, which should be shown as a visible symbol.
        assert panel._title_sep_edit.text() == "\u3000"
        assert panel._title_sep_edit._mode_combo.lineEdit().text() == "□"
        assert panel._title_sep_edit.maximumWidth() <= 176

        panel._title_sep_edit.setRawText("\t")
        app.processEvents()
        assert panel._title_sep_edit.text() == "\t"
        assert panel._title_sep_edit._mode_combo.lineEdit().text() == "➡"
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_title_separator_change_refreshes_inline_preview():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        panel._adapter.set_binding_field(1, "enabled", True)
        panel._sync_detail_pane()
        app.processEvents()

        custom_index = panel._title_sep_edit._mode_combo.findData("custom")
        panel._title_sep_edit._mode_combo.setCurrentIndex(custom_index)
        app.processEvents()

        panel._title_sep_edit._edit.setRawText("::")
        app.processEvents()

        assert panel._adapter.get_binding(1).title_separator == "::"
        assert "::" in panel._inline_preview._text
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_reference_style_hint_explains_descendant_usage():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        panel._adapter.set_binding_field(1, "enabled", True)
        panel._adapter.set_binding_field(2, "enabled", True)
        panel._adapter.set_binding_field(2, "chain", "parent.current")
        panel._rebuild_level_list()
        app.processEvents()

        roman_index = panel._ref_style_cb.findData("roman_lower")
        panel._ref_style_cb.setCurrentIndex(roman_index)
        app.processEvents()

        assert panel._adapter.get_binding(1).reference_core_style == "roman_lower"
        assert "被下级引用时" in panel._ref_style_hint_label.text()
        assert "i" in panel._ref_style_hint_label.text()
        assert "级别 2" in panel._ref_style_hint_label.text()
        assert "i.1" in panel._ref_style_hint_label.text()
    finally:
        panel.close()
        app.processEvents()


def test_adaptive_pair_row_stacks_when_narrow():
    app = _app()
    left = FormRow("中文字体", FontCombo(lang="cn"), parent=None)
    right = FormRow("英文字体", FontCombo(lang="en"), parent=None)
    row = AdaptivePairRow(left, right)

    row.resize(420, 200)
    row.show()
    app.processEvents()

    assert right.geometry().top() > left.geometry().top()

    row.resize(1280, 200)
    app.processEvents()

    assert abs(right.geometry().top() - left.geometry().top()) <= 4

    row.close()
    app.processEvents()


def test_style_detail_pairs_stack_when_editor_width_is_narrow():
    app = _app()
    detail = StyleDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(360, 900)
        detail.show()
        app.processEvents()

        left_row = detail._font_cn.parent()
        right_row = detail._size_combo.parent()
        left_top = left_row.mapTo(detail, left_row.rect().topLeft()).y()
        right_top = right_row.mapTo(detail, right_row.rect().topLeft()).y()

        assert right_top > left_top
    finally:
        detail.close()
        app.processEvents()

def test_reference_detail_pairs_stack_when_editor_width_is_narrow():
    app = _app()
    detail = ReferenceDetail()

    try:
        detail.set_template(TemplateConfig())
        detail._mode_switch.set_current_index(1)
        detail.resize(560, 900)
        detail.show()
        app.processEvents()

        left_row = detail._font_cn.parent()
        right_row = detail._size_combo.parent()
        left_top = left_row.mapTo(detail, left_row.rect().topLeft()).y()
        right_top = right_row.mapTo(detail, right_row.rect().topLeft()).y()

        assert right_top > left_top
    finally:
        detail.close()
        app.processEvents()
