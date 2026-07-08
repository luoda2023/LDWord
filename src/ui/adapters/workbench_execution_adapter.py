from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from src.config.control_contract_registry import (
    ControlContractAuditResult,
    audit_control_contract_registry,
    get_control_contract,
    resolve_control_contract_evidence_locations,
)
from src.config.material_context import MaterialExecutionContext
from src.config.material_schema_registry import (
    evaluate_material_requirements,
    missing_material_schema_ids,
    recommend_material_schema_replacement,
    resolve_material_schema_ids,
)
from src.config.plugin_manual_gate import plugin_manual_gate_for_pack
from src.config.scene_parameter_ownership import (
    ParameterOwnershipAuditResult,
    audit_scene_parameter_ownership,
)
from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    coverage_packs_for_family,
    coverage_packs_for_scene,
    get_scene_coverage_pack,
)
from src.config.scene_sample_fixture_registry import (
    SceneSampleFixtureAuditIssue,
    audit_scene_sample_fixtures,
    get_scene_sample_fixture,
    scene_sample_fixtures_for_pack,
)
from src.config.style_difference_projection import (
    StyleDifferenceProjection,
    StyleDifferenceSummaryProjection,
    build_style_difference_summary_projection,
)
from src.config.style_field_descriptors import (
    canonical_paragraph_style_field_id,
    scene_style_navigation_target_from_field_id,
)
from src.config.materials import AssetItem
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope

from src.ui.panels.workbench.state import (
    ArtifactItemState,
    ExecutionProgressState,
    ExecutionResultState,
    ReadinessState,
    RecentRunState,
)
from src.ui.panels.workbench.execution_flow_projection import normalize_workbench_stage_text
from src.ui.adapters.field_display_names import (
    field_display_name,
    replace_field_keys_with_display_names,
)
from src.ui.adapters.workbench_artifact_items import (
    _artifact_browser_label,
    _artifact_label,
    _build_artifact_items,
    _planned_output_preflight_items,
    _split_issue_detail_text,
    workbench_artifact_display_items,
)
from src.ui.adapters.workbench_issue_models import (
    ISSUE_ACTION_GROUP_VALUES,
    ISSUE_STATUS_VALUES,
    ISSUE_TERMINAL_STATUS_VALUES,
    MaterialReadinessIssueGroups,
    WorkbenchIssueActionVisualProjection,
    WorkbenchIssueEvidenceLineProjection,
    WorkbenchIssueItem,
    WorkbenchIssueQueueSummary,
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


class WorkbenchExecutionAdapter:
    def build_readiness(
        self,
        *,
        has_document: bool,
        has_strategy: bool,
        material_schema_reasons: list[str] | None = None,
    ) -> ReadinessState:
        reasons: list[str] = []
        if not has_document:
            reasons.append("未选择文档")
        if not has_strategy:
            reasons.append("未选择策略")
        reasons.extend(_clean_reason_list(material_schema_reasons))
        return ReadinessState(
            ready=not reasons,
            label="待执行",
            reasons=reasons,
        )

    def build_progress_state(
        self,
        *,
        stage_text: str,
        current_step: int,
        total_steps: int,
    ) -> ExecutionProgressState:
        sanitized_total_steps = max(total_steps, 0)
        if sanitized_total_steps <= 0:
            sanitized_current_step = 0
        else:
            sanitized_current_step = min(max(current_step, 0), sanitized_total_steps)
        percent = 0
        if sanitized_total_steps > 0:
            percent = int(sanitized_current_step / sanitized_total_steps * 100)
        return ExecutionProgressState(
            stage_text=normalize_workbench_stage_text(stage_text),
            current_step=sanitized_current_step,
            total_steps=sanitized_total_steps,
            percent=percent,
        )

    def build_result_state(
        self,
        *,
        status: str,
        output_path: str,
        report_paths: list[str],
        failed_count: int,
        error_text: str,
        output_paths: dict[str, str] | None = None,
        compare_paths: dict[str, str] | None = None,
        intermediate_paths: dict[str, str] | None = None,
        material_manifest_paths: dict[str, str] | None = None,
        material_package_paths: dict[str, str] | None = None,
        scene_sample_manifest_paths: dict[str, str] | None = None,
        output_target_preflight: dict[str, object] | None = None,
        diagnostics_count: int = 0,
        diagnostics_summary: str = "",
        style_source: dict[str, object] | None = None,
        style_source_summary: str = "",
        object_preflight: dict[str, object] | None = None,
        material_field_consistency: dict[str, object] | None = None,
        batch_isolation: dict[str, object] | None = None,
        question_figure_repair_queue: dict[str, object] | None = None,
        diagnostics_items: list[dict] | None = None,
        batch_issue_items: list[dict] | None = None,
    ) -> ExecutionResultState:
        summary_map = {
            "success": "本次执行已完成",
            "partial_success": f"执行完成，但有 {failed_count} 个模块未成功",
            "failed": "执行失败",
            "cancelled": "已取消",
        }
        if status not in summary_map:
            raise ValueError(f"Unknown execution status: {status!r}")

        object_preflight_payload = _dict_payload(object_preflight)
        style_source_payload = _dict_payload(style_source)
        field_consistency = _dict_payload(material_field_consistency)
        batch_isolation_payload = _dict_payload(batch_isolation)
        question_figure_repair_queue_payload = _dict_payload(question_figure_repair_queue)
        style_source_envelope = _style_source_receipt_envelope(
            style_source_payload,
            fallback=style_source_summary,
        )
        style_difference_summary = _style_difference_summary_projection(
            style_source_payload
        )
        return ExecutionResultState(
            status=status,
            summary=summary_map[status],
            error_text=error_text,
            style_source=style_source_payload,
            style_source_summary=style_source_envelope.receipt_summary(
                title_fallback="样式来源"
            ),
            style_source_envelope=style_source_envelope,
            style_difference_summary=style_difference_summary,
            output_path=output_path,
            output_paths=_string_path_map(output_paths),
            compare_paths=_string_path_map(compare_paths),
            report_paths=list(report_paths),
            intermediate_paths=_string_path_map(intermediate_paths),
            material_manifest_paths=_string_path_map(material_manifest_paths),
            material_package_paths=_string_path_map(material_package_paths),
            scene_sample_manifest_paths=_string_path_map(scene_sample_manifest_paths),
            failed_count=failed_count,
            diagnostics_count=diagnostics_count,
            diagnostics_summary=diagnostics_summary,
            object_preflight=object_preflight_payload,
            object_preflight_summary=_object_preflight_summary(object_preflight_payload),
            object_preflight_details=_object_preflight_detail_lines(
                object_preflight_payload
            ),
            material_field_consistency=field_consistency,
            material_field_consistency_summary=_material_field_consistency_summary(
                field_consistency
            ),
            batch_isolation=batch_isolation_payload,
            batch_isolation_summary=_batch_isolation_summary(batch_isolation_payload),
            batch_isolation_details=_batch_isolation_detail_lines(batch_isolation_payload),
            question_figure_repair_queue=question_figure_repair_queue_payload,
            artifact_items=_build_artifact_items(
                output_path=output_path,
                output_paths=_string_path_map(output_paths),
                compare_paths=_string_path_map(compare_paths),
                report_paths=list(report_paths),
                intermediate_paths=_string_path_map(intermediate_paths),
                material_manifest_paths=_string_path_map(material_manifest_paths),
                material_package_paths=_string_path_map(material_package_paths),
                scene_sample_manifest_paths=_string_path_map(scene_sample_manifest_paths),
                output_target_preflight=output_target_preflight,
                question_figure_repair_queue=question_figure_repair_queue_payload,
            ),
            issue_items=[
                *output_target_preflight_issue_items(output_target_preflight),
                *execution_diagnostic_issue_items(diagnostics_items),
                *batch_execution_issue_items(batch_issue_items),
                *question_figure_repair_queue_issue_items(
                    question_figure_repair_queue_payload
                ),
                *question_figure_transaction_task_issue_items(
                    question_figure_repair_queue_payload
                ),
            ],
        )

    def build_recent_run_state(
        self,
        result_state: ExecutionResultState,
    ) -> RecentRunState:
        report_label = ", ".join(result_state.report_paths)
        return RecentRunState(
            status=result_state.status,
            title="最近结果",
            summary=result_state.summary,
            output_label=_artifact_label(
                result_state.output_paths,
                result_state.output_path,
                delivery_preset_labels=True,
            ),
            compare_label=_artifact_label(
                result_state.compare_paths,
                delivery_preset_labels=True,
            ),
            report_label=report_label,
            intermediate_label=_artifact_label(
                result_state.intermediate_paths,
                delivery_preset_labels=True,
            ),
            material_manifest_label=_artifact_label(result_state.material_manifest_paths),
            material_package_label=_artifact_label(result_state.material_package_paths),
            scene_sample_manifest_label=_artifact_label(
                result_state.scene_sample_manifest_paths
            ),
            artifact_label=_artifact_browser_label(result_state.artifact_items),
            artifact_items=list(result_state.artifact_items),
            error_summary=result_state.error_text,
            diagnostics_count=result_state.diagnostics_count,
            diagnostics_summary=result_state.diagnostics_summary,
            style_source=dict(result_state.style_source),
            style_source_summary=result_state.style_source_summary,
            style_source_envelope=result_state.style_source_envelope,
            style_difference_summary=result_state.style_difference_summary,
            object_preflight=dict(result_state.object_preflight),
            object_preflight_summary=result_state.object_preflight_summary,
            object_preflight_details=list(result_state.object_preflight_details),
            material_field_consistency=dict(result_state.material_field_consistency),
            material_field_consistency_summary=result_state.material_field_consistency_summary,
            batch_isolation=dict(result_state.batch_isolation),
            batch_isolation_summary=result_state.batch_isolation_summary,
            batch_isolation_details=list(result_state.batch_isolation_details),
            question_figure_repair_queue=dict(result_state.question_figure_repair_queue),
        )


def material_schema_readiness_reasons(scene) -> list[str]:
    """Return run-blocking material schema problems visible before execution."""

    missing_ids = _missing_scene_material_schema_ids(scene)
    if not missing_ids:
        return []
    return ["资料 Schema 未注册：" + ", ".join(missing_ids)]


def summarize_workbench_issue_queue(
    items: list[WorkbenchIssueItem] | tuple[WorkbenchIssueItem, ...],
    *,
    category: str = "",
    action_group: str = "",
) -> WorkbenchIssueQueueSummary:
    """Return counts and visible items for a filterable Workbench issue queue."""

    queue_items = [
        item for item in list(items or []) if isinstance(item, WorkbenchIssueItem)
    ]
    normalized_category = str(category or "").strip()
    normalized_action_group = str(action_group or "").strip()
    if normalized_action_group not in ISSUE_ACTION_GROUP_VALUES:
        normalized_action_group = ""
    visible_items = tuple(
        item
        for item in queue_items
        if not normalized_category or item.category == normalized_category
        if not normalized_action_group
        or workbench_issue_action_group(item) == normalized_action_group
    )
    return WorkbenchIssueQueueSummary(
        total_count=len(queue_items),
        visible_count=len(visible_items),
        blocking_count=sum(1 for item in queue_items if item.blocking),
        actionable_count=sum(1 for item in visible_items if _issue_repair_target_key(item)),
        active_category=normalized_category,
        active_action_group=normalized_action_group,
        category_counts=_count_issue_values(item.category for item in queue_items),
        severity_counts=_count_issue_values(item.severity for item in queue_items),
        status_counts=_count_issue_values(_issue_status(item) for item in queue_items),
        owner_counts=_count_issue_values(_issue_owner(item) for item in queue_items),
        action_group_counts=_count_issue_action_values(
            workbench_issue_action_group(item) for item in queue_items
        ),
        visible_action_group_counts=_count_issue_action_values(
            workbench_issue_action_group(item) for item in visible_items
        ),
        repair_target_counts=_count_issue_values(
            _issue_repair_target_key(item) for item in visible_items
        ),
        visible_items=visible_items,
    )


def workbench_issue_action_group(item: WorkbenchIssueItem) -> str:
    """Return the user-action bucket for a Workbench issue."""

    if not isinstance(item, WorkbenchIssueItem):
        return "view_only"
    if _issue_status(item) in ISSUE_TERMINAL_STATUS_VALUES:
        return "view_only"
    severity = str(getattr(item, "severity", "") or "").strip().lower()
    if bool(getattr(item, "blocking", False)) or severity in {
        "error",
        "fatal",
        "critical",
    }:
        return "handle_first"
    if _issue_repair_target_key(item):
        return "confirm"
    return "view_only"


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


def workbench_issue_action_visual_for_item(
    item: WorkbenchIssueItem,
) -> WorkbenchIssueActionVisualProjection:
    """Return visual action semantics for a concrete Workbench issue."""

    if not isinstance(item, WorkbenchIssueItem):
        return workbench_issue_action_visual("view_only")
    return workbench_issue_action_visual(
        workbench_issue_action_group(item),
        status=_issue_status(item),
    )


def workbench_issue_action_target(item: WorkbenchIssueItem) -> tuple[str, str]:
    """Return the routable UI action target for a Workbench issue."""

    if not isinstance(item, WorkbenchIssueItem):
        return ("", "")
    target_type = str(item.repair_target_type or "").strip()
    target_key = str(item.repair_target_key or "").strip()
    if not target_type:
        return ("", "")
    profile_id = _issue_repair_context_value(item, "profile_id")
    profile_name = _issue_repair_context_value(item, "profile_name")
    candidate_json = _issue_repair_context_value(item, "repair_candidate_json")
    if (
        (profile_id or profile_name)
        and item.category == "question_figure_repair_queue"
        and target_type == "question_figure_item"
        and candidate_json
    ):
        candidate = _json_object(candidate_json)
        if (
            bool(candidate.get("confirmation_apply_supported"))
            and _clean_text(candidate.get("confirmation_status")) == "ready"
        ):
            return (
                "profile_question_figure_repair_candidate",
                json.dumps(
                    {
                        "profile_id": profile_id,
                        "profile_name": profile_name,
                        "target_key": target_key,
                        "candidate": candidate,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        conflict_candidate = _question_figure_conflict_selection_candidate(candidate)
        if conflict_candidate:
            return (
                "profile_question_figure_repair_conflict_selection",
                json.dumps(
                    {
                        "profile_id": profile_id,
                        "profile_name": profile_name,
                        "target_key": target_key,
                        "candidate": conflict_candidate,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
    if (profile_id or profile_name) and target_type in {
        "field",
        "asset",
        "schema",
        "question_figure_item",
    }:
        return (
            f"profile_{target_type}",
            json.dumps(
                {
                    "profile_id": profile_id,
                    "profile_name": profile_name,
                    "target_key": target_key,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    if target_type == "question_figure_batch_apply_transaction_task_summary":
        payload = _json_object(target_key)
        if not payload:
            payload = {"target_key": target_key} if target_key else {}
        return (
            target_type,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
    return (target_type, target_key)


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


def _batch_issue_parameter_paths(payload: dict[str, object]) -> tuple[str, ...]:
    paths: list[str] = []
    for key in (
        "repair_target_key",
        "field_id",
        "parameter_path",
        "parameter_field",
    ):
        value = _clean_text(payload.get(key))
        if value:
            paths.append(value)
    for key in ("parameter_paths", "declared_paths", "runtime_paths"):
        paths.extend(_clean_list(payload.get(key)))

    unique: list[str] = []
    for path in paths:
        if path and path not in unique:
            unique.append(path)
    return tuple(unique)


def _infer_scene_field_repair_target(
    parameter_paths: tuple[str, ...],
    *,
    fallback_key: str = "",
) -> tuple[str, str]:
    candidates = [path for path in parameter_paths if path]
    if fallback_key and fallback_key not in candidates:
        candidates.insert(0, fallback_key)

    for path in candidates:
        target = _normalize_scene_scope_field_path(path)
        if target:
            return ("scene_scope_field", target)

    for path in candidates:
        target = _normalize_scene_style_field_path(path)
        if target:
            return ("scene_style_field", target)

    return ("", "")


def _normalize_scene_scope_field_path(path: str) -> str:
    target = _clean_text(path)
    for prefix in ("scene.format_scope.sections.", "format_scope.sections."):
        if target.startswith(prefix):
            zone = target[len(prefix):].split(".", 1)[0]
            return f"format_scope.sections.{zone}" if zone else ""
    if target.startswith("sections."):
        zone = target[len("sections."):].split(".", 1)[0]
        return f"format_scope.sections.{zone}" if zone else ""
    return ""


def _normalize_scene_style_field_path(path: str) -> str:
    target = _clean_text(path)
    variant_key, editor_field = scene_style_navigation_target_from_field_id(target)
    if variant_key:
        if not editor_field:
            return f"scene.section_styles.{variant_key}"
        canonical = canonical_paragraph_style_field_id(editor_field)
        return f"scene.section_styles.{variant_key}.{canonical or editor_field}"
    for prefix in ("scene.section_styles.", "section_styles."):
        if target.startswith(prefix):
            tail = target[len(prefix):]
            return f"scene.section_styles.{tail}" if tail else ""
    return ""


def _question_figure_conflict_selection_candidate(
    candidate: dict[str, object],
) -> dict[str, object]:
    if not isinstance(candidate, dict):
        return {}
    if _clean_text(candidate.get("confirmation_status")) != "conflict":
        return {}
    if _clean_text(candidate.get("confirmation_action")) != (
        "resolve_question_figure_replacement_conflict"
    ):
        return {}
    if not bool(candidate.get("conflict_resolution_select_supported")):
        return {}
    queue_id = _clean_text(candidate.get("queue_id"))
    conflict_group_id = _clean_text(candidate.get("conflict_group_id"))
    replacement_path = _clean_text(candidate.get("replacement_source_path"))
    if not queue_id or not conflict_group_id or not replacement_path:
        return {}
    conflict_queue_ids = [
        queue_id_value
        for queue_id_value in _clean_list(candidate.get("conflict_candidate_queue_ids"))
        if queue_id_value
    ]
    if queue_id not in conflict_queue_ids:
        conflict_queue_ids.insert(0, queue_id)
    rejected_queue_ids = [
        queue_id_value
        for queue_id_value in conflict_queue_ids
        if queue_id_value != queue_id
    ]
    blockers = [
        blocker
        for blocker in _clean_list(candidate.get("apply_blockers"))
        if blocker != "candidate_conflict_same_repair_target"
    ]
    resolved = dict(candidate)
    resolved["confirmation_action"] = "confirm_question_figure_replacement"
    resolved["confirmation_apply_supported"] = True
    resolved["confirmation_status"] = "ready"
    resolved["conflict_resolution_status"] = "selected"
    resolved["conflict_resolution_action"] = (
        "select_question_figure_replacement_conflict_candidate"
    )
    resolved["conflict_selected_queue_id"] = queue_id
    resolved["conflict_resolution_group_id"] = conflict_group_id
    resolved["conflict_resolution_candidate_queue_ids"] = conflict_queue_ids
    resolved["conflict_resolution_rejected_queue_ids"] = rejected_queue_ids
    resolved["conflict_resolution_by"] = "workbench_issue_action"
    resolved["conflict_resolution_note"] = "selected from Workbench issue queue"
    resolved["apply_blockers"] = blockers
    return resolved


def update_workbench_issue_status(
    items: list[WorkbenchIssueItem] | tuple[WorkbenchIssueItem, ...],
    issue_id: str,
    status: str,
) -> list[WorkbenchIssueItem]:
    """Return a copy of issue items with one issue status updated."""

    normalized_id = str(issue_id or "").strip()
    normalized_status = str(status or "").strip()
    queue_items = [
        item for item in list(items or []) if isinstance(item, WorkbenchIssueItem)
    ]
    if not normalized_id or normalized_status not in ISSUE_STATUS_VALUES:
        return queue_items
    return [
        replace(item, status=normalized_status)
        if item.issue_id == normalized_id
        else item
        for item in queue_items
    ]


def material_readiness_reasons(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> list[str]:
    """Return material schema, field, and asset problems visible before execution."""

    return material_readiness_issue_groups(scene, material_context).to_reasons()


def material_readiness_issue_items(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> list[WorkbenchIssueItem]:
    """Return structured Workbench issue items for material readiness."""

    groups = material_readiness_issue_groups(scene, material_context)
    items: list[WorkbenchIssueItem] = []
    if groups.field_keys:
        items.append(
            WorkbenchIssueItem(
                issue_id="material.fields.missing",
                category="material_field",
                severity="warning",
                title="资料字段缺失",
                summary=", ".join(groups.field_keys),
                details=tuple("字段：" + key for key in groups.field_keys),
                source_notes=groups.source_notes,
                repair_target_type="field",
                repair_target_key=groups.field_keys[0],
                blocking=True,
            )
        )
    if groups.asset_roles:
        items.append(
            WorkbenchIssueItem(
                issue_id="material.assets.missing",
                category="material_asset",
                severity="warning",
                title="资料资产缺失",
                summary=", ".join(groups.asset_roles),
                details=tuple("资产：" + role for role in groups.asset_roles),
                source_notes=groups.source_notes,
                repair_target_type="asset",
                repair_target_key=groups.asset_roles[0],
                blocking=True,
            )
        )
    if groups.schema_ids:
        details: list[str] = []
        if groups.recommendation_schema_id:
            recommendation = "推荐替换：" + groups.recommendation_schema_id
            if groups.recommendation_reasons:
                recommendation += "（" + "; ".join(groups.recommendation_reasons) + "）"
            details.append(recommendation)
        items.append(
            WorkbenchIssueItem(
                issue_id="material.schema.unregistered",
                category="material_schema",
                severity="error",
                title="资料 Schema 未注册",
                summary=", ".join(groups.schema_ids),
                details=tuple(details),
                source_notes=groups.source_notes,
                repair_target_type="schema",
                repair_target_key=groups.schema_ids[0],
                blocking=True,
            )
        )
    return items


def material_asset_comparison_issue_items(
    material_context: MaterialExecutionContext | None = None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issues for manually flagged question-figure comparisons."""

    context = (
        material_context
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    items: list[WorkbenchIssueItem] = []
    for index, asset_item in enumerate(list(context.asset_items or []), start=1):
        if not isinstance(asset_item, AssetItem):
            continue
        metadata = _asset_metadata(asset_item)
        if _clean_text(metadata.get("comparison_issue_status")).lower() != "flagged":
            continue
        question_target = _question_figure_target_value(metadata) or str(index)
        display_name = (
            _clean_text(metadata.get("comparison_issue_display_name"))
            or _clean_text(metadata.get("comparison_issue_reference"))
            or _clean_text(asset_item.label)
            or Path(str(asset_item.path or "")).name
            or _clean_text(asset_item.item_id)
        )
        issue_kind = _clean_text(metadata.get("comparison_issue_kind")) or "题图对比"
        summary = (
            _clean_text(metadata.get("comparison_issue_summary"))
            or f"题{question_target} {issue_kind}: {display_name}"
        )
        details = [
            f"题号：{question_target}",
            f"标注类型：{_clean_text(metadata.get('comparison_issue_type')) or 'manual_compare'}",
            f"对比类型：{issue_kind}",
            f"对比对象：{display_name}",
        ]
        reference = _clean_text(metadata.get("comparison_issue_reference"))
        if reference and reference != display_name:
            details.append("对比引用：" + reference)
        marked_at = _clean_text(metadata.get("comparison_issue_marked_at"))
        if marked_at:
            details.append("标注时间：" + marked_at)
        region_summary = _clean_text(metadata.get("comparison_issue_region_summary"))
        if region_summary:
            details.append("差异区域：" + region_summary)
        target_key = _question_figure_item_repair_target_key(asset_item, question_target)
        issue_id = (
            "material.asset_comparison."
            f"{_issue_token(asset_item.item_id or question_target)}."
            f"{_issue_token(display_name)}"
        )
        items.append(
            WorkbenchIssueItem(
                issue_id=issue_id,
                category="material_asset_comparison",
                severity="warning",
                title="题图对比问题",
                summary=summary,
                details=tuple(details),
                source_notes=("asset_items.metadata.comparison_issue_*",),
                repair_target_type="question_figure_item",
                repair_target_key=target_key,
                repair_context=tuple(
                    pair
                    for pair in (
                        ("profile_id", _clean_text(context.profile_id)),
                        ("profile_name", _clean_text(context.profile_name)),
                    )
                    if pair[1]
                ),
                blocking=False,
                owner="workbench",
            )
        )
    return items


def object_preflight_issue_items(
    object_preflight: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return structured Workbench issue items for object preflight payloads."""

    payload = _dict_payload(object_preflight)
    if not payload or payload.get("enabled") is False:
        return []

    findings_count = _safe_int(payload.get("findings_count"))
    module_skips_count = _safe_int(payload.get("module_skips_count"))
    if findings_count <= 0 and module_skips_count <= 0:
        return []

    blocking_count = _safe_int(payload.get("blocking_findings_count"))
    source_notes = _object_preflight_source_notes(payload)
    findings = [
        finding
        for finding in list(payload.get("findings") or [])
        if isinstance(finding, dict)
    ]
    module_skips = [
        module_skip
        for module_skip in list(payload.get("module_skips") or [])
        if isinstance(module_skip, dict)
    ]
    items: list[WorkbenchIssueItem] = []
    matched_skip_indexes: set[int] = set()

    for index, finding in enumerate(findings, start=1):
        kind = _clean_text(finding.get("kind")) or "risk"
        severity = _clean_text(finding.get("severity")) or "warning"
        location = _clean_text(finding.get("location"))
        message = _clean_text(finding.get("message"))
        finding_line = _object_preflight_finding_line(finding)
        related_skip_lines, related_indexes = _object_preflight_related_skip_lines(
            finding,
            module_skips,
        )
        matched_skip_indexes.update(related_indexes)
        summary = message or location or kind
        if location and message:
            summary = f"{location}: {message}"
        items.append(
            WorkbenchIssueItem(
                issue_id=f"object_preflight.finding.{index}.{_issue_token(kind)}",
                category="object_preflight",
                severity=severity,
                title=f"对象风险：{kind}",
                summary=summary,
                details=tuple(
                    line for line in [finding_line, *related_skip_lines] if line
                ),
                source_notes=source_notes,
                repair_target_type="object_preflight",
                repair_target_key=_object_preflight_finding_target_key(finding, index),
                blocking=severity == "error",
            )
        )

    for index, module_skip in enumerate(module_skips, start=1):
        if (index - 1) in matched_skip_indexes:
            continue
        skip_line = _object_preflight_skip_line(module_skip)
        if not skip_line:
            continue
        module_name = _clean_text(module_skip.get("module_name"))
        items.append(
            WorkbenchIssueItem(
                issue_id=f"object_preflight.skip.{index}.{_issue_token(module_name or 'module')}",
                category="object_preflight",
                severity="warning",
                title="对象预检跳过模块",
                summary=skip_line.replace("跳过模块 ", "", 1),
                details=(skip_line,),
                source_notes=source_notes,
                repair_target_type="object_preflight",
                repair_target_key=_object_preflight_skip_target_key(module_skip, index),
                blocking=blocking_count > 0 and not items,
            )
        )

    if items:
        return items

    summary = _object_preflight_summary(payload)
    return [
        WorkbenchIssueItem(
            issue_id="object_preflight.risk",
            category="object_preflight",
            severity="error" if blocking_count > 0 else "warning",
            title="对象预检风险",
            summary=summary.replace("对象预检：", "", 1) if summary else "",
            details=tuple(_object_preflight_detail_lines(payload)),
            source_notes=source_notes,
            repair_target_type="object_preflight",
            repair_target_key="summary",
            blocking=blocking_count > 0,
        )
    ]


def output_target_preflight_issue_items(
    output_target_preflight: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return structured Workbench issue items for planned output risks."""

    items: list[WorkbenchIssueItem] = []
    for (
        label,
        display_label,
        detail,
        path,
    ) in _planned_output_preflight_items(output_target_preflight):
        if not detail:
            continue
        item_label = str(label or "output").strip() or "output"
        source_notes = []
        if display_label != item_label:
            source_notes.append("交付版本 ID：" + item_label)
        if str(path or "").strip():
            source_notes.append("输出路径：" + str(path))
        items.append(
            WorkbenchIssueItem(
                issue_id=f"output_target.{item_label}.warning",
                category="output_target",
                severity="warning",
                title="输出目标预检",
                summary=f"{display_label}：{detail}",
                details=tuple(_split_issue_detail_text(detail)),
                source_notes=tuple(source_notes),
                repair_target_type="output_target",
                repair_target_key=item_label,
                blocking=False,
            )
        )
    return items


def execution_diagnostic_issue_items(
    diagnostics_items: list[dict] | tuple[dict, ...] | None,
) -> list[WorkbenchIssueItem]:
    """Return actionable Workbench issues for routable execution diagnostics."""

    items: list[WorkbenchIssueItem] = []
    for index, payload in enumerate(list(diagnostics_items or []), start=1):
        if not isinstance(payload, dict):
            continue

        parameter_paths = _batch_issue_parameter_paths(payload)
        explicit_target_type = _clean_text(payload.get("repair_target_type"))
        explicit_target_key = _clean_text(payload.get("repair_target_key"))
        repair_target_type, repair_target_key = _infer_scene_field_repair_target(
            parameter_paths,
            fallback_key=explicit_target_key,
        )
        if not repair_target_type and explicit_target_type:
            repair_target_type = explicit_target_type
            repair_target_key = explicit_target_key

        if repair_target_type not in {"scene_scope_field", "scene_style_field"}:
            continue

        rule_name = _clean_text(payload.get("rule_name")) or "diagnostic"
        change_type = _clean_text(payload.get("change_type")) or "diagnostic"
        target = _clean_text(payload.get("target"))
        section = _clean_text(payload.get("section"))
        reason = _clean_text(payload.get("reason")) or change_type
        severity = _clean_text(payload.get("severity") or payload.get("level"))
        if not severity:
            severity = "error" if payload.get("success") is False else "warning"
        category = (
            "scene_scope" if repair_target_type == "scene_scope_field" else "scene_style"
        )
        title = (
            "场景处理范围需要确认"
            if repair_target_type == "scene_scope_field"
            else "场景样式需要确认"
        )
        details = [
            f"规则：{rule_name}" if rule_name else "",
            f"类型：{change_type}" if change_type else "",
            f"对象：{target}" if target else "",
            f"结构：{section}" if section else "",
            "参数路径：" + ", ".join(parameter_paths[:3]) if parameter_paths else "",
        ]
        items.append(
            WorkbenchIssueItem(
                issue_id=(
                    _clean_text(payload.get("issue_id"))
                    or "diagnostic."
                    f"{_issue_token(repair_target_type)}."
                    f"{_issue_token(repair_target_key)}.{index}"
                ),
                category=category,
                severity=severity,
                title=title,
                summary=reason,
                details=tuple(line for line in details if line),
                source_notes=("diagnostics_items",),
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
                blocking=severity == "error",
                status="open",
                owner="scene",
            )
        )
    return items


def batch_execution_issue_items(
    batch_issue_items: list[dict] | tuple[dict, ...] | None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issue items for per-record batch execution payloads."""

    items: list[WorkbenchIssueItem] = []
    for index, payload in enumerate(list(batch_issue_items or []), start=1):
        if not isinstance(payload, dict):
            continue
        profile_id = _clean_text(payload.get("profile_id"))
        profile_name = _clean_text(payload.get("profile_name"))
        kind = _clean_text(payload.get("kind")) or "batch_issue"
        summary = _clean_text(payload.get("summary")) or kind
        severity = _clean_text(payload.get("severity")) or "warning"
        status = _clean_text(payload.get("status")) or "open"
        repair_target_type = _clean_text(payload.get("repair_target_type"))
        repair_target_key = _clean_text(payload.get("repair_target_key"))
        parameter_paths = _batch_issue_parameter_paths(payload)
        if not repair_target_type:
            inferred_type, inferred_key = _infer_scene_field_repair_target(
                parameter_paths,
                fallback_key=repair_target_key,
            )
            repair_target_type = inferred_type
            repair_target_key = repair_target_key or inferred_key
        missing_fields = _clean_list(payload.get("missing_field_keys"))
        missing_assets = _clean_list(payload.get("missing_asset_roles"))
        suspicious_assets = [
            dict(item)
            for item in _list_values(payload.get("suspicious_asset_items"))
            if isinstance(item, dict)
        ]
        comparison_assets = [
            dict(item)
            for item in _list_values(payload.get("comparison_issue_items"))
            if isinstance(item, dict)
        ]
        details = _batch_issue_detail_lines(
            profile_id=profile_id,
            profile_name=profile_name,
            status=status,
            parameter_paths=parameter_paths,
            missing_fields=missing_fields,
            missing_assets=missing_assets,
            suspicious_assets=suspicious_assets,
            comparison_assets=comparison_assets,
        )
        source_notes = tuple(
            note
            for note in (
                "batch_issue_items",
                f"profile_id:{profile_id}" if profile_id else "",
                f"profile_name:{profile_name}" if profile_name else "",
            )
            if note
        )
        issue_id = (
            _clean_text(payload.get("issue_id"))
            or f"batch.{_issue_token(profile_id or profile_name or str(index))}.{_issue_token(kind)}.{index}"
        )
        items.append(
            WorkbenchIssueItem(
                issue_id=issue_id,
                category="batch_issue",
                severity=severity,
                title="批量记录问题",
                summary=summary,
                details=tuple(details),
                source_notes=source_notes,
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
                repair_context=tuple(
                    pair
                    for pair in (
                        ("profile_id", profile_id),
                        ("profile_name", profile_name),
                    )
                    if pair[1]
                ),
                blocking=severity == "error",
                status="open",
                owner="workbench",
            )
        )
    return items


def question_figure_repair_queue_issue_items(
    question_figure_repair_queue: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return actionable Workbench issues for question-figure repair candidates."""

    queue_payload = _dict_payload(question_figure_repair_queue)
    entries = [
        dict(entry)
        for entry in _list_values(queue_payload.get("entries"))
        if isinstance(entry, dict)
    ]
    items: list[WorkbenchIssueItem] = []
    for index, entry in enumerate(entries, start=1):
        repair_target_type = _clean_text(entry.get("repair_target_type"))
        repair_target_key = _clean_text(entry.get("repair_target_key"))
        if not repair_target_type or not repair_target_key:
            continue
        profile_id = _clean_text(entry.get("profile_id"))
        profile_name = _clean_text(entry.get("profile_name"))
        question_index = _clean_text(entry.get("question_index"))
        reference = (
            _clean_text(entry.get("comparison_display_name"))
            or _clean_text(entry.get("comparison_reference"))
        )
        issue_summary = (
            _clean_text(entry.get("issue_summary"))
            or _clean_text(entry.get("issue_kind"))
            or "题图对比修复候选"
        )
        queue_id = _clean_text(entry.get("queue_id"))
        status = _clean_text(entry.get("status")) or "candidate"
        region_summary = _clean_text(entry.get("region_summary"))
        confirmation_status = _clean_text(entry.get("confirmation_status"))
        replacement_source_path = _clean_text(entry.get("replacement_source_path"))
        apply_blockers = _clean_list(entry.get("apply_blockers"))
        conflict_group_id = _clean_text(entry.get("conflict_group_id"))
        conflict_resolution_action = _clean_text(
            entry.get("conflict_resolution_action")
        )
        conflict_resolution_status = _clean_text(
            entry.get("conflict_resolution_status")
        )
        conflict_resolution_note = _clean_text(entry.get("conflict_resolution_note"))
        conflict_candidate_queue_ids = _clean_list(
            entry.get("conflict_candidate_queue_ids")
        )
        details = [
            f"题号：{question_index}" if question_index else "",
            f"候选状态：{status}",
            f"对比对象：{reference}" if reference else "",
            f"差异区域：{region_summary}" if region_summary else "",
            (
                "确认替换：可用"
                if bool(entry.get("confirmation_apply_supported"))
                else "确认替换：不可用"
            ),
            f"替换来源：{replacement_source_path}" if replacement_source_path else "",
            "阻断原因：" + ", ".join(apply_blockers) if apply_blockers else "",
            f"确认状态：{confirmation_status}" if confirmation_status else "",
            f"冲突组：{conflict_group_id}" if conflict_group_id else "",
            (
                f"冲突动作：{conflict_resolution_action}"
                if conflict_resolution_action
                else ""
            ),
            (
                "冲突裁决：可选择此候选"
                if bool(entry.get("conflict_resolution_select_supported"))
                else ""
            ),
            (
                f"冲突裁决：{conflict_resolution_status}"
                if conflict_resolution_status
                else ""
            ),
            (
                f"裁决说明：{conflict_resolution_note}"
                if conflict_resolution_note
                else ""
            ),
            (
                "同组候选：" + ", ".join(conflict_candidate_queue_ids)
                if conflict_candidate_queue_ids
                else ""
            ),
            "需要人工确认"
            if bool(entry.get("requires_user_confirmation", True))
            else "",
            "自动应用关闭"
            if not bool(entry.get("auto_apply_supported", False))
            else "",
            f"来源 issue：{_clean_text(entry.get('source_issue_id'))}"
            if _clean_text(entry.get("source_issue_id"))
            else "",
        ]
        issue_id = (
            queue_id
            or "question_figure_repair_queue."
            f"{_issue_token(profile_id or profile_name or str(index))}."
            f"{_issue_token(question_index or str(index))}.{index}"
        )
        items.append(
            WorkbenchIssueItem(
                issue_id=issue_id,
                category="question_figure_repair_queue",
                severity="warning",
                title="题图修复候选",
                summary=issue_summary,
                details=tuple(detail for detail in details if detail),
                source_notes=("question_figure_repair_queue",),
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
                repair_context=tuple(
                    pair
                    for pair in (
                        ("profile_id", profile_id),
                        ("profile_name", profile_name),
                        (
                            "repair_candidate_json",
                            json.dumps(
                                entry,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                    if pair[1]
                ),
                blocking=False,
                status="open",
                owner="workbench",
            )
        )
    return items


def question_figure_transaction_task_issue_items(
    question_figure_repair_queue: dict[str, object] | None,
) -> list[WorkbenchIssueItem]:
    """Return actionable issues for active question-figure transaction tasks."""

    queue_payload = _dict_payload(question_figure_repair_queue)
    manifest_payload = _dict_payload(
        queue_payload.get("batch_apply_transaction_manifest")
    )
    task_payload = _dict_payload(manifest_payload.get("task_summary"))
    status = _clean_text(task_payload.get("status"))
    if status not in {"active", "blocked", "orphaned"}:
        return []

    next_action = _clean_text(task_payload.get("next_action"))
    artifact_path = _clean_text(manifest_payload.get("artifact_path"))
    report_path = (
        _clean_text(task_payload.get("report_path"))
        or _clean_text(manifest_payload.get("report_path"))
        or artifact_path
    )
    blockers = _clean_list(task_payload.get("blockers")) or _clean_list(
        manifest_payload.get("blockers")
    )
    active_ids = _clean_list(task_payload.get("active_transaction_ids"))
    rolled_back_ids = _clean_list(task_payload.get("rolled_back_transaction_ids"))
    rollback_available_ids = _clean_list(
        task_payload.get("rollback_available_transaction_ids")
    )
    latest_transaction_id = _clean_text(task_payload.get("latest_transaction_id"))
    latest_transaction_status = _clean_text(
        task_payload.get("latest_transaction_status")
    )
    latest_apply_audit_id = _clean_text(task_payload.get("latest_apply_audit_id"))
    latest_rollback_audit_id = _clean_text(
        task_payload.get("latest_rollback_audit_id")
    )
    transaction_count = _safe_int(task_payload.get("transaction_count"))
    active_count = _safe_int(task_payload.get("active_count"))
    rolled_back_count = _safe_int(task_payload.get("rolled_back_count"))
    rollback_available_count = _safe_int(
        task_payload.get("rollback_available_count")
    )
    orphan_rollback_count = _safe_int(task_payload.get("orphan_rollback_count"))
    action_payload = {
        "status": status,
        "next_action": next_action,
        "report_path": report_path,
        "artifact_path": artifact_path,
        "fragment": "question-figure-batch-apply-transaction-task-summary",
        "transaction_count": transaction_count,
        "active_count": active_count,
        "rolled_back_count": rolled_back_count,
        "rollback_available_count": rollback_available_count,
        "orphan_rollback_count": orphan_rollback_count,
        "latest_transaction_id": latest_transaction_id,
        "latest_transaction_status": latest_transaction_status,
        "latest_apply_audit_id": latest_apply_audit_id,
        "latest_rollback_audit_id": latest_rollback_audit_id,
    }
    details = [
        f"事务状态：{status}",
        f"下一步：{next_action}" if next_action else "",
        f"事务总数：{transaction_count}",
        f"活动事务：{active_count}",
        f"可回滚事务：{rollback_available_count}",
        f"已回滚事务：{rolled_back_count}",
        f"孤立回滚：{orphan_rollback_count}",
        (
            f"最近事务：{latest_transaction_id}"
            + (f" ({latest_transaction_status})" if latest_transaction_status else "")
            if latest_transaction_id
            else ""
        ),
        f"最近 apply audit：{latest_apply_audit_id}" if latest_apply_audit_id else "",
        (
            f"最近 rollback audit：{latest_rollback_audit_id}"
            if latest_rollback_audit_id
            else ""
        ),
        "活动事务 ID：" + ", ".join(active_ids) if active_ids else "",
        (
            "可回滚事务 ID：" + ", ".join(rollback_available_ids)
            if rollback_available_ids
            else ""
        ),
        "已回滚事务 ID：" + ", ".join(rolled_back_ids) if rolled_back_ids else "",
        "阻断原因：" + ", ".join(blockers) if blockers else "",
        f"报告：{report_path}" if report_path else "",
        f"台账：{artifact_path}" if artifact_path else "",
    ]
    issue_suffix = (
        latest_transaction_id
        or latest_apply_audit_id
        or latest_rollback_audit_id
        or next_action
        or status
    )
    severity = "error" if status == "blocked" else "warning"
    return [
        WorkbenchIssueItem(
            issue_id=(
                "question_figure_batch_apply_transaction_task."
                f"{_issue_token(status)}.{_issue_token(issue_suffix)}"
            ),
            category="question_figure_batch_apply_transaction_task",
            severity=severity,
            title="题图批量应用事务任务",
            summary=(
                f"{status}; next={next_action or '-'}; "
                f"rollback_available={rollback_available_count}"
            ),
            details=tuple(detail for detail in details if detail),
            source_notes=(
                "batch_apply_transaction_manifest",
                "transaction_task_summary",
            ),
            repair_target_type="question_figure_batch_apply_transaction_task_summary",
            repair_target_key=json.dumps(
                action_payload, ensure_ascii=False, separators=(",", ":")
            ),
            repair_context=tuple(
                pair
                for pair in (
                    ("task_status", status),
                    ("next_action", next_action),
                    ("report_path", report_path),
                    ("artifact_path", artifact_path),
                    (
                        "fragment",
                        "question-figure-batch-apply-transaction-task-summary",
                    ),
                )
                if pair[1]
            ),
            blocking=status == "blocked",
            status="open",
            owner="pipeline",
        )
    ]


def coverage_boundary_issue_items(scene) -> list[WorkbenchIssueItem]:
    """Return non-blocking Workbench issues for manifest boundary warnings."""

    items: list[WorkbenchIssueItem] = []
    for pack in _coverage_packs_for_scene_context(scene):
        is_contract_legal_boundary = pack.pack_id == "contract_delivery"
        if not pack.plugin_boundary and not is_contract_legal_boundary:
            continue
        gate = plugin_manual_gate_for_pack(pack.pack_id)
        category = "plugin_boundary" if pack.plugin_boundary else "coverage_boundary"
        title = "插件/专业边界" if pack.plugin_boundary else "法律/交付边界"
        target_type = "plugin_manual_gate" if gate is not None else "coverage_boundary"
        items.append(
            WorkbenchIssueItem(
                issue_id=f"coverage.{pack.pack_id}.{category}",
                category=category,
                severity="warning",
                title=title,
                summary=f"{pack.label}: {pack.boundary}",
                details=_coverage_boundary_details(pack),
                source_notes=(f"coverage pack：{pack.pack_id}",),
                repair_target_type=target_type,
                repair_target_key=gate.gate_id if gate is not None else pack.pack_id,
                blocking=False,
                owner="plugin" if pack.plugin_boundary else "scene",
            )
        )
    return items


def sample_fixture_issue_items(
    scene,
    audit: (
        tuple[SceneSampleFixtureAuditIssue, ...]
        | list[SceneSampleFixtureAuditIssue]
        | None
    ) = None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issues for scene sample coverage audit gaps."""

    packs = _coverage_packs_for_scene_context(scene)
    if not packs:
        return []
    pack_ids = tuple(pack.pack_id for pack in packs)
    audit_issues = tuple(audit) if audit is not None else audit_scene_sample_fixtures()
    items: list[WorkbenchIssueItem] = []

    for pack_id in pack_ids:
        if scene_sample_fixtures_for_pack(pack_id):
            continue
        items.append(
            _sample_fixture_issue(
                pack_id=pack_id,
                issue=SceneSampleFixtureAuditIssue(
                    fixture_id=pack_id,
                    kind="missing_required_pack_fixture",
                    message=f"Required pack '{pack_id}' has no DOCX sample fixture.",
                ),
            )
        )

    for issue in audit_issues:
        target_pack_id = _sample_fixture_issue_pack_id(issue, pack_ids)
        if not target_pack_id:
            continue
        issue_key = f"{target_pack_id}.{issue.kind}.{issue.fixture_id}"
        duplicate_issue_id = f"sample_fixture.{_issue_token(issue_key)}"
        if any(item.issue_id == duplicate_issue_id for item in items):
            continue
        items.append(_sample_fixture_issue(pack_id=target_pack_id, issue=issue))
    return items


def parameter_ownership_issue_items(scene) -> list[WorkbenchIssueItem]:
    """Return Workbench issues for scene parameter ownership audit gaps."""

    audit = audit_scene_parameter_ownership(scene.__class__)
    if audit.is_clean:
        return []
    details = _parameter_ownership_detail_lines(audit)
    return [
        WorkbenchIssueItem(
            issue_id="scene.parameter_ownership.audit",
            category="parameter_ownership",
            severity="warning",
            title="参数归属缺口",
            summary=f"{len(details)} 类缺口",
            details=tuple(details),
            source_notes=("scene_parameter_ownership registry",),
            repair_target_type="parameter_ownership",
            repair_target_key="registry",
            blocking=False,
            owner="scene",
        )
    ]


def control_contract_issue_items(
    audit: ControlContractAuditResult | None = None,
) -> list[WorkbenchIssueItem]:
    """Return Workbench issues for UI control contract audit gaps."""

    audit_result = audit if audit is not None else audit_control_contract_registry()
    if audit_result.is_clean:
        return []
    items: list[WorkbenchIssueItem] = []
    for contract_id in audit_result.missing_required_contracts:
        items.append(
            _control_contract_issue(
                issue_id=f"ui.control_contract.required.{_issue_token(contract_id)}",
                title="控件契约缺失",
                summary=contract_id,
                detail=f"缺少必审控件契约：{contract_id}",
                repair_target_key=contract_id,
            )
        )
    for contract_id, owner_layer in audit_result.invalid_owner_layers:
        items.append(
            _control_contract_issue(
                issue_id=f"ui.control_contract.owner.{_issue_token(contract_id)}",
                title="控件归属层非法",
                summary=f"{contract_id}: {owner_layer}",
                detail=f"非法控件归属层：{contract_id}:{owner_layer}",
                repair_target_key=contract_id,
            )
        )
    for contract_id, paired_id in audit_result.missing_paired_contracts:
        items.append(
            _control_contract_issue(
                issue_id=(
                    "ui.control_contract.pair."
                    f"{_issue_token(contract_id)}.{_issue_token(paired_id)}"
                ),
                title="配对控件缺失",
                summary=f"{contract_id} -> {paired_id}",
                detail=f"配对控件缺失：{contract_id}->{paired_id}",
                repair_target_key=contract_id,
            )
        )
    for contract_id, source_path in audit_result.missing_evidence_files:
        items.append(
            _control_contract_issue(
                issue_id=(
                    "ui.control_contract.evidence_file."
                    f"{_issue_token(contract_id)}.{_issue_token(source_path)}"
                ),
                title="控件证据文件缺失",
                summary=f"{contract_id}: {source_path}",
                detail=f"证据文件缺失：{contract_id}:{source_path}",
                repair_target_key=contract_id,
            )
        )
    for contract_id, source_path, marker in audit_result.missing_evidence_markers:
        items.append(
            _control_contract_issue(
                issue_id=(
                    "ui.control_contract.evidence_marker."
                    f"{_issue_token(contract_id)}.{_issue_token(marker)}"
                ),
                title="控件证据 marker 缺失",
                summary=f"{contract_id}: {marker}",
                detail=f"证据 marker 缺失：{contract_id}:{source_path}#{marker}",
                repair_target_key=contract_id,
            )
        )
    if items:
        return items
    details = _control_contract_detail_lines(audit_result)
    return [
        _control_contract_issue(
            issue_id="ui.control_contract.audit",
            title="控件契约缺口",
            summary="存在控件契约缺口",
            detail="；".join(details),
            repair_target_key="registry",
        )
    ]


def material_readiness_issue_groups(
    scene,
    material_context: MaterialExecutionContext | None = None,
) -> MaterialReadinessIssueGroups:
    """Return structured material schema, field, asset, and source issue groups."""

    missing_schema_ids = _missing_scene_material_schema_ids(scene)
    schema_recommendation = _material_schema_recommendation(scene, missing_schema_ids)
    profile = getattr(scene, "input_source_profile", None)
    if profile is None:
        return MaterialReadinessIssueGroups(
            schema_ids=missing_schema_ids,
            source_notes=_material_source_notes(
                missing_schema_ids=missing_schema_ids,
                recommendation_schema_id=(
                    schema_recommendation.schema_id if schema_recommendation is not None else ""
                ),
            ),
            recommendation_schema_id=(
                schema_recommendation.schema_id if schema_recommendation is not None else ""
            ),
            recommendation_reasons=(
                schema_recommendation.reasons if schema_recommendation is not None else ()
            ),
        )
    schema_ids = _scene_material_schema_ids(scene)
    extra_fields = list(getattr(profile, "required_material_fields", []) or [])
    extra_roles = list(getattr(profile, "required_image_roles", []) or [])
    if not schema_ids and not extra_fields and not extra_roles:
        return MaterialReadinessIssueGroups(
            schema_ids=missing_schema_ids,
            source_notes=_material_source_notes(
                missing_schema_ids=missing_schema_ids,
                recommendation_schema_id=(
                    schema_recommendation.schema_id if schema_recommendation is not None else ""
                ),
            ),
            recommendation_schema_id=(
                schema_recommendation.schema_id if schema_recommendation is not None else ""
            ),
            recommendation_reasons=(
                schema_recommendation.reasons if schema_recommendation is not None else ()
            ),
        )

    context = (
        material_context
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    schema_id = schema_ids[0] if schema_ids else ""
    check = evaluate_material_requirements(
        schema_id=schema_id,
        schema_ids=schema_ids,
        entity_data=getattr(context, "entity_data", {}) or {},
        asset_roles=_material_context_asset_roles(context),
        extra_required_fields=extra_fields,
        extra_required_asset_roles=extra_roles,
    )
    missing_asset_roles = _unique_texts(
        [
            *check.missing_asset_roles,
            *(
                context.missing_required_asset_roles()
                if isinstance(context, MaterialExecutionContext)
                else []
            ),
        ]
    )
    issue_groups = MaterialReadinessIssueGroups(
        schema_ids=missing_schema_ids,
        field_keys=tuple(check.missing_field_keys),
        asset_roles=tuple(missing_asset_roles),
        source_notes=_material_source_notes(
            missing_schema_ids=missing_schema_ids,
            schema_ids=schema_ids,
            schema_labels=check.requirements.schema_labels,
            extra_fields=extra_fields,
            extra_roles=extra_roles,
            material_context=context,
            include_context=bool(check.missing_field_keys or missing_asset_roles),
            recommendation_schema_id=(
                schema_recommendation.schema_id if schema_recommendation is not None else ""
            ),
        ),
        recommendation_schema_id=(
            schema_recommendation.schema_id if schema_recommendation is not None else ""
        ),
        recommendation_reasons=(
            schema_recommendation.reasons if schema_recommendation is not None else ()
        ),
    )
    if not issue_groups.has_issues:
        return MaterialReadinessIssueGroups()
    return issue_groups


def _missing_scene_material_schema_ids(scene) -> tuple[str, ...]:
    return missing_material_schema_ids(_scene_material_schema_ids(scene))


def _scene_material_schema_ids(scene) -> tuple[str, ...]:
    profile = getattr(scene, "input_source_profile", None)
    if profile is None:
        return ()
    schema_ids = resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or ""),
        list(getattr(profile, "material_schema_ids", []) or []),
    )
    return schema_ids


def _material_context_asset_roles(context: MaterialExecutionContext) -> list[str]:
    return _unique_texts(
        [
            str(getattr(item, "role", "") or "")
            for item in list(getattr(context, "asset_items", []) or [])
            if str(getattr(item, "path", "") or "").strip()
        ]
    )


def _asset_metadata(item: object) -> dict[str, str]:
    metadata = getattr(item, "metadata", {})
    if not isinstance(metadata, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in metadata.items()
        if str(key or "").strip() and str(value or "").strip()
    }


def _asset_render_path(item: AssetItem) -> str:
    raw_path = str(getattr(item, "path", "") or "").strip()
    if raw_path:
        return raw_path
    return _asset_cached_path(_asset_metadata(item))


def _asset_cached_path(metadata: dict[str, str]) -> str:
    for key in (
        "cache_path",
        "cachePath",
        "cached_path",
        "cachedPath",
        "local_path",
        "localPath",
        "local_cache_path",
        "localCachePath",
        "resolved_path",
        "resolvedPath",
        "download_path",
        "downloadPath",
        "asset_path",
        "assetPath",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _looks_like_remote_asset_path(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith(("http://", "https://", "asset://", "lark://"))


def _question_figure_target_value(metadata: dict[str, str]) -> str:
    return (
        str(metadata.get("question_index") or metadata.get("questionIndex") or "").strip()
        or str(metadata.get("question_id") or metadata.get("questionId") or "").strip()
        or str(metadata.get("question_no") or metadata.get("questionNo") or "").strip()
        or str(metadata.get("number") or metadata.get("no") or "").strip()
    )


def _question_figure_item_repair_target_key(
    item: AssetItem,
    question_target: str,
) -> str:
    metadata = _asset_metadata(item)
    render_path = _asset_render_path(item)
    target: dict[str, object] = {
        "role": "question_figure",
        "item_id": str(getattr(item, "item_id", "") or ""),
        "question_index": str(question_target or ""),
        "path": render_path,
        "metadata": metadata,
    }
    cache_path = _asset_cached_path(metadata)
    if cache_path and not _looks_like_remote_asset_path(render_path):
        target["cache_path"] = cache_path
    asset_id = (
        str(metadata.get("asset_id") or "").strip()
        or str(metadata.get("assetId") or "").strip()
    )
    if asset_id:
        target["asset_id"] = asset_id
    return json.dumps(target, ensure_ascii=False, separators=(",", ":"))


def _material_schema_recommendation(scene, missing_schema_ids: tuple[str, ...]):
    if not missing_schema_ids:
        return None
    schema_ids = _scene_material_schema_ids(scene)
    return recommend_material_schema_replacement(
        missing_schema_ids,
        family_hints=(
            str(getattr(scene, "category", "") or ""),
            str(getattr(scene, "scene_id", "") or ""),
        ),
        existing_schema_ids=tuple(
            schema_id for schema_id in schema_ids if schema_id not in missing_schema_ids
        ),
    )


def _coverage_packs_for_scene_context(scene) -> tuple[SceneCoveragePack, ...]:
    keys = _unique_texts(
        [
            str(getattr(scene, "scene_id", "") or ""),
            str(getattr(scene, "category", "") or ""),
        ]
    )
    packs: list[SceneCoveragePack] = []
    for key in keys:
        try:
            packs.append(get_scene_coverage_pack(key))
        except KeyError:
            pass
        packs.extend(coverage_packs_for_scene(key))
        packs.extend(coverage_packs_for_family(key))
    return tuple(_dedupe_coverage_packs(packs))


def _dedupe_coverage_packs(packs: list[SceneCoveragePack]) -> list[SceneCoveragePack]:
    result: list[SceneCoveragePack] = []
    seen: set[str] = set()
    for pack in packs:
        if pack.pack_id in seen:
            continue
        seen.add(pack.pack_id)
        result.append(pack)
    return result


def _coverage_boundary_details(pack: SceneCoveragePack) -> tuple[str, ...]:
    details: list[str] = []
    primary = ", ".join(pack.primary_landings)
    secondary = ", ".join(pack.secondary_landings)
    axes = ", ".join(pack.capability_axis_ids)
    if primary:
        details.append("首选承载：" + primary)
    if secondary:
        details.append("次级承载：" + secondary)
    if axes:
        details.append("能力轴：" + axes)
    gate = plugin_manual_gate_for_pack(pack.pack_id)
    if gate is not None:
        details.append("插件入口：" + gate.plugin_entry_id)
        details.append(
            "人工确认："
            + ("required" if gate.manual_confirmation_required else "optional")
        )
        details.append(
            "置信度报告："
            + ("required" if gate.confidence_report_required else "optional")
        )
        if gate.risk_domain_ids:
            details.append("风险域：" + ", ".join(gate.risk_domain_ids))
        if gate.confirmation_decision_states:
            details.append(
                "确认状态：" + ", ".join(gate.confirmation_decision_states)
            )
        if gate.unsupported_core_inputs:
            details.append("核心不直接承诺：" + ", ".join(gate.unsupported_core_inputs))
    if pack.closure_tasks:
        for task in list(pack.closure_tasks)[:3]:
            details.append(
                "未闭合"
                f"[{task.priority}/{task.owner}/{task.target_phase}]：{task.summary}"
            )
    else:
        for closure in list(pack.missing_closures or ())[:3]:
            details.append("未闭合：" + closure)
    details.append("执行策略：核心只做排版/资料/交付闭环，专业判断或生成质量需插件或人工确认")
    return tuple(details)


def _sample_fixture_issue(
    *,
    pack_id: str,
    issue: SceneSampleFixtureAuditIssue,
) -> WorkbenchIssueItem:
    issue_key = f"{pack_id}.{issue.kind}.{issue.fixture_id}"
    details = [
        "覆盖 pack：" + pack_id,
        "缺口类型：" + issue.kind,
        issue.message,
    ]
    if issue.fixture_id and issue.fixture_id != pack_id:
        details.append("样本/对象：" + issue.fixture_id)
    return WorkbenchIssueItem(
        issue_id=f"sample_fixture.{_issue_token(issue_key)}",
        category="sample_fixture",
        severity=issue.severity or "warning",
        title="样本覆盖缺口",
        summary=f"{pack_id}: {issue.kind}",
        details=tuple(details),
        source_notes=("scene_sample_fixture_registry",),
        repair_target_type="sample_fixture",
        repair_target_key=pack_id,
        blocking=False,
        owner="scene",
    )


def _sample_fixture_issue_pack_id(
    issue: SceneSampleFixtureAuditIssue,
    pack_ids: tuple[str, ...],
) -> str:
    fixture_or_pack = str(getattr(issue, "fixture_id", "") or "").strip()
    if fixture_or_pack in pack_ids:
        return fixture_or_pack
    try:
        fixture = get_scene_sample_fixture(fixture_or_pack)
    except KeyError:
        if str(getattr(issue, "kind", "") or "").strip() == "missing_required_surface":
            return pack_ids[0] if pack_ids else ""
        return ""
    return fixture.pack_id if fixture.pack_id in pack_ids else ""


def _material_source_notes(
    *,
    missing_schema_ids: tuple[str, ...] = (),
    schema_ids: tuple[str, ...] = (),
    schema_labels: tuple[str, ...] = (),
    extra_fields: list[str] | None = None,
    extra_roles: list[str] | None = None,
    material_context: MaterialExecutionContext | None = None,
    include_context: bool = False,
    recommendation_schema_id: str = "",
) -> tuple[str, ...]:
    notes: list[str] = []
    if missing_schema_ids:
        notes.append("未注册 Schema：" + ", ".join(missing_schema_ids))
    if recommendation_schema_id:
        notes.append("推荐 Schema：" + recommendation_schema_id)
    if schema_ids:
        schema_notes: list[str] = []
        for index, schema_id in enumerate(schema_ids):
            label = schema_labels[index] if index < len(schema_labels) else ""
            if label and label != schema_id:
                schema_notes.append(f"{label} ({schema_id})")
            else:
                schema_notes.append(schema_id)
        notes.append("Schema：" + ", ".join(schema_notes))
    normalized_fields = _unique_texts(list(extra_fields or []))
    if normalized_fields:
        notes.append("场景字段：" + ", ".join(normalized_fields))
    normalized_roles = _unique_texts(list(extra_roles or []))
    if normalized_roles:
        notes.append("场景资产：" + ", ".join(normalized_roles))
    if include_context:
        context = (
            material_context
            if isinstance(material_context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        profile_label = str(context.profile_name or context.profile_id or "").strip()
        if profile_label:
            notes.append("当前资料：" + profile_label)
        elif context.is_empty():
            notes.append("当前资料：未配置")
    return tuple(_unique_texts(notes))


def _unique_texts(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _clean_reason_list(reasons: list[str] | None) -> list[str]:
    return [
        text
        for text in (str(item or "").strip() for item in list(reasons or []))
        if text
    ]


def _count_issue_values(values) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        if normalized not in counts:
            counts[normalized] = 0
            order.append(normalized)
        counts[normalized] += 1
    return tuple((key, counts[key]) for key in order)


def _count_issue_action_values(values) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    return tuple(
        sorted(
            counts.items(),
            key=lambda item: (
                workbench_issue_action_visual(item[0]).rank,
                item[0],
            ),
        )
    )


def _issue_repair_target_key(item: WorkbenchIssueItem) -> str:
    target_type = str(item.repair_target_type or "").strip()
    target_key = str(item.repair_target_key or "").strip()
    if target_type and target_key:
        return f"{target_type}:{target_key}"
    if target_type:
        return target_type
    return ""


def _issue_repair_context_value(item: WorkbenchIssueItem, key: str) -> str:
    normalized_key = str(key or "").strip()
    for context_key, context_value in tuple(getattr(item, "repair_context", ()) or ()):
        if str(context_key or "").strip() == normalized_key:
            return str(context_value or "").strip()
    return ""


def _issue_status(item: WorkbenchIssueItem) -> str:
    status = str(getattr(item, "status", "") or "").strip()
    return status or "open"


def _issue_owner(item: WorkbenchIssueItem) -> str:
    owner = str(getattr(item, "owner", "") or "").strip()
    if owner:
        return owner
    target_type = str(getattr(item, "repair_target_type", "") or "").strip()
    category = str(getattr(item, "category", "") or "").strip()
    if target_type in {"field", "asset", "schema"} or category.startswith("material_"):
        return "workbench"
    if target_type.startswith("template_") or category.startswith("template_"):
        return "template"
    if target_type in {"object_preflight", "output_target"}:
        return "scene"
    if target_type == "parameter_ownership" or category == "parameter_ownership":
        return "scene"
    if target_type == "control_contract" or category == "control_contract":
        return "scene"
    if target_type == "sample_fixture" or category == "sample_fixture":
        return "scene"
    if target_type == "coverage_boundary" or category == "plugin_boundary":
        return "plugin"
    return "workbench"


def _parameter_ownership_detail_lines(
    audit: ParameterOwnershipAuditResult,
) -> list[str]:
    lines: list[str] = []
    if audit.missing_top_level_paths:
        lines.append("缺少顶层字段归属：" + ", ".join(audit.missing_top_level_paths))
    if audit.missing_required_paths:
        lines.append("缺少必审路径：" + ", ".join(audit.missing_required_paths))
    if audit.unknown_spec_paths:
        lines.append("未知 registry 路径：" + ", ".join(audit.unknown_spec_paths))
    if audit.invalid_owner_layers:
        invalid = ", ".join(
            f"{path}:{owner}" for path, owner in audit.invalid_owner_layers
        )
        lines.append("非法归属层：" + invalid)
    return lines


def _control_contract_issue(
    *,
    issue_id: str,
    title: str,
    summary: str,
    detail: str,
    repair_target_key: str,
) -> WorkbenchIssueItem:
    return WorkbenchIssueItem(
        issue_id=issue_id,
        category="control_contract",
        severity="warning",
        title=title,
        summary=summary,
        details=tuple(_control_contract_issue_detail_lines(repair_target_key, detail)),
        source_notes=("control_contract_registry",),
        repair_target_type="control_contract",
        repair_target_key=repair_target_key or "registry",
        blocking=False,
        owner="scene",
    )


def _control_contract_issue_detail_lines(
    contract_id: str,
    primary_detail: str,
) -> list[str]:
    lines = [str(primary_detail or "").strip()] if str(primary_detail or "").strip() else []
    normalized_id = str(contract_id or "").strip()
    if not normalized_id or normalized_id == "registry":
        return lines
    try:
        contract = get_control_contract(normalized_id)
    except KeyError:
        lines.append("契约：" + normalized_id)
        return lines

    lines.extend(
        [
            f"契约：{contract.canonical_label} ({contract.contract_id})",
            "规范控件：" + contract.canonical_control,
            "归属层：" + contract.owner_layer,
        ]
    )
    if contract.parameter_paths:
        lines.append("参数路径：" + ", ".join(contract.parameter_paths))
    surfaces = [
        ("模板表面", contract.template_surface),
        ("场景表面", contract.scene_surface),
        ("工作台表面", contract.workbench_surface),
    ]
    for label, value in surfaces:
        cleaned = str(value or "").strip()
        if cleaned:
            lines.append(f"{label}：{cleaned}")
    evidence_lines = [
        _control_contract_evidence_location_line(location)
        for location in resolve_control_contract_evidence_locations(contract.contract_id)
    ]
    if evidence_lines:
        lines.extend(evidence_lines)
    else:
        for evidence in contract.evidence:
            source_path = str(evidence.source_path or "").strip()
            if source_path:
                lines.append("证据：" + source_path)
    if contract.notes:
        lines.append("说明：" + contract.notes)
    return lines


def _control_contract_evidence_location_line(location) -> str:
    line_number = int(getattr(location, "line_number", 0) or 0)
    source_path = str(getattr(location, "source_path", "") or "").strip()
    marker = str(getattr(location, "marker", "") or "").strip()
    suffix = f":{line_number}" if line_number > 0 else ":0"
    if source_path and marker:
        return f"证据：{source_path}{suffix}#{marker}"
    if source_path:
        return f"证据：{source_path}{suffix}"
    return "证据：-"


def _control_contract_detail_lines(
    audit: ControlContractAuditResult,
) -> list[str]:
    lines: list[str] = []
    if audit.missing_required_contracts:
        lines.append("缺少必审控件契约：" + ", ".join(audit.missing_required_contracts))
    if audit.invalid_owner_layers:
        invalid = ", ".join(
            f"{contract_id}:{owner_layer}"
            for contract_id, owner_layer in audit.invalid_owner_layers
        )
        lines.append("非法控件归属层：" + invalid)
    if audit.missing_paired_contracts:
        missing_pairs = ", ".join(
            f"{contract_id}->{paired_id}"
            for contract_id, paired_id in audit.missing_paired_contracts
        )
        lines.append("配对控件缺失：" + missing_pairs)
    if audit.missing_evidence_files:
        missing_files = ", ".join(
            f"{contract_id}:{source_path}"
            for contract_id, source_path in audit.missing_evidence_files
        )
        lines.append("证据文件缺失：" + missing_files)
    if audit.missing_evidence_markers:
        missing_markers = ", ".join(
            f"{contract_id}:{source_path}#{marker}"
            for contract_id, source_path, marker in audit.missing_evidence_markers
        )
        lines.append("证据 marker 缺失：" + missing_markers)
    return lines


def _dict_payload(value: dict[str, object] | None) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _json_object(value: str) -> dict[str, object]:
    try:
        payload = json.loads(str(value or ""))
    except (TypeError, ValueError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _string_path_map(value: dict[str, str] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(path)
        for key, path in value.items()
        if str(key or "").strip() and str(path or "").strip()
    }


def _style_source_receipt_summary(
    value: dict[str, object],
    *,
    fallback: str = "",
) -> str:
    return _style_source_receipt_envelope(
        value,
        fallback=fallback,
    ).receipt_summary(title_fallback="样式来源")


def _style_source_receipt_envelope(
    value: dict[str, object],
    *,
    fallback: str = "",
) -> StylePresentationEnvelope:
    return StylePresentationEnvelope.from_execution_result(
        value,
        fallback=fallback,
    )


def _style_difference_summary_projection(
    value: dict[str, object],
) -> StyleDifferenceSummaryProjection | None:
    direct = value.get("difference_summary") or value.get("style_difference_summary")
    if isinstance(direct, StyleDifferenceSummaryProjection):
        return direct
    if isinstance(direct, dict):
        return _style_difference_summary_from_payload(direct)

    projections = tuple(
        projection
        for projection in (
            _style_difference_projection_from_payload(item)
            for item in _list_values(
                value.get("sections") or value.get("section_differences")
            )
        )
        if projection is not None
    )
    return build_style_difference_summary_projection(projections)


def _style_difference_summary_from_payload(
    value: dict[str, object],
) -> StyleDifferenceSummaryProjection | None:
    template_status = _clean_text(value.get("template_status")) or "模板基线"
    current_status = _clean_text(value.get("current_status"))
    difference_status = _clean_text(value.get("difference_status"))
    detail = _clean_text(value.get("detail"))
    section_count = _safe_int(value.get("section_count"))
    changed_section_count = _safe_int(value.get("changed_section_count"))
    pending_section_count = _safe_int(value.get("pending_section_count"))
    if not any(
        (
            current_status,
            difference_status,
            detail,
            section_count,
            changed_section_count,
            pending_section_count,
        )
    ):
        return None
    return StyleDifferenceSummaryProjection(
        template_status=template_status,
        current_status=current_status,
        difference_status=difference_status,
        detail=detail,
        variant=_clean_text(value.get("variant")) or "info",
        section_count=section_count,
        changed_section_count=changed_section_count,
        pending_section_count=pending_section_count,
    )


def _style_difference_projection_from_payload(
    value: object,
) -> StyleDifferenceProjection | None:
    if isinstance(value, StyleDifferenceProjection):
        return value
    if not isinstance(value, dict):
        return None

    changed_labels = _clean_list(value.get("changed_labels"))
    changed_count = _safe_int(value.get("changed_count"))
    if not changed_labels and changed_count > 0:
        changed_labels = (f"{changed_count} 项字段",)

    scope_label = (
        _clean_text(value.get("scope_label"))
        or _clean_text(value.get("label"))
        or _clean_text(value.get("section_label"))
        or _clean_text(value.get("variant_key"))
    )
    variant_key = _clean_text(value.get("variant_key")) or scope_label
    overridden = _safe_bool(
        value.get("overridden"),
        default=bool(changed_labels or _clean_text(value.get("difference_status"))),
    )
    follows_template = _safe_bool(value.get("follows_template"), default=not overridden)
    section_enabled = _safe_bool(value.get("section_enabled"), default=True)
    template_available = _safe_bool(value.get("template_available"), default=True)
    current_status = _clean_text(value.get("current_status")) or (
        "独立样式" if overridden else "跟随模板"
    )
    difference_status = _clean_text(value.get("difference_status")) or (
        f"已调整 {len(changed_labels)} 项" if changed_labels else "无差异"
    )

    if not any((scope_label, changed_labels, overridden, difference_status)):
        return None
    return StyleDifferenceProjection(
        variant_key=variant_key,
        scope_label=scope_label or "分区",
        section_enabled=section_enabled,
        overridden=overridden,
        follows_template=follows_template,
        template_available=template_available,
        changed_labels=changed_labels,
        compact_label=_clean_text(value.get("compact_label")),
        detail_label=_clean_text(value.get("detail_label")),
        status_label=_clean_text(value.get("status")),
        template_status=_clean_text(value.get("template_status")) or "模板基线",
        current_status=current_status,
        difference_status=difference_status,
        detail=_clean_text(value.get("detail")),
        variant=_clean_text(value.get("variant")) or ("warning" if overridden else "info"),
    )


def _object_preflight_summary(value: dict[str, object]) -> str:
    if not value or value.get("enabled") is False:
        return ""
    findings_count = _safe_int(value.get("findings_count"))
    module_skips_count = _safe_int(value.get("module_skips_count"))
    scan_targets = [
        str(item or "").strip()
        for item in list(value.get("scan_targets") or [])
        if str(item or "").strip()
    ]
    if findings_count > 0:
        summary = f"对象预检：{findings_count} 项风险"
        if module_skips_count > 0:
            summary = f"{summary} · 跳过 {module_skips_count} 个模块"
        return summary
    if module_skips_count > 0:
        return f"对象预检：跳过 {module_skips_count} 个模块"
    if scan_targets:
        return "对象预检：未发现风险"
    return ""


def _object_preflight_detail_lines(
    value: dict[str, object],
    *,
    limit: int = 8,
) -> list[str]:
    if not value or value.get("enabled") is False or limit <= 0:
        return []

    entries: list[tuple[str, dict[str, object]]] = []
    for finding in list(value.get("findings") or []):
        if isinstance(finding, dict):
            entries.append(("finding", finding))
    for module_skip in list(value.get("module_skips") or []):
        if isinstance(module_skip, dict):
            entries.append(("skip", module_skip))

    lines: list[str] = []
    for kind, payload in entries[:limit]:
        if kind == "finding":
            line = _object_preflight_finding_line(payload)
        else:
            line = _object_preflight_skip_line(payload)
        if line:
            lines.append(line)
    remaining = len(entries) - len(lines)
    if remaining > 0:
        lines.append(f"... 还有 {remaining} 条对象预检明细")
    return lines


def _object_preflight_finding_line(finding: dict[str, object]) -> str:
    kind = _clean_text(finding.get("kind"))
    severity = _clean_text(finding.get("severity")) or "warning"
    location = _clean_text(finding.get("location"))
    message = _clean_text(finding.get("message"))

    head = f"风险[{severity}]"
    if kind:
        head = f"{head} {kind}"
    if location:
        head = f"{head} @ {location}"
    if message:
        return f"{head}: {message}"
    return head if kind or location else ""


def _object_preflight_skip_line(module_skip: dict[str, object]) -> str:
    module_name = _clean_text(module_skip.get("module_name"))
    reason = _clean_text(module_skip.get("reason"))
    finding_kinds = [
        cleaned
        for cleaned in (_clean_text(item) for item in _list_values(module_skip.get("finding_kinds")))
        if cleaned
    ]
    if not module_name and not finding_kinds and not reason:
        return ""

    head = "跳过模块"
    if module_name:
        head = f"{head} {module_name}"
    if finding_kinds:
        head = f"{head} <- {'/'.join(finding_kinds)}"
    if reason:
        return f"{head}: {reason}"
    return head


def _object_preflight_source_notes(value: dict[str, object]) -> tuple[str, ...]:
    notes: list[str] = []
    preservation_mode = _clean_text(value.get("preservation_mode"))
    if preservation_mode:
        notes.append("保护模式：" + preservation_mode)
    scan_targets = [
        cleaned
        for cleaned in (_clean_text(item) for item in _list_values(value.get("scan_targets")))
        if cleaned
    ]
    if scan_targets:
        notes.append("扫描对象：" + ", ".join(scan_targets))
    return tuple(notes)


def _object_preflight_related_skip_lines(
    finding: dict[str, object],
    module_skips: list[dict[str, object]],
) -> tuple[list[str], set[int]]:
    finding_kind = _clean_text(finding.get("kind"))
    if not finding_kind:
        return [], set()
    lines: list[str] = []
    indexes: set[int] = set()
    for index, module_skip in enumerate(module_skips):
        finding_kinds = {
            cleaned
            for cleaned in (
                _clean_text(item)
                for item in _list_values(module_skip.get("finding_kinds"))
            )
            if cleaned
        }
        if finding_kind not in finding_kinds:
            continue
        line = _object_preflight_skip_line(module_skip)
        if line:
            lines.append(line)
            indexes.add(index)
    return lines, indexes


def _object_preflight_finding_target_key(
    finding: dict[str, object],
    index: int,
) -> str:
    kind = _clean_text(finding.get("kind"))
    location = _clean_text(finding.get("location"))
    if kind and location:
        return f"{kind}@{location}"
    return kind or location or f"finding-{index}"


def _object_preflight_skip_target_key(
    module_skip: dict[str, object],
    index: int,
) -> str:
    module_name = _clean_text(module_skip.get("module_name"))
    finding_kinds = [
        cleaned
        for cleaned in (
            _clean_text(item)
            for item in _list_values(module_skip.get("finding_kinds"))
        )
        if cleaned
    ]
    if module_name and finding_kinds:
        return f"skip:{module_name}<-{'/'.join(finding_kinds)}"
    return f"skip:{module_name or index}"


def _issue_token(value: str) -> str:
    token = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(value or "").strip().lower()
    ).strip("_")
    return token or "item"


def _material_field_consistency_summary(value: dict[str, object]) -> str:
    if not value:
        return ""
    schema_id = str(value.get("schema_id") or "").strip()
    status = str(value.get("status") or "").strip()
    issue_count = _safe_int(value.get("issue_count"))
    field_count = _safe_int(value.get("field_count"))
    if not schema_id and not status and field_count <= 0:
        return ""
    if status == "not_applicable" and field_count <= 0:
        return ""
    label = schema_id or "material fields"
    if issue_count > 0:
        return f"字段一致性：{label} · {issue_count} 项风险"
    if status in {"ok", "not_applicable"} or field_count > 0:
        return f"字段一致性：{label} · 通过"
    return f"字段一致性：{label} · {status}"


def _batch_isolation_summary(value: dict[str, object]) -> str:
    if not value:
        return ""
    total = _safe_int(value.get("total_count"))
    success = _safe_int(value.get("success_count"))
    warning = _safe_int(value.get("warning_count"))
    failed = _safe_int(value.get("failed_count"))
    if total <= 0 and success <= 0 and warning <= 0 and failed <= 0:
        return ""
    return (
        "Batch isolation: "
        f"total={total}; success={success}; warning={warning}; failed={failed}"
    )


def _batch_isolation_detail_lines(value: dict[str, object]) -> list[str]:
    if not value:
        return []
    lines: list[str] = []
    for profile in list(value.get("profiles") or []):
        if not isinstance(profile, dict):
            continue
        status = _clean_text(profile.get("status"))
        if status == "success":
            continue
        label = (
            _clean_text(profile.get("profile_name"))
            or _clean_text(profile.get("profile_id"))
            or "profile"
        )
        summary = _clean_text(profile.get("summary"))
        missing_fields = _clean_list(profile.get("missing_field_keys"))
        missing_assets = _clean_list(profile.get("missing_asset_roles"))
        detail = f"{label}: {status or 'failed'}"
        if missing_fields:
            detail += " | missing fields=" + ",".join(missing_fields)
        if missing_assets:
            detail += " | missing assets=" + ",".join(missing_assets)
        if summary:
            detail += " | " + summary
        lines.append(detail)
    return lines


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_bool(value, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enabled", "启用", "是"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disabled", "停用", "否"}:
        return False
    return bool(default)


def _clean_text(value) -> str:
    return " ".join(str(value or "").strip().split())


def _clean_list(value) -> tuple[str, ...]:
    return tuple(
        cleaned
        for cleaned in (_clean_text(item) for item in _list_values(value))
        if cleaned
    )


def _list_values(value) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _batch_issue_detail_lines(
    *,
    profile_id: str,
    profile_name: str,
    status: str,
    parameter_paths: tuple[str, ...],
    missing_fields: tuple[str, ...],
    missing_assets: tuple[str, ...],
    suspicious_assets: list[dict[str, object]],
    comparison_assets: list[dict[str, object]],
) -> list[str]:
    lines: list[str] = []
    if profile_id:
        lines.append("记录 ID：" + profile_id)
    if profile_name:
        lines.append("记录名称：" + profile_name)
    if status:
        lines.append("执行状态：" + status)
    if parameter_paths:
        lines.append("参数路径：" + ", ".join(parameter_paths[:3]))
    if missing_fields:
        lines.append("缺字段：" + ", ".join(missing_fields))
    if missing_assets:
        lines.append("缺素材：" + ", ".join(missing_assets))
    for item in suspicious_assets[:3]:
        target = _clean_text(item.get("question_index"))
        detected = _clean_text(item.get("detected_question_index"))
        path = _clean_text(item.get("path"))
        filename = Path(path).name if path else ""
        pieces = [
            f"目标题号 {target}" if target else "",
            f"文件名题号 {detected}" if detected else "",
            filename,
        ]
        lines.append("疑似错图：" + " / ".join(piece for piece in pieces if piece))
    for item in comparison_assets[:3]:
        target = _clean_text(item.get("question_index"))
        issue_kind = _clean_text(item.get("comparison_issue_kind")) or "题图对比"
        display = (
            _clean_text(item.get("comparison_issue_display_name"))
            or _clean_text(item.get("comparison_issue_reference"))
            or _clean_text(item.get("path"))
        )
        marked_at = _clean_text(item.get("comparison_issue_marked_at"))
        region_summary = _clean_text(item.get("comparison_issue_region_summary"))
        pieces = [
            f"题号 {target}" if target else "",
            issue_kind,
            display,
            f"标注时间 {marked_at}" if marked_at else "",
            f"区域 {region_summary}" if region_summary else "",
        ]
        lines.append("人工对比问题：" + " / ".join(piece for piece in pieces if piece))
    return lines
