import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_ambiguity_clarification_ui_audit import (  # noqa: E402
    SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS,
    SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES,
    audit_scene_ambiguity_clarification_ui_report,
    build_scene_ambiguity_clarification_ui_audit_report,
)


def test_scene_ambiguity_clarification_ui_audit_baseline_counts():
    report = build_scene_ambiguity_clarification_ui_audit_report(project_root=ROOT)
    issues, warnings = audit_scene_ambiguity_clarification_ui_report(report)

    assert report.status == "passed"
    assert issues == ()
    assert warnings == ()
    assert report.clarification_count == 6
    assert report.ready_clarification_count == 6
    assert report.candidate_route_count == 10
    assert report.candidate_pack_count == 7
    assert report.fixture_backed_count == 6
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0


def test_scene_ambiguity_clarification_rows_expose_prompt_candidates_and_record_contract():
    report = build_scene_ambiguity_clarification_ui_audit_report(project_root=ROOT)
    rows = {row.sample_id: row for row in report.rows}

    product = rows["ambiguous_product_manual"]
    assert product.status == "ready"
    assert product.candidate_route_ids == (
        "product_sales_document",
        "technical_long_document",
    )
    assert product.candidate_pack_ids == (
        "application_reports",
        "technical_long_docs",
    )
    assert "产品手册" in product.clarification_prompt
    assert product.report_anchor_id == "request-cell-ambiguous-product-manual"

    notice = rows["ambiguous_batch_notice"]
    assert {"hr_batch_documents", "official_policy_documents"}.issubset(
        set(notice.candidate_route_ids)
    )
    assert notice.candidate_pack_ids == ("batch_forms", "official_policy")
    assert notice.fixture_ids

    for row in report.rows:
        assert tuple(row.ui_surface_ids) == (
            SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_UI_SURFACES
        )
        assert tuple(row.decision_record_fields) == (
            SCENE_AMBIGUITY_CLARIFICATION_REQUIRED_DECISION_FIELDS
        )
        assert row.clarification_prompt
        assert len(row.candidate_route_ids) >= 2
        assert len(row.candidate_pack_ids) >= 2


def test_scene_ambiguity_clarification_export_script_writes_json_and_markdown(tmp_path):
    output_path = tmp_path / "ambiguity_clarification.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_ambiguity_clarification_ui_audit.py",
            "--format",
            "json",
            "--boundary",
            "product_manual_application_vs_technical",
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
    assert payload["counts"]["clarification_count"] == 1
    assert payload["rows"][0]["sample_id"] == "ambiguous_product_manual"

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_ambiguity_clarification_ui_audit.py",
            "--format",
            "markdown",
            "--pack",
            "batch_forms",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Ambiguity Clarification UI Audit" in markdown_result.stdout
    assert "| Clarification | Status | Prompt | Candidate routes |" in (
        markdown_result.stdout
    )
    assert "clarify:project_application_form" in markdown_result.stdout
    assert "fixed_form_batch_documents" in markdown_result.stdout


def test_release_gate_includes_scene_ambiguity_clarification_ui_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_ambiguity_clarification_ui_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_ambiguity_clarification_count"] == 6
    assert payload["counts"]["scene_ambiguity_clarification_ready_count"] == 6
    assert payload["counts"][
        "scene_ambiguity_clarification_candidate_route_count"
    ] == 10
    assert payload["counts"][
        "scene_ambiguity_clarification_candidate_pack_count"
    ] == 7
    assert payload["counts"]["scene_ambiguity_clarification_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_ambiguity_clarification_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_ambiguity_clarification_ui_audit"]["status"] == (
        "passed"
    )
