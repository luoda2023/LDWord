import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_word_risk_closure_audit import (  # noqa: E402
    N2_157D_WORD_RISK_SURFACE_IDS,
    audit_scene_word_risk_closure_report,
    build_scene_word_risk_closure_audit_report,
)


def test_scene_word_risk_closure_audit_locks_ooxml_surface_chain():
    report = build_scene_word_risk_closure_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.surface_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.surface_count == 15
    assert report.issue_count == 0
    assert report.preflight_surface_count == 8
    assert audit_scene_word_risk_closure_report(report) == ()
    assert tuple(payload["required_surface_ids"]) == N2_157D_WORD_RISK_SURFACE_IDS

    for row in report.rows:
        assert row.pack_ids
        assert row.source_evidence_count > 0
        assert "runtime" in row.evidence_layer_ids
        assert "test" in row.evidence_layer_ids

    fixed = rows["fixed_row_height"]
    assert fixed.preflight_targets == ()
    assert fixed.sample_surface_ids == ("fixed_row_height",)
    assert "batch_forms_fixed_layout" in fixed.sample_fixture_ids
    assert any(
        item.source_path == "src/shared/engine/fixed_layout_tables.py"
        for item in fixed.source_evidence
    )

    comments = rows["comments_revisions"]
    assert set(comments.preflight_targets) == {"comments", "tracked_changes"}
    assert "english_journal_revision_comments" in comments.sample_fixture_ids
    assert "contract_delivery_revisions" in comments.sample_fixture_ids

    notes = rows["footnotes_endnotes"]
    assert notes.preflight_targets == ()
    assert notes.sample_surface_ids == ()
    assert any(
        item.source_path == "src/shared/engine/count_engine.py"
        for item in notes.source_evidence
    )

    ole = rows["ole_embedded_vba"]
    assert set(ole.preflight_targets) == {
        "ole_objects",
        "embedded_workbooks",
        "macros",
    }
    assert "technical_long_docs_skip_objects" in ole.sample_fixture_ids
    assert "import_ai_boundary_blocking_macro" in ole.sample_fixture_ids
    assert {"object_preflight", "report", "workbench"} <= set(ole.evidence_layer_ids)

    package = rows["package_relationships"]
    assert "embedded_packages" in package.preflight_targets
    assert "bidding_materials_attachments" in package.sample_fixture_ids


def test_scene_word_risk_closure_export_script_writes_json(tmp_path):
    output_path = tmp_path / "word_risk.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_word_risk_closure_audit.py",
            "--format",
            "json",
            "--surface",
            "fixed_row_height",
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
    assert payload["surface_count"] == 1
    assert payload["rows"][0]["surface_id"] == "fixed_row_height"
    assert payload["rows"][0]["sample_surface_ids"] == ["fixed_row_height"]


def test_scene_word_risk_closure_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_word_risk_closure_audit.py",
            "--format",
            "markdown",
            "--surface",
            "ole_embedded_vba",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Word Risk Closure Audit" in result.stdout
    assert "| Surface | Status | Packs | Sample Surfaces |" in result.stdout
    assert "ole_embedded_vba" in result.stdout
    assert "technical_long_docs_skip_objects" in result.stdout
    assert "object_preflight.report" in result.stdout


def test_release_gate_includes_scene_word_risk_closure_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_word_risk_closure_audit"]["status"] == "passed"
    assert payload["counts"]["scene_word_risk_surface_count"] == 15
    assert payload["counts"]["scene_word_risk_issue_count"] == 0
    assert payload["counts"]["scene_word_risk_preflight_surface_count"] == 8
    assert payload["scene_word_risk_closure_audit"]["status"] == "passed"
