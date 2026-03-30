import gc
import sys
import warnings
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt
from src.shared.ui.themed_slider import ThemedSlider


def test_themed_slider_handle_rect_is_square():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.resize(220, 36)

    rect = slider._handle_rect_for_value(slider.value())

    assert abs(rect.width() - rect.height()) <= 0.01


def test_themed_slider_keyboard_and_click_update_value():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(25)
    slider.resize(220, 36)
    slider.show()
    slider.setFocus()
    app.processEvents()

    QTest.keyClick(slider, Qt.Key_Right)
    QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() - 12, slider.height() // 2))
    app.processEvents()

    assert slider.value() > 25


def test_themed_slider_drag_emits_slider_lifecycle_signals():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(10)
    slider.resize(220, 36)
    slider.show()
    app.processEvents()

    pressed = []
    released = []
    slider.sliderPressed.connect(lambda: pressed.append(True))
    slider.sliderReleased.connect(lambda: released.append(True))

    start = slider._handle_rect_for_value(slider.value()).center().toPoint()
    end = QPoint(slider.width() - 10, slider.height() // 2)
    QTest.mousePress(slider, Qt.LeftButton, pos=start)
    QTest.mouseMove(slider, end)
    QTest.mouseRelease(slider, Qt.LeftButton, pos=end)
    app.processEvents()

    assert pressed == [True]
    assert released == [True]
    assert slider.value() > 10


def test_themed_slider_theme_binding_cleanup_does_not_emit_runtime_warning():
    app = QApplication.instance() or QApplication([])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        slider = ThemedSlider(Qt.Horizontal)
        slider.show()
        app.processEvents()
        slider.deleteLater()
        app.processEvents()
        del slider
        gc.collect()
        app.processEvents()

    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert runtime_warnings == []


def test_themed_slider_focus_ring_color_uses_reduced_opacity():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)

    color = slider._focus_ring_color()

    assert color.alpha() < 255


def test_themed_slider_focus_ring_rect_stays_within_widget_bounds_at_extremes():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.resize(100, 36)

    left_rect = slider._focus_ring_rect_for_handle(slider._handle_rect_for_value(slider.minimum()))
    right_rect = slider._focus_ring_rect_for_handle(slider._handle_rect_for_value(slider.maximum()))

    assert left_rect.left() >= 0
    assert left_rect.right() <= slider.width()
    assert right_rect.left() >= 0
    assert right_rect.right() <= slider.width()


def test_themed_slider_handle_rect_is_inset_from_widget_edges_at_extremes():
    app = QApplication.instance() or QApplication([])
    slider = ThemedSlider(Qt.Horizontal)
    slider.resize(100, 36)

    left_handle = slider._handle_rect_for_value(slider.minimum())
    right_handle = slider._handle_rect_for_value(slider.maximum())

    assert left_handle.left() > 0
    assert right_handle.right() < slider.width()
