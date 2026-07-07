import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_material_schema_audit import (  # noqa: E402
    audit_scene_material_schema_report,
    build_scene_material_schema_audit_report,
)


def test_scene_material_schema_audit_covers_families_packs_and_registry():
    report = build_scene_material_schema_audit_report(project_root=ROOT)
    payload = report.to_payload()
    family_rows = {row.family_id: row for row in report.family_rows}
    pack_rows = {row.pack_id: row for row in report.pack_rows}
    schema_rows = {row.schema_id: row for row in report.schema_rows}

    assert report.status == "passed"
    assert audit_scene_material_schema_report(report) == ((), ())
    assert payload["counts"]["family_count"] == 15
    assert payload["counts"]["material_family_count"] == 15
    assert payload["counts"]["ready_material_family_count"] == 15
    assert payload["counts"]["pack_count"] == 12
    assert payload["counts"]["material_pack_count"] == 10
    assert payload["counts"]["ready_material_pack_count"] == 10
    assert payload["counts"]["schema_count"] == 22
    assert payload["counts"]["referenced_schema_count"] == 21
    assert payload["counts"]["registry_only_schema_count"] == 1
    assert payload["counts"]["required_field_count"] == 41
    assert payload["counts"]["required_asset_count"] == 6
    assert report.missing_source_evidence_count == 0

    assert family_rows["thesis_cn"].status == "ready"
    assert family_rows["thesis_cn"].material_schema_ids == (
        "thesis_school_rule_context_v1",
    )
    assert family_rows["exam_teaching"].batch_modes == (
        "structured_source",
        "single",
    )
    assert "answer_sheet" in family_rows["exam_teaching"].delivery_preset_ids
    assert "exam_items_v1" in family_rows["exam_teaching"].material_schema_ids

    assert pack_rows["bidding_materials"].material_schema_ids == (
        "qualification_archive_assets_v1",
        "bid_materials_v1",
    )
    assert pack_rows["chinese_academic"].material_schema_ids == (
        "thesis_school_rule_context_v1",
    )
    assert pack_rows["quick_formatting"].status == "not_applicable"
    assert pack_rows["professional_disclosure"].material_schema_ids == (
        "finance_quote_fields_v1",
        "regulated_disclosure_materials_v1",
        "patent_document_fields_v1",
        "bilingual_terms_v1",
    )

    assert schema_rows["finance_quote_fields_v1"].batch_mode == (
        "attachment_package"
    )
    assert schema_rows["journal_materials_v1"].status == "registry_only"


def test_scene_material_schema_audit_filters_by_pack_family_and_schema():
    contract = build_scene_material_schema_audit_report(
        family_id="contract_delivery",
        project_root=ROOT,
    )
    bidding = build_scene_material_schema_audit_report(
        pack_id="bidding_materials",
        project_root=ROOT,
    )
    finance = build_scene_material_schema_audit_report(
        schema_id="finance_quote_fields_v1",
        project_root=ROOT,
    )

    assert [row.family_id for row in contract.family_rows] == ["contract_delivery"]
    assert [row.pack_id for row in contract.pack_rows] == ["contract_delivery"]
    assert [row.schema_id for row in contract.schema_rows] == [
        "contract_parties_v1",
        "signature_assets_v1",
    ]

    assert [row.family_id for row in bidding.family_rows] == [
        "qualification_archive_packages"
    ]
    assert [row.pack_id for row in bidding.pack_rows] == ["bidding_materials"]
    assert [row.schema_id for row in bidding.schema_rows] == [
        "bid_materials_v1",
        "qualification_archive_assets_v1",
    ]

    assert [row.family_id for row in finance.family_rows] == [
        "finance_quote_documents"
    ]
    assert [row.pack_id for row in finance.pack_rows] == [
        "professional_disclosure"
    ]
    assert [row.schema_id for row in finance.schema_rows] == [
        "finance_quote_fields_v1"
    ]


def test_scene_material_schema_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_material_schema_audit.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_material_schema_audit.py",
            "--format",
            "json",
            "--family",
            "contract_delivery",
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
    assert payload["counts"]["family_count"] == 1
    assert payload["counts"]["pack_count"] == 1
    assert payload["family_rows"][0]["family_id"] == "contract_delivery"


def test_scene_material_schema_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_material_schema_audit.py",
            "--format",
            "markdown",
            "--schema",
            "finance_quote_fields_v1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene MaterialSchema Audit" in result.stdout
    assert "| Family | Status | Packs | Schemas | Fields | Assets | Batch | Evidence |" in (
        result.stdout
    )
    assert "finance_quote_documents" in result.stdout
    assert "finance_quote_fields_v1" in result.stdout
    assert "attachment_package" in result.stdout


def test_release_gate_includes_scene_material_schema_audit(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_material_schema_audit"]["status"] == "passed"
    assert payload["counts"]["scene_material_schema_family_count"] == 15
    assert payload["counts"]["scene_material_schema_material_family_count"] == 15
    assert (
        payload["counts"]["scene_material_schema_ready_material_family_count"]
        == 15
    )
    assert payload["counts"]["scene_material_schema_pack_count"] == 12
    assert payload["counts"]["scene_material_schema_material_pack_count"] == 10
    assert payload["counts"]["scene_material_schema_ready_material_pack_count"] == 10
    assert payload["counts"]["scene_material_schema_schema_count"] == 22
    assert payload["counts"]["scene_material_schema_referenced_schema_count"] == 21
    assert payload["counts"]["scene_material_schema_registry_only_schema_count"] == 1
    assert payload["counts"]["scene_material_schema_required_field_count"] == 41
    assert payload["counts"]["scene_material_schema_required_asset_count"] == 6
    assert payload["counts"]["scene_material_schema_issue_count"] == 0
    assert (
        payload["counts"]["scene_material_schema_missing_source_evidence_count"]
        == 0
    )
    assert payload["scene_material_schema_audit"]["status"] == "passed"
