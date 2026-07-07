import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    _print_human,
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_release_acceptance_certificate_audit import (  # noqa: E402
    audit_scene_release_acceptance_certificate_report,
    build_scene_release_acceptance_certificate_audit_report,
)


def test_release_acceptance_certificate_certifies_release_surfaces():
    report = build_scene_release_acceptance_certificate_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.certificate_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_release_acceptance_certificate_report(report) == ()
    assert payload["source_id"] == "scene_release_acceptance_certificate_audit"
    assert report.certificate_count == 14
    assert report.ready_certificate_count == 14
    assert report.receipt_certificate_count == 2
    assert report.ready_receipt_certificate_count == 2
    assert report.component_report_count == 14
    assert report.expected_count_match_count == 14
    assert payload["counts"]["receipt_certificate_count"] == 2
    assert payload["counts"]["ready_receipt_certificate_count"] == 2
    assert payload["counts"]["requirement_dimension_count"] == 10
    assert payload["counts"]["ready_requirement_dimension_count"] == 10
    assert payload["counts"]["source_evidence_count"] == 15
    assert payload["counts"]["ready_source_evidence_count"] == 15
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    source_status = {
        item["source_id"]: item["status"] for item in payload["source_evidence"]
    }
    assert source_status["scene_matrix_dashboard"] == "ready"
    assert source_status["summary_projection"] == "ready"
    assert source_status["release_gate"] == "ready"
    assert source_status["export_script"] == "ready"
    assert source_status["acceptance_certificate_test"] == "ready"
    assert source_status["n2_394_plan"] == "ready"
    assert source_status["n2_395_requirement_trace_plan"] == "ready"
    assert source_status["n2_397_retained_gap_receipt_plan"] == "ready"
    assert source_status["n2_398_residual_ratio_receipt_plan"] == "ready"
    assert source_status["n2_399_projection_trace_plan"] == "ready"
    assert source_status["n2_400_acceptance_receipt_plan"] == "ready"

    assert rows["high_frequency_coverage"].observed_ratio == "12/12"
    assert rows["release_projection_surface_parity"].observed_ratio == "13/13"
    assert rows["release_closure_ledger"].observed_ratio == "13/13"
    assert rows["boundary_maturity_release_envelope"].observed_ratio == "6/6"
    assert rows["release_residual_ratio_ledger"].observed_ratio == "3/3"
    assert rows["release_residual_ratio_exit_criteria"].observed_ratio == "10/10"
    assert rows["release_residual_ratio_receipts"].observed_ratio == "10/10"
    assert rows["count_delivery_boundary_alignment"].observed_ratio == "4/4"
    assert rows["maturity_l5_blocker_alignment"].observed_ratio == "6/6"
    assert rows["release_residual_boundary_scope_alignment"].observed_ratio == "6/6"
    assert rows["release_residual_explanation"].observed_ratio == "14/14"
    assert rows["retained_gap_exit_criteria"].observed_ratio == "6/6"
    assert rows["retained_gap_external_receipts"].observed_ratio == "6/6"
    assert rows["release_governance_export_scripts"].observed_ratio == "15/15"
    assert all(row.status == "certificate_ready" for row in report.rows)

    dimensions = {row.dimension_id: row for row in report.requirement_dimension_rows}
    assert dimensions["high_frequency_scene_coverage"].observed_ratio == "12/12"
    assert dimensions["scene_board_control_style_consistency"].observed_ratio == "25/25"
    assert dimensions["formula_output_watermark_scene_ownership"].observed_ratio == "18/18"
    assert (
        dimensions["residual_boundary_release_governance"].observed_ratio
        == "65/65"
    )
    assert dimensions["projection_export_visibility"].observed_ratio == "28/28"
    assert all(row.status == "dimension_ready" for row in report.requirement_dimension_rows)


def test_release_acceptance_certificate_export_script_supports_json_and_markdown(
    tmp_path,
):
    output_path = tmp_path / "scene_release_acceptance_certificate.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_acceptance_certificate_audit.py",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert json_result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["ready_certificate_count"] == 14
    assert payload["counts"]["ready_receipt_certificate_count"] == 2
    assert payload["counts"]["receipt_certificate_count"] == 2
    assert payload["counts"]["ready_requirement_dimension_count"] == 10
    rows = {row["certificate_id"]: row for row in payload["rows"]}
    dimensions = {row["dimension_id"]: row for row in payload["requirement_dimension_rows"]}
    assert rows["high_frequency_coverage"]["observed_ratio"] == "12/12"
    assert rows["high_frequency_coverage"]["expected_ratio"] == "12/12"
    assert rows["high_frequency_coverage"]["status"] == "certificate_ready"
    assert rows["release_governance_export_scripts"]["observed_ratio"] == "15/15"
    assert rows["release_governance_export_scripts"]["expected_ratio"] == "15/15"
    assert rows["count_delivery_boundary_alignment"]["observed_ratio"] == "4/4"
    assert rows["count_delivery_boundary_alignment"]["expected_ratio"] == "4/4"
    assert rows["maturity_l5_blocker_alignment"]["observed_ratio"] == "6/6"
    assert rows["maturity_l5_blocker_alignment"]["expected_ratio"] == "6/6"
    assert rows["release_residual_ratio_receipts"]["observed_ratio"] == "10/10"
    assert rows["release_residual_ratio_receipts"]["expected_ratio"] == "10/10"
    assert (
        rows["release_residual_boundary_scope_alignment"]["observed_ratio"]
        == "6/6"
    )
    assert (
        rows["release_residual_boundary_scope_alignment"]["expected_ratio"]
        == "6/6"
    )
    assert rows["retained_gap_external_receipts"]["observed_ratio"] == "6/6"
    assert rows["retained_gap_external_receipts"]["expected_ratio"] == "6/6"
    assert dimensions["high_frequency_scene_coverage"]["observed_ratio"] == "12/12"
    assert dimensions["formula_output_watermark_scene_ownership"]["status"] == (
        "dimension_ready"
    )

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_acceptance_certificate_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Acceptance Certificate Audit" in markdown_result.stdout
    assert "Certificates ready: 14/14" in markdown_result.stdout
    assert "Receipt certificates ready: 2/2" in markdown_result.stdout
    assert "Requirement dimensions ready: 10/10" in markdown_result.stdout
    assert "high_frequency_coverage" in markdown_result.stdout
    assert "high_frequency_scene_coverage" in markdown_result.stdout
    assert "release_projection_surface_parity" in markdown_result.stdout
    assert "release_residual_ratio_ledger" in markdown_result.stdout
    assert "release_residual_ratio_exit_criteria" in markdown_result.stdout
    assert "release_residual_ratio_receipts" in markdown_result.stdout
    assert "count_delivery_boundary_alignment" in markdown_result.stdout
    assert "maturity_l5_blocker_alignment" in markdown_result.stdout
    assert "release_residual_boundary_scope_alignment" in markdown_result.stdout
    assert "release_residual_explanation" in markdown_result.stdout
    assert "retained_gap_exit_criteria" in markdown_result.stdout
    assert "retained_gap_external_receipts" in markdown_result.stdout
    assert "release_governance_export_scripts" in markdown_result.stdout
    assert "formula_output_watermark_scene_ownership" in markdown_result.stdout


def test_release_gate_includes_release_acceptance_certificate(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_acceptance_certificate_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["high_frequency_completeness_ready_pack_count"] == 12
    assert payload["counts"]["high_frequency_completeness_pack_count"] == 12
    assert payload["counts"]["scene_release_acceptance_certificate_count"] == 14
    assert payload["counts"]["scene_release_acceptance_certificate_ready_count"] == 14
    assert payload["counts"]["scene_release_acceptance_certificate_receipt_count"] == 2
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_receipt_count"
        ]
        == 2
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_requirement_dimension_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_requirement_dimension_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_expected_count_match_count"
        ]
        == 14
    )
    assert payload["counts"]["scene_release_acceptance_certificate_issue_count"] == 0
    assert (
        payload["counts"]["scene_release_governance_export_script_report_count"]
        == 15
    )
    assert (
        payload["counts"]["scene_release_governance_export_script_ready_count"]
        == 15
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_source_evidence_count"
        ]
        == 15
    )
    assert (
        payload["counts"][
            "scene_retained_gap_external_receipt_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_receipt_alignment_link_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_count_delivery_boundary_alignment_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_count_delivery_boundary_link_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_boundary_scope_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_boundary_scope_link_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_acceptance_certificate_ready_source_evidence_count"
        ]
        == 15
    )
    assert (
        payload["scene_release_acceptance_certificate_audit"]["counts"][
            "ready_certificate_count"
        ]
        == 14
    )
    assert (
        payload["scene_release_acceptance_certificate_audit"]["counts"][
            "ready_receipt_certificate_count"
        ]
        == 2
    )
    assert (
        payload["scene_release_acceptance_certificate_audit"]["counts"][
            "ready_source_evidence_count"
        ]
        == 15
    )

    _print_human(payload)
    output = capsys.readouterr().out
    assert "acceptance_certificate=14/14" in output
    assert "acceptance_receipts=2/2" in output
    assert "retained_gap_receipts=6/6" in output
    assert "residual_ratio_receipts=10/10" in output
    assert "count_delivery_alignment=4/4" in output
    assert "maturity_l5_alignment=6/6" in output
    assert "boundary_scope_alignment=6/6" in output
    assert "requirement_dimensions=10/10" in output
    assert "acceptance_evidence=15/15" in output
    assert "release_export_scripts=15/15 ready" in output
