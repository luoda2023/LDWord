import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_import_handoff_audit import (  # noqa: E402
    N2_163_REQUIRED_HANDOFF_IDS,
    N2_163_REQUIRED_REPORT_FIELDS,
    audit_scene_import_handoff_report,
    build_scene_import_handoff_audit_report,
)


def test_scene_import_handoff_audit_locks_pdf_thesis_handoff_chain():
    report = build_scene_import_handoff_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.handoff_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.handoff_count == 1
    assert report.ready_handoff_count == 1
    assert report.target_pack_count == 1
    assert report.fallback_strategy_count == 1
    assert report.issue_count == 0
    assert report.missing_source_evidence_count == 0
    assert audit_scene_import_handoff_report(report) == ()
    assert tuple(payload["required_handoff_ids"]) == N2_163_REQUIRED_HANDOFF_IDS
    assert {evidence.status for evidence in report.source_evidence} == {"ready"}

    row = rows["pdf_thesis_import_to_chinese_academic"]
    assert row.status == "ready"
    assert row.sample_id == "import_pdf_thesis"
    assert row.route_status == "matched"
    assert row.selected_route_id == "import_pdf_thesis_boundary"
    assert row.selected_pack_id == "import_ai_boundary"
    assert row.source_pack_id == "import_ai_boundary"
    assert row.target_pack_id == "chinese_academic"
    assert row.target_family_id == "thesis_cn"
    assert row.route_handoff_pack_id == "chinese_academic"
    assert row.route_handoff_family_id == "thesis_cn"
    assert row.sample_handoff_pack_ids == ("chinese_academic",)
    assert row.sample_handoff_family_ids == ("thesis_cn",)
    assert row.request_cell_coverage_level == "manual_boundary_fixture"
    assert row.request_cell_fixture_ids == ("import_ai_boundary_blocking_macro",)
    assert row.plugin_gate_id == "import_ai_conversion_gate"
    assert row.gate_manual_confirmation_required is True
    assert row.gate_confidence_report_required is True
    assert row.gate_blocks_core_execution is True
    assert row.required_decision_state == "needs_plugin_handoff"
    assert "needs_plugin_handoff" in row.gate_decision_states
    assert all(field in row.gate_report_fields for field in N2_163_REQUIRED_REPORT_FIELDS)
    assert row.required_report_fields == N2_163_REQUIRED_REPORT_FIELDS
    assert row.fallback_strategy == (
        "stay_in_import_ai_boundary_until_manual_confirmation"
    )
    assert "chinese_academic" in row.target_family_pack_ids


def test_scene_import_handoff_export_script_writes_json(tmp_path):
    output_path = tmp_path / "import_handoff.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_import_handoff_audit.py",
            "--format",
            "json",
            "--target-pack",
            "chinese_academic",
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
    assert payload["counts"]["handoff_count"] == 1
    assert payload["counts"]["ready_handoff_count"] == 1
    assert payload["rows"][0]["handoff_id"] == (
        "pdf_thesis_import_to_chinese_academic"
    )
    assert payload["rows"][0]["target_pack_id"] == "chinese_academic"
    assert payload["rows"][0]["target_family_id"] == "thesis_cn"
    assert payload["rows"][0]["required_report_fields"] == list(
        N2_163_REQUIRED_REPORT_FIELDS
    )


def test_scene_import_handoff_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_import_handoff_audit.py",
            "--format",
            "markdown",
            "--handoff",
            "pdf_thesis_import_to_chinese_academic",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Import Handoff Audit" in result.stdout
    assert "| Handoff | Source | Target | Route | Gate | Decision |" in result.stdout
    assert "pdf_thesis_import_to_chinese_academic" in result.stdout
    assert "import_ai_boundary" in result.stdout
    assert "chinese_academic/thesis_cn" in result.stdout
    assert "needs_plugin_handoff" in result.stdout
    assert "stay_in_import_ai_boundary_until_manual_confirmation" in result.stdout


def test_release_gate_includes_scene_import_handoff_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_import_handoff_audit"]["status"] == "passed"
    assert payload["counts"]["scene_import_handoff_count"] == 1
    assert payload["counts"]["scene_import_handoff_ready_count"] == 1
    assert payload["counts"]["scene_import_handoff_target_pack_count"] == 1
    assert payload["counts"]["scene_import_handoff_fallback_strategy_count"] == 1
    assert payload["counts"]["scene_import_handoff_issue_count"] == 0
    assert (
        payload["counts"][
            "scene_import_handoff_missing_source_evidence_count"
        ]
        == 0
    )
    assert payload["scene_import_handoff_audit"]["status"] == "passed"
