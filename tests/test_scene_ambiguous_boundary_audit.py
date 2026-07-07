import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_ambiguous_boundary_audit import (  # noqa: E402
    N2_162_REQUIRED_BOUNDARY_IDS,
    audit_scene_ambiguous_boundary_report,
    build_scene_ambiguous_boundary_audit_report,
)
from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)


def test_scene_ambiguous_boundary_audit_locks_n2_162_pack_pairs():
    report = build_scene_ambiguous_boundary_audit_report(project_root=ROOT)

    assert report.status == "passed"
    assert report.boundary_count == 6
    assert report.pack_pair_count == 6
    assert report.ready_boundary_count == 6
    assert report.ambiguous_sample_count == 6
    assert report.fixture_backed_count == 6
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert tuple(N2_162_REQUIRED_BOUNDARY_IDS) == (
        "product_manual_application_vs_technical",
        "quote_plan_application_vs_finance",
        "certificate_materials_bidding_vs_fixed_form",
        "bilingual_document_formatting_vs_review",
        "project_application_form_application_vs_fixed_form",
        "batch_notice_official_vs_hr",
    )
    assert audit_scene_ambiguous_boundary_report(report) == ()


def test_scene_ambiguous_boundary_rows_prove_router_and_fixture_evidence():
    report = build_scene_ambiguous_boundary_audit_report(project_root=ROOT)
    rows = {row.boundary_id: row for row in report.rows}

    project = rows["project_application_form_application_vs_fixed_form"]
    assert project.sample_id == "project_application_form"
    assert project.route_status == "ambiguous"
    assert set(project.expected_pack_ids) == {"application_reports", "batch_forms"}
    assert set(project.expected_route_ids) == {
        "project_application_package",
        "fixed_form_batch_documents",
    }
    assert project.coverage_level == "ambiguous_fixture_set"
    assert project.fixture_ids
    assert "固定版式表单" in project.disambiguation_prompt

    notice = rows["batch_notice_official_vs_hr"]
    assert notice.sample_id == "ambiguous_batch_notice"
    assert notice.route_status == "ambiguous"
    assert set(notice.expected_pack_ids) == {"official_policy", "batch_forms"}
    assert {"hr_batch_documents", "official_policy_documents"}.issubset(
        notice.candidate_route_ids
    )
    assert notice.coverage_level == "ambiguous_fixture_set"
    assert notice.fixture_ids


def test_scene_ambiguous_boundary_export_script_writes_json(tmp_path):
    output_path = tmp_path / "ambiguous_boundary.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_ambiguous_boundary_audit.py",
            "--format",
            "json",
            "--pack",
            "official_policy",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["counts"]["boundary_count"] == 1
    assert payload["rows"][0]["boundary_id"] == "batch_notice_official_vs_hr"


def test_scene_ambiguous_boundary_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_ambiguous_boundary_audit.py",
            "--format",
            "markdown",
            "--boundary",
            "project_application_form_application_vs_fixed_form",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Ambiguous Boundary Audit" in result.stdout
    assert "project_application_form_application_vs_fixed_form" in result.stdout
    assert "项目申请表" in result.stdout


def test_release_gate_includes_scene_ambiguous_boundary_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path / "samples")

    assert payload["checks"]["scene_ambiguous_boundary_audit"]["status"] == "passed"
    assert payload["counts"]["scene_ambiguous_boundary_count"] == 6
    assert payload["counts"]["scene_ambiguous_boundary_pack_pair_count"] == 6
    assert payload["counts"]["scene_ambiguous_boundary_fixture_backed_count"] == 6
    assert payload["counts"]["scene_ambiguous_boundary_issue_count"] == 0
    assert payload["scene_ambiguous_boundary_audit"]["status"] == "passed"
