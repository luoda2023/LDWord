import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_delivery_preset_audit import (  # noqa: E402
    audit_scene_delivery_preset_report,
    build_scene_delivery_preset_audit_report,
)


def test_scene_delivery_preset_audit_tracks_high_frequency_family_delivery():
    report = build_scene_delivery_preset_audit_report(project_root=ROOT)
    rows = {row.family_id: row for row in report.family_rows}

    assert report.status == "passed"
    assert audit_scene_delivery_preset_report(report) == ((), ())
    assert report.family_count == 15
    assert report.ready_family_count == 14
    assert report.boundary_family_count == 1
    assert report.accounted_family_count == 15
    assert report.pack_count == 12
    assert report.delivery_pack_count == 12
    assert report.ready_delivery_pack_count == 11
    assert report.boundary_delivery_pack_count == 1
    assert report.accounted_delivery_pack_count == 12
    assert report.delivery_preset_count == 41
    assert report.final_docx_preset_count == 35
    assert report.compare_docx_preset_count == 17
    assert report.report_only_preset_count == 18
    assert report.material_package_preset_count == 15
    assert report.structured_intermediate_preset_count == 39
    assert report.content_visibility_rule_count == 18
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0

    project = rows["project_application"]
    assert project.planned_delivery_preset_ids == (
        "application_package",
        "attachment_inventory_report",
    )
    assert project.actual_delivery_preset_ids == (
        "application_package",
        "attachment_inventory_report",
    )
    assert project.report_only_preset_count == 1
    assert project.material_package_preset_count == 2

    contract = rows["contract_delivery"]
    assert "compare_docx" not in contract.planned_delivery_preset_ids
    assert contract.artifact_pseudo_ids == ()
    assert contract.compare_docx_preset_count == 2
    assert contract.report_only_preset_count == 1

    exam = rows["exam_teaching"]
    assert "answer_sheet" in exam.actual_delivery_preset_ids
    assert exam.structured_intermediate_preset_count == 5
    assert exam.content_visibility_rule_count == 18

    patent = rows["ip_patent_documents"]
    assert patent.status == "boundary"
    assert patent.plugin_boundary_only is True
    assert patent.actual_delivery_preset_ids == ()
    assert patent.issue_ids == ()


def test_scene_delivery_preset_audit_filters_pack_family_and_preset():
    project_report = build_scene_delivery_preset_audit_report(
        family_id="project_application",
        project_root=ROOT,
    )
    professional_report = build_scene_delivery_preset_audit_report(
        pack_id="professional_disclosure",
        project_root=ROOT,
    )
    answer_sheet_report = build_scene_delivery_preset_audit_report(
        preset_id="answer_sheet",
        project_root=ROOT,
    )

    assert project_report.status == "passed"
    assert [row.family_id for row in project_report.family_rows] == [
        "project_application"
    ]
    assert [row.pack_id for row in project_report.pack_rows] == [
        "application_reports"
    ]

    assert professional_report.family_count == 4
    assert [row.pack_id for row in professional_report.pack_rows] == [
        "professional_disclosure"
    ]
    assert {row.family_id for row in professional_report.family_rows} == {
        "finance_quote_documents",
        "ip_patent_documents",
        "bilingual_translation_documents",
        "regulated_disclosure_documents",
    }
    assert professional_report.ready_family_count == 3
    assert professional_report.boundary_family_count == 1

    assert [row.family_id for row in answer_sheet_report.family_rows] == [
        "exam_teaching"
    ]
    assert [row.pack_id for row in answer_sheet_report.pack_rows] == [
        "exam_education"
    ]


def test_scene_delivery_preset_audit_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_delivery_preset_audit.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_delivery_preset_audit.py",
            "--format",
            "json",
            "--preset",
            "answer_sheet",
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
    assert payload["family_rows"][0]["family_id"] == "exam_teaching"
    assert "answer_sheet" in payload["family_rows"][0]["actual_delivery_preset_ids"]


def test_scene_delivery_preset_audit_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_delivery_preset_audit.py",
            "--format",
            "markdown",
            "--family",
            "project_application",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene DeliveryPreset Audit" in result.stdout
    assert "| Family | Status | Packs | Planned | Actual | Default | Final |" in (
        result.stdout
    )
    assert "project_application" in result.stdout
    assert "application_package" in result.stdout
    assert "attachment_inventory_report" in result.stdout


def test_release_gate_includes_scene_delivery_preset_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_delivery_preset_audit"]["status"] == "passed"
    assert payload["counts"]["scene_delivery_preset_family_count"] == 15
    assert payload["counts"]["scene_delivery_preset_ready_family_count"] == 14
    assert payload["counts"]["scene_delivery_preset_boundary_family_count"] == 1
    assert payload["counts"]["scene_delivery_preset_accounted_family_count"] == 15
    assert payload["counts"]["scene_delivery_preset_pack_count"] == 12
    assert payload["counts"]["scene_delivery_preset_delivery_pack_count"] == 12
    assert payload["counts"]["scene_delivery_preset_ready_delivery_pack_count"] == 11
    assert payload["counts"]["scene_delivery_preset_boundary_delivery_pack_count"] == 1
    assert payload["counts"]["scene_delivery_preset_accounted_delivery_pack_count"] == 12
    assert payload["counts"]["scene_delivery_preset_unique_preset_count"] == 41
    assert payload["counts"]["scene_delivery_preset_compare_docx_preset_count"] == 17
    assert payload["counts"]["scene_delivery_preset_report_only_preset_count"] == 18
    assert payload["counts"]["scene_delivery_preset_issue_count"] == 0
    assert (
        payload["counts"]["scene_delivery_preset_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_delivery_preset_audit"]["status"] == "passed"
