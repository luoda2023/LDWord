"""User-facing scene overview projection.

This module keeps the first screen focused on task intent and next actions.
The heavier matrix, fixture, and release evidence remains in
``scene_summary_projection`` and should be shown as advanced evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from src.config.default_delivery_identity import project_default_delivery_identity
from src.config.scene import ExamPaperConfig, SceneWorkspace, coerce_exam_paper_config
from src.config.template import TemplateConfig
from src.shared.engine.exam_paper_style import (
    exam_blank_style_label,
    resolve_exam_blank_style,
)
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
)
from src.ui.panels.scene_product_summary_projection import (
    build_input_profile_summary_items,
    build_product_scene_overview_summary_items,
    material_schema_display_name,
    scene_document_scope_display_name,
)
from src.ui.panels.style_source_projection import (
    StyleSourceProjection,
    build_style_source_projection,
)
from src.ui.panels.workbench.execution_flow_projection import standard_execution_flow_steps


@dataclass(frozen=True)
class SceneOverviewTaskSpec:
    title: str
    template_label: str
    numbering_label: str
    suitable_for: str
    boundary_note: str


@dataclass(frozen=True)
class SceneRunStepSpec:
    key: str
    title: str
    detail: str
    icon_name: str = "circle"


@dataclass(frozen=True)
class SceneOverviewRowSpec:
    key: str
    label: str
    summary: str
    target_card_id: str
    icon_name: str = "circle"
    status: str = "会处理"
    action_label: str = ""
    secondary_target_card_id: str = ""
    secondary_action_label: str = ""


@dataclass(frozen=True)
class SceneRiskNoticeSpec:
    key: str
    label: str
    detail: str
    severity: str = "info"


@dataclass(frozen=True)
class SceneEvidenceLinkSpec:
    key: str
    label: str
    summary: str
    evidence_key: str


@dataclass(frozen=True)
class SceneOverviewSpec:
    task: SceneOverviewTaskSpec
    run_steps: tuple[SceneRunStepSpec, ...]
    style_source: StyleSourceProjection
    key_settings: tuple[SceneOverviewRowSpec, ...]
    risk_notices: tuple[SceneRiskNoticeSpec, ...]
    evidence_links: tuple[SceneEvidenceLinkSpec, ...]


FIRST_SCREEN_BANNED_TERMS = (
    "pack",
    "fixture",
    "proxy",
    "drilldown",
    "source evidence",
    "Green/L5",
    "Blue/Boundary",
    "maturity",
    "static closure",
    "contract",
    "OOXML",
    "handoff",
    "gate",
    "registry",
    "profile id",
    "schema",
    "preset",
    "manual_review",
    "docx",
    "xlsx",
    "content_controls",
    "custom_basic",
    "quick_formatting",
    "template ",
    "scene ",
    "material ",
    "output ",
    "plugin ",
    "manual /",
    "field/comment",
)

EXAM_RUNTIME_FIELD_LABELS = {
    "title": "标题",
    "subject": "科目",
    "grade": "年级",
    "duration": "考试时间",
    "total_score": "满分",
    "class_name": "班级",
    "teacher": "命题人",
    "exam_date": "日期",
}


def build_scene_overview_spec(
    scene: SceneWorkspace,
    *,
    template: TemplateConfig | None = None,
    template_label: str = "",
    template_preview_action: str = "",
) -> SceneOverviewSpec:
    summary = _summary_item_map(scene)
    input_item = summary.get("input_profile")
    risk_item = summary.get("object_preflight")
    output_item = summary.get("delivery")
    style_source = build_style_source_projection(
        scene,
        template=template,
        template_label=template_label,
        template_preview_action=template_preview_action,
    )

    return SceneOverviewSpec(
        task=build_scene_task_summary(scene, template_label=template_label, summary=summary),
        run_steps=build_scene_run_preview_steps(
            scene,
            template_label=template_label,
            input_summary=_item_value(input_item, "Word 文档"),
            risk_summary=_risk_setting_summary(risk_item),
            output_summary=_item_value(output_item, "最终 Word"),
        ),
        style_source=style_source,
        key_settings=build_scene_key_setting_rows(
            scene,
            template=template,
            template_label=template_label,
            template_preview_action=template_preview_action,
            style_source=style_source,
            input_summary=_input_setting_summary(scene, input_item),
            output_summary=_output_setting_summary(output_item),
        ),
        risk_notices=build_scene_risk_notices(scene, summary=summary),
        evidence_links=build_scene_evidence_links(summary),
    )


def build_scene_task_summary(
    scene: SceneWorkspace,
    *,
    template_label: str = "",
    summary: dict[str, object] | None = None,
) -> SceneOverviewTaskSpec:
    summary = summary or _summary_item_map(scene)
    coverage_item = summary.get("coverage_pack")
    risk_item = summary.get("object_preflight")
    title = str(getattr(scene, "name", "") or "").strip() or _item_value(
        coverage_item,
        str(getattr(scene, "category_label", "") or "").strip() or "当前任务",
    )
    template = str(template_label or "").strip() or _template_label_from_scene(scene)
    suitable_for = _task_suitable_for(scene, summary, template)
    boundary = _task_boundary_note(summary, risk_item)
    return SceneOverviewTaskSpec(
        title=_clean_first_screen_text(title),
        template_label=_clean_first_screen_text(template),
        numbering_label="重建编号" if bool(getattr(scene, "strict_mode", False)) else "保留原编号",
        suitable_for=_clean_first_screen_text(suitable_for),
        boundary_note=_clean_first_screen_text(boundary),
    )


def build_scene_run_preview_steps(
    scene: SceneWorkspace,
    *,
    template_label: str = "",
    input_summary: str = "Word 文档",
    risk_summary: str = "检查高风险 Word 对象",
    output_summary: str = "最终 Word",
) -> tuple[SceneRunStepSpec, ...]:
    if _is_exam_scene(scene):
        return _build_exam_run_preview_steps()
    template = _clean_first_screen_text(
        str(template_label or "").strip() or _template_label_from_scene(scene)
    )
    flow = {step.key: step for step in standard_execution_flow_steps()}
    return (
        SceneRunStepSpec(
            key=flow["read"].key,
            title=flow["read"].title,
            detail=f"读取 {input_summary}",
            icon_name=flow["read"].icon_name,
        ),
        SceneRunStepSpec(
            key=flow["preflight"].key,
            title=flow["preflight"].title,
            detail=_shorten_sentence(risk_summary),
            icon_name=flow["preflight"].icon_name,
        ),
        SceneRunStepSpec(
            key=flow["format"].key,
            title=flow["format"].title,
            detail=f"按“{template}”统一主要样式",
            icon_name=flow["format"].icon_name,
        ),
        SceneRunStepSpec(
            key=flow["report"].key,
            title=flow["report"].title,
            detail="记录提醒和处理结果",
            icon_name=flow["report"].icon_name,
        ),
        SceneRunStepSpec(
            key=flow["deliver"].key,
            title=flow["deliver"].title,
            detail=f"生成{output_summary}",
            icon_name=flow["deliver"].icon_name,
        ),
    )


def build_scene_key_setting_rows(
    scene: SceneWorkspace,
    *,
    template: TemplateConfig | None = None,
    template_label: str = "",
    template_preview_action: str = "",
    style_source: StyleSourceProjection | None = None,
    input_summary: str = "Word 文档",
    output_summary: str = "最终 Word",
) -> tuple[SceneOverviewRowSpec, ...]:
    if style_source is None:
        style_source = build_style_source_projection(
            scene,
            template=template,
            template_label=template_label,
            template_preview_action=template_preview_action,
        )
    if _is_exam_scene(scene):
        return _build_exam_key_setting_rows(scene)
    rows: list[SceneOverviewRowSpec] = [
        SceneOverviewRowSpec(
            key="materials",
            label="资料包",
            summary=_material_package_summary(scene),
            target_card_id="scn_content",
            icon_name="package",
            status=_material_package_status(scene),
            action_label="设置",
        ),
        SceneOverviewRowSpec(
            key="scope",
            label="处理范围",
            summary=_scope_setting_summary(scene),
            target_card_id="scn_rules",
            icon_name="scan-text",
            action_label="设置",
        ),
    ]
    if _scene_uses_reference_format(scene):
        rows.append(
            SceneOverviewRowSpec(
                key="reference_format",
                label="参考文献",
                summary=_reference_format_summary(scene),
                target_card_id="scn_rules",
                icon_name="book-open",
                status="论文专属",
                action_label="设置",
            )
        )
    if _should_show_delivery_row(scene):
        rows.append(
            SceneOverviewRowSpec(
                key="delivery",
                label="交付结果",
                summary=_delivery_setting_summary(scene, output_summary),
                target_card_id="scn_output",
                icon_name="file-output",
                status="特殊交付",
                action_label="设置",
            )
        )
    if scene_uses_official_document_surface(scene):
        rows = [row for row in rows if row.key != "scope"]
    return tuple(rows)


def _scene_uses_reference_format(scene: SceneWorkspace) -> bool:
    if _is_exam_scene(scene):
        return False
    profile = getattr(scene, "compliance_profile", None)
    parts = (
        getattr(scene, "scene_id", ""),
        getattr(scene, "category", ""),
        getattr(scene, "category_label", ""),
        getattr(scene, "name", ""),
        getattr(scene, "description", ""),
        getattr(profile, "profile_id", ""),
        getattr(profile, "rule_family", ""),
        getattr(profile, "count_profile_id", ""),
    )
    text = " ".join(str(part or "").lower() for part in parts)
    return any(
        token in text
        for token in (
            "academic",
            "thesis",
            "journal",
            "论文",
            "学术",
            "期刊",
            "投稿",
        )
    )


def _reference_format_summary(scene: SceneWorkspace) -> str:
    ref = scene.reference_style
    return (
        f"悬挂缩进 {ref.hanging_indent_cm:g}cm，"
        f"段后 {ref.space_after_pt:g}{getattr(ref, 'space_after_unit', 'pt')}"
    )


def _build_exam_key_setting_rows(scene: SceneWorkspace) -> tuple[SceneOverviewRowSpec, ...]:
    config = _exam_config(scene)
    blank_style = resolve_exam_blank_style(config, scene.master_id)
    return (
        SceneOverviewRowSpec(
            key="exam_blank_style",
            label="当前方案",
            summary=_exam_blank_style_summary(config, scene.master_id),
            target_card_id="scn_exam_paper",
            icon_name="layers",
            status="内置卷面" if blank_style.readonly else "可修改",
            action_label="设置",
        ),
        SceneOverviewRowSpec(
            key="exam_runtime_fields",
            label="本次信息",
            summary=_exam_runtime_fields_summary(config),
            target_card_id="scn_exam_paper",
            icon_name="settings",
            status="执行时填写",
            action_label="查看",
        ),
    )


def _build_exam_run_preview_steps() -> tuple[SceneRunStepSpec, ...]:
    return (
        SceneRunStepSpec(
            key="exam_import",
            title="导入试卷内容",
            detail="在工作台粘贴或选择 Markdown、Word",
            icon_name="file-text",
        ),
        SceneRunStepSpec(
            key="exam_fields",
            title="填写考试信息",
            detail="标题、科目、时间、满分由本次任务填写",
            icon_name="settings",
        ),
        SceneRunStepSpec(
            key="exam_structure",
            title="检查题目结构",
            detail="确认大题、小题、选项和分值",
            icon_name="list",
        ),
        SceneRunStepSpec(
            key="exam_style",
            title="套入试卷样式",
            detail="使用试卷卷面装配页面",
            icon_name="file-text",
        ),
        SceneRunStepSpec(
            key="exam_deliver",
            title="生成 Word 试卷",
            detail="按工作台本次设置输出 Word 文件",
            icon_name="book-open",
        ),
    )


def _exam_config(scene: SceneWorkspace) -> ExamPaperConfig:
    return coerce_exam_paper_config(getattr(scene, "exam_paper", None))


def _exam_blank_style_summary(config: ExamPaperConfig, master_id: str) -> str:
    label = exam_blank_style_label(master_id, config)
    return f"{label}；标题区、考试信息栏、页眉页脚和密封线由试卷卷面决定"


def _exam_runtime_fields_summary(config: ExamPaperConfig) -> str:
    labels = [
        EXAM_RUNTIME_FIELD_LABELS.get(field_id, field_id)
        for field_id in config.runtime_fields
        if str(field_id or "").strip()
    ]
    if not labels:
        labels = ["标题", "科目", "年级", "考试时间", "满分"]
    if len(labels) <= 5:
        fields = "、".join(labels)
    else:
        fields = "、".join(labels[:5]) + f"等 {len(labels)} 项"
    return f"工作台填写：{fields}"

def _scope_setting_summary(scene: SceneWorkspace) -> str:
    return scene_document_scope_display_name(scene)


def build_scene_risk_notices(
    scene: SceneWorkspace,
    *,
    summary: dict[str, object] | None = None,
) -> tuple[SceneRiskNoticeSpec, ...]:
    summary = summary or _summary_item_map(scene)
    notices: list[SceneRiskNoticeSpec] = []
    preflight = scene.compliance_profile.object_preflight
    block_on = [str(value or "").strip() for value in preflight.block_on if str(value or "").strip()]
    if block_on:
        notices.append(
            SceneRiskNoticeSpec(
                key="blocking_objects",
                label="会阻断",
                detail=f"{_readable_object_list(block_on)}会停止执行，避免破坏文档。",
                severity="warning",
            )
        )
    risk_item = summary.get("object_preflight")
    if risk_item is not None:
        notices.append(
            SceneRiskNoticeSpec(
                key="object_preflight",
                label="会提醒",
                detail=_item_detail(risk_item, "发现高风险 Word 对象时会先提醒。"),
                severity="info",
            )
        )
    manual_item = _actionable_manual_item(summary)
    if manual_item is not None:
        notices.append(
            SceneRiskNoticeSpec(
                key="manual_boundary",
                label="需确认",
                detail=_compact_manual_boundary_text(
                    _item_detail(manual_item, _item_value(manual_item, "有事项需要确认"))
                ),
                severity="warning",
            )
        )
    notices.append(
        SceneRiskNoticeSpec(
            key="professional_scope",
            label="不会替你做",
            detail="不判断法律、审计、专利、财务或翻译质量。",
            severity="neutral",
        )
    )
    by_key = {notice.key: notice for notice in notices}
    priority = (
        "blocking_objects",
        "manual_boundary",
        "professional_scope",
        "object_preflight",
    )
    cleaned: list[SceneRiskNoticeSpec] = []
    seen: set[str] = set()
    for key in priority:
        notice = by_key.get(key)
        if notice is None:
            continue
        if notice.key in seen:
            continue
        cleaned.append(
            SceneRiskNoticeSpec(
                key=notice.key,
                label=notice.label,
                detail=_clean_first_screen_text(_shorten_sentence(notice.detail)),
                severity=notice.severity,
            )
        )
        seen.add(notice.key)
        if len(cleaned) >= 3:
            break
    return tuple(cleaned)


def build_scene_evidence_links(
    summary: dict[str, object] | None = None,
) -> tuple[SceneEvidenceLinkSpec, ...]:
    summary = summary or {}
    result: list[SceneEvidenceLinkSpec] = []
    for key, label in (
        ("parameter_ownership", "参数归属"),
        ("control_contract", "格式控件一致性"),
        ("coverage_pack", "方案覆盖"),
        ("product_readiness", "可用度说明"),
        ("sample_fixture_coverage", "样本文档"),
        ("request_cell_coverage", "常见说法"),
    ):
        item = summary.get(key)
        if item is None:
            continue
        result.append(
            SceneEvidenceLinkSpec(
                key=key,
                label=label,
                summary=_item_value(item, ""),
                evidence_key=key,
            )
        )
    return tuple(result)


def first_screen_texts(spec: SceneOverviewSpec) -> tuple[str, ...]:
    texts: list[str] = [
        spec.task.title,
        spec.task.template_label,
        spec.task.numbering_label,
        spec.task.suitable_for,
        spec.task.boundary_note,
    ]
    for step in spec.run_steps:
        texts.extend((step.title, step.detail))
    for row in spec.key_settings:
        texts.extend((row.label, row.summary, row.status))
    return tuple(texts)


def first_screen_forbidden_terms(spec: SceneOverviewSpec) -> tuple[str, ...]:
    joined = "\n".join(first_screen_texts(spec)).lower()
    return tuple(term for term in FIRST_SCREEN_BANNED_TERMS if term.lower() in joined)


def _summary_item_map(scene: SceneWorkspace) -> dict[str, object]:
    return {
        item.key: item
        for item in build_product_scene_overview_summary_items(scene)
    }


def _is_exam_scene(scene: SceneWorkspace) -> bool:
    return scene_uses_exam_paper_surface(scene)


def _input_setting_summary(scene: SceneWorkspace, input_item: object | None) -> str:
    parts = [_item_value(input_item, "Word 文档")]
    input_items = {item.key: item for item in build_input_profile_summary_items(scene)}
    materials = input_items.get("materials")
    if materials is not None:
        parts.append("资料包" + _item_value(materials, "可选"))
    return "，".join(part for part in parts if part)


def _material_package_summary(scene: SceneWorkspace) -> str:
    profile = scene.input_source_profile
    schema_names = _material_schema_names(scene)
    has_material_rules = bool(
        schema_names
        or getattr(profile, "required_material_fields", ())
        or getattr(profile, "required_image_roles", ())
    )
    if not bool(getattr(profile, "require_material_package", False)) and not has_material_rules:
        return "未开启资料包，只处理当前文档"
    if schema_names:
        return "已开启：" + "、".join(schema_names[:3])
    return "已开启资料包，尚未选择资料包"


def _material_package_status(scene: SceneWorkspace) -> str:
    profile = scene.input_source_profile
    if not bool(getattr(profile, "require_material_package", False)) and not _material_schema_names(scene):
        return "未开启"
    if _material_schema_names(scene):
        return "已开启"
    return "待选择"


def _risk_setting_summary(risk_item: object | None) -> str:
    value = _item_value(risk_item, "发现风险先提醒")
    detail = _item_detail(risk_item, "")
    text = f"{value}；{detail}"
    if any(word in text for word in ("跳过", "阻断", "停止", "严格保护")):
        return "发现风险会先提醒，高风险内容不会自动改"
    return "发现风险会先提醒"


def _output_setting_summary(output_item: object | None) -> str:
    value = _item_value(output_item, "最终 Word")
    detail = _item_detail(output_item, "")
    if detail:
        output_count = _output_count_from_detail(detail)
        if output_count <= 1:
            return value
        if output_count > 1:
            return f"{value}；共 {output_count} 个版本"
        return f"{value}；{detail}"
    return value


def _manual_setting_summary(item: object | None) -> str:
    if item is None:
        return "无需人工确认"
    detail = _compact_manual_boundary_text(
        _item_detail(item, _item_value(item, "有事项需确认"))
    )
    return f"请确认：{_shorten_sentence(detail, max_chars=54)}"


def _should_show_delivery_row(scene: SceneWorkspace) -> bool:
    presets = list(getattr(scene, "delivery_presets", ()) or ())
    identity = project_default_delivery_identity(scene)
    if not identity.is_ok:
        return True
    if len(presets) > 1:
        return True
    default = identity.preset
    artifacts = getattr(default, "artifacts", None)
    if bool(getattr(default, "include_structured_intermediate", False)):
        return True
    if getattr(default, "content_visibility_rules", None):
        return True
    if bool(getattr(artifacts, "material_manifest", False)):
        return True
    if bool(getattr(artifacts, "material_package", False)):
        return True
    return bool(artifacts is not None and not bool(getattr(artifacts, "final_docx", True)))


def _delivery_setting_summary(scene: SceneWorkspace, fallback: str) -> str:
    presets = list(getattr(scene, "delivery_presets", ()) or ())
    identity = project_default_delivery_identity(scene)
    if identity.status == "invalid":
        return f"默认交付引用无效：{identity.requested_id}"
    if identity.status == "missing":
        return "未设置默认交付版本"
    default = identity.preset
    labels = [_delivery_preset_label(preset) for preset in presets]
    if len(labels) > 1:
        preview = "、".join(labels[:2])
        suffix = "等" if len(labels) > 2 else ""
        return f"会生成 {len(labels)} 个版本：{preview}{suffix}"
    extras = _delivery_extra_labels(default)
    if extras:
        return "会额外生成" + "、".join(extras)
    return fallback


def _template_setting_summary(
    template: str,
    *,
    template_preview_action: str = "",
    strict_mode: bool,
) -> str:
    action = _clean_first_screen_text(str(template_preview_action or "").strip())
    if action:
        return _shorten_sentence(f"使用“{template}”；{action}", max_chars=96)
    numbering = "重建编号" if strict_mode else "保留原编号"
    return f"使用“{template}”，编号：{numbering}"


def _task_suitable_for(
    scene: SceneWorkspace,
    summary: dict[str, object],
    template_label: str,
) -> str:
    input_value = _item_value(summary.get("input_profile"), "Word 文档")
    coverage = _item_value(summary.get("coverage_pack"), "当前方案")
    if coverage and coverage != "当前方案":
        return f"适合{coverage}：把 {input_value} 按“{template_label}”处理成可交付文档。"
    return f"把 {input_value} 按“{template_label}”处理成可交付文档。"


def _task_boundary_note(summary: dict[str, object], risk_item: object | None) -> str:
    manual = _actionable_manual_item(summary)
    if manual is not None:
        return "有内容需要先确认，确认后再继续处理"
    return "发现风险会先提醒，高风险内容不会自动改"


def _template_label_from_scene(scene: SceneWorkspace) -> str:
    return (
        str(scene.template_id or "").strip()
        or "当前模板"
    )


def _material_schema_names(scene: SceneWorkspace) -> tuple[str, ...]:
    profile = scene.input_source_profile
    schema_ids = [
        str(value or "").strip()
        for value in (
            getattr(profile, "material_schema_id", ""),
            *list(getattr(profile, "material_schema_ids", ()) or ()),
        )
        if str(value or "").strip()
    ]
    return tuple(
        material_schema_display_name(schema_id)
        for schema_id in dict.fromkeys(schema_ids)
    )


def _delivery_preset_label(preset: object) -> str:
    label = str(getattr(preset, "label", "") or "").strip()
    preset_id = str(getattr(preset, "preset_id", "") or "").strip()
    value = label or preset_id or "最终 Word"
    return _clean_first_screen_text(value).replace("Final DOCX", "最终 Word")


def _delivery_extra_labels(preset: object | None) -> tuple[str, ...]:
    if preset is None:
        return ()
    artifacts = getattr(preset, "artifacts", None)
    labels: list[str] = []
    if bool(getattr(artifacts, "material_manifest", False)):
        labels.append("资料清单")
    if bool(getattr(artifacts, "material_package", False)):
        labels.append("资料包")
    if bool(getattr(preset, "include_structured_intermediate", False)):
        labels.append("中间结果")
    if getattr(preset, "content_visibility_rules", None):
        labels.append("内容版本")
    if artifacts is not None and not bool(getattr(artifacts, "final_docx", True)):
        labels.append("非 Word 结果")
    return tuple(dict.fromkeys(labels))


def _first_existing(mapping: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        item = mapping.get(key)
        if item is not None:
            return item
    return None


def _actionable_manual_item(mapping: dict[str, object]) -> object | None:
    for key in (
        "coverage_plugin_boundary",
        "sample_fixture_boundary",
        "request_cell_boundary",
    ):
        item = mapping.get(key)
        if item is None:
            continue
        value = str(getattr(item, "value", "") or "")
        detail = str(getattr(item, "detail", "") or "")
        text = f"{value} {detail}"
        if any(
            token in text
            for token in (
                "需确认",
                "需要外部确认",
                "需人工确认",
                "人工确认",
                "专业审阅确认",
            )
        ):
            return item
    return None


def _item_value(item: object | None, fallback: str) -> str:
    if item is None:
        return fallback
    value = str(getattr(item, "value", "") or "").strip()
    if value.startswith("无效引用："):
        return value
    return _clean_first_screen_text(value or fallback)


def _item_detail(item: object | None, fallback: str) -> str:
    if item is None:
        return fallback
    detail = str(getattr(item, "detail", "") or "").strip()
    return _clean_first_screen_text(detail or fallback)


def _readable_object_list(values: Sequence[str]) -> str:
    names = {
        "macros": "宏",
        "fields": "域",
        "comments": "批注",
        "tracked_changes": "修订",
        "hidden_text": "隐藏文字",
        "ole_objects": "嵌入对象",
        "embedded_workbooks": "嵌入表格",
        "embedded_packages": "嵌入附件",
        "visio_drawings": "Visio 图",
        "textboxes": "文本框",
        "content_controls": "内容控件",
    }
    return "、".join(names.get(value, value.replace("_", " ")) for value in values)


def _compact_risk_summary(value: str, detail: str) -> str:
    status = _clean_first_screen_text(str(value or "").strip()) or "发现风险先提醒"
    parts = [
        _clean_first_screen_text(part.strip())
        for part in str(detail or "").split("；")
        if part.strip()
    ]
    if parts and parts[0] == status:
        parts = parts[1:]
    highlights: list[str] = []
    for part in parts:
        compact = _compact_risk_highlight(part)
        if compact and compact not in highlights:
            highlights.append(compact)
    if not highlights:
        return status
    return _shorten_sentence("；".join((status, *highlights[:2])), max_chars=72)


def _compact_manual_boundary_text(text: str) -> str:
    value = _clean_first_screen_text(str(text or "").strip())
    if not value:
        return ""
    if "清理格式时会保留域和批注" in value:
        if "遇到高风险对象先提醒" in value:
            return "会保留域和批注；遇到高风险对象先提醒"
        if "不会静默改写高风险对象" in value:
            return "会保留域和批注；不会静默改写高风险对象"
    return value


def _compact_risk_highlight(text: str) -> str:
    value = _clean_first_screen_text(str(text or "").strip())
    if not value:
        return ""
    value = value.replace(" 会阻断", "会阻断")
    value = value.replace(" 会停止执行", "会停止执行")
    if "会阻断" in value:
        return value
    if "先跳过" in value:
        return "高风险对象先跳过"
    return ""


def _output_count_from_detail(detail: str) -> int:
    normalized = str(detail or "").strip()
    prefix = "共 "
    marker = " 个输出版本"
    if not normalized.startswith(prefix) or marker not in normalized:
        return -1
    count_text = normalized[len(prefix): normalized.index(marker)].strip()
    return int(count_text) if count_text.isdigit() else -1


def _shorten_sentence(text: str, *, max_chars: int = 64) -> str:
    normalized = " ".join(str(text or "").replace(" / ", "、").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip("，；、 ") + "…"


def _clean_first_screen_text(text: str) -> str:
    replacements = {
        "preset_final_schema": "最终资料规则",
        "proxy": "借用样本",
        "fixture": "证据样本",
        "pack": "方案",
        "OOXML 对象": "Word 对象",
        "OOXML": "Word 对象",
        "contract": "一致性规则",
        "Green/L5": "可直接使用",
        "Blue/Boundary": "需人工/插件把关",
        "handoff": "交接",
        "gate": "确认",
        "registry": "清单",
        "profile id": "配置编号",
        "Schema": "资料规则",
        "schema": "资料规则",
        "preset": "输出版本",
        "manual_review": "人工确认",
        "content_controls": "内容控件",
        "tracked_changes": "修订",
        "hidden_text": "隐藏文字",
        "embedded_packages": "嵌入附件",
        "final": "最终",
        "docx": "Word 文档",
        "xlsx": "Excel 表格",
        "custom_basic": "基础格式",
        "quick_formatting": "快速格式清理",
        "template ": "模板 ",
        "scene ": "方案 ",
        "material ": "资料 ",
        "output ": "输出 ",
        "plugin ": "插件 ",
        "manual /": "需人工确认 /",
        "field/comment": "域和批注",
    }
    result = str(text or "").replace(" / ", "、").strip()
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = result.replace("_", " ")
    return result


__all__ = [
    "FIRST_SCREEN_BANNED_TERMS",
    "SceneEvidenceLinkSpec",
    "SceneOverviewRowSpec",
    "SceneOverviewSpec",
    "SceneOverviewTaskSpec",
    "SceneRiskNoticeSpec",
    "SceneRunStepSpec",
    "build_scene_evidence_links",
    "build_scene_key_setting_rows",
    "build_scene_overview_spec",
    "build_scene_risk_notices",
    "build_scene_run_preview_steps",
    "build_scene_task_summary",
    "first_screen_forbidden_terms",
    "first_screen_texts",
]
