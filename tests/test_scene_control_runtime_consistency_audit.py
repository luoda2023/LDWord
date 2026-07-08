import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_control_runtime_consistency_audit import (  # noqa: E402
    N2_175_SCENE_CONTROL_RUNTIME_SPECS,
    audit_scene_control_runtime_consistency_report,
    build_scene_control_runtime_consistency_audit_report,
)


def test_scene_control_runtime_consistency_locks_n2_175_runtime_groups():
    report = build_scene_control_runtime_consistency_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.runtime_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.runtime_control_count == 12
    assert report.ready_runtime_control_count == 12
    assert report.control_contract_link_count == 16
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert audit_scene_control_runtime_consistency_report(report) == ()
    assert tuple(row.runtime_id for row in report.rows) == tuple(
        spec.runtime_id for spec in N2_175_SCENE_CONTROL_RUNTIME_SPECS
    )
    assert dict(report.owner_layer_counts) == {
        "material": 1,
        "output": 2,
        "plugin": 1,
        "scene": 3,
        "template": 5,
    }

    assert rows["text_font_size_shared_controls"].contract_ids == (
        "body.font_cn",
        "body.font_en",
        "body.size_pt",
    )
    assert "FontCombo" in rows["text_font_size_shared_controls"].shared_component_ids
    assert "SizeCombo" in rows["text_font_size_shared_controls"].shared_component_ids

    indent = rows["paragraph_indent_pair"]
    assert indent.contract_ids == ("body.left_indent", "body.right_indent")
    assert "IndentInput" in indent.shared_component_ids
    assert "same row/group pair" in indent.required_semantics
    assert "style.left_indent_unit" in indent.runtime_consumer_ids
    assert "style.right_indent_unit" in indent.runtime_consumer_ids

    special = rows["special_indent_switch"]
    assert special.contract_ids == ("body.special_indent",)
    assert "SpecialIndentInput" in special.shared_component_ids
    assert "interactive mode switch: none/first_line/hanging" in (
        special.required_semantics
    )
    assert "mode=none returns value 0" in special.required_semantics

    line_spacing = rows["line_spacing_binding"]
    assert line_spacing.contract_ids == ("body.line_spacing",)
    assert "line type and value stay in one group" in (
        line_spacing.required_semantics
    )
    assert "style.line_spacing_pt" in line_spacing.runtime_consumer_ids

    spacing = rows["paragraph_spacing_pair"]
    assert spacing.contract_ids == ("body.space_before", "body.space_after")
    assert "SpacingInput" in spacing.shared_component_ids
    assert "auto disables numeric editing" in spacing.required_semantics

    row_height = rows["fixed_layout_row_height_profile"]
    assert row_height.contract_ids == ("fixed_layout.table_row_height",)
    assert row_height.scope == "fixed_layout_profile"
    assert "not a generic TableConfig control" in row_height.required_semantics
    assert "word.w:trHeight" in row_height.runtime_consumer_ids

    assert rows["formula_policy_scene_controls"].owner_layer_ids == ("scene",)
    assert rows["watermark_status_scene_controls"].owner_layer_ids == ("scene",)
    assert rows["delivery_preset_controls"].owner_layer_ids == ("output",)
    assert rows["content_visibility_rule_controls"].owner_layer_ids == ("output",)
    assert rows["material_schema_selection_controls"].owner_layer_ids == (
        "material",
    )
    assert rows["plugin_manual_gate_runtime_controls"].owner_layer_ids == ("plugin",)

    assert payload["source_evidence_count"] == sum(
        len(spec.evidence) for spec in N2_175_SCENE_CONTROL_RUNTIME_SPECS
    )
    assert payload["counts"]["runtime_control_count"] == report.runtime_control_count
    assert (
        payload["counts"]["ready_runtime_control_count"]
        == report.ready_runtime_control_count
    )
    assert (
        payload["counts"]["control_contract_link_count"]
        == report.control_contract_link_count
    )
    assert payload["counts"]["issue_count"] == report.issue_count
    assert (
        payload["counts"]["missing_source_evidence_count"]
        == report.missing_source_evidence_count
    )
    assert all(item["status"] == "ready" for item in payload["source_evidence"])


def test_scene_control_runtime_consistency_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_control_runtime_consistency.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_control_runtime_consistency_audit.py",
            "--format",
            "json",
            "--runtime",
            "special_indent_switch",
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
    assert payload["runtime_control_count"] == 1
    assert payload["rows"][0]["runtime_id"] == "special_indent_switch"
    assert payload["rows"][0]["contract_ids"] == ["body.special_indent"]


def test_scene_control_runtime_consistency_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_control_runtime_consistency_audit.py",
            "--format",
            "markdown",
            "--runtime",
            "paragraph_indent_pair",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Control Runtime Consistency Audit" in result.stdout
    assert "| Runtime | Status | Contracts | Components | Scope | Semantics |" in (
        result.stdout
    )
    assert "paragraph_indent_pair" in result.stdout
    assert "body.left_indent" in result.stdout
    assert "IndentInput" in result.stdout
    assert "## Source Evidence" in result.stdout


def test_release_gate_includes_scene_control_runtime_consistency_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert (
        payload["checks"]["scene_control_runtime_consistency_audit"]["status"]
        == "passed"
    )
    assert payload["counts"]["scene_control_runtime_control_count"] == 12
    assert payload["counts"]["scene_control_runtime_ready_control_count"] == 12
    assert payload["counts"]["scene_control_runtime_contract_link_count"] == 16
    assert payload["counts"]["scene_control_runtime_issue_count"] == 0
    assert (
        payload["counts"]["scene_control_runtime_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_control_runtime_consistency_audit"]["status"] == "passed"
