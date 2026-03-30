import inspect
import sys
from pathlib import Path

from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import LIGHT


def test_popup_container_qss_paints_surface_instead_of_transparent_shell():
    qss = StyledComboBox.build_popup_container_qss("popup_shell", LIGHT)

    assert "#popup_shell" in qss
    assert f"background: {LIGHT.bg_card};" in qss
    assert f"border: 1px solid {LIGHT.border};" in qss
    assert f"border-radius: {LIGHT.combo_popup_radius}px;" in qss
    assert "background: transparent;" not in qss.lower()


def test_popup_view_qss_paints_opaque_surface_instead_of_transparent_viewport():
    qss = StyledComboBox.build_popup_view_qss("popup_view", LIGHT)

    assert "#popup_view" in qss
    assert f"background: {LIGHT.bg_card};" in qss
    assert "border: none;" in qss
    assert f"padding: {LIGHT.combo_popup_padding}px;" in qss
    assert f"padding: {LIGHT.combo_popup_item_padding_y}px {LIGHT.combo_popup_item_padding_x}px;" in qss
    assert "background: transparent;" not in qss.lower()


def test_show_popup_does_not_apply_binary_mask_to_popup_shell():
    show_popup_source = inspect.getsource(StyledComboBox.showPopup)

    assert "_apply_popup_mask" not in show_popup_source


def test_sync_popup_geometry_keeps_popup_height_non_zero():
    app = QApplication.instance() or QApplication([])
    combo = StyledComboBox()
    combo.addItems(["默认选项", "选项 A", "选项 B"])
    combo.resize(180, 36)
    combo.show()
    app.processEvents()

    popup = combo.view().window()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(50)
        app.processEvents()

        assert popup.isVisible() is True
        assert popup.geometry().height() > 0
        assert popup.maximumHeight() > 0
    finally:
        popup.hide()
        combo.hide()
        app.processEvents()


def test_sync_popup_geometry_shrinks_popup_to_visible_row_height_without_blank_tail():
    app = QApplication.instance() or QApplication([])
    combo = StyledComboBox()
    combo.addItems(["默认选项", "选项 A", "选项 B"])
    combo.resize(180, 36)
    combo.show()
    app.processEvents()

    popup = combo.view().window()
    view = combo.view()

    try:
        combo.showPopup()
        app.processEvents()
        QTest.qWait(50)
        app.processEvents()

        visible_rows = min(combo.count(), combo.maxVisibleItems())
        visible_rows_height = sum(view.sizeHintForRow(i) for i in range(visible_rows))
        chrome_height = view.contentsMargins().top() + view.contentsMargins().bottom()
        viewport_blank_height = view.viewport().height() - visible_rows_height

        assert abs(popup.geometry().height() - (visible_rows_height + chrome_height)) <= 2
        assert viewport_blank_height <= 2
    finally:
        popup.hide()
        combo.hide()
        app.processEvents()


def test_sync_popup_geometry_uses_named_helpers_for_popup_workaround():
    class_source = inspect.getsource(StyledComboBox)
    sync_source = inspect.getsource(StyledComboBox._sync_popup_geometry)

    assert "def _release_popup_height_constraint" in class_source
    assert "def _popup_content_height" in class_source
    assert "def _position_popup_below_combo" in class_source
    assert "self._release_popup_height_constraint(popup)" in sync_source
    assert "self._popup_content_height()" in sync_source
    assert "self._position_popup_below_combo(popup)" in sync_source
    assert "_QT_WIDGETSIZE_MAX" not in sync_source
