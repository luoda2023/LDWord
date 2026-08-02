"""Boundary registry for enterprise/legacy asset capabilities.

The assets panel currently contains both local material-management features and
large enterprise asset-governance workflows. This registry makes that product
boundary explicit so future refactors do not accidentally promote enterprise
writeback/governance code into the local formatting-tool core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


BoundaryDecision = Literal["keep", "isolate", "freeze", "delete_candidate"]


@dataclass(frozen=True, slots=True)
class AssetCapabilityBoundary:
    """Classification for an assets-panel capability group."""

    key: str
    decision: BoundaryDecision
    summary: str
    function_prefixes: tuple[str, ...]
    rationale: str
    next_action: str
    requires_external_system: bool = False
    core_local: bool = False


ASSET_CAPABILITY_BOUNDARIES: tuple[AssetCapabilityBoundary, ...] = (
    AssetCapabilityBoundary(
        key="local_question_figures",
        decision="keep",
        summary="Local question-figure metadata, labels, ordering, matching, and preview references.",
        function_prefixes=(
            "_question_figure_asset_items",
            "_question_figure_collection_summary",
            "_question_figure_item_summary",
            "_question_figure_target",
            "_question_figure_payload_matches_item",
            "_question_figure_repair_target_payload",
            "_question_figure_item_matches_repair_target",
            "_question_figure_compare",
            "_question_figure_order_value",
            "_asset_item_library_asset_id",
            "_asset_item_source",
            "_asset_item_cached_path",
            "_asset_item_preview",
            "_asset_item_thumbnail_path",
            "_asset_item_alt_text",
        ),
        rationale="This is required for local document generation and question-image placeholder replacement.",
        next_action="Move toward service-layer extraction after AssetsPanel UI methods are thinner.",
        core_local=True,
    ),
    AssetCapabilityBoundary(
        key="local_question_audit",
        decision="keep",
        summary="Local question-figure repair and rollback audit records.",
        function_prefixes=(
            "_question_figure_repair_audit",
            "_question_figure_repair_rollback_audit",
            "_append_question_figure_repair_audit_record",
            "_read_question_figure_repair_audit_payload",
        ),
        rationale="Local repair evidence is useful without any remote backend.",
        next_action="Keep scoped to local repair/rollback evidence only.",
        core_local=True,
    ),
)


def boundary_by_key(key: str) -> AssetCapabilityBoundary | None:
    """Return a boundary record by stable key."""

    target = str(key or "").strip()
    for boundary in ASSET_CAPABILITY_BOUNDARIES:
        if boundary.key == target:
            return boundary
    return None


def boundaries_by_decision(decision: BoundaryDecision) -> tuple[AssetCapabilityBoundary, ...]:
    """Return boundary records for a decision bucket."""

    return tuple(
        boundary
        for boundary in ASSET_CAPABILITY_BOUNDARIES
        if boundary.decision == decision
    )


def matching_boundaries_for_function(function_name: str) -> tuple[AssetCapabilityBoundary, ...]:
    """Return every boundary whose prefix list matches a function name."""

    name = str(function_name or "").strip()
    if not name:
        return ()
    matches: list[tuple[int, AssetCapabilityBoundary]] = []
    for boundary in ASSET_CAPABILITY_BOUNDARIES:
        for prefix in boundary.function_prefixes:
            if name.startswith(prefix):
                matches.append((len(prefix), boundary))
                break
    return tuple(boundary for _length, boundary in sorted(matches, reverse=True, key=lambda item: item[0]))


def primary_boundary_for_function(function_name: str) -> AssetCapabilityBoundary | None:
    """Return the most-specific boundary for a function name."""

    matches = matching_boundaries_for_function(function_name)
    return matches[0] if matches else None


def boundary_summary_counts() -> dict[str, int]:
    """Count boundary records by decision."""

    counts: dict[str, int] = {}
    for boundary in ASSET_CAPABILITY_BOUNDARIES:
        counts[boundary.decision] = counts.get(boundary.decision, 0) + 1
    return counts


__all__ = [
    "ASSET_CAPABILITY_BOUNDARIES",
    "AssetCapabilityBoundary",
    "BoundaryDecision",
    "boundaries_by_decision",
    "boundary_by_key",
    "boundary_summary_counts",
    "matching_boundaries_for_function",
    "primary_boundary_for_function",
]
