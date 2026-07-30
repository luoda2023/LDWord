import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_natural_request_router import (
    audit_natural_request_router,
    build_natural_request_route_summary,
    get_natural_request_route,
    list_natural_request_routes,
    natural_request_route_payload,
    route_natural_scene_request,
    routes_for_coverage_pack,
)


def test_natural_request_router_registry_is_complete_and_auditable():
    assert audit_natural_request_router() == {}

    route_ids = {route.route_id for route in list_natural_request_routes()}
    assert {
        "quick_formatting_general",
        "chinese_academic_thesis",
        "english_journal_submission",
        "exam_teaching_versions",
        "bidding_document_authoring",
        "bidding_qualification_archive",
        "technical_long_document",
        "product_sales_document",
        "finance_quote_documents",
        "ip_patent_manual_boundary",
        "import_pdf_thesis_boundary",
    } <= route_ids
    assert routes_for_coverage_pack("professional_disclosure")
    assert get_natural_request_route("ip_patent_manual_boundary").plugin_gate_id == (
        "professional_disclosure_review_gate"
    )
    with pytest.raises(KeyError):
        get_natural_request_route("missing_route")


def test_natural_request_router_matches_core_high_frequency_requests():
    cases = (
        (
            "毕业论文学校字数检查",
            "chinese_academic_thesis",
            "chinese_academic",
            "thesis_cn",
        ),
        (
            "英文期刊 cover letter 和 revision",
            "english_journal_submission",
            "english_journal",
            "journal_en",
        ),
        (
            "学生版教师版试卷",
            "exam_teaching_versions",
            "exam_education",
            "exam_teaching",
        ),
        (
            "合同签署包字段一致性",
            "contract_delivery_package",
            "contract_delivery",
            "contract_delivery",
        ),
        (
            "会议纪要内部传阅归档",
            "official_policy_documents",
            "official_policy",
            "meeting_policy_documents",
        ),
    )

    for query, route_id, pack_id, family_id in cases:
        result = route_natural_scene_request(query)

        assert result.status == "matched"
        assert result.selected_route_id == route_id
        assert result.selected_pack_id == pack_id
        assert result.selected_route is not None
        assert result.selected_route.family_id == family_id
        assert any(f"pack={pack_id}" == line for line in result.evidence_lines)
        assert family_id in build_natural_request_route_summary(result)
        if route_id == "english_journal_submission":
            assert result.selected_route.plugin_gate_id == (
                "journal_publisher_rule_review_gate"
            )
            assert "plugin_gate=journal_publisher_rule_review_gate" in (
                build_natural_request_route_summary(result)
            )


def test_natural_request_router_disambiguates_product_manual_and_quote_plan():
    ambiguous_product = route_natural_scene_request("产品手册")

    assert ambiguous_product.status == "ambiguous"
    assert {
        ambiguous_product.matches[0].route.route_id,
        ambiguous_product.matches[1].route.route_id,
    } == {"product_sales_document", "technical_long_document"}
    assert "产品手册" in ambiguous_product.disambiguation_prompt

    customer_product = route_natural_scene_request("客户版产品手册")
    assert customer_product.status == "matched"
    assert customer_product.selected_route_id == "product_sales_document"
    assert customer_product.selected_pack_id == "application_reports"

    technical_product = route_natural_scene_request("技术产品手册")
    assert technical_product.status == "matched"
    assert technical_product.selected_route_id == "technical_long_document"
    assert technical_product.selected_pack_id == "technical_long_docs"

    ambiguous_quote = route_natural_scene_request("报价方案")
    assert ambiguous_quote.status == "ambiguous"
    assert {
        ambiguous_quote.matches[0].route.route_id,
        ambiguous_quote.matches[1].route.route_id,
    } == {"finance_quote_documents", "product_sales_document"}

    ambiguous_contract = route_natural_scene_request("合同法律审查签署包")
    assert ambiguous_contract.status == "ambiguous"
    assert {
        match.route.route_id for match in ambiguous_contract.matches[:2]
    } == {"contract_delivery_package", "legal_document_manual_boundary"}
    assert {
        match.route.pack_id for match in ambiguous_contract.matches[:2]
    } == {"contract_delivery", "professional_disclosure"}
    assert "法律意见/条款有效性判断" in ambiguous_contract.disambiguation_prompt
    assert "报价方案" in ambiguous_quote.disambiguation_prompt

    finance_quote = route_natural_scene_request("报价金额表和预算附件")
    assert finance_quote.status == "matched"
    assert finance_quote.selected_route_id == "finance_quote_documents"
    assert finance_quote.selected_pack_id == "professional_disclosure"

    product_quote = route_natural_scene_request("产品报价方案正文")
    assert product_quote.status == "matched"
    assert product_quote.selected_route_id == "product_sales_document"


def test_natural_request_router_disambiguates_certificates_and_bilingual_documents():
    certificate = route_natural_scene_request("证书材料")

    assert certificate.status == "ambiguous"
    assert {
        certificate.matches[0].route.route_id,
        certificate.matches[1].route.route_id,
    } == {"bidding_qualification_archive", "fixed_form_batch_documents"}
    assert "证书材料" in certificate.disambiguation_prompt

    qualification = route_natural_scene_request("投标资质证书材料")
    assert qualification.status == "matched"
    assert qualification.selected_route_id == "bidding_qualification_archive"
    assert qualification.selected_pack_id == "bidding_materials"

    bid_document = route_natural_scene_request("生成一份投标标书正文")
    assert bid_document.status == "matched"
    assert bid_document.selected_route_id == "bidding_document_authoring"
    assert bid_document.selected_pack_id == "bidding_materials"
    assert bid_document.selected_route is not None
    assert bid_document.selected_route.family_id == ""
    assert bid_document.selected_route.delivery_preset_id == "original"

    generic_report = route_natural_scene_request("生成一份项目报告")
    assert generic_report.selected_route_id != "bidding_document_authoring"

    generated_certificate = route_natural_scene_request("批量生成证书套打")
    assert generated_certificate.status == "matched"
    assert generated_certificate.selected_route_id == "fixed_form_batch_documents"
    assert generated_certificate.selected_pack_id == "batch_forms"

    bilingual = route_natural_scene_request("双语文档")
    assert bilingual.status == "ambiguous"
    assert {
        bilingual.matches[0].route.route_id,
        bilingual.matches[1].route.route_id,
    } == {"bilingual_review_documents", "quick_bilingual_formatting"}

    bilingual_format = route_natural_scene_request("双语文档排版")
    assert bilingual_format.status == "matched"
    assert bilingual_format.selected_route_id == "quick_bilingual_formatting"
    assert bilingual_format.selected_pack_id == "quick_formatting"

    term_review = route_natural_scene_request("双语术语一致性审阅")
    assert term_review.status == "matched"
    assert term_review.selected_route_id == "bilingual_review_documents"
    assert term_review.selected_pack_id == "professional_disclosure"


def test_natural_request_router_keeps_import_and_professional_boundaries_visible():
    pdf_thesis = route_natural_scene_request("PDF论文排版")

    assert pdf_thesis.status == "matched"
    assert pdf_thesis.selected_route_id == "import_pdf_thesis_boundary"
    assert pdf_thesis.selected_pack_id == "import_ai_boundary"
    assert pdf_thesis.selected_route is not None
    assert pdf_thesis.selected_route.handoff_pack_id == "chinese_academic"
    assert pdf_thesis.selected_route.handoff_family_id == "thesis_cn"
    assert pdf_thesis.selected_route.plugin_gate_id == "import_ai_conversion_gate"
    assert "handoff=chinese_academic" in build_natural_request_route_summary(pdf_thesis)

    latex_project = route_natural_scene_request("LaTeX转Word完整工程")
    assert latex_project.status == "matched"
    assert latex_project.selected_route_id == "import_ai_conversion_boundary"
    assert latex_project.selected_pack_id == "import_ai_boundary"

    patent = route_natural_scene_request("专利说明书权利要求草稿")

    assert patent.status == "matched"
    assert patent.selected_route_id == "ip_patent_manual_boundary"
    assert patent.selected_pack_id == "professional_disclosure"
    assert patent.selected_route is not None
    assert patent.selected_route.family_id == "ip_patent_documents"
    assert patent.selected_route.plugin_gate_id == "professional_disclosure_review_gate"
    assert any("plugin_gate=professional_disclosure_review_gate" == line for line in patent.evidence_lines)

    payload = natural_request_route_payload(patent)
    assert payload["status"] == "matched"
    assert payload["selected_route_id"] == "ip_patent_manual_boundary"
    assert payload["selected_pack_id"] == "professional_disclosure"
    assert payload["selected_family_id"] == "ip_patent_documents"
    assert payload["plugin_gate_id"] == "professional_disclosure_review_gate"
    assert "plugin_gate=professional_disclosure_review_gate" in payload["evidence_lines"]


def test_natural_request_router_reports_unmatched_requests_without_guessing():
    result = route_natural_scene_request("   ")

    assert result.status == "unmatched"
    assert result.selected_route is None
    assert "请输入" in result.disambiguation_prompt

    unknown = route_natural_scene_request("完全未知的神秘材料")
    assert unknown.status == "unmatched"
    assert unknown.selected_route is None
    assert "未找到稳定方案落点" in build_natural_request_route_summary(unknown)
