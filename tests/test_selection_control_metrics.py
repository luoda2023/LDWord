import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QAbstractSlider
from src.shared.ui.selection_control_metrics import (
    RadioMetrics,
    SliderMetrics,
    build_radio_metrics,
    build_slider_metrics,
)
from src.shared.ui.theme import LIGHT


def test_qt_api_exports_qabstractslider_for_shared_controls():
    assert QAbstractSlider.__name__ == "QAbstractSlider"


def test_theme_exposes_geometry_first_selection_control_tokens():
    assert LIGHT.radio_indicator_diameter == 18
    assert LIGHT.radio_ring_width == 1
    assert LIGHT.radio_dot_diameter == 7
    assert LIGHT.radio_hit_padding_x >= 4
    assert LIGHT.radio_hit_padding_y >= 4
    assert LIGHT.slider_track_height == 4
    assert LIGHT.slider_handle_diameter == 20
    assert LIGHT.slider_handle_ring_width == 1
    assert LIGHT.slider_hit_extra_radius >= 4


def test_build_radio_metrics_clamps_invalid_values():
    metrics = build_radio_metrics(
        LIGHT.merge(
            {
                "radio_indicator_diameter": 4,
                "radio_ring_width": 9,
                "radio_dot_diameter": 99,
                "radio_focus_ring_width": 50,
            }
        )
    )

    assert isinstance(metrics, RadioMetrics)
    assert metrics.indicator_diameter >= 12
    assert metrics.ring_width <= metrics.indicator_diameter / 2
    assert metrics.dot_diameter < metrics.indicator_diameter
    assert metrics.focus_ring_width <= metrics.indicator_diameter / 2


def test_build_slider_metrics_clamps_invalid_values():
    metrics = build_slider_metrics(
        LIGHT.merge(
            {
                "slider_track_height": 0,
                "slider_handle_diameter": 6,
                "slider_handle_ring_width": 12,
                "slider_focus_ring_width": 40,
                "slider_hit_extra_radius": -5,
            }
        )
    )

    assert isinstance(metrics, SliderMetrics)
    assert metrics.track_height >= 2
    assert metrics.handle_diameter >= 12
    assert metrics.handle_ring_width <= metrics.handle_diameter / 2
    assert metrics.focus_ring_width <= metrics.handle_diameter / 2
    assert metrics.hit_extra_radius >= 0
