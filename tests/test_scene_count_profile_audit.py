import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_count_profile_audit import (  # noqa: E402
    COUNT_PROFILE_REPORT_SURFACES,
    COUNT_PROFILE_RUNTIME_CONSUMERS,
    audit_scene_count_profile_report,
    build_scene_count_profile_audit_report,
)


def test_scene_count_profile_audit_links_profiles_families_packs_and_reports():
    report = build_scene_count_profile_audit_report(project_root=ROOT)
    profiles = {row.profile_id: row for row in report.profile_rows}
    families = {row.family_id: row for row in report.family_rows}
    packs = {row.pack_id: row for row in report.pack_rows}

    assert report.status == "passed"
    assert audit_scene_count_profile_report(report) == ((), report.warnings)
    assert report.profile_count == 20
    assert report.referenced_profile_count == 17
    assert report.rule_source_profile_count == 11
    assert report.registry_only_profile_count == 2
    assert report.rule_source_only_profile_count == 1
    assert report.section_limit_profile_count == 1
    assert report.unique_scope_count == 19
    assert report.unique_primary_metric_count == 18
    assert report.family_count == 15
    assert report.ready_family_count == 14
    assert report.boundary_family_count == 1
    assert report.accounted_family_count == 15
    assert report.pack_count == 12
    assert report.count_profile_pack_count == 10
    assert report.ready_count_profile_pack_count == 10
    assert report.runtime_consumer_count == len(COUNT_PROFILE_RUNTIME_CONSUMERS)
    assert report.report_surface_count == len(COUNT_PROFILE_REPORT_SURFACES)
    assert report.issue_count == 0
    assert report.warning_count == 2
    assert report.missing_source_evidence_count == 0

    assert profiles["basic"].status == "registry_only"
    assert profiles["word_xml_full"].status == "registry_only"
    assert profiles["bid_package"].status == "rule_source_only"
    assert profiles["bid_package"].rule_source_ids == (
        "procurement_bidding_rule_defaults",
    )

    journal = families["journal_en"]
    assert journal.status == "ready"
    assert journal.count_profile_ids == ("journal_words", "journal_display_items")
    assert journal.executable_default_count_profile_id == "journal_words"
    assert journal.executable_default_in_declared_profiles is True
    assert "english_words" in journal.primary_metrics
    assert journal.rule_source_ids == ("journal_submission_reviewed_generic_rules",)
    assert journal.report_surfaces == COUNT_PROFILE_REPORT_SURFACES
    assert journal.runtime_consumers == COUNT_PROFILE_RUNTIME_CONSUMERS

    patent = families["ip_patent_documents"]
    assert patent.status == "boundary"
    assert patent.plugin_boundary_only is True
    assert patent.count_profile_ids == ("patent_section_inventory",)
    assert patent.executable_default_count_profile_id == ""

    application = packs["application_reports"]
    assert application.status == "ready"
    assert application.count_profile_ids == (
        "application_word_limits",
        "attachment_inventory",
        "product_asset_inventory",
    )
    assert application.executable_default_count_profile_ids == (
        "application_word_limits",
        "product_asset_inventory",
    )
    assert application.rule_source_ids == ("project_application_rule_defaults",)

    assert packs["quick_formatting"].status == "not_applicable"
    assert packs["import_ai_boundary"].status == "not_applicable"


def test_scene_count_profile_audit_filters_by_profile_family_and_pack():
    journal = build_scene_count_profile_audit_report(
        family_id="journal_en",
        project_root=ROOT,
    )
    application = build_scene_count_profile_audit_report(
        pack_id="application_reports",
        project_root=ROOT,
    )
    attachment = build_scene_count_profile_audit_report(
        profile_id="attachment_inventory",
        project_root=ROOT,
    )
    bid_package = build_scene_count_profile_audit_report(
        profile_id="bid_package",
        project_root=ROOT,
    )

    assert [row.profile_id for row in journal.profile_rows] == [
        "journal_words",
        "journal_display_items",
    ]
    assert [row.family_id for row in journal.family_rows] == ["journal_en"]
    assert [row.pack_id for row in journal.pack_rows] == ["english_journal"]

    assert [row.family_id for row in application.family_rows] == [
        "project_application",
        "product_sales_documents",
    ]
    assert [row.profile_id for row in application.profile_rows] == [
        "application_word_limits",
        "attachment_inventory",
        "product_asset_inventory",
    ]

    assert [row.family_id for row in attachment.family_rows] == [
        "project_application",
        "qualification_archive_packages",
        "regulated_disclosure_documents",
    ]
    assert [row.pack_id for row in attachment.pack_rows] == [
        "bidding_materials",
        "application_reports",
        "professional_disclosure",
    ]

    assert bid_package.profile_rows[0].status == "rule_source_only"
    assert bid_package.family_rows == ()
    assert bid_package.pack_rows == ()


def test_scene_count_profile_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_count_profile.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_count_profile_audit.py",
            "--format",
            "json",
            "--family",
            "journal_en",
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
    assert payload["family_rows"][0]["family_id"] == "journal_en"
    assert payload["profile_rows"][0]["profile_id"] == "journal_words"


def test_scene_count_profile_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_count_profile_audit.py",
            "--format",
            "markdown",
            "--profile",
            "attachment_inventory",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene CountProfile Audit" in result.stdout
    assert "| Family | Status | Packs | Profiles | Default | Scopes |" in result.stdout
    assert "attachment_inventory" in result.stdout
    assert "project_application" in result.stdout
    assert "procurement_bidding_rule_defaults" in result.stdout
