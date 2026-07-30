import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_control_consistency_audit import (  # noqa: E402
    N2_157C_CONTROL_CONTRACT_IDS,
    audit_scene_control_consistency_report,
    build_scene_control_consistency_audit_report,
)


def test_scene_control_consistency_audit_locks_n2_157c_contracts():
    report = build_scene_control_consistency_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.contract_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.contract_count == 13
    assert report.issue_count == 0
    assert audit_scene_control_consistency_report(report) == ()
    assert tuple(payload["required_contract_ids"]) == N2_157C_CONTROL_CONTRACT_IDS
    assert dict(report.owner_layer_counts) == {
        "material": 1,
        "output": 2,
        "plugin": 1,
        "scene": 3,
        "template": 6,
    }
    assert payload["missing_surface_evidence_count"] == 0

    assert rows["body.left_indent"].canonical_control == "IndentInput"
    assert rows["body.left_indent"].paired_contract_ids == ("body.right_indent",)
    assert rows["body.right_indent"].paired_contract_ids == ("body.left_indent",)
    assert rows["body.left_indent"].template_surface == "TemplatePanel StyleDetail"
    assert rows["body.left_indent"].scene_surface == ""
    assert rows["body.special_indent"].canonical_control == "SpecialIndentInput"
    assert rows["body.special_indent"].template_surface == "TemplatePanel StyleDetail"
    assert rows["body.special_indent"].scene_surface == ""
    assert "mode=none" in rows["body.special_indent"].disabled_state_rule
    assert rows["body.line_spacing"].canonical_control == (
        "StyledComboBox + SpacingInput"
    )
    assert "single/one_half/double" in rows["body.line_spacing"].disabled_state_rule
    assert rows["body.space_before"].paired_contract_ids == ("body.space_after",)
    assert rows["body.space_after"].paired_contract_ids == ("body.space_before",)
    assert rows["fixed_layout.table_row_height"].owner_layer == "scene"
    assert rows["fixed_layout.table_row_height"].template_surface == (
        "not_generic_template"
    )
    assert "word.w:trHeight" in rows["fixed_layout.table_row_height"].parameter_paths

    surface_evidence = {
        item["evidence_id"]: item for item in payload["surface_evidence"]
    }
    assert set(surface_evidence) == {
        "scene_summary_projection",
        "workbench_scene_summary",
        "workbench_execution_gate",
        "report_writer",
    }
    assert all(item["status"] == "ready" for item in surface_evidence.values())


def test_scene_control_consistency_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_control_consistency.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_control_consistency_audit.py",
            "--format",
            "json",
            "--contract",
            "body.special_indent",
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
    assert payload["contract_count"] == 1
    assert payload["rows"][0]["contract_id"] == "body.special_indent"
    assert payload["rows"][0]["canonical_control"] == "SpecialIndentInput"


def test_scene_control_consistency_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_control_consistency_audit.py",
            "--format",
            "markdown",
            "--contract",
            "body.left_indent",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Control Consistency Audit" in result.stdout
    assert "| Contract | Status | Owner | Control | Units | Pair |" in result.stdout
    assert "body.left_indent" in result.stdout
    assert "IndentInput" in result.stdout
    assert "body.right_indent" in result.stdout
    assert "## Surface Evidence" in result.stdout


def test_release_gate_includes_scene_control_consistency_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["checks"]["scene_control_consistency_audit"]["status"] == "passed"
    assert payload["counts"]["scene_control_consistency_contract_count"] == 13
    assert payload["counts"]["scene_control_consistency_issue_count"] == 0
    assert payload["scene_control_consistency_audit"]["status"] == "passed"
