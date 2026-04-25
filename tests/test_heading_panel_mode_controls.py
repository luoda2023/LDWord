"""Tests for heading panel mode controls — now verifies fixed layout (no mode switching)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel


def _build_panel():
    app = QApplication.instance() or QApplication([])
    panel = HeadingNumberingPanel(PanelBridge())
    panel.on_template_changed(TemplateConfig())
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
