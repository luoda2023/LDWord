from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent

from src.config.scene_rule_source_governance import (
    REQUIRED_RULE_SOURCE_PACK_IDS,
    audit_scene_rule_source_governance,
    build_scene_rule_source_summary,
    get_scene_rule_source,
    list_scene_rule_sources,
    scene_rule_source_payload_for_pack,
    scene_rule_sources_for_count_profile,
    scene_rule_sources_for_family,
    scene_rule_sources_for_pack,
)


def test_scene_rule_source_registry_covers_n2_132_required_packs():
    assert audit_scene_rule_source_governance(ROOT) == ()

    sources = {source.source_id: source for source in list_scene_rule_sources()}
    assert {
        "school_thesis_rule_defaults",
        "journal_submission_reviewed_generic_rules",
        "project_application_rule_defaults",
        "procurement_bidding_rule_defaults",
        "professional_disclosure_boundary_rules",
    } <= set(sources)
    assert set(REQUIRED_RULE_SOURCE_PACK_IDS) <= {
        source.pack_id for source in list_scene_rule_sources()
    }
    for source in sources.values():
        assert source.version == "2026-06-18"
        assert source.source_references
        assert source.report_surfaces
        assert source.boundary_notes


def test_school_and_application_rule_sources_remain_manual_until_reviewed_rules_exist():
    school = get_scene_rule_source("school_thesis_rule_defaults")
    application = get_scene_rule_source("project_application_rule_defaults")

    assert school.pack_id == "chinese_academic"
    assert school.review_status == "manual_required"
    assert school.manual_confirmation_required is True
    assert {"school_thesis", "thesis_cn"} <= set(school.count_profile_ids)
    assert any("not authoritative" in note for note in school.exclude_scope_summary)
    assert any("named-school" in note for note in school.boundary_notes)

    assert application.pack_id == "application_reports"
    assert application.review_status == "manual_required"
    assert application.manual_confirmation_required is True
    assert application.family_ids == ("project_application",)
    assert "application_word_limits" in application.count_profile_ids
    assert "project_application_materials_v1" in application.material_schema_ids
    assert any("submission-system" in item for item in application.exclude_scope_summary)


def test_journal_rule_source_reuses_reviewed_registry_but_keeps_generic_boundary():
    journal = get_scene_rule_source("journal_submission_reviewed_generic_rules")

    assert journal.pack_id == "english_journal"
    assert journal.review_status == "reviewed_generic"
    assert journal.is_reviewed is True
    assert journal.is_strictly_executable is False
    assert journal.manual_confirmation_required is True
    assert journal.upstream_source_ids == ("journal_en_default_rules",)
    assert "journal_words" in journal.count_profile_ids
    assert scene_rule_sources_for_count_profile("journal_words") == (journal,)
    assert any("Publisher-specific limits" in item for item in journal.exclude_scope_summary)

    summary = build_scene_rule_source_summary(journal)
    assert "review=reviewed_generic" in summary
    assert "manual=True" in summary


def test_procurement_and_professional_sources_keep_boundaries_separate():
    bidding = get_scene_rule_source("procurement_bidding_rule_defaults")
    professional = get_scene_rule_source("professional_disclosure_boundary_rules")

    assert bidding.pack_id == "bidding_materials"
    assert bidding.family_ids == ("qualification_archive_packages",)
    assert {"bid_package", "attachment_inventory"} <= set(bidding.count_profile_ids)
    assert {"bid_materials_v1", "qualification_archive_assets_v1"} <= set(
        bidding.material_schema_ids
    )
    assert bidding.review_status == "manual_required"
    assert any("Procurement platform-specific" in item for item in bidding.exclude_scope_summary)

    assert professional.pack_id == "professional_disclosure"
    assert professional.review_status == "plugin_required"
    assert professional.plugin_gate_id == "professional_disclosure_review_gate"
    assert professional.manual_confirmation_required is True
    assert {
        "regulated_disclosure_documents",
        "finance_quote_documents",
        "ip_patent_documents",
        "bilingual_translation_documents",
    } <= set(professional.family_ids)
    assert "disclosure_section_inventory" in professional.count_profile_ids
    assert any("Core does not decide" in item for item in professional.exclude_scope_summary)


def test_rule_source_lookup_and_payloads_are_pack_family_count_friendly():
    assert scene_rule_sources_for_pack("application_reports") == (
        get_scene_rule_source("project_application_rule_defaults"),
    )
    assert scene_rule_sources_for_family("regulated_disclosure_documents") == (
        get_scene_rule_source("professional_disclosure_boundary_rules"),
    )
    assert scene_rule_sources_for_count_profile("attachment_inventory") == (
        get_scene_rule_source("project_application_rule_defaults"),
        get_scene_rule_source("procurement_bidding_rule_defaults"),
    )

    payload = scene_rule_source_payload_for_pack("professional_disclosure")

    assert payload["pack_id"] == "professional_disclosure"
    assert payload["rule_source_count"] == 1
    assert payload["manual_confirmation_required"] is True
    assert payload["plugin_required"] is True
    source_payload = payload["sources"][0]
    assert source_payload["source_id"] == "professional_disclosure_boundary_rules"
    assert source_payload["plugin_gate_id"] == "professional_disclosure_review_gate"
    assert source_payload["strictly_executable"] is False


def test_scene_rule_source_lookup_failures_are_explicit():
    with pytest.raises(KeyError):
        get_scene_rule_source("missing_rule_source")
