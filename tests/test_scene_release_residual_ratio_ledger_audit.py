import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_boundary_maturity_release_envelope_audit import (  # noqa: E402
    build_scene_boundary_maturity_release_envelope_audit_report,
)
from src.config.scene_release_residual_ratio_ledger_audit import (  # noqa: E402
    audit_scene_release_residual_ratio_ledger_report,
    build_scene_release_residual_ratio_ledger_audit_report,
)
from src.config.scene_retained_gap_exit_criteria_audit import (  # noqa: E402
    build_scene_retained_gap_exit_criteria_audit_report,
)


def test_release_residual_ratio_ledger_publishes_non_full_gate_ratios():
    report = build_scene_release_residual_ratio_ledger_audit_report(
        project_root=ROOT
    )
    payload = report.to_payload()
    rows = {row.ratio_id: row for row in report.rows}

    assert report.status == "passed"
    assert audit_scene_release_residual_ratio_ledger_report(report) == ()
    assert payload["counts"]["ratio_count"] == 3
    assert payload["counts"]["published_ratio_count"] == 3
    assert payload["counts"]["non_full_ratio_count"] == 3
    assert payload["counts"]["readiness_reconciliation_link_count"] == 11
    assert payload["counts"]["terminal_exception_link_count"] == 3
    assert payload["counts"]["release_envelope_link_count"] == 10
    assert payload["counts"]["retained_gap_exit_criteria_link_count"] == 10
    assert payload["counts"]["retained_gap_receipt_alignment_link_count"] == 10
    assert payload["counts"]["count_delivery_boundary_alignment_count"] == 4
    assert payload["counts"]["count_delivery_boundary_link_count"] == 4
    assert payload["counts"]["count_delivery_receipt_alignment_count"] == 4
    assert payload["counts"]["count_delivery_receipt_alignment_link_count"] == 4
    assert payload["counts"]["maturity_l5_blocker_alignment_count"] == 6
    assert payload["counts"]["maturity_l5_blocker_release_envelope_count"] == 6
    assert payload["counts"]["maturity_l5_blocker_receipt_alignment_count"] == 6
    assert payload["counts"]["maturity_l5_blocker_receipt_alignment_link_count"] == 6
    assert payload["counts"]["boundary_scope_alignment_count"] == 6
    assert payload["counts"]["boundary_scope_link_count"] == 6
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0

    assert rows["count_profiles"].observed_ratio == "14/15"
    assert rows["count_profiles"].residual_mode == (
        "boundary_or_not_applicable_count_surface"
    )
    assert len(rows["count_profiles"].readiness_reconciliation_row_ids) == 3
    assert len(rows["count_profiles"].release_envelope_ids) == 2
    assert len(rows["count_profiles"].retained_gap_exit_criteria_ids) == 2
    assert len(rows["count_profiles"].retained_gap_receipt_alignment_ids) == 2
    assert rows["delivery_families"].observed_ratio == "14/15"
    assert len(rows["delivery_families"].readiness_reconciliation_row_ids) == 2
    assert len(rows["delivery_families"].release_envelope_ids) == 2
    assert len(rows["delivery_families"].retained_gap_exit_criteria_ids) == 2
    assert len(rows["delivery_families"].retained_gap_receipt_alignment_ids) == 2
    assert rows["maturity_l5_blocked"].observed_ratio == "6/27"
    assert len(rows["maturity_l5_blocked"].release_envelope_ids) == 6
    assert len(rows["maturity_l5_blocked"].retained_gap_exit_criteria_ids) == 6
    assert len(rows["maturity_l5_blocked"].retained_gap_receipt_alignment_ids) == 6
    source_status = {
        item["source_id"]: item["status"] for item in payload["source_evidence"]
    }
    assert source_status["export_script"] == "ready"
    assert source_status["n2_393b_maturity_blocker_envelope_plan"] == "ready"
    assert source_status["n2_393k_exit_criteria_links_plan"] == "ready"
    assert source_status["n2_398_receipt_alignment_plan"] == "ready"
    assert source_status["n2_405_count_delivery_receipt_plan"] == "ready"
    assert source_status["n2_406_maturity_l5_receipt_plan"] == "ready"


def test_count_and_delivery_residual_ratios_share_boundary_exit_criteria():
    report = build_scene_release_residual_ratio_ledger_audit_report(
        project_root=ROOT
    )
    rows = {row.ratio_id: row for row in report.rows}
    count_profiles = rows["count_profiles"]
    delivery_families = rows["delivery_families"]
    shared_exit_criteria = {
        "family:ip_patent_documents:IP plugin handoff",
        "pack:import_ai_boundary:real OCR/PDF/LaTeX plugin integration",
    }

    assert count_profiles.observed_ratio == "14/15"
    assert delivery_families.observed_ratio == "14/15"
    assert report.count_delivery_boundary_alignment_count == 4
    assert report.count_delivery_boundary_link_count == 4
    assert report.count_delivery_receipt_alignment_count == 4
    assert report.count_delivery_receipt_alignment_link_count == 4
    assert report.retained_gap_receipt_alignment_link_count == 10
    assert set(count_profiles.release_envelope_ids) == shared_exit_criteria
    assert set(delivery_families.release_envelope_ids) == shared_exit_criteria
    assert (
        set(count_profiles.retained_gap_exit_criteria_ids)
        == shared_exit_criteria
    )
    assert (
        set(count_profiles.retained_gap_receipt_alignment_ids)
        == shared_exit_criteria
    )
    assert (
        set(delivery_families.retained_gap_exit_criteria_ids)
        == shared_exit_criteria
    )
    assert (
        set(delivery_families.retained_gap_receipt_alignment_ids)
        == shared_exit_criteria
    )
    assert (
        "scene_count_profile_audit:family_readiness_delta:family:ip_patent_documents"
        in count_profiles.readiness_reconciliation_row_ids
    )
    assert (
        "scene_delivery_preset_audit:family_readiness_delta:family:ip_patent_documents"
        in delivery_families.readiness_reconciliation_row_ids
    )


def test_maturity_l5_blockers_match_release_envelopes_and_exit_criteria():
    residual_report = build_scene_release_residual_ratio_ledger_audit_report(
        project_root=ROOT
    )
    envelope_report = build_scene_boundary_maturity_release_envelope_audit_report(
        project_root=ROOT
    )
    exit_criteria_report = build_scene_retained_gap_exit_criteria_audit_report(
        project_root=ROOT,
        boundary_maturity_release_envelope_report=envelope_report,
    )
    rows = {row.ratio_id: row for row in residual_report.rows}
    maturity_l5_blocked = rows["maturity_l5_blocked"]
    envelope_ids = {row.envelope_id for row in envelope_report.rows}
    exit_criteria_ids = {row.criteria_id for row in exit_criteria_report.rows}

    assert maturity_l5_blocked.observed_ratio == "6/27"
    assert residual_report.maturity_l5_blocker_alignment_count == 6
    assert residual_report.maturity_l5_blocker_receipt_alignment_count == 6
    assert residual_report.maturity_l5_blocker_receipt_alignment_link_count == 6
    assert residual_report.boundary_scope_alignment_count == 6
    assert residual_report.boundary_scope_link_count == 6
    assert residual_report.retained_gap_receipt_alignment_link_count == 10
    assert set(maturity_l5_blocked.release_envelope_ids) == envelope_ids
    assert set(maturity_l5_blocked.retained_gap_exit_criteria_ids) == envelope_ids
    assert set(maturity_l5_blocked.retained_gap_receipt_alignment_ids) == envelope_ids
    assert exit_criteria_ids == envelope_ids
    assert all(row.status == "release_envelope_ready" for row in envelope_report.rows)
    assert all(
        row.status == "release_allowed_with_exit_criteria"
        for row in exit_criteria_report.rows
    )


def test_release_residual_ratio_ledger_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_residual_ratio_ledger_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["ratio_count"] == 3
    assert payload["counts"]["published_ratio_count"] == 3
    assert payload["counts"]["count_delivery_boundary_alignment_count"] == 4
    assert payload["counts"]["count_delivery_boundary_link_count"] == 4
    assert payload["counts"]["count_delivery_receipt_alignment_count"] == 4
    assert payload["counts"]["count_delivery_receipt_alignment_link_count"] == 4
    assert payload["counts"]["retained_gap_receipt_alignment_link_count"] == 10
    assert payload["counts"]["maturity_l5_blocker_alignment_count"] == 6
    assert payload["counts"]["maturity_l5_blocker_release_envelope_count"] == 6
    assert payload["counts"]["maturity_l5_blocker_receipt_alignment_count"] == 6
    assert payload["counts"]["maturity_l5_blocker_receipt_alignment_link_count"] == 6
    assert payload["counts"]["boundary_scope_alignment_count"] == 6
    assert payload["counts"]["boundary_scope_link_count"] == 6
    rows = {row["ratio_id"]: row for row in payload["rows"]}
    assert rows["count_profiles"]["observed_ratio"] == "14/15"
    assert rows["count_profiles"]["residual_mode"] == (
        "boundary_or_not_applicable_count_surface"
    )
    assert (
        "family:ip_patent_documents:IP plugin handoff"
        in rows["count_profiles"]["release_envelope_ids"]
    )
    assert (
        "family:ip_patent_documents:IP plugin handoff"
        in rows["count_profiles"]["retained_gap_receipt_alignment_ids"]
    )
    assert rows["delivery_families"]["observed_ratio"] == "14/15"
    assert rows["delivery_families"]["residual_mode"] == (
        "boundary_delivery_surface"
    )
    assert (
        "family:ip_patent_documents:IP plugin handoff"
        in rows["delivery_families"]["retained_gap_exit_criteria_ids"]
    )
    assert rows["maturity_l5_blocked"]["observed_ratio"] == "6/27"
    assert rows["maturity_l5_blocked"]["residual_mode"] == (
        "boundary_maturity_retained"
    )
    assert (
        "family:regulated_disclosure_documents:external assurance review handoff"
        in rows["maturity_l5_blocked"]["release_envelope_ids"]
    )

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_residual_ratio_ledger_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Residual Ratio Ledger Audit" in markdown_result.stdout
    assert "Residual ratios published: 3/3" in markdown_result.stdout
    assert "Retained-gap exit criteria links: 10" in markdown_result.stdout
    assert "Receipt alignments: 10/10" in markdown_result.stdout
    assert "Count/delivery boundary alignments: 4/4" in markdown_result.stdout
    assert "Maturity L5 blocker alignments: 6" in markdown_result.stdout
    assert "Boundary scope alignments: 6/6" in markdown_result.stdout
    assert "count_profiles" in markdown_result.stdout
    assert "delivery_families" in markdown_result.stdout
    assert "Count/delivery receipt alignments: 4/4" in markdown_result.stdout
    assert "maturity_l5_blocked" in markdown_result.stdout
    assert "Maturity L5 receipt alignments: 6/6" in markdown_result.stdout


def test_release_gate_includes_release_residual_ratio_ledger(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_residual_ratio_ledger_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_release_residual_ratio_ledger_count"] == 3
    assert (
        payload["counts"]["scene_release_residual_ratio_ledger_published_count"]
        == 3
    )
    assert payload["counts"]["scene_release_residual_ratio_ledger_non_full_count"] == 3
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_readiness_reconciliation_link_count"
        ]
        == 11
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_release_envelope_link_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_exit_criteria_link_count"
        ]
        == 10
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
            "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_count"
        ]
        == 4
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count"
        ]
        == 4
    )
    assert payload["counts"]["scene_release_residual_ratio_ledger_issue_count"] == 0
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
        payload["scene_release_residual_ratio_ledger_audit"]["counts"][
            "maturity_l5_blocker_alignment_count"
        ]
        == 6
    )
    assert (
        payload["scene_release_residual_ratio_ledger_audit"]["counts"][
            "maturity_l5_blocker_receipt_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count"
        ]
        == 6
    )
    assert (
        payload["counts"][
            "scene_release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count"
        ]
        == 6
    )
