"""Workbench issue display, visual, and evidence projections."""

from __future__ import annotations

from src.ui.adapters.field_display_names import (
    field_display_name,
    replace_field_keys_with_display_names,
)
from src.ui.adapters.workbench_issue_models import (
    ISSUE_ACTION_GROUP_VALUES,
    WorkbenchIssueActionVisualProjection,
    WorkbenchIssueEvidenceLineProjection,
    WorkbenchIssueItem,
)


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
    "Quick cleanup should preserve field/comment layout and warn instead of rewriting risky Word objects.": "清理格式时会保留域和批注；遇到高风险对象先提醒",
    "Business templates can be cleaned through template field repair without making professional or content-quality promises.": "可清理业务模板字段，但不承诺专业判断或内容质量",
    "Contract samples do not imply legal review.": "合同样本只验证格式和字段，不代表法律审查",
    "Missing or inconsistent contract party, amount, date, or signature assets should downgrade to a field/signature boundary report.": "合同方、金额、日期或签章资料不一致时，会降级为字段/签章边界报告",
    "Fixed-layout row height is not generic table styling.": "固定行高只用于套打/固定版式，不当作通用表格样式",
    "HR batch samples do not verify personnel truthfulness.": "人事批量样本不核验人员信息真伪",
    "Disclosure samples do not perform audit or assurance judgment.": "披露样本不执行审计或鉴证判断",
    "Import samples require confidence/manual confirmation before core execution.": "导入样本需要置信度检查或人工确认后再执行",
    "Bid strategy and certificate truthfulness remain outside core.": "不判断投标策略，也不核验证照真实性",
    "Missing certificate, license, or required archive assets should downgrade to an attachment inventory and missing-items report.": "证照或归档资料缺失时，会降级为附件清单和缺项报告",
}


def workbench_issue_action_visual(
    action_group: str,
    *,
    status: str = "",
) -> WorkbenchIssueActionVisualProjection:
    """Return the shared visual semantics for an action group."""

    group = str(action_group or "").strip()
    if group not in ISSUE_ACTION_GROUP_VALUES:
        group = "view_only"
    status_value = str(status or "").strip().lower()
    if group == "handle_first":
        return WorkbenchIssueActionVisualProjection(
            group=group,
            label="先处理",
            rank=0,
            badge_tone="error",
            detail_tone="error",
        )
    if group == "confirm":
        return WorkbenchIssueActionVisualProjection(
            group=group,
            label="建议确认",
            rank=1,
            badge_tone="info",
            detail_tone="info",
        )
    return WorkbenchIssueActionVisualProjection(
        group=group,
        label="仅查看",
        rank=2,
        badge_tone="neutral",
        detail_tone="success" if status_value == "resolved" else "neutral",
    )


def workbench_issue_evidence_lines(
    item: WorkbenchIssueItem,
) -> tuple[WorkbenchIssueEvidenceLineProjection, ...]:
    """Return structured readable evidence rows for one Workbench issue."""

    if not isinstance(item, WorkbenchIssueItem):
        return ()
    lines: list[WorkbenchIssueEvidenceLineProjection] = []
    for raw_line in list(getattr(item, "details", ()) or ()):
        projected = _workbench_issue_evidence_line_projection(raw_line)
        if projected is not None:
            lines.append(projected)
    for note in list(getattr(item, "source_notes", ()) or ()):
        source = workbench_issue_source_note_label(note)
        if source:
            projected_source = _workbench_issue_evidence_line_projection(source)
            if projected_source is not None and projected_source.kind != "note":
                lines.append(projected_source)
            else:
                lines.append(
                    WorkbenchIssueEvidenceLineProjection(
                        kind="source",
                        label="来源",
                        text=source,
                    )
                )
    return tuple(lines)


def workbench_issue_evidence_actions(
    item: WorkbenchIssueItem,
) -> tuple[tuple[str, str, str], ...]:
    """Return action-capable evidence rows as stable tuples."""

    return tuple(
        (line.kind, line.action_type, line.action_value)
        for line in workbench_issue_evidence_lines(item)
        if line.has_action()
    )


def workbench_issue_evidence_body_text(item: WorkbenchIssueItem) -> str:
    """Return a newline fallback body for legacy label-based issue details."""

    lines = [line.display_text() for line in workbench_issue_evidence_lines(item)]
    return "\n".join(lines) if lines else "暂无证据。"


def workbench_issue_display_text(
    text: str,
    *,
    include_raw_field_key: bool = True,
    translate_field_keys: bool = True,
) -> str:
    """Return user-facing display text for issue details."""

    value = str(text or "").strip()
    if not value:
        return ""
    for needle, replacement in BOUNDARY_TEXT_DISPLAY_LABELS.items():
        if needle and needle in value:
            value = value.replace(needle, replacement)
    for pack_id, label in sorted(
        COVERAGE_PACK_DISPLAY_LABELS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if pack_id and pack_id in value:
            value = value.replace(pack_id, label)
    replacements = (
        ("Contract delivery", "合同交付"),
        ("Exam and teaching materials", "试卷/教学资料"),
        ("English journal submission", "英文期刊投稿"),
        ("Chinese academic", "中文论文/课程论文"),
        ("Bidding materials", "标书/资质包"),
        ("Official policy", "公文/会议纪要"),
        ("Technical long documents", "技术长文档"),
        ("Application reports", "项目申报/产品材料"),
        ("Batch forms", "批量表单/套打"),
        ("Professional disclosure", "专业披露/审阅"),
        ("Import and AI boundary", "导入与 AI 辅助"),
        ("contract_delivery: missing_surfaces", "合同交付：样本缺少 Word 对象"),
        ("合同交付: missing_surfaces", "合同交付：样本缺少 Word 对象"),
        ("合同交付: 样本缺少 Word 对象", "合同交付：样本缺少 Word 对象"),
        ("合同交付: 不提供", "合同交付：不提供"),
        ("exam_ai_quality_diagram_plugin", "试卷 AI/复杂图插件"),
        ("journal_publisher_rule_review_gate", "期刊规则确认"),
        ("exam_ai_complex_diagram_gate", "试卷 AI 与复杂图确认"),
        ("professional_disclosure_review_gate", "专业披露审阅确认"),
        ("import_ai_conversion_gate", "导入/AI 转换确认"),
        ("ai_content_quality", "AI 内容质量"),
        ("ai_quality_judgment", "AI 内容质量判断"),
        ("audit_opinion", "审计意见"),
        ("citation_source_truthfulness", "引用来源真实性"),
        ("financial_assurance", "财务鉴证"),
        ("full_latex_project_conversion", "完整 LaTeX 工程转换"),
        ("geometry_diagram_generation", "复杂图生成"),
        ("legal_conclusion", "法律结论"),
        ("lossless_pdf_to_word", "PDF 到 Word 无损转换"),
        ("medical_or_drug_regulatory_conclusion", "医疗/药品监管结论"),
        ("ocr_truthfulness", "OCR 内容真实性"),
        ("patentability_judgment", "可专利性判断"),
        ("publisher_final_layout_guarantee", "出版社最终版式保证"),
        ("translation_quality_judgment", "翻译质量判断"),
        ("unreviewed_rule_fetching", "未复核规则抓取"),
        ("ContentVisibilityRule", "内容显隐规则"),
        ("missing_required_pack_fixture", "缺少资料包样本"),
        ("missing_required_surface", "缺少必需 Word 对象"),
        ("missing_surfaces", "样本缺少 Word 对象"),
        ("Sample fixture must declare at least one DOCX surface.", "样本需要声明至少一个 Word 对象。"),
        ("Required pack '", "资料包“"),
        ("' has no DOCX sample fixture.", "”缺少 Word 样本。"),
        ("人工确认：required", "人工确认：必须确认"),
        ("人工确认：optional", "人工确认：可选"),
        ("置信度报告：required", "置信度报告：必须生成"),
        ("置信度报告：optional", "置信度报告：可选"),
        ("覆盖 pack：", "覆盖资料包："),
        ("coverage pack：", "覆盖资料包："),
        ("manual gate：", "人工确认："),
        ("fixture：", "样本文件："),
        ("family：", "场景族："),
        ("pack：", "资料包："),
    )
    for source, target in replacements:
        value = value.replace(source, target)
    if translate_field_keys:
        value = replace_field_keys_with_display_names(
            value,
            include_raw_key=include_raw_field_key,
        )
    return value


def workbench_issue_source_note_label(note: str) -> str:
    """Return user-facing source labels for raw issue source notes."""

    value = workbench_issue_display_text(note)
    labels = {
        "scene_sample_fixture_registry": "样本覆盖登记",
        "scene_parameter_ownership registry": "参数归属登记",
        "control_contract_registry": "控件边界登记",
        "question_figure_repair_queue": "题图处理队列",
        "asset_items.metadata.comparison_issue_*": "题图素材检查",
    }
    return labels.get(value, value)


def _workbench_issue_evidence_line_projection(
    line: str,
) -> WorkbenchIssueEvidenceLineProjection | None:
    value = workbench_issue_display_text(
        line,
        translate_field_keys=False,
    )
    if not value:
        return None
    prefix_map = (
        ("参数路径：", "parameter_path", "参数", "navigate_parameter"),
        ("证据：", "evidence_file", "证据文件", "open_evidence"),
        ("输出路径：", "output_path", "输出", "open_output"),
        ("记录名称：", "record", "记录", ""),
        ("来源：", "source", "来源", ""),
        ("替换来源：", "replacement", "替换来源", "open_replacement"),
        ("保护模式：", "guard", "保护", ""),
        ("扫描对象：", "scan_target", "扫描", ""),
    )
    for prefix, kind, label, action_type in prefix_map:
        if value.startswith(prefix):
            text = value.removeprefix(prefix).strip()
            display_text = text
            if kind == "parameter_path":
                display_text = field_display_name(text) or text
            elif kind not in {
                "evidence_file",
                "output_path",
                "replacement",
            }:
                display_text = replace_field_keys_with_display_names(text)
            return WorkbenchIssueEvidenceLineProjection(
                kind=kind,
                label=label,
                text=display_text,
                action_type=action_type,
                action_value=text if action_type else "",
                action_label=(
                    _workbench_issue_evidence_action_label(action_type)
                    if action_type
                    else ""
                ),
                tone=_workbench_issue_evidence_line_tone(kind, action_type),
            )
    return WorkbenchIssueEvidenceLineProjection(
        kind="note",
        label="说明",
        text=workbench_issue_display_text(value),
    )


def _workbench_issue_evidence_action_label(action_type: str) -> str:
    action = str(action_type or "").strip()
    if action == "navigate_parameter":
        return "定位参数"
    if action == "open_output":
        return "打开输出"
    if action == "open_replacement":
        return "打开来源"
    return "打开证据"


def _workbench_issue_evidence_line_tone(kind: str, action_type: str) -> str:
    if str(action_type or "").strip():
        return "primary"
    normalized = str(kind or "").strip()
    if normalized in {"guard", "scan_target"}:
        return "info"
    return "neutral"
