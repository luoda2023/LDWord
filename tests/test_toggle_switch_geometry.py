import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.toggle_switch import ToggleSwitch


def _app():
    return QApplication.instance() or QApplication([])


def test_toggle_switch_off_track_border_stays_inside_widget_bounds():
    _app()
    switch = ToggleSwitch(checked=False)

    rect = switch._track_rect()

    assert rect.x() == 0.5
    assert rect.y() == 0.5
    assert rect.width() == switch.width() - switch.OFF_TRACK_BORDER_W
    assert rect.height() == switch.height() - switch.OFF_TRACK_BORDER_W


def test_toggle_switch_checked_track_uses_full_widget_bounds():
    _app()
    switch = ToggleSwitch(checked=True)

    rect = switch._track_rect()

    assert rect.x() == 0.0
    assert rect.y() == 0.0
    assert rect.width() == switch.width()
    assert rect.height() == switch.height()


def test_toggle_switch_thumb_stays_vertically_centered_on_track_rect():
    _app()
    switch = ToggleSwitch(checked=False)

    track_rect = switch._track_rect()
    thumb_y = switch._thumb_y(track_rect)

    assert thumb_y == 3.0
    assert (thumb_y + switch.THUMB_D / 2.0) == track_rect.center().y()


def test_toggle_switch_uses_responsive_motion_duration():
    _app()
    switch = ToggleSwitch()

    assert switch.ANIMATION_DURATION_MS == 160
    assert switch._anim.duration() == switch.ANIMATION_DURATION_MS
