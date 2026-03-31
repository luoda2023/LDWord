import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.feature_toggle_row import FeatureToggleRow


def _app():
    return QApplication.instance() or QApplication([])


def test_feature_toggle_row_config_button_tracks_checked_state():
    _app()
    row = FeatureToggleRow("Heading")

    assert row.is_checked() is False
    assert row.config_button().isEnabled() is False

    row.set_checked(True)
    assert row.is_checked() is True
    assert row.config_button().isEnabled() is True

    row.set_checked(False)
    assert row.is_checked() is False
    assert row.config_button().isEnabled() is False


def test_feature_toggle_row_emits_toggled_signal_with_new_state():
    _app()
    row = FeatureToggleRow("Heading")
    states = []
    row.toggled.connect(states.append)

    row.set_checked(True)
    row.set_checked(False)

    assert states == [True, False]

