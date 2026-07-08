"""High-frequency task lexicon audit for the scene matrix.

N2.161 turns the V29 task-family table into an auditable lexicon.  Each
high-frequency task family must have representative user wording that either
routes to a stable scene landing, asks for disambiguation, or is explicitly
kept as a negative/non-core request.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from src.config.scene_high_frequency_request_samples import (
    HighFrequencyRequestSample,
    list_high_frequency_request_samples,
)
from src.config.scene_natural_request_router import (
    NaturalRequestRouteResult,
    route_natural_scene_request,
)
from src.config.scene_request_cell_fixture_registry import (
    list_scene_request_cell_fixtures,
)


N2_161_REQUIRED_TASK_IDS: tuple[str, ...] = (
    "quick_formatting_cleanup",
    "personal_career_formatting",
    "chinese_academic_thesis",
    "english_journal_submission",
    "exam_teaching_versions",
    "bidding_qualification_archive",
    "official_policy_documents",
    "technical_long_document",
    "project_application_package",
    "product_sales_document",
    "contract_delivery_package",
    "hr_batch_documents",
    "fixed_form_batch_documents",
    "finance_quote_documents",
    "regulated_disclosure_documents",
    "ip_patent_manual_boundary",
    "legal_document_manual_boundary",
    "medical_regulatory_manual_boundary",
    "bilingual_review_documents",
    "import_pdf_thesis_boundary",
    "import_ocr_pdf",
    "import_latex_project",
    "import_ai_diagrams",
    "data_to_word_batch",
    "ambiguous_product_manual",
    "ambiguous_quote_plan",
    "ambiguous_certificate_materials",
    "ambiguous_bilingual_document",
    "negative_non_word_native_delivery",
)

N2_161_SOURCE_EVIDENCE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "v29_task_table",
        "docs/audits/高层场景能力矩阵V29高频任务全集与边界准入深化规划_2026-06-19.md",
        ("## 4. 高频任务全集视角", "N2.161", "非 Word 原生交付"),
    ),
    (
        "natural_router",
        "src/config/scene_natural_request_router.py",
        ("route_natural_scene_request", "NATURAL_REQUEST_ROUTES", "handoff_pack_id"),
    ),
    (
        "request_samples",
        "src/config/scene_high_frequency_request_samples.py",
        ("HIGH_FREQUENCY_REQUEST_SAMPLES", "negative_ppt_poster_design"),
    ),
    (
        "request_cell_evidence",
        "src/config/scene_request_cell_fixture_registry.py",
        ("negative_control", "manual_boundary_fixture", "ambiguous_fixture_set"),
    ),
)


@dataclass(frozen=True, slots=True)
class HighFrequencyTaskLexiconEntry:
    task_id: str
    label: str
    landing_layer: str
    expected_status: str
    core_phrases: tuple[str, ...]
    expected_route_ids: tuple[str, ...] = ()
    expected_pack_ids: tuple[str, ...] = ()
    expected_family_ids: tuple[str, ...] = ()
    expected_plugin_gate_ids: tuple[str, ...] = ()
    expected_handoff_pack_ids: tuple[str, ...] = ()
    expected_handoff_family_ids: tuple[str, ...] = ()
    required_sample_ids: tuple[str, ...] = ()
    boundary_type: str = "matched"
    non_core_boundary: str = ""

    def to_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "landing_layer": self.landing_layer,
            "expected_status": self.expected_status,
            "core_phrases": list(self.core_phrases),
            "expected_route_ids": list(self.expected_route_ids),
            "expected_pack_ids": list(self.expected_pack_ids),
            "expected_family_ids": list(self.expected_family_ids),
            "expected_plugin_gate_ids": list(self.expected_plugin_gate_ids),
            "expected_handoff_pack_ids": list(self.expected_handoff_pack_ids),
            "expected_handoff_family_ids": list(self.expected_handoff_family_ids),
            "required_sample_ids": list(self.required_sample_ids),
            "boundary_type": self.boundary_type,
            "non_core_boundary": self.non_core_boundary,
        }


def _task(
    task_id: str,
    label: str,
    landing_layer: str,
    expected_status: str,
    core_phrase: str,
    *,
    route_ids: tuple[str, ...] = (),
    pack_ids: tuple[str, ...] = (),
    family_ids: tuple[str, ...] = (),
    plugin_gate_ids: tuple[str, ...] = (),
    handoff_pack_ids: tuple[str, ...] = (),
    handoff_family_ids: tuple[str, ...] = (),
    sample_ids: tuple[str, ...] = (),
    boundary_type: str = "matched",
    non_core_boundary: str = "",
    extra_phrases: tuple[str, ...] = (),
) -> HighFrequencyTaskLexiconEntry:
    return HighFrequencyTaskLexiconEntry(
        task_id=task_id,
        label=label,
        landing_layer=landing_layer,
        expected_status=expected_status,
        core_phrases=(core_phrase, *extra_phrases),
        expected_route_ids=route_ids,
        expected_pack_ids=pack_ids,
        expected_family_ids=family_ids,
        expected_plugin_gate_ids=plugin_gate_ids,
        expected_handoff_pack_ids=handoff_pack_ids,
        expected_handoff_family_ids=handoff_family_ids,
        required_sample_ids=sample_ids,
        boundary_type=boundary_type,
        non_core_boundary=non_core_boundary,
    )


HIGH_FREQUENCY_TASK_LEXICON: tuple[HighFrequencyTaskLexiconEntry, ...] = (
    _task(
        "quick_formatting_cleanup",
        "Quick formatting cleanup",
        "coverage_pack",
        "matched",
        "套模板修目录页码不对",
        route_ids=("quick_formatting_general",),
        pack_ids=("quick_formatting",),
        sample_ids=("quick_template_cleanup", "quick_word_cleanup"),
    ),
    _task(
        "personal_career_formatting",
        "Personal career formatting",
        "coverage_pack",
        "matched",
        "简历个人陈述排版",
        route_ids=("personal_career_formatting",),
        pack_ids=("quick_formatting",),
        sample_ids=("personal_resume_formatting",),
    ),
    _task(
        "chinese_academic_thesis",
        "Chinese academic thesis and coursework",
        "planned_family",
        "matched",
        "毕业论文学校字数检查",
        route_ids=("chinese_academic_thesis",),
        pack_ids=("chinese_academic",),
        family_ids=("thesis_cn",),
        sample_ids=("chinese_thesis_count", "chinese_course_formula_reference"),
    ),
    _task(
        "english_journal_submission",
        "English journal submission",
        "planned_family",
        "matched",
        "journal manuscript submission package BibTeX",
        route_ids=("english_journal_submission",),
        pack_ids=("english_journal",),
        family_ids=("journal_en",),
        sample_ids=("english_journal_submission_package",),
    ),
    _task(
        "exam_teaching_versions",
        "Exam and teaching versions",
        "plugin_boundary_family",
        "matched",
        "学生版教师版试卷",
        route_ids=("exam_teaching_versions",),
        pack_ids=("exam_education",),
        family_ids=("exam_teaching",),
        plugin_gate_ids=("exam_ai_complex_diagram_gate",),
        sample_ids=("exam_multi_version",),
        boundary_type="manual_boundary",
        non_core_boundary="AI quality and complex diagrams stay outside core.",
    ),
    _task(
        "bidding_qualification_archive",
        "Bidding qualification archive",
        "planned_family",
        "matched",
        "标书正本副本盖章",
        route_ids=("bidding_qualification_archive",),
        pack_ids=("bidding_materials",),
        family_ids=("qualification_archive_packages",),
        sample_ids=("bidding_original_copy", "bidding_consortium_seal_archive"),
    ),
    _task(
        "official_policy_documents",
        "Official policy documents",
        "planned_family",
        "matched",
        "会议纪要内部传阅归档",
        route_ids=("official_policy_documents",),
        pack_ids=("official_policy",),
        family_ids=("meeting_policy_documents",),
        sample_ids=("official_minutes_archive",),
    ),
    _task(
        "technical_long_document",
        "Technical long document",
        "planned_family",
        "matched",
        "接口文档验收报告",
        route_ids=("technical_long_document",),
        pack_ids=("technical_long_docs",),
        family_ids=("long_document_publishing",),
        sample_ids=("technical_interface_acceptance",),
    ),
    _task(
        "project_application_package",
        "Project application package",
        "planned_family",
        "matched",
        "项目申报限字附件",
        route_ids=("project_application_package",),
        pack_ids=("application_reports",),
        family_ids=("project_application",),
        sample_ids=("application_project_limits",),
    ),
    _task(
        "product_sales_document",
        "Product and pre-sales document",
        "planned_family",
        "matched",
        "售前方案客户方案",
        route_ids=("product_sales_document",),
        pack_ids=("application_reports",),
        family_ids=("product_sales_documents",),
        sample_ids=("application_presales_plan",),
    ),
    _task(
        "contract_delivery_package",
        "Contract delivery package",
        "planned_family",
        "matched",
        "合同签署包字段一致性",
        route_ids=("contract_delivery_package",),
        pack_ids=("contract_delivery",),
        family_ids=("contract_delivery",),
        sample_ids=("contract_signing_consistency",),
        non_core_boundary="Legal advice stays outside contract delivery.",
    ),
    _task(
        "hr_batch_documents",
        "HR batch documents",
        "planned_family",
        "matched",
        "HR批量offer",
        route_ids=("hr_batch_documents",),
        pack_ids=("batch_forms",),
        family_ids=("hr_batch_documents",),
        sample_ids=("batch_employee_certificate",),
    ),
    _task(
        "fixed_form_batch_documents",
        "Fixed-layout form and certificate batch",
        "planned_family",
        "matched",
        "批量生成证书套打",
        route_ids=("fixed_form_batch_documents",),
        pack_ids=("batch_forms",),
        family_ids=("form_batch_documents",),
        sample_ids=("batch_certificate_printing",),
    ),
    _task(
        "finance_quote_documents",
        "Finance quote documents",
        "professional_boundary",
        "matched",
        "报价金额表和预算附件",
        route_ids=("finance_quote_documents",),
        pack_ids=("professional_disclosure",),
        family_ids=("finance_quote_documents",),
        plugin_gate_ids=("professional_disclosure_review_gate",),
        sample_ids=("professional_finance_quote",),
        boundary_type="manual_boundary",
    ),
    _task(
        "regulated_disclosure_documents",
        "Regulated disclosure archive",
        "professional_boundary",
        "matched",
        "年报ESG披露归档",
        route_ids=("regulated_disclosure_documents",),
        pack_ids=("professional_disclosure",),
        family_ids=("regulated_disclosure_documents",),
        plugin_gate_ids=("professional_disclosure_review_gate",),
        sample_ids=("professional_esg_archive",),
        boundary_type="manual_boundary",
    ),
    _task(
        "ip_patent_manual_boundary",
        "IP and patent manual boundary",
        "plugin_manual_boundary",
        "matched",
        "专利说明书权利要求草稿",
        route_ids=("ip_patent_manual_boundary",),
        pack_ids=("professional_disclosure",),
        family_ids=("ip_patent_documents",),
        plugin_gate_ids=("professional_disclosure_review_gate",),
        sample_ids=("professional_patent_claims",),
        boundary_type="manual_boundary",
    ),
    _task(
        "legal_document_manual_boundary",
        "Legal document manual boundary",
        "plugin_manual_boundary",
        "matched",
        "法律意见书",
        route_ids=("legal_document_manual_boundary",),
        pack_ids=("professional_disclosure",),
        plugin_gate_ids=("professional_disclosure_review_gate",),
        sample_ids=("professional_legal_opinion",),
        boundary_type="manual_boundary",
    ),
    _task(
        "medical_regulatory_manual_boundary",
        "Medical regulatory manual boundary",
        "plugin_manual_boundary",
        "matched",
        "医疗注册申报资料",
        route_ids=("medical_regulatory_manual_boundary",),
        pack_ids=("professional_disclosure",),
        plugin_gate_ids=("professional_disclosure_review_gate",),
        sample_ids=("professional_medical_regulatory",),
        boundary_type="manual_boundary",
    ),
    _task(
        "bilingual_review_documents",
        "Bilingual review and term consistency",
        "professional_boundary",
        "matched",
        "双语术语一致性审阅",
        route_ids=("bilingual_review_documents",),
        pack_ids=("professional_disclosure",),
        family_ids=("bilingual_translation_documents",),
        plugin_gate_ids=("professional_disclosure_review_gate",),
        sample_ids=("professional_bilingual_terms",),
        boundary_type="manual_boundary",
    ),
    _task(
        "import_pdf_thesis_boundary",
        "PDF thesis import boundary",
        "import_handoff",
        "matched",
        "PDF论文排版",
        route_ids=("import_pdf_thesis_boundary",),
        pack_ids=("import_ai_boundary",),
        plugin_gate_ids=("import_ai_conversion_gate",),
        handoff_pack_ids=("chinese_academic",),
        handoff_family_ids=("thesis_cn",),
        sample_ids=("import_pdf_thesis",),
        boundary_type="handoff",
    ),
    _task(
        "import_ocr_pdf",
        "OCR/PDF import",
        "import_boundary",
        "matched",
        "OCR扫描件PDF转Word",
        route_ids=("import_ai_conversion_boundary",),
        pack_ids=("import_ai_boundary",),
        plugin_gate_ids=("import_ai_conversion_gate",),
        sample_ids=("import_ocr_pdf",),
        boundary_type="manual_boundary",
    ),
    _task(
        "import_latex_project",
        "Full LaTeX project import",
        "import_boundary",
        "matched",
        "LaTeX转Word完整工程",
        route_ids=("import_ai_conversion_boundary",),
        pack_ids=("import_ai_boundary",),
        plugin_gate_ids=("import_ai_conversion_gate",),
        sample_ids=("import_latex_project",),
        boundary_type="manual_boundary",
    ),
    _task(
        "import_ai_diagrams",
        "AI content and complex diagrams",
        "import_boundary",
        "matched",
        "AI写作复杂图形",
        route_ids=("import_ai_conversion_boundary",),
        pack_ids=("import_ai_boundary",),
        plugin_gate_ids=("import_ai_conversion_gate",),
        sample_ids=("import_ai_diagrams",),
        boundary_type="manual_boundary",
    ),
    _task(
        "data_to_word_batch",
        "Data-to-Word batch generation",
        "batch_preset",
        "matched",
        "登记表申请表批量",
        route_ids=("fixed_form_batch_documents", "hr_batch_documents"),
        pack_ids=("batch_forms",),
        family_ids=("form_batch_documents", "hr_batch_documents"),
        sample_ids=("batch_registration_form", "batch_hr_offer"),
        extra_phrases=("offer batch HR证明",),
    ),
    _task(
        "ambiguous_product_manual",
        "Ambiguous product manual",
        "ambiguous_boundary",
        "ambiguous",
        "产品手册",
        route_ids=("product_sales_document", "technical_long_document"),
        pack_ids=("application_reports", "technical_long_docs"),
        sample_ids=("ambiguous_product_manual",),
        boundary_type="ambiguous",
    ),
    _task(
        "ambiguous_quote_plan",
        "Ambiguous quote plan",
        "ambiguous_boundary",
        "ambiguous",
        "报价方案",
        route_ids=("finance_quote_documents", "product_sales_document"),
        pack_ids=("professional_disclosure", "application_reports"),
        sample_ids=("ambiguous_quote_plan",),
        boundary_type="ambiguous",
    ),
    _task(
        "ambiguous_certificate_materials",
        "Ambiguous certificate materials",
        "ambiguous_boundary",
        "ambiguous",
        "证书材料",
        route_ids=("bidding_qualification_archive", "fixed_form_batch_documents"),
        pack_ids=("bidding_materials", "batch_forms"),
        sample_ids=("ambiguous_certificate_materials",),
        boundary_type="ambiguous",
    ),
    _task(
        "ambiguous_bilingual_document",
        "Ambiguous bilingual document",
        "ambiguous_boundary",
        "ambiguous",
        "双语文档",
        route_ids=("bilingual_review_documents", "quick_bilingual_formatting"),
        pack_ids=("professional_disclosure", "quick_formatting"),
        sample_ids=("ambiguous_bilingual_document",),
        boundary_type="ambiguous",
    ),
    _task(
        "negative_non_word_native_delivery",
        "Non-Word native delivery negative controls",
        "negative_control",
        "unmatched",
        "PPT海报设计",
        sample_ids=(
            "negative_ppt_poster_design",
            "negative_webpage_publish",
            "unknown_stays_unmatched",
        ),
        boundary_type="negative",
        non_core_boundary="Slide, poster, and web publishing must not be silently absorbed by Word scene packs.",
        extra_phrases=("网页发布",),
    ),
)

HIGH_FREQUENCY_TASK_LEXICON_MAP: dict[str, HighFrequencyTaskLexiconEntry] = {
    entry.task_id: entry for entry in HIGH_FREQUENCY_TASK_LEXICON
}


@dataclass(frozen=True, slots=True)
class HighFrequencyTaskPhraseAudit:
    task_id: str
    phrase: str
    status: str
    selected_route_id: str
    selected_pack_id: str
    candidate_route_ids: tuple[str, ...]
    candidate_pack_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "phrase": self.phrase,
            "status": self.status,
            "selected_route_id": self.selected_route_id,
            "selected_pack_id": self.selected_pack_id,
            "candidate_route_ids": list(self.candidate_route_ids),
            "candidate_pack_ids": list(self.candidate_pack_ids),
        }


@dataclass(frozen=True, slots=True)
class HighFrequencyTaskLexiconIssue:
    task_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class HighFrequencyTaskLexiconSourceEvidence:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class HighFrequencyTaskLexiconRow:
    task_id: str
    label: str
    landing_layer: str
    expected_status: str
    boundary_type: str
    core_phrases: tuple[str, ...]
    phrase_audits: tuple[HighFrequencyTaskPhraseAudit, ...]
    expected_route_ids: tuple[str, ...]
    expected_pack_ids: tuple[str, ...]
    expected_family_ids: tuple[str, ...]
    expected_plugin_gate_ids: tuple[str, ...]
    expected_handoff_pack_ids: tuple[str, ...]
    expected_handoff_family_ids: tuple[str, ...]
    required_sample_ids: tuple[str, ...]
    request_cell_sample_ids: tuple[str, ...]
    non_core_boundary: str
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    @property
    def phrase_count(self) -> int:
        return len(self.core_phrases)

    def to_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "status": self.status,
            "landing_layer": self.landing_layer,
            "expected_status": self.expected_status,
            "boundary_type": self.boundary_type,
            "core_phrases": list(self.core_phrases),
            "phrase_count": self.phrase_count,
            "phrase_audits": [item.to_payload() for item in self.phrase_audits],
            "expected_route_ids": list(self.expected_route_ids),
            "expected_pack_ids": list(self.expected_pack_ids),
            "expected_family_ids": list(self.expected_family_ids),
            "expected_plugin_gate_ids": list(self.expected_plugin_gate_ids),
            "expected_handoff_pack_ids": list(self.expected_handoff_pack_ids),
            "expected_handoff_family_ids": list(self.expected_handoff_family_ids),
            "required_sample_ids": list(self.required_sample_ids),
            "request_cell_sample_ids": list(self.request_cell_sample_ids),
            "non_core_boundary": self.non_core_boundary,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class HighFrequencyTaskLexiconAuditReport:
    rows: tuple[HighFrequencyTaskLexiconRow, ...]
    issues: tuple[HighFrequencyTaskLexiconIssue, ...]
    source_evidence: tuple[HighFrequencyTaskLexiconSourceEvidence, ...]
    task_filter: str = ""
    status_filter: str = ""
    boundary_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def task_count(self) -> int:
        return len(self.rows)

    @property
    def phrase_count(self) -> int:
        return sum(row.phrase_count for row in self.rows)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def negative_task_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_type == "negative")

    @property
    def ambiguous_task_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_type == "ambiguous")

    @property
    def manual_boundary_task_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_type == "manual_boundary")

    @property
    def handoff_task_count(self) -> int:
        return sum(1 for row in self.rows if row.boundary_type == "handoff")

    @property
    def request_sample_count(self) -> int:
        return len(
            _unique_values(
                sample_id for row in self.rows for sample_id in row.required_sample_ids
            )
        )

    @property
    def request_cell_count(self) -> int:
        return len(
            _unique_values(
                sample_id for row in self.rows for sample_id in row.request_cell_sample_ids
            )
        )

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    @property
    def landing_layer_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(row.landing_layer for row in self.rows).items()))

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "task_filter": self.task_filter,
            "status_filter": self.status_filter,
            "boundary_filter": self.boundary_filter,
            "task_count": self.task_count,
            "phrase_count": self.phrase_count,
            "issue_count": self.issue_count,
            "negative_task_count": self.negative_task_count,
            "ambiguous_task_count": self.ambiguous_task_count,
            "manual_boundary_task_count": self.manual_boundary_task_count,
            "handoff_task_count": self.handoff_task_count,
            "request_sample_count": self.request_sample_count,
            "request_cell_count": self.request_cell_count,
            "missing_source_evidence_count": self.missing_source_evidence_count,
            "counts": {
                "task_count": self.task_count,
                "phrase_count": self.phrase_count,
                "issue_count": self.issue_count,
                "negative_task_count": self.negative_task_count,
                "ambiguous_task_count": self.ambiguous_task_count,
                "manual_boundary_task_count": self.manual_boundary_task_count,
                "handoff_task_count": self.handoff_task_count,
                "request_sample_count": self.request_sample_count,
                "request_cell_count": self.request_cell_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "landing_layer_counts": [
                {"landing_layer": layer, "count": count}
                for layer, count in self.landing_layer_counts
            ],
            "required_task_ids": list(N2_161_REQUIRED_TASK_IDS),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def list_high_frequency_task_lexicon_entries() -> tuple[HighFrequencyTaskLexiconEntry, ...]:
    return HIGH_FREQUENCY_TASK_LEXICON


def build_high_frequency_task_lexicon_audit_report(
    *,
    task_id: str = "",
    expected_status: str = "",
    boundary_type: str = "",
    project_root: Path | None = None,
) -> HighFrequencyTaskLexiconAuditReport:
    root = project_root or Path(__file__).resolve().parents[2]
    normalized_task = str(task_id or "").strip()
    normalized_status = str(expected_status or "").strip()
    normalized_boundary = str(boundary_type or "").strip()
    entries = tuple(
        entry
        for entry in HIGH_FREQUENCY_TASK_LEXICON
        if (not normalized_task or entry.task_id == normalized_task)
        and (not normalized_status or entry.expected_status == normalized_status)
        and (not normalized_boundary or entry.boundary_type == normalized_boundary)
    )

    rows_with_issues: list[HighFrequencyTaskLexiconRow] = []
    issues: list[HighFrequencyTaskLexiconIssue] = []
    samples = {sample.sample_id: sample for sample in list_high_frequency_request_samples()}
    request_cells = {
        cell.sample_id: cell for cell in list_scene_request_cell_fixtures()
    }
    for entry in entries:
        row = _build_row(entry, samples=samples, request_cells=request_cells)
        row_issues = _row_issues(row, samples=samples, request_cells=request_cells)
        issues.extend(row_issues)
        rows_with_issues.append(
            replace(row, issue_ids=tuple(issue.kind for issue in row_issues))
        )
    rows = tuple(rows_with_issues)

    if normalized_task and not rows:
        issues.append(
            HighFrequencyTaskLexiconIssue(
                task_id=normalized_task,
                kind="unknown_task_filter",
                message=f"Unknown high-frequency task lexicon entry: {normalized_task}",
            )
        )
    if not normalized_task and not normalized_status and not normalized_boundary:
        issues.extend(_global_issues(rows))

    source_evidence = _build_source_evidence(root)
    for evidence in source_evidence:
        if evidence.status != "ready":
            issues.append(
                HighFrequencyTaskLexiconIssue(
                    task_id="*",
                    kind=f"missing_source_evidence.{evidence.evidence_id}",
                    message=(
                        f"{evidence.source_path} is missing markers: "
                        + ", ".join(evidence.missing_markers)
                    ),
                )
            )

    return HighFrequencyTaskLexiconAuditReport(
        rows=rows,
        issues=tuple(issues),
        source_evidence=source_evidence,
        task_filter=normalized_task,
        status_filter=normalized_status,
        boundary_filter=normalized_boundary,
    )


def audit_high_frequency_task_lexicon_report(
    report: HighFrequencyTaskLexiconAuditReport | None = None,
) -> tuple[HighFrequencyTaskLexiconIssue, ...]:
    current = report or build_high_frequency_task_lexicon_audit_report()
    return current.issues


def _build_row(
    entry: HighFrequencyTaskLexiconEntry,
    *,
    samples: dict[str, HighFrequencyRequestSample],
    request_cells,
) -> HighFrequencyTaskLexiconRow:
    phrase_audits = tuple(
        _phrase_audit(entry.task_id, phrase, route_natural_scene_request(phrase))
        for phrase in entry.core_phrases
    )
    request_cell_sample_ids = tuple(
        sample_id for sample_id in entry.required_sample_ids if sample_id in request_cells
    )
    return HighFrequencyTaskLexiconRow(
        task_id=entry.task_id,
        label=entry.label,
        landing_layer=entry.landing_layer,
        expected_status=entry.expected_status,
        boundary_type=entry.boundary_type,
        core_phrases=entry.core_phrases,
        phrase_audits=phrase_audits,
        expected_route_ids=entry.expected_route_ids,
        expected_pack_ids=entry.expected_pack_ids,
        expected_family_ids=entry.expected_family_ids,
        expected_plugin_gate_ids=entry.expected_plugin_gate_ids,
        expected_handoff_pack_ids=entry.expected_handoff_pack_ids,
        expected_handoff_family_ids=entry.expected_handoff_family_ids,
        required_sample_ids=entry.required_sample_ids,
        request_cell_sample_ids=request_cell_sample_ids,
        non_core_boundary=entry.non_core_boundary,
        issue_ids=(),
    )


def _phrase_audit(
    task_id: str,
    phrase: str,
    result: NaturalRequestRouteResult,
) -> HighFrequencyTaskPhraseAudit:
    selected = result.selected_route
    return HighFrequencyTaskPhraseAudit(
        task_id=task_id,
        phrase=phrase,
        status=result.status,
        selected_route_id=result.selected_route_id,
        selected_pack_id=result.selected_pack_id,
        candidate_route_ids=tuple(match.route.route_id for match in result.matches),
        candidate_pack_ids=tuple(match.route.pack_id for match in result.matches),
    )


def _row_issues(
    row: HighFrequencyTaskLexiconRow,
    *,
    samples: dict[str, HighFrequencyRequestSample],
    request_cells,
) -> tuple[HighFrequencyTaskLexiconIssue, ...]:
    issues: list[HighFrequencyTaskLexiconIssue] = []

    def append(kind: str, message: str, severity: str = "error") -> None:
        issues.append(
            HighFrequencyTaskLexiconIssue(
                task_id=row.task_id,
                kind=kind,
                message=message,
                severity=severity,
            )
        )

    if not row.core_phrases:
        append("missing_core_phrases", "Task lexicon entry must include core phrases.")
    if not row.required_sample_ids:
        append(
            "missing_required_samples",
            "Task lexicon entry must point to at least one request sample.",
        )
    for audit in row.phrase_audits:
        if audit.status != row.expected_status:
            append(
                f"phrase_status_mismatch.{_issue_token(audit.phrase)}",
                (
                    f"Phrase {audit.phrase!r} routed as {audit.status}; "
                    f"expected {row.expected_status}."
                ),
            )
            continue
        if row.expected_status == "matched":
            if row.expected_route_ids and audit.selected_route_id not in row.expected_route_ids:
                append(
                    f"phrase_route_mismatch.{_issue_token(audit.phrase)}",
                    (
                        f"Phrase {audit.phrase!r} selected route "
                        f"{audit.selected_route_id}; expected one of "
                        + ", ".join(row.expected_route_ids)
                    ),
                )
            if row.expected_pack_ids and audit.selected_pack_id not in row.expected_pack_ids:
                append(
                    f"phrase_pack_mismatch.{_issue_token(audit.phrase)}",
                    (
                        f"Phrase {audit.phrase!r} selected pack "
                        f"{audit.selected_pack_id}; expected one of "
                        + ", ".join(row.expected_pack_ids)
                    ),
                )
        elif row.expected_status == "ambiguous":
            missing_routes = tuple(
                route_id
                for route_id in row.expected_route_ids
                if route_id not in audit.candidate_route_ids
            )
            if missing_routes:
                append(
                    f"ambiguous_missing_routes.{_issue_token(audit.phrase)}",
                    "Ambiguous phrase is missing candidate routes: "
                    + ", ".join(missing_routes),
                )
            missing_packs = tuple(
                pack_id
                for pack_id in row.expected_pack_ids
                if pack_id not in audit.candidate_pack_ids
            )
            if missing_packs:
                append(
                    f"ambiguous_missing_packs.{_issue_token(audit.phrase)}",
                    "Ambiguous phrase is missing candidate packs: "
                    + ", ".join(missing_packs),
                )

    for sample_id in row.required_sample_ids:
        sample = samples.get(sample_id)
        if sample is None:
            append(
                f"missing_request_sample.{sample_id}",
                f"Required request sample is missing: {sample_id}",
            )
            continue
        if sample.expected_status != row.expected_status:
            append(
                f"sample_status_mismatch.{sample_id}",
                (
                    f"Sample {sample_id} has status {sample.expected_status}; "
                    f"expected {row.expected_status}."
                ),
            )
        if row.expected_pack_ids and not (
            set(sample.expected_pack_ids) & set(row.expected_pack_ids)
        ):
            append(
                f"sample_pack_mismatch.{sample_id}",
                (
                    f"Sample {sample_id} does not reference expected packs: "
                    + ", ".join(row.expected_pack_ids)
                ),
            )
        if row.expected_plugin_gate_ids and not (
            set(sample.expected_plugin_gate_ids) & set(row.expected_plugin_gate_ids)
        ):
            append(
                f"sample_plugin_gate_mismatch.{sample_id}",
                (
                    f"Sample {sample_id} does not reference expected plugin gates: "
                    + ", ".join(row.expected_plugin_gate_ids)
                ),
            )
        if sample_id not in request_cells:
            append(
                f"missing_request_cell.{sample_id}",
                f"Required request sample has no request-cell evidence: {sample_id}",
            )

    if row.boundary_type in {"manual_boundary", "handoff"}:
        if not row.expected_plugin_gate_ids:
            append(
                "missing_plugin_gate_boundary",
                "Manual/handoff boundary tasks must declare a plugin gate.",
            )
    if row.boundary_type == "negative":
        if row.expected_pack_ids or row.expected_route_ids:
            append(
                "negative_has_positive_landing",
                "Negative-control tasks must not declare positive route or pack ids.",
            )
        if not row.non_core_boundary:
            append(
                "missing_negative_boundary_text",
                "Negative-control tasks must explain why they are outside core.",
            )
    if row.boundary_type == "handoff" and not row.expected_handoff_pack_ids:
        append("missing_handoff_pack", "Handoff tasks must declare target pack ids.")
    return tuple(issues)


def _global_issues(
    rows: tuple[HighFrequencyTaskLexiconRow, ...],
) -> tuple[HighFrequencyTaskLexiconIssue, ...]:
    issues: list[HighFrequencyTaskLexiconIssue] = []
    task_ids = {row.task_id for row in rows}
    for task_id in N2_161_REQUIRED_TASK_IDS:
        if task_id not in task_ids:
            issues.append(
                HighFrequencyTaskLexiconIssue(
                    task_id=task_id,
                    kind="missing_required_task",
                    message=f"Required high-frequency task is missing: {task_id}",
                )
            )
    if len(task_ids) != len(rows):
        issues.append(
            HighFrequencyTaskLexiconIssue(
                task_id="*",
                kind="duplicate_task_ids",
                message="Task lexicon contains duplicate task ids.",
            )
        )
    if not any(row.boundary_type == "negative" for row in rows):
        issues.append(
            HighFrequencyTaskLexiconIssue(
                task_id="*",
                kind="missing_negative_task",
                message="Task lexicon must include at least one negative task.",
            )
        )
    if not any(row.boundary_type == "ambiguous" for row in rows):
        issues.append(
            HighFrequencyTaskLexiconIssue(
                task_id="*",
                kind="missing_ambiguous_task",
                message="Task lexicon must include ambiguous boundary tasks.",
            )
        )
    if not any(row.boundary_type == "handoff" for row in rows):
        issues.append(
            HighFrequencyTaskLexiconIssue(
                task_id="*",
                kind="missing_handoff_task",
                message="Task lexicon must include import handoff tasks.",
            )
        )
    return tuple(issues)


def _build_source_evidence(
    root: Path,
) -> tuple[HighFrequencyTaskLexiconSourceEvidence, ...]:
    evidence_items: list[HighFrequencyTaskLexiconSourceEvidence] = []
    for evidence_id, source_path, markers in N2_161_SOURCE_EVIDENCE:
        path = root / source_path
        content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing_markers = tuple(marker for marker in markers if marker not in content)
        evidence_items.append(
            HighFrequencyTaskLexiconSourceEvidence(
                evidence_id=evidence_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing_markers,
            )
        )
    return tuple(evidence_items)


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def _issue_token(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())[:40]


__all__ = [
    "HIGH_FREQUENCY_TASK_LEXICON",
    "HIGH_FREQUENCY_TASK_LEXICON_MAP",
    "HighFrequencyTaskLexiconAuditReport",
    "HighFrequencyTaskLexiconEntry",
    "HighFrequencyTaskLexiconIssue",
    "HighFrequencyTaskLexiconRow",
    "N2_161_REQUIRED_TASK_IDS",
    "audit_high_frequency_task_lexicon_report",
    "build_high_frequency_task_lexicon_audit_report",
    "list_high_frequency_task_lexicon_entries",
]
