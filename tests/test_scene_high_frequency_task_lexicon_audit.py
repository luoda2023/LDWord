import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_high_frequency_task_lexicon_audit import (  # noqa: E402
    N2_161_REQUIRED_TASK_IDS,
    audit_high_frequency_task_lexicon_report,
    build_high_frequency_task_lexicon_audit_report,
)


def test_high_frequency_task_lexicon_audit_locks_v29_task_families():
    report = build_high_frequency_task_lexicon_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.task_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.task_count == 30
    assert report.phrase_count == 32
    assert report.issue_count == 0
    assert report.negative_task_count == 1
    assert report.ambiguous_task_count == 4
    assert report.manual_boundary_task_count == 10
    assert report.handoff_task_count == 1
    assert report.request_sample_count == 36
    assert report.request_cell_count == 36
    assert report.missing_source_evidence_count == 0
    assert audit_high_frequency_task_lexicon_report(report) == ()
    assert tuple(payload["required_task_ids"]) == N2_161_REQUIRED_TASK_IDS
    assert payload["counts"]["task_count"] == report.task_count
    assert payload["counts"]["phrase_count"] == report.phrase_count
    assert payload["counts"]["negative_task_count"] == report.negative_task_count
    assert payload["counts"]["issue_count"] == report.issue_count
    assert (
        payload["counts"]["missing_source_evidence_count"]
        == report.missing_source_evidence_count
    )

    for row in report.rows:
        assert row.status == "ready"
        assert row.issue_ids == ()
        assert row.core_phrases
        assert row.required_sample_ids
        assert row.request_cell_sample_ids == row.required_sample_ids

    assert rows["quick_formatting_cleanup"].expected_pack_ids == (
        "quick_formatting",
    )
    assert rows["exam_teaching_versions"].expected_plugin_gate_ids == (
        "exam_ai_complex_diagram_gate",
    )
    assert "bidding_consortium_seal_archive" in (
        rows["bidding_qualification_archive"].required_sample_ids
    )
    assert rows["import_pdf_thesis_boundary"].expected_handoff_pack_ids == (
        "chinese_academic",
    )
    assert rows["ambiguous_product_manual"].expected_status == "ambiguous"
    assert set(rows["ambiguous_product_manual"].expected_route_ids) == {
        "product_sales_document",
        "technical_long_document",
    }

    negative = rows["negative_non_word_native_delivery"]
    assert negative.expected_status == "unmatched"
    assert negative.boundary_type == "negative"
    assert negative.expected_route_ids == ()
    assert negative.expected_pack_ids == ()
    assert set(negative.required_sample_ids) == {
        "negative_ppt_poster_design",
        "negative_webpage_publish",
        "unknown_stays_unmatched",
    }


def test_high_frequency_task_lexicon_filters_negative_boundary():
    report = build_high_frequency_task_lexicon_audit_report(
        boundary_type="negative",
        project_root=ROOT,
    )

    assert report.status == "passed"
    assert report.task_count == 1
    assert report.rows[0].task_id == "negative_non_word_native_delivery"
    assert {phrase.status for phrase in report.rows[0].phrase_audits} == {
        "unmatched",
    }


def test_high_frequency_task_lexicon_export_script_writes_json(tmp_path):
    output_path = tmp_path / "task_lexicon.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_high_frequency_task_lexicon_audit.py",
            "--format",
            "json",
            "--task",
            "import_pdf_thesis_boundary",
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
    assert payload["task_count"] == 1
    assert payload["rows"][0]["task_id"] == "import_pdf_thesis_boundary"
    assert payload["rows"][0]["expected_handoff_pack_ids"] == [
        "chinese_academic",
    ]


def test_high_frequency_task_lexicon_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_high_frequency_task_lexicon_audit.py",
            "--format",
            "markdown",
            "--boundary",
            "ambiguous",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene High-Frequency Task Lexicon Audit" in result.stdout
    assert "| Task | Status | Expected | Boundary |" in result.stdout
    assert "ambiguous_product_manual" in result.stdout
    assert "product_sales_document" in result.stdout


def test_release_gate_includes_high_frequency_task_lexicon_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["high_frequency_task_lexicon_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["high_frequency_task_lexicon_task_count"] == 30
    assert payload["counts"]["high_frequency_task_lexicon_phrase_count"] == 32
    assert payload["counts"]["high_frequency_task_lexicon_negative_task_count"] == 1
    assert payload["counts"]["high_frequency_task_lexicon_ambiguous_task_count"] == 4
    assert payload["counts"]["high_frequency_task_lexicon_issue_count"] == 0
    assert payload["high_frequency_task_lexicon_audit"]["status"] == "passed"
