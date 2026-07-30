"""Natural-language request routing for high-level scene capabilities."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_product_coverage_manifest import (
    SCENE_COVERAGE_PACK_MAP,
    coverage_packs_for_family,
    list_scene_coverage_packs,
)
from src.config.scene_family_registry import get_planned_scene_family


_AMBIGUITY_SCORE_DELTA = 14


@dataclass(frozen=True, slots=True)
class NaturalRequestRoute:
    """One route from a user's natural wording to a scene capability landing."""

    route_id: str
    label: str
    pack_id: str
    aliases: tuple[str, ...]
    family_id: str = ""
    profile_id: str = ""
    delivery_preset_id: str = ""
    plugin_gate_id: str = ""
    handoff_pack_id: str = ""
    handoff_family_id: str = ""
    route_type: str = "scene_family"
    context_tokens: tuple[str, ...] = ()
    anti_tokens: tuple[str, ...] = ()
    reason: str = ""
    disambiguation_prompt: str = ""


@dataclass(frozen=True, slots=True)
class NaturalRequestRouteMatch:
    """Scored match between a request and one configured route."""

    route: NaturalRequestRoute
    score: int
    matched_aliases: tuple[str, ...] = ()
    matched_context_tokens: tuple[str, ...] = ()
    matched_anti_tokens: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NaturalRequestRouteResult:
    """Routing result for one natural request."""

    query: str
    normalized_query: str
    status: str
    matches: tuple[NaturalRequestRouteMatch, ...] = ()
    selected_route: NaturalRequestRoute | None = None
    disambiguation_prompt: str = ""
    evidence_lines: tuple[str, ...] = ()

    @property
    def selected_route_id(self) -> str:
        return self.selected_route.route_id if self.selected_route is not None else ""

    @property
    def selected_pack_id(self) -> str:
        return self.selected_route.pack_id if self.selected_route is not None else ""


NATURAL_REQUEST_ROUTES: tuple[NaturalRequestRoute, ...] = (
    NaturalRequestRoute(
        route_id="quick_formatting_general",
        label="Quick formatting and template cleanup",
        pack_id="quick_formatting",
        aliases=(
            "format word",
            "clean document",
            "normalize report",
            "统一Word格式",
            "清洗格式",
            "套模板",
            "修目录",
            "页码不对",
            "普通排版",
            "格式要求",
            "格式规则",
            "格式规范",
            "标准样稿",
            "参考样稿",
        ),
        route_type="executable_scene",
        context_tokens=("格式", "目录", "页码", "template", "cleanup"),
        reason="General formatting requests should stay in quick_formatting without professional promises.",
    ),
    NaturalRequestRoute(
        route_id="quick_bilingual_formatting",
        label="Bilingual formatting without translation review",
        pack_id="quick_formatting",
        aliases=("双语文档", "bilingual document"),
        route_type="executable_scene",
        context_tokens=("排版", "格式", "套模板", "format"),
        anti_tokens=("术语", "一致性", "翻译质量", "审阅"),
        reason="Plain bilingual layout/format cleanup is a formatting request, not a translation-quality review.",
        disambiguation_prompt="请确认是双语排版，还是术语一致性/翻译审阅。",
    ),
    NaturalRequestRoute(
        route_id="personal_career_formatting",
        label="Personal career document formatting",
        pack_id="quick_formatting",
        aliases=("简历", "个人陈述", "求职信", "resume", "personal statement", "cover letter"),
        route_type="executable_scene",
        context_tokens=("排版", "格式", "套模板", "format"),
        anti_tokens=("HR", "批量", "员工", "offer"),
        reason=(
            "Personal career documents can use quick formatting unless the product "
            "scope later promotes them into a dedicated family."
        ),
    ),
    NaturalRequestRoute(
        route_id="chinese_academic_thesis",
        label="Chinese academic thesis and coursework",
        pack_id="chinese_academic",
        aliases=(
            "thesis",
            "course paper",
            "literature review",
            "proposal",
            "毕业论文",
            "课程论文",
            "开题报告",
            "文献综述",
            "学校字数",
            "论文排版",
        ),
        family_id="thesis_cn",
        profile_id="thesis_cn",
        route_type="planned_family",
        context_tokens=("学校", "字数", "参考文献", "公式", "摘要"),
        anti_tokens=("journal", "cover letter", "revision", "期刊投稿"),
        reason="Chinese academic requests use thesis_cn and school/count profiles, not journal submission.",
    ),
    NaturalRequestRoute(
        route_id="english_journal_submission",
        label="English journal submission",
        pack_id="english_journal",
        aliases=(
            "journal manuscript",
            "cover letter",
            "revision",
            "submission package",
            "英文期刊投稿",
            "期刊投稿",
            "BibTeX",
            "CSL",
            "cover letter",
            "revision",
        ),
        family_id="journal_en",
        profile_id="journal_en_default",
        delivery_preset_id="submission_manuscript",
        plugin_gate_id="journal_publisher_rule_review_gate",
        route_type="planned_family",
        context_tokens=("journal", "publisher", "manuscript", "投稿", "期刊"),
        anti_tokens=("毕业论文", "课程论文", "学校"),
        reason=(
            "Journal submission has independent profiles, citation sources, "
            "delivery package semantics, and publisher-final layout and "
            "unreviewed journal rules boundaries."
        ),
    ),
    NaturalRequestRoute(
        route_id="exam_teaching_versions",
        label="Exam and teaching material versions",
        pack_id="exam_education",
        aliases=(
            "student version",
            "teacher version",
            "answer key",
            "handout",
            "试卷",
            "题库",
            "学生版",
            "教师版",
            "答案版",
            "解析版",
            "答题卡",
            "讲义",
        ),
        family_id="exam_teaching",
        profile_id="exam_teaching_default",
        delivery_preset_id="student_version",
        plugin_gate_id="exam_ai_complex_diagram_gate",
        route_type="planned_family",
        context_tokens=("题目", "答案", "解析", "分值", "多版本"),
        reason="Exam requests derive student/teacher/answer outputs from one structured source.",
    ),
    NaturalRequestRoute(
        route_id="bidding_document_authoring",
        label="Bidding document authoring and formatting",
        pack_id="bidding_materials",
        aliases=(
            "bid document",
            "tender copy",
            "标书",
            "投标文件",
            "投标书",
            "正本副本",
        ),
        profile_id="bidding_document_default",
        delivery_preset_id="original",
        route_type="executable_scene",
        # Generic authoring verbs must never route a project report into the
        # bidding work mode.  The domain aliases above are the required anchor.
        context_tokens=(),
        anti_tokens=("资质", "证照", "营业执照", "证书材料", "附件包", "资料包"),
        reason=(
            "Bid document authoring and formatting produce reviewable DOCX "
            "original/copy outputs; they are not qualification attachment archives."
        ),
    ),
    NaturalRequestRoute(
        route_id="bidding_qualification_archive",
        label="Bidding and qualification archive",
        pack_id="bidding_materials",
        aliases=(
            "seal assets",
            "qualification archive",
            "资质证照",
            "营业执照",
            "投标证书材料",
            "证书材料",
            "资质附件包",
            "投标资料包",
        ),
        family_id="qualification_archive_packages",
        profile_id="qualification_archive_packages_default",
        delivery_preset_id="attachment_package",
        route_type="planned_family",
        context_tokens=("投标", "资质", "营业执照", "附件", "资料包", "归档"),
        anti_tokens=("套打", "生成证书", "奖状", "登记表", "标书正文", "正本", "副本"),
        reason="Qualification certificates used as bid evidence belong to bidding material archive workflows.",
        disambiguation_prompt="请确认证书材料是投标资质附件，还是要批量套打生成证书。",
    ),
    NaturalRequestRoute(
        route_id="official_policy_documents",
        label="Official meeting and policy documents",
        pack_id="official_policy",
        aliases=(
            "notice",
            "letter",
            "minutes",
            "policy collection",
            "通知",
            "函",
            "请示",
            "批复",
            "会议纪要",
            "制度汇编",
            "内部传阅",
        ),
        family_id="meeting_policy_documents",
        profile_id="meeting_policy_documents_default",
        delivery_preset_id="formal_minutes",
        route_type="planned_family",
        context_tokens=("文号", "归档", "政策", "会议"),
        reason="Administrative document variants stay under official_policy profiles instead of new top-level scenes.",
    ),
    NaturalRequestRoute(
        route_id="technical_long_document",
        label="Technical long document",
        pack_id="technical_long_docs",
        aliases=(
            "SOP",
            "interface manual",
            "acceptance report",
            "book manuscript",
            "技术手册",
            "产品手册",
            "接口文档",
            "验收报告",
            "书稿",
            "操作手册",
        ),
        family_id="long_document_publishing",
        profile_id="long_document_publishing_default",
        delivery_preset_id="final_docx",
        route_type="planned_family",
        context_tokens=("技术", "接口", "操作", "SOP", "验收", "手册"),
        anti_tokens=("客户", "售前", "白皮书", "营销", "方案正文"),
        reason="Operational/product technical manuals need long-document inventory and review/proof/final delivery.",
        disambiguation_prompt="请确认产品手册是技术操作手册，还是面向客户的产品/售前资料。",
    ),
    NaturalRequestRoute(
        route_id="project_application_package",
        label="Project application and review package",
        pack_id="application_reports",
        aliases=(
            "application book",
            "review package",
            "项目申报",
            "评审材料",
            "立项书",
            "申报附件包",
            "项目申请表",
        ),
        family_id="project_application",
        profile_id="project_application_default",
        delivery_preset_id="application_package",
        route_type="planned_family",
        context_tokens=("申报", "评审", "附件", "限字", "预算表", "申请表"),
        reason="Project applications need section limits, attachment inventory, and application package delivery.",
        disambiguation_prompt="请确认项目申请表是申报材料包，还是固定版式表单套打。",
    ),
    NaturalRequestRoute(
        route_id="product_sales_document",
        label="Product, whitepaper, and pre-sales document",
        pack_id="application_reports",
        aliases=(
            "whitepaper",
            "pre-sales document",
            "白皮书",
            "产品手册",
            "售前方案",
            "客户方案",
            "产品报价方案",
            "报价方案",
        ),
        family_id="product_sales_documents",
        profile_id="product_sales_documents_default",
        delivery_preset_id="customer_copy",
        route_type="planned_family",
        context_tokens=("客户", "售前", "白皮书", "产品", "方案正文", "营销"),
        anti_tokens=("技术", "操作", "接口", "金额", "预算", "财务", "报价单"),
        reason="Customer-facing product or pre-sales text belongs to application_reports/product_sales_documents.",
        disambiguation_prompt="请确认是产品/售前正文，还是报价金额表或预算附件。",
    ),
    NaturalRequestRoute(
        route_id="contract_delivery_package",
        label="Contract review and signing delivery",
        pack_id="contract_delivery",
        aliases=(
            "review copy",
            "signing copy",
            "field consistency",
            "signature package",
            "合同",
            "协议",
            "合同审阅稿",
            "签署包",
            "字段一致性",
        ),
        family_id="contract_delivery",
        profile_id="contract_delivery_default",
        delivery_preset_id="review_copy",
        route_type="planned_family",
        context_tokens=("甲方", "乙方", "金额", "签章", "修订", "批注"),
        reason="Contract delivery can handle field consistency and signing artifacts, not legal advice.",
    ),
    NaturalRequestRoute(
        route_id="hr_batch_documents",
        label="HR batch documents",
        pack_id="batch_forms",
        aliases=("offer batch", "HR证明", "offer", "批量通知", "人员证明"),
        family_id="hr_batch_documents",
        profile_id="hr_batch_documents_default",
        delivery_preset_id="per_person_docx",
        route_type="planned_family",
        context_tokens=("HR", "员工", "人员", "offer", "入职"),
        reason="HR batch documents use one-record-one-output and failed-item isolation.",
    ),
    NaturalRequestRoute(
        route_id="fixed_form_batch_documents",
        label="Fixed-layout form and certificate batch",
        pack_id="batch_forms",
        aliases=(
            "certificate batch",
            "fixed form",
            "registration form",
            "证书材料",
            "证书",
            "奖状",
            "登记表",
            "申请表",
            "套打",
        ),
        family_id="form_batch_documents",
        profile_id="form_batch_documents_default",
        delivery_preset_id="per_record_docx",
        route_type="planned_family",
        context_tokens=("套打", "生成证书", "奖状", "登记表", "申请表", "批量"),
        anti_tokens=("投标", "资质", "营业执照"),
        reason="Generated certificates/forms are fixed-layout batch outputs, not qualification evidence.",
        disambiguation_prompt="请确认证书材料是批量套打生成，还是投标资质附件。",
    ),
    NaturalRequestRoute(
        route_id="finance_quote_documents",
        label="Finance quote and attachment report",
        pack_id="professional_disclosure",
        aliases=(
            "quote",
            "budget",
            "报价单",
            "预算书",
            "报价方案",
            "财务附件",
            "客户报价",
            "成本表报价",
        ),
        family_id="finance_quote_documents",
        profile_id="finance_quote_documents_default",
        delivery_preset_id="customer_quote",
        plugin_gate_id="professional_disclosure_review_gate",
        route_type="professional_boundary",
        context_tokens=(
            "金额",
            "预算",
            "财务",
            "报价单",
            "报价表",
            "成本表",
            "附件",
        ),
        anti_tokens=("产品", "售前", "方案正文", "营销"),
        reason="Quote/budget tables can be formatted and packaged, but financial correctness stays outside core.",
        disambiguation_prompt="请确认报价方案是金额/预算表，还是产品售前方案正文。",
    ),
    NaturalRequestRoute(
        route_id="regulated_disclosure_documents",
        label="Regulated disclosure archive",
        pack_id="professional_disclosure",
        aliases=("ESG report", "年报", "ESG", "披露材料", "年度报告"),
        family_id="regulated_disclosure_documents",
        profile_id="regulated_disclosure_documents_default",
        delivery_preset_id="board_review_copy",
        plugin_gate_id="professional_disclosure_review_gate",
        route_type="professional_boundary",
        context_tokens=("披露", "董事会", "公开发布", "归档", "hidden text"),
        reason="Disclosure documents can produce review/public/archive packages without audit assurance.",
    ),
    NaturalRequestRoute(
        route_id="ip_patent_manual_boundary",
        label="Patent and IP plugin/manual boundary",
        pack_id="professional_disclosure",
        aliases=("patent draft", "专利交底", "专利说明书", "权利要求", "说明书草稿"),
        family_id="ip_patent_documents",
        profile_id="ip_patent_documents_default",
        plugin_gate_id="professional_disclosure_review_gate",
        route_type="plugin_manual_boundary",
        context_tokens=("专利", "权利要求", "侵权", "授权", "法律质量"),
        reason="Patent/IP legal quality must stay behind professional plugin/manual review.",
    ),
    NaturalRequestRoute(
        route_id="legal_document_manual_boundary",
        label="Legal document plugin/manual boundary",
        pack_id="professional_disclosure",
        aliases=(
            "合同法律审查",
            "合同条款法律审查",
            "合同法律风险",
            "法律风险审查",
            "法律意见书",
            "法律文书",
            "诉状",
            "legal opinion",
            "legal document",
        ),
        plugin_gate_id="professional_disclosure_review_gate",
        route_type="plugin_manual_boundary",
        context_tokens=("法律", "法律风险", "诉讼", "合规意见", "律师", "legal"),
        anti_tokens=("签署包", "字段一致性"),
        reason=(
            "Legal documents stay behind professional plugin/manual review and must "
            "not be absorbed by contract_delivery."
        ),
        disambiguation_prompt="请确认是合同字段/签署包交付，还是法律意见/条款有效性判断。",
    ),
    NaturalRequestRoute(
        route_id="medical_regulatory_manual_boundary",
        label="Medical and drug regulatory plugin/manual boundary",
        pack_id="professional_disclosure",
        aliases=("医疗注册", "医药注册", "药品注册", "医疗器械注册", "注册申报资料"),
        plugin_gate_id="professional_disclosure_review_gate",
        route_type="plugin_manual_boundary",
        context_tokens=("医疗", "医药", "药品", "器械", "注册"),
        anti_tokens=("项目申报", "立项书", "评审材料"),
        reason=(
            "Medical or drug regulatory submissions are high-risk professional "
            "materials, not generic project applications."
        ),
    ),
    NaturalRequestRoute(
        route_id="bilingual_review_documents",
        label="Bilingual review and term consistency",
        pack_id="professional_disclosure",
        aliases=("bilingual review", "双语文档", "双语审阅", "术语一致性", "翻译审阅"),
        family_id="bilingual_translation_documents",
        profile_id="bilingual_translation_documents_default",
        delivery_preset_id="bilingual_review_copy",
        plugin_gate_id="professional_disclosure_review_gate",
        route_type="professional_boundary",
        context_tokens=("术语", "翻译", "对照"),
        anti_tokens=("排版", "格式", "套模板"),
        reason="Bilingual review can check layout and term consistency, while translation quality stays outside core.",
        disambiguation_prompt="请确认是双语排版，还是术语一致性/翻译审阅。",
    ),
    NaturalRequestRoute(
        route_id="import_pdf_thesis_boundary",
        label="PDF thesis import boundary before academic routing",
        pack_id="import_ai_boundary",
        aliases=("PDF论文", "PDF论文排版", "pdf thesis", "PDF转Word论文"),
        handoff_pack_id="chinese_academic",
        handoff_family_id="thesis_cn",
        plugin_gate_id="import_ai_conversion_gate",
        route_type="import_boundary",
        context_tokens=("PDF", "扫描", "OCR", "转Word", "导入"),
        anti_tokens=("LaTeX",),
        reason="PDF thesis requests must pass import confidence/manual confirmation before thesis formatting.",
    ),
    NaturalRequestRoute(
        route_id="import_ai_conversion_boundary",
        label="Import and AI conversion boundary",
        pack_id="import_ai_boundary",
        aliases=(
            "OCR import",
            "PDF to Word",
            "full LaTeX",
            "AI content",
            "complex diagrams",
            "OCR",
            "PDF转Word",
            "LaTeX转Word",
            "AI写作",
            "复杂图形",
            "几何图",
        ),
        plugin_gate_id="import_ai_conversion_gate",
        route_type="import_boundary",
        context_tokens=("扫描", "低置信度", "无损", "AI", "LaTeX", "OCR"),
        reason="Import/AI/complex diagram requests need confidence reports and manual confirmation first.",
    ),
)


NATURAL_REQUEST_ROUTE_MAP: dict[str, NaturalRequestRoute] = {
    route.route_id: route for route in NATURAL_REQUEST_ROUTES
}


def list_natural_request_routes() -> tuple[NaturalRequestRoute, ...]:
    """Return all configured natural request routes."""

    return NATURAL_REQUEST_ROUTES


def get_natural_request_route(route_id: str) -> NaturalRequestRoute:
    """Look up one natural request route."""

    normalized = str(route_id or "").strip()
    try:
        return NATURAL_REQUEST_ROUTE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown natural request route: {route_id}") from exc


def routes_for_coverage_pack(pack_id: str) -> tuple[NaturalRequestRoute, ...]:
    """Return routes whose primary landing is a coverage pack."""

    normalized = str(pack_id or "").strip()
    return tuple(route for route in NATURAL_REQUEST_ROUTES if route.pack_id == normalized)


def route_natural_scene_request(query: str) -> NaturalRequestRouteResult:
    """Route a user-facing natural request to a coverage pack/family landing."""

    normalized = _normalize_text(query)
    if not normalized:
        return NaturalRequestRouteResult(
            query=str(query or ""),
            normalized_query=normalized,
            status="unmatched",
            disambiguation_prompt="请输入要处理的文档任务。",
        )

    matches = tuple(
        sorted(
            (
                match
                for route in NATURAL_REQUEST_ROUTES
                if (match := _match_route(route, normalized)) is not None
            ),
            key=lambda item: (-item.score, item.route.route_id),
        )
    )
    if not matches:
        return NaturalRequestRouteResult(
            query=str(query or ""),
            normalized_query=normalized,
            status="unmatched",
            disambiguation_prompt="未找到稳定方案落点，请先判断是否属于模板、资料、输出或插件边界。",
        )

    top_score = matches[0].score
    competing = tuple(
        match for match in matches if top_score - match.score <= _AMBIGUITY_SCORE_DELTA
    )
    if len(competing) > 1:
        return NaturalRequestRouteResult(
            query=str(query or ""),
            normalized_query=normalized,
            status="ambiguous",
            matches=matches,
            disambiguation_prompt=_combined_disambiguation_prompt(competing),
            evidence_lines=_route_evidence_lines(competing[0].route, competing[0]),
        )

    selected_match = matches[0]
    return NaturalRequestRouteResult(
        query=str(query or ""),
        normalized_query=normalized,
        status="matched",
        matches=matches,
        selected_route=selected_match.route,
        disambiguation_prompt=selected_match.route.disambiguation_prompt,
        evidence_lines=_route_evidence_lines(selected_match.route, selected_match),
    )


def build_natural_request_route_summary(result: NaturalRequestRouteResult) -> str:
    """Build a compact summary suitable for Workbench or report surfaces."""

    if result.status == "unmatched":
        return f"unmatched: {result.disambiguation_prompt}"
    if result.status == "ambiguous":
        route_ids = "/".join(match.route.route_id for match in result.matches[:3])
        return f"ambiguous: {route_ids}; prompt={result.disambiguation_prompt}"
    route = result.selected_route
    if route is None:
        return "unmatched: no selected route"
    parts = [f"route={route.route_id}", f"pack={route.pack_id}"]
    if route.family_id:
        parts.append(f"family={route.family_id}")
    if route.delivery_preset_id:
        parts.append(f"delivery={route.delivery_preset_id}")
    if route.plugin_gate_id:
        parts.append(f"plugin_gate={route.plugin_gate_id}")
    if route.handoff_pack_id:
        parts.append(f"handoff={route.handoff_pack_id}")
    return "; ".join(parts)


def natural_request_route_payload(result: NaturalRequestRouteResult) -> dict[str, object]:
    """Build a structured payload for Workbench/report route explanations."""

    selected = result.selected_route
    return {
        "query": result.query,
        "status": result.status,
        "selected_route_id": result.selected_route_id,
        "selected_pack_id": result.selected_pack_id,
        "selected_family_id": selected.family_id if selected is not None else "",
        "selected_profile_id": selected.profile_id if selected is not None else "",
        "selected_delivery_preset_id": (
            selected.delivery_preset_id if selected is not None else ""
        ),
        "plugin_gate_id": selected.plugin_gate_id if selected is not None else "",
        "handoff_pack_id": selected.handoff_pack_id if selected is not None else "",
        "handoff_family_id": selected.handoff_family_id if selected is not None else "",
        "disambiguation_prompt": result.disambiguation_prompt,
        "evidence_lines": list(result.evidence_lines),
        "candidate_route_ids": [match.route.route_id for match in result.matches[:5]],
        "candidate_pack_ids": [match.route.pack_id for match in result.matches[:5]],
        "summary": build_natural_request_route_summary(result),
    }


def audit_natural_request_router() -> dict[str, str]:
    """Audit route references and coverage-pack natural request aliases."""

    issues: dict[str, str] = {}
    route_ids: set[str] = set()
    alias_index = {_normalize_text(alias) for route in NATURAL_REQUEST_ROUTES for alias in route.aliases}
    for route in NATURAL_REQUEST_ROUTES:
        if not route.route_id:
            issues["route:<empty>"] = "route_id is required"
            continue
        if route.route_id in route_ids:
            issues[f"route:{route.route_id}"] = "duplicate route_id"
        route_ids.add(route.route_id)
        if not route.aliases:
            issues[f"route:{route.route_id}:aliases"] = "at least one alias is required"
        if route.pack_id not in SCENE_COVERAGE_PACK_MAP:
            issues[f"route:{route.route_id}:pack"] = f"unknown pack {route.pack_id}"
        if route.family_id:
            try:
                get_planned_scene_family(route.family_id)
            except KeyError:
                issues[f"route:{route.route_id}:family"] = f"unknown family {route.family_id}"
            else:
                pack_ids = {pack.pack_id for pack in coverage_packs_for_family(route.family_id)}
                if route.pack_id not in pack_ids:
                    issues[f"route:{route.route_id}:family_pack"] = (
                        f"{route.family_id} is not covered by {route.pack_id}"
                    )
        if route.handoff_pack_id and route.handoff_pack_id not in SCENE_COVERAGE_PACK_MAP:
            issues[f"route:{route.route_id}:handoff_pack"] = (
                f"unknown handoff pack {route.handoff_pack_id}"
            )
        if route.handoff_family_id:
            try:
                get_planned_scene_family(route.handoff_family_id)
            except KeyError:
                issues[f"route:{route.route_id}:handoff_family"] = (
                    f"unknown handoff family {route.handoff_family_id}"
                )
        if route.plugin_gate_id:
            gate = plugin_manual_gate_for_pack(route.pack_id)
            if gate is None:
                issues[f"route:{route.route_id}:plugin_gate"] = (
                    f"{route.pack_id} has no plugin/manual gate"
                )
            elif gate.gate_id != route.plugin_gate_id:
                issues[f"route:{route.route_id}:plugin_gate"] = (
                    f"expected gate {gate.gate_id}, got {route.plugin_gate_id}"
                )

    for pack in list_scene_coverage_packs():
        for natural_request in pack.natural_requests:
            normalized_alias = _normalize_text(natural_request)
            if normalized_alias not in alias_index:
                issues[f"pack:{pack.pack_id}:{natural_request}"] = (
                    "coverage pack natural request is not represented in router aliases"
                )
    return issues


def _match_route(
    route: NaturalRequestRoute,
    normalized_query: str,
) -> NaturalRequestRouteMatch | None:
    matched_aliases = tuple(
        alias for alias in route.aliases if _normalize_text(alias) in normalized_query
    )
    matched_context = tuple(
        token for token in route.context_tokens if _normalize_text(token) in normalized_query
    )
    matched_anti = tuple(
        token for token in route.anti_tokens if _normalize_text(token) in normalized_query
    )
    if not matched_aliases and not matched_context:
        return None
    score = 0
    if matched_aliases:
        score += max(120 + min(len(_normalize_text(alias)), 40) for alias in matched_aliases)
    score += 28 * len(matched_context)
    if route.route_type == "import_boundary" and any(
        _normalize_text(token)
        in {"pdf", "扫描", "ocr", "转word", "导入"}
        for token in matched_context
    ):
        score += 120
    score -= 45 * len(matched_anti)
    if score <= 0:
        return None
    return NaturalRequestRouteMatch(
        route=route,
        score=score,
        matched_aliases=matched_aliases,
        matched_context_tokens=matched_context,
        matched_anti_tokens=matched_anti,
    )


def _route_evidence_lines(
    route: NaturalRequestRoute,
    match: NaturalRequestRouteMatch,
) -> tuple[str, ...]:
    lines = [
        f"pack={route.pack_id}",
        f"route_type={route.route_type}",
    ]
    if route.family_id:
        lines.append(f"family={route.family_id}")
    if route.profile_id:
        lines.append(f"profile={route.profile_id}")
    if route.delivery_preset_id:
        lines.append(f"delivery={route.delivery_preset_id}")
    if route.plugin_gate_id:
        lines.append(f"plugin_gate={route.plugin_gate_id}")
    if route.handoff_pack_id:
        lines.append(f"handoff_pack={route.handoff_pack_id}")
    if route.handoff_family_id:
        lines.append(f"handoff_family={route.handoff_family_id}")
    if match.matched_aliases:
        lines.append("matched_aliases=" + ",".join(match.matched_aliases))
    if match.matched_context_tokens:
        lines.append("context=" + ",".join(match.matched_context_tokens))
    if route.reason:
        lines.append("reason=" + route.reason)
    return tuple(lines)


def _combined_disambiguation_prompt(
    matches: tuple[NaturalRequestRouteMatch, ...],
) -> str:
    prompts = _unique_texts(
        match.route.disambiguation_prompt
        for match in matches
        if match.route.disambiguation_prompt
    )
    if prompts:
        return " / ".join(prompts)
    labels = " / ".join(match.route.label for match in matches[:3])
    return f"请求同时命中多个方案落点，请在这些方向中选择：{labels}"


def _normalize_text(value: str) -> str:
    normalized = str(value or "").casefold()
    return re.sub(r"[\s\-_/\\:：,，.。;；、!！?？()（）\[\]【】{}<>《》]+", "", normalized)


def _unique_texts(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


__all__ = [
    "NATURAL_REQUEST_ROUTE_MAP",
    "NATURAL_REQUEST_ROUTES",
    "NaturalRequestRoute",
    "NaturalRequestRouteMatch",
    "NaturalRequestRouteResult",
    "audit_natural_request_router",
    "build_natural_request_route_summary",
    "get_natural_request_route",
    "list_natural_request_routes",
    "natural_request_route_payload",
    "route_natural_scene_request",
    "routes_for_coverage_pack",
]
