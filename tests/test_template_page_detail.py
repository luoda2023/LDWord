import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.loader import load_template, save_template
from src.config.template import TemplateConfig
from src.qt_api import QApplication, Qt
from src.shared.ui import DashedSeparator, SummaryGrid
from src.shared.ui.form_row import FormRow
from src.shared.ui.toast import Toast
from src.ui.bridge import PanelBridge
from src.ui.panels.template_page_detail import PageSetupDetail
from src.ui.panels.template_panel import TemplatePanel


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
        assert isinstance(detail._summary_grid, SummaryGrid)
        assert len(detail._summary_grid.items()) == 5
        summary_items = {item.key: item for item in detail._summary_grid.items()}
        assert detail._summary_grid.value_for("paper") == "A3"
        assert detail._summary_grid.value_for("orientation") == "横向"
        assert detail._summary_grid.value_for("section") == "下一页分节"
        assert summary_items["paper"].column_span == 2
        assert summary_items["orientation"].column_span == 2
        assert summary_items["section"].column_span == 2
        assert summary_items["margin_gutter"].label == "页边距与装订线"
        assert summary_items["margin_gutter"].column_span == 3
        assert detail._summary_grid.value_for("margin_gutter") == "上 2.5 cm  下 3.8 cm"
        assert detail._summary_grid.detail_for("margin_gutter") == "左 3.2 cm  右 3.2 cm  装订线 0.8 cm"
        assert summary_items["header_footer"].label == "页眉与页脚"
        assert summary_items["header_footer"].column_span == 3
        assert detail._summary_grid.value_for("header_footer") == "页眉距离 1.6 cm"
        assert detail._summary_grid.detail_for("header_footer") == "页脚距离 3 cm"
        assert summary_items["margin_gutter"].detail_emphasis is True
        assert summary_items["header_footer"].detail_emphasis is True
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
        assert panel._page_detail._summary_grid.value_for("margin_gutter") == "上 4.5 cm  下 3.8 cm"
        assert panel._page_detail._restore_entry_btn.isEnabled() is True
        assert panel._page_detail._save_btn.isEnabled() is True
        assert bridge.is_template_dirty() is True
        assert emitted
        assert emitted[-1].page_setup.margin.top_cm == 4.5
    finally:
        panel.close()
        app.processEvents()


def test_page_setup_detail_reuses_shared_spacing_input_control():
    source = (ROOT / "src/ui/panels/template_page_detail.py").read_text(encoding="utf-8")

    assert "SummaryGrid(" in source
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


def test_page_setup_detail_right_column_form_rows_left_align_labels_for_visual_balance():
    app = _app()
    detail = PageSetupDetail()
    detail.set_template(TemplateConfig())
    detail.resize(1280, 980)

    try:
        detail.show()
        app.processEvents()
        row_map = {row.label_text: row for row in detail.findChildren(FormRow)}
        assert row_map["分节方式"]._label.alignment() & Qt.AlignLeft
        assert row_map["下边距"]._label.alignment() & Qt.AlignLeft
        assert row_map["右边距"]._label.alignment() & Qt.AlignLeft
        assert row_map["页脚距离"]._label.alignment() & Qt.AlignLeft
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
        assert "已保存" in panel._io_detail._status.text()
    finally:
        panel.close()
        app.processEvents()


def test_template_panel_page_save_uses_current_path_for_library_templates(tmp_path, monkeypatch):
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    monkeypatch.setattr(Toast, "show_success", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(Toast, "show_error", staticmethod(lambda *args, **kwargs: None))

    try:
        target = tmp_path / "library_template.json"
        save_template(panel._current_template, target)
        panel._current_template_path = str(target)
        panel._current_template_source = "library"

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
