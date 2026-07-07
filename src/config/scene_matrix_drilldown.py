"""Front-end drilldown registry for the high-level scene matrix.

N2.165 keeps the existing audit sources authoritative and adds one normalized
index that a scene UI can browse without re-implementing source-specific
business rules.  It does not create new scene promises; it exposes the rows
already proven by dashboard, request-cell, plugin-boundary, Word-risk,
import-handoff, and family-fixture-depth audits.
"""

from __future__ import annotations

import os
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from src.config.scene_coverage_manifest import list_scene_coverage_packs
from src.config.scene_family_registry import list_planned_scene_families
from src.config.scene_request_cell_fixture_registry import (
    list_scene_request_cell_fixtures,
)
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures
from src.config.scene_matrix_drilldown_sources import (
    REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS,
    SCENE_MATRIX_DRILLDOWN_SOURCE_ID,
    SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS,
)
from src.config.scene_matrix_drilldown_projection_profiles import (
    SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES,
    SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP,
    SceneMatrixDrilldownProjectionProfile,
)
from src.config.scene_matrix_drilldown_projection_references import (
    _projection_control_runtime_reference_map,
    _projection_evidence_reference_map,
    _projection_external_handoff_contract_reference_map,
    _projection_formula_output_watermark_reference_map,
    _projection_path_reference_map,
    _projection_release_link_reference_map,
    _projection_release_marker_reference_map,
    _projection_release_metric_reference_map,
    _projection_report_delivery_marker_reference_map,
    _projection_requirement_dimension_reference_map,
    _projection_retained_gap_exit_reference_map,
    _projection_source_reference_ids,
    _projection_source_reference_map,
    _projection_surface_reference_map,
    _projection_target_plugin_reference_map,
)
from src.config.scene_matrix_drilldown_models import (
    SceneMatrixDrilldownIssue,
    SceneMatrixDrilldownItem,
    SceneMatrixDrilldownReport,
    SceneMatrixDrilldownRow,
    SceneMatrixDrilldownSourceEvidence,
)
from src.config.scene_matrix_drilldown_items import _item_factories_for_source
from src.config.scene_matrix_drilldown_reference_ids import (
    _delivery_reference_ids,
    _external_handoff_contract_reference_ids,
    _input_render_reference_ids,
    _material_reference_ids,
    _maturity_gap_reference_ids,
    _object_preflight_reference_ids,
    _plugin_gate_reference_ids,
    _projection_test_reference_ids,
    _risk_domain_reference_ids,
    _target_plugin_reference_ids,
    _word_risk_surface_reference_ids,
)
from src.shared.engine.count_engine import list_count_profiles


def _pytest_scene_matrix_drilldown_cache_enabled() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not bool(
        os.environ.get("LARK_DISABLE_SCENE_MATRIX_TEST_CACHE")
    )


def _scene_matrix_drilldown_build_audit_enabled() -> bool:
    return not bool(os.environ.get("PYTEST_CURRENT_TEST")) or bool(
        os.environ.get("LARK_FULL_SCENE_DRILLDOWN_AUDIT_IN_TESTS")
    )


def _project_root_cache_key(project_root: Path | str | None) -> str:
    return str(Path(project_root).resolve()) if project_root else ""


@lru_cache(maxsize=4)
def _cached_scene_matrix_drilldown_base(
    project_root_key: str,
) -> SceneMatrixDrilldownReport:
    project_root = Path(project_root_key) if project_root_key else None
    return _build_scene_matrix_drilldown_report_uncached(project_root=project_root)


def _filter_scene_matrix_drilldown_report(
    base: SceneMatrixDrilldownReport,
    *,
    pack_id: str,
    family_id: str,
    source_id: str,
    query: str,
    query_label: str,
) -> SceneMatrixDrilldownReport:
    if not (pack_id or family_id or source_id or query):
        return base
    items = tuple(
        replace(
            item,
            visible_rows=tuple(
                row
                for row in item.rows
                if _matches_filters(
                    row,
                    pack_id=pack_id,
                    family_id=family_id,
                    query=query,
                )
            ),
        )
        for item in base.items
        if not source_id or item.source_id == source_id
    )
    return replace(
        base,
        items=items,
        pack_filter=pack_id,
        family_filter=family_id,
        source_filter=source_id,
        query=query_label,
    )


def build_scene_matrix_drilldown_report(
    *,
    pack_id: str = "",
    family_id: str = "",
    source_id: str = "",
    query: str = "",
    project_root: Path | str | None = None,
) -> SceneMatrixDrilldownReport:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_source = str(source_id or "").strip()
    query_label = str(query or "").strip()
    normalized_query = query_label.lower()

    if _pytest_scene_matrix_drilldown_cache_enabled():
        project_root_key = _project_root_cache_key(project_root)
        base_is_warm = bool(_cached_scene_matrix_drilldown_base.cache_info().currsize)
        if not normalized_source or base_is_warm:
            return _filter_scene_matrix_drilldown_report(
                _cached_scene_matrix_drilldown_base(project_root_key),
                pack_id=normalized_pack,
                family_id=normalized_family,
                source_id=normalized_source,
                query=normalized_query,
                query_label=query_label,
            )

    return _build_scene_matrix_drilldown_report_uncached(
        pack_id=normalized_pack,
        family_id=normalized_family,
        source_id=normalized_source,
        query=query_label,
        project_root=project_root,
    )


def _build_scene_matrix_drilldown_report_uncached(
    *,
    pack_id: str = "",
    family_id: str = "",
    source_id: str = "",
    query: str = "",
    project_root: Path | str | None = None,
) -> SceneMatrixDrilldownReport:
    normalized_pack = str(pack_id or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_source = str(source_id or "").strip()
    normalized_query = str(query or "").strip().lower()

    items = _build_all_items(
        pack_id=normalized_pack,
        family_id=normalized_family,
        source_id=normalized_source,
        query=normalized_query,
    )

    source_evidence = _source_evidence(project_root)
    report_without_issues = SceneMatrixDrilldownReport(
        items=items,
        issues=(),
        source_evidence=source_evidence,
        pack_filter=normalized_pack,
        family_filter=normalized_family,
        source_filter=normalized_source,
        query=str(query or "").strip(),
    )
    issues = (
        audit_scene_matrix_drilldown_report(report_without_issues)
        if _scene_matrix_drilldown_build_audit_enabled()
        else ()
    )
    return SceneMatrixDrilldownReport(
        items=items,
        issues=issues,
        source_evidence=source_evidence,
        pack_filter=normalized_pack,
        family_filter=normalized_family,
        source_filter=normalized_source,
        query=str(query or "").strip(),
    )


def audit_scene_matrix_drilldown_report(
    report: SceneMatrixDrilldownReport,
) -> tuple[SceneMatrixDrilldownIssue, ...]:
    issues: list[SceneMatrixDrilldownIssue] = []
    evidence_source_ids = {evidence.source_id for evidence in report.source_evidence}
    coverage_pack_ids = {pack.pack_id for pack in list_scene_coverage_packs()}
    planned_family_ids = {
        family.family_id for family in list_planned_scene_families()
    }
    request_cell_ids = {
        cell.sample_id for cell in list_scene_request_cell_fixtures()
    }
    sample_fixture_ids = {
        fixture.fixture_id for fixture in list_scene_sample_fixtures()
    }
    count_profile_ids = {
        profile.profile_id for profile in list_count_profiles()
    }
    delivery_reference_ids = _delivery_reference_ids()
    material_reference_ids = _material_reference_ids()
    input_source_reference_ids, render_source_reference_ids = (
        _input_render_reference_ids()
    )
    object_preflight_reference_ids = _object_preflight_reference_ids()
    word_risk_surface_reference_ids = _word_risk_surface_reference_ids()
    plugin_gate_reference_ids = _plugin_gate_reference_ids()
    risk_domain_reference_ids = _risk_domain_reference_ids()
    maturity_gap_reference_ids = _maturity_gap_reference_ids()
    external_handoff_contract_reference_ids = (
        _external_handoff_contract_reference_ids()
    )
    target_plugin_reference_ids = _target_plugin_reference_ids()
    projection_test_reference_ids = _projection_test_reference_ids()
    projection_source_reference_ids = _projection_source_reference_ids(report)
    projection_source_reference_map = _projection_source_reference_map()
    projection_surface_reference_map = _projection_surface_reference_map()
    projection_path_reference_map = _projection_path_reference_map()
    projection_evidence_reference_map = _projection_evidence_reference_map()
    projection_release_marker_reference_map = (
        _projection_release_marker_reference_map()
    )
    projection_release_link_reference_map = _projection_release_link_reference_map()
    projection_retained_gap_exit_reference_map = (
        _projection_retained_gap_exit_reference_map()
    )
    projection_control_runtime_reference_map = (
        _projection_control_runtime_reference_map()
    )
    projection_release_metric_reference_map = (
        _projection_release_metric_reference_map()
    )
    projection_external_handoff_contract_reference_map = (
        _projection_external_handoff_contract_reference_map()
    )
    projection_report_delivery_marker_reference_map = (
        _projection_report_delivery_marker_reference_map()
    )
    projection_requirement_dimension_reference_map = (
        _projection_requirement_dimension_reference_map()
    )
    projection_target_plugin_reference_map = (
        _projection_target_plugin_reference_map()
    )
    projection_formula_output_watermark_reference_map = (
        _projection_formula_output_watermark_reference_map()
    )
    projection_path_root = Path(__file__).resolve().parents[2]
    item_source_ids = {item.source_id for item in report.items}
    row_source_ids = {row.source_id for item in report.items for row in item.rows}
    missing_item_source_ids = item_source_ids - evidence_source_ids
    missing_row_source_ids = row_source_ids - evidence_source_ids
    seen_drilldown_ids: set[str] = set()
    seen_projection_profile_ids: set[str] = set()
    for profile in SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES:
        if profile.drilldown_id in seen_projection_profile_ids:
            issues.append(
                SceneMatrixDrilldownIssue(
                    "projection_profile",
                    profile.drilldown_id,
                    "duplicate_projection_profile",
                    (
                        "Duplicate scene matrix drilldown projection profile: "
                        f"{profile.drilldown_id}."
                    ),
                )
            )
        seen_projection_profile_ids.add(profile.drilldown_id)
    for item in report.items:
        if item.drilldown_id in seen_drilldown_ids:
            issues.append(
                SceneMatrixDrilldownIssue(
                    "drilldown",
                    item.drilldown_id,
                    "duplicate_drilldown_id",
                    f"Duplicate scene matrix drilldown id: {item.drilldown_id}.",
                )
            )
        seen_drilldown_ids.add(item.drilldown_id)
    item_by_id = {item.drilldown_id: item for item in report.items}
    if not report.source_filter:
        for drilldown_id in REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS:
            item = item_by_id.get(drilldown_id)
            if item is None:
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "drilldown",
                        drilldown_id,
                        "missing_required_drilldown",
                        f"Missing required scene matrix drilldown: {drilldown_id}.",
                    )
                )
            elif not item.rows:
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "drilldown",
                        drilldown_id,
                        "empty_required_drilldown",
                        f"Required scene matrix drilldown has no source rows: {drilldown_id}.",
                    )
                )
    for item in report.items:
        if item.drilldown_id not in REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS:
            issues.append(
                SceneMatrixDrilldownIssue(
                    "drilldown",
                    item.drilldown_id,
                    "unknown_drilldown",
                    f"Unknown scene matrix drilldown id: {item.drilldown_id}.",
                )
            )
        if item.source_id in missing_item_source_ids:
            issues.append(
                SceneMatrixDrilldownIssue(
                    "drilldown",
                    item.drilldown_id,
                    "missing_item_source_evidence",
                    (
                        "Scene matrix drilldown source is not covered by "
                        f"source evidence: {item.source_id}."
                    ),
                )
            )
        if item.issue_count:
            issues.append(
                SceneMatrixDrilldownIssue(
                    "drilldown",
                    item.drilldown_id,
                    "source_row_issues",
                    f"Drilldown source rows still contain {item.issue_count} issue ids.",
                )
            )
        projection_profile = SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP.get(
            item.drilldown_id
        )
        if (
            projection_profile is not None
            and projection_profile.source_id != item.source_id
        ):
            issues.append(
                SceneMatrixDrilldownIssue(
                    "drilldown",
                    item.drilldown_id,
                    "projection_profile_source_mismatch",
                    (
                        "Scene matrix drilldown projection profile source does "
                        f"not match item source: {projection_profile.source_id} "
                        f"!= {item.source_id}."
                    ),
                )
            )
        seen_row_ids: set[str] = set()
        for row in item.rows:
            if row.row_id in seen_row_ids:
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "row",
                        f"{item.drilldown_id}:{row.row_id}",
                        "duplicate_row_id",
                        (
                            "Duplicate scene matrix drilldown row id: "
                            f"{item.drilldown_id}:{row.row_id}."
                        ),
                    )
                )
            seen_row_ids.add(row.row_id)
            if row.source_id in missing_row_source_ids:
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "row",
                        f"{item.drilldown_id}:{row.row_id}",
                        "missing_row_source_evidence",
                        (
                            "Scene matrix drilldown row source is not covered "
                            f"by source evidence: {row.source_id}."
                        ),
                    )
                )
            if row.source_id != item.source_id:
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "row",
                        f"{item.drilldown_id}:{row.row_id}",
                        "row_source_mismatch",
                        (
                            "Scene matrix drilldown row source does not match "
                            f"its item source: {row.source_id} != {item.source_id}."
                        ),
                    )
                )
            if row.action_behavior_ids and (
                projection_profile is None
                or not projection_profile.action_source_fields
            ):
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "row",
                        f"{item.drilldown_id}:{row.row_id}",
                        "missing_action_behavior_projection_profile",
                        (
                            "Scene matrix drilldown row exposes "
                            "action_behavior_ids without a source-aware "
                            f"projection profile: {item.drilldown_id}."
                        ),
                    )
                )
            if row.capability_ids and (
                projection_profile is None
                or not projection_profile.capability_source_fields
            ):
                issues.append(
                    SceneMatrixDrilldownIssue(
                        "row",
                        f"{item.drilldown_id}:{row.row_id}",
                        "missing_capability_projection_profile",
                        (
                            "Scene matrix drilldown row exposes capability_ids "
                            "without a source-aware projection profile: "
                            f"{item.drilldown_id}."
                        ),
                    )
                )
            for field_name, projection_ids in (
                ("action_behavior_ids", row.action_behavior_ids),
                ("capability_ids", row.capability_ids),
            ):
                for projection_id in projection_ids:
                    if (
                        projection_id.startswith("test_")
                        and projection_id not in projection_test_reference_ids
                    ):
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "unknown_projection_test_reference_id",
                                (
                                    "Scene matrix drilldown row references an "
                                    f"unknown projected test id in {field_name}: "
                                    f"{projection_id}."
                                ),
                            )
                        )
                for source_reference_id in projection_source_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                ):
                    if source_reference_id not in projection_source_reference_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "unknown_projection_source_reference_id",
                                (
                                    "Scene matrix drilldown row projects a "
                                    "source id that is not registered as a "
                                    "dashboard, release, or drilldown source: "
                                    f"{source_reference_id}."
                                ),
                            )
                        )
                    if source_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_source_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"source id projection in {field_name}: "
                                    f"{source_reference_id}."
                                ),
                            )
                        )
                for surface_reference_id in projection_surface_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                ):
                    if surface_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_surface_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"runtime/UI/report surface projection in "
                                    f"{field_name}: {surface_reference_id}."
                                ),
                            )
                        )
                for path_reference_id in projection_path_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                ):
                    if path_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_path_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"script/test/doc path projection in "
                                    f"{field_name}: {path_reference_id}."
                                ),
                            )
                        )
                    if not (projection_path_root / path_reference_id).exists():
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_path_file",
                                (
                                    "Scene matrix drilldown row projects a "
                                    "script/test/doc path that does not exist: "
                                    f"{path_reference_id}."
                                ),
                            )
                        )
                for evidence_reference_id in projection_evidence_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                ):
                    if evidence_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_evidence_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"source evidence-id projection in "
                                    f"{field_name}: {evidence_reference_id}."
                                ),
                            )
                        )
                for marker_reference_id in (
                    projection_release_marker_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if marker_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_release_marker_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"release marker projection in "
                                    f"{field_name}: {marker_reference_id}."
                                ),
                            )
                        )
                for link_reference_id in projection_release_link_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                ):
                    if link_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_release_link_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"release link projection in "
                                    f"{field_name}: {link_reference_id}."
                                ),
                            )
                        )
                for retained_gap_exit_reference_id in (
                    projection_retained_gap_exit_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if retained_gap_exit_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                (
                                    "missing_projection_retained_gap_exit_"
                                    "reference_id"
                                ),
                                (
                                    "Scene matrix drilldown row is missing a "
                                    "retained-gap exit criteria projection in "
                                    f"{field_name}: "
                                    f"{retained_gap_exit_reference_id}."
                                ),
                            )
                        )
                for control_runtime_reference_id in (
                    projection_control_runtime_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if control_runtime_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                (
                                    "missing_projection_control_runtime_"
                                    "reference_id"
                                ),
                                (
                                    "Scene matrix drilldown row is missing a "
                                    "control-runtime projection in "
                                    f"{field_name}: "
                                    f"{control_runtime_reference_id}."
                                ),
                            )
                        )
                for release_metric_reference_id in (
                    projection_release_metric_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if release_metric_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_release_metric_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    "release metric projection in "
                                    f"{field_name}: {release_metric_reference_id}."
                                ),
                            )
                        )
                for handoff_contract_reference_id in (
                    projection_external_handoff_contract_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if (
                        handoff_contract_reference_id
                        not in external_handoff_contract_reference_ids
                    ):
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                (
                                    "unknown_projection_external_handoff_"
                                    "contract_reference_id"
                                ),
                                (
                                    "Scene matrix drilldown row references an "
                                    "external handoff contract that is not in "
                                    "the external handoff ledger: "
                                    f"{handoff_contract_reference_id}."
                                ),
                            )
                        )
                    if handoff_contract_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                (
                                    "missing_projection_external_handoff_"
                                    "contract_reference_id"
                                ),
                                (
                                    "Scene matrix drilldown row is missing an "
                                    "external handoff contract projection in "
                                    f"{field_name}: "
                                    f"{handoff_contract_reference_id}."
                                ),
                            )
                        )
                for report_delivery_marker_id in (
                    projection_report_delivery_marker_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if report_delivery_marker_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                (
                                    "missing_projection_report_delivery_"
                                    "marker_reference_id"
                                ),
                                (
                                    "Scene matrix drilldown row is missing a "
                                    "report/delivery output marker projection "
                                    f"in {field_name}: "
                                    f"{report_delivery_marker_id}."
                                ),
                            )
                        )
                for requirement_dimension_id in (
                    projection_requirement_dimension_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if requirement_dimension_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_requirement_dimension_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    "release acceptance requirement dimension "
                                    f"projection in {field_name}: "
                                    f"{requirement_dimension_id}."
                                ),
                            )
                        )
                for target_plugin_id in projection_target_plugin_reference_map.get(
                    (item.drilldown_id, row.row_id, field_name),
                    set(),
                ):
                    if target_plugin_id not in target_plugin_reference_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "unknown_projection_target_plugin_reference_id",
                                (
                                    "Scene matrix drilldown row references a "
                                    "target plugin that is not in the external "
                                    f"handoff target-plugin ledger: {target_plugin_id}."
                                ),
                            )
                        )
                    if target_plugin_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                "missing_projection_target_plugin_reference_id",
                                (
                                    "Scene matrix drilldown row is missing a "
                                    f"target plugin projection in {field_name}: "
                                    f"{target_plugin_id}."
                                ),
                            )
                        )
                for formula_output_watermark_reference_id in (
                    projection_formula_output_watermark_reference_map.get(
                        (item.drilldown_id, row.row_id, field_name),
                        set(),
                    )
                ):
                    if formula_output_watermark_reference_id not in projection_ids:
                        issues.append(
                            SceneMatrixDrilldownIssue(
                                "row",
                                f"{item.drilldown_id}:{row.row_id}",
                                (
                                    "missing_projection_formula_output_"
                                    "watermark_reference_id"
                                ),
                                (
                                    "Scene matrix drilldown row is missing a "
                                    "formula/output/watermark source "
                                    f"projection in {field_name}: "
                                    f"{formula_output_watermark_reference_id}."
                                ),
                            )
                        )
            for pack_id in row.pack_ids:
                if pack_id not in coverage_pack_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_pack_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown coverage pack id: {pack_id}."
                            ),
                        )
                    )
            for family_id in row.family_ids:
                if family_id not in planned_family_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_family_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown planned family id: {family_id}."
                            ),
                        )
                    )
            for request_cell_id in row.request_cell_ids:
                if request_cell_id not in request_cell_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_request_cell_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown request cell id: {request_cell_id}."
                            ),
                        )
                    )
            for fixture_id in row.fixture_ids:
                if fixture_id not in sample_fixture_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_fixture_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown sample fixture id: {fixture_id}."
                            ),
                        )
                    )
            for count_profile_id in row.count_profile_ids:
                if count_profile_id not in count_profile_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_count_profile_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown count profile id: {count_profile_id}."
                            ),
                        )
                    )
            for delivery_reference_id in row.delivery_preset_ids:
                if delivery_reference_id not in delivery_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_delivery_reference_id",
                            (
                                "Scene matrix drilldown row references an "
                                "unknown delivery preset or output signal id: "
                                f"{delivery_reference_id}."
                            ),
                        )
                    )
            for material_reference_id in row.material_schema_ids:
                if material_reference_id not in material_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_material_reference_id",
                            (
                                "Scene matrix drilldown row references an "
                                "unknown material schema or repair signal id: "
                                f"{material_reference_id}."
                            ),
                        )
                    )
            for input_source_id in row.input_source_ids:
                if input_source_id not in input_source_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_input_source_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown input source id: {input_source_id}."
                            ),
                        )
                    )
            for render_source_id in row.render_source_ids:
                if render_source_id not in render_source_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_render_source_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown render source id: {render_source_id}."
                            ),
                        )
                    )
            for object_preflight_target_id in row.object_preflight_target_ids:
                if object_preflight_target_id not in object_preflight_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_object_preflight_target_id",
                            (
                                "Scene matrix drilldown row references an "
                                "unknown object preflight target id: "
                                f"{object_preflight_target_id}."
                            ),
                        )
                    )
            for word_risk_surface_id in row.word_risk_surface_ids:
                if word_risk_surface_id not in word_risk_surface_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_word_risk_surface_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown Word risk surface id: {word_risk_surface_id}."
                            ),
                        )
                    )
            for plugin_gate_id in row.plugin_gate_ids:
                if plugin_gate_id not in plugin_gate_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_plugin_gate_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown plugin/manual gate id: {plugin_gate_id}."
                            ),
                        )
                    )
            for risk_domain_id in row.risk_domain_ids:
                if risk_domain_id not in risk_domain_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_risk_domain_id",
                            (
                                "Scene matrix drilldown row references an "
                                f"unknown plugin/manual risk domain id: {risk_domain_id}."
                            ),
                        )
                    )
            for maturity_gap_reference_id in row.maturity_gap_domain_ids:
                if maturity_gap_reference_id not in maturity_gap_reference_ids:
                    issues.append(
                        SceneMatrixDrilldownIssue(
                            "row",
                            f"{item.drilldown_id}:{row.row_id}",
                            "unknown_row_maturity_gap_reference_id",
                            (
                                "Scene matrix drilldown row references an "
                                "unknown maturity gap domain or retained gap id: "
                                f"{maturity_gap_reference_id}."
                            ),
                        )
                    )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneMatrixDrilldownIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues)


def _build_all_items(
    *,
    pack_id: str,
    family_id: str,
    source_id: str,
    query: str,
) -> tuple[SceneMatrixDrilldownItem, ...]:
    raw_items = tuple(
        factory() for factory in _item_factories_for_source(source_id)
    )
    return tuple(
        SceneMatrixDrilldownItem(
            drilldown_id=item.drilldown_id,
            label=item.label,
            source_id=item.source_id,
            lens_ids=item.lens_ids,
            route_hint=item.route_hint,
            detail=item.detail,
            rows=item.rows,
            visible_rows=tuple(
                row
                for row in item.rows
                if _matches_filters(
                    row,
                    pack_id=pack_id,
                    family_id=family_id,
                    query=query,
                )
            ),
        )
        for item in raw_items
    )


def _matches_filters(
    row: SceneMatrixDrilldownRow,
    *,
    pack_id: str,
    family_id: str,
    query: str,
) -> bool:
    if pack_id and pack_id not in row.pack_ids:
        return False
    if family_id and family_id not in row.family_ids:
        return False
    if query and query not in row.search_text:
        return False
    return True


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneMatrixDrilldownSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence: list[SceneMatrixDrilldownSourceEvidence] = []
    for source_id, source_path, markers in SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS:
        path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneMatrixDrilldownSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
                status="ready" if path.exists() and not missing else "missing",
            )
        )
    return tuple(evidence)


__all__ = [
    "REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS",
    "SCENE_MATRIX_DRILLDOWN_SOURCE_ID",
    "SceneMatrixDrilldownIssue",
    "SceneMatrixDrilldownItem",
    "SceneMatrixDrilldownReport",
    "SceneMatrixDrilldownRow",
    "SceneMatrixDrilldownSourceEvidence",
    "audit_scene_matrix_drilldown_report",
    "build_scene_matrix_drilldown_report",
]
