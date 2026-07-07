"""Style variant helpers — manage section-specific style overrides.

Core rule: "key exists in styles → independent; key absent → inherits body".

This module provides the single source of truth for which style keys
are section variants and how to query / toggle their override state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.config.section_semantics import SECTION_STYLE_KEY_MAP
from src.config.style_semantics import (
    normalize_line_spacing_type,
    resolve_line_spacing_value,
    resolve_spacing_render_pt,
)
from src.config.template import StyleConfig, TemplateConfig


@dataclass(frozen=True)
class StyleVariantMeta:
    """Metadata for a section-specific paragraph style variant."""

    key: str              # e.g. "references_body"
    section_type: str     # e.g. "references"
    label: str            # UI display name, e.g. "参考文献"
    description: str      # tooltip / help text


@dataclass(frozen=True)
class SectionStyleOverrideProjection:
    """User-facing state for one scene section style override."""

    variant_key: str
    section_type: str
    label: str
    section_enabled: bool
    overridden: bool
    changed_labels: tuple[str, ...] = ()
    status_value: str = ""
    status_detail: str = ""
    editor_hint: str = ""
    variant: str = "info"

    @property
    def changed_count(self) -> int:
        return len(self.changed_labels)

    @property
    def editable(self) -> bool:
        return self.section_enabled and self.overridden


@dataclass(frozen=True)
class SectionStylePreviewProjection:
    """Lightweight paragraph preview data for one scene section style."""

    variant_key: str
    label: str
    sample_text: str
    source_label: str
    detail: str
    font_cn: str
    font_en: str
    size_pt: float
    bold: bool
    italic: bool
    alignment: str
    line_spacing_type: str
    line_spacing_value: float
    left_indent_pt: float
    right_indent_pt: float
    first_indent_pt: float
    hanging_indent_pt: float
    space_before_pt: float
    space_after_pt: float


@dataclass(frozen=True)
class SectionStyleComparisonProjection:
    """Compact comparison between the template baseline and current section style."""

    variant_key: str
    label: str
    template_status: str
    current_status: str
    difference_status: str
    detail: str = ""
    variant: str = "info"


STYLE_VARIANTS: tuple[StyleVariantMeta, ...] = (
    StyleVariantMeta(
        key="references_body",
        section_type="references",
        label="参考文献",
        description="参考文献段落的字体、字号、缩进和行距。",
    ),
    StyleVariantMeta(
        key="acknowledgment_body",
        section_type="acknowledgment",
        label="致谢",
        description="致谢段落的排版样式。",
    ),
    StyleVariantMeta(
        key="abstract_body",
        section_type="abstract_cn",
        label="摘要",
        description="中英文摘要段落的排版样式。",
    ),
    StyleVariantMeta(
        key="appendix_body",
        section_type="appendix",
        label="附录",
        description="附录段落的排版样式。",
    ),
    StyleVariantMeta(
        key="resume_body",
        section_type="resume",
        label="个人简历",
        description="个人简历段落的排版样式。",
    ),
)

VARIANT_KEY_TO_META: dict[str, StyleVariantMeta] = {
    v.key: v for v in STYLE_VARIANTS
}


def get_effective_style(template: TemplateConfig, variant_key: str) -> StyleConfig:
    """Return the effective StyleConfig for *variant_key*.

    If the variant has an independent override, return it.
    Otherwise fall back to ``styles["body"]`` (or a fresh default).
    """
    override = template.styles.get(variant_key)
    if override is not None:
        return override

    body = template.styles.get("body")
    if body is not None:
        return body

    return template.styles.get("normal") or StyleConfig()


def is_variant_overridden(template: TemplateConfig, variant_key: str) -> bool:
    """Return ``True`` when the variant has its own independent style."""
    return variant_key in template.styles


def enable_variant_override(template: TemplateConfig, variant_key: str) -> StyleConfig:
    """Create an independent style for *variant_key* (deep-copied from body).

    Returns the newly created ``StyleConfig`` so the caller can bind UI to it.
    """
    if variant_key in template.styles:
        return template.styles[variant_key]

    body = get_effective_style(template, "body")
    independent = deepcopy(body)
    template.styles[variant_key] = independent
    return independent


def disable_variant_override(template: TemplateConfig, variant_key: str) -> None:
    """Remove the independent style, making the variant inherit from body."""
    template.styles.pop(variant_key, None)


# ---------------------------------------------------------------------------
# Scene-aware variant API (section_styles lives in SceneWorkspace)
# ---------------------------------------------------------------------------

def get_effective_section_style(
    scene, template: TemplateConfig, variant_key: str,
):
    """Return effective StyleConfig: scene override → template body → default."""
    from src.config.scene import SceneWorkspace
    if isinstance(scene, SceneWorkspace) and variant_key in scene.section_styles:
        return scene.section_styles[variant_key]
    return get_effective_style(template, variant_key)


def is_section_style_overridden(scene, variant_key: str) -> bool:
    """Check if the scene has an independent style for this variant."""
    return variant_key in getattr(scene, "section_styles", {})


def enable_section_style_override(scene, template: TemplateConfig, variant_key: str):
    """Create an independent section style from the template effective baseline."""
    if variant_key in scene.section_styles:
        return scene.section_styles[variant_key]
    baseline = get_effective_style(template, variant_key)
    independent = deepcopy(baseline)
    scene.section_styles[variant_key] = independent
    return independent


def disable_section_style_override(scene, variant_key: str) -> None:
    """Remove the independent section style, reverting to body."""
    if hasattr(scene, "section_styles"):
        scene.section_styles.pop(variant_key, None)


def build_section_style_override_projection(
    scene,
    template: TemplateConfig,
    variant_key: str,
) -> SectionStyleOverrideProjection:
    """Return user-facing override state for scene style controls."""

    meta = VARIANT_KEY_TO_META.get(
        variant_key,
        StyleVariantMeta(
            key=variant_key,
            section_type=variant_key,
            label=variant_key or "分区",
            description="",
        ),
    )
    section_enabled = True
    section_styles = getattr(scene, "section_styles", {}) or {}
    overridden = variant_key in section_styles
    baseline = get_effective_style(template, variant_key)
    override = section_styles.get(variant_key)
    changed_labels = (
        _style_changed_labels(baseline, override) if overridden and override is not None else ()
    )

    if not section_enabled:
        status_value = "未处理"
        status_detail = f"先启用「{meta.label}」。"
        editor_hint = status_detail
        variant = "warning"
    elif not overridden:
        status_value = "跟随模板"
        status_detail = "使用模板样式。"
        editor_hint = "跟随模板 · 开启独立样式后可编辑"
        variant = "info"
    elif not changed_labels:
        status_value = "已开启独立样式"
        status_detail = "与模板一致。"
        editor_hint = "已开启独立样式 · 与模板一致"
        variant = "warning"
    else:
        status_value = f"已调整 {len(changed_labels)} 项"
        status_detail = "不同：" + "、".join(changed_labels)
        editor_hint = f"正在编辑 · {status_detail}"
        variant = "success"

    return SectionStyleOverrideProjection(
        variant_key=meta.key,
        section_type=meta.section_type,
        label=meta.label,
        section_enabled=section_enabled,
        overridden=overridden,
        changed_labels=changed_labels,
        status_value=status_value,
        status_detail=status_detail,
        editor_hint=editor_hint,
        variant=variant,
    )


def build_section_style_preview_projection(
    scene,
    template: TemplateConfig,
    variant_key: str,
) -> SectionStylePreviewProjection:
    """Return a compact preview projection for the scene's effective style."""

    override_projection = build_section_style_override_projection(
        scene,
        template,
        variant_key,
    )
    style = get_effective_section_style(scene, template, variant_key)
    size_pt = _style_float(getattr(style, "size_pt", 12), default=12.0)
    line_spacing_type = normalize_line_spacing_type(
        getattr(style, "line_spacing_type", "exact")
    )
    line_spacing_value = resolve_line_spacing_value(
        line_spacing_type,
        getattr(style, "line_spacing_pt", 0),
    )
    from src.shared.engine.indent_ops import resolve_style_config_indents

    indents = resolve_style_config_indents(style, size_pt=size_pt)
    line_height_pt = (
        line_spacing_value
        if line_spacing_type == "exact"
        else size_pt * max(0.1, line_spacing_value)
    )
    return SectionStylePreviewProjection(
        variant_key=override_projection.variant_key,
        label=override_projection.label,
        sample_text=(
            f"{override_projection.label}样式预览："
            "中文、English、数字 123 与括号（示例）。"
        ),
        source_label=override_projection.status_value,
        detail=override_projection.status_detail,
        font_cn=str(getattr(style, "font_cn", "") or ""),
        font_en=str(getattr(style, "font_en", "") or ""),
        size_pt=size_pt,
        bold=bool(getattr(style, "bold", False)),
        italic=bool(getattr(style, "italic", False)),
        alignment=str(getattr(style, "alignment", "justify") or "justify"),
        line_spacing_type=line_spacing_type,
        line_spacing_value=line_spacing_value,
        left_indent_pt=_style_float(
            indents.get("effective_left_pt", 0.0),
            default=0.0,
        ),
        right_indent_pt=_style_float(indents.get("right_pt", 0.0), default=0.0),
        first_indent_pt=_style_float(indents.get("first_pt", 0.0), default=0.0),
        hanging_indent_pt=_style_float(indents.get("hanging_pt", 0.0), default=0.0),
        space_before_pt=resolve_spacing_render_pt(
            getattr(style, "space_before_pt", 0.0),
            getattr(style, "space_before_unit", "pt"),
            line_height_pt=line_height_pt,
        ),
        space_after_pt=resolve_spacing_render_pt(
            getattr(style, "space_after_pt", 0.0),
            getattr(style, "space_after_unit", "pt"),
            line_height_pt=line_height_pt,
        ),
    )


def build_section_style_comparison_projection(
    scene,
    template: TemplateConfig,
    variant_key: str,
) -> SectionStyleComparisonProjection:
    """Return a short user-facing template/current/diff comparison."""

    projection = build_section_style_override_projection(scene, template, variant_key)
    if not projection.section_enabled:
        current_status = "未处理"
        difference_status = "未比较"
        detail = f"「{projection.label}」暂不可比较。"
    elif not projection.overridden:
        current_status = "跟随模板"
        difference_status = "无差异"
        detail = "当前分区直接使用模板基线。"
    elif not projection.changed_labels:
        current_status = "独立样式"
        difference_status = "未改字段"
        detail = "已独立，但字段仍与模板一致。"
    else:
        current_status = "独立样式"
        difference_status = f"已调整 {len(projection.changed_labels)} 项"
        detail = "不同：" + "、".join(projection.changed_labels)

    return SectionStyleComparisonProjection(
        variant_key=projection.variant_key,
        label=projection.label,
        template_status="模板基线",
        current_status=current_status,
        difference_status=difference_status,
        detail=detail,
        variant=projection.variant,
    )


STYLE_OVERRIDE_DIFF_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("中文字体", ("font_cn",)),
    ("英文字体", ("font_en",)),
    ("字号", ("size_pt",)),
    ("字形", ("bold", "italic")),
    ("对齐", ("alignment",)),
    (
        "特殊缩进",
        (
            "first_line_indent_chars",
            "first_line_indent_unit",
            "hanging_indent_chars",
            "hanging_indent_unit",
            "special_indent_mode",
            "special_indent_value",
            "special_indent_unit",
        ),
    ),
    ("左缩进", ("left_indent_chars", "left_indent_unit")),
    ("右缩进", ("right_indent_chars", "right_indent_unit")),
    ("行距", ("line_spacing_type", "line_spacing_pt")),
    ("段前", ("space_before_pt", "space_before_unit")),
    ("段后", ("space_after_pt", "space_after_unit")),
)


def _style_changed_labels(
    baseline: StyleConfig,
    override: StyleConfig,
) -> tuple[str, ...]:
    labels: list[str] = []
    for label, fields in STYLE_OVERRIDE_DIFF_GROUPS:
        if any(
            not _style_values_equal(
                getattr(baseline, field_name, None),
                getattr(override, field_name, None),
            )
            for field_name in fields
        ):
            labels.append(label)
    return tuple(labels)


def _style_values_equal(left, right) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 0.0001
    return left == right


def _style_float(value, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


__all__ = [
    "SectionStyleOverrideProjection",
    "SectionStyleComparisonProjection",
    "SectionStylePreviewProjection",
    "StyleVariantMeta",
    "STYLE_VARIANTS",
    "VARIANT_KEY_TO_META",
    "STYLE_OVERRIDE_DIFF_GROUPS",
    "get_effective_style",
    "is_variant_overridden",
    "enable_variant_override",
    "disable_variant_override",
    "get_effective_section_style",
    "is_section_style_overridden",
    "enable_section_style_override",
    "disable_section_style_override",
    "build_section_style_override_projection",
    "build_section_style_comparison_projection",
    "build_section_style_preview_projection",
]
