"""Compatibility import for shared style-difference projections."""

from src.config.style_difference_projection import (
    StyleDifferenceProjection,
    StyleDifferenceSummaryProjection,
    build_scene_style_difference_projections,
    build_style_difference_projection,
    build_style_difference_summary_projection,
    compact_changed_labels,
)


__all__ = [
    "StyleDifferenceProjection",
    "StyleDifferenceSummaryProjection",
    "build_scene_style_difference_projections",
    "build_style_difference_projection",
    "build_style_difference_summary_projection",
    "compact_changed_labels",
]
