from __future__ import annotations

from src.qt_api import QVBoxLayout, QWidget
from src.shared.ui.styled_combo_box import _source_badge_colors
from src.shared.ui.theme import (
    LIGHT,
    WARM_LIGHT,
    flush_theme_changes,
    get_theme,
    set_theme,
)
from src.ui.bridge import PanelBridge
from src.ui.panels.assets_panel import AssetsPanel


def test_assets_panel_keeps_descendant_table_theme_after_deferred_show(qapp):
    original = get_theme()
    host = QWidget()
    layout = QVBoxLayout(host)
    try:
        set_theme(LIGHT)
        flush_theme_changes()
        panel = AssetsPanel(PanelBridge())
        layout.addWidget(panel)

        set_theme(WARM_LIGHT)
        flush_theme_changes()
        host.show()
        qapp.processEvents()

        stylesheet = panel.styleSheet()
        assert "QListWidget, QTableWidget" in stylesheet
        assert f"background: {WARM_LIGHT.bg_card};" in stylesheet
        assert f"alternate-background-color: {WARM_LIGHT.bg_window};" in stylesheet
        assert f"color: {WARM_LIGHT.text_primary};" in stylesheet
    finally:
        host.close()
        qapp.processEvents()
        set_theme(original)
        flush_theme_changes()


def test_off_badge_uses_theme_tokens_instead_of_fixed_black_and_white():
    fill, text = _source_badge_colors(WARM_LIGHT, "off", enabled=True)

    assert fill.name() == WARM_LIGHT.bg_tooltip.lower()
    assert text.name() == WARM_LIGHT.text_on_tooltip.lower()
