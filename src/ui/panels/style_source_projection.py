"""Shared projection for template baseline and scene section style source."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene import SceneWorkspace
from src.config.style_difference_projection import (
    StyleDifferenceProjection,
    build_scene_style_difference_projections,
)
from src.config.template import TemplateConfig
from src.ui.panels.scene_style_override_service import scene_style_variants_for_scene


@dataclass(frozen=True)
class StyleSourceActionSpec:
    label: str
    target_card_id: str


@dataclass(frozen=True)
class StyleSourceProjection:
    template_label: str
    template_action_summary: str
    section_status_label: str
    independent_section_count: int
    independent_section_labels: tuple[str, ...]
    status_label: str
    summary: str
    primary_action: StyleSourceActionSpec
    secondary_action: StyleSourceActionSpec
    diff_tags: tuple[str, ...] = ()
    section_diff_labels: tuple[str, ...] = ()
    section_differences: tuple[StyleDifferenceProjection, ...] = ()
    template_line_prefix: str = "模板"
    section_line_prefix: str = "例外"
    view_mode: str = "scene_editable"

    @property
    def has_independent_sections(self) -> bool:
        return self.independent_section_count > 0


def build_style_source_projection(
    scene: SceneWorkspace,
    *,
    template: TemplateConfig | None = None,
    template_label: str = "",
    template_preview_action: str = "",
    template_target_card_id: str = "tpl_overview",
    section_target_card_id: str = "scn_rules",
    view_mode: str = "scene_editable",
) -> StyleSourceProjection:
    template_name = _clean_visible_text(
        str(template_label or "").strip() or _template_label_from_scene(scene)
    )
    action = _compact_template_action_summary(
        _clean_visible_text(str(template_preview_action or "").strip())
    )
    section_differences = build_scene_style_difference_projections(
        scene,
        template,
        variants=scene_style_variants_for_scene(scene, template),
        overridden_only=True,
    )
    section_labels = tuple(item.scope_label for item in section_differences)
    section_diff_labels = tuple(item.diff_tag for item in section_differences)
    mode = _normalize_view_mode(view_mode, default="scene_editable")
    section_status = _section_style_status_label(section_differences)
    status = _status_label(
        independent_section_count=len(section_labels),
        section_diff_labels=section_diff_labels,
        template_action_summary=action,
    )
    template_part = f"模板：{template_name}"
    if action:
        template_part = f"{template_part}，{action}"
    return StyleSourceProjection(
        template_label=template_name,
        template_action_summary=action,
        section_status_label=section_status,
        independent_section_count=len(section_labels),
        independent_section_labels=section_labels,
        status_label=status,
        summary=_shorten_sentence(
            f"{template_part}；例外：{section_status}",
            max_chars=108,
        ),
        primary_action=StyleSourceActionSpec("看模板", template_target_card_id),
        secondary_action=_section_action_spec(
            mode,
            independent_section_count=len(section_labels),
            section_target_card_id=section_target_card_id,
        ),
        diff_tags=section_diff_labels,
        section_diff_labels=section_diff_labels,
        section_differences=section_differences,
        view_mode=mode,
    )


def build_template_style_source_projection(
    template: TemplateConfig,
    *,
    template_label: str = "",
    target_card_id: str = "tpl_style",
) -> StyleSourceProjection:
    """Build the template-management baseline view of the shared style source row."""

    label = _clean_visible_text(
        str(template_label or "").strip()
        or str(getattr(template, "name", "") or "").strip()
        or "当前模板"
    )
    template_action = "作为样式基线"
    section_status = "默认跟随此模板"
    return StyleSourceProjection(
        template_label=label,
        template_action_summary=template_action,
        section_status_label=section_status,
        independent_section_count=0,
        independent_section_labels=(),
        status_label="模板基线",
        summary=_shorten_sentence(
            f"模板：{label}，{template_action}；场景例外：{section_status}",
            max_chars=108,
        ),
        primary_action=StyleSourceActionSpec("编辑正文", target_card_id),
        secondary_action=StyleSourceActionSpec("", ""),
        diff_tags=(),
        section_differences=(),
        template_line_prefix="模板",
        section_line_prefix="场景例外",
        view_mode="template_baseline",
    )


def _normalize_view_mode(value: str, *, default: str) -> str:
    allowed = {"scene_editable", "template_baseline", "execution_review", "readonly"}
    normalized = str(value or "").strip()
    return normalized if normalized in allowed else default


def _section_action_spec(
    view_mode: str,
    *,
    independent_section_count: int,
    section_target_card_id: str,
) -> StyleSourceActionSpec:
    if str(view_mode or "").strip() == "execution_review" and independent_section_count <= 0:
        return StyleSourceActionSpec("", "")
    return StyleSourceActionSpec("调例外", section_target_card_id)


def _section_style_status_label(items: tuple[StyleDifferenceProjection, ...]) -> str:
    if not items:
        return "无格式例外"
    visible = "、".join(item.source_line_label for item in items[:2])
    suffix = "等" if len(items) > 2 else ""
    return f"{len(items)} 个格式例外：{visible}{suffix}"


def _status_label(
    *,
    independent_section_count: int,
    section_diff_labels: tuple[str, ...] = (),
    template_action_summary: str,
) -> str:
    if independent_section_count > 0:
        if any(
            "与模板一致" not in label and "独立设置" not in label
            for label in section_diff_labels
        ):
            return "有格式例外"
        return "有格式例外"
    if template_action_summary:
        return "同源预览"
    return "跟随模板"


def _compact_template_action_summary(text: str) -> str:
    value = str(text or "").strip()
    if not value.startswith("核对"):
        return value
    target = value.removeprefix("核对").strip(" ：:，,")
    if not target:
        return value
    parts = _split_cn_list(target)
    if len(parts) < 4:
        return value
    return f"{len(parts)} 类参数可核对"


def _split_cn_list(text: str) -> tuple[str, ...]:
    normalized = str(text or "").replace(" 和 ", "和").replace(" 与 ", "和")
    pieces: list[str] = []
    for chunk in normalized.split("、"):
        subparts = chunk.split("和") if "和" in chunk else [chunk]
        for part in subparts:
            label = part.strip(" ，,；;")
            if label:
                pieces.append(label)
    return tuple(pieces)


def _template_label_from_scene(scene: SceneWorkspace) -> str:
    return (
        str(scene.template_id or scene.default_template_id or "").strip()
        or "当前模板"
    )


def _shorten_sentence(text: str, *, max_chars: int = 64) -> str:
    normalized = " ".join(str(text or "").replace(" / ", "、").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip("，；、 ") + "…"


def _clean_visible_text(text: str) -> str:
    replacements = {
        "preset_final_schema": "最终资料规则",
        "proxy": "借用样本",
        "fixture": "证据样本",
        "pack": "场景",
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
    }
    result = str(text or "").replace(" / ", "、").strip()
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = result.replace("_", " ")
    return result


__all__ = [
    "StyleSourceActionSpec",
    "StyleSourceProjection",
    "build_style_source_projection",
    "build_template_style_source_projection",
]
