import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_fixed_layout_profile_audit import (  # noqa: E402
    N2_178_FIXED_LAYOUT_PROFILE_SPECS,
    audit_scene_fixed_layout_profile_report,
    build_scene_fixed_layout_profile_audit_report,
)


def test_scene_fixed_layout_profile_audit_locks_n2_178_channels():
    report = build_scene_fixed_layout_profile_audit_report(project_root=ROOT)
    payload = report.to_payload()
    counts = payload["counts"]
    rows = {row.profile_channel_id: row for row in report.rows}

    assert report.status == "passed"
    assert report.profile_channel_count == 12
    assert report.ready_profile_channel_count == 12
    assert report.fixed_layout_surface_count == 5
    assert report.word_ooxml_touchpoint_count == 11
    assert report.runtime_surface_count == 28
    assert report.ui_surface_count == 20
    assert report.report_surface_count == 15
    assert report.repair_target_type_count == 6
    assert report.test_evidence_count == 25
    assert report.covered_pack_count == 6
    assert report.covered_family_count == 6
    assert report.issue_count == 0
    assert report.source_evidence_count == 34
    assert report.missing_source_evidence_count == 0
    assert audit_scene_fixed_layout_profile_report(report) == ()
    assert tuple(row.profile_channel_id for row in report.rows) == tuple(
        spec.profile_channel_id for spec in N2_178_FIXED_LAYOUT_PROFILE_SPECS
    )
    assert all(item["status"] == "ready" for item in payload["source_evidence"])

    registry = rows["fixed_layout_profile_policy_registry"]
    assert registry.pack_ids == ("batch_forms",)
    assert registry.family_ids == ("form_batch_documents",)
    assert "w:trHeight" in registry.word_ooxml_touchpoints
    assert "row_height" in registry.repair_target_types
    assert "control_contracts.fixed_layout.table_row_height" in (
        registry.report_surface_ids
    )

    row_height = rows["row_height_ooxml_runtime"]
    assert "w:hRule" in row_height.word_ooxml_touchpoints
    assert "apply_fixed_layout_row_height_policy" in row_height.runtime_surface_ids
    assert "test_scene_sample_fixed_layout_preserves_existing_row_height" in (
        row_height.test_ids
    )

    answer_sheet = rows["exam_answer_sheet_fixed_layout_runtime"]
    assert answer_sheet.pack_ids == ("exam_education",)
    assert answer_sheet.family_ids == ("exam_teaching",)
    assert "answer_sheet_table" in answer_sheet.fixed_layout_surface_ids
    assert {"w:tbl", "w:trHeight", "w:hRule"}.issubset(
        set(answer_sheet.word_ooxml_touchpoints)
    )
    assert "_render_exam_answer_sheet_docx" in answer_sheet.runtime_surface_ids
    assert "DeliveryPreset.answer_sheet" in answer_sheet.ui_surface_ids
    assert (
        "exam_delivery_runtime.rendered_versions.fixed_layout_row_height_twips"
        in answer_sheet.report_surface_ids
    )

    boundary = rows["generic_table_boundary"]
    assert "TableConfig" in boundary.word_ooxml_touchpoints
    assert "Template table detail" in boundary.ui_surface_ids
    assert "test_table_config_no_longer_exposes_legacy_row_height_setting" in (
        boundary.test_ids
    )

    text_surface = rows["fixed_layout_text_surface_runtime"]
    assert {"content_controls", "textbox_shape"}.issubset(
        set(text_surface.fixed_layout_surface_ids)
    )
    assert "import_ai_boundary" in text_surface.pack_ids
    assert "iter_fixed_layout_text_blocks" in text_surface.runtime_surface_ids

    entity_mapping = rows["entity_fill_fixed_layout_mapping"]
    assert "fixed_layout_field_mapping" in entity_mapping.report_surface_ids
    assert "placeholder_residue" in entity_mapping.repair_target_types

    family_defaults = rows["form_batch_family_defaults"]
    assert "placeholder_residue" in family_defaults.fixed_layout_surface_ids
    assert "batch_summary_report" in family_defaults.report_surface_ids
    assert "DeliveryPreset.per_record_docx" in family_defaults.runtime_surface_ids

    sample_fixture = rows["fixed_layout_sample_fixture_preview"]
    assert "build_scene_sample_docx" in sample_fixture.runtime_surface_ids
    assert "fixture_manifest" in sample_fixture.report_surface_ids

    preflight = rows["object_preflight_fixed_layout_surfaces"]
    assert "exam_education" in preflight.pack_ids
    assert "object_preflight" in preflight.repair_target_types
    assert "inspect_docx_package" in preflight.runtime_surface_ids

    repair_route = rows["fixed_layout_repair_route"]
    assert {"fixed_layout", "row_height", "content_controls", "textboxes"}.issubset(
        set(repair_route.repair_target_types)
    )
    assert "WorkbenchPanel._open_issue_repair_target" in (
        repair_route.runtime_surface_ids
    )

    report_evidence = rows["fixed_layout_report_evidence"]
    assert "word.w:trHeight" in report_evidence.word_ooxml_touchpoints
    assert "control_contracts" in report_evidence.report_surface_ids

    matrix_browse = rows["matrix_browse_fixed_layout_profile"]
    assert "SceneMatrixDashboard.fixed_layout_profile" in (
        matrix_browse.runtime_surface_ids
    )
    assert "Dashboard card" in matrix_browse.ui_surface_ids
    assert "release_gate.counts" in matrix_browse.report_surface_ids

    assert counts["profile_channel_count"] == report.profile_channel_count
    assert counts["missing_source_evidence_count"] == 0


def test_scene_fixed_layout_profile_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_fixed_layout_profile.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_fixed_layout_profile_audit.py",
            "--format",
            "json",
            "--profile-channel",
            "matrix_browse_fixed_layout_profile",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.stdout == ""
    assert payload["status"] == "passed"
    assert payload["counts"]["profile_channel_count"] == 1
    assert payload["rows"][0]["profile_channel_id"] == (
        "matrix_browse_fixed_layout_profile"
    )
    assert "fixed_layout" in payload["rows"][0]["repair_target_types"]


def test_scene_fixed_layout_profile_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_fixed_layout_profile_audit.py",
            "--format",
            "markdown",
            "--profile-channel",
            "row_height_ooxml_runtime",
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )

    assert "# Fixed-Layout Profile Productization Audit" in result.stdout
    assert "| Channel | Status | Coverage | Packs | Families | Surfaces |" in (
        result.stdout
    )
    assert "row_height_ooxml_runtime" in result.stdout
    assert "apply_fixed_layout_row_height_policy" in result.stdout
    assert "## Source Evidence" in result.stdout


def test_release_gate_includes_scene_fixed_layout_profile_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_fixed_layout_profile_audit"]["status"] == (
        "passed"
    )
    assert payload["counts"]["scene_fixed_layout_profile_channel_count"] == 12
    assert payload["counts"]["scene_fixed_layout_profile_ready_channel_count"] == 12
    assert payload["counts"]["scene_fixed_layout_profile_surface_count"] == 5
    assert payload["counts"]["scene_fixed_layout_profile_ooxml_touchpoint_count"] == 11
    assert payload["counts"]["scene_fixed_layout_profile_runtime_surface_count"] == 28
    assert payload["counts"]["scene_fixed_layout_profile_ui_surface_count"] == 20
    assert payload["counts"]["scene_fixed_layout_profile_report_surface_count"] == 15
    assert payload["counts"]["scene_fixed_layout_profile_repair_target_type_count"] == 6
    assert payload["counts"]["scene_fixed_layout_profile_test_evidence_count"] == 25
    assert payload["counts"]["scene_fixed_layout_profile_covered_pack_count"] == 6
    assert payload["counts"]["scene_fixed_layout_profile_covered_family_count"] == 6
    assert payload["counts"]["scene_fixed_layout_profile_issue_count"] == 0
    assert (
        payload["counts"]["scene_fixed_layout_profile_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_fixed_layout_profile_audit"]["status"] == "passed"
