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
from src.config.scene_release_closure_ledger_audit import (  # noqa: E402
    SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS,
    audit_scene_release_closure_ledger_report,
    build_scene_release_closure_ledger_audit_report,
)
from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
    build_scene_release_governance_report,
)


def test_release_closure_ledger_orders_release_stages_across_surfaces():
    report = build_scene_release_closure_ledger_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.stage_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_release_closure_ledger_report(report) == ()
    assert payload["counts"]["stage_count"] == 13
    assert payload["counts"]["ready_stage_count"] == 13
    assert payload["counts"]["stage_order_count"] == 13
    assert payload["counts"]["upstream_dependency_count"] == 18
    assert payload["counts"]["upstream_dependency_ready_count"] == 18
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
        item["source_id"]: item["status"] for item in payload["source_evidence"]
    }
    assert source_status["export_script"] == "ready"
    assert source_status["n2_390_index"] == "ready"
    assert source_status["n2_395_requirement_trace_plan"] == "ready"
    assert source_status["n2_398_receipt_alignment_plan"] == "ready"
    assert source_status["n2_399_projection_trace_plan"] == "ready"
    assert source_status["n2_400_acceptance_receipt_plan"] == "ready"
    assert source_status["n2_401_acceptance_projection_trace_plan"] == "ready"
    stage_ids = tuple(row.stage_id for row in report.rows)
    assert stage_ids == tuple(
        spec.stage_id for spec in SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS
    )
    assert "release_projection_surface_parity" in stage_ids
    assert "release_closure_ledger" not in stage_ids
    assert rows["terminal_release_trace_ledger"].source_id == (
        "scene_terminal_release_exception_audit"
    )
    assert rows["release_trace_partition_guard"].upstream_stage_ids == (
        "boundary_subject_release_dossier",
        "non_subject_release_trace_attribution",
    )
    assert rows["boundary_subject_release_continuity"].upstream_stage_ids == (
        "boundary_subject_release_dossier",
        "release_projection_surface_parity",
    )
    assert rows["boundary_maturity_release_envelope"].upstream_stage_ids == (
        "boundary_subject_release_continuity",
        "release_projection_surface_parity",
    )
    assert rows["release_residual_ratio_ledger"].upstream_stage_ids == (
        "boundary_readiness_reconciliation",
        "boundary_maturity_release_envelope",
    )
    assert "residual_ratio_receipt_alignment_trace" in (
        rows["release_residual_ratio_ledger"].evidence_ids
    )
    assert rows[
        "release_residual_ratio_ledger"
    ].supplemental_closure_doc_paths == (
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md",
    )
    assert rows["release_acceptance_certificate"].upstream_stage_ids == (
        "release_projection_surface_parity",
        "release_residual_ratio_ledger",
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


def test_release_governance_reports_expose_export_script_source_evidence():
    missing_export_script = []
    unready_export_script = []

    for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS:
        payload = build_scene_release_governance_report(
            spec.report_id, project_root=ROOT
        ).to_payload()
        source_status = {
            item["source_id"]: item["status"] for item in payload["source_evidence"]
        }

        assert payload["source_id"] == spec.report_id
        if "export_script" not in source_status:
            missing_export_script.append(spec.report_id)
            continue
        if source_status["export_script"] != "ready":
            unready_export_script.append(
                (spec.report_id, source_status["export_script"])
            )

    assert missing_export_script == []
    assert unready_export_script == []


def test_release_closure_ledger_registry_paths_do_not_drift():
    registry_specs = {
        spec.report_id: spec for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    }
    source = (
        ROOT / "src" / "config" / "scene_release_closure_ledger_audit.py"
    ).read_text(encoding="utf-8")
    spec_block = source.split("SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS", 1)[
        1
    ].split("class SceneReleaseClosureLedgerIssue", 1)[0]

    assert "def release_gate_check_id(self) -> str:" in source
    assert "return self.source_id" in source
    assert "scene_release_governance_report_spec(self.source_id)" in source
    assert "release_gate_check_id=" not in spec_block
    assert "export_script_path=" not in spec_block
    assert "test_path=" not in spec_block
    assert "dashboard_card_id=" in spec_block
    assert "drilldown_id=" in spec_block
    assert "summary_marker=" in spec_block

    for spec in SCENE_RELEASE_CLOSURE_LEDGER_STAGE_SPECS:
        registry_spec = registry_specs[spec.source_id]

        assert spec.release_gate_check_id == spec.source_id
        assert spec.export_script_path == registry_spec.export_script_path
        assert spec.test_path == registry_spec.test_path


def test_release_closure_ledger_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_closure_ledger_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["stage_count"] == 13
    assert payload["counts"]["ready_stage_count"] == 13
    rows = {row["stage_id"]: row for row in payload["rows"]}
    assert rows["release_residual_ratio_ledger"]["order"] == 12
    assert rows["release_residual_ratio_ledger"]["upstream_stage_ids"] == [
        "boundary_readiness_reconciliation",
        "boundary_maturity_release_envelope",
    ]
    assert "export_script" in rows["release_residual_ratio_ledger"]["evidence_ids"]
    assert (
        "residual_ratio_receipt_alignment_trace"
        in rows["release_residual_ratio_ledger"]["evidence_ids"]
    )
    assert rows["release_residual_ratio_ledger"]["supplemental_evidence_ids"] == [
        "residual_ratio_receipt_alignment_trace"
    ]
    assert rows["release_residual_ratio_ledger"][
        "supplemental_closure_doc_paths"
    ] == [
        "docs/audits/scene_release_residual_ratio_receipt_alignment_N2_398_2026-06-25.md"
    ]
    assert rows["release_acceptance_certificate"]["order"] == 13
    assert rows["release_acceptance_certificate"]["upstream_stage_ids"] == [
        "release_projection_surface_parity",
        "release_residual_ratio_ledger",
    ]
    assert "closure_doc" in rows["release_acceptance_certificate"]["evidence_ids"]
    assert (
        "requirement_dimension_trace"
        in rows["release_acceptance_certificate"]["evidence_ids"]
    )
    assert (
        "acceptance_receipt_trace"
        in rows["release_acceptance_certificate"]["evidence_ids"]
    )
    assert rows["release_acceptance_certificate"]["supplemental_evidence_ids"] == [
        "requirement_dimension_trace",
        "acceptance_receipt_trace",
    ]
    assert rows["release_acceptance_certificate"]["supplemental_closure_doc_paths"] == [
        "docs/audits/scene_release_acceptance_requirement_trace_N2_395_2026-06-25.md",
        "docs/audits/scene_release_acceptance_receipt_trace_N2_400_2026-06-25.md",
        "docs/audits/scene_release_acceptance_projection_trace_N2_401_2026-06-25.md",
    ]

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_closure_ledger_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Closure Ledger Audit" in markdown_result.stdout
    assert "Stages ready: 13/13" in markdown_result.stdout
    assert "release_trace_partition_guard" in markdown_result.stdout
    assert "boundary_subject_release_continuity" in markdown_result.stdout
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


def test_release_gate_includes_release_closure_ledger(tmp_path, capsys):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_closure_ledger_audit"]["status"] == (
        "passed"
    )
    assert payload["checks"][
        "scene_release_governance_export_script_evidence"
    ]["status"] == "passed"
    assert payload["counts"]["scene_release_closure_ledger_stage_count"] == 13
    assert payload["counts"]["scene_release_closure_ledger_ready_count"] == 13
    assert payload["counts"]["scene_release_closure_ledger_stage_order_count"] == 13
    assert (
        payload["counts"]["scene_release_closure_ledger_upstream_dependency_count"]
        == 18
    )
    assert (
        payload["counts"][
            "scene_release_closure_ledger_upstream_dependency_ready_count"
        ]
        == 18
    )
    assert (
        payload["counts"]["scene_release_closure_ledger_release_gate_check_count"]
        == 13
    )
    assert payload["counts"]["scene_release_closure_ledger_dashboard_card_count"] == 13
    assert payload["counts"]["scene_release_closure_ledger_drilldown_item_count"] == 13
    assert (
        payload["counts"]["scene_release_closure_ledger_summary_projection_count"]
        == 13
    )
    assert payload["counts"]["scene_release_closure_ledger_issue_count"] == 0
    assert (
        payload["counts"]["scene_release_governance_export_script_report_count"]
        == 15
    )
    assert (
        payload["counts"]["scene_release_governance_export_script_ready_count"]
        == 15
    )
    assert (
        payload["counts"]["scene_release_governance_export_script_missing_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_release_governance_export_script_unready_count"]
        == 0
    )
    export_rows = {
        row["report_id"]: row
        for row in payload["scene_release_governance_export_script_evidence"]
    }
    assert len(export_rows) == 15
    assert export_rows["scene_release_closure_ledger_audit"][
        "payload_source_id"
    ] == "scene_release_closure_ledger_audit"
    assert all(
        row["export_script_status"] == "ready" for row in export_rows.values()
    )

    _print_human(payload)
    output = capsys.readouterr().out
    assert "release_export_scripts=15/15 ready" in output
