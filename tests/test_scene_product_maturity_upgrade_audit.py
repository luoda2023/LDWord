import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_product_maturity_upgrade_audit import (  # noqa: E402
    PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS,
    audit_scene_product_maturity_upgrade_report,
    build_scene_product_maturity_upgrade_audit_report,
)


def test_product_maturity_upgrade_audit_maps_every_subject_to_l5_blockers():
    report = build_scene_product_maturity_upgrade_audit_report(project_root=ROOT)
    rows = {f"{row.subject_type}:{row.subject_id}": row for row in report.rows}
    payload = report.to_payload()
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_product_maturity_upgrade_report(report) == ((), ())
    assert report.subject_count == 27
    assert report.pack_subject_count == 12
    assert report.family_subject_count == 15
    assert report.green_subject_count == 21
    assert report.l5_blocked_subject_count == 6
    assert report.l3_subject_count == 0
    assert report.l4_subject_count == 0
    assert report.boundary_subject_count == 6
    assert report.static_closed_not_green_count == 2
    assert report.gap_count == 6
    assert report.gap_domain_count == 3
    assert report.issue_count == 0
    assert report.warning_count == 0
    assert report.missing_source_evidence_count == 0
    assert source_status["n2_393g_plan"] == "ready"
    assert payload["counts"]["gap_domain_counts"] == [
        {"domain_id": "runtime_execution", "count": 1},
        {"domain_id": "report_artifact", "count": 1},
        {"domain_id": "boundary_gate", "count": 6},
    ]

    quick = rows["pack:quick_formatting"]
    assert quick.status == "green_l5"
    assert quick.current_readiness_level == "green_l5"
    assert quick.next_upgrade_goal == "maintain_green_l5"
    assert quick.pack_ids == ("quick_formatting",)
    assert quick.family_ids == ()
    assert quick.l5_blocker_count == 0
    assert "field-level template repair routing" in quick.evidence_surfaces
    assert "real business template fixture" in quick.evidence_surfaces
    assert quick.remaining_product_gaps == ()
    assert quick.gap_domain_ids == ()

    contract = rows["pack:contract_delivery"]
    assert contract.status == "green_l5"
    assert contract.current_readiness_level == "green_l5"
    assert contract.next_upgrade_goal == "maintain_green_l5"
    assert "field evidence UI" in contract.evidence_surfaces
    assert "pre-execution legal-boundary banner" in contract.evidence_surfaces
    assert contract.remaining_product_gaps == ()
    assert contract.gap_domain_ids == ()

    bidding = rows["pack:bidding_materials"]
    assert bidding.status == "green_l5"
    assert bidding.current_readiness_level == "green_l5"
    assert bidding.next_upgrade_goal == "maintain_green_l5"
    assert "multi-party consortium schema" in bidding.evidence_surfaces
    assert "seal-position residual checks" in bidding.evidence_surfaces
    assert bidding.remaining_product_gaps == ()
    assert bidding.gap_domain_ids == ()

    official = rows["pack:official_policy"]
    assert official.status == "green_l5"
    assert official.current_readiness_level == "green_l5"
    assert official.next_upgrade_goal == "maintain_green_l5"
    assert "official metadata schema" in official.evidence_surfaces
    assert "formal/internal/archive report depth" in official.evidence_surfaces
    assert official.remaining_product_gaps == ()
    assert official.gap_domain_ids == ()

    batch = rows["pack:batch_forms"]
    assert batch.status == "green_l5"
    assert batch.current_readiness_level == "green_l5"
    assert batch.next_upgrade_goal == "maintain_green_l5"
    assert "fixed-layout profile browser" in batch.evidence_surfaces
    assert "exam answer-sheet reuse path" in batch.evidence_surfaces
    assert "fixed-layout batch evidence UI" in batch.evidence_surfaces
    assert batch.remaining_product_gaps == ()
    assert batch.gap_domain_ids == ()

    application = rows["pack:application_reports"]
    assert application.status == "green_l5"
    assert application.current_readiness_level == "green_l5"
    assert application.next_upgrade_goal == "maintain_green_l5"
    assert "project rule-source governance" in application.evidence_surfaces
    assert "submission-system boundary UI" in application.evidence_surfaces
    assert "product asset consistency UI" in application.evidence_surfaces
    assert "quote/body disambiguation fixtures" in application.evidence_surfaces
    assert "application/report evidence UI" in application.evidence_surfaces
    assert application.remaining_product_gaps == ()
    assert application.gap_domain_ids == ()

    journal = rows["pack:english_journal"]
    assert journal.status == "green_l5"
    assert journal.current_readiness_level == "green_l5"
    assert journal.next_upgrade_goal == "maintain_green_l5"
    assert "reviewed journal profile updates" in journal.evidence_surfaces
    assert "submission artifact manifest" in journal.evidence_surfaces
    assert "journal submission evidence UI" in journal.evidence_surfaces
    assert "publisher manual gate" in journal.evidence_surfaces
    assert journal.remaining_product_gaps == ()
    assert journal.gap_domain_ids == ()

    technical = rows["pack:technical_long_docs"]
    assert technical.status == "green_l5"
    assert technical.current_readiness_level == "green_l5"
    assert technical.next_upgrade_goal == "maintain_green_l5"
    assert "index/appendix handling" in technical.evidence_surfaces
    assert "multi-file merge boundary" in technical.evidence_surfaces
    assert technical.remaining_product_gaps == ()
    assert technical.gap_domain_ids == ()

    chinese = rows["pack:chinese_academic"]
    assert chinese.status == "green_l5"
    assert chinese.current_readiness_level == "green_l5"
    assert chinese.next_upgrade_goal == "maintain_green_l5"
    assert "school rule source governance UI" in chinese.evidence_surfaces
    assert "section classifier confirmation" in chinese.evidence_surfaces
    assert chinese.remaining_product_gaps == ()
    assert chinese.gap_domain_ids == ()

    qualification = rows["family:qualification_archive_packages"]
    assert qualification.status == "green_l5"
    assert qualification.current_readiness_level == "green_l5"
    assert qualification.next_upgrade_goal == "maintain_green_l5"
    assert "expiry metadata governance" in qualification.evidence_surfaces
    assert "multi-party archive depth" in qualification.evidence_surfaces
    assert qualification.remaining_product_gaps == ()
    assert qualification.gap_domain_ids == ()

    meeting = rows["family:meeting_policy_documents"]
    assert meeting.status == "green_l5"
    assert meeting.current_readiness_level == "green_l5"
    assert meeting.next_upgrade_goal == "maintain_green_l5"
    assert "official metadata schema" in meeting.evidence_surfaces
    assert "formal/internal/archive report depth" in meeting.evidence_surfaces
    assert meeting.remaining_product_gaps == ()
    assert meeting.gap_domain_ids == ()

    long_doc = rows["family:long_document_publishing"]
    assert long_doc.status == "green_l5"
    assert long_doc.current_readiness_level == "green_l5"
    assert long_doc.next_upgrade_goal == "maintain_green_l5"
    assert "index/appendix handling" in long_doc.evidence_surfaces
    assert "multi-file import boundary" in long_doc.evidence_surfaces
    assert long_doc.remaining_product_gaps == ()
    assert long_doc.gap_domain_ids == ()

    thesis = rows["family:thesis_cn"]
    assert thesis.status == "green_l5"
    assert thesis.current_readiness_level == "green_l5"
    assert thesis.next_upgrade_goal == "maintain_green_l5"
    assert "thesis school rule context schema" in thesis.evidence_surfaces
    assert "section classifier confirmation" in thesis.evidence_surfaces
    assert thesis.remaining_product_gaps == ()
    assert thesis.gap_domain_ids == ()

    hr_batch = rows["family:hr_batch_documents"]
    assert hr_batch.status == "green_l5"
    assert hr_batch.current_readiness_level == "green_l5"
    assert hr_batch.next_upgrade_goal == "maintain_green_l5"
    assert "profile-specific fixed-layout previews" in hr_batch.evidence_surfaces
    assert "profile preview material manifest" in hr_batch.evidence_surfaces
    assert hr_batch.remaining_product_gaps == ()
    assert hr_batch.gap_domain_ids == ()

    form_batch = rows["family:form_batch_documents"]
    assert form_batch.status == "green_l5"
    assert form_batch.current_readiness_level == "green_l5"
    assert form_batch.next_upgrade_goal == "maintain_green_l5"
    assert "profile browser" in form_batch.evidence_surfaces
    assert "answer-sheet reuse path" in form_batch.evidence_surfaces
    assert "scene-owned fixed row-height policy" in form_batch.evidence_surfaces
    assert form_batch.remaining_product_gaps == ()
    assert form_batch.gap_domain_ids == ()

    project_application = rows["family:project_application"]
    assert project_application.status == "green_l5"
    assert project_application.current_readiness_level == "green_l5"
    assert project_application.next_upgrade_goal == "maintain_green_l5"
    assert "external rule source governance" in project_application.evidence_surfaces
    assert "submission system boundary UI" in project_application.evidence_surfaces
    assert project_application.remaining_product_gaps == ()
    assert project_application.gap_domain_ids == ()

    product_sales = rows["family:product_sales_documents"]
    assert product_sales.status == "green_l5"
    assert product_sales.current_readiness_level == "green_l5"
    assert product_sales.next_upgrade_goal == "maintain_green_l5"
    assert "quote/body disambiguation fixtures" in product_sales.evidence_surfaces
    assert "asset consistency UI" in product_sales.evidence_surfaces
    assert "asset consistency report" in product_sales.evidence_surfaces
    assert product_sales.remaining_product_gaps == ()
    assert product_sales.gap_domain_ids == ()

    journal_family = rows["family:journal_en"]
    assert journal_family.status == "green_l5"
    assert journal_family.current_readiness_level == "green_l5"
    assert journal_family.next_upgrade_goal == "maintain_green_l5"
    assert "reviewed journal source updates" in journal_family.evidence_surfaces
    assert "submission artifact manifest" in journal_family.evidence_surfaces
    assert "journal submission evidence UI" in journal_family.evidence_surfaces
    assert journal_family.remaining_product_gaps == ()
    assert journal_family.gap_domain_ids == ()

    professional = rows["pack:professional_disclosure"]
    assert professional.status == "boundary_guarded"
    assert professional.next_upgrade_goal == "boundary_guarded_orange_l4"
    assert professional.remaining_product_gaps == ("real plugin ecosystem",)
    assert "boundary capability matrix" in professional.evidence_surfaces
    assert "professional family report depth" in professional.evidence_surfaces
    assert "boundary_gate" in professional.gap_domain_ids

    import_boundary = rows["pack:import_ai_boundary"]
    assert import_boundary.status == "boundary_guarded"
    assert import_boundary.remaining_product_gaps == (
        "real OCR/PDF/LaTeX plugin integration",
    )
    assert "confidence artifact manifest" in import_boundary.evidence_surfaces
    assert "boundary capability matrix" in import_boundary.evidence_surfaces

    finance = rows["family:finance_quote_documents"]
    assert finance.remaining_product_gaps == ("finance plugin handoff",)
    assert "spreadsheet table mapping manifest" in finance.evidence_surfaces
    assert "finance boundary capability matrix" in finance.evidence_surfaces

    patent = rows["family:ip_patent_documents"]
    assert patent.remaining_product_gaps == ("IP plugin handoff",)
    assert "claim-quality boundary UI" in patent.evidence_surfaces

    bilingual = rows["family:bilingual_translation_documents"]
    assert bilingual.remaining_product_gaps == (
        "translation-quality plugin handoff",
    )
    assert "termbase UI" in bilingual.evidence_surfaces

    disclosure = rows["family:regulated_disclosure_documents"]
    assert disclosure.remaining_product_gaps == (
        "external assurance review handoff",
    )
    assert "regulated rule source governance" in disclosure.evidence_surfaces
    assert "assurance boundary UI" in disclosure.evidence_surfaces

    exam = rows["pack:exam_education"]
    assert exam.status == "green_l5"
    assert exam.current_readiness_level == "green_l5"
    assert exam.next_upgrade_goal == "maintain_green_l5"
    assert "runtime Word versions" in exam.evidence_surfaces
    assert "Markdown preview report" in exam.evidence_surfaces
    assert "fixed-layout answer-sheet runtime" in exam.evidence_surfaces
    assert "question asset runtime" in exam.evidence_surfaces
    assert "question asset replacement UI bridge" in exam.evidence_surfaces
    assert "question asset per-question runtime mapping" in exam.evidence_surfaces
    assert "question asset structured asset-items import bridge" in exam.evidence_surfaces
    assert "question asset frontstage mapping summary" in exam.evidence_surfaces
    assert "question asset frontstage detail table" in exam.evidence_surfaces
    assert "question asset frontstage row preview" in exam.evidence_surfaces
    assert "question asset frontstage row replacement" in exam.evidence_surfaces
    assert "question asset missing-file row repair" in exam.evidence_surfaces
    assert "question asset issue queue row routing" in exam.evidence_surfaces
    assert "question asset remote id/source bridge" in exam.evidence_surfaces
    assert "question asset remote cache path bridge" in exam.evidence_surfaces
    assert "question asset remote cache miss repair bridge" in exam.evidence_surfaces
    assert "question asset remote no-cache repair bridge" in exam.evidence_surfaces
    assert "question asset remote url download cache bridge" in exam.evidence_surfaces
    assert (
        "question asset remote asset-url metadata download bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote asset-id resolver bridge" in exam.evidence_surfaces
    assert "question asset remote authenticated download bridge" in exam.evidence_surfaces
    assert "question asset remote authorization UI bridge" in exam.evidence_surfaces
    assert (
        "question asset remote permission failure diagnostics bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote cache refresh bridge" in exam.evidence_surfaces
    assert (
        "question asset remote cache expiry refresh bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote conditional revalidation bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote cache index manifest bridge" in exam.evidence_surfaces
    assert "question asset remote cache-hit index bridge" in exam.evidence_surfaces
    assert "question asset remote cache index summary bridge" in exam.evidence_surfaces
    assert (
        "question asset remote cache hit-rate summary bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate trend history bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate trend history UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate archive trend panel UI bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote shared cache index bridge" in exam.evidence_surfaces
    assert (
        "question asset remote shared cache directory summary bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote shared cache directory browser UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote shared cache index drilldown UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote shared cache directory open UI bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote cache invalidation bridge" in exam.evidence_surfaces
    assert (
        "question asset remote cache batch invalidation bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote filtered batch cache invalidation bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cross-directory cache cleanup bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup dry-run bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup history bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup history UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup confirmation UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup confirmed execution bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup task list UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup archive task center UI bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote download retry bridge" in exam.evidence_surfaces
    assert "question asset remote cache package bridge" in exam.evidence_surfaces
    assert "question asset remote cache package report bridge" in exam.evidence_surfaces
    assert (
        "question asset remote cache package report drilldown bridge"
        in exam.evidence_surfaces
    )
    assert "question asset remote content metadata bridge" in exam.evidence_surfaces
    assert (
        "question asset remote thumbnail preview UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote thumbnail-url preview UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote full-preview URL UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote full-preview viewer UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote full-preview zoom UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote full-preview compare UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote full-preview multi-compare UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset remote full-preview manual annotation UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset manual comparison issue queue bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset batch comparison matrix report bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison region annotation bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue candidate bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue artifact bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue issue action bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue confirmation plan bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch confirmation preflight bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch confirmation freeze bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply dry-run guard bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply execution plan bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply Word media write bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply execution audit bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply audit rollback bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction manifest bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction manifest artifact bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction manifest report bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task summary bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task issue-action bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task report-drilldown action bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task report-drilldown audit bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue frontstage apply bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue replacement audit bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue rollback bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue conflict guard bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue conflict resolution bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue conflict selection action bridge"
        in exam.evidence_surfaces
    )
    assert "question asset figure group ordering bridge" in exam.evidence_surfaces
    assert "question asset flat figure group import bridge" in exam.evidence_surfaces
    assert "question asset filename mismatch preflight bridge" in exam.evidence_surfaces
    assert (
        "question asset per-question asset library index UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset per-question asset library metadata editing UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset per-question asset library metadata issue UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset per-question asset library version history UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset per-question asset library version rollback UI bridge"
        in exam.evidence_surfaces
    )
    assert (
        "question asset per-question asset library local version consistency UI bridge"
        in exam.evidence_surfaces
    )
    assert "question asset altText editing UI bridge" in exam.evidence_surfaces
    assert "question asset altText runtime/report" in exam.evidence_surfaces
    assert exam.remaining_product_gaps == ()
    assert exam.gap_domain_ids == ()

    exam_family = rows["family:exam_teaching"]
    assert "question asset runtime" in exam_family.evidence_surfaces
    assert "question asset replacement UI bridge" in exam_family.evidence_surfaces
    assert "question asset per-question runtime mapping" in exam_family.evidence_surfaces
    assert "question asset structured asset-items import bridge" in exam_family.evidence_surfaces
    assert "question asset frontstage mapping summary" in exam_family.evidence_surfaces
    assert "question asset frontstage detail table" in exam_family.evidence_surfaces
    assert "question asset frontstage row preview" in exam_family.evidence_surfaces
    assert "question asset frontstage row replacement" in exam_family.evidence_surfaces
    assert "question asset missing-file row repair" in exam_family.evidence_surfaces
    assert "question asset issue queue row routing" in exam_family.evidence_surfaces
    assert "question asset remote id/source bridge" in exam_family.evidence_surfaces
    assert "question asset remote cache path bridge" in exam_family.evidence_surfaces
    assert (
        "question asset remote cache miss repair bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote no-cache repair bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote url download cache bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote asset-url metadata download bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote asset-id resolver bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote authenticated download bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote authorization UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote permission failure diagnostics bridge"
        in exam_family.evidence_surfaces
    )
    assert "question asset remote cache refresh bridge" in exam_family.evidence_surfaces
    assert (
        "question asset remote cache expiry refresh bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote conditional revalidation bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache index manifest bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache-hit index bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache index summary bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate summary bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate trend history bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate trend history UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache hit-rate archive trend panel UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote shared cache index bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote shared cache directory summary bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote shared cache directory browser UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote shared cache index drilldown UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote shared cache directory open UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache invalidation bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache batch invalidation bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote filtered batch cache invalidation bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cross-directory cache cleanup bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup dry-run bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup history bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup history UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup confirmation UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup confirmed execution bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup task list UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache cleanup archive task center UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote download retry bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache package bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache package report bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote cache package report drilldown bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote content metadata bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote thumbnail preview UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote thumbnail-url preview UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote full-preview URL UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote full-preview viewer UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote full-preview zoom UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote full-preview compare UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote full-preview multi-compare UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset remote full-preview manual annotation UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset manual comparison issue queue bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset batch comparison matrix report bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison region annotation bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue candidate bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue artifact bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue issue action bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue confirmation plan bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch confirmation preflight bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch confirmation freeze bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply dry-run guard bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply execution plan bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply Word media write bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply execution audit bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply audit rollback bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction manifest bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction manifest artifact bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction manifest report bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task summary bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task issue-action bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task report-drilldown action bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue batch apply transaction task report-drilldown audit bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue frontstage apply bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue replacement audit bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue rollback bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue conflict guard bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue conflict resolution bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset comparison repair queue conflict selection action bridge"
        in exam_family.evidence_surfaces
    )
    assert "question asset figure group ordering bridge" in exam_family.evidence_surfaces
    assert "question asset flat figure group import bridge" in exam_family.evidence_surfaces
    assert (
        "question asset filename mismatch preflight bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset per-question asset library index UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset per-question asset library metadata editing UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset per-question asset library metadata issue UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset per-question asset library version history UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset per-question asset library version rollback UI bridge"
        in exam_family.evidence_surfaces
    )
    assert (
        "question asset per-question asset library local version consistency UI bridge"
        in exam_family.evidence_surfaces
    )
    assert "question asset altText editing UI bridge" in exam_family.evidence_surfaces
    assert "question asset altText runtime/report" in exam_family.evidence_surfaces
    assert exam_family.remaining_product_gaps == ()
    assert exam_family.gap_domain_ids == ()

    project = rows["family:project_application"]
    assert project.status == "green_l5"
    assert project.current_readiness_level == "green_l5"
    assert "journey runtime report" in project.evidence_surfaces
    assert "artifact drilldown bridge" in project.evidence_surfaces
    assert "submission system boundary UI" in project.evidence_surfaces
    assert project.remaining_product_gaps == ()
    assert project.gap_domain_ids == ()

    product = rows["family:product_sales_documents"]
    assert product.status == "green_l5"
    assert product.current_readiness_level == "green_l5"
    assert "journey runtime report" in product.evidence_surfaces
    assert "artifact drilldown bridge" in product.evidence_surfaces
    assert "asset consistency UI" in product.evidence_surfaces
    assert product.remaining_product_gaps == ()
    assert product.gap_domain_ids == ()

    contract_family = rows["family:contract_delivery"]
    assert contract_family.status == "green_l5"
    assert contract_family.current_readiness_level == "green_l5"
    assert contract_family.next_upgrade_goal == "maintain_green_l5"
    assert contract_family.pack_ids == ("contract_delivery",)
    assert contract_family.family_ids == ("contract_delivery",)
    assert "field evidence UI" in contract_family.evidence_surfaces
    assert contract_family.remaining_product_gaps == ()
    assert contract_family.gap_domain_ids == ()


def test_product_maturity_upgrade_filters_by_type_readiness_domain_and_query():
    pack_report = build_scene_product_maturity_upgrade_audit_report(
        subject_type="pack",
        project_root=ROOT,
    )
    boundary_report = build_scene_product_maturity_upgrade_audit_report(
        readiness_level="blue_boundary",
        project_root=ROOT,
    )
    boundary_domain_report = build_scene_product_maturity_upgrade_audit_report(
        domain_id="boundary_gate",
        project_root=ROOT,
    )
    answer_sheet_report = build_scene_product_maturity_upgrade_audit_report(
        query="answer-sheet",
        project_root=ROOT,
    )

    assert pack_report.subject_count == 12
    assert boundary_report.subject_count == 6
    assert boundary_domain_report.subject_count == 6
    assert {row.subject_id for row in answer_sheet_report.rows} == {
        "exam_education",
        "batch_forms",
        "exam_teaching",
        "form_batch_documents",
    }


def test_product_maturity_upgrade_export_script_writes_json(tmp_path):
    output_path = tmp_path / "scene_product_maturity_upgrade.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_product_maturity_upgrade_audit.py",
            "--format",
            "json",
            "--readiness",
            "blue_boundary",
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
    assert payload["counts"]["subject_count"] == 6
    assert payload["counts"]["boundary_subject_count"] == 6
    assert payload["rows"][0]["current_readiness_level"] == "blue_boundary"


def test_product_maturity_upgrade_export_script_prints_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_product_maturity_upgrade_audit.py",
            "--format",
            "markdown",
            "--domain",
            "boundary_gate",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Product Maturity Upgrade Audit" in result.stdout
    assert "| Subject | Type | Current | Next | Status | Packs | Families |" in (
        result.stdout
    )
    assert "boundary_gate" in result.stdout
    assert "scene_product_readiness" in result.stdout




def test_product_maturity_upgrade_audit_excludes_deleted_enterprise_asset_evidence():
    report = build_scene_product_maturity_upgrade_audit_report(project_root=ROOT)
    rows = {f"{row.subject_type}:{row.subject_id}": row for row in report.rows}
    deleted_fragments = tuple(
        " ".join(parts)
        for parts in (
            ("master", "registry", "sync"),
            ("master", "subscription"),
            ("subscription", "drift"),
            ("failure", "recovery"),
            ("persistent", "worker"),
            ("durable", "worker"),
            ("file", "recovery", "center"),
            ("historical", "docx"),
            ("non-question", "asset", "family"),
            ("remote", "writeback"),
            ("cross", "system", "writeback"),
            ("enterprise", "auth"),
            ("signed", "url"),
            ("external", "permission"),
        )
    )

    for key in ("pack:batch_forms", "family:exam_teaching"):
        row = rows[key]
        evidence_text = "\n".join(row.evidence_surfaces).casefold()
        rationale_text = row.rationale.casefold()
        for fragment in deleted_fragments:
            assert fragment not in evidence_text, f"{key}:{fragment}"
            assert fragment not in rationale_text, f"{key}:{fragment}"
