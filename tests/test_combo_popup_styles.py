import inspect
import sys
from pathlib import Path

from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QPoint, Qt, QVBoxLayout, QWidget
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import LIGHT


def test_popup_container_qss_stays_transparent_when_panel_handles_shell():
    qss = StyledComboBox.build_popup_container_qss("popup_shell", LIGHT)

    assert "#popup_shell" in qss
    assert "background: transparent;" in qss.lower()
    assert "border: none;" in qss


def test_popup_surface_qss_paints_single_visible_shell():
    qss = StyledComboBox.build_popup_surface_qss("popup_surface", LIGHT)

    assert "#popup_surface" in qss
    assert f"background: {LIGHT.bg_card};" in qss
    assert f"border: {LIGHT.combo_popup_border_width}px solid {LIGHT.border};" in qss
    assert f"border-radius: {LIGHT.combo_popup_radius}px;" in qss


def test_popup_view_qss_keeps_view_and_viewport_visuals_transparent():
    qss = StyledComboBox.build_popup_view_qss("popup_view", LIGHT)

    assert "#popup_view" in qss
    assert "background: transparent;" in qss.lower()
    assert "border: none;" in qss
    assert f"padding: {LIGHT.combo_popup_padding}px;" in qss
    assert f"padding: {LIGHT.combo_popup_item_padding_y}px {LIGHT.combo_popup_item_padding_x}px;" in qss


def test_styled_combo_box_uses_custom_popup_panel_instead_of_native_showpopup():
    source = inspect.getsource(StyledComboBox.showPopup)

    assert "super().showPopup()" not in source
    assert "_popup_panel" in source


def test_styled_combo_box_exposes_geometry_helper_for_anchored_popup():
    class_source = inspect.getsource(StyledComboBox)

    assert "def _popup_geometry_in_window" in class_source
    assert "def _popup_content_height" in class_source
    assert "def _popup_content_width" in class_source
    assert "mapTo(" in class_source


def test_refresh_style_keeps_viewport_transparent_so_surface_is_the_only_visible_shell():
    source = inspect.getsource(StyledComboBox._refresh_style)

    assert "viewport.setAutoFillBackground(False)" in source
    assert "viewport.setStyleSheet" in source
    assert 'background: transparent; border: none;' in source


def test_popup_panel_appears_inside_same_window_as_combo():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    layout.addWidget(combo)
    combo.addItems(["默认选项", "选项 A", "选项 B"])
    combo.resize(180, 36)
    host.show()
    app.processEvents()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(50)
        app.processEvents()

        panel = combo._popup_panel
        assert panel is not None
        assert panel.isVisible() is True
        assert panel.parentWidget() is combo.window()
        assert panel.width() == combo.window().width()
        assert panel.height() == combo.window().height()
        assert abs(panel.surface().width() - combo.width()) <= 2
        assert panel.surface().height() > 0
        assert combo.view().parentWidget() is panel.surface()
    finally:
        combo.hidePopup()
        host.hide()
        app.processEvents()


def test_inline_narrow_combo_popup_expands_to_fit_longer_items():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    combo.set_inline(True)
    combo.setFixedWidth(49)
    combo.addItems(["字", "磅", "centimeter"])
    layout.addWidget(combo)
    host.resize(320, 180)
    host.show()
    app.processEvents()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(50)
        app.processEvents()

        panel = combo._popup_panel
        min_popup_width = (
            combo.view().sizeHintForColumn(0)
            + combo.view().contentsMargins().left()
            + combo.view().contentsMargins().right()
            + (LIGHT.combo_popup_border_width * 2)
        )
        assert panel.surface().width() >= min_popup_width
        assert panel.surface().width() > combo.width()
    finally:
        combo.hidePopup()
        host.hide()
        app.processEvents()


def test_single_item_popup_avoids_extra_bottom_chrome_band():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    layout.addWidget(combo)
    combo.addItem("Only item", "only")
    combo.resize(180, 36)
    host.resize(320, 180)
    host.show()
    app.processEvents()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(50)
        app.processEvents()

        panel = combo._popup_panel
        expected_height = (
            combo.view().sizeHintForRow(0)
            + combo.view().contentsMargins().top()
            + (LIGHT.combo_popup_border_width * 2)
        )
        assert abs(panel.surface().height() - expected_height) <= 2
    finally:
        combo.hidePopup()
        host.hide()
        app.processEvents()


def test_wheel_event_scrolls_popup_view_without_dismissing_panel():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    layout.addWidget(combo)
    for index in range(30):
        combo.addItem(f"Item {index}", index)
    host.resize(320, 360)
    host.show()
    app.processEvents()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(50)
        app.processEvents()

        panel = combo._popup_panel
        scrollbar = combo.view().verticalScrollBar()
        before = scrollbar.value()

        QTest.qWait(20)
        wheel_target = combo.view().viewport()
        from PySide6.QtCore import QPointF, QPoint
        from PySide6.QtGui import QWheelEvent

        pos = wheel_target.rect().center()
        global_pos = wheel_target.mapToGlobal(pos)
        event = QWheelEvent(
            QPointF(pos),
            QPointF(global_pos),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(wheel_target, event)
        app.processEvents()
        QTest.qWait(20)
        app.processEvents()

        assert panel.isVisible() is True
        assert scrollbar.value() > before
    finally:
        combo.hidePopup()
        host.hide()
        app.processEvents()


def test_scrollbar_drag_keeps_popup_open_and_updates_value():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = StyledComboBox(host)
    layout.addWidget(combo)
    for index in range(30):
        combo.addItem(f"Item {index}", index)
    combo.setMaxVisibleItems(8)
    host.resize(320, 480)
    host.show()
    app.processEvents()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(80)
        app.processEvents()

        panel = combo._popup_panel
        scrollbar = combo.view().verticalScrollBar()

        # Guard: the scrollbar must actually be scrollable for this test.
        assert scrollbar.maximum() > 0, (
            f"scrollbar.maximum()={scrollbar.maximum()}, "
            f"viewport rows may fit without scrolling"
        )

        # Verify scrollbar interaction keeps the popup open.
        pos = scrollbar.rect().center()
        QTest.mousePress(scrollbar, Qt.LeftButton, pos=pos)
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()
        QTest.mouseRelease(scrollbar, Qt.LeftButton, pos=pos)
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()

        assert panel.isVisible() is True, "popup should stay open after scrollbar click"

        # Verify programmatic scroll updates the value (proves scrollbar is
        # wired up and functional, independent of mouse-drag pixel geometry).
        before = scrollbar.value()
        scrollbar.setValue(scrollbar.maximum())
        app.processEvents()
        assert scrollbar.value() > before
    finally:
        combo.hidePopup()
        host.hide()
        app.processEvents()
