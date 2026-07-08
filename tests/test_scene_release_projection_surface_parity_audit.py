import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_release_projection_surface_parity_audit import (  # noqa: E402
    SCENE_RELEASE_PROJECTION_SURFACE_SPECS,
    audit_scene_release_projection_surface_parity_report,
    build_scene_release_projection_surface_parity_audit_report,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
)


def test_release_projection_surfaces_are_projected_across_gate_and_ui():
    report = build_scene_release_projection_surface_parity_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.projection_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_release_projection_surface_parity_report(report) == ()
    assert payload["counts"]["projection_count"] == 13
    assert payload["counts"]["ready_projection_count"] == 13
    assert payload["counts"]["release_gate_check_count"] == 13
    assert payload["counts"]["dashboard_source_count"] == 13
    assert payload["counts"]["dashboard_card_count"] == 13
    assert payload["counts"]["drilldown_item_count"] == 13
    assert payload["counts"]["summary_projection_count"] == 13
    assert payload["counts"]["export_script_count"] == 13
    assert payload["counts"]["workflow_test_count"] == 13
    assert payload["counts"]["closure_doc_count"] == 13
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }
    assert source_status["export_script"] == "ready"
    assert source_status["n2_395_requirement_trace_plan"] == "ready"
    assert source_status["n2_398_receipt_alignment_plan"] == "ready"
    assert source_status["n2_399_projection_trace_plan"] == "ready"
    assert source_status["n2_400_acceptance_receipt_plan"] == "ready"
    assert source_status["n2_401_acceptance_projection_trace_plan"] == "ready"
    projection_ids = tuple(row.projection_id for row in report.rows)
    assert projection_ids == tuple(
        spec.projection_id for spec in SCENE_RELEASE_PROJECTION_SURFACE_SPECS
    )
    assert "release_closure_ledger" in projection_ids
    assert "release_projection_surface_parity" not in projection_ids
    assert rows["release_trace_partition_guard"].dashboard_card_id == (
        "release_trace_partition"
    )
    assert rows["non_subject_release_trace_attribution"].drilldown_id == (
        "non_subject_release_trace_attribution"
    )
    assert rows["terminal_release_trace_ledger"].summary_marker == (
        "exception traces"
    )
    assert rows["boundary_subject_release_continuity"].dashboard_card_id == (
        "boundary_subject_continuity"
    )
    assert rows["release_closure_ledger"].drilldown_id == "release_closure_ledger"
    assert rows["boundary_maturity_release_envelope"].dashboard_card_id == (
        "boundary_release_envelopes"
    )
    assert rows["release_residual_ratio_ledger"].dashboard_card_id == (
        "release_residual_ratios"
    )
    assert "residual_ratio_receipt_alignment_trace" in (
        rows["release_residual_ratio_ledger"].evidence_ids
    )
    assert rows[
        "release_residual_ratio_ledger"
    ].supplemental_closure_doc_paths == (
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md",
    )
    assert rows["release_acceptance_certificate"].dashboard_card_id == (
        "release_acceptance_certificate"
    )
    assert "requirement_dimension_trace" in (
        rows["release_acceptance_certificate"].evidence_ids
    )
    assert "acceptance_receipt_trace" in (
        rows["release_acceptance_certificate"].evidence_ids
    )
    assert rows[
        "release_acceptance_certificate"
    ].supplemental_closure_doc_paths == (
        "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md",
        "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md",
        "docs/audits/scene_release_acceptance_projection_trace_N2_401_2026-06-25.md",
    )


def test_release_projection_surface_registry_paths_do_not_drift():
    registry_specs = {
        spec.report_id: spec for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    }
    source = (
        ROOT / "src" / "config" / "scene_release_projection_surface_parity_audit.py"
    ).read_text(encoding="utf-8")
    spec_block = source.split("SCENE_RELEASE_PROJECTION_SURFACE_SPECS", 1)[1].split(
        "class SceneReleaseProjectionSurfaceParityIssue", 1
    )[0]

    assert "def release_gate_check_id(self) -> str:" in source
    assert "return self.audit_source_id" in source
    assert "scene_release_governance_report_spec(" in source
    assert "self.audit_source_id" in source
    assert "release_gate_check_id=" not in spec_block
    assert "export_script_path=" not in spec_block
    assert "test_path=" not in spec_block
    assert "dashboard_card_id=" in spec_block
    assert "drilldown_id=" in spec_block
    assert "summary_marker=" in spec_block

    for spec in SCENE_RELEASE_PROJECTION_SURFACE_SPECS:
        registry_spec = registry_specs[spec.audit_source_id]

        assert spec.release_gate_check_id == spec.audit_source_id
        assert spec.export_script_path == registry_spec.export_script_path
        assert spec.test_path == registry_spec.test_path


def test_release_projection_surface_parity_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_projection_surface_parity_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["projection_count"] == 13
    assert payload["counts"]["ready_projection_count"] == 13
    rows = {row["projection_id"]: row for row in payload["rows"]}
    continuity = rows["boundary_subject_release_continuity"]
    assert continuity["dashboard_card_id"] == "boundary_subject_continuity"
    assert continuity["export_script_path"] == (
        "scripts/export_scene_boundary_subject_release_continuity_audit.py"
    )
    assert "export_script" in continuity["evidence_ids"]
    residual = rows["release_residual_ratio_ledger"]
    assert residual["dashboard_card_id"] == "release_residual_ratios"
    assert residual["drilldown_id"] == "release_residual_ratio_ledger"
    assert "closure_doc" in residual["evidence_ids"]
    assert "residual_ratio_receipt_alignment_trace" in residual["evidence_ids"]
    assert residual["supplemental_evidence_ids"] == [
        "residual_ratio_receipt_alignment_trace"
    ]
    assert residual["supplemental_closure_doc_paths"] == [
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md"
    ]
    acceptance = rows["release_acceptance_certificate"]
    assert acceptance["audit_source_id"] == (
        "scene_release_acceptance_certificate_audit"
    )
    assert acceptance["test_path"] == (
        "tests/test_scene_release_acceptance_certificate_audit.py"
    )
    assert "requirement_dimension_trace" in acceptance["evidence_ids"]
    assert "acceptance_receipt_trace" in acceptance["evidence_ids"]
    assert acceptance["supplemental_evidence_ids"] == [
        "requirement_dimension_trace",
        "acceptance_receipt_trace",
    ]
    assert acceptance["supplemental_closure_doc_paths"] == [
        "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md",
        "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md",
        "docs/audits/scene_release_acceptance_projection_trace_N2_401_2026-06-25.md",
    ]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_projection_surface_parity_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Projection Surface Parity Audit" in (
        markdown_result.stdout
    )
    assert "Projections ready: 13/13" in markdown_result.stdout
    assert "release_trace_partition_guard" in markdown_result.stdout
    assert "boundary_subject_release_dossier" in markdown_result.stdout
    assert "terminal_release_trace_ledger" in markdown_result.stdout
    assert "boundary_subject_release_continuity" in markdown_result.stdout
    assert "release_closure_ledger" in markdown_result.stdout
    assert "boundary_maturity_release_envelope" in markdown_result.stdout
    assert "release_residual_ratio_ledger" in markdown_result.stdout
    assert "release_acceptance_certificate" in markdown_result.stdout
    assert "residual_ratio_receipt_alignment_trace" in markdown_result.stdout
    assert "residual_ratio_receipts=" in markdown_result.stdout
    assert (
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md"
        in markdown_result.stdout
    )
    assert "requirement_dimension_trace" in markdown_result.stdout
    assert "requirement_dimensions=" in markdown_result.stdout
    assert "acceptance_receipt_trace" in markdown_result.stdout
    assert "acceptance_evidence=" in markdown_result.stdout
    assert (
        "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md"
        in markdown_result.stdout
    )
    assert (
        "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md"
        in markdown_result.stdout
    )
    assert (
        "docs/audits/scene_release_acceptance_projection_trace_N2_401_2026-06-25.md"
        in markdown_result.stdout
    )


def test_release_gate_includes_release_projection_surface_parity(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_projection_surface_parity_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_release_projection_surface_parity_count"] == 13
    assert (
        payload["counts"]["scene_release_projection_surface_parity_ready_count"]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_release_gate_check_count"
        ]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_dashboard_card_count"
        ]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_drilldown_item_count"
        ]
        == 13
    )
    assert (
        payload["counts"][
            "scene_release_projection_surface_parity_summary_projection_count"
        ]
        == 13
    )
    assert (
        payload["counts"]["scene_release_projection_surface_parity_issue_count"]
        == 0
    )
