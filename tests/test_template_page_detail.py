import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.loader import load_template, save_template
from src.config.template import SectionMarginConfig, TemplateConfig
from src.qt_api import QApplication, Qt
from src.shared.ui import DashedSeparator, SummaryGrid
from src.shared.ui.form_row import FormRow
from src.shared.ui.theme import get_theme
from src.shared.ui.toast import Toast
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels.template_caption_detail import CaptionDetail
from src.ui.panels.template_elements_detail import ElementsDetail
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_panel import TemplatePanel
from src.ui.panels.template_reference_detail import ReferenceDetail
from src.ui.panels.template_style_detail import StyleDetail
from src.ui.panels.template_table_detail import TableCaptionDetail


def _app():
    return QApplication.instance() or QApplication([])


def test_page_setup_detail_syncs_widget_values_from_template():
    _app()
    detail = PageSetupDetail()
    template = TemplateConfig()
    template.page_setup.paper_size = "A3"
    template.page_setup.orientation = "landscape"
    template.page_setup.margin.top_cm = 2.5
    template.page_setup.gutter_cm = 0.8
    template.page_setup.header_distance_cm = 1.6
    template.section.section_break_type = "nextPage"

    try:
        detail.set_template(template)

        assert detail._paper_combo.currentData() == "A3"
        assert detail._orient_landscape_btn.isChecked() is True
        assert detail._orient_portrait_btn.isChecked() is False
        assert detail._page_inputs["top_cm"].value() == 2.5
        assert detail._page_inputs["gutter_cm"].value() == 0.8
        assert detail._page_inputs["header_distance_cm"].value() == 1.6
        assert detail._section_break_combo.currentData() == "nextPage"
        assert detail._paper_by_section_row.isHidden() is True
        assert detail._orientation_by_section_row.isHidden() is True
        assert isinstance(detail._summary_grid, SummaryGrid)
        assert detail._summary_grid._tile_style == "module"
        assert len(detail._summary_grid.items()) == 3
        summary_items = {item.key: item for item in detail._summary_grid.items()}
        assert summary_items["paper_layout"].icon_name == "layout"
        assert summary_items["margin_gutter"].icon_name == "scan"
        assert summary_items["header_footer"].icon_name == "panel-top"
        assert detail._summary_grid.value_for("paper_layout") == "A3 / 横向"
        assert (
            detail._summary_grid.detail_for("paper_layout")
            == "模板纸张 / 保留源方向 / 语义分节"
        )
        assert summary_items["paper_layout"].column_span == 4
        assert summary_items["margin_gutter"].label == "页边距"
        assert summary_items["margin_gutter"].column_span == 4
        assert detail._summary_grid.value_for("margin_gutter") == "上下 2.5/3.8 cm"
        assert (
            detail._summary_grid.detail_for("margin_gutter")
            == "左右 3.2/3.2 cm / 装订 0.8 cm / 模板边距"
        )
        assert "装订线 0.8 cm" in summary_items["margin_gutter"].tooltip
        assert summary_items["header_footer"].label == "页眉页脚"
        assert summary_items["header_footer"].column_span == 4
        assert detail._summary_grid.value_for("header_footer") == "页眉/页脚 1.6/3 cm"
        assert detail._summary_grid.detail_for("header_footer") == "链接按语义重建"
        assert summary_items["margin_gutter"].detail_emphasis is True
        assert summary_items["header_footer"].detail_emphasis is True
    finally:
        detail.close()


def test_page_setup_detail_round_trips_all_section_layout_policies():
    app = _app()
    detail = PageSetupDetail()
    template = TemplateConfig()
    template.page_setup.paper_size_mode = "per_section"
    template.page_setup.paper_size_by_section = {
        "body": "A4",
        "appendix": "A3",
    }
    template.page_setup.orientation_mode = "per_section"
    template.page_setup.orientation_by_section = {
        "body": "portrait",
        "appendix": "landscape",
    }
    template.page_setup.margin_mode = "per_section"
    template.page_setup.margin_by_section = {
        "appendix": SectionMarginConfig(
            top_cm=2.0,
            bottom_cm=2.1,
            left_cm=2.2,
            right_cm=2.3,
            gutter_cm=0.4,
            header_distance_cm=0.8,
            footer_distance_cm=0.9,
        )
    }
    template.section.boundary_mode = "normalize_all"
    template.section.section_break_type = "oddPage"
    template.section.empty_break_policy = "remove_proven_redundant"
    template.section.caption_table_break_policy = "remove_proven_redundant"
    template.section.header_footer_link_mode = "preserve_source"

    try:
        detail.set_template(template)

        assert detail._paper_mode_combo.currentData() == "per_section"
        assert detail._paper_by_section_row.isHidden() is False
        assert detail._paper_by_section_edit.isEnabled() is True
        assert detail._paper_by_section_edit.text() == "body=A4, appendix=A3"
        assert detail._orientation_mode_combo.currentData() == "per_section"
        assert detail._orientation_by_section_row.isHidden() is False
        assert detail._orientation_by_section_edit.isEnabled() is True
        assert detail._orientation_by_section_edit.text() == (
            "body=portrait, appendix=landscape"
        )
        assert detail._margin_mode_combo.currentData() == "per_section"
        assert detail._margin_by_section_edit.isEnabled() is True
        assert detail._margin_by_section_edit.text() == (
            "appendix=2,2.1,2.2,2.3,0.4,0.8,0.9"
        )
        assert detail._section_break_combo.currentData() == "oddPage"
        assert detail._empty_break_policy_combo.currentData() == (
            "remove_proven_redundant"
        )
        assert detail._caption_table_break_policy_combo.currentData() == (
            "remove_proven_redundant"
        )
        assert detail._header_footer_link_mode_combo.currentData() == (
            "preserve_source"
        )

        detail._paper_by_section_edit.setText("body=B5, 2=A3")
        detail._orientation_by_section_edit.setText(
            "body=landscape, 2=portrait"
        )
        detail._margin_by_section_edit.setText(
            "2=1,1.1,1.2,1.3,0.2,0.6,0.7"
        )
        detail._header_footer_link_mode_combo.setCurrentIndex(
            detail._header_footer_link_mode_combo.findData("semantic_rebuild")
        )
        detail._section_break_combo.setCurrentIndex(
            detail._section_break_combo.findData("evenPage")
        )
        app.processEvents()

        assert template.page_setup.paper_size_by_section == {
            "body": "B5",
            "2": "A3",
        }
        assert template.page_setup.orientation_by_section == {
            "body": "landscape",
            "2": "portrait",
        }
        assert template.page_setup.margin_by_section["2"] == SectionMarginConfig(
            top_cm=1.0,
            bottom_cm=1.1,
            left_cm=1.2,
            right_cm=1.3,
            gutter_cm=0.2,
            header_distance_cm=0.6,
            footer_distance_cm=0.7,
        )
        assert template.section.header_footer_link_mode == "semantic_rebuild"
        assert template.section.section_break_type == "evenPage"
        assert detail.focus_navigation_field(
            "template.page_setup.orientation_by_section"
        )
        assert detail.focus_navigation_field(
            "template.page_setup.paper_size_by_section"
        )
        assert detail.focus_navigation_field(
            "template.page_setup.margin_by_section"
        )
        assert detail.focus_navigation_field(
            "template.section.header_footer_link_mode"
        )
    finally:
        detail.close()
        app.processEvents()


def test_page_setup_detail_blocks_save_for_invalid_or_empty_per_section_map():
    app = _app()
    detail = PageSetupDetail()
    template = TemplateConfig()

    try:
        detail.set_template(template)
        detail.set_save_enabled(True)
        detail._paper_mode_combo.setCurrentIndex(
            detail._paper_mode_combo.findData("per_section")
        )
        app.processEvents()

        assert detail._paper_by_section_row.isHidden() is False
        assert "至少填写一个" in detail._validation_alert.message()
        assert detail._save_btn.isEnabled() is False

        detail._paper_by_section_edit.setText("appendix=TABLOID")
        app.processEvents()
        assert "纸张必须是" in detail._validation_alert.message()
        assert detail._save_btn.isEnabled() is False

        detail._paper_by_section_edit.setText("appendix=A3")
        detail._margin_mode_combo.setCurrentIndex(
            detail._margin_mode_combo.findData("per_section")
        )
        app.processEvents()
        assert "至少填写一个" in detail._validation_alert.message()
        assert detail._save_btn.isEnabled() is False

        detail._margin_by_section_edit.setText("appendix=2,2,2")
        app.processEvents()
        assert "必须填写 7 个数值" in detail._validation_alert.message()
        assert detail._save_btn.isEnabled() is False

        detail._margin_by_section_edit.setText("appendix=2,2,2,2,0,0.8,0.8")
        detail._orientation_mode_combo.setCurrentIndex(
            detail._orientation_mode_combo.findData("per_section")
        )
        app.processEvents()

        assert detail._orientation_by_section_row.isHidden() is False
        assert detail._validation_alert.isHidden() is False
        assert "至少填写一个" in detail._validation_alert.message()
        assert detail._save_btn.isEnabled() is False

        detail._orientation_by_section_edit.setText("appendix=sideways")
        app.processEvents()
        assert "portrait 或 landscape" in detail._validation_alert.message()
        assert detail._save_btn.isEnabled() is False

        detail._orientation_by_section_edit.setText("appendix=landscape")
        app.processEvents()
        assert template.page_setup.orientation_by_section == {
            "appendix": "landscape"
        }
        assert detail._save_btn.isEnabled() is True
    finally:
        detail.close()
        app.processEvents()


def test_per_section_page_layout_survives_strict_save_load(tmp_path):
    template = TemplateConfig()
    template.page_setup.paper_size_mode = "per_section"
    template.page_setup.paper_size_by_section = {"appendix": "A3"}
    template.page_setup.orientation_mode = "per_section"
    template.page_setup.orientation_by_section = {"appendix": "landscape"}
    template.page_setup.margin_mode = "per_section"
    template.page_setup.margin_by_section = {
        "appendix": SectionMarginConfig(
            top_cm=2.0,
            bottom_cm=2.1,
            left_cm=2.2,
            right_cm=2.3,
            gutter_cm=0.4,
            header_distance_cm=0.8,
            footer_distance_cm=0.9,
        )
    }
    target = tmp_path / "section-layout.json"

    save_template(template, target)
    reloaded = load_template(target)

    assert reloaded == template
    assert isinstance(
        reloaded.page_setup.margin_by_section["appendix"],
        SectionMarginConfig,
    )


def test_page_setup_detail_summary_tiles_prefer_single_desktop_row():
    app = _app()
    detail = PageSetupDetail()

    try:
        detail.set_template(TemplateConfig())
        detail.resize(1280, 900)
        detail.show()
        app.processEvents()

        grid = detail._summary_grid
        assert grid._render_columns == 12
        assert grid._layout.itemAtPosition(0, 0).widget() is grid._tiles["paper_layout"]
        assert grid._layout.itemAtPosition(0, 4).widget() is grid._tiles["margin_gutter"]
        assert grid._layout.itemAtPosition(0, 8).widget() is grid._tiles["header_footer"]
    finally:
        detail.close()
        app.processEvents()


def test_page_setup_detail_focus_navigation_field_highlights_page_controls():
    _app()
    detail = PageSetupDetail()
    try:
        detail.set_template(TemplateConfig())

        assert detail.focus_navigation_field("template.page_setup.margin.left_cm")
        assert detail._page_inputs["left_cm"].property("navigation_field_highlight") is True
        assert "左页边距" in detail._page_inputs["left_cm"].toolTip()
        assert (
            "template.page_setup.margin.left_cm"
            not in detail._page_inputs["left_cm"].toolTip()
        )
        assert (
            "template.page_setup.margin.left_cm"
            == detail._page_inputs["left_cm"].property("navigation_field_raw_label")
        )

        assert detail.focus_navigation_field("template.page_setup.header_distance_cm")
        assert (
            detail._page_inputs["header_distance_cm"].property(
                "navigation_field_highlight"
            )
            is True
        )
        assert detail.focus_navigation_field("template.section.section_break_type")
        assert (
            detail._section_break_combo.property("navigation_field_highlight")
            is True
        )
        assert detail.focus_navigation_field("template.page_setup.nope") is False
    finally:
        detail.close()


def test_template_panel_page_setup_edit_updates_preview_and_dirty_state():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    emitted: list[TemplateConfig] = []
    bridge.template_changed.connect(emitted.append)

    try:
        panel._page_detail._page_inputs["top_cm"].set_value(4.5, "cm")
        app.processEvents()

        assert panel._current_template.page_setup.margin.top_cm == 4.5
        assert "4.5" in panel._overview_detail._rows["page"]._value.text()
        assert "4.5" in panel._nav_cards["tpl_page"]._full_subtitle
        assert panel._page_detail._summary_grid.value_for("margin_gutter") == "上下 4.5/3.8 cm"
        assert panel._page_detail._restore_entry_btn.isEnabled() is True
        assert panel._page_detail._save_btn.isEnabled() is True
        assert bridge.is_template_dirty() is True
        assert emitted == []
        assert bridge.current_template().page_setup.margin.top_cm != 4.5
    finally:
        panel.close()
        app.processEvents()


def test_page_setup_detail_reuses_shared_spacing_input_control():
    source = (ROOT / "src/ui/panels/template_page_detail.py").read_text(encoding="utf-8")

    assert "TemplateSummaryCard(" in source
    assert "SpacingInput(" in source
    assert "InspectorForm(" in source
    assert ".add_grid(" in source
    assert "TemplateSplitColumns(" not in source
    assert "def _build_split_form_columns" not in source
    assert "InlineAlert(" in source
    assert 'QPushButton("恢复"' in source
    assert 'QPushButton("保存"' in source
    assert "save_requested = Signal()" in source
    assert 'ThemedRadioButton("纵向"' in source
    assert 'ThemedRadioButton("横向"' in source
    assert "QDoubleSpinBox(" not in source
    assert "tpl_page_apply_btn" not in source
    assert "页面预览" not in source


def test_page_setup_detail_split_columns_use_spacing_without_dashed_separators():
    _app()
    detail = PageSetupDetail()
    try:
        assert not detail.findChildren(DashedSeparator)
    finally:
        detail.close()


def test_page_setup_detail_save_button_emits_save_request():
    _app()
    detail = PageSetupDetail()
    emitted: list[bool] = []

    try:
        detail.set_template(TemplateConfig())
        detail.set_save_enabled(True)
        detail.save_requested.connect(lambda: emitted.append(True))

        detail._save_btn.click()

        assert emitted == [True]
    finally:
        detail.close()


def test_page_setup_detail_split_column_combos_expand_to_fill_available_width():
    app = _app()
    detail = PageSetupDetail()
    detail.set_template(TemplateConfig())
    detail.resize(1280, 980)

    try:
        detail.show()
        app.processEvents()

        assert detail._paper_combo.width() > 300
        assert detail._section_break_combo.width() > 300
    finally:
        detail.close()
        app.processEvents()


def test_page_setup_detail_right_column_form_rows_hug_their_controls():
    app = _app()
    detail = PageSetupDetail()
    detail.set_template(TemplateConfig())
    detail.resize(1280, 980)

    try:
        detail.show()
        app.processEvents()
        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
        assert row_map["分节方式"]._label.alignment() & Qt.AlignRight
        assert row_map["下边距"]._label.alignment() & Qt.AlignRight
        assert row_map["右边距"]._label.alignment() & Qt.AlignRight
        assert row_map["页脚距离"]._label.alignment() & Qt.AlignRight
        assert row_map["分节方式"].widget.geometry().x() - row_map["分节方式"].label_width <= 20
        assert row_map["下边距"].widget.geometry().x() - row_map["下边距"].label_width <= 20
        assert row_map["右边距"].widget.geometry().x() - row_map["右边距"].label_width <= 20
        assert row_map["页脚距离"].widget.geometry().x() - row_map["页脚距离"].label_width <= 20
    finally:
        detail.close()
        app.processEvents()
def test_summary_grid_is_exported_from_shared_ui_package():
    assert SummaryGrid.__name__ == "SummaryGrid"
    source = (ROOT / "src/shared/ui/__init__.py").read_text(encoding="utf-8")

    assert '"SummaryGrid": (".summary_grid", "SummaryGrid")' in source
    assert '"SummaryGridItem": (".summary_grid", "SummaryGridItem")' in source
    assert '"TemplateSummaryCard": (".template_summary_card", "TemplateSummaryCard")' in source
    assert '"apply_template_summary_action_button": (".template_summary_card", "apply_template_summary_action_button")' in source


def test_template_summary_header_actions_share_compact_geometry():
    app = _app()
    bridge = PanelBridge()
    details = [
        PageSetupDetail(),
        StyleDetail(),
        TableCaptionDetail(),
        HeadingNumberingPanel(bridge),
    ]
    template = TemplateConfig()

    try:
        for detail in details:
            if hasattr(detail, "on_template_changed"):
                detail.on_template_changed(template)
            else:
                detail.set_template(template)
            if hasattr(detail, "set_save_enabled"):
                detail.set_save_enabled(True)
            detail.resize(1280, 720)
            detail.show()
            app.processEvents()

            restore = getattr(detail, "_restore_entry_btn", None) or getattr(detail, "_restore_btn")
            save = getattr(detail, "_save_btn")

            assert detail._summary_card.header.height() == 48
            assert detail._summary_card.height() == detail._summary_card._content_height_hint()
            assert restore.sizeHint().height() == 34
            assert save.sizeHint().height() == 34
            assert restore.property("variant") == "ghost-primary"
            assert save.property("variant") == "primary"
    finally:
        for detail in details:
            detail.close()
        app.processEvents()


def test_template_parameter_details_use_shared_16px_card_stack_rhythm():
    app = _app()
    template = TemplateConfig()
    details = [
        PageSetupDetail(),
        StyleDetail(),
        TableCaptionDetail(),
        ElementsDetail(),
        ElementsDetail(scope="toc"),
        CaptionDetail(),
        ReferenceDetail(),
    ]

    try:
        theme = get_theme()
        expected_gap = theme.template_detail_section_gap

        for detail in details:
            detail.set_template(template)
            detail.resize(1280, 900)
            detail.show()
            app.processEvents()

            assert expected_gap == 16
            assert detail.layout().spacing() == expected_gap

            if hasattr(detail, "_style_management_block"):
                block = detail._style_management_block
                summary = block.card
                next_widget = block.editing_section
                assert block.layout().spacing() == expected_gap
            else:
                summary = detail._summary_card
                next_widget = getattr(detail, "_editor_column", None)
                if next_widget is None:
                    if hasattr(detail, "_editor_card"):
                        next_widget = detail._editor_card
                    elif hasattr(detail, "_mode_card"):
                        next_widget = detail._mode_card
            assert next_widget is not None
            assert next_widget.y() - (summary.y() + summary.height()) == expected_gap

            editor_layout = getattr(detail, "_editor_layout", None)
            if editor_layout is None and hasattr(detail, "_editor_column"):
                editor_layout = detail._editor_column.layout()
            if editor_layout is not None:
                assert editor_layout.spacing() == expected_gap

            style_container_layout = getattr(detail, "_style_container_layout", None)
            if style_container_layout is not None:
                assert style_container_layout.spacing() == expected_gap
    finally:
        for detail in details:
            detail.close()
        app.processEvents()


def test_segmented_control_uses_equal_width_shared_track_styling():
    source = (ROOT / "src/shared/ui/segmented_control.py").read_text(encoding="utf-8")

    assert "self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)" in source
    assert "border: 1px solid" in source
    assert "self._layout.addWidget(btn, 1)" in source


def test_page_setup_detail_uses_new_non_duplicate_section_icons():
    source = (ROOT / "src/ui/panels/template_page_detail.py").read_text(encoding="utf-8")

    assert '"layout"' in source
    assert '"scan"' in source
    assert '"panel-top"' in source
    assert "self._actions_card" not in source
    assert '"file-text"' not in source
    assert '"scroll-text"' not in source
    assert '"puzzle"' not in source


def test_page_setup_detail_restore_entry_snapshot_survives_bridge_echo():
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    original_top = panel._current_template.page_setup.margin.top_cm

    try:
        panel._page_detail._page_inputs["top_cm"].set_value(original_top + 1.0, "cm")
        app.processEvents()

        assert panel._page_detail._restore_entry_btn.isEnabled() is True

        panel._page_detail._restore_entry_btn.click()
        app.processEvents()

        assert panel._current_template.page_setup.margin.top_cm == original_top
        assert panel._page_detail._restore_entry_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()


def test_page_setup_detail_drops_top_helper_copy_and_status_note():
    source = (ROOT / "src/ui/panels/template_page_detail.py").read_text(encoding="utf-8")

    assert "self._summary_note" not in source
    assert 'self._add_card_header(\n            self._summary_card' not in source
    assert "self._footer_note" not in source
    assert "_restore_defaults_btn" not in source
    assert "_build_action_controls" not in source
    assert "def _refresh_action_icons" in source
    assert "theme.text_disabled" in source


def test_page_setup_detail_removes_redundant_paper_card_helper_copy():
    source = (ROOT / "src/ui/panels/template_page_detail.py").read_text(encoding="utf-8")

    assert "先确定纸张规格、方向和分节方式，再观察页面比例是否符合预期。" not in source
    assert "description: str | None = None" in source


def test_template_panel_page_save_overwrites_current_file_and_clears_dirty(tmp_path, monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    monkeypatch.setattr(Toast, "show_success", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(Toast, "show_error", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(
        "src.ui.panels.template_panel.confirm",
        lambda *args, **kwargs: True,
    )

    try:
        target = tmp_path / "imported_template.json"
        save_template(panel._current_template, target)
        imported = load_template(target)
        bridge.set_current_template(
            imported,
            config_id=target.stem,
            path=str(target),
            source="file",
        )
        app.processEvents()

        panel._page_detail._page_inputs["top_cm"].set_value(4.2, "cm")
        app.processEvents()

        assert bridge.is_template_dirty() is True
        assert panel._page_detail._save_btn.isEnabled() is True

        panel._page_detail._save_btn.click()
        app.processEvents()

        reloaded = load_template(target)
        assert reloaded.page_setup.margin.top_cm == 4.2
        assert bridge.is_template_dirty() is False
        assert panel._page_detail._save_btn.isEnabled() is False
        assert "已保存" in panel._last_template_management_status
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_page_save_uses_current_path_for_library_templates(tmp_path, monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    monkeypatch.setattr(Toast, "show_success", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(Toast, "show_error", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(
        "src.ui.panels.template_panel.confirm",
        lambda *args, **kwargs: True,
    )

    try:
        target = tmp_path / "library_template.json"
        save_template(panel._current_template, target)
        panel._current_template_path = str(target)
        panel._current_template_source = "library"
        panel._current_template_source_type = "user"

        panel._page_detail._page_inputs["top_cm"].set_value(4.6, "cm")
        app.processEvents()

        panel._page_detail._save_btn.click()
        app.processEvents()

        reloaded = load_template(target)
        assert reloaded.page_setup.margin.top_cm == 4.6
        assert bridge.is_template_dirty() is False
        assert panel._page_detail._save_btn.isEnabled() is False
    finally:
        panel.close()
        app.processEvents()
