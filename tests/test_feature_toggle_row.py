import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.feature_toggle_row import FeatureToggleRow
from src.shared.ui.flow_section import FlowSection


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


def test_flow_section_is_constructible_and_expanded_by_default():
    _app()
    section = FlowSection("Demo")

    assert section.is_expanded() is True


def test_flow_section_supports_expand_collapse_toggle():
    _app()
    section = FlowSection("Demo", expanded=True)

    section.set_expanded(False)
    assert section.is_expanded() is False

    section.set_expanded(True)
    assert section.is_expanded() is True


def test_flow_section_mounts_header_and_content_into_card_body_layout():
    _app()
    section = FlowSection("Demo")

    root_layout = section.layout()
    assert root_layout.count() == 1

    body_layout = root_layout.itemAt(0).layout()
    assert body_layout is not None
    assert body_layout.count() == 2
    assert body_layout.itemAt(0).widget() is section._toggle_button
    assert body_layout.itemAt(1).widget() is section._content
