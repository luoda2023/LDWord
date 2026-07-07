import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_non_subject_release_trace_attribution_audit import (  # noqa: E402
    audit_scene_non_subject_release_trace_attribution_report,
    build_scene_non_subject_release_trace_attribution_audit_report,
)


def test_non_subject_release_traces_are_attributed_without_subject_dossiers():
    report = build_scene_non_subject_release_trace_attribution_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.trace_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_non_subject_release_trace_attribution_report(report) == ()
    assert payload["counts"]["trace_count"] == 10
    assert payload["counts"]["attributed_trace_count"] == 10
    assert payload["counts"]["unattributed_trace_count"] == 0
    assert payload["counts"]["dashboard_projection_trace_count"] == 6
    assert payload["counts"]["registry_only_profile_trace_count"] == 2
    assert payload["counts"]["plugin_manual_pack_trace_count"] == 1
    assert payload["counts"]["generic_not_applicable_trace_count"] == 1
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"

    assert any(
        row.attribution_kind == "plugin_manual_pack_boundary"
        and row.scope_id == "exam_education"
        for row in report.rows
    )
    assert rows[
        "boundary_readiness_reconciliation:scene_count_profile_audit:pack_not_applicable_delta:pack:quick_formatting"
    ].attribution_kind == "generic_not_applicable_surface"
    assert {
        row.scope_id
        for row in report.rows
        if row.attribution_kind == "registry_only_profile_reference"
    } == {"basic", "word_xml_full"}


def test_non_subject_release_trace_attribution_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_non_subject_release_trace_attribution_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["trace_count"] == 10
    assert payload["counts"]["attributed_trace_count"] == 10
    rows = {row["trace_id"]: row for row in payload["rows"]}
    exam_trace = rows[
        "managed_residual_warnings:scene_input_source_audit:pack:exam_education:pack_requires_plugin_or_manual_input_boundary"
    ]
    assert exam_trace["attribution_kind"] == "plugin_manual_pack_boundary"
    assert exam_trace["scope_type"] == "pack"
    assert exam_trace["scope_id"] == "exam_education"
    assert "plugin_manual_pack_boundary" in exam_trace["evidence_ids"]
    basic_trace = rows[
        "managed_residual_warnings:scene_count_profile_audit:count_profile:basic:registry_only_profile"
    ]
    assert basic_trace["attribution_kind"] == "registry_only_profile_reference"
    assert basic_trace["linked_profile_ids"] == ["basic"]
    quick_trace = rows[
        "boundary_readiness_reconciliation:scene_count_profile_audit:pack_not_applicable_delta:pack:quick_formatting"
    ]
    assert quick_trace["attribution_kind"] == "generic_not_applicable_surface"
    assert quick_trace["linked_pack_ids"] == ["quick_formatting"]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_non_subject_release_trace_attribution_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Non-Subject Release Trace Attribution Audit" in (
        markdown_result.stdout
    )
    assert "Attributed traces: 10/10" in markdown_result.stdout
    assert "dashboard_projection_surface" in markdown_result.stdout
    assert "generic_not_applicable_surface" in markdown_result.stdout


def test_release_gate_includes_non_subject_release_trace_attribution(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_non_subject_release_trace_attribution_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_non_subject_release_trace_attribution_count"] == 10
    assert (
        payload["counts"]["scene_non_subject_release_trace_attribution_ready_count"]
        == 10
    )
    assert (
        payload["counts"][
            "scene_non_subject_release_trace_attribution_unattributed_count"
        ]
        == 0
    )
    assert (
        payload["counts"][
            "scene_non_subject_release_trace_attribution_dashboard_projection_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_non_subject_release_trace_attribution_registry_only_profile_count"
        ]
        == 2
    )
