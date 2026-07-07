"""High-frequency request samples for scene routing acceptance.

The natural request router is implementation logic.  This registry is the
acceptance table from the V24 matrix: common and ambiguous user phrasings must
either route to a stable landing, ask for disambiguation, or stay behind an
explicit professional/import boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene_coverage_manifest import SCENE_COVERAGE_PACK_MAP
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP
from src.config.scene_natural_request_router import route_natural_scene_request


MIN_HIGH_FREQUENCY_REQUEST_SAMPLES = 40


@dataclass(frozen=True, slots=True)
class HighFrequencyRequestSample:
    sample_id: str
    request_text: str
    expected_status: str
    expected_route_ids: tuple[str, ...]
    expected_pack_ids: tuple[str, ...]
    expected_family_ids: tuple[str, ...] = ()
    expected_profile_ids: tuple[str, ...] = ()
    expected_delivery_preset_ids: tuple[str, ...] = ()
    expected_plugin_gate_ids: tuple[str, ...] = ()
    expected_handoff_pack_ids: tuple[str, ...] = ()
    expected_handoff_family_ids: tuple[str, ...] = ()
    disambiguation_required: bool = False
    boundary_phrase: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class HighFrequencyRequestSampleAuditResult:
    sample_id: str
    request_text: str
    issue: str
    expected: str = ""
    actual: str = ""

    @property
    def is_clean(self) -> bool:
        return not self.issue


def _sample(
    sample_id: str,
    request_text: str,
    expected_status: str,
    expected_route_ids: tuple[str, ...],
    expected_pack_ids: tuple[str, ...],
    *,
    expected_family_ids: tuple[str, ...] = (),
    expected_profile_ids: tuple[str, ...] = (),
    expected_delivery_preset_ids: tuple[str, ...] = (),
    expected_plugin_gate_ids: tuple[str, ...] = (),
    expected_handoff_pack_ids: tuple[str, ...] = (),
    expected_handoff_family_ids: tuple[str, ...] = (),
    disambiguation_required: bool = False,
    boundary_phrase: str = "",
    notes: str = "",
) -> HighFrequencyRequestSample:
    return HighFrequencyRequestSample(
        sample_id=sample_id,
        request_text=request_text,
        expected_status=expected_status,
        expected_route_ids=expected_route_ids,
        expected_pack_ids=expected_pack_ids,
        expected_family_ids=expected_family_ids,
        expected_profile_ids=expected_profile_ids,
        expected_delivery_preset_ids=expected_delivery_preset_ids,
        expected_plugin_gate_ids=expected_plugin_gate_ids,
        expected_handoff_pack_ids=expected_handoff_pack_ids,
        expected_handoff_family_ids=expected_handoff_family_ids,
        disambiguation_required=disambiguation_required,
        boundary_phrase=boundary_phrase,
        notes=notes,
    )


HIGH_FREQUENCY_REQUEST_SAMPLES: tuple[HighFrequencyRequestSample, ...] = (
    _sample(
        "quick_template_cleanup",
        "套模板修目录页码不对",
        "matched",
        ("quick_formatting_general",),
        ("quick_formatting",),
    ),
    _sample(
        "quick_word_cleanup",
        "统一Word格式清洗格式",
        "matched",
        ("quick_formatting_general",),
        ("quick_formatting",),
    ),
    _sample(
        "personal_resume_formatting",
        "简历个人陈述排版",
        "matched",
        ("personal_career_formatting",),
        ("quick_formatting",),
        boundary_phrase="dedicated family",
    ),
    _sample(
        "chinese_thesis_count",
        "毕业论文学校字数检查",
        "matched",
        ("chinese_academic_thesis",),
        ("chinese_academic",),
        expected_family_ids=("thesis_cn",),
        expected_profile_ids=("thesis_cn",),
    ),
    _sample(
        "chinese_course_formula_reference",
        "课程论文参考文献公式排版",
        "matched",
        ("chinese_academic_thesis",),
        ("chinese_academic",),
        expected_family_ids=("thesis_cn",),
    ),
    _sample(
        "chinese_proposal_abstract",
        "开题报告摘要字数",
        "matched",
        ("chinese_academic_thesis",),
        ("chinese_academic",),
        expected_family_ids=("thesis_cn",),
    ),
    _sample(
        "english_journal_revision",
        "英文期刊 cover letter 和 revision",
        "matched",
        ("english_journal_submission",),
        ("english_journal",),
        expected_family_ids=("journal_en",),
        expected_profile_ids=("journal_en_default",),
    ),
    _sample(
        "english_journal_submission_package",
        "journal manuscript submission package BibTeX",
        "matched",
        ("english_journal_submission",),
        ("english_journal",),
        expected_family_ids=("journal_en",),
        expected_delivery_preset_ids=("submission_manuscript",),
    ),
    _sample(
        "english_journal_response_letter",
        "journal manuscript revision response letter",
        "matched",
        ("english_journal_submission",),
        ("english_journal",),
        expected_family_ids=("journal_en",),
        expected_profile_ids=("journal_en_default",),
        expected_delivery_preset_ids=("submission_manuscript",),
        expected_plugin_gate_ids=("journal_publisher_rule_review_gate",),
        boundary_phrase="publisher-final layout and unreviewed journal rules",
    ),
    _sample(
        "exam_multi_version",
        "学生版教师版试卷",
        "matched",
        ("exam_teaching_versions",),
        ("exam_education",),
        expected_family_ids=("exam_teaching",),
        expected_plugin_gate_ids=("exam_ai_complex_diagram_gate",),
    ),
    _sample(
        "exam_answer_sheet",
        "答题卡学生版",
        "matched",
        ("exam_teaching_versions",),
        ("exam_education",),
        expected_family_ids=("exam_teaching",),
    ),
    _sample(
        "exam_answer_analysis",
        "题库答案版解析版",
        "matched",
        ("exam_teaching_versions",),
        ("exam_education",),
        expected_family_ids=("exam_teaching",),
    ),
    _sample(
        "bidding_qualification_certificate",
        "投标资质证书材料",
        "matched",
        ("bidding_qualification_archive",),
        ("bidding_materials",),
        expected_family_ids=("qualification_archive_packages",),
        disambiguation_required=True,
    ),
    _sample(
        "bidding_original_copy",
        "标书正本副本盖章",
        "matched",
        ("bidding_qualification_archive",),
        ("bidding_materials",),
        expected_family_ids=("qualification_archive_packages",),
    ),
    _sample(
        "bidding_license_archive",
        "营业执照资质附件包",
        "matched",
        ("bidding_qualification_archive",),
        ("bidding_materials",),
        expected_family_ids=("qualification_archive_packages",),
    ),
    _sample(
        "bidding_consortium_seal_archive",
        "联合体投标资料包盖章残留检查",
        "matched",
        ("bidding_qualification_archive",),
        ("bidding_materials",),
        expected_family_ids=("qualification_archive_packages",),
    ),
    _sample(
        "official_minutes_archive",
        "会议纪要内部传阅归档",
        "matched",
        ("official_policy_documents",),
        ("official_policy",),
        expected_family_ids=("meeting_policy_documents",),
    ),
    _sample(
        "official_policy_collection",
        "制度汇编文号归档",
        "matched",
        ("official_policy_documents",),
        ("official_policy",),
        expected_family_ids=("meeting_policy_documents",),
    ),
    _sample(
        "official_notice_formal_archive",
        "official notice formal archive",
        "matched",
        ("official_policy_documents",),
        ("official_policy",),
        expected_family_ids=("meeting_policy_documents",),
    ),
    _sample(
        "technical_product_manual",
        "技术产品手册",
        "matched",
        ("technical_long_document",),
        ("technical_long_docs",),
        expected_family_ids=("long_document_publishing",),
        disambiguation_required=True,
    ),
    _sample(
        "technical_interface_acceptance",
        "接口文档验收报告",
        "matched",
        ("technical_long_document",),
        ("technical_long_docs",),
        expected_family_ids=("long_document_publishing",),
    ),
    _sample(
        "technical_sop_chapter_inventory",
        "SOP chapter inventory appendix",
        "matched",
        ("technical_long_document",),
        ("technical_long_docs",),
        expected_family_ids=("long_document_publishing",),
    ),
    _sample(
        "application_customer_product_manual",
        "客户版产品手册",
        "matched",
        ("product_sales_document",),
        ("application_reports",),
        expected_family_ids=("product_sales_documents",),
        disambiguation_required=True,
    ),
    _sample(
        "application_presales_plan",
        "售前方案客户方案",
        "matched",
        ("product_sales_document",),
        ("application_reports",),
        expected_family_ids=("product_sales_documents",),
    ),
    _sample(
        "application_project_limits",
        "项目申报限字附件",
        "matched",
        ("project_application_package",),
        ("application_reports",),
        expected_family_ids=("project_application",),
    ),
    _sample(
        "application_review_budget",
        "评审材料预算表",
        "matched",
        ("project_application_package",),
        ("application_reports",),
        expected_family_ids=("project_application",),
    ),
    _sample(
        "contract_signing_consistency",
        "合同签署包字段一致性",
        "matched",
        ("contract_delivery_package",),
        ("contract_delivery",),
        expected_family_ids=("contract_delivery",),
        boundary_phrase="not legal advice",
    ),
    _sample(
        "contract_review_revisions",
        "合同审阅稿甲方乙方金额修订批注",
        "matched",
        ("contract_delivery_package",),
        ("contract_delivery",),
        expected_family_ids=("contract_delivery",),
    ),
    _sample(
        "contract_signature_package_fields",
        "contract signature package field consistency",
        "matched",
        ("contract_delivery_package",),
        ("contract_delivery",),
        expected_family_ids=("contract_delivery",),
        boundary_phrase="not legal advice",
    ),
    _sample(
        "ambiguous_contract_legal_review",
        "合同法律审查签署包",
        "ambiguous",
        ("contract_delivery_package", "legal_document_manual_boundary"),
        ("contract_delivery", "professional_disclosure"),
        expected_family_ids=("contract_delivery",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        disambiguation_required=True,
        boundary_phrase="not be absorbed by contract_delivery",
        notes=(
            "Contract legal advice or clause-validity judgment must be clarified "
            "against contract field/signing delivery and then routed to professional review."
        ),
    ),
    _sample(
        "batch_hr_offer",
        "offer batch HR证明",
        "matched",
        ("hr_batch_documents",),
        ("batch_forms",),
        expected_family_ids=("hr_batch_documents",),
    ),
    _sample(
        "batch_employee_certificate",
        "HR批量offer",
        "matched",
        ("hr_batch_documents",),
        ("batch_forms",),
        expected_family_ids=("hr_batch_documents",),
    ),
    _sample(
        "batch_certificate_printing",
        "批量生成证书套打",
        "matched",
        ("fixed_form_batch_documents",),
        ("batch_forms",),
        expected_family_ids=("form_batch_documents",),
        disambiguation_required=True,
    ),
    _sample(
        "batch_registration_form",
        "登记表申请表批量",
        "matched",
        ("fixed_form_batch_documents",),
        ("batch_forms",),
        expected_family_ids=("form_batch_documents",),
    ),
    _sample(
        "professional_finance_quote",
        "报价金额表和预算附件",
        "matched",
        ("finance_quote_documents",),
        ("professional_disclosure",),
        expected_family_ids=("finance_quote_documents",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        boundary_phrase="financial correctness",
    ),
    _sample(
        "professional_esg_archive",
        "年报ESG披露归档",
        "matched",
        ("regulated_disclosure_documents",),
        ("professional_disclosure",),
        expected_family_ids=("regulated_disclosure_documents",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        boundary_phrase="audit assurance",
    ),
    _sample(
        "professional_patent_claims",
        "专利说明书权利要求草稿",
        "matched",
        ("ip_patent_manual_boundary",),
        ("professional_disclosure",),
        expected_family_ids=("ip_patent_documents",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        boundary_phrase="professional plugin",
    ),
    _sample(
        "professional_bilingual_terms",
        "双语术语一致性审阅",
        "matched",
        ("bilingual_review_documents",),
        ("professional_disclosure",),
        expected_family_ids=("bilingual_translation_documents",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        disambiguation_required=True,
        boundary_phrase="translation quality",
    ),
    _sample(
        "professional_legal_opinion",
        "法律意见书",
        "matched",
        ("legal_document_manual_boundary",),
        ("professional_disclosure",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        boundary_phrase="not be absorbed by contract_delivery",
    ),
    _sample(
        "professional_medical_regulatory",
        "医疗注册申报资料",
        "matched",
        ("medical_regulatory_manual_boundary",),
        ("professional_disclosure",),
        expected_plugin_gate_ids=("professional_disclosure_review_gate",),
        boundary_phrase="not generic project applications",
    ),
    _sample(
        "import_pdf_thesis",
        "PDF论文排版",
        "matched",
        ("import_pdf_thesis_boundary",),
        ("import_ai_boundary",),
        expected_plugin_gate_ids=("import_ai_conversion_gate",),
        expected_handoff_pack_ids=("chinese_academic",),
        expected_handoff_family_ids=("thesis_cn",),
        boundary_phrase="manual confirmation",
    ),
    _sample(
        "import_ocr_pdf",
        "OCR扫描件PDF转Word",
        "matched",
        ("import_ai_conversion_boundary",),
        ("import_ai_boundary",),
        expected_plugin_gate_ids=("import_ai_conversion_gate",),
        boundary_phrase="confidence reports",
    ),
    _sample(
        "import_latex_project",
        "LaTeX转Word完整工程",
        "matched",
        ("import_ai_conversion_boundary",),
        ("import_ai_boundary",),
        expected_plugin_gate_ids=("import_ai_conversion_gate",),
        boundary_phrase="manual confirmation",
    ),
    _sample(
        "import_ai_diagrams",
        "AI写作复杂图形",
        "matched",
        ("import_ai_conversion_boundary",),
        ("import_ai_boundary",),
        expected_plugin_gate_ids=("import_ai_conversion_gate",),
        boundary_phrase="manual confirmation",
    ),
    _sample(
        "ambiguous_product_manual",
        "产品手册",
        "ambiguous",
        ("product_sales_document", "technical_long_document"),
        ("application_reports", "technical_long_docs"),
        disambiguation_required=True,
    ),
    _sample(
        "ambiguous_quote_plan",
        "报价方案",
        "ambiguous",
        ("finance_quote_documents", "product_sales_document"),
        ("professional_disclosure", "application_reports"),
        disambiguation_required=True,
    ),
    _sample(
        "ambiguous_certificate_materials",
        "证书材料",
        "ambiguous",
        ("bidding_qualification_archive", "fixed_form_batch_documents"),
        ("bidding_materials", "batch_forms"),
        disambiguation_required=True,
    ),
    _sample(
        "ambiguous_bilingual_document",
        "双语文档",
        "ambiguous",
        ("bilingual_review_documents", "quick_bilingual_formatting"),
        ("professional_disclosure", "quick_formatting"),
        disambiguation_required=True,
    ),
    _sample(
        "project_application_form",
        "项目申请表",
        "ambiguous",
        ("project_application_package", "fixed_form_batch_documents"),
        ("application_reports", "batch_forms"),
        disambiguation_required=True,
    ),
    _sample(
        "ambiguous_batch_notice",
        "批量通知",
        "ambiguous",
        ("hr_batch_documents", "official_policy_documents"),
        ("batch_forms", "official_policy"),
        disambiguation_required=True,
    ),
    _sample(
        "negative_ppt_poster_design",
        "PPT海报设计",
        "unmatched",
        (),
        (),
        disambiguation_required=True,
        boundary_phrase="未找到稳定场景落点",
        notes="Non-Word native slide/poster design must not be absorbed by Word scene packs.",
    ),
    _sample(
        "negative_webpage_publish",
        "网页发布",
        "unmatched",
        (),
        (),
        disambiguation_required=True,
        boundary_phrase="未找到稳定场景落点",
        notes="Web publishing is a negative control unless an external handoff is explicit.",
    ),
    _sample(
        "unknown_stays_unmatched",
        "完全未知的神秘材料",
        "unmatched",
        (),
        (),
        disambiguation_required=True,
        boundary_phrase="未找到稳定场景落点",
    ),
)


def list_high_frequency_request_samples() -> tuple[HighFrequencyRequestSample, ...]:
    return HIGH_FREQUENCY_REQUEST_SAMPLES


def samples_for_pack(pack_id: str) -> tuple[HighFrequencyRequestSample, ...]:
    normalized = str(pack_id or "").strip()
    return tuple(
        sample
        for sample in HIGH_FREQUENCY_REQUEST_SAMPLES
        if normalized in sample.expected_pack_ids
    )


def audit_high_frequency_request_samples() -> tuple[HighFrequencyRequestSampleAuditResult, ...]:
    issues: list[HighFrequencyRequestSampleAuditResult] = []
    issues.extend(_registry_issues())
    for sample in HIGH_FREQUENCY_REQUEST_SAMPLES:
        result = route_natural_scene_request(sample.request_text)
        if result.status != sample.expected_status:
            issues.append(
                _issue(
                    sample,
                    "status_mismatch",
                    sample.expected_status,
                    result.status,
                )
            )
            continue
        if result.status == "matched":
            route = result.selected_route
            if route is None:
                issues.append(_issue(sample, "missing_selected_route"))
                continue
            _check_expected(
                issues,
                sample,
                "route",
                sample.expected_route_ids,
                (route.route_id,),
            )
            _check_expected(
                issues,
                sample,
                "pack",
                sample.expected_pack_ids,
                (route.pack_id,),
            )
            _check_expected(
                issues,
                sample,
                "family",
                sample.expected_family_ids,
                (route.family_id,),
            )
            _check_expected(
                issues,
                sample,
                "profile",
                sample.expected_profile_ids,
                (route.profile_id,),
            )
            _check_expected(
                issues,
                sample,
                "delivery",
                sample.expected_delivery_preset_ids,
                (route.delivery_preset_id,),
            )
            _check_expected(
                issues,
                sample,
                "plugin_gate",
                sample.expected_plugin_gate_ids,
                (route.plugin_gate_id,),
            )
            _check_expected(
                issues,
                sample,
                "handoff_pack",
                sample.expected_handoff_pack_ids,
                (route.handoff_pack_id,),
            )
            _check_expected(
                issues,
                sample,
                "handoff_family",
                sample.expected_handoff_family_ids,
                (route.handoff_family_id,),
            )
        elif result.status == "ambiguous":
            candidate_routes = tuple(match.route.route_id for match in result.matches)
            candidate_packs = tuple(match.route.pack_id for match in result.matches)
            _check_expected_subset(
                issues,
                sample,
                "candidate_routes",
                sample.expected_route_ids,
                candidate_routes,
            )
            _check_expected_subset(
                issues,
                sample,
                "candidate_packs",
                sample.expected_pack_ids,
                candidate_packs,
            )

        if sample.disambiguation_required and not result.disambiguation_prompt:
            issues.append(_issue(sample, "missing_disambiguation_prompt"))
        if sample.boundary_phrase and sample.boundary_phrase.casefold() not in _route_text(result):
            issues.append(
                _issue(
                    sample,
                    "missing_boundary_phrase",
                    sample.boundary_phrase,
                    _route_text(result),
                )
            )
    return tuple(issues)


def _registry_issues() -> list[HighFrequencyRequestSampleAuditResult]:
    issues: list[HighFrequencyRequestSampleAuditResult] = []
    if len(HIGH_FREQUENCY_REQUEST_SAMPLES) < MIN_HIGH_FREQUENCY_REQUEST_SAMPLES:
        issues.append(
            HighFrequencyRequestSampleAuditResult(
                sample_id="registry:minimum_count",
                request_text="",
                issue="not_enough_samples",
                expected=str(MIN_HIGH_FREQUENCY_REQUEST_SAMPLES),
                actual=str(len(HIGH_FREQUENCY_REQUEST_SAMPLES)),
            )
        )
    issues.extend(_duplicate_issues("sample_id", [s.sample_id for s in HIGH_FREQUENCY_REQUEST_SAMPLES]))
    issues.extend(_duplicate_issues("request_text", [s.request_text for s in HIGH_FREQUENCY_REQUEST_SAMPLES]))
    expected_pack_ids = {
        pack_id
        for sample in HIGH_FREQUENCY_REQUEST_SAMPLES
        for pack_id in sample.expected_pack_ids
    }
    missing_pack_ids = tuple(
        pack_id for pack_id in SCENE_COVERAGE_PACK_MAP if pack_id not in expected_pack_ids
    )
    if missing_pack_ids:
        issues.append(
            HighFrequencyRequestSampleAuditResult(
                sample_id="registry:pack_coverage",
                request_text="",
                issue="missing_pack_samples",
                expected=",".join(SCENE_COVERAGE_PACK_MAP),
                actual=",".join(missing_pack_ids),
            )
        )
    for sample in HIGH_FREQUENCY_REQUEST_SAMPLES:
        for pack_id in sample.expected_pack_ids:
            if pack_id not in SCENE_COVERAGE_PACK_MAP:
                issues.append(_issue(sample, "unknown_expected_pack", pack_id))
        for family_id in sample.expected_family_ids:
            if family_id and family_id not in PLANNED_SCENE_FAMILY_MAP:
                issues.append(_issue(sample, "unknown_expected_family", family_id))
    return issues


def _duplicate_issues(
    field_name: str,
    values: list[str],
) -> list[HighFrequencyRequestSampleAuditResult]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    if not duplicates:
        return []
    return [
        HighFrequencyRequestSampleAuditResult(
            sample_id=f"registry:duplicate_{field_name}",
            request_text="",
            issue="duplicate_values",
            actual=",".join(duplicates),
        )
    ]


def _check_expected(
    issues: list[HighFrequencyRequestSampleAuditResult],
    sample: HighFrequencyRequestSample,
    field_name: str,
    expected_values: tuple[str, ...],
    actual_values: tuple[str, ...],
) -> None:
    expected = _clean_values(expected_values)
    if not expected:
        return
    actual = _clean_values(actual_values)
    if tuple(expected) != tuple(actual):
        issues.append(
            _issue(
                sample,
                f"{field_name}_mismatch",
                ",".join(expected),
                ",".join(actual),
            )
        )


def _check_expected_subset(
    issues: list[HighFrequencyRequestSampleAuditResult],
    sample: HighFrequencyRequestSample,
    field_name: str,
    expected_values: tuple[str, ...],
    actual_values: tuple[str, ...],
) -> None:
    expected = set(_clean_values(expected_values))
    if not expected:
        return
    actual = set(_clean_values(actual_values))
    if not expected <= actual:
        issues.append(
            _issue(
                sample,
                f"{field_name}_mismatch",
                ",".join(sorted(expected)),
                ",".join(sorted(actual)),
            )
        )


def _route_text(result) -> str:
    parts = [result.disambiguation_prompt, *result.evidence_lines]
    for match in result.matches:
        route = match.route
        parts.extend(
            [
                route.route_id,
                route.label,
                route.reason,
                route.disambiguation_prompt,
                route.pack_id,
                route.family_id,
                route.plugin_gate_id,
            ]
        )
    if result.selected_route is not None:
        route = result.selected_route
        parts.extend(
            [
                route.route_id,
                route.label,
                route.reason,
                route.disambiguation_prompt,
                route.pack_id,
                route.family_id,
                route.plugin_gate_id,
            ]
        )
    return "\n".join(str(part or "") for part in parts).casefold()


def _clean_values(values: tuple[str, ...]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return tuple(cleaned)


def _issue(
    sample: HighFrequencyRequestSample,
    issue: str,
    expected: str = "",
    actual: str = "",
) -> HighFrequencyRequestSampleAuditResult:
    return HighFrequencyRequestSampleAuditResult(
        sample_id=sample.sample_id,
        request_text=sample.request_text,
        issue=issue,
        expected=expected,
        actual=actual,
    )


__all__ = [
    "HIGH_FREQUENCY_REQUEST_SAMPLES",
    "MIN_HIGH_FREQUENCY_REQUEST_SAMPLES",
    "HighFrequencyRequestSample",
    "HighFrequencyRequestSampleAuditResult",
    "audit_high_frequency_request_samples",
    "list_high_frequency_request_samples",
    "samples_for_pack",
]
