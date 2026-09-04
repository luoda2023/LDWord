"""Pure navigation projections for the scene configuration panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.config.default_delivery_identity import project_default_delivery_identity
from src.config.delivery_preset_display import DELIVERY_PRESET_DISPLAY_LABELS
from src.config.master_library import default_master
from src.shared.engine.exam_paper_style import exam_blank_style_label
from src.ui.adapters.config_selector_models import master_display_label, plan_display_label
from src.ui.panels.scene_material_requirement_block import _profile_material_schema_ids
from src.config.scene_surface_registry import (
    scene_uses_exam_paper_surface,
    scene_uses_official_document_surface,
    scene_uses_plan_preview_surface,
)
from src.ui.panels.scene_product_summary_projection import (
    FORMAT_DISPLAY_LABELS,
    scene_document_scope_display_name,
)


SCENE_RULES_ALIAS_CARDS = frozenset(
    (
        "scn_scope",
        "scn_output",
        # Compatibility only: old repair links now land on the plan rules
        # page.  There is no visible risk/cleanup navigation card.
        "scn_cleanup",
    )
)

NAV_SCOPE_MODE_LABELS = {
    "all": "全部内容",
    "body": "仅正文",
    "selected": "自选区域",
}

NAV_OUTPUT_FIELDS = (
    "final_docx",
    "review_pdf",
    "compare_docx",
    "report_json",
    "report_markdown",
    "material_manifest",
    "material_package",
)


def template_navigation_context_payload(preview_context) -> dict[str, object]:
    return {
        "entry_context_title": preview_context.title,
        "entry_context_detail": preview_context.detail,
        "entry_context_action": preview_context.action,
        "template_preview_groups": preview_context.detail_card_ids,
        "template_preview_coverage": preview_context.coverage_labels,
    }


def scene_display_label(scene, descriptors) -> str:
    scene_id = str(getattr(scene, "scene_id", "") or "").strip()
    for descriptor in descriptors:
        if descriptor.config_id == scene_id:
            return plan_display_label(descriptor)
    return str(getattr(scene, "name", "") or "").strip() or scene_id or "当前方案"


def _normalise_scene_detail_card_id(card_id: str) -> str:
    normalized = str(card_id or "").strip()
    return "scn_rules" if normalized in SCENE_RULES_ALIAS_CARDS else normalized


def _nav_display_id(value: object, mapping: Mapping[str, str] | None = None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if mapping and normalized in mapping:
        return mapping[normalized]
    return normalized.replace("_", " ")


def _nav_join(parts: Sequence[str]) -> str:
    return " · ".join(part for part in parts if str(part or "").strip())


def _nav_scope_subtitle(mode: str) -> str:
    return NAV_SCOPE_MODE_LABELS.get(mode, mode or "按模板默认")


def _nav_format_summary(
    values: Sequence[object],
    format_display_labels: Mapping[str, str],
) -> str:
    labels = [_nav_display_id(value, format_display_labels) for value in values]
    labels = [label for label in labels if label]
    if not labels:
        return "Word 文档"
    if len(labels) <= 2:
        return "、".join(labels)
    return "、".join(labels[:2]) + f"等 {len(labels)} 种输入"


def build_scene_navigation_card_snapshots(
    scene,
    *,
    scene_label: str,
    template_label: str,
    scene_dirty: bool,
    scene_save_state: str = "",
    current_template=None,
    delivery_preset=None,
    exam_paper_config=None,
) -> dict[str, dict[str, str]]:
    return {
        "scn_overview": overview_navigation_snapshot(
            scene_label=scene_label,
            template_label=template_label,
            scene_dirty=scene_dirty,
            scene_save_state=scene_save_state,
        ),
        "scn_exam_paper": plan_preview_navigation_snapshot(scene, exam_paper_config),
        "scn_rules": rules_navigation_snapshot(
            scene,
            current_template=current_template,
            delivery_preset=delivery_preset,
        ),
        "scn_formula": formula_navigation_snapshot(scene),
        "scn_chem_typography": chem_typography_navigation_snapshot(scene),
        "scn_content": content_navigation_snapshot(scene),
    }


def formula_navigation_snapshot(scene) -> dict[str, str]:
    rules = getattr(scene, "thesis_formula_rules", None)
    enabled = bool(rules is not None and getattr(rules, "formula_enabled", False))
    if rules is None:
        return {
            "subtitle": "仅用于论文方案",
            "badge_text": "不可用",
            "badge_variant": "neutral",
        }
    workflow_count = sum(
        1
        for child in (
            rules.formula_convert,
            rules.formula_to_table,
            rules.equation_numbering,
            rules.formula_style,
        )
        if bool(getattr(child, "enabled", False))
    )
    output_label = (
        {
            "word_native": "Word 原生公式",
            "latex": "LaTeX 逻辑",
            "keep_source": "保留原文",
        }.get(str(rules.formula_convert.output_mode or ""), "公式策略")
        if bool(rules.formula_convert.enabled)
        else "不转换"
    )
    if not enabled:
        badge_text, badge_variant = "已关闭", "neutral"
    elif not workflow_count:
        badge_text, badge_variant = "待配置", "warning"
    else:
        badge_text, badge_variant = "已启用", "success"
    return {
        "subtitle": f"{output_label} · {workflow_count} 项处理",
        "badge_text": badge_text,
        "badge_variant": badge_variant,
    }


def chem_typography_navigation_snapshot(scene) -> dict[str, str]:
    rules = getattr(scene, "thesis_formula_rules", None)
    if rules is None:
        return {
            "subtitle": "仅用于论文方案",
            "badge_text": "不可用",
            "badge_variant": "neutral",
        }
    chem = rules.chem_typography
    enabled = bool(chem.enabled)
    scope_count = sum(1 for active in (chem.scopes or {}).values() if bool(active))
    if not enabled:
        badge_text, badge_variant = "已关闭", "neutral"
    elif not scope_count:
        badge_text, badge_variant = "待配置", "warning"
    else:
        badge_text, badge_variant = "已启用", "success"
    return {
        "subtitle": f"{scope_count} 个范围 · {chem.western_font or 'Times New Roman'}",
        "badge_text": badge_text,
        "badge_variant": badge_variant,
    }


def overview_navigation_snapshot(
    *,
    scene_label: str,
    template_label: str,
    scene_dirty: bool,
    scene_save_state: str = "",
) -> dict[str, str]:
    state = str(scene_save_state or "").strip()
    if not state:
        state = "pending" if scene_dirty else "saved"
    badge_by_state = {
        "pending": ("待自动保存", "neutral"),
        "saving": ("保存中", "neutral"),
        "failed": ("保存失败", "warning"),
        "saved": ("已保存", "success"),
    }
    badge_text, badge_variant = badge_by_state.get(
        state,
        badge_by_state["pending" if scene_dirty else "saved"],
    )
    return {
        "subtitle": f"{scene_label} · {template_label}",
        "badge_text": badge_text,
        "badge_variant": badge_variant,
    }


def rules_navigation_snapshot(
    scene,
    *,
    current_template=None,
    delivery_preset=None,
) -> dict[str, str]:
    scope_mode = getattr(scene.document_scope, "mode", "all")
    uses_master_assembly = scene_uses_plan_preview_surface(scene)
    return {
        "subtitle": _nav_join(
            (
                "" if uses_master_assembly else _nav_scope_subtitle(scope_mode),
                output_result_nav_summary(scene, delivery_preset),
            )
        ),
        "badge_text": (
            "生成结果"
            if uses_master_assembly
            else scene_document_scope_display_name(scene)
        ),
        "badge_variant": "success",
    }


def output_result_nav_summary(scene, delivery_preset=None) -> str:
    identity = (
        project_default_delivery_identity(scene)
        if delivery_preset is None
        else None
    )
    if identity is not None:
        delivery_preset = identity.preset
        if identity.status == "invalid":
            return f"无效引用：{identity.requested_id} · 未配置产物"
        if identity.status == "missing":
            return "未设置默认交付 · 未配置产物"
    artifacts = getattr(delivery_preset, "artifacts", None)
    output_count = sum(
        1
        for field_name in NAV_OUTPUT_FIELDS
        if bool(getattr(artifacts, field_name, False))
    )
    preset_label = _delivery_preset_label(delivery_preset)
    return f"{preset_label} {output_count} 项产物" if output_count else "未配置产物"


def exam_paper_navigation_snapshot(scene, exam_paper_config) -> dict[str, str]:
    blank = exam_blank_style_label(
        getattr(scene, "master_id", ""),
        exam_paper_config,
    )
    return {
        "subtitle": f"{blank} · 当前方案",
        "badge_text": "卷面",
        "badge_variant": "info",
    }


def plan_preview_navigation_snapshot(scene, exam_paper_config) -> dict[str, str]:
    if scene_uses_exam_paper_surface(scene):
        return exam_paper_navigation_snapshot(scene, exam_paper_config)
    if scene_uses_official_document_surface(scene):
        return official_document_navigation_snapshot(scene)
    return {
        "subtitle": "按当前方案预览装配入口",
        "badge_text": "方案",
        "badge_variant": "neutral",
    }


def official_document_navigation_snapshot(scene) -> dict[str, str]:
    master = default_master("official")
    master_label = master_display_label(master) if master is not None else "未登记公文版式"
    profile = getattr(scene, "input_source_profile", None)
    schema_ids = _profile_material_schema_ids(profile) if profile is not None else ()
    schema_text = "、".join(schema_ids) if schema_ids else "official_document_v1"
    return {
        "subtitle": f"{master_label} 路 {schema_text}",
        "badge_text": "公文版式",
        "badge_variant": "info" if master is not None else "warning",
    }


def content_navigation_snapshot(scene) -> dict[str, str]:
    profile = scene.input_source_profile
    formats = _nav_format_summary(tuple(profile.accepted_formats or ()), FORMAT_DISPLAY_LABELS)
    material_fields = len(profile.required_material_fields or [])
    schema_count = len(_profile_material_schema_ids(profile))
    configured = bool(
        profile.require_material_package
        or material_fields
        or schema_count
        or profile.material_schema_id
    )
    return {
        "subtitle": _nav_join(
            (
                formats,
                f"资料字段 {material_fields} 个",
                f"资料规则 {schema_count} 项",
            )
        ),
        "badge_text": "已配置" if configured else "未开启",
        "badge_variant": "success" if configured else "neutral",
    }


def output_navigation_snapshot(scene, delivery_preset=None) -> dict[str, str]:
    identity = (
        project_default_delivery_identity(scene)
        if delivery_preset is None
        else None
    )
    if identity is not None:
        delivery_preset = identity.preset
        if identity.status == "invalid":
            return {
                "subtitle": f"无效引用：{identity.requested_id} · 0 项产物",
                "badge_text": "引用无效",
                "badge_variant": "warning",
            }
    artifacts = getattr(delivery_preset, "artifacts", None)
    output_count = sum(
        1
        for field_name in NAV_OUTPUT_FIELDS
        if bool(getattr(artifacts, field_name, False))
    )
    preset_label = _delivery_preset_label(delivery_preset)
    return {
        "subtitle": f"{preset_label} · {output_count} 项产物",
        "badge_text": f"{output_count} 项",
        "badge_variant": "success" if output_count else "warning",
    }


def default_delivery_preset(scene):
    return project_default_delivery_identity(scene).preset


def _delivery_preset_label(delivery_preset) -> str:
    preset_label = str(
        getattr(delivery_preset, "label", "")
        or DELIVERY_PRESET_DISPLAY_LABELS.get(
            str(getattr(delivery_preset, "preset_id", "") or "").strip(),
            "",
        )
        or getattr(delivery_preset, "preset_id", "")
        or "未设置"
    )
    return _nav_display_id(preset_label, DELIVERY_PRESET_DISPLAY_LABELS)
