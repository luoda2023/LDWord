import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_residual_warning_governance_audit import (  # noqa: E402
    audit_scene_residual_warning_governance_report,
    build_scene_residual_warning_governance_audit_report,
)


def test_residual_warning_governance_manages_every_remaining_warning():
    report = build_scene_residual_warning_governance_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.row_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_residual_warning_governance_report(report) == ()
    assert payload["counts"]["warning_count"] == 10
    assert payload["counts"]["managed_warning_count"] == 10
    assert payload["counts"]["input_source_warning_count"] == 5
    assert payload["counts"]["input_source_managed_warning_count"] == 5
    assert payload["counts"]["count_profile_warning_count"] == 2
    assert payload["counts"]["count_profile_managed_warning_count"] == 2
    assert payload["counts"]["dashboard_projection_warning_count"] == 3
    assert payload["counts"]["plugin_manual_warning_count"] == 5
    assert payload["counts"]["plugin_manual_managed_warning_count"] == 5
    assert payload["counts"]["reference_profile_warning_count"] == 2
    assert payload["counts"]["reference_profile_managed_warning_count"] == 2
    assert payload["counts"]["object_preflight_warning_count"] == 0
    assert payload["counts"]["visio_fixture_closed_count"] == 1
    assert payload["counts"]["unmanaged_warning_count"] == 0
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"
    assert source_status["n2_393f_plan"] == "ready"
    assert source_status["n2_393h_plan"] == "ready"

    assert set(rows).issuperset(
        {
            "scene_input_source_audit:family:ip_patent_documents:plugin_manual_boundary_input_contract",
            "scene_input_source_audit:pack:exam_education:pack_requires_plugin_or_manual_input_boundary",
            "scene_input_source_audit:pack:professional_disclosure:pack_requires_plugin_or_manual_input_boundary",
            "scene_input_source_audit:pack:import_ai_boundary:pack_input_axis_boundary_only",
            "scene_input_source_audit:pack:import_ai_boundary:pack_requires_plugin_or_manual_input_boundary",
            "scene_count_profile_audit:count_profile:basic:registry_only_profile",
            "scene_count_profile_audit:count_profile:word_xml_full:registry_only_profile",
            "scene_matrix_dashboard:pack:exam_education:input_source_warnings",
            "scene_matrix_dashboard:pack:professional_disclosure:input_source_warnings",
            "scene_matrix_dashboard:pack:import_ai_boundary:input_source_warnings",
        }
    )
    assert rows[
        "scene_input_source_audit:pack:exam_education:pack_requires_plugin_or_manual_input_boundary"
    ].linked_plugin_gate_ids == ("exam_ai_complex_diagram_gate",)
    assert rows[
        "scene_input_source_audit:pack:professional_disclosure:pack_requires_plugin_or_manual_input_boundary"
    ].linked_boundary_subject_ids == ("pack:professional_disclosure",)
    assert rows[
        "scene_count_profile_audit:count_profile:word_xml_full:registry_only_profile"
    ].linked_profile_ids == ("word_xml_full",)


def test_residual_warning_governance_filters_by_warning_source():
    report = build_scene_residual_warning_governance_audit_report(
        source_id="scene_input_source_audit",
        project_root=ROOT,
    )

    assert report.status == "passed"
    assert report.warning_count == 5
    assert report.managed_warning_count == 5
    assert {row.source_id for row in report.rows} == {"scene_input_source_audit"}


def test_residual_warning_governance_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_residual_warning_governance_audit.py",
            "--format",
            "json",
            "--source",
            "scene_count_profile_audit",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["warning_count"] == 2
    assert payload["counts"]["managed_warning_count"] == 2
    assert payload["counts"]["count_profile_managed_warning_count"] == 2
    assert payload["counts"]["reference_profile_managed_warning_count"] == 2
    assert all(
        row["source_id"] == "scene_count_profile_audit"
        for row in payload["rows"]
    )
    rows = {row["row_id"]: row for row in payload["rows"]}
    basic = rows[
        "scene_count_profile_audit:count_profile:basic:registry_only_profile"
    ]
    assert basic["status"] == "managed_warning"
    assert basic["governance_mode"] == "reference_count_profile"
    assert basic["linked_profile_ids"] == ["basic"]
    word_xml = rows[
        "scene_count_profile_audit:count_profile:word_xml_full:registry_only_profile"
    ]
    assert "report_surface" in word_xml["evidence_ids"]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_residual_warning_governance_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Residual Warning Governance Audit" in markdown_result.stdout
    assert "Managed warnings: 10/10" in markdown_result.stdout
    assert "visio_fixture_closed_count" not in markdown_result.stdout
    assert "scene_residual_warning_governance_audit" in markdown_result.stdout


def test_release_gate_includes_residual_warning_governance(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert (
        payload["checks"]["scene_residual_warning_governance_audit"]["status"]
        == "passed"
    )
    assert payload["counts"]["scene_residual_warning_governance_warning_count"] == 10
    assert payload["counts"]["scene_residual_warning_governance_managed_count"] == 10
    assert (
        payload["counts"][
            "scene_residual_warning_governance_input_source_warning_count"
        ]
        == 5
    )
    assert payload["counts"]["input_source_warning_managed_count"] == 5
    assert (
        payload["counts"][
            "scene_residual_warning_governance_count_profile_warning_count"
        ]
        == 2
    )
    assert payload["counts"]["count_profile_warning_managed_count"] == 2
    assert payload["counts"]["plugin_manual_warning_managed_count"] == 5
    assert payload["counts"]["reference_profile_warning_managed_count"] == 2
    assert payload["counts"]["visio_fixture_closed_verified_count"] == 1
    assert (
        payload["counts"]["input_source_warning_managed_count"]
        == payload["counts"]["scene_input_source_warning_count"]
    )
    assert (
        payload["counts"]["count_profile_warning_managed_count"]
        == payload["counts"]["scene_count_profile_warning_count"]
    )
    assert (
        payload["counts"]["plugin_manual_warning_managed_count"]
        == payload["counts"][
            "scene_residual_warning_governance_plugin_manual_warning_count"
        ]
    )
    assert (
        payload["counts"]["reference_profile_warning_managed_count"]
        == payload["counts"][
            "scene_residual_warning_governance_reference_profile_warning_count"
        ]
    )
    assert (
        payload["counts"]["visio_fixture_closed_verified_count"]
        == payload["counts"][
            "scene_residual_warning_governance_visio_fixture_closed_count"
        ]
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_dashboard_projection_warning_count"
        ]
        == 3
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_object_preflight_warning_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "scene_residual_warning_governance_unmanaged_warning_count"
        ]
        == 0
    )
    assert (
        payload["scene_residual_warning_governance_audit"]["counts"][
            "visio_fixture_closed_count"
        ]
        == 1
    )
