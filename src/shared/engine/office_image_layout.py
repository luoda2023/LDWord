"""Public API and child-process entry point for Office image layout.

Implementations live in focused contract, geometry, inventory, preflight,
parent coordinator, child lifecycle, and child worker modules.  This facade
contains no layout logic.
"""

from __future__ import annotations

import sys
from typing import Sequence

from src.shared.engine.office_image_layout_contracts import (
    DEFAULT_READABILITY_MIN_DIMENSION_PT,
    DEFAULT_SAFETY_MARGIN_PT,
    LAYOUT_SCHEMA_VERSION,
    PROVIDER_SPECS,
    LayoutFailure,
    LayoutFailureCode,
    LayoutStatus,
    LayoutWarning,
    LayoutWarningCode,
    OfficeImageJobReceipt,
    OfficeImageLayoutJob,
    OfficeImageLayoutReceipt,
    OfficeImageLayoutRequest,
    OfficeImageProvider,
    OfficeProviderSpec,
    OOXMLImageIdentity,
    StabilizationRoundReceipt,
)
from src.shared.engine.office_image_layout_coordinator import (
    OFFICE_COM_PATH_MAX_UTF16_UNITS,
    build_office_image_layout_request,
    run_office_image_layout,
)
from src.shared.engine.office_image_layout_geometry import (
    MAX_IMAGE_PROPORTION_ERROR,
    POINTS_PER_CM,
    WORD_MIN_INLINE_DIMENSION_PT,
    ImageGeometryDecision,
    ImageGeometryError,
    ImageGeometryInput,
    compute_image_geometry,
)
from src.shared.engine.office_image_layout_inventory import (
    PREEXISTING_WP_EXTENT_TOLERANCE_EMU,
    image_inventory_sha256,
    image_preservation_sha256,
    inventory_ooxml_images,
)
from src.shared.engine.office_image_layout_worker import (
    module_main as _worker_module_main,
)
from src.shared.engine.office_image_layout_worker import (
    run_office_image_layout_child,
)
from src.shared.io.layout_shadow import (
    LAYOUT_SHADOW_PREFIX,
    LAYOUT_SHADOW_SOURCE_ID_LENGTH,
    build_controlled_layout_shadow_path,
    is_controlled_layout_shadow,
    layout_shadow_source_id,
)


def _module_main(argv: Sequence[str]) -> int:
    return _worker_module_main(argv)


if __name__ == "__main__":
    raise SystemExit(_module_main(sys.argv[1:]))


__all__ = [
    "DEFAULT_READABILITY_MIN_DIMENSION_PT",
    "DEFAULT_SAFETY_MARGIN_PT",
    "ImageGeometryDecision",
    "ImageGeometryError",
    "ImageGeometryInput",
    "LAYOUT_SCHEMA_VERSION",
    "LAYOUT_SHADOW_PREFIX",
    "LAYOUT_SHADOW_SOURCE_ID_LENGTH",
    "MAX_IMAGE_PROPORTION_ERROR",
    "LayoutFailure",
    "LayoutFailureCode",
    "LayoutStatus",
    "LayoutWarning",
    "LayoutWarningCode",
    "OFFICE_COM_PATH_MAX_UTF16_UNITS",
    "OOXMLImageIdentity",
    "OfficeImageJobReceipt",
    "OfficeImageLayoutJob",
    "OfficeImageLayoutReceipt",
    "OfficeImageLayoutRequest",
    "OfficeImageProvider",
    "OfficeProviderSpec",
    "POINTS_PER_CM",
    "PREEXISTING_WP_EXTENT_TOLERANCE_EMU",
    "PROVIDER_SPECS",
    "StabilizationRoundReceipt",
    "WORD_MIN_INLINE_DIMENSION_PT",
    "build_controlled_layout_shadow_path",
    "build_office_image_layout_request",
    "compute_image_geometry",
    "image_inventory_sha256",
    "image_preservation_sha256",
    "inventory_ooxml_images",
    "is_controlled_layout_shadow",
    "layout_shadow_source_id",
    "run_office_image_layout",
    "run_office_image_layout_child",
]
