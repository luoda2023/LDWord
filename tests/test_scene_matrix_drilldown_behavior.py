import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_matrix_drilldown import (  # noqa: E402
    build_scene_matrix_drilldown_report,
)
from src.ui.panels.scene_summary_projection import (  # noqa: E402
    build_scene_matrix_drilldown_summary_items,
)


def test_scene_matrix_drilldown_filters_for_pack_family_source_and_query():
    family_report = build_scene_matrix_drilldown_report(
        family_id="hr_batch_documents",
        project_root=ROOT,
    )
    source_report = build_scene_matrix_drilldown_report(
        source_id="scene_word_risk_closure_audit",
        query="fixed_row_height",
        project_root=ROOT,
    )
    external_report = build_scene_matrix_drilldown_report(
        source_id="scene_external_handoff_contract_audit",
        query="external_receipt_id",
        project_root=ROOT,
    )
    guarded_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_guarded_completion_audit",
        query="boundary_guarded_complete",
        project_root=ROOT,
    )
    residual_report = build_scene_matrix_drilldown_report(
        source_id="scene_residual_warning_governance_audit",
        query="registry_only_profile",
        project_root=ROOT,
    )
    reconciliation_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_readiness_reconciliation_audit",
        query="not_applicable_count_surface",
        project_root=ROOT,
    )
    terminal_report = build_scene_matrix_drilldown_report(
        source_id="scene_terminal_release_exception_audit",
        query="managed_residual_warnings",
        project_root=ROOT,
    )
    dossier_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_subject_release_dossier_audit",
        query="ip_patent_documents",
        project_root=ROOT,
    )
    non_subject_report = build_scene_matrix_drilldown_report(
        source_id="scene_non_subject_release_trace_attribution_audit",
        query="generic_not_applicable_surface",
        project_root=ROOT,
    )
    partition_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_trace_partition_guard_audit",
        query="terminal_release_trace_total",
        project_root=ROOT,
    )
    projection_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_projection_surface_parity_audit",
        query="release_trace_partition_guard",
        project_root=ROOT,
    )
    continuity_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_subject_release_continuity_audit",
        query="ip_patent_documents",
        project_root=ROOT,
    )
    release_ledger_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_closure_ledger_audit",
        query="release_projection_surface_parity",
        project_root=ROOT,
    )
    release_envelope_report = build_scene_matrix_drilldown_report(
        source_id="scene_boundary_maturity_release_envelope_audit",
        query="ip_patent_documents",
        project_root=ROOT,
    )
    release_ratio_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_residual_ratio_ledger_audit",
        query="maturity_l5_blocked",
        project_root=ROOT,
    )
    release_acceptance_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_acceptance_certificate_audit",
        query="release_projection_surface_parity",
        project_root=ROOT,
    )
    acceptance_receipt_report = build_scene_matrix_drilldown_report(
        source_id="scene_release_acceptance_certificate_audit",
        query="acceptance_receipt_trace",
        project_root=ROOT,
    )
    batch_report = build_scene_matrix_drilldown_report(
        pack_id="batch_forms",
        project_root=ROOT,
    )

    family_items = {item.drilldown_id: item for item in family_report.items}
    source_items = {item.drilldown_id: item for item in source_report.items}
    external_items = {item.drilldown_id: item for item in external_report.items}
    guarded_items = {item.drilldown_id: item for item in guarded_report.items}
    residual_items = {item.drilldown_id: item for item in residual_report.items}
    reconciliation_items = {
        item.drilldown_id: item for item in reconciliation_report.items
    }
    terminal_items = {item.drilldown_id: item for item in terminal_report.items}
    dossier_items = {item.drilldown_id: item for item in dossier_report.items}
    non_subject_items = {
        item.drilldown_id: item for item in non_subject_report.items
    }
    partition_items = {
        item.drilldown_id: item for item in partition_report.items
    }
    projection_items = {
        item.drilldown_id: item for item in projection_report.items
    }
    continuity_items = {
        item.drilldown_id: item for item in continuity_report.items
    }
    release_ledger_items = {
        item.drilldown_id: item for item in release_ledger_report.items
    }
    release_envelope_items = {
        item.drilldown_id: item for item in release_envelope_report.items
    }
    release_ratio_items = {
        item.drilldown_id: item for item in release_ratio_report.items
    }
    release_acceptance_items = {
        item.drilldown_id: item for item in release_acceptance_report.items
    }
    acceptance_receipt_items = {
        item.drilldown_id: item for item in acceptance_receipt_report.items
    }
    batch_items = {item.drilldown_id: item for item in batch_report.items}

    assert family_report.status == "passed"
    assert family_items["matrix_dashboard"].visible_count == 1
    assert family_items["request_cells"].visible_count == 2
    assert family_items["ambiguity_clarification"].visible_count == 1
    assert family_items["user_journey_fixture"].visible_count == 5
    assert family_items["business_capability_matrix"].visible_count == 1
    assert family_items["boundary_guarded_completion"].visible_count == 0
    assert family_items["residual_warning_governance"].visible_count == 0
    assert family_items["boundary_readiness_reconciliation"].visible_count == 0
    assert family_items["terminal_release_exception"].visible_count == 0
    assert family_items["boundary_subject_release_dossier"].visible_count == 0
    assert family_items["non_subject_release_trace_attribution"].visible_count == 0
    assert family_items["release_trace_partition_guard"].visible_count == 0
    assert family_items["release_projection_surface_parity"].visible_count == 0
    assert family_items["boundary_subject_release_continuity"].visible_count == 0
    assert family_items["release_closure_ledger"].visible_count == 0
    assert family_items["boundary_maturity_release_envelope"].visible_count == 0
    assert family_items["release_residual_ratio_ledger"].visible_count == 0
    assert family_items["release_acceptance_certificate"].visible_count == 0
    assert family_items["control_runtime_consistency"].visible_count == 0
    assert family_items["input_source"].visible_count == 1
    assert family_items["object_preflight_action"].visible_count == 1
    assert family_items["family_fixture_depth"].visible_count == 1
    assert family_items["count_profile"].visible_count == 1
    assert family_items["material_schema"].visible_count == 1
    assert family_items["material_repair_flow"].visible_count == 11
    assert family_items["fixed_layout_profile"].visible_count == 3
    assert family_items["report_artifact_drilldown"].visible_count == 10
    assert family_items["delivery_preset"].visible_count == 1
    assert family_items["delivery_execution"].visible_count == 7
    assert family_items["formula_output_watermark"].visible_count == 2
    assert family_items["maturity_upgrade"].visible_count == 2
    assert family_items["family_fixture_depth"].visible_rows[0].row_id == (
        "hr_batch_documents"
    )

    assert [item.drilldown_id for item in source_report.items] == ["word_risk"]
    assert source_items["word_risk"].visible_count == 1
    assert source_items["word_risk"].visible_rows[0].row_id == "fixed_row_height"
    assert [item.drilldown_id for item in external_report.items] == [
        "external_handoff_contract"
    ]
    assert external_items["external_handoff_contract"].visible_count == 6
    assert [item.drilldown_id for item in guarded_report.items] == [
        "boundary_guarded_completion"
    ]
    assert guarded_items["boundary_guarded_completion"].visible_count == 6
    assert [item.drilldown_id for item in residual_report.items] == [
        "residual_warning_governance"
    ]
    assert residual_items["residual_warning_governance"].visible_count == 2
    assert [item.drilldown_id for item in reconciliation_report.items] == [
        "boundary_readiness_reconciliation"
    ]
    assert (
        reconciliation_items["boundary_readiness_reconciliation"].visible_count
        == 2
    )
    assert [item.drilldown_id for item in terminal_report.items] == [
        "terminal_release_exception"
    ]
    assert terminal_items["terminal_release_exception"].visible_count == 1
    assert [item.drilldown_id for item in dossier_report.items] == [
        "boundary_subject_release_dossier"
    ]
    assert dossier_items["boundary_subject_release_dossier"].visible_count == 1
    assert [item.drilldown_id for item in non_subject_report.items] == [
        "non_subject_release_trace_attribution"
    ]
    assert (
        non_subject_items["non_subject_release_trace_attribution"].visible_count
        == 1
    )
    assert [item.drilldown_id for item in partition_report.items] == [
        "release_trace_partition_guard"
    ]
    assert partition_items["release_trace_partition_guard"].visible_count == 1
    assert [item.drilldown_id for item in projection_report.items] == [
        "release_projection_surface_parity"
    ]
    assert projection_items["release_projection_surface_parity"].visible_count == 1
    assert [item.drilldown_id for item in continuity_report.items] == [
        "boundary_subject_release_continuity"
    ]
    assert continuity_items["boundary_subject_release_continuity"].visible_count == 1
    assert [item.drilldown_id for item in release_ledger_report.items] == [
        "release_closure_ledger"
    ]
    assert release_ledger_items["release_closure_ledger"].visible_count == 4
    assert [item.drilldown_id for item in release_envelope_report.items] == [
        "boundary_maturity_release_envelope"
    ]
    assert (
        release_envelope_items[
            "boundary_maturity_release_envelope"
        ].visible_count
        == 1
    )
    assert [item.drilldown_id for item in release_ratio_report.items] == [
        "release_residual_ratio_ledger"
    ]
    assert release_ratio_items["release_residual_ratio_ledger"].visible_count == 1
    assert [item.drilldown_id for item in release_acceptance_report.items] == [
        "release_acceptance_certificate"
    ]
    assert (
        release_acceptance_items["release_acceptance_certificate"].visible_count
        == 2
    )
    assert {
        row.row_id
        for row in release_acceptance_items[
            "release_acceptance_certificate"
        ].visible_rows
    } == {
        "release_projection_surface_parity",
        "requirement:projection_export_visibility",
    }
    assert [item.drilldown_id for item in acceptance_receipt_report.items] == [
        "release_acceptance_certificate"
    ]
    assert (
        acceptance_receipt_items["release_acceptance_certificate"].visible_count
        == 2
    )
    assert {
        row.row_id
        for row in acceptance_receipt_items[
            "release_acceptance_certificate"
        ].visible_rows
    } == {
        "release_residual_ratio_receipts",
        "retained_gap_external_receipts",
    }

    assert batch_items["matrix_dashboard"].visible_count == 1
    assert batch_items["request_cells"].visible_count == 7
    assert batch_items["ambiguity_clarification"].visible_count == 3
    assert batch_items["user_journey_fixture"].visible_count == 16
    assert batch_items["business_capability_matrix"].visible_count == 2
    assert batch_items["boundary_guarded_completion"].visible_count == 0
    assert batch_items["residual_warning_governance"].visible_count == 0
    assert batch_items["boundary_readiness_reconciliation"].visible_count == 0
    assert batch_items["terminal_release_exception"].visible_count == 0
    assert batch_items["boundary_subject_release_dossier"].visible_count == 0
    assert batch_items["non_subject_release_trace_attribution"].visible_count == 0
    assert batch_items["release_trace_partition_guard"].visible_count == 0
    assert batch_items["release_projection_surface_parity"].visible_count == 0
    assert batch_items["boundary_subject_release_continuity"].visible_count == 0
    assert batch_items["release_closure_ledger"].visible_count == 0
    assert batch_items["boundary_maturity_release_envelope"].visible_count == 0
    assert batch_items["release_residual_ratio_ledger"].visible_count == 0
    assert batch_items["release_acceptance_certificate"].visible_count == 0
    assert batch_items["control_runtime_consistency"].visible_count == 0
    assert batch_items["input_source"].visible_count == 2
    assert batch_items["object_preflight_action"].visible_count == 5
    assert batch_items["family_fixture_depth"].visible_count == 2
    assert batch_items["count_profile"].visible_count == 2
    assert batch_items["material_schema"].visible_count == 2
    assert batch_items["material_repair_flow"].visible_count == 11
    assert batch_items["fixed_layout_profile"].visible_count == 11
    assert batch_items["report_artifact_drilldown"].visible_count == 10
    assert batch_items["delivery_preset"].visible_count == 2
    assert batch_items["delivery_execution"].visible_count == 7
    assert batch_items["formula_output_watermark"].visible_count == 3
    assert batch_items["maturity_upgrade"].visible_count == 3


def test_scene_matrix_drilldown_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_matrix_drilldown.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "json",
            "--family",
            "hr_batch_documents",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["item_count"] == 37
    assert payload["counts"]["visible_row_count"] == 51
    assert payload["counts"]["source_evidence_count"] == 107
    assert payload["counts"]["ready_source_evidence_count"] == 107
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert len(payload["source_evidence"]) == payload["counts"]["source_evidence_count"]
    payload_source_ids = [item["source_id"] for item in payload["source_evidence"]]
    assert len(payload_source_ids) == len(set(payload_source_ids))
    assert (
        sum(1 for item in payload["source_evidence"] if item["status"] == "ready")
        == payload["counts"]["ready_source_evidence_count"]
    )
    assert (
        sum(1 for item in payload["source_evidence"] if item["status"] != "ready")
        == payload["counts"]["missing_source_evidence_count"]
    )
    assert {
        item["source_id"]: item["status"] for item in payload["source_evidence"]
    }["scene_matrix_drilldown_export_json_source_summary_projection"] == "ready"
    assert payload["items"][0]["drilldown_id"] == "matrix_dashboard"

    receipt_output_path = tmp_path / "scene_matrix_residual_receipts.json"
    receipt_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "json",
            "--source",
            "scene_release_residual_ratio_ledger_audit",
            "--output",
            str(receipt_output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    receipt_payload = json.loads(receipt_output_path.read_text(encoding="utf-8"))
    receipt_item = receipt_payload["items"][0]
    receipt_rows = {row["row_id"]: row for row in receipt_item["rows"]}

    assert receipt_result.stdout == ""
    assert receipt_payload["status"] == "passed"
    assert receipt_payload["counts"]["item_count"] == 1
    assert "count_delivery_receipts=4/4" in receipt_item["detail"]
    assert "maturity_l5_receipts=6/6" in receipt_item["detail"]
    assert "receipt_alignments=2/2" in receipt_rows["count_profiles"]["detail"]
    assert "count_delivery_receipts=2/2" in receipt_rows["count_profiles"]["detail"]
    assert "receipt_alignments=2/2" in receipt_rows["delivery_families"]["detail"]
    assert (
        "count_delivery_receipts=2/2"
        in receipt_rows["delivery_families"]["action_behavior_ids"]
    )
    assert "receipt_alignments=6/6" in receipt_rows["maturity_l5_blocked"]["detail"]
    assert (
        "maturity_l5_receipts=6/6"
        in receipt_rows["maturity_l5_blocked"]["action_behavior_ids"]
    )


def test_scene_matrix_drilldown_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "markdown",
            "--source",
            "scene_plugin_boundary_confirmation_audit",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Matrix Drilldown" in result.stdout
    assert "- Source evidence: 107 / 107 ready (0 missing)" in result.stdout
    assert "| Drilldown | Source | Status | Rows | Visible | Lenses | Route |" in (
        result.stdout
    )
    assert "plugin_boundary" in result.stdout
    assert "exam_ai_complex_diagram_gate" in result.stdout
    assert "scene_plugin_boundary_confirmation_audit" in result.stdout

    receipt_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "markdown",
            "--source",
            "scene_release_acceptance_certificate_audit",
            "--query",
            "acceptance_receipt_trace",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "release_residual_ratio_receipts" in receipt_result.stdout
    assert "retained_gap_external_receipts" in receipt_result.stdout

    residual_receipt_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_matrix_drilldown.py",
            "--format",
            "markdown",
            "--source",
            "scene_release_residual_ratio_ledger_audit",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "count_delivery_receipts=4/4" in residual_receipt_result.stdout
    assert "maturity_l5_receipts=6/6" in residual_receipt_result.stdout
    assert "receipt_alignments=2/2" in residual_receipt_result.stdout
    assert "count_delivery_receipts=2/2" in residual_receipt_result.stdout
    assert "receipt_alignments=6/6" in residual_receipt_result.stdout


def test_release_gate_includes_scene_matrix_drilldown(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_matrix_drilldown"]["status"] == "passed"
    assert payload["counts"]["scene_matrix_drilldown_item_count"] == 37
    assert payload["counts"]["scene_matrix_drilldown_ready_count"] == 37
    assert payload["counts"]["scene_matrix_drilldown_row_count"] == 556
    assert payload["counts"]["scene_matrix_drilldown_visible_row_count"] == 556
    assert payload["counts"]["scene_matrix_drilldown_issue_count"] == 0
    assert payload["counts"]["scene_matrix_drilldown_source_evidence_count"] == 107
    assert (
        payload["counts"]["scene_matrix_drilldown_ready_source_evidence_count"]
        == 107
    )
    assert (
        payload["counts"]["scene_matrix_drilldown_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_matrix_drilldown"]["status"] == "passed"
    assert payload["scene_matrix_drilldown"]["counts"]["item_count"] == 37


def test_scene_summary_projection_exposes_matrix_drilldown_items():
    items = {
        item.key: item for item in build_scene_matrix_drilldown_summary_items()
    }

    assert items["scene_matrix_drilldown"].value == "37/37 ready"
    assert "556 visible rows" in items["scene_matrix_drilldown"].detail
    assert "request-cell" in items["scene_matrix_drilldown"].detail
    assert "Ambiguity clarification" in items["scene_matrix_drilldown"].detail
    assert "User journey fixtures" in items["scene_matrix_drilldown"].detail
    assert "Business capability matrix" in items["scene_matrix_drilldown"].detail
    assert "external handoff contracts" in items["scene_matrix_drilldown"].detail
    assert "Boundary guarded completion" in items["scene_matrix_drilldown"].detail
    assert "Residual warning governance" in items["scene_matrix_drilldown"].detail
    assert "Boundary readiness reconciliation" in items["scene_matrix_drilldown"].detail
    assert "Terminal release exceptions" in items["scene_matrix_drilldown"].detail
    assert "Boundary subject release dossiers" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Non-subject release trace attribution" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release trace partition guard" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release projection parity" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Boundary subject release continuity" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release closure ledger" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Boundary maturity release envelope" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Retained gap exit criteria" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release residual ratio ledger" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release residual explanations" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "Release acceptance certificate" in (
        items["scene_matrix_drilldown"].detail
    )
    assert "InputSourceProfile" in items["scene_matrix_drilldown"].detail
    assert "ObjectPreflight actions" in items["scene_matrix_drilldown"].detail
    assert "CountProfile" in items["scene_matrix_drilldown"].detail
    assert "MaterialSchema" in items["scene_matrix_drilldown"].detail
    assert "Material repair flow" in items["scene_matrix_drilldown"].detail
    assert "Fixed-layout profile" in items["scene_matrix_drilldown"].detail
    assert "Report/artifact drilldown" in items["scene_matrix_drilldown"].detail
    assert "DeliveryPreset" in items["scene_matrix_drilldown"].detail
    assert "Delivery execution" in items["scene_matrix_drilldown"].detail
    assert "Formula/output/watermark" in items["scene_matrix_drilldown"].detail
    assert "Control runtime consistency" in items["scene_matrix_drilldown"].detail
    assert "Maturity upgrade" in items["scene_matrix_drilldown"].detail
    assert items["scene_matrix_drilldown_sources"].label == "Static source markers"
    assert items["scene_matrix_drilldown_sources"].value == "107/107 present"
    assert items["scene_matrix_drilldown_sources"].variant == "info"
    assert "0 missing" in items["scene_matrix_drilldown_sources"].detail
    assert "not runtime verification" in items["scene_matrix_drilldown_sources"].detail
    assert "scene_ambiguity_clarification_ui_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_user_journey_fixture_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_business_capability_matrix_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_external_handoff_contract_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_guarded_completion_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_residual_warning_governance_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_readiness_reconciliation_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_terminal_release_exception_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_subject_release_dossier_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_non_subject_release_trace_attribution_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_trace_partition_guard_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_projection_surface_parity_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_subject_release_continuity_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_closure_ledger_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_boundary_maturity_release_envelope_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_retained_gap_exit_criteria_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_residual_ratio_ledger_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_residual_explanation_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_release_acceptance_certificate_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_material_repair_flow_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_fixed_layout_profile_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_report_artifact_drilldown_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_control_runtime_consistency_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_word_risk_closure_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_residual_receipt_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_export_receipt_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_export_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_export_json_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_evidence_payload_consistency_tests" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_evidence_unique_id_tests" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_source_summary_readiness_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_test_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_source_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_surface_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_path_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_evidence_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_release_marker_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_projection_release_link_reference_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_retained_gap_exit_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_control_runtime_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_release_metric_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_external_handoff_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_report_delivery_marker_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_requirement_dimension_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_target_plugin_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert (
        "scene_matrix_drilldown_projection_formula_output_watermark_reference_audit"
        in items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_407_residual_receipt_drilldown_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_408_residual_receipt_export_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_409_residual_receipt_source_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_release_gate_source_summary_projection" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_item_row_identity_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_item_source_evidence_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_source_evidence_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_pack_family_registry_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_request_fixture_registry_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "scene_matrix_drilldown_row_count_delivery_registry_audit" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_410_drilldown_source_evidence_release_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_411_drilldown_source_summary_ready_total_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_412_drilldown_export_source_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_413_drilldown_json_export_source_summary_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_414_drilldown_source_evidence_payload_consistency_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_415_drilldown_source_evidence_unique_id_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_416_drilldown_item_row_unique_id_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_417_drilldown_item_source_evidence_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_418_drilldown_row_source_evidence_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_419_drilldown_row_pack_family_registry_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_420_drilldown_row_request_fixture_registry_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_421_drilldown_row_count_delivery_registry_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_437_drilldown_projection_report_delivery_marker_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_438_drilldown_projection_requirement_dimension_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_439_drilldown_projection_target_plugin_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
    assert "n2_440_drilldown_projection_formula_output_watermark_trace_plan" in (
        items["scene_matrix_drilldown_sources"].detail
    )
