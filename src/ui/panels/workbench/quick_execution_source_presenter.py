"""Source and readiness projections for the quick-execution surface."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from docx import Document

from src.application.materials import MaterialPreviewSnapshot
from src.config.master_library import get_master
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
)
from src.config.official_material_form import official_material_field_label
from src.config.scene import SceneWorkspace
from src.services.exam_markdown_source import (
    is_exam_markdown_source_path,
    load_exam_markdown_source,
)
from src.shared.engine.official_source_formatting import (
    detect_official_source_roles,
)
from src.ui.adapters.config_selector_models import master_display_label
from src.ui.adapters.workbench_execution_gate import (
    ExecutionGateDecision,
    decide_execution_gate,
)


def build_exam_source_projection(
    *,
    scene: SceneWorkspace | None,
    document_path: str,
) -> tuple[str, dict[str, str]]:
    """Build the source-card projection without leaking parsing into QWidget."""

    exam_paper = getattr(scene, "exam_paper", None)
    path_text = str(document_path or "").strip()
    if path_text and is_exam_markdown_source_path(path_text):
        return _build_exam_markdown_source_projection(
            scene=scene,
            document_path=path_text,
        )
    source_text = _exam_source_status_text(path_text)
    assembly_text = _exam_assembly_text(
        str(getattr(exam_paper, "question_structure_mode", "") or "")
    )
    delivery_text = _exam_delivery_text(
        scene,
        str(getattr(exam_paper, "answer_policy", "") or ""),
    )
    fields = list(getattr(exam_paper, "runtime_fields", []) or [])
    fields_text = "、".join(_exam_runtime_field_label(field) for field in fields)
    if not fields_text:
        fields_text = "标题、科目、年级、考试时间、满分"
    return (
        "题量待结构化校验" if path_text else "等待题稿",
        {
            "source": source_text,
            "assembly": assembly_text,
            "delivery": delivery_text,
            "fields": fields_text,
        },
    )


def _build_exam_markdown_source_projection(
    *,
    scene: SceneWorkspace | None,
    document_path: str,
) -> tuple[str, dict[str, str]]:
    path = Path(document_path)
    name = path.name or document_path
    answer_policy = str(
        getattr(getattr(scene, "exam_paper", None), "answer_policy", "") or ""
    )
    delivery_text = _exam_delivery_text(scene, answer_policy)
    try:
        import_result = load_exam_markdown_source(path)
    except Exception as exc:
        return (
            "题源需确认：Markdown 读取失败",
            {
                "source": f"Markdown 题稿：{name}",
                "assembly": "结构未识别",
                "delivery": delivery_text,
                "fields": f"读取失败：{exc}",
            },
        )

    summary = import_result.summary
    question_count = int(getattr(summary, "question_count", 0) or 0)
    section_count = int(getattr(summary, "section_count", 0) or 0)
    answered_count = int(getattr(summary, "answered_question_count", 0) or 0)
    analysis_count = int(getattr(summary, "analysis_count", 0) or 0)
    declared_total = _format_exam_score(getattr(summary, "declared_total_score", None))
    computed_total = _format_exam_score(getattr(summary, "computed_total_score", None))
    status_text = "可生成"
    if import_result.error_count:
        status_text = f"需确认：{import_result.error_count} 个错误"
    elif import_result.warning_count:
        status_text = f"需确认：{import_result.warning_count} 个提示"
    header = (
        f"已识别 {section_count} 大题 / {question_count} 小题"
        if question_count
        else "题源需确认：未识别到题目"
    )
    score_text = "分值待校验"
    if declared_total or computed_total:
        score_text = f"分值：声明 {declared_total or '-'} / 计算 {computed_total or '-'}"
    return (
        header,
        {
            "source": f"Markdown 题稿：{name}",
            "assembly": f"{section_count} 大题 / {question_count} 小题；{score_text}",
            "delivery": delivery_text,
            "fields": (
                f"答案 {answered_count}/{question_count}；"
                f"解析 {analysis_count}/{question_count}；{status_text}"
            ),
        },
    )


def _exam_runtime_field_label(field_id: object) -> str:
    labels = {
        "title": "标题",
        "paper_title": "标题",
        "subject": "科目",
        "grade": "年级",
        "duration": "考试时间",
        "total_score": "满分",
        "class": "班级",
        "author": "命题人",
        "date": "日期",
    }
    key = str(field_id or "").strip()
    return labels.get(key, key)


def _format_exam_score(value: object) -> str:
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "").strip()
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _exam_source_status_text(document_path: str) -> str:
    path_text = str(document_path or "").strip()
    if not path_text:
        return "待上传 Markdown 题稿"
    name = Path(path_text).name or path_text
    return f"当前试卷入口仅支持 Markdown 题稿：{name}"


def _exam_assembly_text(mode: str) -> str:
    normalized = str(mode or "").strip()
    labels = {
        "markdown_headings": "按 Markdown 标题装配",
        "numbered_questions": "按题号装配",
    }
    return labels.get(normalized, normalized or "按当前试卷配置装配")


def _exam_delivery_text(
    scene: SceneWorkspace | None,
    answer_policy: str,
) -> str:
    normalized = str(answer_policy or "").strip()
    labels = {
        "student_plus_answer": "学生卷 + 答案版",
        "student_only": "学生卷",
        "answer_only": "答案版",
    }
    if normalized in labels:
        return labels[normalized]
    presets = list(getattr(scene, "delivery_presets", []) or [])
    preset_labels = [
        str(
            getattr(preset, "label", "")
            or getattr(preset, "preset_id", "")
            or ""
        ).strip()
        for preset in presets
        if str(
            getattr(preset, "label", "")
            or getattr(preset, "preset_id", "")
            or ""
        ).strip()
    ]
    return " + ".join(preset_labels[:3]) or "按当前交付配置"


def resolve_official_document_profile_id(
    *,
    explicit_profile_id: str,
    scene: SceneWorkspace | None,
) -> str:
    # Document type belongs to the task/work-mode selection.  MaterialPackage
    # V1 removed the former scene-level material-profile back-channel, so a
    # scene must never choose a material record implicitly.
    del scene
    explicit = str(explicit_profile_id or "").strip()
    if explicit and get_official_document_profile(explicit) is not None:
        return explicit
    return "notice"


def build_official_document_readiness_projection(
    *,
    profile_id: str,
    preview_snapshot: MaterialPreviewSnapshot | None,
    plan_label: str,
    template_label: str,
    document_path: str = "",
    material_enabled: bool = True,
) -> tuple[str, dict[str, str]]:
    """Project the selected official strategy and its current readiness."""

    profile = get_official_document_profile(profile_id)
    profile_label = str(getattr(profile, "label", "") or profile_id or "通知").strip()
    contract = get_official_document_assembly_contract(profile_id)
    path_text = str(document_path or "").strip()
    if not material_enabled:
        source_name = Path(path_text).name if path_text else ""
        master_id = str(
            getattr(contract, "master_id", "") or "official_gbt_standard"
        )
        master = get_master(master_id, "official")
        master_label = str(
            getattr(master, "label", "") or master_id
        ).strip()
        mapping_summary, mapping_text = _official_source_mapping_projection(
            path_text,
            profile_id,
        )
        return (
            (
                mapping_summary
                if source_name
                else "等待公文底稿"
            ),
            {
                "source": (
                    f"保留原文校版：{source_name}"
                    if source_name
                    else "请上传需要校版的 DOCX"
                ),
                "assembly": f"{profile_label} · 套用{master_label}",
                "delivery": str(template_label or "").strip() or "GB/T 9704 公文格式",
                "fields": mapping_text,
            },
        )

    if contract is None:
        return (
            "公文执行前检查：文种契约缺失",
            {
                "source": plan_label,
                "assembly": profile_label,
                "delivery": _official_master_and_template_text("", template_label),
                "fields": "未找到当前文种的资料字段契约",
            },
        )

    required_fields = [
        str(getattr(binding, "field_key", "") or "").strip()
        for binding in contract.field_bindings
        if bool(getattr(binding, "required", False))
        and str(getattr(binding, "field_key", "") or "").strip()
    ]
    preview = (
        preview_snapshot
        if isinstance(preview_snapshot, MaterialPreviewSnapshot)
        else None
    )
    required_count = (
        preview.required_field_count
        if preview is not None
        else len(required_fields)
    )
    filled_count = (
        preview.filled_required_field_count
        if preview is not None
        else 0
    )
    missing_count = max(0, required_count - filled_count)
    summary = (
        "公文执行前检查：未选择资料包"
        if preview is None
        else (
            f"公文执行前检查：缺 {missing_count} 个必填值"
            if missing_count
            else "公文执行前检查：必填字段已齐"
        )
    )
    fields_text = (
        "请在资料区选择并确认本次运行记录"
        if preview is None
        else (
            f"当前契约需要 {required_count} 项 · "
            f"已填写 {filled_count} 项 · "
            f"资料记录 {preview.record_count} 条"
        )
    )
    return summary, {
        "source": plan_label,
        "assembly": f"{profile_label} ({profile_id})",
        "delivery": _official_master_and_template_text(
            contract.master_id,
            template_label,
        ),
        "fields": fields_text,
    }


def _official_readiness_summary(
    unmapped_fields: list[str],
    missing_fields: list[str],
) -> str:
    if unmapped_fields:
        return f"公文执行前检查：{len(unmapped_fields)} 个方案字段未绑定"
    if missing_fields:
        return f"公文执行前检查：缺 {len(missing_fields)} 个必填值"
    return "公文执行前检查：必填字段已齐"


def _official_readiness_fields_text(
    *,
    required_fields: list[str],
    mapped_fields: list[str],
    unmapped_fields: list[str],
    missing_fields: list[str],
    floating_fields: list[str],
    entity_data: dict[str, str],
) -> str:
    filled_count = len(mapped_fields) - len(missing_fields)
    text = (
        f"当前方案需要 {len(required_fields)} 项 · "
        f"已映射 {len(mapped_fields)} 项 · 已填写 {filled_count} 项"
    )
    if unmapped_fields:
        labels = [official_material_field_label(field) for field in unmapped_fields]
        text += f" · 未绑定 {len(unmapped_fields)} 项：" + "、".join(labels)
    elif missing_fields:
        labels = [official_material_field_label(field) for field in missing_fields]
        text += " · 待填写：" + "、".join(labels)
    if floating_fields:
        completed = sum(
            1
            for field in floating_fields
            if str(entity_data.get(field, "") or "").strip()
        )
        text += f" · 自由字段 {completed}/{len(floating_fields)} 已填写"
    return text


def _official_master_and_template_text(master_id: str, template_label: str) -> str:
    target = str(master_id or "").strip() or "official_gbt_standard"
    master = get_master(target, "official")
    master_label = master_display_label(master) if master is not None else target
    template_text = str(template_label or "").strip()
    if master_label and template_text:
        return f"{master_label} / {template_text}"
    return master_label or template_text or "按当前公文配置"


def _official_source_mapping_projection(
    document_path: str,
    profile_id: str,
) -> tuple[str, str]:
    roles, warnings, error = _official_source_analysis(document_path, profile_id)
    if error:
        return (
            "已有公文校版：结构识别失败",
            "未能读取段落结构；生成前请检查文档",
        )

    role_labels = {
        "organization": "发文机关",
        "document_no": "文号",
        "title": "标题",
        "recipient": "主送机关",
        "attachment_note": "附件",
        "issuer": "落款",
        "issue_date": "日期",
        "copy_scope": "抄送",
    }
    ordered_roles = (
        "organization",
        "document_no",
        "title",
        "recipient",
        "attachment_note",
        "issuer",
        "issue_date",
        "copy_scope",
    )
    present = {role.role for role in roles}
    labels = [role_labels[key] for key in ordered_roles if key in present]
    body_count = sum(role.role in {"body", "body_heading"} for role in roles)
    if body_count:
        insert_at = min(4, len(labels))
        labels.insert(insert_at, f"正文 {body_count} 段")
    fields_text = "已识别：" + "、".join(labels) if labels else "未识别到公文角色"

    warning_labels = {
        "official_source_empty": "未识别文本",
        "official_source_title_not_detected": "标题",
        "official_source_title_needs_review": "标题",
        "official_source_body_not_detected": "正文",
        "official_source_document_no_not_detected": "文号",
        "official_source_issue_date_not_detected": "日期",
    }
    review_labels = tuple(
        dict.fromkeys(warning_labels.get(warning, warning) for warning in warnings)
    )
    if review_labels:
        fields_text += "；套版提示：" + "、".join(review_labels)
        summary = f"已有公文校版：将套用母版（{len(review_labels)} 项提示）"
    else:
        summary = f"已有公文校版：已识别 {len(roles)} 个段落角色"
    return summary, fields_text


def official_source_execution_issues(
    document_path: str,
    profile_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return hard input failures and non-blocking source-mapping notices."""

    if not str(document_path or "").strip():
        return (), ()
    _roles, warnings, error = _official_source_analysis(document_path, profile_id)
    if error:
        return (("无法读取公文段落结构，请重新选择 DOCX",), ())
    warning_set = set(warnings)
    blockers: list[str] = []
    notices: list[str] = []
    if "official_source_empty" in warning_set:
        notices.append("未识别到文本段落；仍将应用所选公文母版版面")
    if "official_source_title_not_detected" in warning_set:
        notices.append("未识别到独立标题；其余内容仍按正文和落款规则套版")
    if "official_source_body_not_detected" in warning_set:
        notices.append("未识别到独立正文；已识别段落仍按对应公文角色套版")
    if "official_source_title_needs_review" in warning_set:
        notices.append("公文标题识别置信度较低，请核对识别预览")
    if "official_source_document_no_not_detected" in warning_set:
        notices.append("未识别到发文字号；无文号文种可忽略")
    if "official_source_issue_date_not_detected" in warning_set:
        notices.append("未识别到成文日期，请核对原文")
    return tuple(blockers), tuple(notices)


def official_source_execution_gate(
    material_decision: ExecutionGateDecision,
    *,
    official_scene: bool,
    material_enabled: bool,
    document_path: str,
    profile_id: str,
) -> ExecutionGateDecision:
    """Merge source-structure findings into the shared execution gate."""

    if not official_scene or material_enabled:
        return material_decision
    blockers, warnings = official_source_execution_issues(document_path, profile_id)
    return decide_execution_gate(
        blocking_reasons=(*material_decision.blocking_reasons, *blockers),
        warning_reasons=(*material_decision.warning_reasons, *warnings),
        confirmation_reasons=material_decision.confirmation_reasons,
        primary_action=material_decision.primary_action,
    )


def _official_source_analysis(document_path: str, profile_id: str):
    path = Path(str(document_path or "").strip())
    if not path.is_file():
        return (), (), "source_missing"
    try:
        stat = path.stat()
        return _cached_official_source_analysis(
            str(path.resolve()),
            int(stat.st_mtime_ns),
            int(stat.st_size),
            str(profile_id or "").strip(),
        )
    except (OSError, TypeError, ValueError):
        return (), (), "source_unreadable"


@lru_cache(maxsize=32)
def _cached_official_source_analysis(
    document_path: str,
    _modified_ns: int,
    _size: int,
    profile_id: str,
):
    try:
        roles, warnings = detect_official_source_roles(
            Document(document_path),
            document_type_id=profile_id,
        )
    except Exception:  # noqa: BLE001 - invalid DOCX must become a gate blocker
        return (), (), "source_parse_failed"
    return roles, warnings, ""


__all__ = [
    "build_exam_source_projection",
    "build_official_document_readiness_projection",
    "official_source_execution_gate",
    "official_source_execution_issues",
    "resolve_official_document_profile_id",
]
