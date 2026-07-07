import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_input_source_audit import (  # noqa: E402
    BOUNDARY_INPUT_SOURCE_IDS,
    STRUCTURED_SOURCE_FORMATS,
    audit_scene_input_source_report,
    build_scene_input_source_audit_report,
)


def test_scene_input_source_audit_baseline_counts():
    report = build_scene_input_source_audit_report(project_root=ROOT)
    issues, warnings = audit_scene_input_source_report(report)

    assert report.status == "passed"
    assert issues == ()
    assert warnings == report.warnings
    assert report.family_count == 15
    assert report.ready_family_count == 14
    assert report.boundary_family_count == 1
    assert report.pack_count == 12
    assert report.input_pack_count == 12
    assert report.ready_input_pack_count == 12
    assert report.accepted_format_count == 6
    assert report.structured_format_count == len(STRUCTURED_SOURCE_FORMATS)
    assert report.boundary_input_source_count == len(BOUNDARY_INPUT_SOURCE_IDS)
    assert report.material_required_family_count == 12
    assert report.markdown_enabled_family_count == 12
    assert report.latex_fragment_family_count == 8
    assert report.render_source_count == 8
    assert report.target_template_count == 3
    assert report.format_count == 10
    assert report.issue_count == 0
    assert report.warning_count == 5
    assert report.missing_source_evidence_count == 0


def test_exam_teaching_input_source_includes_question_and_teaching_assets():
    report = build_scene_input_source_audit_report(project_root=ROOT)
    families = {row.family_id: row for row in report.family_rows}
    packs = {row.pack_id: row for row in report.pack_rows}

    exam = families["exam_teaching"]
    assert exam.status == "ready"
    assert exam.actual_material_schema_ids == (
        "exam_items_v1",
        "teaching_assets_v1",
    )
    assert exam.structured_formats == ("json", "xlsx")
    assert "structured_intermediate" in exam.render_source_ids
    assert exam.issue_ids == ()

    pack = packs["exam_education"]
    assert pack.status == "boundary_ready"
    assert pack.material_schema_ids == (
        "exam_items_v1",
        "teaching_assets_v1",
    )
    assert {"json", "xlsx"}.issubset(set(pack.structured_formats))
    assert {"ai_content_generation", "complex_diagram_generation"}.issubset(
        set(pack.boundary_input_source_ids)
    )


def test_import_ai_boundary_keeps_high_risk_inputs_as_boundary_sources():
    report = build_scene_input_source_audit_report(project_root=ROOT)
    packs = {row.pack_id: row for row in report.pack_rows}

    boundary = packs["import_ai_boundary"]
    assert boundary.status == "boundary_ready"
    assert boundary.input_formats == ()
    assert boundary.structured_formats == ()
    assert boundary.issue_ids == ()
    assert set(boundary.boundary_input_source_ids) == set(BOUNDARY_INPUT_SOURCE_IDS)


def test_source_format_rows_cover_core_and_boundary_inputs():
    report = build_scene_input_source_audit_report(project_root=ROOT)
    rows = {row.source_id: row for row in report.format_rows}

    for source_id in (
        "docx",
        "markdown",
        "json",
        "xlsx",
        "bibtex",
        "csl_json",
        *BOUNDARY_INPUT_SOURCE_IDS,
    ):
        assert source_id in rows

    assert rows["json"].status == "ready"
    assert rows["json"].source_kind == "structured"
    assert rows["pdf_ocr_import"].status == "boundary"
    assert rows["pdf_ocr_import"].boundary_gate_ids
    assert rows["ai_content_generation"].status == "boundary"


def test_scene_input_source_export_script_prints_markdown_and_writes_json(tmp_path):
    output_path = tmp_path / "scene_input_source.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_input_source_audit.py",
            "--format",
            "json",
            "--family",
            "exam_teaching",
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
    assert payload["counts"]["family_count"] == 1
    assert payload["family_rows"][0]["family_id"] == "exam_teaching"

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_input_source_audit.py",
            "--format",
            "markdown",
            "--source",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene InputSourceProfile Audit" in markdown_result.stdout
    assert "| Family | Status | Packs | Planned inputs | Actual inputs | Structured | Material | Rendering |" in markdown_result.stdout
    assert "exam_teaching" in markdown_result.stdout
    assert "teaching_assets_v1" in markdown_result.stdout
