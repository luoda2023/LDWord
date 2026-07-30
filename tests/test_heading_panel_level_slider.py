import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.qt_api import QApplication, QLabel
from src.shared.ui.spacing_input import SpacingInput
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(create_builtin_template("default"))
    panel.show()
    app.processEvents()
    return app, panel


def test_heading_numbering_panel_uses_spacing_input_for_max_levels_control():
    app, panel = _build_panel()

    try:
        assert isinstance(panel._levels_input, SpacingInput)
        assert isinstance(panel._levels_slider, StyledSpinBox)
        assert panel._levels_slider.minimum() == 1
        assert panel._levels_slider.maximum() == 8
        assert panel._levels_slider.value() == 4
        assert panel._levels_input.value() == 4
        assert panel.panel_icon == "list-ordered"
        assert panel._summary_card.header._icon_name == "list-ordered"
        summary_items = panel._summary_grid.items()
        assert panel._summary_grid._tile_style == "module"
        assert summary_items[0].icon_name == "settings"
        assert summary_items[1].icon_name == "sliders-horizontal"
        assert {item.icon_name for item in summary_items[2:]} == {"list-ordered"}
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_panel_level_slider_updates_adapter_and_preview_rows():
    app, panel = _build_panel()

    try:
        panel._levels_input.set_value(6, "")
        panel._on_levels_changed()
        app.processEvents()

        assert panel._adapter.max_levels == 6
        assert panel._adv_list.count() == 6
        assert panel._levels_input.value() == 6
    finally:
        panel.close()
        app.processEvents()


def _level_list_objects(panel: HeadingNumberingPanel):
    items = [panel._adv_list.item(row) for row in range(panel._adv_list.count())]
    widgets = [panel._adv_list.itemWidget(item) for item in items]
    return items, widgets


def test_heading_level_edit_updates_existing_row_objects_in_place():
    app, panel = _build_panel()

    try:
        panel._adv_list.setCurrentRow(1)
        app.processEvents()
        original_items, original_widgets = _level_list_objects(panel)
        selected_item = panel._adv_list.currentItem()

        panel._adapter.set_binding_field(2, "enabled", False)
        panel._rebuild_level_list()
        app.processEvents()

        current_items, current_widgets = _level_list_objects(panel)
        assert current_items == original_items
        assert all(current is original for current, original in zip(current_items, original_items))
        assert all(current is original for current, original in zip(current_widgets, original_widgets))
        assert panel._adv_list.currentItem() is selected_item
        assert panel._selected_adv_level == 2

        preview_label = current_widgets[1].findChild(QLabel, "hn_list_txt")
        meta_label = current_widgets[1].findChild(QLabel, "hn_preview_meta")
        assert preview_label.text() == "未启用"
        assert "未启用" in meta_label.text()
        assert preview_label.property("muted") is True
        assert meta_label.property("muted") is True

        panel._adapter.set_binding_field(2, "enabled", True)
        panel._rebuild_level_list()
        app.processEvents()

        assert panel._adv_list.itemWidget(panel._adv_list.item(1)) is original_widgets[1]
        assert preview_label.text() != "未启用"
        assert preview_label.property("muted") is False
        assert meta_label.property("muted") is False
    finally:
        panel.close()
        app.processEvents()


def test_heading_level_count_changes_only_add_and_remove_tail_rows():
    app, panel = _build_panel()

    try:
        panel._adv_list.setCurrentRow(2)
        app.processEvents()
        original_items, original_widgets = _level_list_objects(panel)

        panel._adapter.set_max_levels(6)
        panel._rebuild_level_list()
        app.processEvents()

        expanded_items, expanded_widgets = _level_list_objects(panel)
        assert len(expanded_items) == 6
        assert all(expanded_items[i] is original_items[i] for i in range(4))
        assert all(expanded_widgets[i] is original_widgets[i] for i in range(4))
        assert panel._adv_list.currentRow() == 2
        assert panel._selected_adv_level == 3

        removed_items = expanded_items[3:]
        removed_widgets = expanded_widgets[3:]
        panel._adapter.set_max_levels(3)
        panel._rebuild_level_list()
        app.processEvents()

        reduced_items, reduced_widgets = _level_list_objects(panel)
        assert len(reduced_items) == 3
        assert all(reduced_items[i] is original_items[i] for i in range(3))
        assert all(reduced_widgets[i] is original_widgets[i] for i in range(3))
        assert not any(item in reduced_items for item in removed_items)
        assert not any(widget in reduced_widgets for widget in removed_widgets)
        assert panel._adv_list.currentRow() == 2
        assert panel._selected_adv_level == 3

        panel._adapter.set_max_levels(2)
        panel._rebuild_level_list()
        app.processEvents()

        assert panel._adv_list.currentRow() == 1
        assert panel._selected_adv_level == 2
        assert panel._adv_list.item(0) is original_items[0]
        assert panel._adv_list.itemWidget(panel._adv_list.item(0)) is original_widgets[0]
    finally:
        panel.close()
        app.processEvents()
