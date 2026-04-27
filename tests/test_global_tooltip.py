import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QEvent, QSize, QWidget
from src.shared.ui.theme import DARK, get_theme, set_theme
from src.shared.ui.tooltip import (
    DEFAULT_GAP,
    TOOLTIP_ENABLED_PROPERTY,
    TOOLTIP_PLACEMENT_PROPERTY,
    TOOLTIP_ROLE_PROPERTY,
    GlobalTooltipController,
    install_global_tooltip,
    set_global_tooltip,
    tooltip_position_for,
)


def test_global_tooltip_installation_is_idempotent(qapp):
    first = install_global_tooltip(qapp)
    second = install_global_tooltip(qapp)

    assert first is second
    assert isinstance(first, GlobalTooltipController)


def test_set_global_tooltip_stores_shared_metadata(qapp):
    controller = install_global_tooltip(qapp)
    widget = QWidget()
    try:
        set_global_tooltip(widget, "Workbench", placement="right", role="nav")

        options = controller.options_for(widget)

        assert widget.toolTip() == "Workbench"
        assert widget.property(TOOLTIP_ENABLED_PROPERTY) is True
        assert widget.property(TOOLTIP_PLACEMENT_PROPERTY) == "right"
        assert widget.property(TOOLTIP_ROLE_PROPERTY) == "nav"
        assert options is not None
        assert options.delay_ms == 80
    finally:
        widget.close()


def test_global_tooltip_position_anchors_to_right_side(qapp):
    widget = QWidget()
    try:
        widget.resize(40, 40)
        widget.move(20, 20)
        widget.show()
        qapp.processEvents()

        pos = tooltip_position_for(widget, QSize(80, 30), placement="right", screen_margin=0)
        anchor_right = widget.mapToGlobal(widget.rect().bottomRight()).x()

        assert pos.x() == anchor_right + DEFAULT_GAP
    finally:
        widget.close()


def test_global_tooltip_position_clamps_to_screen(qapp):
    widget = QWidget()
    try:
        screen = qapp.primaryScreen().availableGeometry()
        widget.resize(40, 40)
        widget.move(screen.right() - 8, screen.bottom() - 8)
        widget.show()
        qapp.processEvents()

        popup_size = QSize(220, 80)
        pos = tooltip_position_for(widget, popup_size, placement="right")

        assert pos.x() >= screen.left()
        assert pos.y() >= screen.top()
        assert pos.x() + popup_size.width() <= screen.right() + 1
        assert pos.y() + popup_size.height() <= screen.bottom() + 1
    finally:
        widget.close()


def test_global_tooltip_controller_intercepts_native_tooltip_events(qapp):
    controller = install_global_tooltip(qapp)
    widget = QWidget()
    try:
        widget.resize(40, 40)
        widget.show()
        set_global_tooltip(widget, "Workbench", placement="right", delay_ms=0)

        handled = controller.eventFilter(widget, QEvent(QEvent.ToolTip))

        assert handled is True
    finally:
        controller.hide_tooltip()
        widget.close()


def test_global_tooltip_controller_ignores_plain_widget_tooltips(qapp):
    controller = install_global_tooltip(qapp)
    widget = QWidget()
    try:
        widget.resize(40, 40)
        widget.show()
        widget.setToolTip("例如宋体、黑体、Times New Roman，未收录字体名也会保留。")

        handled = controller.eventFilter(widget, QEvent(QEvent.ToolTip))

        assert handled is False
        assert controller.options_for(widget) is None
    finally:
        controller.hide_tooltip()
        widget.close()


def test_global_tooltip_popup_uses_theme_tokens_and_single_line_style(qapp):
    controller = install_global_tooltip(qapp)
    original_theme = get_theme()
    widget = QWidget()
    try:
        set_theme(DARK)
        widget.resize(40, 40)
        widget.show()
        set_global_tooltip(widget, "素材管理", placement="right", delay_ms=0)

        controller.eventFilter(widget, QEvent(QEvent.ToolTip))
        controller._show_pending()

        assert controller.popup._label.wordWrap() is False
        assert controller.popup._label.text() == "素材管理"
        stylesheet = controller.popup._surface.styleSheet()
        assert DARK.bg_tooltip in stylesheet
        assert DARK.border in stylesheet
        assert DARK.text_on_tooltip in stylesheet
    finally:
        controller.hide_tooltip()
        set_theme(original_theme)
        widget.close()


def test_global_tooltip_architecture_is_wired_through_startup_and_chrome():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    sidebar_source = (ROOT / "src/ui/sidebar.py").read_text(encoding="utf-8")
    titlebar_source = (ROOT / "src/ui/title_bar.py").read_text(encoding="utf-8")

    assert "install_global_tooltip(app)" in main_source
    assert "set_global_tooltip(self, tooltip, placement=\"right\", role=\"nav\"" in sidebar_source
    assert "self.setToolTip(tooltip)" not in sidebar_source
    assert "set_global_tooltip(btn, tooltip, placement=\"bottom\", role=\"chrome\")" in titlebar_source
    assert "btn.setToolTip(tooltip)" not in titlebar_source
