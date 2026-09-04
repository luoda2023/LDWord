"""Pure, provider-independent image geometry for Office inline layout."""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.config.image_materials import ImagePlacementMode
from src.shared.engine.office_image_layout_contracts import (
    DEFAULT_READABILITY_MIN_DIMENSION_PT,
    DEFAULT_SAFETY_MARGIN_PT,
    LayoutFailureCode,
)

POINTS_PER_CM = 72.0 / 2.54
PIXELS_PER_POINT_AT_96_DPI = 96.0 / 72.0
WORD_MIN_INLINE_DIMENSION_PT = 0.5
WORD_MAX_INLINE_DIMENSION_PT = 1584.0
MAX_IMAGE_PROPORTION_ERROR = 0.002
DIMENSION_SEARCH_MAX_OFFSET_PT = 1.0
DIMENSION_SEARCH_FALLBACK_OFFSETS_PT = (
    -1.0,
    -0.75,
    -0.5,
    -0.25,
    0.25,
    0.5,
    0.75,
    1.0,
)
MAX_ACTUAL_DIMENSION_DEVIATION_PT = 1.5

@dataclass(frozen=True, slots=True)
class ImageGeometryInput:
    mode: ImagePlacementMode
    source_width_px: int
    source_height_px: int
    container_width_pt: float
    anchor_y_pt: float
    flow_bottom_pt: float
    paragraph_reserve_pt: float
    safety_margin_pt: float = DEFAULT_SAFETY_MARGIN_PT
    fixed_width_pt: float | None = None
    max_width_pt: float | None = None
    word_min_dimension_pt: float = WORD_MIN_INLINE_DIMENSION_PT
    readability_min_dimension_pt: float = DEFAULT_READABILITY_MIN_DIMENSION_PT

@dataclass(frozen=True, slots=True)
class ImageGeometryDecision:
    mode: ImagePlacementMode
    aspect_ratio: float
    width_cap_pt: float
    available_height_pt: float | None
    target_width_pt: float
    target_height_pt: float
    scale_ratio_96dpi: float
    readability_warning: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "aspect_ratio": self.aspect_ratio,
            "width_cap_pt": self.width_cap_pt,
            "available_height_pt": self.available_height_pt,
            "target_width_pt": self.target_width_pt,
            "target_height_pt": self.target_height_pt,
            "scale_ratio_96dpi": self.scale_ratio_96dpi,
            "readability_warning": self.readability_warning,
        }

class ImageGeometryError(ValueError):
    def __init__(self, code: LayoutFailureCode, message: str):
        self.code = code
        super().__init__(message)

def compute_image_geometry(spec: ImageGeometryInput) -> ImageGeometryDecision:
    """Pure contain geometry; title height affects only measured ``anchor_y_pt``."""

    mode = (
        spec.mode
        if isinstance(spec.mode, ImagePlacementMode)
        else ImagePlacementMode(str(spec.mode))
    )
    numeric = {
        "source_width_px": spec.source_width_px,
        "source_height_px": spec.source_height_px,
        "container_width_pt": spec.container_width_pt,
        "anchor_y_pt": spec.anchor_y_pt,
        "flow_bottom_pt": spec.flow_bottom_pt,
        "paragraph_reserve_pt": spec.paragraph_reserve_pt,
        "safety_margin_pt": spec.safety_margin_pt,
        "word_min_dimension_pt": spec.word_min_dimension_pt,
        "readability_min_dimension_pt": spec.readability_min_dimension_pt,
    }
    for name, value in numeric.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ImageGeometryError(
                LayoutFailureCode.INVALID_GEOMETRY,
                f"{name} must be numeric",
            )
        if not math.isfinite(float(value)):
            raise ImageGeometryError(
                LayoutFailureCode.INVALID_GEOMETRY,
                f"{name} must be finite",
            )
    if spec.source_width_px <= 0 or spec.source_height_px <= 0:
        raise ImageGeometryError(
            LayoutFailureCode.INVALID_GEOMETRY,
            "source image dimensions must be positive",
        )
    if spec.container_width_pt <= 0:
        raise ImageGeometryError(
            LayoutFailureCode.INVALID_GEOMETRY,
            "container width must be positive",
        )
    if spec.word_min_dimension_pt <= 0:
        raise ImageGeometryError(
            LayoutFailureCode.INVALID_GEOMETRY,
            "Word minimum dimension must be positive",
        )

    max_width = (
        spec.container_width_pt
        if spec.max_width_pt is None
        else min(spec.container_width_pt, _positive_finite(spec.max_width_pt, "max_width_pt"))
    )
    aspect = float(spec.source_width_px) / float(spec.source_height_px)
    natural_width_pt = float(spec.source_width_px) / PIXELS_PER_POINT_AT_96_DPI
    available: float | None = None
    if mode is ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE:
        available = (
            float(spec.flow_bottom_pt)
            - float(spec.anchor_y_pt)
            - float(spec.paragraph_reserve_pt)
            - float(spec.safety_margin_pt)
        )
        if available <= 0:
            raise ImageGeometryError(
                LayoutFailureCode.NO_REMAINING_SPACE,
                "anchor page has no positive remaining flow height",
            )
        target_width = min(max_width, available * aspect)
    elif mode is ImagePlacementMode.FIT_CONTAINER_FLOW:
        target_width = max_width
    elif mode is ImagePlacementMode.NATURAL_SIZE:
        target_width = min(max_width, natural_width_pt)
    else:
        if spec.fixed_width_pt is None:
            raise ImageGeometryError(
                LayoutFailureCode.INVALID_GEOMETRY,
                "fixed_box modes require fixed_width_pt",
            )
        target_width = min(
            max_width,
            _positive_finite(spec.fixed_width_pt, "fixed_width_pt"),
        )
    target_height = target_width / aspect
    if min(target_width, target_height) < spec.word_min_dimension_pt:
        raise ImageGeometryError(
            LayoutFailureCode.BELOW_WORD_MINIMUM,
            "contained image would be below Word's supported inline dimension",
        )
    if max(target_width, target_height) > WORD_MAX_INLINE_DIMENSION_PT:
        raise ImageGeometryError(
            LayoutFailureCode.ABOVE_WORD_MAXIMUM,
            "contained image exceeds Word's supported inline dimension",
        )
    if available is not None and target_height > available + 1e-6:
        raise ImageGeometryError(
            LayoutFailureCode.INVALID_GEOMETRY,
            "contain calculation exceeded the measured remaining height",
        )
    readability = min(target_width, target_height) < spec.readability_min_dimension_pt
    return ImageGeometryDecision(
        mode=mode,
        aspect_ratio=aspect,
        width_cap_pt=max_width,
        available_height_pt=available,
        target_width_pt=target_width,
        target_height_pt=target_height,
        scale_ratio_96dpi=target_width / natural_width_pt,
        readability_warning=readability,
    )

def _positive_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImageGeometryError(LayoutFailureCode.INVALID_GEOMETRY, f"{name} must be numeric")
    result = float(value)
    if result <= 0 or not math.isfinite(result):
        raise ImageGeometryError(LayoutFailureCode.INVALID_GEOMETRY, f"{name} must be positive")
    return result

__all__ = [
    "DIMENSION_SEARCH_FALLBACK_OFFSETS_PT",
    "DIMENSION_SEARCH_MAX_OFFSET_PT",
    "ImageGeometryDecision",
    "ImageGeometryError",
    "ImageGeometryInput",
    "MAX_ACTUAL_DIMENSION_DEVIATION_PT",
    "MAX_IMAGE_PROPORTION_ERROR",
    "PIXELS_PER_POINT_AT_96_DPI",
    "POINTS_PER_CM",
    "WORD_MAX_INLINE_DIMENSION_PT",
    "WORD_MIN_INLINE_DIMENSION_PT",
    "compute_image_geometry",
]
