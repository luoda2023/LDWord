import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.control_contract_registry import get_control_contract  # noqa: E402
from src.config.scene_formula_output_watermark_audit import (  # noqa: E402
    audit_scene_formula_output_watermark_report,
    build_scene_formula_output_watermark_audit_report,
)


def test_formula_output_watermark_audit_locks_capability_ownership():
    report = build_scene_formula_output_watermark_audit_report(project_root=ROOT)
    rows = {row.capability_id: row for row in report.capability_rows}
    families = {row.family_id: row for row in report.family_rows}

    assert report.status == "passed"
    assert audit_scene_formula_output_watermark_report(report) == ((), ())
    assert report.capability_count == 3
    assert report.ready_capability_count == 3
    assert report.family_count == 15
    assert report.ready_family_count == 14
    assert report.boundary_family_count == 1
    assert report.accounted_family_count == 15
    assert report.formula_family_count == 3
    assert report.output_family_count == 15
    assert report.watermark_family_count == 1
    assert report.plugin_gate_count == 2
    assert report.control_contract_count == 4
    assert report.parameter_path_count == 26
    assert report.template_baseline_path_count == 1
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0

    formula = rows["formula_policy"]
    assert formula.expected_owner_layer == "scene"
    assert formula.family_ids == ("thesis_cn", "journal_en", "exam_teaching")
    assert formula.template_baseline_paths == ("formula_table.formula_font_name",)
    assert formula.plugin_gate_ids == (
        "exam_ai_complex_diagram_gate",
        "import_ai_conversion_gate",
    )
    assert "full LaTeX/OCR/AI quality" in formula.boundary_note

    output = rows["output_delivery"]
    assert output.expected_owner_layer == "output"
    assert len(output.family_ids) == 15
    assert output.control_contract_ids == (
        "output.delivery_preset",
        "output.content_visibility_rules",
    )

    watermark = rows["watermark_status"]
    assert watermark.expected_owner_layer == "scene"
    assert watermark.family_ids == ("meeting_policy_documents",)
    assert "watermark.font_size" in watermark.parameter_paths

    assert families["meeting_policy_documents"].capability_ids == (
        "output_delivery",
        "watermark_status",
    )
    assert families["thesis_cn"].capability_ids == (
        "formula_policy",
        "output_delivery",
    )
    assert families["ip_patent_documents"].status == "boundary"
    assert families["ip_patent_documents"].capability_ids == ("output_delivery",)

    watermark_contract = get_control_contract("scene.watermark_status")
    assert "scene.delivery_presets.*.watermark_status" not in (
        watermark_contract.parameter_paths
    )


def test_formula_output_watermark_audit_filters_capability_family_and_pack():
    formula_report = build_scene_formula_output_watermark_audit_report(
        capability_id="formula_policy",
        project_root=ROOT,
    )
    family_report = build_scene_formula_output_watermark_audit_report(
        family_id="meeting_policy_documents",
        project_root=ROOT,
    )
    pack_report = build_scene_formula_output_watermark_audit_report(
        pack_id="official_policy",
        project_root=ROOT,
    )

    assert [row.capability_id for row in formula_report.capability_rows] == [
        "formula_policy"
    ]
    assert [row.family_id for row in formula_report.family_rows] == [
        "thesis_cn",
        "journal_en",
        "exam_teaching",
    ]
    assert [row.family_id for row in family_report.family_rows] == [
        "meeting_policy_documents"
    ]
    assert family_report.family_rows[0].watermark_relevant is True
    assert [row.capability_id for row in pack_report.capability_rows] == [
        "output_delivery",
        "watermark_status",
    ]
    assert [row.family_id for row in pack_report.family_rows] == [
        "meeting_policy_documents"
    ]


def test_formula_output_watermark_audit_export_script_writes_json(tmp_path):
    output_path = tmp_path / "formula_output_watermark.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_formula_output_watermark_audit.py",
            "--format",
            "json",
            "--capability",
            "watermark_status",
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
    assert payload["capability_rows"][0]["capability_id"] == "watermark_status"
    assert payload["family_rows"][0]["family_id"] == "meeting_policy_documents"


def test_formula_output_watermark_audit_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_formula_output_watermark_audit.py",
            "--format",
            "markdown",
            "--capability",
            "formula_policy",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Formula/Output/Watermark Audit" in result.stdout
    assert "| Capability | Status | Owner | Families | Contracts | Consumers | Plugin Gates |" in (
        result.stdout
    )
    assert "formula_policy" in result.stdout
    assert "import_ai_conversion_gate" in result.stdout


def test_release_gate_includes_formula_output_watermark_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_formula_output_watermark_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_formula_output_watermark_capability_count"] == 3
    assert (
        payload["counts"]["scene_formula_output_watermark_ready_capability_count"]
        == 3
    )
    assert payload["counts"]["scene_formula_output_watermark_family_count"] == 15
    assert payload["counts"]["scene_formula_output_watermark_ready_family_count"] == 14
    assert (
        payload["counts"]["scene_formula_output_watermark_boundary_family_count"]
        == 1
    )
    assert (
        payload["counts"]["scene_formula_output_watermark_accounted_family_count"]
        == 15
    )
    assert payload["counts"]["scene_formula_output_watermark_formula_family_count"] == 3
    assert payload["counts"]["scene_formula_output_watermark_output_family_count"] == 15
    assert (
        payload["counts"]["scene_formula_output_watermark_watermark_family_count"]
        == 1
    )
    assert payload["counts"]["scene_formula_output_watermark_plugin_gate_count"] == 2
    assert payload["counts"]["scene_formula_output_watermark_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_formula_output_watermark_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_formula_output_watermark_audit"]["status"] == "passed"
