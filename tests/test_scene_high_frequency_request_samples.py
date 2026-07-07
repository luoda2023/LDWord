import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_coverage_manifest import list_scene_coverage_packs
from src.config.scene_family_registry import list_planned_scene_families
from src.config.scene_high_frequency_request_samples import (
    MIN_HIGH_FREQUENCY_REQUEST_SAMPLES,
    audit_high_frequency_request_samples,
    list_high_frequency_request_samples,
    samples_for_pack,
)
from src.config.scene_natural_request_router import route_natural_scene_request
from src.config.scene_product_readiness import (
    audit_scene_product_readiness,
    list_scene_product_readiness_specs,
    product_readiness_for,
    readiness_summary,
    static_closed_but_not_green_specs,
)


def test_high_frequency_request_sample_registry_is_auditable():
    samples = list_high_frequency_request_samples()

    assert len(samples) >= MIN_HIGH_FREQUENCY_REQUEST_SAMPLES
    assert audit_high_frequency_request_samples() == ()
    assert {sample.sample_id for sample in samples} >= {
        "ambiguous_product_manual",
        "ambiguous_certificate_materials",
        "ambiguous_batch_notice",
        "project_application_form",
        "professional_medical_regulatory",
        "personal_resume_formatting",
        "negative_ppt_poster_design",
        "negative_webpage_publish",
    }
    for pack in list_scene_coverage_packs():
        assert samples_for_pack(pack.pack_id), pack.pack_id


def test_v24_boundary_samples_do_not_silently_fall_into_neighbor_scenes():
    medical = route_natural_scene_request("医疗注册申报资料")
    legal = route_natural_scene_request("法律意见书")
    personal = route_natural_scene_request("简历个人陈述")
    ppt = route_natural_scene_request("PPT海报设计")
    project_form = route_natural_scene_request("项目申请表")
    batch_notice = route_natural_scene_request("批量通知")
    journal = route_natural_scene_request("journal manuscript revision response letter")

    assert medical.status == "matched"
    assert medical.selected_route_id == "medical_regulatory_manual_boundary"
    assert medical.selected_pack_id == "professional_disclosure"
    assert medical.selected_route is not None
    assert medical.selected_route.plugin_gate_id == "professional_disclosure_review_gate"

    assert legal.status == "matched"
    assert legal.selected_route_id == "legal_document_manual_boundary"
    assert legal.selected_pack_id == "professional_disclosure"
    assert legal.selected_route is not None
    assert legal.selected_route.plugin_gate_id == "professional_disclosure_review_gate"

    assert journal.status == "matched"
    assert journal.selected_route_id == "english_journal_submission"
    assert journal.selected_pack_id == "english_journal"
    assert journal.selected_route is not None
    assert journal.selected_route.plugin_gate_id == "journal_publisher_rule_review_gate"

    assert personal.status == "matched"
    assert personal.selected_route_id == "personal_career_formatting"
    assert personal.selected_pack_id == "quick_formatting"

    assert ppt.status == "unmatched"
    assert ppt.selected_route_id == ""

    assert project_form.status == "ambiguous"
    assert {"project_application_package", "fixed_form_batch_documents"}.issubset(
        {match.route.route_id for match in project_form.matches}
    )
    assert {"application_reports", "batch_forms"}.issubset(
        {match.route.pack_id for match in project_form.matches}
    )

    assert batch_notice.status == "ambiguous"
    assert {"hr_batch_documents", "official_policy_documents"}.issubset(
        {match.route.route_id for match in batch_notice.matches}
    )
    assert {"batch_forms", "official_policy"}.issubset(
        {match.route.pack_id for match in batch_notice.matches}
    )


def test_scene_product_readiness_registry_separates_static_closure_from_product_green():
    pack_specs = list_scene_product_readiness_specs("pack")
    family_specs = list_scene_product_readiness_specs("family")

    assert audit_scene_product_readiness() == ()
    assert {spec.subject_id for spec in pack_specs} == {
        pack.pack_id for pack in list_scene_coverage_packs()
    }
    assert {spec.subject_id for spec in family_specs} == {
        family.family_id for family in list_planned_scene_families()
    }
    assert {spec.subject_id for spec in static_closed_but_not_green_specs()} == {
        pack.pack_id
        for pack in list_scene_coverage_packs()
            if pack.pack_id not in {
                "quick_formatting",
                "english_journal",
                "exam_education",
                "contract_delivery",
                "application_reports",
                "batch_forms",
                "bidding_materials",
                "chinese_academic",
                "official_policy",
                "technical_long_docs",
            }
        }
    assert {spec.subject_id for spec in pack_specs if spec.is_green} == {
        "quick_formatting",
        "application_reports",
        "batch_forms",
        "bidding_materials",
        "chinese_academic",
        "contract_delivery",
        "english_journal",
        "exam_education",
        "official_policy",
        "technical_long_docs",
    }
    assert {spec.subject_id for spec in family_specs if spec.is_green} == {
        "contract_delivery",
        "exam_teaching",
        "form_batch_documents",
        "hr_batch_documents",
        "journal_en",
        "long_document_publishing",
        "meeting_policy_documents",
        "product_sales_documents",
        "project_application",
        "qualification_archive_packages",
        "thesis_cn",
    }


def test_scene_product_readiness_marks_boundary_packs_without_overclaiming_l5():
    professional = product_readiness_for("professional_disclosure")
    import_ai = product_readiness_for("import_ai_boundary")
    quick = product_readiness_for("quick_formatting")

    assert professional.is_boundary
    assert import_ai.is_boundary
    assert professional.product_readiness_level == "blue_boundary"
    assert import_ai.product_readiness_level == "blue_boundary"
    assert quick.static_closure_level == "closed"
    assert quick.product_readiness_level == "green_l5"
    assert not quick.remaining_product_gaps
    assert readiness_summary(quick).startswith("pack:quick_formatting static=closed")
