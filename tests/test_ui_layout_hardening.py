import sys
from pathlib import Path

from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.template import StyleConfig, TemplateConfig
from src.qt_api import QApplication, QComboBox, QLineEdit, QPoint, QPushButton, Qt, QVBoxLayout, QWidget
from src.shared.ui.adaptive_pair_row import AdaptivePairRow
from src.shared.ui.font_combo import FontCombo
from src.shared.ui.form_row import FormRow
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.form_action_row import FormActionButtonRow
from src.shared.ui.icon_button import apply_icon_button_style
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.file_drop_zone import FileDropZone
from src.shared.ui.option_toggle_chip import OptionToggleChip
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.search_input import SearchInput
from src.shared.ui.style_editing_section import StyleEditingSection
from src.shared.ui.style_owner_state import template_body_style_owner_state
from src.shared.ui.style_owner_toolbar import StyleOwnerOption
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.template_form_layout import TemplateFormGrid
from src.qt_api import QLabel
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import DARK, LIGHT, get_theme, set_theme
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.ui.panels.template_style_detail import StyleDetail
from src.ui.panels.template_table_detail import TableCaptionDetail


def _app():
    return QApplication.instance() or QApplication([])


def _dark_sample_count(widget: QWidget) -> int:
    image = widget.grab().toImage()
    dark_samples = 0
    y_step = max(1, image.height() // 80)
    x_step = max(1, image.width() // 80)
    for y in range(0, image.height(), y_step):
        for x in range(0, image.width(), x_step):
            color = image.pixelColor(x, y)
            if color.alpha() and color.red() + color.green() + color.blue() < 650:
                dark_samples += 1
    return dark_samples


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


def test_all_shared_md_controls_use_one_outer_height_without_clipping():
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    theme = get_theme()
    expected_height = resolved_control_height(theme, "md")

    line_edit = QLineEdit(host)
    line_edit.setStyleSheet(build_text_input_stylesheet(theme))
    button = QPushButton("Action", host)
    apply_button_variant(button, "secondary")
    button.setStyleSheet(build_button_stylesheet(theme))
    combo = QComboBox(host)
    combo.addItem("Option")
    combo.setStyleSheet(build_text_input_stylesheet(theme, selector="QComboBox"))
    styled_combo = StyledComboBox(host)
    styled_combo.addItem("Option")
    styled_spin = StyledSpinBox(host)
    search = SearchInput(parent=host)
    spacing = SpacingInput(show_unit=False, parent=host)
    folder = FolderPicker(parent=host)
    drop_zone = FileDropZone(parent=host)
    actions = FormActionButtonRow(host)
    action_button = actions.add_button("Action")
    icon_button = QPushButton(host)
    apply_icon_button_style(icon_button, size=34, icon_size=16)

    controls = [
        line_edit,
        button,
        combo,
        styled_combo,
        styled_spin,
        search,
        spacing,
        folder._path,
        folder._btn,
        drop_zone._file_input,
        drop_zone._browse_button,
        drop_zone._recent_combo,
        action_button,
    ]
    for control in controls:
        apply_size_class(control, "md")
    for widget in (
        line_edit,
        button,
        combo,
        styled_combo,
        styled_spin,
        search,
        spacing,
        folder,
        drop_zone,
        actions,
        icon_button,
    ):
        layout.addWidget(widget)

    try:
        host.resize(760, 900)
        host.show()
        app.processEvents()

        for control in controls:
            assert control.height() == expected_height, type(control).__name__
            assert control.maximumHeight() >= control.minimumSizeHint().height()
            assert control.height() >= control.minimumSizeHint().height()
        assert folder._path.geometry().bottom() <= folder.rect().bottom()
        assert folder._btn.geometry().bottom() <= folder.rect().bottom()
        assert icon_button.height() == 34
        assert icon_button.width() == 34
        assert icon_button.maximumHeight() >= icon_button.minimumSizeHint().height()
    finally:
        host.close()
        app.processEvents()


def test_shared_control_outer_height_is_stable_across_theme_refresh():
    app = _app()
    controls = [StyledComboBox(), StyledSpinBox(), SearchInput(), FolderPicker()]
    try:
        for theme in (DARK, LIGHT):
            set_theme(theme)
            app.processEvents()
            expected = resolved_control_height(theme, "md")
            for control in controls:
                control.show()
            app.processEvents()
            for control in controls:
                assert control.height() == expected
                assert control.maximumHeight() >= control.minimumSizeHint().height()
    finally:
        set_theme(LIGHT)
        for control in controls:
            control.close()
        app.processEvents()


def test_every_size_class_and_button_variant_resolves_to_outer_height():
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    theme = get_theme()
    controls: list[tuple[QWidget, str]] = []

    for size in ("sm", "md", "lg"):
        line_edit = QLineEdit(host)
        line_edit.setStyleSheet(build_text_input_stylesheet(theme))
        combo = StyledComboBox(host)
        combo.addItem("Option")
        spin = StyledSpinBox(host)
        search = SearchInput(parent=host)
        for control in (line_edit, combo, spin, search):
            apply_size_class(control, size)
            controls.append((control, size))
            layout.addWidget(control)

        for variant in (
            "primary",
            "secondary",
            "danger",
            "ghost-danger",
            "ghost-primary",
        ):
            button = QPushButton(variant, host)
            apply_button_variant(button, variant)
            button.setStyleSheet(build_button_stylesheet(theme))
            apply_size_class(button, size)
            controls.append((button, size))
            layout.addWidget(button)

    try:
        host.resize(760, 1200)
        host.show()
        app.processEvents()
        for control, size in controls:
            expected = resolved_control_height(theme, size)
            assert control.height() == expected, (
                type(control).__name__,
                size,
                control.property("variant"),
            )
            assert control.maximumHeight() >= control.minimumSizeHint().height()
    finally:
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
    assert isinstance(panel._nn_section, Card)
    assert panel._nn_section.isVisible()
    assert panel._nn_texts_edit.isVisible()
    assert panel._nn_prefix_edit.isVisible()
    assert panel._nn_style_mode_combo.isVisible()
    assert not hasattr(panel, "_nn_scope_note")
    assert not hasattr(panel._nn_section, "set_expanded")

    panel.close()
    app.processEvents()


def test_heading_panel_card_spacing_uses_template_detail_gap():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()
        app.processEvents()

        expected_gap = get_theme().template_detail_section_gap
        assert panel.layout().spacing() == expected_gap
        assert panel._level_editor_content.layout().spacing() == expected_gap
        assert panel._detail_inspector_panel.layout().spacing() == expected_gap

        assert panel._scheme_section.y() - (
            panel._summary_card.y() + panel._summary_card.height()
        ) == expected_gap
        assert panel._level_editor_card.y() - (
            panel._scheme_section.y() + panel._scheme_section.height()
        ) == expected_gap
        assert panel._nn_section.y() - (
            panel._level_editor_card.y() + panel._level_editor_card.height()
        ) == expected_gap

        level_content_layout = panel._level_editor_content.layout()
        sidebar = level_content_layout.itemAt(0).widget()
        detail_panel = level_content_layout.itemAt(1).widget()
        assert detail_panel.x() - (sidebar.x() + sidebar.width()) == expected_gap

        detail_layout = panel._detail_inspector_panel.layout()
        result_strip = detail_layout.itemAt(1).widget()
        first_block = detail_layout.itemAt(2).widget()
        assert first_block.y() - (result_strip.y() + result_strip.height()) == expected_gap
    finally:
        panel.close()
        app.processEvents()


def test_template_overview_card_spacing_uses_template_detail_gap():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel.resize(1330, 1120)
        panel.show()
        app.processEvents()
        app.processEvents()

        detail = panel._overview_detail
        expected_gap = get_theme().template_detail_section_gap
        assert detail.layout().spacing() == expected_gap
        assert detail._overview_card.y() - (
            detail._selector_card.y() + detail._selector_card.height()
        ) == expected_gap
        assert detail._preview_card.y() - (
            detail._overview_card.y() + detail._overview_card.height()
        ) == expected_gap
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_detail_summaries_keep_three_columns_at_medium_width():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel.resize(1330, 1120)
        panel.show()
        app.processEvents()
        app.processEvents()

        cases = [
            ("tpl_page", ("paper_layout", "margin_gutter", "header_footer")),
            ("tpl_style", ("text", "paragraph", "spacing")),
            ("tpl_heading", ("scheme", "level_preview", "special_rules")),
            ("tpl_table", ("border", "width", "type")),
            ("tpl_caption", ("caption_text", "numbering_rules", "caption_style")),
        ]
        for card_id, keys in cases:
            panel._show_detail(card_id)
            app.processEvents()
            app.processEvents()
            app.processEvents()

            detail = panel._details.current_detail
            grid = detail._summary_grid
            assert 900 <= grid.width() < 1160
            assert grid._render_columns == 6
            assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles[keys[0]]
            assert grid._layout.itemAtPosition(0, 2).widget() is grid._tiles[keys[1]]
            assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles[keys[2]]
            assert grid._layout.itemAtPosition(1, 0) is None
            assert {grid._tiles[key].y() for key in keys} == {0}
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_detail_summary_grids_are_visible_after_refresh():
    app = _app()
    panel = TemplatePanel(PanelBridge())

    try:
        panel.resize(1330, 1120)
        panel.show()
        app.processEvents()
        app.processEvents()

        for card_id in (
            "tpl_page",
            "tpl_style",
            "tpl_heading",
            "tpl_table",
            "tpl_header_footer",
            "tpl_toc",
            "tpl_caption",
        ):
            panel._show_detail(card_id)
            app.processEvents()
            app.processEvents()
            app.processEvents()

            detail = panel._details.current_detail
            grid = detail._summary_grid
            assert grid.isVisible()
            assert len(grid.items()) > 0
            assert all(tile.isVisible() for tile in grid._tiles.values())
            assert detail._summary_card.height() > detail._summary_card.header.height()
    finally:
        panel.close()
        app.processEvents()


def test_table_summary_compacts_long_font_name_at_high_dpi_width():
    app = _app()
    detail = TableCaptionDetail()

    try:
        detail.resize(848, 680)
        detail.set_template(TemplateConfig())
        detail.show()
        app.processEvents()
        app.processEvents()

        grid = detail._summary_grid
        tile = grid._tiles["type"]
        assert 720 <= grid.width() < 1160
        assert grid._render_columns == 6
        assert tile.item.value == "微软雅黑 / Times New Roman"
        assert tile._value.wordWrap() is False
        assert tile._value.text().endswith("Times...")
        assert "New" not in tile._value.text()
        assert "Roman" not in tile._value.text()
    finally:
        detail.close()
        app.processEvents()


def test_heading_summary_keeps_three_columns_at_high_dpi_screenshot_width():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(848, 900)
        panel.show()
        app.processEvents()
        app.processEvents()

        grid = panel._summary_grid
        assert 720 <= grid.width() < 1160
        assert grid._render_columns == 6
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["scheme"]
        assert grid._layout.itemAtPosition(0, 2).widget() is grid._tiles["level_preview"]
        assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles["special_rules"]
        assert grid._layout.itemAtPosition(1, 0) is None
        assert {grid._tiles[key].y() for key in ("scheme", "level_preview", "special_rules")} == {0}
    finally:
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


def test_heading_panel_inspector_keeps_heading_style_visible_and_expert_collapsed():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    panel.on_template_changed(TemplateConfig())
    panel.resize(1280, 900)
    panel.show()
    app.processEvents()

    assert panel._result_heading_label.isVisible()
    assert not hasattr(panel, "_result_meta_label")
    assert not hasattr(panel, "_detail_hint")
    assert not hasattr(panel, "_style_summary_primary")
    assert not hasattr(panel, "_expert_summary_primary")
    assert panel._core_style_cb.isVisible()
    assert panel._style_editor_container.isVisible()
    assert not hasattr(panel, "_style_toggle_btn")
    assert not panel._expert_editor_container.isVisible()

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
            panel._start_at_input,
            panel._restart_on_cb,
            panel._ref_style_cb,
            panel._title_sep_edit,
        ]

        for widget in widgets:
            row = row_map[widget]
            layout_gap = row.layout().spacing()
            label_width = row.label_width or row.preferred_label_width()
            visible_gap = row.widget.x() - label_width
            assert layout_gap == 4
            assert visible_gap <= 20
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_numbering_composition_uses_responsive_form_grid():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()
        panel._adv_list.setCurrentRow(1)
        app.processEvents()
        app.processEvents()

        row_map = {row.widget: row for row in panel.findChildren(FormRow)}
        pairs = [
            (row_map[panel._level_enabled_switch], row_map[panel._core_style_cb]),
            (row_map[panel._prefix_edit], row_map[panel._suffix_edit]),
            (row_map[panel._chain_cb], row_map[panel._ref_style_cb]),
        ]

        for left_row, right_row in pairs:
            assert isinstance(left_row.parentWidget(), AdaptivePairRow)
            assert left_row.parentWidget() is right_row.parentWidget()
            left_pos = left_row.mapTo(panel, left_row.rect().topLeft())
            right_pos = right_row.mapTo(panel, right_row.rect().topLeft())
            assert left_pos.y() == right_pos.y()
            assert left_pos.x() < right_pos.x()
            assert left_row.height() == 44
            assert right_row.height() == 44

        # The inspector's current master/detail split keeps the form inline at
        # 760 px; use its actual narrow floor to exercise the stacked mode.
        panel.resize(600, 900)
        app.processEvents()
        app.processEvents()

        for left_row, right_row in pairs:
            left_pos = left_row.mapTo(panel, left_row.rect().topLeft())
            right_pos = right_row.mapTo(panel, right_row.rect().topLeft())
            assert left_pos.x() == right_pos.x()
            assert right_pos.y() > left_pos.y()
            assert left_row.parentWidget().height() == 88
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_level_inspector_rows_use_44px_form_rhythm():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()
        app.processEvents()

        panel._adv_list.setCurrentRow(1)
        app.processEvents()

        row_map = {row.widget: row for row in panel.findChildren(FormRow)}
        row_widgets = [
            panel._level_enabled_switch,
            panel._core_style_cb,
            panel._prefix_edit,
            panel._suffix_edit,
            panel._chain_cb,
            panel._chain_sep_edit,
            panel._start_at_input,
            panel._restart_on_cb,
            panel._ref_style_cb,
            panel._title_sep_edit,
            panel._hd_font_cn,
            panel._hd_font_en,
            panel._hd_size_combo,
            panel._hd_emphasis_widget,
            panel._hd_alignment,
            panel._hd_line_type,
            panel._hd_line_value,
            panel._hd_space_before,
            panel._hd_space_after,
        ]
        for widget in row_widgets:
            assert row_map[widget].height() == 44

        control_widgets = [
            panel._core_style_cb,
            panel._prefix_edit,
            panel._suffix_edit,
            panel._chain_cb,
            panel._chain_sep_edit,
            panel._start_at_input,
            panel._restart_on_cb,
            panel._ref_style_cb,
            panel._title_sep_edit,
            panel._hd_font_cn,
            panel._hd_font_en,
            panel._hd_size_combo,
            panel._hd_emphasis_widget,
            panel._hd_alignment,
            panel._hd_line_type,
            panel._hd_line_value,
            panel._hd_space_before,
            panel._hd_space_after,
        ]
        expected_control_height = resolved_control_height(get_theme(), "md")
        for widget in control_widgets:
            assert widget.height() == expected_control_height

        assert panel._hd_bold.parentWidget().height() == expected_control_height
        assert panel._hd_italic.parentWidget().height() == expected_control_height

        assert panel._level_enabled_switch.height() == 24
        assert len(panel._numbering_grid._pair_rows) == 3
        for pair_row in panel._numbering_grid._pair_rows:
            assert isinstance(pair_row, AdaptivePairRow)
            assert pair_row.height() == 44
            assert pair_row.minimumHeight() == 44
        assert panel._numbering_grid.minimumSizeHint().height() == 132
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_heading_style_grid_uses_zero_stacked_spacing():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(760, 900)
        panel.show()
        app.processEvents()
        app.processEvents()
        panel._adv_list.setCurrentRow(1)
        app.processEvents()
        app.processEvents()

        for pair_row in panel._style_block.findChildren(AdaptivePairRow):
            assert pair_row._stacked_spacing == 0
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_uses_shared_template_form_row_baseline():
    source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    assert "from src.shared.ui.form_row import FormRow" not in source
    assert "FormRow(" not in source
    assert "InspectorForm(" in source
    assert "template_form_row(" in source
    assert "TemplateFormGrid" in source
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

        # Default template uses full-width space, shown with a readable label.
        assert panel._title_sep_edit.text() == "\u3000"
        assert panel._title_sep_edit._mode_combo.lineEdit().text() == "全角空格 (□)"
        assert panel._title_sep_edit.minimumWidth() >= panel._title_sep_edit.sizeHint().width()

        panel._title_sep_edit.setRawText("\t")
        app.processEvents()
        assert panel._title_sep_edit.text() == "\t"
        assert panel._title_sep_edit._mode_combo.lineEdit().text() == "制表符 (➡)"
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_chain_separator_uses_presets_with_custom_fallback():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(create_builtin_template("default"))
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        panel._adv_list.setCurrentRow(1)
        app.processEvents()

        assert panel._chain_sep_lbl_row.isVisible()
        assert panel._chain_sep_edit.text() == "."
        assert panel._chain_sep_edit._mode_combo.lineEdit().text() == "小数点 (.)"

        hyphen_index = panel._chain_sep_edit._mode_combo.findData("hyphen")
        panel._chain_sep_edit._mode_combo.setCurrentIndex(hyphen_index)
        app.processEvents()

        assert panel._chain_sep_edit.text() == "-"
        assert panel._adapter.get_binding(2).chain_separator == "-"

        custom_index = panel._chain_sep_edit._mode_combo.findData("custom")
        panel._chain_sep_edit._mode_combo.setCurrentIndex(custom_index)
        app.processEvents()
        panel._chain_sep_edit._edit.setRawText("/")
        app.processEvents()

        assert panel._chain_sep_edit.text() == "/"
        assert panel._adapter.get_binding(2).chain_separator == "/"
    finally:
        panel.close()
        app.processEvents()


def test_heading_panel_restart_counting_uses_mode_and_trigger_level_controls():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(1280, 900)
        panel.show()
        app.processEvents()

        panel._adv_list.setCurrentRow(1)
        app.processEvents()

        specific_index = panel._restart_on_cb.findData("specific")
        panel._restart_on_cb.setCurrentIndex(specific_index)
        app.processEvents()

        assert panel._restart_trigger_row.isVisible()
        assert panel._adapter.get_binding(2).restart_on == "heading1"

        document_index = panel._restart_on_cb.findData("document")
        panel._restart_on_cb.setCurrentIndex(document_index)
        app.processEvents()

        assert not panel._restart_trigger_row.isVisible()
        assert panel._adapter.get_binding(2).restart_on == "document"
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


def test_heading_panel_reference_style_hint_text_is_removed():
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
        assert not hasattr(panel, "_ref_style_hint_label")
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


def test_adaptive_pair_row_can_use_separate_stacked_spacing():
    app = _app()
    left = FormRow("中文字体", FontCombo(lang="cn"), parent=None)
    right = FormRow("英文字体", FontCombo(lang="en"), parent=None)
    row = AdaptivePairRow(left, right, spacing=12, stacked_spacing=0)

    row.resize(420, 200)
    row.show()
    app.processEvents()

    assert right.geometry().top() > left.geometry().top()
    assert row.layout().spacing() == 0

    row.resize(1280, 200)
    app.processEvents()

    assert row.layout().spacing() == 12

    row.close()
    app.processEvents()


def test_adaptive_pair_row_defaults_to_zero_stacked_spacing():
    app = _app()
    left = FormRow("Left", FontCombo(lang="cn"), parent=None)
    right = FormRow("Right", FontCombo(lang="en"), parent=None)
    row = AdaptivePairRow(left, right, spacing=12)

    row.resize(420, 200)
    row.show()
    app.processEvents()

    assert right.geometry().top() > left.geometry().top()
    assert row.layout().spacing() == 0

    row.close()
    app.processEvents()


def test_adaptive_pair_row_can_opt_back_into_inline_stacked_spacing():
    app = _app()
    left = FormRow("Left", FontCombo(lang="cn"), parent=None)
    right = FormRow("Right", FontCombo(lang="en"), parent=None)
    row = AdaptivePairRow(left, right, spacing=12, stacked_spacing=None)

    row.resize(420, 200)
    row.show()
    app.processEvents()

    assert right.geometry().top() > left.geometry().top()
    assert row.layout().spacing() == 12

    row.close()
    app.processEvents()


def test_template_form_grid_coordinates_responsive_mode_across_rows():
    app = _app()
    compact_left = QWidget()
    compact_right = QWidget()
    wide_left = QWidget()
    wide_right = QWidget()
    for widget, width in (
        (compact_left, 80),
        (compact_right, 80),
        (wide_left, 180),
        (wide_right, 180),
    ):
        widget.setMinimumSize(width, 36)

    grid = TemplateFormGrid(
        [
            [compact_left, compact_right],
            [wide_left, wide_right],
        ],
        column_gap=12,
    )

    try:
        grid.resize(300, 200)
        grid.show()
        app.processEvents()

        assert all(row._forced_stacked is True for row in grid._pair_rows)

        grid.resize(420, 200)
        app.processEvents()

        assert all(row._forced_stacked is False for row in grid._pair_rows)
    finally:
        grid.close()
        app.processEvents()


def test_heading_style_uses_canonical_pairs_and_keeps_spacing_inline_at_desktop_width():
    app = _app()
    panel = HeadingNumberingPanel(PanelBridge())

    try:
        panel.on_template_changed(TemplateConfig())
        panel.resize(760, 900)
        panel.show()
        app.processEvents()
        app.processEvents()

        row_map = {row.widget: row for row in panel.findChildren(FormRow)}
        assert panel._style_grid._rows[:2] == [
            (row_map[panel._hd_font_cn], row_map[panel._hd_size_combo]),
            (row_map[panel._hd_font_en], row_map[panel._hd_emphasis_widget]),
        ]

        paired_rows = [
            (row_map[panel._hd_font_cn], row_map[panel._hd_size_combo]),
            (row_map[panel._hd_font_en], row_map[panel._hd_emphasis_widget]),
            (row_map[panel._hd_line_type], row_map[panel._hd_line_value]),
            (row_map[panel._hd_space_before], row_map[panel._hd_space_after]),
        ]
        for left_row, right_row in paired_rows:
            left_y = left_row.mapTo(panel, left_row.rect().topLeft()).y()
            right_y = right_row.mapTo(panel, right_row.rect().topLeft()).y()
            assert left_y == right_y
    finally:
        panel.close()
        app.processEvents()


def test_style_editing_section_renders_chrome_preview_and_surface_in_order():
    app = _app()
    shell = StyleEditingSection(
        object_name_prefix="layout_style_editing",
        owner_options=(
            StyleOwnerOption("body", "正文"),
            StyleOwnerOption("references_body", "参考文献"),
        ),
        owner_title="编辑样式",
        selector_label="编辑对象",
        action_label="恢复",
    )

    class PreviewProjection:
        sample_text = "正文样式预览：中文、English、数字 123。"
        source_label = "模板默认样式"
        detail = "宋体 / Times New Roman / 12 磅"
        font_cn = "宋体"
        font_en = "Times New Roman"
        size_pt = 12.0
        bold = False
        italic = False
        alignment = "justify"
        line_spacing_value = 1.5
        left_indent_pt = 0.0
        right_indent_pt = 0.0
        first_indent_pt = 24.0
        hanging_indent_pt = 0.0
        space_before_pt = 0.0
        space_after_pt = 6.0

    try:
        shell.apply_owner_state(
            template_body_style_owner_state(
                StyleConfig(font_cn="宋体", font_en="Times New Roman", size_pt=12)
            )
        )
        shell.apply_preview_projection(PreviewProjection())
        shell.resize(920, 980)
        shell.show()
        app.processEvents()
        app.processEvents()

        assert shell.owner_toolbar is not None
        assert shell.owner_status is not None
        assert shell.preview is not None
        assert shell.chrome_widget.isVisible()
        assert shell.style_surface.isVisible()

        status_bottom = (
            shell.owner_status.mapTo(shell, QPoint(0, 0)).y()
            + shell.owner_status.height()
        )
        toolbar_top = shell.owner_toolbar.mapTo(shell, QPoint(0, 0)).y()
        toolbar_bottom = (
            shell.owner_toolbar.mapTo(shell, QPoint(0, 0)).y()
            + shell.owner_toolbar.height()
        )
        preview_top = shell.preview.mapTo(shell, QPoint(0, 0)).y()
        preview_bottom = preview_top + shell.preview.height()
        surface_top = shell.style_surface.mapTo(shell, QPoint(0, 0)).y()

        assert toolbar_top >= status_bottom
        assert preview_top >= toolbar_bottom
        assert surface_top > preview_bottom
        assert _dark_sample_count(shell) > 20
    finally:
        shell.close()
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


def test_style_detail_uses_global_stacked_spacing_and_compact_emphasis():
    app = _app()
    detail = StyleDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(760, 900)
        detail.show()
        app.processEvents()
        app.processEvents()

        theme = get_theme()
        assert detail.layout().spacing() == theme.template_detail_section_gap
        assert detail._editor_column.layout().spacing() == theme.template_detail_section_gap

        assert detail.findChildren(AdaptivePairRow)
        for pair_row in detail.findChildren(AdaptivePairRow):
            assert pair_row._stacked_spacing == 0

        expected_control_height = resolved_control_height(theme, "md")
        row_map = {row.widget: row for row in detail.findChildren(FormRow)}
        for widget in (
            detail._font_cn,
            detail._font_en,
            detail._size_combo,
            detail._alignment_combo,
            detail._line_type_combo,
            detail._line_value,
            detail._space_before,
            detail._space_after,
        ):
            assert row_map[widget].height() == 44

        emphasis = detail._bold_switch.parentWidget().parentWidget()
        assert row_map[emphasis].height() == 44
        assert emphasis.height() == expected_control_height
        for chip in emphasis.findChildren(OptionToggleChip):
            assert chip.height() == expected_control_height
            assert chip.sizeHint().height() == expected_control_height
    finally:
        detail.close()
        app.processEvents()


def test_reference_detail_pairs_stack_when_editor_width_is_narrow():
    app = _app()
    detail = ReferenceDetail()

    try:
        detail.set_template(TemplateConfig())
        detail._mode_combo.setCurrentIndex(1)
        detail.resize(480, 900)
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
