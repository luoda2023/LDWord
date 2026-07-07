"""Assets/material-management panel helpers."""

from __future__ import annotations

from src.ui.panels.assets.enterprise_boundary import (
    ASSET_CAPABILITY_BOUNDARIES,
    AssetCapabilityBoundary,
    boundaries_by_decision,
    boundary_by_key,
    boundary_summary_counts,
    matching_boundaries_for_function,
    primary_boundary_for_function,
)
from src.ui.panels.assets.specs import (
    ASSETS_SECTION_SPECS,
    BATCH_OUTPUT_CUSTOM_TEMPLATE,
    BATCH_OUTPUT_NAMING_OPTIONS,
    COMMON_ASSET_SLOTS,
    COMMON_FIELD_DEFS,
    FIELD_SOURCE_IMPORTED_MAPPING,
    REQUIRED_FIELD_KEYS,
    SUPPORTED_IMAGE_SUFFIXES,
    AssetSlotSpec,
    AssetsSectionSpec,
    AttachmentRoleSpec,
)

__all__ = [
    "ASSET_CAPABILITY_BOUNDARIES",
    "ASSETS_SECTION_SPECS",
    "BATCH_OUTPUT_CUSTOM_TEMPLATE",
    "BATCH_OUTPUT_NAMING_OPTIONS",
    "COMMON_ASSET_SLOTS",
    "COMMON_FIELD_DEFS",
    "FIELD_SOURCE_IMPORTED_MAPPING",
    "REQUIRED_FIELD_KEYS",
    "SUPPORTED_IMAGE_SUFFIXES",
    "AssetCapabilityBoundary",
    "AssetSlotSpec",
    "AssetsSectionSpec",
    "AttachmentRoleSpec",
    "boundaries_by_decision",
    "boundary_by_key",
    "boundary_summary_counts",
    "matching_boundaries_for_function",
    "primary_boundary_for_function",
]
