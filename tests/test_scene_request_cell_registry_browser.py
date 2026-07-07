import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_high_frequency_request_samples import (  # noqa: E402
    list_high_frequency_request_samples,
)
from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    build_scene_request_cell_registry_browser,
)


def test_scene_request_cell_registry_browser_exposes_global_evidence():
    browser = build_scene_request_cell_registry_browser()
    items = {item.sample_id: item for item in browser.items}
    coverage_counts = dict(browser.coverage_level_counts)

    assert browser.total_count == len(list_high_frequency_request_samples())
    assert browser.visible_count == browser.total_count
    assert coverage_counts == {
        "direct_family_fixture": 31,
        "manual_boundary_fixture": 12,
        "ambiguous_fixture_set": 7,
        "negative_control": 3,
    }
    assert "contract_delivery" in browser.pack_options
    assert "professional_disclosure" in browser.pack_options
    assert "hr_batch_documents" in browser.family_options
    assert "product_sales_documents" in browser.family_options

    contract = items["contract_signing_consistency"]
    contract_legal = items["ambiguous_contract_legal_review"]
    journal_response = items["english_journal_response_letter"]
    unknown = items["unknown_stays_unmatched"]
    ppt = items["negative_ppt_poster_design"]

    assert contract.coverage_label == "直接证据"
    assert contract.status_label == "有证据"
    assert "contract_delivery_revisions" in contract.fixture_ids
    assert contract_legal.coverage_level == "ambiguous_fixture_set"
    assert contract_legal.expected_pack_ids == (
        "contract_delivery",
        "professional_disclosure",
    )
    assert contract_legal.manual_gate_ids == (
        "professional_disclosure_review_gate",
    )
    assert journal_response.coverage_level == "manual_boundary_fixture"
    assert journal_response.manual_gate_ids == ("journal_publisher_rule_review_gate",)
    assert unknown.coverage_level == "negative_control"
    assert unknown.status_label == "负例"
    assert unknown.fixture_ids == ()
    assert ppt.coverage_level == "negative_control"
    assert ppt.expected_pack_ids == ()


def test_scene_request_cell_registry_browser_filters_pack_family_coverage_and_query():
    professional_manual = build_scene_request_cell_registry_browser(
        pack_id="professional_disclosure",
        coverage_level="manual_boundary_fixture",
    )
    hr_family = build_scene_request_cell_registry_browser(
        family_id="hr_batch_documents",
    )
    unknown_query = build_scene_request_cell_registry_browser(
        query="unknown_stays_unmatched",
    )

    assert professional_manual.visible_count == 6
    assert {item.coverage_level for item in professional_manual.items} == {
        "manual_boundary_fixture",
    }
    assert all(
        "professional_disclosure" in item.expected_pack_ids
        for item in professional_manual.items
    )
    assert {item.sample_id for item in hr_family.items} >= {
        "batch_hr_offer",
        "batch_employee_certificate",
        "ambiguous_batch_notice",
    }
    assert unknown_query.visible_count == 1
    assert unknown_query.items[0].sample_id == "unknown_stays_unmatched"


def test_scene_request_cell_registry_export_script_writes_json(tmp_path):
    output_path = tmp_path / "contract_request_cells.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_request_cell_registry.py",
            "--format",
            "json",
            "--pack",
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
    assert payload["total_count"] == len(list_high_frequency_request_samples())
    assert payload["visible_count"] == 4
    assert {item["sample_id"] for item in payload["items"]} == {
        "contract_signing_consistency",
        "contract_review_revisions",
        "contract_signature_package_fields",
        "ambiguous_contract_legal_review",
    }


def test_scene_request_cell_registry_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_request_cell_registry.py",
            "--format",
            "markdown",
            "--coverage-level",
            "negative_control",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Request-Cell Registry" in result.stdout
    assert "| Sample | Coverage | Status | Packs | Families | Fixtures | Gates | Request |" in (
        result.stdout
    )
    assert "unknown_stays_unmatched" in result.stdout
    assert "negative_ppt_poster_design" in result.stdout
    assert "negative_webpage_publish" in result.stdout
    assert "负例" in result.stdout
