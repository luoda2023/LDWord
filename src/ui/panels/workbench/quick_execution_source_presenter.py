"""Source and readiness projections for the quick-execution surface."""

from __future__ import annotations

from pathlib import Path

from src.config.master_library import get_master
from src.config.material_context import MaterialExecutionContext
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
from src.ui.adapters.config_selector_models import master_display_label


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
    explicit = str(explicit_profile_id or "").strip()
    if explicit and get_official_document_profile(explicit) is not None:
        return explicit
    scene_profile = str(
        getattr(scene, "default_material_profile_id", "") or ""
    ).strip()
    if ":" in scene_profile:
        _prefix, scene_profile = scene_profile.split(":", 1)
    scene_profile = scene_profile.strip()
    if scene_profile and get_official_document_profile(scene_profile) is not None:
        return scene_profile
    return "notice"


def build_official_document_readiness_projection(
    *,
    profile_id: str,
    material_context: MaterialExecutionContext,
    plan_label: str,
    template_label: str,
) -> tuple[str, dict[str, str]]:
    """Project the selected official contract and current material readiness."""

    profile = get_official_document_profile(profile_id)
    contract = get_official_document_assembly_contract(profile_id)
    profile_label = str(getattr(profile, "label", "") or profile_id or "通知").strip()
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
    entity_data = material_context.resolved_entity_data()
    field_scopes = dict(getattr(material_context, "field_scopes", {}) or {})
    active_token_keys = {
        key for key, scope in field_scopes.items() if scope in {"fixed", "floating"}
    }
    mapped_fields = [field for field in required_fields if field in active_token_keys]
    unmapped_fields = [field for field in required_fields if field not in active_token_keys]
    missing_fields = [
        field
        for field in mapped_fields
        if not str(entity_data.get(field, "") or "").strip()
    ]
    floating_fields = [
        key for key, scope in field_scopes.items() if scope == "floating"
    ]
    return _official_readiness_summary(unmapped_fields, missing_fields), {
        "source": plan_label,
        "assembly": f"{profile_label} ({profile_id})",
        "delivery": _official_master_and_template_text(
            contract.master_id,
            template_label,
        ),
        "fields": _official_readiness_fields_text(
            required_fields=required_fields,
            mapped_fields=mapped_fields,
            unmapped_fields=unmapped_fields,
            missing_fields=missing_fields,
            floating_fields=floating_fields,
            entity_data=entity_data,
        ),
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


__all__ = [
    "build_exam_source_projection",
    "build_official_document_readiness_projection",
    "resolve_official_document_profile_id",
]
