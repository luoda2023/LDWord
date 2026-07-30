"""Tests for heading panel mode controls — now verifies fixed layout (no mode switching)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(create_builtin_template("default"))
    panel.show()
    app.processEvents()
    return app, panel


def test_heading_numbering_panel_uses_segmented_control_for_mode_switching():
    """Mode switching removed — panel now has fixed three-section layout."""
    app, panel = _build_panel()

    try:
        # No mode segment — all sections always visible
        assert not hasattr(panel, "_mode_segment")
        assert panel._summary_card.isVisible()
        assert panel._scheme_section.isVisible()
        assert panel._level_editor_card.isVisible()
    finally:
        panel.close()
        app.processEvents()


def test_heading_numbering_panel_mode_segment_switches_stack_views():
    """Stack views removed — level list + detail pane always visible."""
    app, panel = _build_panel()

    try:
        # No stack — sidebar and detail always visible
        assert not hasattr(panel, "_stack")
        assert panel._adv_list.isVisible()
        assert panel._detail_title is not None
    finally:
        panel.close()
        app.processEvents()


def test_heading_level_header_and_numbering_settings_are_compact():
    """TOC stays in the header while numbering controls share one settings card."""
    app, panel = _build_panel()

    try:
        assert panel._detail_title.parentWidget() is panel._detail_header
        assert panel._toc_switch.parentWidget() is panel._detail_header
        assert panel._result_heading_label.text() == "编号预览"
        assert panel._numbering_settings_block.isAncestorOf(panel._ref_style_row)
        assert panel._numbering_settings_block.isAncestorOf(panel._start_at_input)
        assert panel._numbering_settings_block.isAncestorOf(panel._title_sep_row)
        assert panel._restart_trigger_row.isHidden()
        assert panel._restart_trigger_grid.isHidden()
        assert panel._chain_sep_grid.isHidden()
        assert panel._ref_style_row.isVisible()
        assert panel._counter_grid._pair_rows[1].height() == panel._title_sep_row.height()
        assert panel._counter_grid._pair_rows[1].width() == panel._title_sep_row.width()

        panel._adv_list.setCurrentRow(1)
        app.processEvents()
        assert panel._chain_sep_grid.isVisible()

        specific_index = panel._restart_on_cb.findData("specific")
        assert specific_index >= 0
        panel._restart_on_cb.setCurrentIndex(specific_index)
        app.processEvents()
        assert panel._restart_trigger_grid.isVisible()
        assert panel._restart_trigger_row.width() == panel._restart_trigger_grid.width()
    finally:
        panel.close()
        app.processEvents()
