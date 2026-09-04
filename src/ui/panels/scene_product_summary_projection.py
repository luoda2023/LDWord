"""Summary projection helpers for scene configuration surfaces."""

from __future__ import annotations

from collections.abc import Sequence

from src.config.default_delivery_identity import (
    DefaultDeliveryIdentity,
    project_default_delivery_identity,
)
from src.config.delivery_preset_display import (
    DELIVERY_PRESET_DISPLAY_LABELS,
    delivery_preset_display_name,
)
from src.config.material_schema_registry import (
    build_material_requirements,
    list_material_schemas,
)
from src.config.scene import SceneWorkspace
from src.config.scene_family_registry import get_planned_scene_family
from src.config.scene_product_coverage_manifest import (
    SceneCoveragePack,
    coverage_candidate_keys_for_config,
    coverage_packs_for_config,
)
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

# Scene/contract summary localization only. Material-package previews must use
# labels explicitly owned by a package domain object and must never extend or
# consume this registry to manufacture field metadata.
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

DOCUMENT_SCOPE_DISPLAY_LABELS = {
    "all": "全部内容",
    "body": "仅正文",
    "selected": "自选区域",
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

BOUNDARY_TEXT_DISPLAY_LABELS = {
    "does not judge professional compliance": "不判断专业合规，只处理格式和对象风险",
    "does not absorb English journal submission or exam generation": "不混入英文投稿或试卷生成方案",
    "does not promise publisher-final layout or unreviewed rule fetching": "不承诺出版社最终版式；目标期刊规则需人工确认",
    "does not guarantee AI content quality or complex diagram generation": "不保证 AI 内容质量或复杂图生成",
    "does not judge bidding strategy, legal conclusions, or certificate authenticity": "不判断投标策略、法律结论或证书真伪",
    "does not create many small administrative top-level scenes": "不为每类小公文单独开顶层方案",
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


def _build_scene_core_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    input_profile = scene.input_source_profile
    compliance = scene.compliance_profile
    preflight = compliance.object_preflight
    delivery_identity = project_default_delivery_identity(scene)

    return (
        SummaryGridItem(
            key="input_profile",
            label="输入",
            value=_format_list_label(input_profile.accepted_formats),
            detail=_input_policy_detail(scene),
            variant="info",
            icon_name="file-input",
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
            value=_default_delivery_identity_display(delivery_identity),
            detail=_delivery_overview_detail(scene),
            variant="success" if delivery_identity.is_ok else "warning",
            icon_name="file-output",
        ),
    )


def build_product_scene_overview_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    """Return customer-facing status without engineering maturity evidence."""

    coverage_items = tuple(
        item
        for item in build_coverage_summary_items(scene)
        if item.key in {"coverage_pack", "coverage_plugin_boundary"}
    )
    return (*_build_scene_core_summary_items(scene), *coverage_items)


def build_scene_scope_summary_items(
    scene: SceneWorkspace | None,
) -> tuple[SummaryGridItem, ...]:
    """Return summary items for the plan-owned document scope."""

    label = scene_document_scope_display_name(scene)
    detail = scene_document_scope_detail(scene)
    if scene is None:
        value = "选择处理范围"
        variant = "info"
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


def build_coverage_summary_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    packs = _coverage_packs_for_scene(scene)
    if not packs:
        return ()

    plugin_count = sum(1 for pack in packs if pack.plugin_boundary)
    first_task = _first_closure_task(packs)
    items = [
        SummaryGridItem(
            key="coverage_pack",
            label="适用方案",
            value=_coverage_pack_value(packs),
            detail=_coverage_pack_detail(packs),
            variant="warning"
            if any(pack.missing_closures for pack in packs)
            else "success",
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


def build_input_profile_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
    profile = scene.input_source_profile
    requirements = build_material_requirements(
        profile.material_schema_id,
        schema_ids=getattr(profile, "material_schema_ids", ()),
        extra_required_fields=profile.required_material_fields,
        extra_required_asset_roles=profile.required_image_roles,
    )
    accepted_formats = _display_list(profile.accepted_formats, FORMAT_DISPLAY_LABELS)
    structured_formats = _display_list(
        profile.structured_formats, FORMAT_DISPLAY_LABELS
    )
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
            value=FAILURE_POLICY_LABELS.get(
                profile.failure_policy, profile.failure_policy
            ),
            detail="资料或输入不满足时的方案级处理方式",
            variant=_failure_variant(profile.failure_policy),
        ),
    )


def build_compliance_summary_items(
    scene: SceneWorkspace,
) -> tuple[SummaryGridItem, ...]:
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
            detail=FAILURE_POLICY_LABELS.get(
                profile.failure_policy, profile.failure_policy
            ),
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
    identity = project_default_delivery_identity(scene)
    default_id = identity.requested_id
    default = identity.preset
    default_display = _default_delivery_identity_display(identity)
    preset_display_names = [_delivery_preset_display_name(preset) for preset in presets]

    return (
        SummaryGridItem(
            key="default_delivery",
            label="默认交付",
            value=default_display,
            detail=_delivery_identity_detail(identity),
            variant="success" if identity.is_ok else "warning",
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
            variant="info" if default is not None else "warning",
        ),
        SummaryGridItem(
            key="structured",
            label="结构化中间产物",
            value="保留"
            if bool(getattr(default, "include_structured_intermediate", False))
            else "不保留",
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
    return _join_values(
        _material_schema_display_name(schema_id) for schema_id in schema_ids
    )


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
            return schema.label or _display_id(
                normalized, MATERIAL_SCHEMA_DISPLAY_LABELS
            )
    return _display_id(normalized, MATERIAL_SCHEMA_DISPLAY_LABELS)


def material_schema_display_name(schema_id: object) -> str:
    return _material_schema_display_name(schema_id)


def _material_field_detail(field_keys: Sequence[object]) -> str:
    return _display_named_values(field_keys, _material_field_display_name, unit="字段")


def _material_asset_role_detail(role_keys: Sequence[object]) -> str:
    return _display_named_values(
        role_keys, _material_asset_role_display_name, unit="角色"
    )


def _material_field_display_name(field_key: object) -> str:
    normalized = str(field_key or "").strip()
    if not normalized:
        return ""
    if normalized in MATERIAL_FIELD_DISPLAY_LABELS:
        return MATERIAL_FIELD_DISPLAY_LABELS[normalized]
    for schema in list_material_schemas():
        for field in schema.fields:
            if field.key == normalized:
                return field.label or _display_id(
                    normalized, MATERIAL_FIELD_DISPLAY_LABELS
                )
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
                return role.label or _display_id(
                    normalized, MATERIAL_ASSET_ROLE_DISPLAY_LABELS
                )
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
    skip = (
        "高风险模块会先跳过"
        if preflight.skip_high_risk_modules
        else "高风险模块不自动跳过"
    )
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
    rule_label = PROFILE_DISPLAY_LABELS.get(
        rule_family,
        PROFILE_DISPLAY_LABELS.get(rule_family.replace("_format", ""), "基础格式规则"),
    )
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


def _default_delivery_identity_display(identity: DefaultDeliveryIdentity) -> str:
    if identity.is_ok:
        return _delivery_preset_display_name(identity.preset)
    if identity.status == "invalid":
        return f"无效引用：{identity.requested_id}"
    return "未设置"


def _delivery_identity_detail(identity: DefaultDeliveryIdentity) -> str:
    if identity.is_ok:
        return _delivery_default_detail(identity.preset)
    if identity.status == "invalid":
        return "默认交付引用无效，请先选择有效输出版本"
    return "未设置默认交付版本"


def _delivery_preset_display_name(preset_or_id: object) -> str:
    return delivery_preset_display_name(preset_or_id)


def _delivery_preset_tooltip(preset: object | None, fallback_id: object = "") -> str:
    preset_id = str(
        getattr(preset, "preset_id", "") if preset is not None else fallback_id
    ).strip()
    label = str(getattr(preset, "label", "") if preset is not None else "").strip()
    parts = [
        "默认交付",
        _delivery_preset_display_name(preset if preset is not None else preset_id),
    ]
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
    return REPORT_LEVEL_DISPLAY_LABELS.get(
        normalized, _display_id(normalized, REPORT_LEVEL_DISPLAY_LABELS)
    )


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


def _planning_preflight_recommendation_item(
    scene: SceneWorkspace,
) -> SummaryGridItem | None:
    targets = recommended_object_preflight_targets_for_scene(scene)
    if not targets:
        return None
    configured = {
        str(target or "").strip()
        for target in getattr(
            scene.compliance_profile.object_preflight, "scan_targets", []
        )
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
        label="方案族预检",
        value=value,
        detail=_join_values(targets),
        variant=variant,
    )


def _planned_family_for_scene(scene: SceneWorkspace):
    for candidate in coverage_candidate_keys_for_config(scene):
        try:
            return get_planned_scene_family(candidate)
        except KeyError:
            continue
    return None


def _coverage_packs_for_scene(scene: SceneWorkspace) -> tuple[SceneCoveragePack, ...]:
    return coverage_packs_for_config(scene)


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
    return f"{len(packs)} 类方案"


def _coverage_pack_detail(packs: Sequence[SceneCoveragePack]) -> str:
    if not packs:
        return ""
    if len(packs) == 1:
        pack = packs[0]
        return f"处理：{_coverage_pack_display_name(pack.pack_id)}；注意：{_boundary_text_display(pack.boundary)}"
    return _join_values(_coverage_pack_display_name(pack.pack_id) for pack in packs)


def _coverage_pack_display_name(pack_id: object) -> str:
    return _display_id(pack_id, COVERAGE_PACK_DISPLAY_LABELS)


def _closure_task_tooltip(task) -> str:
    lines = [
        task.summary,
        f"优先级：{task.priority}",
        f"负责人：{task.owner}",
        f"目标阶段：{task.target_phase}",
    ]
    lines.extend("验收：" + command for command in task.validation_commands)
    return "\n".join(lines)


def _artifact_summary(artifacts) -> str:
    if artifacts is None:
        return "未设置"
    names: list[str] = []
    if bool(getattr(artifacts, "final_docx", False)):
        names.append("DOCX")
    if bool(getattr(artifacts, "review_pdf", False)):
        names.append("审阅 PDF")
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


def _join_values(values: Sequence[object]) -> str:
    normalized = [str(value).strip() for value in values if str(value or "").strip()]
    return " / ".join(normalized) if normalized else "无"


def scene_document_scope_mode(scene: SceneWorkspace | None) -> str:
    scope = getattr(scene, "document_scope", None)
    mode = str(getattr(scope, "mode", "") or "").strip()
    if mode in DOCUMENT_SCOPE_DISPLAY_LABELS:
        return mode
    return "all"


def scene_document_scope_display_name(scene: SceneWorkspace | None) -> str:
    mode = scene_document_scope_mode(scene)
    return DOCUMENT_SCOPE_DISPLAY_LABELS[mode]


def scene_document_scope_detail(scene: SceneWorkspace | None) -> str:
    if scene is None or scene_document_scope_mode(scene) != "selected":
        return ""
    from src.config.document_scope import document_scope_role_label

    return "、".join(
        document_scope_role_label(role)
        for role in (scene.document_scope.selected_roles or ())
    )
