import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.themed_radio_button import ThemedRadioButton, _radio_label_color


def _non_transparent_bounds(image):
    xs = []
    ys = []
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def test_themed_radio_label_color_uses_semantic_theme_tokens():
    theme = SimpleNamespace(
        selection_label_color="#123456",
        selection_label_checked_color="#234567",
        selection_label_disabled_color="#345678",
    )

    assert _radio_label_color(theme, enabled=True, checked=False).name() == "#123456"
    assert _radio_label_color(theme, enabled=True, checked=True).name() == "#234567"
    assert _radio_label_color(theme, enabled=False, checked=False).name() == "#345678"
    assert _radio_label_color(theme, enabled=False, checked=True).name() == "#345678"


def test_themed_radio_indicator_rect_is_square():
    app = QApplication.instance() or QApplication([])
    button = ThemedRadioButton("选项 A")
    button.resize(button.sizeHint())

    rect = button._indicator_rect()

    assert abs(rect.width() - rect.height()) <= 0.01


def test_themed_radio_click_emits_checked_state():
    app = QApplication.instance() or QApplication([])
    button = ThemedRadioButton("选项 A")
    states = []
    button.toggled.connect(states.append)

    button.click()

    assert button.isChecked() is True
    assert states == [True]


def test_themed_radio_rendered_indicator_stays_visually_square():
    app = QApplication.instance() or QApplication([])
    button = ThemedRadioButton("选项 A")
    button.setChecked(True)
    button.resize(button.sizeHint())
    button.show()
    app.processEvents()

    image = button.grab().toImage()
    indicator_rect = button._indicator_rect().toAlignedRect()
    cropped = image.copy(indicator_rect)
    left, top, right, bottom = _non_transparent_bounds(cropped)

    assert abs(indicator_rect.width() - indicator_rect.height()) <= 1
    assert abs((right - left) - (bottom - top)) <= indicator_rect.width() + 10
