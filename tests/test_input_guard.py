import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QWheelEvent


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QSlider, Qt
from src.shared.ui.input_guard import GlobalInputGuard
from src.shared.ui.themed_slider import ThemedSlider


def test_global_input_guard_blocks_slider_wheel_changes():
    _app = QApplication.instance() or QApplication([])
    guard = GlobalInputGuard()
    slider = QSlider(Qt.Horizontal)
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollUpdate,
        False,
    )

    handled = guard.eventFilter(slider, event)

    assert handled is True
    assert event.isAccepted() is False


def test_global_input_guard_blocks_themed_slider_wheel_changes():
    _app = QApplication.instance() or QApplication([])
    guard = GlobalInputGuard()
    slider = ThemedSlider(Qt.Horizontal)
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollUpdate,
        False,
    )

    handled = guard.eventFilter(slider, event)

    assert handled is True
    assert event.isAccepted() is False
