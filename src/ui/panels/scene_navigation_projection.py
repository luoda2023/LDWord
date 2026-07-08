"""Pure navigation projections for the scene configuration panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.config.delivery_preset_display import DELIVERY_PRESET_DISPLAY_LABELS
from src.shared.engine.exam_paper_style import exam_blank_style_label
from src.ui.panels.scene_material_requirement_block import _profile_material_schema_ids
from src.ui.panels.scene_style_override_service import (
    scene_style_variants_for_scene,
    scene_uses_reference_format,
)
from src.ui.panels.scene_summary_projection import (
    FAILURE_POLICY_LABELS,
    FORMAT_DISPLAY_LABELS,
    scene_application_boundary_display_name,
)


SCENE_RULES_ALIAS_CARDS = frozenset(
    (
        "scn_scope",
        "scn_style_rules",
        "scn_reference",
        "scn_output",
    )
)

NAV_SCOPE_MODE_LABELS = {
    "follow_template": "按模板默认",
    "body_only": "只处理正文",
    "full_document": "处理全文",
    "confirm_before_apply": "每次执行前选择",
}

NAV_OUTPUT_FIELDS = (
    "final_docx",
    "compare_docx",
    "report_json",
    "report_markdown",
    "material_manifest",
    "material_package",
)


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
    current_template=None,
    delivery_preset=None,
    exam_paper_config=None,
) -> dict[str, dict[str, str]]:
    return {
        "scn_overview": overview_navigation_snapshot(
            scene_label=scene_label,
            template_label=template_label,
            scene_dirty=scene_dirty,
        ),
        "scn_exam_paper": exam_paper_navigation_snapshot(exam_paper_config),
        "scn_rules": rules_navigation_snapshot(
            scene,
            current_template=current_template,
            delivery_preset=delivery_preset,
        ),
        "scn_content": content_navigation_snapshot(scene),
    }


def overview_navigation_snapshot(
    *,
    scene_label: str,
    template_label: str,
    scene_dirty: bool,
) -> dict[str, str]:
    return {
        "subtitle": f"{scene_label} · {template_label}",
        "badge_text": "未保存" if scene_dirty else "场景",
        "badge_variant": "warning" if scene_dirty else "success",
    }


def rules_navigation_snapshot(
    scene,
    *,
    current_template=None,
    delivery_preset=None,
) -> dict[str, str]:
    boundary_mode = getattr(scene.application_boundary, "mode", "follow_template")
    override_count = style_override_count(scene, current_template)
    has_style_rules = bool(scene_style_variants_for_scene(scene, current_template))
    style_summary = (
        f"{override_count} 个格式例外"
        if override_count
        else ("无格式例外" if has_style_rules else "")
    )
    return {
        "subtitle": _nav_join(
            (
                _nav_scope_subtitle(boundary_mode),
                style_summary,
                output_result_nav_summary(scene, delivery_preset),
                "参考文献规则" if scene_uses_reference_format(scene) else "",
            )
        ),
        "badge_text": scene_application_boundary_display_name(scene),
        "badge_variant": (
            "warning" if boundary_mode == "confirm_before_apply" else "success"
        ),
    }


def output_result_nav_summary(scene, delivery_preset=None) -> str:
    output_count = sum(
        1 for field_name in NAV_OUTPUT_FIELDS if bool(getattr(scene.output, field_name, False))
    )
    preset_label = _delivery_preset_label(delivery_preset)
    return f"{preset_label} {output_count} 项产物" if output_count else "未配置产物"


def style_override_count(scene, current_template=None) -> int:
    visible_keys = {
        variant.key for variant in scene_style_variants_for_scene(scene, current_template)
    }
    return sum(
        1
        for key, value in scene.section_styles.items()
        if key in visible_keys and value is not None
    )


def style_rules_navigation_snapshot(scene, *, current_template=None) -> dict[str, str]:
    override_count = style_override_count(scene, current_template)
    if override_count:
        return {
            "subtitle": f"{override_count} 个格式例外 · 可恢复模板",
            "badge_text": f"{override_count} 项",
            "badge_variant": "info",
        }
    return {
        "subtitle": "跟随模板 · 无格式例外",
        "badge_text": "模板",
        "badge_variant": "neutral",
    }


def reference_navigation_snapshot(scene) -> dict[str, str]:
    ref = scene.reference_style
    mode = "独立条目样式" if scene.section_styles.get("references_body") is not None else "跟随正文"
    return {
        "subtitle": (
            f"{mode} · 悬挂缩进 {ref.hanging_indent_cm:g}cm · "
            f"段后 {ref.space_after_pt:g}{getattr(ref, 'space_after_unit', 'pt')}"
        ),
        "badge_text": "论文",
        "badge_variant": "info",
    }


def exam_paper_navigation_snapshot(exam_paper_config) -> dict[str, str]:
    blank = exam_blank_style_label(
        getattr(exam_paper_config, "blank_style_id", ""),
        exam_paper_config,
    )
    return {
        "subtitle": f"{blank} · 试卷母版",
        "badge_text": "试卷",
        "badge_variant": "info",
    }


def cleanup_navigation_snapshot(scene) -> dict[str, str]:
    profile = scene.compliance_profile
    preflight = profile.object_preflight
    checks = len(profile.enabled_checks or [])
    scan_targets = len(preflight.scan_targets or [])
    enabled = bool(preflight.enabled or checks)
    return {
        "subtitle": _nav_join(
            (
                f"检查 {checks} 项",
                f"扫描目标 {scan_targets} 个",
                FAILURE_POLICY_LABELS.get(profile.failure_policy, profile.failure_policy),
            )
        ),
        "badge_text": "已开启" if enabled else "未开启",
        "badge_variant": "success" if enabled else "neutral",
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
    output_count = sum(
        1 for field_name in NAV_OUTPUT_FIELDS if bool(getattr(scene.output, field_name, False))
    )
    preset_label = _delivery_preset_label(delivery_preset)
    return {
        "subtitle": f"{preset_label} · {output_count} 项产物",
        "badge_text": f"{output_count} 项",
        "badge_variant": "success" if output_count else "warning",
    }


def default_delivery_preset(scene):
    target_id = str(getattr(scene, "default_delivery_preset_id", "") or "").strip()
    for preset in scene.delivery_presets or []:
        if str(getattr(preset, "preset_id", "") or "").strip() == target_id:
            return preset
    return (scene.delivery_presets or [None])[0]


def _delivery_preset_label(delivery_preset) -> str:
    preset_label = str(
        getattr(delivery_preset, "label", "")
        or DELIVERY_PRESET_DISPLAY_LABELS.get(
            str(getattr(delivery_preset, "preset_id", "") or "").strip(),
            "",
        )
        or getattr(delivery_preset, "preset_id", "")
        or "默认交付"
    )
    return _nav_display_id(preset_label, DELIVERY_PRESET_DISPLAY_LABELS)
