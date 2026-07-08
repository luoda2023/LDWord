import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_matrix_dashboard import (  # noqa: E402
    SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_MARKER_IDS,
)
from src.config.scene_matrix_dashboard_lenses import (  # noqa: E402
    SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS,
)
from src.config.scene_matrix_dashboard_models import (  # noqa: E402
    SceneMatrixDashboardReport,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS,
    SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS,
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
    scene_release_governance_report_id,
)


def test_scene_matrix_dashboard_uses_release_governance_registry_for_builders():
    source = (ROOT / "src" / "config" / "scene_matrix_dashboard.py").read_text(
        encoding="utf-8"
    )
    function_body = source.split(
        "def _build_scene_matrix_dashboard_uncached(",
        maxsplit=1,
    )[1].split(
        "def _filter_rows(",
        maxsplit=1,
    )[0]
    cards_body = source.split(
        "def _dashboard_cards(",
        maxsplit=1,
    )[1].split(
        "def _status_counts(",
        maxsplit=1,
    )[0]
    card_source_helper_body = source.split(
        "def _release_governance_card_source_ids(",
        maxsplit=1,
    )[1].split(
        "def _dashboard_report_issue_variant(",
        maxsplit=1,
    )[0]
    card_variant_helper_body = source.split(
        "def _dashboard_report_issue_variant(",
        maxsplit=1,
    )[1].split(
        "def _release_governance_cards(",
        maxsplit=1,
    )[0]
    release_cards_body = source.split(
        "def _release_governance_cards(",
        maxsplit=1,
    )[1].split(
        "def _dashboard_cards(",
        maxsplit=1,
    )[0]
    direct_builder_names = tuple(
        spec.builder_name
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
        if spec.report_id not in SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS
    )
    dashboard_builder_names = tuple(
        spec.builder_name
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
        if spec.report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS
    )

    assert "build_scene_release_governance_report" in source
    assert dashboard_builder_names == (
        "build_scene_release_residual_explanation_audit_report",
    )
    assert dashboard_builder_names[0] in source
    assert all(name not in source for name in direct_builder_names)
    assert SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_MARKER_IDS == (
        SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS
    )
    assert "for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS" in (
        function_body
    )
    assert "scene_release_governance_report_spec(report_id)" in function_body
    assert "build_scene_release_governance_report(\n            report_id" in (
        function_body
    )
    assert "spec.builder_dependency_names" in function_body
    assert all(
        f'"{report_id}"' not in function_body
        for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS
    )
    assert "scene_release_governance_report_id(report_attribute)" in (
        card_source_helper_body
    )
    assert "report.issue_count == 0" in card_variant_helper_body
    assert "_release_governance_card_source_ids(" in release_cards_body
    assert "_dashboard_report_issue_variant(" in release_cards_body
    assert "_release_governance_cards(" in cards_body
    assert 'card_id="boundary_guarded_completion"' not in cards_body
    assert "residual_warning_governance_report.unmanaged_warning_count == 0" in (
        release_cards_body
    )
    assert "boundary_readiness_reconciliation_report.unreconciled_count == 0" in (
        release_cards_body
    )
    assert "terminal_release_exception_report.ungoverned_exception_count == 0" in (
        release_cards_body
    )
    assert all(
        scene_release_governance_report_id(spec.report_attribute) == spec.report_id
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        f'"{spec.report_attribute}"' in release_cards_body
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        f'"{spec.report_id}"' not in release_cards_body
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
    assert all(
        f'"{spec.report_id}"' not in cards_body
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )


def test_release_gate_payload_uses_release_governance_registry_for_reports():
    source = (
        ROOT / "scripts" / "scene_matrix_release_gate_payload.py"
    ).read_text(encoding="utf-8")
    function_body = source.split(
        "def _build_release_gate_governance_reports(",
        maxsplit=1,
    )[1].split(
        "def _build_release_gate_material_delivery_reports(",
        maxsplit=1,
    )[0]

    assert "for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS" in (
        function_body
    )
    assert "scene_release_governance_report_spec(report_id)" in function_body
    assert "build_scene_release_governance_report(\n            report_id" in (
        function_body
    )
    assert all(
        f'"{report_id}"' not in function_body
        for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS
    )

    dashboard_function_body = source.split(
        "def _build_release_gate_dashboard_residual_reports(",
        maxsplit=1,
    )[1].split(
        "def build_scene_matrix_release_gate_payload(",
        maxsplit=1,
    )[0]

    assert "for report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS" in (
        dashboard_function_body
    )
    assert "scene_release_governance_report_spec(report_id)" in (
        dashboard_function_body
    )
    assert "build_scene_release_governance_report(\n            report_id" in (
        dashboard_function_body
    )
    assert all(
        f'"{report_id}"' not in dashboard_function_body
        for report_id in SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS
    )


def test_scene_matrix_dashboard_lenses_use_release_governance_registry_sources():
    source = (
        ROOT / "src" / "config" / "scene_matrix_dashboard_lenses.py"
    ).read_text(encoding="utf-8")
    expected_source_ids = (
        *(
            report_id
            for report_id in SCENE_RELEASE_GOVERNANCE_EARLY_GATE_CHECK_IDS
            if report_id != SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID
        ),
        *SCENE_RELEASE_GOVERNANCE_DASHBOARD_GATE_CHECK_IDS,
        SCENE_RELEASE_ACCEPTANCE_CERTIFICATE_AUDIT_SOURCE_ID,
    )

    assert SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS == (
        expected_source_ids
    )
    assert SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS == (
        SCENE_RELEASE_GOVERNANCE_DASHBOARD_SOURCE_IDS
    )
    assert set(SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS) == {
        spec.report_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    }
    assert "SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_SOURCE_IDS" in source
    assert all(
        f'"{spec.report_id}"' not in source
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )


def test_scene_matrix_dashboard_release_counts_are_registry_backed():
    source = (ROOT / "src" / "config" / "scene_matrix_dashboard.py").read_text(
        encoding="utf-8"
    )
    function_body = source.split(
        "def _build_scene_matrix_dashboard_uncached(",
        maxsplit=1,
    )[1].split(
        "def _filter_rows(",
        maxsplit=1,
    )[0]
    count_helper_body = source.split(
        "def _release_governance_dashboard_count_entries(",
        maxsplit=1,
    )[1].split(
        "def _dashboard_report_issue_variant(",
        maxsplit=1,
    )[0]
    export_script_count_ids = {
        spec.count_id for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_COUNT_SPECS
    }
    dashboard_release_count_ids = tuple(
        spec.count_id.removeprefix("scene_")
        for spec in SCENE_RELEASE_GOVERNANCE_DETAIL_COUNT_SPECS
        if spec.count_id not in export_script_count_ids
    )
    dashboard_field_ids = {field.name for field in fields(SceneMatrixDashboardReport)}

    assert set(dashboard_release_count_ids) <= dashboard_field_ids
    assert "scene_release_governance_count_entries(" in count_helper_body
    assert "SCENE_MATRIX_DASHBOARD_RELEASE_GOVERNANCE_COUNT_SPECS" in (
        count_helper_body
    )
    assert "**release_governance_dashboard_counts" in function_body
    assert "release_governance_dashboard_reports = {" in function_body
    assert "release_residual_explanation_report" in function_body
    assert "release_projection_surface_parity_count=(" not in function_body
    assert "release_closure_ledger_stage_count=(" not in function_body
    assert "release_acceptance_certificate_count=(" not in function_body
    assert "residual_warning_governance_input_source_managed_warning_count=" in (
        function_body
    )
    assert "dashboard_warning_projection_governed_count=" in function_body
    assert "retained_gap_enveloped_count=" in function_body
