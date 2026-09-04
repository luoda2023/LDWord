from __future__ import annotations

from dataclasses import dataclass

from src.shared.ui.theme import AppTheme


@dataclass(frozen=True)
class RadioMetrics:
    indicator_diameter: float
    ring_width: float
    dot_diameter: float
    label_gap: int
    hit_padding_x: int
    hit_padding_y: int
    focus_ring_width: float


@dataclass(frozen=True)
class SliderMetrics:
    track_height: float
    handle_diameter: float
    handle_ring_width: float
    hit_extra_radius: int
    focus_ring_width: float


def build_radio_metrics(theme: AppTheme) -> RadioMetrics:
    indicator = max(12.0, float(theme.radio_indicator_diameter))
    ring_width = min(indicator / 2.0, max(1.0, float(theme.radio_ring_width)))
    inner_limit = max(2.0, indicator - ring_width * 2.0)
    dot = min(inner_limit, max(2.0, float(theme.radio_dot_diameter)))
    focus = min(indicator / 2.0, max(1.0, float(theme.radio_focus_ring_width)))
    return RadioMetrics(
        indicator_diameter=indicator,
        ring_width=ring_width,
        dot_diameter=dot,
        label_gap=int(max(0, theme.radio_label_gap)),
        hit_padding_x=int(max(0, theme.radio_hit_padding_x)),
        hit_padding_y=int(max(0, theme.radio_hit_padding_y)),
        focus_ring_width=focus,
    )


def build_slider_metrics(theme: AppTheme) -> SliderMetrics:
    handle = max(12.0, float(theme.slider_handle_diameter))
    ring_width = min(handle / 2.0, max(1.0, float(theme.slider_handle_ring_width)))
    focus = min(handle / 2.0, max(1.0, float(theme.slider_focus_ring_width)))
    return SliderMetrics(
        track_height=max(2.0, float(theme.slider_track_height)),
        handle_diameter=handle,
        handle_ring_width=ring_width,
        hit_extra_radius=int(max(0, theme.slider_hit_extra_radius)),
        focus_ring_width=focus,
    )
