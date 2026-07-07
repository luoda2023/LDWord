"""Summary projection helpers for scene configuration surfaces."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from src.config.control_contract_registry import (
    ControlContractAuditResult,
    audit_control_contract_registry,
    list_control_contracts,
)
from src.config.delivery_preset_display import (
    DELIVERY_PRESET_DISPLAY_LABELS,
    delivery_preset_display_name,
)
from src.config.material_schema_registry import (
    build_material_requirements,
    list_material_schemas,
)
from src.config.scene_boundary_capability_matrix import (
    list_scene_boundary_capabilities,
)
from src.config.scene_parameter_ownership import (
    ALLOWED_PARAMETER_OWNER_LAYERS,
    ParameterOwnershipAuditResult,
    audit_scene_parameter_ownership,
    scene_parameter_ownership_specs,
)
from src.config.scene_product_readiness import (
    SceneProductReadinessSpec,
    product_readiness_for,
)
from src.config.scene_request_cell_fixture_registry import (
    SceneRequestCellFixtureSpec,
    SceneRequestCellFixtureSummary,
    build_scene_request_cell_fixture_summary,
    request_cell_fixtures_for_pack,
)
from src.config.scene_rule_source_governance import scene_rule_sources_for_pack
from src.config.scene_sample_fixture_registry import (
    SCENE_SAMPLE_FIXTURE_MAP,
    SceneSampleCoverageSummary,
    SceneSampleFixtureSpec,
    build_scene_sample_coverage_summary,
    scene_sample_fixtures_for_pack,
)
from src.config.style_variant_semantics import STYLE_VARIANTS, is_section_style_overridden
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
from src.config.scene_fixed_layout_profile_audit import (
    build_scene_fixed_layout_profile_audit_report,
)
from src.config.scene_matrix_dashboard import build_scene_matrix_dashboard
from src.config.scene_matrix_drilldown import build_scene_matrix_drilldown_report
from src.config.scene_family_registry import get_planned_scene_family
from src.config.scene_natural_request_router import route_natural_scene_request
from src.config.scene import SceneWorkspace
from src.shared.engine.count_engine import get_count_profile
from src.shared.engine.object_preflight import object_preflight_targets_for_touchpoints
from src.shared.ui.summary_grid import SummaryGridItem


MARKDOWN_POLICY_LABELS = {
    "disabled": "禁用",
    "cleanup_only": "仅清理",
    "preview_and_cleanup": "预览并清理",
}

LATEX_POLICY_LABELS = {
    "disabled": "禁用",
    "formula_fragments_only": "仅公式片段",
}

FAILURE_POLICY_LABELS = {
    "warn": "提示",
    "block": "阻断",
}

PRESERVATION_MODE_LABELS = {
    "warn": "提示",
    "strict": "严格",
}

REQUEST_CELL_COVERAGE_DISPLAY_LABELS = {
    "direct_family_fixture": "直接证据",
    "manual_boundary_fixture": "人工确认",
    "ambiguous_fixture_set": "容易误解",
    "negative_control": "不处理样本",
    "pack_fixture_proxy": "借用样本",
}

REQUEST_CELL_FILTER_ALL_ID = "all"
REQUEST_CELL_FILTER_OPTIONS = (
    (REQUEST_CELL_FILTER_ALL_ID, "全部说法"),
    *tuple(REQUEST_CELL_COVERAGE_DISPLAY_LABELS.items()),
)


@dataclass(frozen=True, slots=True)
class SceneRequestCellListItemProjection:
    sample_id: str
    text: str
    tooltip: str


@dataclass(frozen=True, slots=True)
class SceneSampleFixtureListItemProjection:
    fixture_id: str
    text: str
    tooltip: str

FORMAT_DISPLAY_LABELS = {
    "docx": "Word 文档",
    "markdown": "Markdown",
    "md": "Markdown",
    "xlsx": "Excel 表格",
    "xls": "Excel 表格",
    "json": "结构化数据",
    "csv": "CSV 表格",
    "bibtex": "BibTeX 文献",
    "csl_json": "CSL 文献",
    "pdf": "PDF",
}

MATERIAL_SCHEMA_DISPLAY_LABELS = {
    "bid_materials_v1": "标书资料",
    "official_document_v1": "公文字段资料",
    "technical_document_v1": "技术文档资料",
    "journal_materials_v1": "期刊资料",
    "thesis_school_rule_context_v1": "学校论文规则资料",
    "journal_submission_materials_v1": "期刊投稿资料",
    "exam_items_v1": "试卷题目资料",
    "teaching_assets_v1": "教学素材",
    "project_application_materials_v1": "项目申报资料",
    "contract_parties_v1": "合同方字段资料",
    "signature_assets_v1": "签章资料",
    "personnel_records_v1": "人员记录资料",
    "administrative_meeting_fields_v1": "公文/会议字段资料",
    "product_assets_v1": "产品资料",
    "case_study_assets_v1": "案例资料",
    "long_document_metadata_v1": "长文档元数据",
    "form_batch_fields_v1": "表单字段资料",
    "qualification_archive_assets_v1": "资质归档资料",
    "finance_quote_fields_v1": "报价字段资料",
    "patent_document_fields_v1": "专利字段资料",
    "bilingual_terms_v1": "双语术语资料",
    "regulated_disclosure_materials_v1": "披露材料资料",
}

MATERIAL_FIELD_DISPLAY_LABELS = {
    "company_name": "公司名称",
    "project_name": "项目名称",
    "legal_person": "法定代表人",
    "bid_date": "投标日期",
    "address": "公司地址",
    "consortium_lead": "联合体牵头方",
    "consortium_members": "联合体成员",
    "consortium_roles": "联合体分工",
    "organization": "机构名称",
    "document_no": "文件编号",
    "issue_date": "发布日期",
    "issuer": "签发人",
    "recipient": "接收方",
    "document_type": "文件类型",
    "security_level": "密级",
    "urgency": "紧急程度",
    "signer": "签署人",
    "copy_scope": "抄送范围",
    "archive_status": "归档状态",
    "archive_no": "归档编号",
    "retention_period": "保管期限",
    "document_title": "文档标题",
    "version": "版本",
    "owner": "负责人",
    "index_scope": "索引范围",
    "appendix_scope": "附录范围",
    "source_file_manifest": "源文件清单",
    "author": "作者",
    "affiliation": "作者单位",
    "school_rule_source_id": "学校规则来源",
    "section_classifier_decisions": "章节识别确认",
    "school_name": "学校名称",
    "rule_source_version": "规则版本",
    "reviewed_by": "规则复核人",
    "reviewed_on": "规则复核日期",
    "confirmed_by": "识别确认人",
    "confirmed_at": "识别确认时间",
    "article_title": "文章标题",
    "corresponding_author": "通讯作者",
    "journal_name": "期刊名称",
    "target_journal_profile_id": "目标期刊规则",
    "reviewed_rule_source_id": "已复核规则来源",
    "submission_package_manifest": "投稿材料清单",
    "citation_source_manifest": "引用来源清单",
    "publisher_boundary_note": "出版社边界说明",
    "paper_title": "试卷标题",
    "subject": "学科",
    "grade": "年级",
    "duration": "考试时长",
    "total_score": "总分",
    "course_name": "课程名称",
    "teacher_name": "教师姓名",
    "class_name": "班级名称",
    "applicant_unit": "申报单位",
    "principal_investigator": "项目负责人",
    "budget_total": "预算总额",
    "submission_system_id": "提交系统",
    "party_a": "甲方",
    "party_b": "乙方",
    "contract_amount": "合同金额",
    "signing_date": "签署日期",
    "contract_no": "合同编号",
    "employee_name": "员工姓名",
    "employee_id": "员工编号",
    "department": "部门",
    "position": "岗位",
    "effective_date": "生效日期",
    "meeting_title": "会议标题",
    "meeting_date": "会议日期",
    "participants": "参会人员",
    "product_name": "产品名称",
    "product_version": "产品版本",
    "product_model": "产品型号",
    "asset_source_manifest": "素材来源清单",
    "quote_boundary_signal": "报价边界提示",
    "customer_name": "客户名称",
    "case_title": "案例标题",
    "case_evidence_source": "案例证据来源",
    "case_approval_status": "案例授权状态",
    "title": "标题",
    "editor": "编辑",
    "merge_boundary_notes": "合并边界说明",
    "form_title": "表单标题",
    "record_id": "记录编号",
    "applicant_name": "申请人姓名",
    "package_name": "资料包名称",
    "certificate_no": "证书编号",
    "license_no": "营业执照编号",
    "valid_from": "有效期开始",
    "valid_until": "有效期结束",
    "consortium_member_name": "联合体成员名称",
    "consortium_member_role": "联合体成员角色",
    "quote_no": "报价单号",
    "amount": "金额",
    "currency": "币种",
    "invention_title": "发明名称",
    "applicant": "申请人",
    "inventor": "发明人",
    "technical_field": "技术领域",
    "review_owner": "复核负责人",
    "source_language": "源语言",
    "target_language": "目标语言",
    "reviewer": "审阅人",
    "termbase_name": "术语库名称",
    "report_period": "报告期间",
    "report_type": "报告类型",
    "board_meeting_date": "董事会会议日期",
    "public_release_date": "公开披露日期",
}

MATERIAL_ASSET_ROLE_DISPLAY_LABELS = {
    "logo": "企业标志",
    "seal": "印章",
    "qualification": "资质证书",
    "diagram": "图示",
    "figure": "图片",
    "graphical_abstract": "图文摘要",
    "cover_image": "封面图",
    "question_figure": "题目图片",
    "handout_cover": "讲义封面",
    "teaching_diagram": "教学图示",
    "application_form": "申报表",
    "budget_sheet": "预算表",
    "legal_signature": "法定代表签名",
    "agent_signature": "经办人签名",
    "portrait": "头像",
    "signature": "签名",
    "product_image": "产品图片",
    "case_image": "案例图片",
    "cover": "封面图片",
    "certificate": "资质证书",
    "business_license": "营业执照",
    "attachment": "附件",
    "table_source": "表格来源",
    "disclosure_attachment": "披露附件",
    "term_table": "术语表",
}

REPORT_LEVEL_DISPLAY_LABELS = {
    "summary": "简要报告",
    "detailed": "详细报告",
    "none": "不生成报告",
}

PROFILE_DISPLAY_LABELS = {
    "basic": "基础格式检查",
    "custom_basic": "基础格式检查",
    "basic_format": "基础格式规则",
    "contract_delivery": "合同交付规则",
    "thesis_cn": "中文论文规则",
    "school_thesis": "学校论文规则",
    "journal_submission": "期刊投稿规则",
    "journal_revision": "期刊返修规则",
}

OWNER_LAYER_DISPLAY_LABELS = {
    "template": "模板管样式",
    "scene": "场景管流程",
    "material": "资料管输入",
    "output": "输出管版本",
    "plugin": "插件管人工确认",
}

COVERAGE_PACK_DISPLAY_LABELS = {
    "quick_formatting": "通用格式清理",
    "chinese_academic": "中文论文/课程论文",
    "english_journal": "英文期刊投稿",
    "exam_education": "试卷/教学资料",
    "bidding_materials": "标书/资质包",
    "official_policy": "公文/会议纪要",
    "technical_long_docs": "技术长文档",
    "application_reports": "项目申报/产品材料",
    "contract_delivery": "合同交付",
    "batch_forms": "批量表单/套打",
    "professional_disclosure": "专业披露/审阅",
    "import_ai_boundary": "导入与 AI 辅助",
}

FAMILY_DISPLAY_LABELS = {
    "thesis_cn": "中文论文/课程论文",
    "journal_en": "英文期刊投稿",
    "exam_teaching": "试卷/教学资料",
    "qualification_archive_packages": "标书/资质归档",
    "meeting_policy_documents": "公文/会议材料",
    "long_document_publishing": "技术长文档",
    "project_application": "项目申报材料",
    "product_sales_documents": "产品/售前材料",
    "contract_delivery": "合同交付",
    "hr_batch_documents": "人事批量文档",
    "form_batch_documents": "批量表单/套打",
    "finance_quote_documents": "报价/财务材料",
    "regulated_disclosure_documents": "披露/审阅材料",
    "ip_patent_documents": "知识产权/专利材料",
    "bilingual_translation_documents": "双语审阅材料",
}

SCENE_SCOPE_ZONE_DISPLAY_LABELS = {
    "body": "正文",
    "references": "参考文献",
    "acknowledgment": "致谢",
    "appendix": "附录",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
    "toc": "目录",
    "errata": "勘误页",
    "resume": "个人简历",
}

SCENE_SCOPE_ZONE_ORDER = tuple(SCENE_SCOPE_ZONE_DISPLAY_LABELS)

SCENE_APPLICATION_BOUNDARY_DISPLAY_LABELS = {
    "follow_template": "按模板默认",
    "body_only": "只处理正文",
    "full_document": "处理全文",
    "confirm_before_apply": "每次执行前选择",
}

SCENE_APPLICATION_BOUNDARY_DETAILS = {
    "follow_template": "模板负责识别正文、附录等区域。",
    "body_only": "只处理模板识别出的正文内容。",
    "full_document": "处理当前文档的所有可处理内容。",
    "confirm_before_apply": "每次执行前选择要处理的范围。",
}

WORKFLOW_DISPLAY_LABELS = {
    "template_normalization": "套用模板",
    "scope_localization": "按范围处理",
    "object_safety": "保护 Word 对象",
    "submission_archive": "生成交付包",
    "structured_input": "读取结构化资料",
    "material_fill": "填充资料",
    "field_consistency": "核对字段一致性",
    "review_compare": "审阅/对比",
    "batch_generation": "批量生成",
    "failure_isolation": "隔离失败项",
    "fixed_layout_table": "固定版式表格",
    "placeholder_fill": "填充占位字段",
    "residue_check": "检查残留内容",
    "placeholder_residue": "检查占位残留",
    "content_visibility": "控制版本显隐",
    "count_compliance": "按规则计数",
    "compliance_counting": "按规则计数",
    "citation_reference": "处理引用文献",
    "references_citations": "处理引用文献",
    "formula_symbol": "处理公式符号",
    "formula_symbols": "处理公式符号",
    "plugin_manual_gate": "人工/插件确认",
    "asset_attachment_inventory": "整理附件素材",
    "image_table_assets": "核对图片和表格资料",
    "delivery_package": "生成交付包",
    "submission_package": "生成提交包",
    "signing_package": "生成签署稿",
    "formal_internal_delivery": "正式归档交付",
    "customer_internal_delivery": "客户/内部版本交付",
    "archive_package": "归档打包",
    "attachment_inventory": "整理附件清单",
    "official_fields": "核对公文字段",
    "preserve_numbering": "保留原编号",
    "collection_archive": "整理归档资料",
    "chapter_inventory": "整理章节清单",
    "cross_reference_protection": "保护交叉引用",
}

OOXML_TOUCHPOINT_DISPLAY_LABELS = {
    "paragraph": "段落",
    "paragraph_run": "正文片段",
    "run": "文字片段",
    "styles": "样式",
    "numbering": "编号",
    "table": "表格",
    "table_grid": "表格",
    "fixed_row_height": "固定行高",
    "drawing": "图片/形状",
    "drawing_media_rels": "图片关系",
    "field": "域",
    "fields": "域",
    "header_footer": "页眉页脚",
    "headers_footers": "页眉页脚",
    "section": "分节",
    "footnote": "脚注",
    "footnotes_endnotes": "脚注/尾注",
    "endnote": "尾注",
    "comments_revisions": "批注/修订",
    "comment": "批注",
    "comments": "批注",
    "revision": "修订",
    "tracked_changes": "修订",
    "hidden_text": "隐藏文字",
    "textbox_shape": "文本框",
    "textboxes": "文本框",
    "content_controls": "内容控件",
    "ole_objects": "嵌入对象",
    "ole_embedded_vba": "宏/嵌入对象",
    "embedded_workbooks": "嵌入表格",
    "embedded_packages": "嵌入附件",
    "visio_drawings": "Visio 图",
    "macros": "宏",
    "relationship": "文件关系",
    "package_relationships": "文件关系",
}

BEHAVIOR_DISPLAY_LABELS = {
    "detect": "先检测",
    "preserve_layout": "保留版式",
    "manual_confirmation": "人工确认",
    "skip_report": "跳过并报告",
    "block_report": "阻断并报告",
}

PRODUCT_READINESS_DISPLAY_LABELS = {
    "gray_l1": "刚开始接入",
    "blue_boundary": "需人工/插件把关",
    "yellow_l3": "可试用",
    "orange_l4": "基本可用",
    "green_l5": "可直接使用",
}

PRODUCT_READINESS_DETAIL_LABELS = {
    "gray_l1": "只登记了方向，还不适合直接交付",
    "blue_boundary": "核心格式流程可用，专业判断需要人工或插件确认",
    "yellow_l3": "已有主要流程，但还需要补齐边界和样本",
    "orange_l4": "主要流程已闭合，仍有少量产品化缺口",
    "green_l5": "核心流程、样本和交付证据已闭合",
}

BOUNDARY_TEXT_DISPLAY_LABELS = {
    "does not judge professional compliance": "不判断专业合规，只处理格式和对象风险",
    "does not absorb English journal submission or exam generation": "不混入英文投稿或试卷生成场景",
    "does not promise publisher-final layout or unreviewed rule fetching": "不承诺出版社最终版式；目标期刊规则需人工确认",
    "does not guarantee AI content quality or complex diagram generation": "不保证 AI 内容质量或复杂图生成",
    "does not judge bidding strategy, legal conclusions, or certificate authenticity": "不判断投标策略、法律结论或证书真伪",
    "does not create many small administrative top-level scenes": "不为每类小公文单独开顶层场景",
    "does not verify technical truth or replace publisher systems": "不校验技术内容真伪，也不替代发布系统",
    "does not replace submission systems or promise marketing copy quality": "不替代申报系统，也不保证营销文案质量",
    "does not provide legal advice or judge clause validity": "不提供法律意见，也不判断条款有效性",
    "does not verify personnel or business data truthfulness": "不核验人员或业务数据真伪",
    "does not perform audit, legal, patent, finance, or translation-quality judgment": "不做审计、法律、专利、财务或翻译质量判断",
    "core does not promise lossless import or content quality": "核心功能不承诺无损导入或内容质量",
    "General formatting must preserve field/comment awareness.": "清理格式时会保留域和批注，不会静默改写高风险对象",
    (
        "Quick cleanup should preserve field/comment layout and warn instead of "
        "rewriting risky Word objects."
    ): "清理格式时会保留域和批注；遇到高风险对象先提醒",
    (
        "Business templates can be cleaned through template field repair "
        "without making professional or content-quality promises."
    ): "可清理业务模板字段，但不承诺专业判断或内容质量",
    "Contract samples do not imply legal review.": "合同样本只验证格式和字段，不代表法律审查",
    (
        "Missing or inconsistent contract party, amount, date, or signature "
        "assets should downgrade to a field/signature boundary report."
    ): "合同方、金额、日期或签章资料不一致时，会降级为字段/签章边界报告",
    "Fixed-layout row height is not generic table styling.": "固定行高只用于套打/固定版式，不当作通用表格样式",
    "HR batch samples do not verify personnel truthfulness.": "人事批量样本不核验人员信息真伪",
    "Disclosure samples do not perform audit or assurance judgment.": "披露样本不执行审计或鉴证判断",
    "Import samples require confidence/manual confirmation before core execution.": "导入样本需要置信度检查或人工确认后再执行",
    "Bid strategy and certificate truthfulness remain outside core.": "不判断投标策略，也不核验证照真实性",
    (
        "Missing certificate, license, or required archive assets should "
        "downgrade to an attachment inventory and missing-items report."
    ): "证照或归档资料缺失时，会降级为附件清单和缺项报告",
}


def build_scene_overview_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    input_profile = scene.input_source_profile
    compliance = scene.compliance_profile
    preflight = compliance.object_preflight
    delivery_ids = [preset.preset_id for preset in scene.delivery_presets]
    default_delivery = _delivery_preset_for_id(scene, scene.default_delivery_preset_id)

    items = (
        SummaryGridItem(
            key="input_profile",
            label="输入",
            value=_format_list_label(input_profile.accepted_formats),
            detail=_input_policy_detail(scene),
            variant="info",
            icon_name="inbox",
        ),
        SummaryGridItem(
            key="compliance_profile",
            label="处理方式",
            value=_compliance_overview_value(compliance),
            detail=_compliance_overview_detail(compliance),
            variant=_failure_variant(compliance.failure_policy),
            icon_name="scan",
        ),
        SummaryGridItem(
            key="object_preflight",
            label="对象风险",
            value=_object_policy_value(preflight),
            detail=_object_policy_detail(scene),
            variant="warning" if preflight.preservation_mode == "strict" else "neutral",
            icon_name="shield-alert",
        ),
        SummaryGridItem(
            key="delivery",
            label="输出",
            value=_delivery_preset_display_name(default_delivery or _first_or_empty(delivery_ids)),
            detail=_delivery_overview_detail(scene),
            variant="success" if delivery_ids else "warning",
            icon_name="package-check",
        ),
    )
    return (
        *items,
        *build_parameter_ownership_summary_items(scene),
        *build_control_contract_summary_items(),
        *build_planning_family_summary_items(scene),
        *build_coverage_summary_items(scene),
        *build_academic_rule_source_evidence_summary_items(scene),
        *build_journal_submission_evidence_summary_items(scene),
        *build_contract_field_evidence_summary_items(scene),
        *build_bidding_archive_evidence_summary_items(scene),
        *build_official_policy_evidence_summary_items(scene),
        *build_technical_long_doc_evidence_summary_items(scene),
        *build_application_report_evidence_summary_items(scene),
        *build_fixed_layout_batch_evidence_summary_items(scene),
        *build_boundary_capability_evidence_summary_items(scene),
        *build_product_readiness_summary_items(scene),
        *build_scene_sample_fixture_summary_items(scene),
        *build_scene_request_cell_summary_items(scene),
    )


def build_scene_scope_summary_items(
    scene: SceneWorkspace | None,
) -> tuple[SummaryGridItem, ...]:
    """Return summary items for the scene application boundary."""

    mode = scene_application_boundary_mode(scene)
    label = scene_application_boundary_display_name(scene)
    detail = scene_application_boundary_detail(scene)
    if scene is None:
        value = "选择处理范围"
        detail = "模板负责识别正文、附录等区域。"
        variant = "info"
    elif mode == "confirm_before_apply":
        value = label
        variant = "warning"
    else:
        value = label
        variant = "info"

    return (
        SummaryGridItem(
            key="main_controls",
            label="处理范围",
            value=value,
            detail=detail,
            variant=variant,
        ),
    )


def build_scene_style_override_summary_items(
    scene: SceneWorkspace | None,
    projection=None,
    variants=None,
) -> tuple[SummaryGridItem, ...]:
    """Return summary items for scene section-style override state."""

    style_variants = tuple(variants) if variants is not None else STYLE_VARIANTS
    overridden = [
        variant.label
        for variant in style_variants
        if scene is not None and is_section_style_overridden(scene, variant.key)
    ]
    if overridden:
        status_value = f"{len(overridden)} 个格式例外"
        status_detail = "、".join(overridden)
    else:
        status_value = "无格式例外"
        status_detail = "默认跟随模板；需要局部不同时再添加例外。"

    items = [
        SummaryGridItem(
            key="override_status",
            label="例外状态",
            value=status_value,
            detail=status_detail,
            variant="info",
        )
    ]
    if projection is not None:
        items.append(
            SummaryGridItem(
                key="current_variant_status",
                label="当前例外",
                value=f"{projection.label} · {projection.status_value}",
                detail=projection.status_detail,
                variant=projection.variant,
            )
        )
    items.append(
        SummaryGridItem(
            key="owner_boundary",
            label="样式边界",
            value="仅当前场景",
            detail="全局默认样式在模板管理中修改。",
            variant="warning",
        )
    )
    return tuple(items)


def build_scene_matrix_dashboard_summary_items() -> tuple[SummaryGridItem, ...]:
    dashboard = build_scene_matrix_dashboard()
    payload = dashboard.to_payload()
    counts = payload["counts"]
    return (
        SummaryGridItem(
            key="scene_matrix_dashboard",
            label="Matrix dashboard",
            value=f"{dashboard.visible_count}/{dashboard.total_count} packs",
            detail=(
                f"high_frequency_coverage="
                f"{counts['high_frequency_completeness_ready_pack_count']}/"
                f"{dashboard.total_count} / "
                f"{counts['family_count']} families / "
                f"{counts['family_fixture_depth_p1_ready_count']}/"
                f"{counts['family_fixture_depth_p1_family_count']} P1 fixtures / "
                f"{counts['task_lexicon_task_count']} task families / "
                f"{counts['ambiguous_boundary_pack_pair_count']} ambiguous pairs / "
                f"{counts['ambiguity_clarification_ready_count']}/"
                f"{counts['ambiguity_clarification_count']} clarifications / "
                f"{counts['import_handoff_count']} handoff / "
                f"{counts['input_source_ready_input_pack_count']}/"
                f"{counts['input_source_input_pack_count']} input packs / "
                f"{counts['request_cell_count']} request cells / "
                f"{counts['user_journey_path_count']} user journeys"
                f" / {counts['business_capability_matrix_ready_count']}/"
                f"{counts['business_capability_matrix_count']} business capabilities"
            ),
            variant="success" if dashboard.status == "passed" else "warning",
            icon_name="layout-dashboard",
            tooltip=_scene_matrix_dashboard_tooltip(dashboard),
        ),
        SummaryGridItem(
            key="scene_matrix_boundary",
            label="Boundary signals",
            value=f"{counts['plugin_boundary_pack_count']} plugin packs",
            detail=(
                f"{counts['manual_boundary_pack_count']} manual-boundary packs / "
                f"{counts['ambiguous_pack_count']} ambiguous packs / "
                f"{counts['ambiguous_boundary_pack_pair_count']} ambiguous pairs / "
                f"{counts['import_handoff_count']} handoff / "
                f"{counts['plugin_boundary_gate_count']} gates / "
                f"{counts['plugin_boundary_risk_domain_count']} risk domains / "
                f"{counts['external_handoff_contract_ready_count']}/"
                f"{counts['external_handoff_contract_count']} external handoffs / "
                f"{counts['boundary_guarded_completion_ready_count']}/"
                f"{counts['boundary_guarded_completion_subject_count']} guarded / "
                f"{counts['residual_warning_governance_managed_count']}/"
                f"{counts['residual_warning_governance_warning_count']} managed warnings / "
                f"{counts['residual_warning_governance_input_source_managed_warning_count']}/"
                f"{counts['input_source_warning_count']} input warnings managed / "
                f"{counts['residual_warning_governance_count_profile_managed_warning_count']}/"
                f"{counts['count_profile_warning_count']} count warnings managed / "
                f"{counts['residual_warning_governance_plugin_manual_managed_warning_count']}/"
                f"{counts['residual_warning_governance_plugin_manual_warning_count']} plugin/manual warnings managed / "
                f"{counts['residual_warning_governance_reference_profile_managed_warning_count']}/"
                f"{counts['residual_warning_governance_reference_profile_warning_count']} reference warnings managed / "
                f"{counts['residual_warning_governance_visio_fixture_verified_count']}/"
                f"{counts['residual_warning_governance_visio_fixture_closed_count']} Visio fixture closed / "
                f"{counts['dashboard_warning_projection_governed_count']}/"
                f"{dashboard.warning_count} dashboard warnings governed / "
                f"{counts['boundary_readiness_reconciliation_reconciled_count']}/"
                f"{counts['boundary_readiness_reconciliation_count']} readiness reconciled / "
                f"{counts['terminal_release_exception_governed_count']}/"
                f"{counts['terminal_release_exception_count']} release exceptions / "
                f"{counts['static_closed_not_green_governed_count']}/"
                f"{counts['static_closed_but_not_green_count']} static-closed governed / "
                f"{counts['terminal_release_exception_trace_count']} exception traces / "
                f"{counts['boundary_subject_release_dossier_ready_count']}/"
                f"{counts['boundary_subject_release_dossier_subject_count']} boundary dossiers / "
                f"{counts['non_subject_release_trace_attribution_ready_count']}/"
                f"{counts['non_subject_release_trace_attribution_count']} non-subject traces / "
                f"{counts['release_trace_partition_guard_partitioned_trace_count']}/"
                f"{counts['release_trace_partition_guard_terminal_trace_count']} trace partition / "
                f"{counts['release_projection_surface_parity_ready_count']}/"
                f"{counts['release_projection_surface_parity_count']} release projections / "
                f"{counts['boundary_subject_release_continuity_ready_count']}/"
                f"{counts['boundary_subject_release_continuity_subject_count']} subject continuity / "
                f"{counts['release_closure_ledger_ready_count']}/"
                f"{counts['release_closure_ledger_stage_count']} release ledger / "
                f"{counts['boundary_maturity_release_envelope_ready_count']}/"
                f"{counts['boundary_maturity_release_envelope_count']} boundary release envelopes / "
                f"{counts['boundary_maturity_release_envelope_l5_blocker_enveloped_count']}/"
                f"{counts['maturity_upgrade_l5_blocked_subject_count']} L5 blockers enveloped / "
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count']} "
                "L5 blockers aligned / "
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count']} "
                "L5 receipts aligned / "
                f"{counts['retained_gap_enveloped_count']}/"
                f"{counts['maturity_upgrade_gap_count']} retained gaps enveloped / "
                f"{counts['retained_gap_exit_criteria_release_allowed_count']}/"
                f"{counts['retained_gap_exit_criteria_count']} retained gap exit criteria / "
                f"{counts['retained_gap_external_receipt_alignment_count']}/"
                f"{counts['retained_gap_exit_criteria_count']} retained gap receipts / "
                f"{counts['maturity_upgrade_gap_domain_classified_count']}/"
                f"{counts['maturity_upgrade_gap_domain_count']} gap domains classified / "
                f"{counts['release_residual_ratio_ledger_published_count']}/"
                f"{counts['release_residual_ratio_ledger_count']} release residual ratios / "
                f"{counts['release_residual_ratio_ledger_exit_criteria_link_count']} "
                "residual ratio exit criteria / "
                f"{counts['release_residual_ratio_ledger_receipt_alignment_link_count']} "
                "residual ratio receipts / "
                f"{counts['release_residual_ratio_ledger_count_delivery_boundary_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_count_delivery_boundary_link_count']} "
                "count/delivery boundary links aligned / "
                f"{counts['release_residual_ratio_ledger_count_delivery_receipt_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count']} "
                "count/delivery receipts aligned / "
                f"{counts['release_residual_ratio_ledger_boundary_scope_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_boundary_scope_link_count']} "
                "boundary scopes guarded / "
                f"{counts['release_residual_explanation_covered_count']}/"
                f"{counts['release_residual_explanation_count']} residual explanations / "
                f"{counts['release_acceptance_certificate_ready_count']}/"
                f"{counts['release_acceptance_certificate_count']} release acceptance certificate / "
                f"{counts['release_acceptance_certificate_ready_receipt_count']}/"
                f"{counts['release_acceptance_certificate_receipt_count']} "
                "receipt certificates / "
                f"{counts['release_acceptance_certificate_ready_requirement_dimension_count']}/"
                f"{counts['release_acceptance_certificate_requirement_dimension_count']} "
                "requirement dimensions / "
                f"{counts['release_acceptance_certificate_ready_source_evidence_count']}/"
                f"{counts['release_acceptance_certificate_source_evidence_count']} acceptance evidence"
            ),
            variant="info",
            icon_name="route",
            tooltip=_scene_matrix_dashboard_tooltip(dashboard),
        ),
        SummaryGridItem(
            key="scene_matrix_evidence",
            label="Evidence chain",
            value=f"{counts['word_risk_surface_count']} Word risks",
            detail=(
                f"{counts['sample_fixture_count']} DOCX fixtures / "
                f"{counts['user_journey_path_count']} user journeys / "
                f"{counts['business_capability_matrix_ready_count']}/"
                f"{counts['business_capability_matrix_count']} business capabilities / "
                f"{counts['ambiguity_clarification_count']} clarifications / "
                f"{counts['family_fixture_depth_p1_ready_count']} P1 family fixtures / "
                f"{counts['object_preflight_action_ready_target_count']}/"
                f"{counts['object_preflight_action_target_count']} ObjectPreflight actions / "
                f"{counts['count_profile_ready_family_count']}/"
                f"{counts['count_profile_family_count']} CountProfile families / "
                f"{counts['count_profile_accounted_family_count']}/"
                f"{counts['count_profile_family_count']} CountProfile accounted / "
                f"{counts['input_source_ready_family_count']} InputSourceProfile families / "
                f"{counts['material_schema_ready_material_family_count']} material families / "
                f"{counts['material_repair_flow_ready_count']}/"
                f"{counts['material_repair_flow_count']} material repair flows / "
                f"{counts['fixed_layout_profile_ready_channel_count']}/"
                f"{counts['fixed_layout_profile_channel_count']} fixed-layout profile / "
                f"{counts['report_artifact_drilldown_ready_channel_count']}/"
                f"{counts['report_artifact_drilldown_channel_count']} report/artifact drilldown / "
                f"{counts['delivery_preset_ready_family_count']}/"
                f"{counts['delivery_preset_family_count']} delivery families / "
                f"{counts['delivery_preset_accounted_family_count']}/"
                f"{counts['delivery_preset_family_count']} delivery accounted / "
                f"{counts['delivery_execution_ready_channel_count']}/"
                f"{counts['delivery_execution_channel_count']} delivery execution / "
                f"{counts['formula_output_watermark_ready_capability_count']}/"
                f"{counts['formula_output_watermark_capability_count']} F/O/W / "
                f"{counts['formula_output_watermark_accounted_family_count']}/"
                f"{counts['formula_output_watermark_family_count']} F/O/W families accounted / "
                f"{counts['external_handoff_contract_ready_count']}/"
                f"{counts['external_handoff_contract_count']} handoff contracts / "
                f"{counts['boundary_guarded_completion_ready_count']}/"
                f"{counts['boundary_guarded_completion_subject_count']} guarded completions / "
                f"{counts['residual_warning_governance_managed_count']}/"
                f"{counts['residual_warning_governance_warning_count']} managed warnings / "
                f"{counts['residual_warning_governance_input_source_managed_warning_count']}/"
                f"{counts['input_source_warning_count']} input warnings managed / "
                f"{counts['residual_warning_governance_count_profile_managed_warning_count']}/"
                f"{counts['count_profile_warning_count']} count warnings managed / "
                f"{counts['residual_warning_governance_plugin_manual_managed_warning_count']}/"
                f"{counts['residual_warning_governance_plugin_manual_warning_count']} plugin/manual warnings managed / "
                f"{counts['residual_warning_governance_reference_profile_managed_warning_count']}/"
                f"{counts['residual_warning_governance_reference_profile_warning_count']} reference warnings managed / "
                f"{counts['residual_warning_governance_visio_fixture_verified_count']}/"
                f"{counts['residual_warning_governance_visio_fixture_closed_count']} Visio fixture closed / "
                f"{counts['dashboard_warning_projection_governed_count']}/"
                f"{dashboard.warning_count} dashboard warnings governed / "
                f"{counts['boundary_readiness_reconciliation_reconciled_count']}/"
                f"{counts['boundary_readiness_reconciliation_count']} readiness reconciled / "
                f"{counts['terminal_release_exception_governed_count']}/"
                f"{counts['terminal_release_exception_count']} release exceptions / "
                f"{counts['static_closed_not_green_governed_count']}/"
                f"{counts['static_closed_but_not_green_count']} static-closed governed / "
                f"{counts['terminal_release_exception_trace_count']} exception traces / "
                f"{counts['boundary_subject_release_dossier_ready_count']}/"
                f"{counts['boundary_subject_release_dossier_subject_count']} boundary dossiers / "
                f"{counts['non_subject_release_trace_attribution_ready_count']}/"
                f"{counts['non_subject_release_trace_attribution_count']} non-subject traces / "
                f"{counts['release_trace_partition_guard_partitioned_trace_count']}/"
                f"{counts['release_trace_partition_guard_terminal_trace_count']} trace partition / "
                f"{counts['release_projection_surface_parity_ready_count']}/"
                f"{counts['release_projection_surface_parity_count']} release projections / "
                f"{counts['boundary_subject_release_continuity_ready_count']}/"
                f"{counts['boundary_subject_release_continuity_subject_count']} subject continuity / "
                f"{counts['release_closure_ledger_ready_count']}/"
                f"{counts['release_closure_ledger_stage_count']} Release closure ledger / "
                f"{counts['boundary_maturity_release_envelope_ready_count']}/"
                f"{counts['boundary_maturity_release_envelope_count']} boundary release envelopes / "
                f"{counts['boundary_maturity_release_envelope_l5_blocker_enveloped_count']}/"
                f"{counts['maturity_upgrade_l5_blocked_subject_count']} L5 blockers enveloped / "
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_release_envelope_count']} "
                "L5 blockers aligned / "
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count']} "
                "L5 receipts aligned / "
                f"{counts['retained_gap_enveloped_count']}/"
                f"{counts['maturity_upgrade_gap_count']} retained gaps enveloped / "
                f"{counts['retained_gap_exit_criteria_release_allowed_count']}/"
                f"{counts['retained_gap_exit_criteria_count']} retained gap exit criteria / "
                f"{counts['retained_gap_external_receipt_alignment_count']}/"
                f"{counts['retained_gap_exit_criteria_count']} retained gap receipts / "
                f"{counts['maturity_upgrade_gap_domain_classified_count']}/"
                f"{counts['maturity_upgrade_gap_domain_count']} gap domains classified / "
                f"{counts['release_residual_ratio_ledger_published_count']}/"
                f"{counts['release_residual_ratio_ledger_count']} release residual ratios / "
                f"{counts['release_residual_ratio_ledger_exit_criteria_link_count']} "
                "residual ratio exit criteria / "
                f"{counts['release_residual_ratio_ledger_receipt_alignment_link_count']} "
                "residual ratio receipts / "
                f"{counts['release_residual_ratio_ledger_count_delivery_boundary_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_count_delivery_boundary_link_count']} "
                "count/delivery boundary links aligned / "
                f"{counts['release_residual_ratio_ledger_count_delivery_receipt_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count']} "
                "count/delivery receipts aligned / "
                f"{counts['release_residual_ratio_ledger_boundary_scope_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_boundary_scope_link_count']} "
                "boundary scopes guarded / "
                f"{counts['release_residual_explanation_covered_count']}/"
                f"{counts['release_residual_explanation_count']} residual explanations / "
                f"{counts['release_acceptance_certificate_ready_count']}/"
                f"{counts['release_acceptance_certificate_count']} release acceptance certificate / "
                f"{counts['release_acceptance_certificate_ready_receipt_count']}/"
                f"{counts['release_acceptance_certificate_receipt_count']} "
                "receipt certificates / "
                f"{counts['release_acceptance_certificate_ready_requirement_dimension_count']}/"
                f"{counts['release_acceptance_certificate_requirement_dimension_count']} "
                "requirement dimensions / "
                f"{counts['release_acceptance_certificate_ready_source_evidence_count']}/"
                f"{counts['release_acceptance_certificate_source_evidence_count']} acceptance evidence / "
                f"{counts['control_contract_count']} control contracts / "
                f"{counts['control_runtime_ready_control_count']}/"
                f"{counts['control_runtime_control_count']} control runtime"
            ),
            variant="success" if dashboard.issue_count == 0 else "warning",
            icon_name="scan",
            tooltip=_scene_matrix_dashboard_tooltip(dashboard),
        ),
        SummaryGridItem(
            key="scene_matrix_readiness",
            label="Readiness",
            value=f"{counts['product_readiness_subject_count']} subjects",
            detail=(
                f"{counts['static_closed_not_green_governed_count']}/"
                f"{counts['static_closed_but_not_green_count']} static-closed "
                "governed below Green/L5 / "
                f"{counts['maturity_upgrade_l5_blocked_subject_count']} "
                "L5-blocked / "
                f"{counts['retained_gap_enveloped_count']}/"
                f"{counts['maturity_upgrade_gap_count']} retained gaps enveloped / "
                f"{counts['retained_gap_exit_criteria_release_allowed_count']}/"
                f"{counts['retained_gap_exit_criteria_count']} retained gap exit criteria / "
                f"{counts['retained_gap_external_receipt_alignment_count']}/"
                f"{counts['retained_gap_exit_criteria_count']} retained gap receipts / "
                f"{counts['maturity_upgrade_gap_count']} gaps / "
                f"{counts['maturity_upgrade_gap_domain_classified_count']}/"
                f"{counts['maturity_upgrade_gap_domain_count']} gap domains classified / "
                f"{counts['maturity_upgrade_gap_domain_count']} domains / "
                f"{counts['boundary_guarded_completion_ready_count']}/"
                f"{counts['boundary_guarded_completion_subject_count']} boundary guarded / "
                f"{counts['residual_warning_governance_input_source_managed_warning_count']}/"
                f"{counts['input_source_warning_count']} input warnings managed / "
                f"{counts['residual_warning_governance_count_profile_managed_warning_count']}/"
                f"{counts['count_profile_warning_count']} count warnings managed / "
                f"{counts['residual_warning_governance_plugin_manual_managed_warning_count']}/"
                f"{counts['residual_warning_governance_plugin_manual_warning_count']} plugin/manual warnings managed / "
                f"{counts['residual_warning_governance_reference_profile_managed_warning_count']}/"
                f"{counts['residual_warning_governance_reference_profile_warning_count']} reference warnings managed / "
                f"{counts['residual_warning_governance_visio_fixture_verified_count']}/"
                f"{counts['residual_warning_governance_visio_fixture_closed_count']} Visio fixture closed / "
                f"{counts['dashboard_warning_projection_governed_count']}/"
                f"{dashboard.warning_count} dashboard warnings governed / "
                f"{counts['residual_warning_governance_unmanaged_warning_count']} unmanaged warnings / "
                f"{counts['boundary_readiness_reconciliation_unreconciled_count']} unreconciled readiness / "
                f"{counts['terminal_release_exception_ungoverned_count']} ungoverned exceptions / "
                f"{counts['boundary_subject_release_dossier_issue_count']} dossier issues / "
                f"{counts['non_subject_release_trace_attribution_unattributed_count']} unattributed traces / "
                f"{counts['release_trace_partition_guard_missing_trace_count']} trace partition gaps / "
                f"{counts['release_projection_surface_parity_issue_count']} release projection gaps / "
                f"{counts['boundary_subject_release_continuity_mismatch_count']} subject continuity gaps / "
                f"{counts['release_closure_ledger_issue_count']} release ledger gaps / "
                f"{counts['boundary_maturity_release_envelope_issue_count']} boundary envelope gaps / "
                f"{counts['release_residual_ratio_ledger_issue_count']} residual ratio gaps / "
                f"{counts['release_residual_ratio_ledger_exit_criteria_link_count']} "
                "residual ratio exit criteria / "
                f"{counts['release_residual_ratio_ledger_receipt_alignment_link_count']} "
                "residual ratio receipts / "
                f"{counts['release_residual_ratio_ledger_count_delivery_receipt_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_count_delivery_receipt_alignment_link_count']} "
                "count/delivery receipts aligned / "
                f"{counts['release_residual_ratio_ledger_boundary_scope_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_boundary_scope_link_count']} "
                "boundary scopes guarded / "
                f"{counts['boundary_maturity_release_envelope_l5_blocker_enveloped_count']}/"
                f"{counts['maturity_upgrade_l5_blocked_subject_count']} L5 blockers enveloped / "
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_count']}/"
                f"{counts['release_residual_ratio_ledger_maturity_l5_blocker_receipt_alignment_link_count']} "
                "L5 receipts aligned / "
                f"{counts['release_acceptance_certificate_issue_count']} acceptance certificate gaps"
            ),
            variant=(
                "warning"
                if counts["static_closed_but_not_green_count"]
                else "success"
            ),
            icon_name="badge-check",
            tooltip=_scene_matrix_dashboard_tooltip(dashboard),
        ),
    )


def build_scene_matrix_drilldown_summary_items() -> tuple[SummaryGridItem, ...]:
    report = build_scene_matrix_drilldown_report()
    counts = report.to_payload()["counts"]
    return (
        SummaryGridItem(
            key="scene_matrix_drilldown",
            label="Matrix drilldown",
            value=f"{counts['ready_count']}/{counts['item_count']} ready",
            detail=(
                f"{counts['visible_row_count']} visible rows / "
                "dashboard, request-cell, Ambiguity clarification, User journey fixtures, Business capability matrix, plugin boundary, Word risk, "
                "external handoff contracts, Boundary guarded completion, Residual warning governance, Boundary readiness reconciliation, Terminal release exceptions, Boundary subject release dossiers, Non-subject release trace attribution, import handoff, InputSourceProfile, family fixture depth, "
                "Release trace partition guard, "
                "Release projection parity, "
                "Boundary subject release continuity, "
                "Release closure ledger, "
                "Boundary maturity release envelope, "
                "Retained gap exit criteria, "
                "Release residual ratio ledger, "
                "Release residual explanations, "
                "Release acceptance certificate, "
                "ObjectPreflight actions, CountProfile, MaterialSchema, Material repair flow, Fixed-layout profile, "
                "Report/artifact drilldown, DeliveryPreset, "
                "Delivery execution, "
                "Formula/output/watermark, Control runtime consistency, Maturity upgrade"
            ),
            variant="success" if report.status == "passed" else "warning",
            icon_name="list-tree",
            tooltip=_scene_matrix_drilldown_tooltip(report),
        ),
        SummaryGridItem(
            key="scene_matrix_drilldown_sources",
            label="Drilldown sources",
            value=(
                f"{counts['ready_source_evidence_count']}/"
                f"{counts['source_evidence_count']} ready"
            ),
            detail=(
                f"{report.missing_source_evidence_count} missing / "
                + _join_values(
                    evidence.source_id for evidence in report.source_evidence
                )
            ),
            variant=(
                "success"
                if report.missing_source_evidence_count == 0
                else "warning"
            ),
            icon_name="file-search",
            tooltip=_scene_matrix_drilldown_tooltip(report),
        ),
    )


def build_parameter_ownership_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    specs = scene_parameter_ownership_specs()
    audit = audit_scene_parameter_ownership(scene.__class__)
    layer_counts = Counter(spec.owner_layer for spec in specs.values())
    issue_count = (
        len(audit.missing_top_level_paths)
        + len(audit.missing_required_paths)
        + len(audit.unknown_spec_paths)
        + len(audit.invalid_owner_layers)
    )
    return (
        SummaryGridItem(
            key="parameter_ownership",
            label="参数归属",
            value="归属清楚" if audit.is_clean else f"{issue_count} 个待处理",
            detail=_owner_layer_detail(layer_counts),
            variant="success" if audit.is_clean else "warning",
            icon_name="workflow",
            tooltip=(
                _ownership_audit_tooltip(audit)
                + "\n归属计数："
                + _owner_layer_count_detail(layer_counts)
            ),
        ),
        SummaryGridItem(
            key="parameter_boundary",
            label="参数边界",
            value="按字段应用",
            detail="未知参数不会乱套；固定行高只用于套打/固定版式",
            variant="info",
            icon_name="route",
            tooltip=(
                "场景参数必须精确登记归属层；"
                "未登记的嵌套参数不会被父级路径自动吸收。"
            ),
        ),
    )


def build_control_contract_summary_items() -> tuple[SummaryGridItem, ...]:
    contracts = list_control_contracts()
    audit = audit_control_contract_registry()
    owner_counts = Counter(contract.owner_layer for contract in contracts)
    issue_count = (
        len(audit.missing_required_contracts)
        + len(audit.invalid_owner_layers)
        + len(audit.missing_paired_contracts)
        + len(audit.missing_evidence_files)
        + len(audit.missing_evidence_markers)
    )
    return (
        SummaryGridItem(
            key="control_contract",
            label="格式控件",
            value="已统一" if audit.is_clean else f"{issue_count} 个待统一",
            detail=_control_contract_detail(contracts),
            variant="success" if audit.is_clean else "warning",
            icon_name="sliders-horizontal",
            tooltip=(
                _control_contract_audit_tooltip(audit)
                + "\n已统一控件："
                + _control_contract_full_detail(contracts)
            ),
        ),
        SummaryGridItem(
            key="control_contract_scope",
            label="控件范围",
            value=f"{len(contracts)} 类控件",
            detail=_control_contract_owner_detail(owner_counts),
            variant="info",
            icon_name="list-checks",
            tooltip=(
                "同名格式参数必须复用模板管理的控件、单位和禁用规则；"
                "固定版位行高保留在表单/套打场景，不回到通用表格模板。"
                "\n控件归属："
                + _control_contract_owner_count_detail(owner_counts)
            ),
        ),
    )


def build_planning_family_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    family = _planned_family_for_scene(scene)
    if family is None:
        return ()
    preflight_targets = object_preflight_targets_for_touchpoints(family.ooxml_touchpoints)
    return (
        SummaryGridItem(
            key="planning_family",
            label="场景类型",
            value=_family_display_name(family.family_id),
            detail=f"{family.priority} · {_maturity_level_label(family.maturity_level)}",
            variant="info",
            icon_name="layers",
            tooltip=f"{family.family_id} / {family.intended_landing}",
        ),
        SummaryGridItem(
            key="planning_workflows",
            label="会做的事",
            value=f"{len(family.workflow_archetypes)} 类流程",
            detail=_display_list(family.workflow_archetypes, WORKFLOW_DISPLAY_LABELS),
            variant="info",
            icon_name="workflow",
            tooltip=_join_values(family.workflow_archetypes),
        ),
        SummaryGridItem(
            key="planning_first_slice",
            label="当前已打通",
            value="已有首个闭环",
            detail=_first_slice_display(family.first_closed_slice),
            variant="success",
            icon_name="route",
            tooltip=family.first_closed_slice,
        ),
        SummaryGridItem(
            key="planning_ooxml",
            label="Word 风险点",
            value=f"{len(family.ooxml_touchpoints)} 类需检查",
            detail=_ooxml_touchpoint_detail(family.ooxml_touchpoints, preflight_targets),
            variant="warning",
            icon_name="file-warning",
            tooltip=_join_values(family.ooxml_touchpoints),
        ),
    )


def build_coverage_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    packs = _coverage_packs_for_scene(scene)
    if not packs:
        return ()

    pack_ids = [pack.pack_id for pack in packs]
    plugin_count = sum(1 for pack in packs if pack.plugin_boundary)
    first_task = _first_closure_task(packs)
    items = [
        SummaryGridItem(
            key="coverage_pack",
            label="适用场景",
            value=_coverage_pack_value(packs),
            detail=_coverage_pack_detail(packs),
            variant="warning" if any(pack.missing_closures for pack in packs) else "success",
            icon_name="grid-2x2",
            tooltip=_coverage_pack_tooltip(packs),
        )
    ]
    if first_task is not None:
        items.append(
            SummaryGridItem(
                key="coverage_next_closure",
                label="待补能力",
                value=f"{first_task.priority} · {first_task.target_phase}",
                detail=first_task.summary,
                variant="warning",
                icon_name="list-checks",
                tooltip=_closure_task_tooltip(first_task),
            )
        )
    if plugin_count:
        items.append(
            SummaryGridItem(
                key="coverage_plugin_boundary",
                label="需要外部确认",
                value=f"{plugin_count} 项需确认",
                detail=_join_values(
                    _boundary_text_display(pack.boundary)
                    for pack in packs
                    if pack.plugin_boundary
                ),
                variant="warning",
                icon_name="plug-zap",
            )
        )
    return tuple(items)


def build_product_readiness_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    specs = _product_readiness_specs_for_scene(scene)
    if not specs:
        return ()
    pack_specs = [spec for spec in specs if spec.subject_type == "pack"]
    family_specs = [spec for spec in specs if spec.subject_type == "family"]
    pack_detail = _product_readiness_detail(pack_specs)
    family_detail = _product_readiness_detail(family_specs)
    gap_count = sum(len(spec.remaining_product_gaps) for spec in specs)
    first_spec = specs[0]
    items = [
        SummaryGridItem(
            key="product_readiness",
            label="可用程度",
            value=_product_readiness_value(specs),
            detail=pack_detail or family_detail,
            variant=_product_readiness_variant(first_spec),
            icon_name="badge-check",
            tooltip=_product_readiness_tooltip(specs),
        )
    ]
    if family_specs:
        items.append(
            SummaryGridItem(
                key="product_readiness_family",
                label="场景族可用度",
                value=_product_readiness_value(family_specs),
                detail=family_detail,
                variant=_product_readiness_variant(family_specs[0]),
                icon_name="layers",
                tooltip=_product_readiness_tooltip(family_specs),
            )
        )
    if gap_count:
        items.append(
            SummaryGridItem(
                key="product_readiness_gaps",
                label="还不能自动做",
                value=f"{gap_count} 项需确认",
                detail=_product_readiness_gap_detail(specs),
                variant="warning",
                icon_name="list-checks",
                tooltip=_product_readiness_tooltip(specs),
            )
        )
    return tuple(items)


def build_academic_rule_source_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "chinese_academic" not in pack_ids and "thesis_cn" not in candidate_keys:
        return ()
    fixtures = scene_sample_fixtures_for_pack("chinese_academic")
    report_ids = (
        "rule_source_governance",
        "school_rule_source_selection",
        "section_classifier_confirmation",
        "count_report",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "thesis_school_rule_context_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    return (
        SummaryGridItem(
            key="academic_rule_source_evidence",
            label="学术规则证据",
            value="已打通" if evidence_fixture_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids else "warning",
            icon_name="graduation-cap",
            tooltip=_append_evidence_tooltip(
                (
                    "覆盖学校规则来源选择、章节分类确认、字数统计和对象预检；"
                    "不会把本地默认规则当成所有学校的权威规则。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_journal_submission_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "english_journal" not in pack_ids and "journal_en" not in candidate_keys:
        return ()

    fixtures = scene_sample_fixtures_for_pack("english_journal")
    report_ids = (
        "journal_rule_source_governance",
        "reviewed_journal_profile_update",
        "citation_source_report",
        "journal_submission_package",
        "submission_artifact_manifest",
        "plugin_manual_gate",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "journal_submission_materials_v1",
            "journal_materials_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    rule_source_ids = tuple(
        source.source_id for source in scene_rule_sources_for_pack("english_journal")
    )
    return (
        SummaryGridItem(
            key="journal_submission_evidence",
            label="期刊投稿证据",
            value="已打通" if evidence_fixture_ids and rule_source_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                rule_ids=rule_source_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids and rule_source_ids else "warning",
            icon_name="book-marked",
            tooltip=_append_evidence_tooltip(
                (
                    "连接通用投稿规则、BibTeX/CSL 引用诊断、投稿包产物、"
                    "期刊规则人工确认和对象预检；目标期刊最终版式仍需人工确认。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                rule_ids=rule_source_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_contract_field_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    if not any(pack.pack_id == "contract_delivery" for pack in _coverage_packs_for_scene(scene)):
        return ()
    fixtures = scene_sample_fixtures_for_pack("contract_delivery")
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if "contract_field_consistency_report" in fixture.report_expectations
    )
    schema_ids = _unique_values(
        [
            "contract_parties_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    preset_ids = _unique_values(
        [
            "field_consistency_report",
            *[
                str(getattr(preset, "preset_id", "") or "").strip()
                for preset in list(getattr(scene, "delivery_presets", ()) or ())
            ],
        ]
    )
    return (
        SummaryGridItem(
            key="contract_field_evidence",
            label="合同字段证据",
            value="已打通" if evidence_fixture_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=("contract_field_consistency_report",),
                preset_ids=preset_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids else "warning",
            icon_name="file-check-2",
            tooltip=_append_evidence_tooltip(
                (
                    "使用合同方资料规则，并产出字段一致性报告；"
                    "不提供法律意见，也不判断条款有效性。"
                ),
                schema_ids=schema_ids,
                report_ids=("contract_field_consistency_report",),
                preset_ids=preset_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_bidding_archive_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "bidding_materials" not in pack_ids and (
        "qualification_archive_packages" not in candidate_keys
    ):
        return ()
    fixtures = scene_sample_fixtures_for_pack("bidding_materials")
    report_ids = (
        "expiry_metadata_report",
        "consortium_archive_manifest",
        "seal_position_residue_report",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "bid_materials_v1",
            "qualification_archive_assets_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    return (
        SummaryGridItem(
            key="bidding_archive_evidence",
            label="标书资质证据",
            value="已打通" if evidence_fixture_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids else "warning",
            icon_name="archive",
            tooltip=_append_evidence_tooltip(
                (
                    "覆盖联合体成员字段、证书有效期信息和签章位置残留报告；"
                    "不核验证书真实性，也不判断资质有效性。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_official_policy_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "official_policy" not in pack_ids and (
        "meeting_policy_documents" not in candidate_keys
    ):
        return ()
    fixtures = scene_sample_fixtures_for_pack("official_policy")
    report_ids = (
        "official_metadata_report",
        "formal_internal_archive_manifest",
        "official_delivery_status_report",
        "watermark_status_report",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "official_document_v1",
            "administrative_meeting_fields_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    return (
        SummaryGridItem(
            key="official_policy_evidence",
            label="公文元数据证据",
            value="已打通" if evidence_fixture_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids else "warning",
            icon_name="file-badge",
            tooltip=_append_evidence_tooltip(
                (
                    "覆盖公文元数据、正式/内部/归档交付清单和水印状态；"
                    "不判断行政决策内容，也不证明正式发布有效性。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_technical_long_doc_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "technical_long_docs" not in pack_ids and (
        "long_document_publishing" not in candidate_keys
    ):
        return ()
    fixtures = scene_sample_fixtures_for_pack("technical_long_docs")
    report_ids = (
        "chapter_inventory",
        "index_appendix_inventory",
        "multi_file_merge_boundary_report",
        "cross_reference_status_report",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "technical_document_v1",
            "long_document_metadata_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    return (
        SummaryGridItem(
            key="technical_long_doc_evidence",
            label="技术长文档证据",
            value="已打通" if evidence_fixture_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids else "warning",
            icon_name="book-open-check",
            tooltip=_append_evidence_tooltip(
                (
                    "覆盖章节清单、索引/附录清单、交叉引用状态和多文件合并边界；"
                    "不承诺发布系统无损合并，也不判断技术内容正确性。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_application_report_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "application_reports" not in pack_ids and not (
        {"project_application", "product_sales_documents"} & candidate_keys
    ):
        return ()

    fixtures = scene_sample_fixtures_for_pack("application_reports")
    report_ids = (
        "rule_source_governance",
        "submission_system_boundary_report",
        "attachment_inventory",
        "budget_attachment_report",
        "asset_consistency_report",
        "quote_body_disambiguation",
        "product_asset_inventory",
        "customer_internal_version_report",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "project_application_materials_v1",
            "product_assets_v1",
            "case_study_assets_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    rule_source_ids = tuple(
        source.source_id for source in scene_rule_sources_for_pack("application_reports")
    )
    return (
        SummaryGridItem(
            key="application_report_evidence",
            label="申报/材料证据",
            value="已打通" if evidence_fixture_ids and rule_source_ids else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                rule_ids=rule_source_ids,
                fixture_ids=evidence_fixture_ids,
            ),
            variant="success" if evidence_fixture_ids and rule_source_ids else "warning",
            icon_name="file-stack",
            tooltip=_append_evidence_tooltip(
                (
                    "连接项目规则来源、申报系统边界、附件清单、产品素材一致性、"
                    "引文/正文消歧和客户/内部版本证据；外部系统和营销表述真实性仍需人工确认。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                rule_ids=rule_source_ids,
                fixture_ids=evidence_fixture_ids,
            ),
        ),
    )


def build_fixed_layout_batch_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    if "batch_forms" not in pack_ids and not (
        {"hr_batch_documents", "form_batch_documents"} & candidate_keys
    ):
        return ()

    fixtures = scene_sample_fixtures_for_pack("batch_forms")
    report_ids = (
        "fixed_layout_profile_browser",
        "profile_specific_preview",
        "answer_sheet_reuse_path",
        "fixed_layout_row_height",
        "placeholder_residue_report",
        "batch_failure_isolation",
    )
    evidence_fixture_ids = tuple(
        fixture.fixture_id
        for fixture in fixtures
        if set(report_ids) & set(fixture.report_expectations)
    )
    schema_ids = _unique_values(
        [
            "personnel_records_v1",
            "form_batch_fields_v1",
            *[
                str(value or "").strip()
                for value in (
                    getattr(scene.input_source_profile, "material_schema_id", ""),
                    *list(getattr(scene.input_source_profile, "material_schema_ids", ()) or ()),
                )
                if str(value or "").strip()
            ],
        ]
    )
    profile_report = build_scene_fixed_layout_profile_audit_report()
    ready = (
        profile_report.issue_count == 0
        and profile_report.ready_profile_channel_count
        == profile_report.profile_channel_count
    )
    return (
        SummaryGridItem(
            key="fixed_layout_batch_evidence",
            label="固定版式批量证据",
            value="已打通" if evidence_fixture_ids and ready else "待补样本",
            detail=_evidence_detail(
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
                channel_text=(
                    f"{profile_report.ready_profile_channel_count}/"
                    f"{profile_report.profile_channel_count}"
                ),
            ),
            variant="success" if evidence_fixture_ids and ready else "warning",
            icon_name="table-properties",
            tooltip=_append_evidence_tooltip(
                (
                    "连接固定版式画像、分画像预览、答题卡复用、Word 固定行高保留、"
                    "占位残留报告和逐条失败隔离；固定行高不会回流为通用模板表格设置。"
                ),
                schema_ids=schema_ids,
                report_ids=report_ids,
                fixture_ids=evidence_fixture_ids,
                channel_text=(
                    f"{profile_report.ready_profile_channel_count}/"
                    f"{profile_report.profile_channel_count}"
                ),
            ),
        ),
    )


def build_boundary_capability_evidence_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    pack_ids = {pack.pack_id for pack in _coverage_packs_for_scene(scene)}
    candidate_keys = set(coverage_candidate_keys_for_config(scene))
    specs = tuple(
        spec
        for spec in list_scene_boundary_capabilities()
        if spec.pack_id in pack_ids
        or spec.subject_id in candidate_keys
        or spec.family_id in candidate_keys
    )
    if not specs:
        return ()

    fixture_ids = _unique_values(
        fixture_id for spec in specs for fixture_id in spec.fixture_ids
    )
    report_ids = _unique_values(
        report_id for spec in specs for report_id in spec.report_expectation_ids
    )
    boundary_report_markers = (
        "professional_boundary_matrix",
        "confidence_artifact_manifest",
    )
    gate_ids = _unique_values(spec.plugin_gate_id for spec in specs)
    ui_surface_ids = _unique_values(
        surface_id for spec in specs for surface_id in spec.ui_surface_ids
    )
    risk_domain_ids = _unique_values(
        domain_id for spec in specs for domain_id in spec.risk_domain_ids
    )
    receipt_ids = _unique_values(
        receipt_id for spec in specs for receipt_id in spec.external_receipt_ids
    )
    missing_fixture_ids = tuple(
        fixture_id
        for fixture_id in fixture_ids
        if fixture_id not in SCENE_SAMPLE_FIXTURE_MAP
    )
    ready = not missing_fixture_ids
    return (
        SummaryGridItem(
            key="boundary_capability_evidence",
            label="边界能力证据",
            value=f"{len(specs)} 项能力" if ready else "待补样本",
            detail=_evidence_detail(
                report_ids=(*report_ids, *boundary_report_markers),
                ui_ids=ui_surface_ids,
                gate_ids=gate_ids,
                risk_ids=risk_domain_ids,
                receipt_ids=receipt_ids,
                fixture_ids=fixture_ids,
            ),
            variant="warning",
            icon_name="shield-check",
            tooltip=_append_evidence_tooltip(
                _boundary_capability_tooltip(specs),
                report_ids=(*report_ids, *boundary_report_markers),
                ui_ids=ui_surface_ids,
                gate_ids=gate_ids,
                risk_ids=risk_domain_ids,
                receipt_ids=receipt_ids,
                fixture_ids=fixture_ids,
            ),
        ),
    )


def build_scene_sample_fixture_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    packs = _coverage_packs_for_scene(scene)
    if not packs:
        return ()
    summary = build_scene_sample_coverage_summary([pack.pack_id for pack in packs])
    issue_count = len(summary.missing_pack_ids) + len(summary.audit_issues)
    items = [
        SummaryGridItem(
            key="sample_fixture_coverage",
            label="样本覆盖",
            value="已有样本文档" if summary.is_clean else f"{issue_count} 个待补",
            detail=(
                f"{len(summary.fixture_ids)} 个样本 / "
                f"{len(summary.docx_surfaces)} 类 Word 对象 / "
                f"{_display_list(summary.expected_behaviors, BEHAVIOR_DISPLAY_LABELS)}"
            ),
            variant="success" if summary.is_clean else "warning",
            icon_name="scan",
            tooltip=_sample_fixture_tooltip(summary),
        )
    ]
    if summary.manual_gate_ids or summary.boundary_notes:
        items.append(
            SummaryGridItem(
                key="sample_fixture_boundary",
                label="样本提醒",
                value=(
                    f"{len(summary.manual_gate_ids)} 项需人工确认"
                    if summary.manual_gate_ids
                    else "有边界说明"
                ),
                detail=_sample_fixture_boundary_detail(summary),
                variant="warning",
                icon_name="circle-alert",
                tooltip=_sample_fixture_tooltip(summary),
            )
        )
    return tuple(items)


def build_scene_request_cell_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    packs = _coverage_packs_for_scene(scene)
    if not packs:
        return ()
    summary = build_scene_request_cell_fixture_summary(
        [pack.pack_id for pack in packs]
    )
    issue_count = len(summary.audit_issues)
    release_clean = (
        summary.is_clean
        and summary.family_proxy_count == 0
        and (
            summary.fixture_cell_count + summary.negative_control_count
            == summary.cell_count
        )
    )
    items = [
        SummaryGridItem(
            key="request_cell_coverage",
            label="常见说法",
            value="常见说法已覆盖" if release_clean else f"{issue_count} 个待补",
            detail=(
                f"{summary.cell_count} 个请求 / "
                f"{summary.fixture_cell_count} 个证据 / "
                f"{summary.family_proxy_count} 个借用样本"
            ),
            variant="success" if release_clean else "warning",
            icon_name="list-checks",
            tooltip=_request_cell_tooltip(summary),
        )
    ]
    if summary.manual_boundary_count or summary.ambiguous_count:
        items.append(
            SummaryGridItem(
                key="request_cell_boundary",
                label="请求提醒",
                value=(
                    f"{summary.manual_boundary_count} 项需人工确认"
                    if summary.manual_boundary_count
                    else f"{summary.ambiguous_count} 个容易误解的说法"
                ),
                detail=(
                    f"需澄清 {summary.ambiguous_count} 个 / "
                    f"明确不处理 {summary.negative_control_count} 个"
                ),
                variant="warning" if summary.manual_boundary_count else "info",
                icon_name="route",
                tooltip=_request_cell_tooltip(summary),
            )
        )
    return tuple(items)


def build_scene_sample_fixture_detail_text(scene: SceneWorkspace) -> str:
    packs = _coverage_packs_for_scene(scene)
    if not packs:
        return ""
    lines: list[str] = []
    for pack in packs:
        fixtures = scene_sample_fixtures_for_pack(pack.pack_id)
        lines.append(f"资料包：{_coverage_pack_display_name(pack.pack_id)}")
        if not fixtures:
            lines.append("  - 还没有最小 Word 样本")
            continue
        for fixture_index, fixture in enumerate(fixtures, start=1):
            detail_parts = [
                scene_sample_fixture_display_name(fixture, fixture_index),
                f"场景族：{_family_display_name(fixture.family_id) if fixture.family_id else '-'}",
                f"Word 对象：{_display_list(fixture.docx_surfaces, OOXML_TOUCHPOINT_DISPLAY_LABELS)}",
                f"检查重点：{_display_list(fixture.expected_preflight_findings, OOXML_TOUCHPOINT_DISPLAY_LABELS)}",
                f"处理方式：{_display_list(fixture.expected_behaviors, BEHAVIOR_DISPLAY_LABELS)}",
            ]
            if fixture.report_expectations:
                detail_parts.append(
                    f"报告证据：{len(fixture.report_expectations)} 项"
                )
            if fixture.manual_gate_id:
                detail_parts.append(f"人工确认：{_manual_gate_display(fixture.manual_gate_id)}")
            lines.append("  - " + "；".join(detail_parts))
            for note in fixture.boundary_notes:
                lines.append("    边界：" + _boundary_text_display(note))
        request_cells = request_cell_fixtures_for_pack(pack.pack_id)
        if request_cells:
            lines.append("  常见说法：")
            for cell in request_cells:
                fixture_count = len(tuple(cell.fixture_ids or ()))
                cell_parts = [
                    f"用户说法：{cell.request_text}",
                    f"覆盖方式：{_request_cell_coverage_display(cell.coverage_level)}",
                    (
                        f"证据样本：{fixture_count} 个"
                        if fixture_count
                        else "证据样本：无"
                    ),
                ]
                if cell.expected_family_ids:
                    cell_parts.append(
                        "适用场景："
                        + _join_values(
                            _family_display_name(family_id)
                            for family_id in cell.expected_family_ids
                        )
                    )
                if cell.disambiguation_required:
                    cell_parts.append("处理：先澄清")
                if cell.manual_gate_ids:
                    cell_parts.append(
                        "人工确认："
                        + _join_values(
                            _manual_gate_display(gate_id)
                            for gate_id in cell.manual_gate_ids
                        )
                    )
                for note in cell.boundary_notes[:2]:
                    cell_parts.append("边界：" + _boundary_text_display(note))
                lines.append("    - " + "；".join(cell_parts))
    return "\n".join(lines)


def scene_sample_fixture_specs_for_scene(
    scene: SceneWorkspace,
) -> tuple[SceneSampleFixtureSpec, ...]:
    packs = _coverage_packs_for_scene(scene)
    fixtures: list[SceneSampleFixtureSpec] = []
    seen: set[str] = set()
    for pack in packs:
        for fixture in scene_sample_fixtures_for_pack(pack.pack_id):
            if fixture.fixture_id in seen:
                continue
            fixtures.append(fixture)
            seen.add(fixture.fixture_id)
    return tuple(fixtures)


def scene_request_cell_fixture_specs_for_scene(
    scene: SceneWorkspace,
) -> tuple[SceneRequestCellFixtureSpec, ...]:
    packs = _coverage_packs_for_scene(scene)
    cells: list[SceneRequestCellFixtureSpec] = []
    seen: set[str] = set()
    for pack in packs:
        for cell in request_cell_fixtures_for_pack(pack.pack_id):
            if cell.sample_id in seen:
                continue
            cells.append(cell)
            seen.add(cell.sample_id)
    return tuple(cells)


def scene_sample_fixture_display_name(
    fixture: SceneSampleFixtureSpec,
    ordinal: int | None = None,
) -> str:
    base = _family_display_name(fixture.family_id) if fixture.family_id else ""
    if not base:
        base = _coverage_pack_display_name(fixture.pack_id)
    suffix = f"样本 {ordinal}" if ordinal else "样本文档"
    surfaces = tuple(fixture.docx_surfaces or ())
    if surfaces:
        return f"{base}{suffix}：{_display_list(surfaces[:3], OOXML_TOUCHPOINT_DISPLAY_LABELS)}"
    return f"{base}{suffix}"


def scene_sample_fixture_tooltip_text(fixture: SceneSampleFixtureSpec) -> str:
    lines = [
        f"样本编号：{fixture.fixture_id}",
        f"资料包：{_coverage_pack_display_name(fixture.pack_id)}",
    ]
    if fixture.family_id:
        lines.append(f"场景族：{_family_display_name(fixture.family_id)}")
    if fixture.docx_surfaces:
        lines.append(
            "Word 对象："
            + _display_list(fixture.docx_surfaces, OOXML_TOUCHPOINT_DISPLAY_LABELS)
        )
    if fixture.expected_preflight_findings:
        lines.append(
            "检查重点："
            + _display_list(
                fixture.expected_preflight_findings,
                OOXML_TOUCHPOINT_DISPLAY_LABELS,
            )
        )
    if fixture.expected_behaviors:
        lines.append(
            "处理方式："
            + _display_list(fixture.expected_behaviors, BEHAVIOR_DISPLAY_LABELS)
        )
    if fixture.report_expectations:
        lines.append(f"报告证据：{len(fixture.report_expectations)} 项")
    if fixture.manual_gate_id:
        lines.append(f"人工确认：{_manual_gate_display(fixture.manual_gate_id)}")
    for note in fixture.boundary_notes[:3]:
        lines.append("边界：" + _boundary_text_display(note))
    return "\n".join(lines)


def scene_sample_fixture_list_item_projection(
    fixture: SceneSampleFixtureSpec,
    ordinal: int | None = None,
) -> SceneSampleFixtureListItemProjection:
    return SceneSampleFixtureListItemProjection(
        fixture_id=str(fixture.fixture_id or "").strip(),
        text=scene_sample_fixture_display_name(fixture, ordinal),
        tooltip=scene_sample_fixture_tooltip_text(fixture),
    )


def scene_request_cell_display_text(cell: SceneRequestCellFixtureSpec) -> str:
    request = str(cell.request_text or "").strip()
    level = _request_cell_coverage_display(cell.coverage_level)
    if cell.disambiguation_required:
        return f"{request} · 先澄清 · {level}" if request else f"先澄清 · {level}"
    return f"{request} · {level}" if request else level


def scene_request_cell_tooltip_text(cell: SceneRequestCellFixtureSpec) -> str:
    fixture_count = len(tuple(cell.fixture_ids or ()))
    lines = [
        f"请求：{cell.request_text}",
        f"覆盖层级：{_request_cell_coverage_display(cell.coverage_level)}",
        "资料包："
        + _join_values(
            _coverage_pack_display_name(pack_id)
            for pack_id in cell.expected_pack_ids
        ),
        "场景族："
        + _join_values(
            _family_display_name(family_id)
            for family_id in cell.expected_family_ids
        ),
        f"证据样本：{fixture_count} 个" if fixture_count else "证据样本：无",
    ]
    if cell.fixture_ids:
        lines.append("证据编号：" + _join_values(cell.fixture_ids))
    if cell.sample_id:
        lines.append(f"请求编号：{cell.sample_id}")
    if cell.manual_gate_ids:
        lines.append(
            "人工确认："
            + _join_values(_manual_gate_display(gate_id) for gate_id in cell.manual_gate_ids)
        )
        lines.append("人工确认编号：" + _join_values(cell.manual_gate_ids))
    if cell.disambiguation_required:
        lines.append("需要先澄清")
    for note in cell.boundary_notes[:3]:
        lines.append("边界：" + _boundary_text_display(note))
    return "\n".join(lines)


def scene_request_cell_list_item_projection(
    cell: SceneRequestCellFixtureSpec,
) -> SceneRequestCellListItemProjection:
    tooltip = scene_request_cell_tooltip_text(cell)
    if cell.disambiguation_required:
        route_result = route_natural_scene_request(cell.request_text)
        extra_lines: list[str] = []
        if route_result.disambiguation_prompt:
            extra_lines.append("澄清：" + route_result.disambiguation_prompt)
        candidate_pack_labels = _unique_values(
            _coverage_pack_display_name(match.route.pack_id)
            for match in route_result.matches[:3]
            if getattr(match.route, "pack_id", "")
        )
        if candidate_pack_labels:
            extra_lines.append("候选资料包：" + _join_values(candidate_pack_labels))
        if extra_lines:
            tooltip = tooltip + "\n" + "\n".join(extra_lines)
    return SceneRequestCellListItemProjection(
        sample_id=str(cell.sample_id or "").strip(),
        text=scene_request_cell_display_text(cell),
        tooltip=tooltip,
    )


def scene_request_cell_filter_options() -> tuple[tuple[str, str], ...]:
    return REQUEST_CELL_FILTER_OPTIONS


def scene_request_cell_matches_filter(
    cell: SceneRequestCellFixtureSpec,
    filter_id: object,
) -> bool:
    normalized = str(filter_id or REQUEST_CELL_FILTER_ALL_ID).strip()
    if not normalized or normalized == REQUEST_CELL_FILTER_ALL_ID:
        return True
    return str(cell.coverage_level or "").strip() == normalized


def scene_request_cell_filter_label(filter_id: object) -> str:
    normalized = str(filter_id or REQUEST_CELL_FILTER_ALL_ID).strip()
    labels = dict(REQUEST_CELL_FILTER_OPTIONS)
    return labels.get(normalized, normalized.replace("_", " ") or "全部说法")


def scene_request_cell_count_text(visible_count: int, total_count: int) -> str:
    visible = max(0, int(visible_count or 0))
    total = max(0, int(total_count or 0))
    if total == 0:
        return "无请求说法"
    if visible == 0:
        return "无匹配说法"
    if visible == total:
        return f"{total} 条说法"
    return f"{visible} 条 / 共 {total} 条"


def scene_request_cell_count_tooltip(
    visible_count: int,
    total_count: int,
    filter_id: object,
) -> str:
    visible = max(0, int(visible_count or 0))
    total = max(0, int(total_count or 0))
    filter_label = scene_request_cell_filter_label(filter_id)
    if total == 0:
        return "当前场景还没有请求说法"
    if visible == 0:
        return f"当前筛选：{filter_label}\n没有匹配的请求说法；本场景共 {total} 条"
    return f"当前筛选：{filter_label}\n显示 {visible} 条请求说法；本场景共 {total} 条"


def scene_request_cell_empty_text(filter_id: object, total_count: int) -> str:
    total = max(0, int(total_count or 0))
    if total == 0:
        return "当前场景还没有请求说法"
    filter_label = scene_request_cell_filter_label(filter_id)
    return f"当前没有“{filter_label}”的请求说法"


REQUEST_CELL_EVIDENCE_STATUS_TEXTS = {
    "ready": "可以打开说法依据",
    "no_selection": "先选择一条请求说法",
    "no_docx": "当前说法没有可打开的 Word 证据",
    "missing_file": "证据文件未生成",
    "opened": "已打开说法依据",
    "open_failed": "无法打开说法依据",
}


def scene_request_cell_evidence_status_text(status: object) -> str:
    normalized = str(status or "").strip()
    return REQUEST_CELL_EVIDENCE_STATUS_TEXTS.get(normalized, "说法依据状态未知")


def scene_request_cell_evidence_status_tooltip(
    status: object,
    path: object | None = None,
) -> str:
    normalized = str(status or "").strip()
    text = scene_request_cell_evidence_status_text(normalized)
    detail = {
        "ready": "证据文件已生成，可以打开查看。",
        "no_selection": "先在请求说法列表中选择一条记录。",
        "no_docx": "这条请求说法没有绑定可打开的 Word 样本。",
        "missing_file": "先生成样本库，再打开这条请求说法的证据文件。",
        "opened": "证据文件已交给系统打开。",
        "open_failed": "系统没有成功打开证据文件，可以检查文件路径或权限。",
    }.get(normalized, "")
    parts = [text]
    if detail:
        parts.append(detail)
    if path is not None:
        path_text = str(path or "").strip()
        if path_text:
            parts.append("位置：" + path_text)
    return "\n".join(parts)


SAMPLE_FIXTURE_LIBRARY_STATUS_TEXTS = {
    "not_generated": "尚未生成样本库",
    "generated": "样本库已生成",
    "generation_failed": "样本库生成失败",
    "no_sample_selection": "先选择一个样本文档",
    "sample_missing": "样本文件未生成",
    "sample_opened": "已打开样本",
    "sample_open_failed": "无法打开样本",
    "directory_missing": "样本目录未生成",
    "directory_opened": "已打开样本目录",
    "directory_open_failed": "无法打开样本目录",
}


def scene_sample_fixture_library_status_text(
    status: object,
    artifact_count: int | None = None,
) -> str:
    normalized = str(status or "").strip()
    text = SAMPLE_FIXTURE_LIBRARY_STATUS_TEXTS.get(normalized, "样本库状态未知")
    if normalized == "generated" and artifact_count is not None:
        count = max(0, int(artifact_count or 0))
        return f"{text} · {count} 个样本"
    return text


def scene_sample_fixture_library_status_tooltip(
    status: object,
    path: object | None = None,
    *,
    detail: object = "",
) -> str:
    normalized = str(status or "").strip()
    text = scene_sample_fixture_library_status_text(normalized)
    helper = {
        "not_generated": "生成样本库后，可以打开样本文档和说法依据。",
        "generated": "样本库已经生成，可以打开目录或当前样本文档。",
        "generation_failed": "样本库生成过程中出现错误。",
        "no_sample_selection": "先在样本文件列表中选择一个样本文档。",
        "sample_missing": "先生成样本库，再打开当前样本文档。",
        "sample_opened": "样本文档已交给系统打开。",
        "sample_open_failed": "系统没有成功打开样本文档，可以检查文件路径或权限。",
        "directory_missing": "先生成样本库，再打开样本目录。",
        "directory_opened": "样本目录已交给系统打开。",
        "directory_open_failed": "系统没有成功打开样本目录，可以检查目录路径或权限。",
    }.get(normalized, "")
    parts = [text]
    if helper:
        parts.append(helper)
    detail_text = str(detail or "").strip()
    if detail_text:
        parts.append("说明：" + detail_text)
    if path is not None:
        path_text = str(path or "").strip()
        if path_text:
            parts.append("位置：" + path_text)
    return "\n".join(parts)


def build_input_profile_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    profile = scene.input_source_profile
    requirements = build_material_requirements(
        profile.material_schema_id,
        schema_ids=getattr(profile, "material_schema_ids", ()),
        extra_required_fields=profile.required_material_fields,
        extra_required_asset_roles=profile.required_image_roles,
    )
    accepted_formats = _display_list(profile.accepted_formats, FORMAT_DISPLAY_LABELS)
    structured_formats = _display_list(profile.structured_formats, FORMAT_DISPLAY_LABELS)
    material_fields = list(getattr(requirements, "required_field_keys", ()) or ())
    image_roles = list(getattr(requirements, "required_asset_roles", ()) or ())
    return (
        SummaryGridItem(
            key="accepted_formats",
            label="允许输入",
            value=accepted_formats,
            detail=f"结构化：{structured_formats}",
            variant="info",
            tooltip=(
                "允许输入\n"
                f"{accepted_formats}\n"
                f"格式 ID：{_join_values(profile.accepted_formats)}\n"
                f"结构化格式 ID：{_join_values(profile.structured_formats)}"
            ),
        ),
        SummaryGridItem(
            key="input_policy",
            label="导入策略",
            value=f"MD {MARKDOWN_POLICY_LABELS.get(profile.markdown_policy, profile.markdown_policy)}",
            detail=f"LaTeX {LATEX_POLICY_LABELS.get(profile.latex_policy, profile.latex_policy)}",
        ),
        SummaryGridItem(
            key="materials",
            label="资料包",
            value="必需" if profile.require_material_package else "可选",
            detail=_material_schema_detail(requirements),
            variant="warning" if profile.require_material_package else "neutral",
            tooltip=_material_schema_tooltip(requirements),
        ),
        SummaryGridItem(
            key="material_fields",
            label="必填资料",
            value=f"{len(material_fields)} 个字段",
            detail=_material_field_detail(material_fields),
            tooltip=_raw_list_tooltip("字段 key", material_fields),
        ),
        SummaryGridItem(
            key="image_roles",
            label="图片角色",
            value=f"{len(image_roles)} 个角色",
            detail=_material_asset_role_detail(image_roles),
            tooltip=_raw_list_tooltip("图片角色 key", image_roles),
        ),
        SummaryGridItem(
            key="input_failure",
            label="失败策略",
            value=FAILURE_POLICY_LABELS.get(profile.failure_policy, profile.failure_policy),
            detail="资料或输入不满足时的场景级处理方式",
            variant=_failure_variant(profile.failure_policy),
        ),
    )


def build_compliance_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    profile = scene.compliance_profile
    preflight = profile.object_preflight
    items = (
        SummaryGridItem(
            key="profile",
            label="规则口径",
            value=profile.profile_id or "basic",
            detail=profile.rule_family or "basic_format",
            variant="info",
        ),
        SummaryGridItem(
            key="count_profile",
            label="计数口径",
            value=profile.count_profile_id or "未启用",
            detail=_count_profile_detail(profile.count_profile_id),
        ),
        SummaryGridItem(
            key="check_scopes",
            label="检查范围",
            value=f"{len(profile.check_scopes)} 个范围",
            detail=_join_values(profile.check_scopes),
        ),
        SummaryGridItem(
            key="object_policy",
            label="对象预检",
            value="启用" if preflight.enabled else "关闭",
            detail=_object_policy_detail(scene),
            variant="warning" if preflight.preservation_mode == "strict" else "neutral",
        ),
        SummaryGridItem(
            key="scan_targets",
            label="扫描目标",
            value=f"{len(list(getattr(preflight, 'scan_targets', []) or []))} 个目标",
            detail=_join_values(getattr(preflight, "scan_targets", []) or []),
            variant="info",
        ),
        SummaryGridItem(
            key="skip_policy",
            label="高风险跳过",
            value="启用" if preflight.skip_high_risk_modules else "关闭",
            detail=f"{len(preflight.skip_modules_by_finding)} 类对象映射",
        ),
        SummaryGridItem(
            key="report_level",
            label="报告粒度",
            value=profile.report_level or "summary",
            detail=FAILURE_POLICY_LABELS.get(profile.failure_policy, profile.failure_policy),
            variant=_failure_variant(profile.failure_policy),
        ),
    )
    recommendation = _planning_preflight_recommendation_item(scene)
    return items if recommendation is None else (*items, recommendation)


def recommended_object_preflight_targets_for_scene(
    scene: SceneWorkspace,
) -> tuple[str, ...]:
    family = _planned_family_for_scene(scene)
    if family is None:
        return ()
    return object_preflight_targets_for_touchpoints(family.ooxml_touchpoints)


def build_delivery_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    presets = list(scene.delivery_presets)
    default_id = scene.default_delivery_preset_id or (presets[0].preset_id if presets else "")
    default = next((preset for preset in presets if preset.preset_id == default_id), presets[0] if presets else None)
    default_display = _delivery_preset_display_name(default if default is not None else default_id)
    preset_display_names = [_delivery_preset_display_name(preset) for preset in presets]

    return (
        SummaryGridItem(
            key="default_delivery",
            label="默认交付",
            value=default_display,
            detail=_delivery_default_detail(default),
            variant="success" if default is not None else "warning",
            tooltip=_delivery_preset_tooltip(default, default_id),
        ),
        SummaryGridItem(
            key="preset_count",
            label="版本数量",
            value=f"{len(presets)} 个输出版本",
            detail=_join_values(preset_display_names),
            tooltip=_delivery_preset_list_tooltip(presets),
        ),
        SummaryGridItem(
            key="default_artifacts",
            label="默认产物",
            value=_artifact_summary(getattr(default, "artifacts", None)),
            detail=_delivery_artifact_detail(default),
            variant="info",
        ),
        SummaryGridItem(
            key="structured",
            label="结构化中间产物",
            value="保留" if bool(getattr(default, "include_structured_intermediate", False)) else "不保留",
            detail=f"报告：{_report_level_display(getattr(default, 'report_level', 'summary') if default is not None else 'summary')}",
        ),
    )


def _input_policy_detail(scene: SceneWorkspace) -> str:
    profile = scene.input_source_profile
    parts = [
        _markdown_policy_sentence(profile.markdown_policy),
        _latex_policy_sentence(profile.latex_policy),
    ]
    if profile.require_material_package:
        schema_ids = [
            str(value or "").strip()
            for value in [
                getattr(profile, "material_schema_id", ""),
                *list(getattr(profile, "material_schema_ids", []) or []),
            ]
            if str(value or "").strip()
        ]
        schema_names = [
            _material_schema_display_name(schema_id)
            for schema_id in dict.fromkeys(schema_ids)
        ]
        parts.append(
            "需要资料包" + (f"：{_join_values(schema_names)}" if schema_names else "")
        )
    return " / ".join(part for part in parts if part)


def _material_schema_detail(requirements) -> str:
    schema_ids = _material_schema_ids_from_requirements(requirements)
    if not schema_ids:
        return "未绑定资料规则"
    return _join_values(_material_schema_display_name(schema_id) for schema_id in schema_ids)


def _material_schema_tooltip(requirements) -> str:
    schema_ids = _material_schema_ids_from_requirements(requirements)
    labels = _join_values(
        str(label or "").strip()
        for label in getattr(requirements, "schema_labels", ()) or ()
    )
    parts = ["资料包", _material_schema_detail(requirements)]
    if schema_ids:
        parts.append("资料规则 ID：" + _join_values(schema_ids))
    if labels and labels != "无":
        parts.append("注册表标签：" + labels)
    return "\n".join(part for part in parts if part)


def _material_schema_ids_from_requirements(requirements) -> tuple[str, ...]:
    schema_ids = [
        str(value or "").strip()
        for value in getattr(requirements, "schema_ids", ()) or ()
        if str(value or "").strip()
    ]
    primary_id = str(getattr(requirements, "schema_id", "") or "").strip()
    if primary_id and primary_id not in schema_ids:
        schema_ids.insert(0, primary_id)
    return tuple(dict.fromkeys(schema_ids))


def _material_schema_display_name(schema_id: object) -> str:
    normalized = str(schema_id or "").strip()
    if not normalized:
        return ""
    if normalized in MATERIAL_SCHEMA_DISPLAY_LABELS:
        return MATERIAL_SCHEMA_DISPLAY_LABELS[normalized]
    for schema in list_material_schemas():
        if schema.schema_id == normalized:
            return schema.label or _display_id(normalized, MATERIAL_SCHEMA_DISPLAY_LABELS)
    return _display_id(normalized, MATERIAL_SCHEMA_DISPLAY_LABELS)


def material_schema_display_name(schema_id: object) -> str:
    return _material_schema_display_name(schema_id)


def _material_field_detail(field_keys: Sequence[object]) -> str:
    return _display_named_values(field_keys, _material_field_display_name, unit="字段")


def _material_asset_role_detail(role_keys: Sequence[object]) -> str:
    return _display_named_values(role_keys, _material_asset_role_display_name, unit="角色")


def _material_field_display_name(field_key: object) -> str:
    normalized = str(field_key or "").strip()
    if not normalized:
        return ""
    if normalized in MATERIAL_FIELD_DISPLAY_LABELS:
        return MATERIAL_FIELD_DISPLAY_LABELS[normalized]
    for schema in list_material_schemas():
        for field in schema.fields:
            if field.key == normalized:
                return field.label or _display_id(normalized, MATERIAL_FIELD_DISPLAY_LABELS)
    return _display_id(normalized, MATERIAL_FIELD_DISPLAY_LABELS)


def material_field_display_name(field_key: object) -> str:
    return _material_field_display_name(field_key)


def _material_asset_role_display_name(role_key: object) -> str:
    normalized = str(role_key or "").strip()
    if not normalized:
        return ""
    if normalized in MATERIAL_ASSET_ROLE_DISPLAY_LABELS:
        return MATERIAL_ASSET_ROLE_DISPLAY_LABELS[normalized]
    for schema in list_material_schemas():
        for role in schema.asset_roles:
            if role.role == normalized:
                return role.label or _display_id(normalized, MATERIAL_ASSET_ROLE_DISPLAY_LABELS)
    return _display_id(normalized, MATERIAL_ASSET_ROLE_DISPLAY_LABELS)


def material_asset_role_display_name(role_key: object) -> str:
    return _material_asset_role_display_name(role_key)


def _display_named_values(
    values: Sequence[object],
    display_func,
    *,
    unit: str = "项",
    limit: int = 5,
) -> str:
    labels = [
        display_func(value)
        for value in values
        if str(value or "").strip() and display_func(value)
    ]
    if not labels:
        return "无"
    if len(labels) <= limit:
        return _join_values(labels)
    return _join_values(labels[:limit]) + f" 等 {len(labels)} 个{unit}"


def _raw_list_tooltip(label: str, values: Sequence[object]) -> str:
    return f"{label}：" + _join_values(values)


def _object_policy_detail(scene: SceneWorkspace) -> str:
    preflight = scene.compliance_profile.object_preflight
    scan_targets = _display_list(
        list(getattr(preflight, "scan_targets", []) or [])[:4],
        OOXML_TOUCHPOINT_DISPLAY_LABELS,
    )
    skip = "高风险模块会先跳过" if preflight.skip_high_risk_modules else "高风险模块不自动跳过"
    block = _display_list(preflight.block_on, OOXML_TOUCHPOINT_DISPLAY_LABELS)
    parts = [
        _object_policy_value(preflight),
        f"检查 {scan_targets}" if scan_targets else "检查高风险 Word 对象",
        skip,
    ]
    if block:
        parts.append(f"{block} 会阻断")
    return "；".join(parts)


def _count_profile_detail(profile_id: str) -> str:
    normalized = str(profile_id or "").strip()
    if not normalized:
        return "未配置计数 profile"
    return get_count_profile(normalized).label


def _format_list_label(values: Sequence[object]) -> str:
    labels = [_display_id(value, FORMAT_DISPLAY_LABELS) for value in values]
    labels = [label for label in labels if label]
    if not labels:
        return "未设置"
    if len(labels) <= 2:
        return " / ".join(labels)
    return f"{len(labels)} 种输入"


def _compliance_overview_value(profile) -> str:
    if str(getattr(profile, "failure_policy", "") or "") == "block":
        return "风险会阻断"
    profile_id = str(getattr(profile, "profile_id", "") or "").strip()
    return PROFILE_DISPLAY_LABELS.get(profile_id, "发现问题先提醒")


def _compliance_overview_detail(profile) -> str:
    rule_family = str(getattr(profile, "rule_family", "") or "").strip()
    rule_label = PROFILE_DISPLAY_LABELS.get(rule_family, PROFILE_DISPLAY_LABELS.get(rule_family.replace("_format", ""), "基础格式规则"))
    policy = (
        "遇到问题会停止执行"
        if str(getattr(profile, "failure_policy", "") or "") == "block"
        else "发现问题先提醒"
    )
    return f"{rule_label}；{policy}"


def _object_policy_value(preflight) -> str:
    if not bool(getattr(preflight, "enabled", True)):
        return "不检查"
    if str(getattr(preflight, "preservation_mode", "") or "") == "strict":
        return "严格保护"
    return "发现风险先提醒"


def _delivery_preset_for_id(scene: SceneWorkspace, preset_id: object):
    normalized = str(preset_id or "").strip()
    for preset in list(getattr(scene, "delivery_presets", []) or []):
        if str(getattr(preset, "preset_id", "") or "").strip() == normalized:
            return preset
    return None


def _delivery_preset_display_name(preset_or_id: object) -> str:
    return delivery_preset_display_name(preset_or_id)


def _delivery_preset_tooltip(preset: object | None, fallback_id: object = "") -> str:
    preset_id = str(
        getattr(preset, "preset_id", "") if preset is not None else fallback_id
    ).strip()
    label = str(getattr(preset, "label", "") if preset is not None else "").strip()
    parts = ["默认交付", _delivery_preset_display_name(preset if preset is not None else preset_id)]
    if preset_id:
        parts.append("版本 ID：" + preset_id)
    if label:
        parts.append("原始标签：" + label)
    return "\n".join(part for part in parts if part)


def _delivery_default_detail(preset: object | None) -> str:
    if preset is None:
        return "还未选择输出版本"
    display_name = _delivery_preset_display_name(preset)
    label = str(getattr(preset, "label", "") or "").strip()
    label_display = DELIVERY_PRESET_DISPLAY_LABELS.get(label, label)
    if label_display and label_display not in {display_name, "Final DOCX"}:
        return label_display
    return "执行时默认生成"


def _delivery_preset_list_tooltip(presets: Sequence[object]) -> str:
    preset_ids = [
        str(getattr(preset, "preset_id", "") or "").strip()
        for preset in presets
        if str(getattr(preset, "preset_id", "") or "").strip()
    ]
    return "输出版本 ID：" + _join_values(preset_ids)


def _report_level_display(report_level: object) -> str:
    normalized = str(report_level or "").strip()
    return REPORT_LEVEL_DISPLAY_LABELS.get(normalized, _display_id(normalized, REPORT_LEVEL_DISPLAY_LABELS))


def _delivery_overview_detail(scene: SceneWorkspace) -> str:
    presets = list(getattr(scene, "delivery_presets", []) or [])
    if not presets:
        return "还没有设置输出版本"
    names = [_delivery_preset_display_name(preset) for preset in presets[:3]]
    suffix = " 等" if len(presets) > 3 else ""
    return f"共 {len(presets)} 个输出版本：{_join_values(names)}{suffix}"


def _markdown_policy_sentence(policy: object) -> str:
    normalized = str(policy or "").strip()
    if normalized == "disabled":
        return "不处理 Markdown"
    if normalized == "cleanup_only":
        return "Markdown 只做清理"
    if normalized == "preview_and_cleanup":
        return "Markdown 可预览并清理"
    return f"Markdown {MARKDOWN_POLICY_LABELS.get(normalized, normalized)}"


def _latex_policy_sentence(policy: object) -> str:
    normalized = str(policy or "").strip()
    if normalized == "disabled":
        return "不处理 LaTeX"
    if normalized == "formula_fragments_only":
        return "LaTeX 只处理公式片段"
    return f"LaTeX {LATEX_POLICY_LABELS.get(normalized, normalized)}"


def _display_id(value: object, mapping: dict[str, str]) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return mapping.get(normalized, normalized.replace("_", " "))


def _display_list(values: Sequence[object], mapping: dict[str, str]) -> str:
    return _join_values(_display_id(value, mapping) for value in values)


def _evidence_detail(
    *,
    schema_ids: Sequence[object] = (),
    report_ids: Sequence[object] = (),
    rule_ids: Sequence[object] = (),
    preset_ids: Sequence[object] = (),
    fixture_ids: Sequence[object] = (),
    ui_ids: Sequence[object] = (),
    gate_ids: Sequence[object] = (),
    risk_ids: Sequence[object] = (),
    receipt_ids: Sequence[object] = (),
    channel_text: str = "",
) -> str:
    parts: list[str] = []
    if schema_ids:
        parts.append(
            "资料规则：" + _compact_display_values(
                schema_ids,
                material_schema_display_name,
                unit="类",
            )
        )
    if preset_ids:
        parts.append(
            "输出版本：" + _compact_display_values(
                preset_ids,
                _delivery_preset_display_name,
                unit="个",
            )
        )
    if report_ids:
        parts.append(_evidence_count_label("报告", report_ids))
    if rule_ids:
        parts.append(_evidence_count_label("规则来源", rule_ids))
    if fixture_ids:
        parts.append(_evidence_count_label("样本", fixture_ids))
    if ui_ids:
        parts.append(_evidence_count_label("界面入口", ui_ids))
    if gate_ids:
        parts.append("人工确认：" + _join_values(_manual_gate_display(gate_id) for gate_id in gate_ids))
    if risk_ids:
        parts.append(_evidence_count_label("风险域", risk_ids))
    if receipt_ids:
        parts.append(_evidence_count_label("回执", receipt_ids))
    normalized_channel = str(channel_text or "").strip()
    if normalized_channel:
        parts.append("通道：" + normalized_channel)
    return " / ".join(parts)


def _evidence_technical_detail(
    *,
    schema_ids: Sequence[object] = (),
    report_ids: Sequence[object] = (),
    rule_ids: Sequence[object] = (),
    preset_ids: Sequence[object] = (),
    fixture_ids: Sequence[object] = (),
    ui_ids: Sequence[object] = (),
    gate_ids: Sequence[object] = (),
    risk_ids: Sequence[object] = (),
    receipt_ids: Sequence[object] = (),
    channel_text: str = "",
) -> str:
    parts: list[str] = []
    if schema_ids:
        parts.append("资料规则 ID：" + _join_values(schema_ids))
    if report_ids:
        parts.append("报告 ID：" + _join_values(report_ids))
    if rule_ids:
        parts.append("规则来源 ID：" + _join_values(rule_ids))
    if preset_ids:
        parts.append("输出版本 ID：" + _join_values(preset_ids))
    if fixture_ids:
        parts.append("样本 ID：" + _join_values(fixture_ids))
    if ui_ids:
        parts.append("界面入口 ID：" + _join_values(ui_ids))
    if gate_ids:
        parts.append("人工确认 ID：" + _join_values(gate_ids))
    if risk_ids:
        parts.append("风险域 ID：" + _join_values(risk_ids))
    if receipt_ids:
        parts.append("回执 ID：" + _join_values(receipt_ids))
    normalized_channel = str(channel_text or "").strip()
    if normalized_channel:
        parts.append("通道：" + normalized_channel)
    return " / ".join(parts)


def _append_evidence_tooltip(base: str, **evidence) -> str:
    technical = _evidence_technical_detail(**evidence)
    normalized_base = str(base or "").strip()
    if not technical:
        return normalized_base
    if not normalized_base:
        return "技术证据：\n" + technical
    return normalized_base + "\n\n技术证据：\n" + technical


def _compact_display_values(
    values: Sequence[object],
    display_func,
    *,
    unit: str = "项",
    limit: int = 3,
) -> str:
    labels = [
        str(display_func(value) or "").strip()
        for value in _unique_values([str(value or "").strip() for value in values])
        if str(value or "").strip()
    ]
    if not labels:
        return "无"
    if len(labels) <= limit:
        return _join_values(labels)
    return _join_values(labels[:limit]) + f" 等 {len(labels)} {unit}"


def _evidence_count_label(label: str, values: Sequence[object]) -> str:
    count = len(_unique_values([str(value or "").strip() for value in values]))
    units = {
        "样本": "个",
        "界面入口": "个",
        "风险域": "类",
    }
    unit = units.get(label, "项")
    return f"{label} {count} {unit}" if count else f"{label} 0 {unit}"


def _request_cell_coverage_display(level: object) -> str:
    return _display_id(level, REQUEST_CELL_COVERAGE_DISPLAY_LABELS)


def _boundary_text_display(text: object) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    if normalized in BOUNDARY_TEXT_DISPLAY_LABELS:
        return BOUNDARY_TEXT_DISPLAY_LABELS[normalized]
    for needle, replacement in BOUNDARY_TEXT_DISPLAY_LABELS.items():
        if needle and needle in normalized:
            return replacement
    return normalized


def _manual_gate_display(gate_id: object) -> str:
    normalized = str(gate_id or "").strip()
    if not normalized:
        return ""
    if "professional_disclosure" in normalized:
        return "专业审阅确认"
    if "journal" in normalized:
        return "期刊规则确认"
    if "exam" in normalized:
        return "AI/复杂图确认"
    if "import_ai" in normalized:
        return "导入置信度确认"
    return normalized.replace("_", " ")


def _readiness_gap_display(text: object) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    replacements = (
        ("IP plugin handoff", "需要知识产权/专利插件接手"),
        ("plugin handoff", "需要插件接手"),
        ("manual boundary", "需要人工确认"),
        ("real plugin ecosystem", "需要真实插件生态"),
        ("professional review", "需要专业审阅"),
    )
    result = normalized
    for needle, replacement in replacements:
        result = result.replace(needle, replacement)
    return result


def _planning_preflight_recommendation_item(
    scene: SceneWorkspace,
) -> SummaryGridItem | None:
    targets = recommended_object_preflight_targets_for_scene(scene)
    if not targets:
        return None
    configured = {
        str(target or "").strip()
        for target in getattr(scene.compliance_profile.object_preflight, "scan_targets", [])
        if str(target or "").strip()
    }
    target_set = set(targets)
    if configured == target_set:
        value = "已应用"
        variant = "success"
    elif target_set.issubset(configured):
        value = "已覆盖"
        variant = "info"
    else:
        value = "需同步"
        variant = "warning"
    return SummaryGridItem(
        key="planning_scan_targets",
        label="场景族预检",
        value=value,
        detail=_join_values(targets),
        variant=variant,
    )


def _ooxml_touchpoint_detail(
    touchpoints: Sequence[object],
    preflight_targets: Sequence[object],
) -> str:
    touchpoint_text = _display_list(touchpoints, OOXML_TOUCHPOINT_DISPLAY_LABELS)
    target_text = _display_list(preflight_targets, OOXML_TOUCHPOINT_DISPLAY_LABELS)
    if not preflight_targets:
        return touchpoint_text
    return f"{touchpoint_text} / 预检: {target_text}"


def _planned_family_for_scene(scene: SceneWorkspace):
    for candidate in coverage_candidate_keys_for_config(scene):
        try:
            return get_planned_scene_family(candidate)
        except KeyError:
            continue
    return None


def _coverage_packs_for_scene(scene: SceneWorkspace) -> tuple[SceneCoveragePack, ...]:
    return coverage_packs_for_config(scene)


def _product_readiness_specs_for_scene(
    scene: SceneWorkspace,
) -> tuple[SceneProductReadinessSpec, ...]:
    specs: list[SceneProductReadinessSpec] = []
    seen: set[tuple[str, str]] = set()
    for pack in _coverage_packs_for_scene(scene):
        _append_readiness_spec(specs, seen, "pack", pack.pack_id)
    family = _planned_family_for_scene(scene)
    if family is not None:
        _append_readiness_spec(specs, seen, "family", family.family_id)
    return tuple(specs)


def _append_readiness_spec(
    specs: list[SceneProductReadinessSpec],
    seen: set[tuple[str, str]],
    subject_type: str,
    subject_id: str,
) -> None:
    key = (subject_type, subject_id)
    if key in seen:
        return
    try:
        spec = product_readiness_for(subject_id, subject_type=subject_type)
    except KeyError:
        return
    specs.append(spec)
    seen.add(key)


def _first_closure_task(packs: Sequence[SceneCoveragePack]):
    for pack in packs:
        if pack.closure_tasks:
            return pack.closure_tasks[0]
    return None


def _coverage_pack_tooltip(packs: Sequence[SceneCoveragePack]) -> str:
    lines: list[str] = []
    for pack in packs:
        lines.append(f"{pack.pack_id}: {pack.label}")
        lines.append(f"边界：{pack.boundary}")
        if pack.missing_closures:
            lines.append("未闭合：" + "；".join(pack.missing_closures[:3]))
    return "\n".join(lines)


def _coverage_pack_value(packs: Sequence[SceneCoveragePack]) -> str:
    if not packs:
        return "未匹配"
    if len(packs) == 1:
        return _coverage_pack_display_name(packs[0].pack_id)
    return f"{len(packs)} 类场景"


def _coverage_pack_detail(packs: Sequence[SceneCoveragePack]) -> str:
    if not packs:
        return ""
    if len(packs) == 1:
        pack = packs[0]
        return f"处理：{_coverage_pack_display_name(pack.pack_id)}；注意：{_boundary_text_display(pack.boundary)}"
    return _join_values(_coverage_pack_display_name(pack.pack_id) for pack in packs)


def _coverage_pack_display_name(pack_id: object) -> str:
    return _display_id(pack_id, COVERAGE_PACK_DISPLAY_LABELS)


def _family_display_name(family_id: object) -> str:
    return _display_id(family_id, FAMILY_DISPLAY_LABELS)


def _maturity_level_label(level: object) -> str:
    normalized = str(level or "").strip()
    if not normalized:
        return "成熟度未登记"
    if normalized.upper().startswith("L"):
        return f"成熟度 {normalized.upper()}"
    return normalized


def _first_slice_display(text: object) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return "已有最小可用流程"
    replacements = (
        ("existing thesis scene uses thesis_cn compliance profile and school_thesis count profile", "已接入论文规则和学校计数口径"),
        ("section word count + display item count + submission package manifest", "已打通分区计数、展示项计数和投稿包清单"),
        ("structured question source + student/teacher/answer visibility rendering", "已打通结构化题源和多版本显隐"),
        ("attachment inventory + word limit profile + application package manifest", "已打通附件清单、字数限制和申报包清单"),
        ("party/amount/date consistency + tracked-change protection + review/signing presets", "已打通合同字段一致性、修订保护和审阅/签署稿"),
        ("one-record-one-output xlsx/json batch + failure isolation + summary report", "已打通一条记录一个输出、失败隔离和汇总报告"),
        ("official sub-profile + formal/internal delivery + archive metadata", "已打通公文子配置、正式/内部交付和归档信息"),
        ("product asset schema + customer/internal delivery presets", "已打通产品资料规则和客户/内部版本"),
        ("chapter inventory + object-risk report", "已打通章节清单和对象风险报告"),
        ("fixed-layout field fill + placeholder residue report", "已打通固定版式填充和占位残留报告"),
        ("tracked-change protection", "修订保护"),
        ("field consistency", "字段一致性"),
        ("archive metadata", "归档信息"),
        ("delivery presets", "输出版本"),
        ("count profile", "计数口径"),
        ("material schema", "资料规则"),
        ("runtime", "运行链路"),
        ("report evidence", "报告证据"),
        ("first slice", "首个闭环"),
    )
    result = normalized
    for needle, replacement in replacements:
        result = result.replace(needle, replacement)
    return result


def _product_readiness_value(
    specs: Sequence[SceneProductReadinessSpec],
) -> str:
    if not specs:
        return "未登记"
    if len(specs) == 1:
        return _product_readiness_label(specs[0].product_readiness_level)
    levels = _unique_values(
        [spec.product_readiness_level for spec in specs if spec.product_readiness_level]
    )
    return " / ".join(_product_readiness_label(level) for level in levels)


def _product_readiness_label(level: str) -> str:
    return PRODUCT_READINESS_DISPLAY_LABELS.get(
        str(level or "").strip(),
        str(level or "").strip() or "未登记",
    )


def _product_readiness_variant(spec: SceneProductReadinessSpec) -> str:
    if spec.product_readiness_level == "green_l5":
        return "success"
    if spec.product_readiness_level in {"orange_l4", "yellow_l3"}:
        return "warning"
    if spec.product_readiness_level == "blue_boundary":
        return "warning"
    return "neutral"


def _product_readiness_detail(
    specs: Sequence[SceneProductReadinessSpec],
) -> str:
    if not specs:
        return ""
    details = [
        PRODUCT_READINESS_DETAIL_LABELS.get(
            spec.product_readiness_level,
            _product_readiness_label(spec.product_readiness_level),
        )
        for spec in specs
    ]
    return _join_values(dict.fromkeys(details))


def _product_readiness_gap_detail(
    specs: Sequence[SceneProductReadinessSpec],
) -> str:
    gaps: list[str] = []
    for spec in specs:
        for gap in spec.remaining_product_gaps:
            text = f"{spec.subject_id}: {gap}"
            if text not in gaps:
                gaps.append(text)
    return _join_values(_readiness_gap_display(gap) for gap in gaps[:3])


def _product_readiness_tooltip(
    specs: Sequence[SceneProductReadinessSpec],
) -> str:
    lines = [
        "可用程度会同时看配置闭合和真实交付证据，避免只通过静态检查就直接承诺可交付。"
    ]
    for spec in specs:
        lines.append(
            f"{_readiness_subject_display(spec)}："
            f"配置检查 {_static_closure_label(spec.static_closure_level)}；"
            f"可用程度 {_product_readiness_label(spec.product_readiness_level)}"
        )
        if spec.evidence_surfaces:
            lines.append(f"证据面：{len(spec.evidence_surfaces)} 项")
        if spec.remaining_product_gaps:
            lines.append(
                "还需确认："
                + _join_values(
                    _readiness_gap_display(gap)
                    for gap in spec.remaining_product_gaps[:3]
                )
            )
        if spec.rationale:
            lines.append("说明：" + _readiness_rationale_display(spec.rationale))
    return "\n".join(lines)


def _readiness_subject_display(spec: SceneProductReadinessSpec) -> str:
    if spec.subject_type == "pack":
        return _coverage_pack_display_name(spec.subject_id)
    if spec.subject_type == "family":
        return _family_display_name(spec.subject_id)
    return _display_id(spec.subject_id, {})


def _static_closure_label(level: object) -> str:
    labels = {
        "declared": "已登记",
        "audited": "已审计",
        "closed": "已闭合",
    }
    normalized = str(level or "").strip()
    return labels.get(normalized, normalized.replace("_", " ") or "未登记")


def _readiness_rationale_display(text: object) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    replacements = (
        ("General formatting", "通用格式清理"),
        ("Chinese academic support", "中文论文/课程论文"),
        ("English journal submission", "英文期刊投稿"),
        ("has", "已具备"),
        ("router", "路由"),
        ("template controls", "模板控件"),
        ("issue queue", "问题队列"),
        ("report", "报告"),
        ("field-level template repair routing", "字段级模板修复跳转"),
        ("real business template fixture evidence", "真实业务模板样本证据"),
        ("sample fixture", "样本文档"),
        ("while", "；同时"),
        ("core", "核心能力"),
    )
    result = normalized
    for needle, replacement in replacements:
        result = result.replace(needle, replacement)
    if any(ch in result for ch in "，。；、"):
        return result
    if len(result) > 96:
        return "已有运行、界面、报告和样本证据；仍按边界说明控制承诺范围。"
    return result


def _scene_matrix_dashboard_tooltip(dashboard) -> str:
    lines = [
        "Global scene-matrix dashboard combines pack, family, request-cell, "
        "Word-risk, control-contract, and product-readiness audits."
    ]
    for card in dashboard.cards:
        lines.append(f"{card.card_id}: {card.value} - {card.detail}")
    if dashboard.issues:
        lines.append(
            "blocking: "
            + _join_values(
                f"{issue.scope_id}:{issue.kind}" for issue in dashboard.issues[:3]
            )
        )
    if dashboard.warnings:
        lines.append(
            "warnings: "
            + _join_values(
                f"{warning.scope_id}:{warning.kind}"
                for warning in dashboard.warnings[:3]
            )
        )
    return "\n".join(lines)


def _boundary_capability_tooltip(specs) -> str:
    lines = [
        "边界能力矩阵记录专业判断、导入转换和插件交接证据；核心格式能力不冒充外部判断或转换质量。"
    ]
    for spec in specs:
        lines.append(f"{spec.capability_id}: {spec.label}")
        if spec.core_scope:
            lines.append("核心范围：" + _join_values(spec.core_scope[:2]))
        if spec.excluded_scope:
            lines.append("不处理内容：" + _join_values(spec.excluded_scope[:2]))
        if spec.risk_domain_ids:
            lines.append("风险域：" + _join_values(spec.risk_domain_ids[:4]))
        if spec.decision_requirement_ids:
            lines.append("决策要求：" + _join_values(spec.decision_requirement_ids[:4]))
        if spec.external_receipt_ids:
            lines.append("外部回执：" + _join_values(spec.external_receipt_ids[:4]))
        if spec.release_guardrail_ids:
            lines.append("交付守门：" + _join_values(spec.release_guardrail_ids[:4]))
        if spec.report_expectation_ids:
            lines.append("报告：" + _join_values(spec.report_expectation_ids[:4]))
    return "\n".join(lines)


def _scene_matrix_drilldown_tooltip(report) -> str:
    lines = [
        "Scene matrix drilldown exposes front-end browse entries for the "
        "dashboard, request-cell, plugin boundary, Word risk, import handoff, "
        "InputSourceProfile, ObjectPreflight actions, family fixture depth, "
        "CountProfile, material schema, delivery preset, formula/output/watermark, "
        "and maturity upgrade sources."
    ]
    for item in report.items:
        lines.append(
            f"{item.drilldown_id}: {item.visible_count}/{item.row_count} rows "
            f"from {item.source_id}"
        )
    if report.issues:
        lines.append(
            "blocking: "
            + _join_values(
                f"{issue.scope_id}:{issue.kind}" for issue in report.issues[:3]
            )
        )
    return "\n".join(lines)


def _closure_task_tooltip(task) -> str:
    lines = [
        task.summary,
        f"优先级：{task.priority}",
        f"负责人：{task.owner}",
        f"目标阶段：{task.target_phase}",
    ]
    lines.extend("验收：" + command for command in task.validation_commands)
    return "\n".join(lines)


def _sample_fixture_tooltip(summary: SceneSampleCoverageSummary) -> str:
    lines = ["样本登记：真实 DOCX 样本库"]
    lines.append(
        "覆盖资料包："
        + _join_values(_coverage_pack_display_name(pack_id) for pack_id in summary.pack_ids)
    )
    if summary.fixture_ids:
        lines.append(f"样本：{len(summary.fixture_ids)} 个")
    if summary.docx_surfaces:
        lines.append("Word 对象：" + _display_list(summary.docx_surfaces, OOXML_TOUCHPOINT_DISPLAY_LABELS))
    if summary.expected_behaviors:
        lines.append("预期处理：" + _display_list(summary.expected_behaviors, BEHAVIOR_DISPLAY_LABELS))
    if summary.manual_gate_ids:
        lines.append(
            "人工确认："
            + _join_values(_manual_gate_display(gate_id) for gate_id in summary.manual_gate_ids)
        )
    if summary.missing_pack_ids:
        lines.append(
            "缺少样本资料包："
            + _join_values(_coverage_pack_display_name(pack_id) for pack_id in summary.missing_pack_ids)
        )
    if summary.audit_issues:
        lines.append(
            "审计缺口："
            + "；".join(issue.message for issue in summary.audit_issues[:3])
        )
    for note in summary.boundary_notes[:3]:
        lines.append("边界：" + _boundary_text_display(note))
    return "\n".join(lines)


def _sample_fixture_boundary_detail(summary: SceneSampleCoverageSummary) -> str:
    parts = [_manual_gate_display(gate_id) for gate_id in summary.manual_gate_ids[:2]]
    parts.extend(_boundary_text_display(note) for note in summary.boundary_notes[:2])
    return _join_values(dict.fromkeys(part for part in parts if part))


def _request_cell_tooltip(summary: SceneRequestCellFixtureSummary) -> str:
    lines = ["常见说法登记：高频用户说法"]
    lines.append(
        "覆盖资料包："
        + _join_values(_coverage_pack_display_name(pack_id) for pack_id in summary.pack_ids)
    )
    lines.append(
        "状态："
        f"{summary.cell_count} 请求 / "
        f"{summary.fixture_cell_count} 有证据 / "
        f"{summary.family_proxy_count} 借用样本"
    )
    if summary.coverage_level_counts:
        lines.append(
            "层级："
            + _join_values(
                [
                    f"{_request_cell_coverage_display(level)} {count}"
                    for level, count in summary.coverage_level_counts
                ]
            )
        )
    if summary.fixture_ids:
        lines.append(f"样本：{len(summary.fixture_ids)} 个")
    if summary.family_proxy_sample_ids:
        lines.append(f"借用样本：{len(summary.family_proxy_sample_ids)} 个")
    if summary.audit_issues:
        lines.append(
            "审计缺口："
            + "；".join(issue.message for issue in summary.audit_issues[:3])
        )
    return "\n".join(lines)


def _unique_values(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _artifact_summary(artifacts) -> str:
    if artifacts is None:
        return "未设置"
    names: list[str] = []
    if bool(getattr(artifacts, "final_docx", False)):
        names.append("DOCX")
    if bool(getattr(artifacts, "compare_docx", False)):
        names.append("对比稿")
    if bool(getattr(artifacts, "report_json", False)):
        names.append("JSON")
    if bool(getattr(artifacts, "report_markdown", False)):
        names.append("Markdown")
    if bool(getattr(artifacts, "material_manifest", False)):
        names.append("资料清单")
    if bool(getattr(artifacts, "material_package", False)):
        names.append("资料包")
    return " / ".join(names) if names else "仅运行不输出"


def _delivery_artifact_detail(preset) -> str:
    rule_count = (
        len(list(getattr(preset, "content_visibility_rules", []) or []))
        if preset is not None
        else 0
    )
    if rule_count:
        return f"显隐规则 {rule_count} 条 / 由当前输出版本决定"
    return "由当前输出版本决定"


def _failure_variant(policy: str) -> str:
    return "warning" if policy == "block" else "neutral"


def _owner_layer_detail(layer_counts: Counter[str]) -> str:
    visible_layers = [
        OWNER_LAYER_DISPLAY_LABELS.get(layer, layer)
        for layer in ALLOWED_PARAMETER_OWNER_LAYERS
        if layer_counts.get(layer, 0)
    ]
    if not visible_layers:
        return "未登记参数归属"
    if len(visible_layers) <= 4:
        return "、".join(visible_layers) + "已分工"
    return f"{len(visible_layers)} 类参数归属已分工"


def _owner_layer_count_detail(layer_counts: Counter[str]) -> str:
    return " / ".join(
        f"{OWNER_LAYER_DISPLAY_LABELS.get(layer, layer)} {layer_counts.get(layer, 0)}"
        for layer in ALLOWED_PARAMETER_OWNER_LAYERS
        if layer_counts.get(layer, 0)
    )


def _ownership_audit_tooltip(audit: ParameterOwnershipAuditResult) -> str:
    lines = ["新增场景参数必须声明归属层、UI surface、执行消费点和存在理由。"]
    if audit.is_clean:
        lines.append("当前 SceneWorkspace 顶层字段和必审嵌套路径已登记。")
    if audit.missing_top_level_paths:
        lines.append("缺少顶层字段：" + ", ".join(audit.missing_top_level_paths))
    if audit.missing_required_paths:
        lines.append("缺少必审路径：" + ", ".join(audit.missing_required_paths))
    if audit.unknown_spec_paths:
        lines.append("未知 registry 路径：" + ", ".join(audit.unknown_spec_paths))
    if audit.invalid_owner_layers:
        invalid = ", ".join(
            f"{path}:{owner}" for path, owner in audit.invalid_owner_layers
        )
        lines.append("非法归属层：" + invalid)
    return "\n".join(lines)


def _control_contract_detail(contracts: Sequence[object]) -> str:
    labels = [
        str(getattr(contract, "canonical_label", "") or "").strip()
        for contract in contracts
    ]
    groups: list[str] = []
    if any(label in labels for label in ("左缩进", "右缩进", "特殊缩进")):
        groups.append("缩进")
    if any(label in labels for label in ("行距", "段前", "段后")):
        groups.append("段落间距")
    if "固定版位行高" in labels:
        groups.append("固定版式行高")
    if "公式策略" in labels:
        groups.append("公式")
    if "水印状态" in labels:
        groups.append("水印")
    if any(label in labels for label in ("资料 Schema", "输出版本", "内容显隐", "插件人工确认")):
        groups.append("交付边界")
    if not groups:
        return f"{len(contracts)} 类控件已归一"
    return "、".join(groups[:5]) + "等已归一"


def _control_contract_full_detail(contracts: Sequence[object]) -> str:
    labels = [
        str(getattr(contract, "canonical_label", "") or "").strip()
        for contract in contracts
    ]
    display_labels = {"资料 Schema": "资料规则"}
    preferred = [
        display_labels.get(label, label)
        for label in (
            "左缩进",
            "右缩进",
            "特殊缩进",
            "行距",
            "段前",
            "段后",
            "固定版位行高",
            "公式策略",
            "水印状态",
            "资料 Schema",
            "输出版本",
            "内容显隐",
            "插件人工确认",
        )
        if label in labels
    ]
    return " / ".join(preferred) if preferred else f"{len(contracts)} 个控件契约"


def _control_contract_owner_detail(owner_counts: Counter[str]) -> str:
    owners = [
        OWNER_LAYER_DISPLAY_LABELS.get(owner, owner)
        for owner in ("template", "scene", "material", "output", "plugin")
        if owner_counts.get(owner, 0)
    ]
    if not owners:
        return "未登记控件归属"
    if len(owners) <= 4:
        return "、".join(owners) + "各管一段"
    return f"{len(owners)} 类控件归属已分开"


def _control_contract_owner_count_detail(owner_counts: Counter[str]) -> str:
    return " / ".join(
        f"{OWNER_LAYER_DISPLAY_LABELS.get(owner, owner)} {owner_counts.get(owner, 0)}"
        for owner in ("template", "scene", "material", "output", "plugin")
        if owner_counts.get(owner, 0)
    )


def _control_contract_audit_tooltip(audit: ControlContractAuditResult) -> str:
    lines = ["模板、场景和 Workbench 的同名参数必须使用同一套控件契约。"]
    if audit.is_clean:
        lines.append("当前必审控件、配对字段、单位和源码证据已通过审计。")
    if audit.missing_required_contracts:
        lines.append("缺少必审契约：" + ", ".join(audit.missing_required_contracts))
    if audit.invalid_owner_layers:
        invalid = ", ".join(
            f"{contract_id}:{owner}" for contract_id, owner in audit.invalid_owner_layers
        )
        lines.append("非法归属层：" + invalid)
    if audit.missing_paired_contracts:
        pairs = ", ".join(
            f"{left}->{right}" for left, right in audit.missing_paired_contracts
        )
        lines.append("缺少配对契约：" + pairs)
    if audit.missing_evidence_files:
        files = ", ".join(
            f"{contract_id}:{path}" for contract_id, path in audit.missing_evidence_files
        )
        lines.append("缺少源码证据文件：" + files)
    if audit.missing_evidence_markers:
        markers = ", ".join(
            f"{contract_id}:{marker}"
            for contract_id, _path, marker in audit.missing_evidence_markers
        )
        lines.append("缺少源码证据 marker：" + markers)
    return "\n".join(lines)


def _join_values(values: Sequence[object]) -> str:
    normalized = [str(value).strip() for value in values if str(value or "").strip()]
    return " / ".join(normalized) if normalized else "无"


def scene_application_boundary_mode(scene: SceneWorkspace | None) -> str:
    boundary = getattr(scene, "application_boundary", None)
    mode = str(getattr(boundary, "mode", "") or "").strip()
    if mode in SCENE_APPLICATION_BOUNDARY_DISPLAY_LABELS:
        return mode
    return "follow_template"


def scene_application_boundary_display_name(scene: SceneWorkspace | None) -> str:
    mode = scene_application_boundary_mode(scene)
    return SCENE_APPLICATION_BOUNDARY_DISPLAY_LABELS[mode]


def scene_application_boundary_detail(scene: SceneWorkspace | None) -> str:
    mode = scene_application_boundary_mode(scene)
    return SCENE_APPLICATION_BOUNDARY_DETAILS[mode]


def _enabled_scope_zone_keys(scene: SceneWorkspace | None) -> tuple[str, ...]:
    if scene is None:
        return ()
    sections = getattr(getattr(scene, "format_scope", None), "sections", {}) or {}
    ordered = [
        key
        for key in SCENE_SCOPE_ZONE_ORDER
        if bool(sections.get(key, False))
    ]
    ordered.extend(
        str(key)
        for key, enabled in sections.items()
        if bool(enabled) and key not in SCENE_SCOPE_ZONE_DISPLAY_LABELS
    )
    return tuple(ordered)


def _scope_zone_detail(zone_keys: Sequence[str]) -> str:
    labels = [
        SCENE_SCOPE_ZONE_DISPLAY_LABELS.get(str(key), str(key))
        for key in zone_keys
    ]
    if not labels:
        return "无"
    if len(labels) <= 4:
        return "、".join(labels)
    return "、".join(labels[:4]) + f"等 {len(labels)} 个"


def _first_or_empty(values: Sequence[str]) -> str:
    return values[0] if values else ""


__all__ = [
    "LATEX_POLICY_LABELS",
    "MARKDOWN_POLICY_LABELS",
    "PRESERVATION_MODE_LABELS",
    "SCENE_SCOPE_ZONE_DISPLAY_LABELS",
    "SCENE_APPLICATION_BOUNDARY_DISPLAY_LABELS",
    "SceneRequestCellListItemProjection",
    "SceneSampleFixtureListItemProjection",
    "build_academic_rule_source_evidence_summary_items",
    "build_application_report_evidence_summary_items",
    "build_boundary_capability_evidence_summary_items",
    "build_compliance_summary_items",
    "build_coverage_summary_items",
    "build_control_contract_summary_items",
    "build_delivery_summary_items",
    "build_fixed_layout_batch_evidence_summary_items",
    "build_input_profile_summary_items",
    "build_journal_submission_evidence_summary_items",
    "build_official_policy_evidence_summary_items",
    "build_parameter_ownership_summary_items",
    "build_planning_family_summary_items",
    "build_product_readiness_summary_items",
    "build_scene_matrix_dashboard_summary_items",
    "build_scene_matrix_drilldown_summary_items",
    "build_scene_style_override_summary_items",
    "build_technical_long_doc_evidence_summary_items",
    "build_scene_request_cell_summary_items",
    "build_scene_scope_summary_items",
    "build_scene_sample_fixture_detail_text",
    "build_scene_sample_fixture_summary_items",
    "build_scene_overview_summary_items",
    "material_asset_role_display_name",
    "material_field_display_name",
    "material_schema_display_name",
    "scene_request_cell_count_text",
    "scene_request_cell_count_tooltip",
    "scene_request_cell_empty_text",
    "scene_request_cell_evidence_status_text",
    "scene_request_cell_evidence_status_tooltip",
    "scene_request_cell_filter_label",
    "scene_request_cell_filter_options",
    "scene_request_cell_fixture_specs_for_scene",
    "scene_request_cell_list_item_projection",
    "scene_request_cell_matches_filter",
    "scene_sample_fixture_list_item_projection",
    "scene_sample_fixture_library_status_text",
    "scene_sample_fixture_library_status_tooltip",
    "scene_application_boundary_detail",
    "scene_application_boundary_display_name",
    "scene_application_boundary_mode",
    "recommended_object_preflight_targets_for_scene",
]
