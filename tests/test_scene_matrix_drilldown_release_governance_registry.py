import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_drilldown_items import (  # noqa: E402
    _item_factories_for_source,
)
from src.config.scene_matrix_drilldown_projection_references import (  # noqa: E402
    _projection_release_link_reference_map,
    _projection_release_marker_reference_map,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
    scene_release_governance_drilldown_id,
    scene_release_governance_drilldown_source_marker_entries,
    scene_release_governance_report_id,
    scene_release_governance_report_spec,
)


RELEASE_GOVERNANCE_DIRECT_BUILDER_NAMES = tuple(
    spec.builder_name for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
)


def test_projection_references_use_release_governance_registry():
    source = (
        ROOT
        / "src"
        / "config"
        / "scene_matrix_drilldown_projection_references.py"
    ).read_text(encoding="utf-8")

    assert "build_scene_release_governance_report" in source
    assert "_release_governance_report" in source
    assert "scene_release_governance_report_id(report_attribute)" in source
    assert all(name not in source for name in RELEASE_GOVERNANCE_DIRECT_BUILDER_NAMES)
    assert all(
        scene_release_governance_report_id(spec.report_attribute) == spec.report_id
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        f'"{spec.report_id}"' not in source
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )


def test_drilldown_release_mapping_uses_release_governance_registry():
    paths = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_release_items.py",
        ROOT / "src" / "config" / "scene_matrix_drilldown_reference_ids.py",
    )

    for path in paths:
        source = path.read_text(encoding="utf-8")

        assert "build_scene_release_governance_report" in source
        assert "_release_governance_report" in source
        assert all(
            name not in source
            for name in RELEASE_GOVERNANCE_DIRECT_BUILDER_NAMES
        )


def test_drilldown_item_factories_use_release_governance_registry_for_sources():
    source = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_items.py"
    ).read_text(encoding="utf-8")
    expected_factory_names = tuple(
        f"_{scene_release_governance_report_spec(report_id).report_attribute.removesuffix('_report')}_item"
        for report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS
    )

    assert "_release_governance_item_factories()" in source
    assert "SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS" in source
    assert "RELEASE_GOVERNANCE_ITEM_FACTORIES.get(report_id)" in source
    assert set(SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS) == {
        spec.report_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    }
    assert tuple(
        _item_factories_for_source(report_id)[0].__name__
        for report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS
    ) == expected_factory_names
    assert all(
        f'"{report_id}"' not in source
        for report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS
    )


def test_drilldown_sources_use_release_governance_registry_for_source_markers():
    source = (
        ROOT / "src" / "config" / "scene_matrix_drilldown_sources.py"
    ).read_text(encoding="utf-8")
    entries = scene_release_governance_drilldown_source_marker_entries()

    assert "scene_release_governance_drilldown_source_marker_entries" in source
    assert all(name not in source for name in RELEASE_GOVERNANCE_DIRECT_BUILDER_NAMES)
    assert len(entries) == len(SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS)
    assert tuple(item[0] for item in entries) == tuple(
        spec.report_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        spec.builder_name in markers
        for spec, (_source_id, _source_path, markers) in zip(
            SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
            entries,
            strict=True,
        )
    )


def test_projection_release_marker_and_link_maps_derive_drilldown_ids_from_registry():
    source = (
        ROOT
        / "src"
        / "config"
        / "scene_matrix_drilldown_projection_references.py"
    ).read_text(encoding="utf-8")
    marker_body = source.split(
        "def _projection_release_marker_reference_map()",
        maxsplit=1,
    )[1].split(
        "def _projection_release_link_reference_map()",
        maxsplit=1,
    )[0]
    link_body = source.split(
        "def _projection_release_link_reference_map()",
        maxsplit=1,
    )[1].split(
        "def _projection_retained_gap_exit_reference_map()",
        maxsplit=1,
    )[0]
    marker_report_attributes = (
        "release_projection_surface_parity_report",
        "release_closure_ledger_report",
    )
    link_report_attributes = (
        "terminal_release_exception_report",
        "boundary_subject_release_dossier_report",
        "non_subject_release_trace_attribution_report",
        "release_trace_partition_guard_report",
        "boundary_subject_release_continuity_report",
        "release_closure_ledger_report",
        "boundary_maturity_release_envelope_report",
        "retained_gap_exit_criteria_report",
        "release_residual_ratio_ledger_report",
    )

    assert "scene_release_governance_drilldown_id(report_attribute)" in source
    assert "_release_report_rows(" in marker_body
    assert "_release_report_rows(" in link_body
    assert all(
        scene_release_governance_drilldown_id(report_attribute)
        == report_attribute.removesuffix("_report")
        for report_attribute in (
            *marker_report_attributes,
            *link_report_attributes,
        )
    )
    assert all(
        f'"{scene_release_governance_drilldown_id(report_attribute)}",'
        not in marker_body
        for report_attribute in marker_report_attributes
    )
    assert all(
        f'"{scene_release_governance_drilldown_id(report_attribute)}",'
        not in link_body
        for report_attribute in link_report_attributes
    )

    marker_map = _projection_release_marker_reference_map()
    link_map = _projection_release_link_reference_map()

    assert (
        "scene_release_projection_surface_parity_audit"
        in marker_map[
            (
                "release_closure_ledger",
                "release_projection_surface_parity",
                "action_behavior_ids",
            )
        ]
    )
    assert (
        "release_projection_surface_parity"
        in link_map[
            (
                "release_closure_ledger",
                "release_acceptance_certificate",
                "capability_ids",
            )
        ]
    )
