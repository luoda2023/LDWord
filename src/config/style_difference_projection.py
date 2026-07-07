"""Shared style-difference projection for scene sections and template baseline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.config.scene import SceneWorkspace
from src.config.style_variant_semantics import (
    STYLE_VARIANTS,
    VARIANT_KEY_TO_META,
    StyleVariantMeta,
    build_section_style_override_projection,
    is_section_style_overridden,
)
from src.config.template import TemplateConfig


@dataclass(frozen=True)
class StyleDifferenceProjection:
    variant_key: str
    scope_label: str
    section_enabled: bool
    overridden: bool
    follows_template: bool
    template_available: bool
    changed_labels: tuple[str, ...] = ()
    compact_label: str = ""
    detail_label: str = ""
    status_label: str = ""
    template_status: str = "模板基线"
    current_status: str = ""
    difference_status: str = ""
    detail: str = ""
    variant: str = "info"

    @property
    def changed_count(self) -> int:
        return len(self.changed_labels)

    @property
    def has_changed_fields(self) -> bool:
        return self.changed_count > 0

    @property
    def source_line_label(self) -> str:
        if self.detail_label and self.detail_label != "独立设置":
            return f"{self.scope_label}（{self.detail_label}）"
        return self.scope_label

    @property
    def diff_tag(self) -> str:
        if self.detail_label:
            return f"{self.scope_label}：{self.detail_label}"
        return self.scope_label


@dataclass(frozen=True)
class StyleDifferenceSummaryProjection:
    """Readable aggregate of section style differences for readonly review."""

    template_status: str = "模板基线"
    current_status: str = ""
    difference_status: str = ""
    detail: str = ""
    variant: str = "info"
    section_count: int = 0
    changed_section_count: int = 0
    pending_section_count: int = 0


def build_style_difference_projection(
    scene: SceneWorkspace,
    template: TemplateConfig | None,
    variant_key: str,
) -> StyleDifferenceProjection:
    """Compare one scene section style against its template baseline."""

    key = str(variant_key or "").strip()
    meta = _variant_meta(key)
    section_enabled = _section_enabled(scene, meta)
    overridden = is_section_style_overridden(scene, key)

    if template is None:
        return _projection_without_template(
            meta,
            section_enabled=section_enabled,
            overridden=overridden,
        )

    override = build_section_style_override_projection(scene, template, key)
    changed_labels = _clean_labels(override.changed_labels)
    follows_template = bool(section_enabled and not overridden)
    current_status, difference_status, detail = _comparison_text(
        meta,
        section_enabled=section_enabled,
        overridden=overridden,
        changed_labels=changed_labels,
    )
    detail_label = _detail_label(
        section_enabled=section_enabled,
        overridden=overridden,
        changed_labels=changed_labels,
        template_available=True,
    )
    return StyleDifferenceProjection(
        variant_key=meta.key,
        scope_label=meta.label,
        section_enabled=section_enabled,
        overridden=overridden,
        follows_template=follows_template,
        template_available=True,
        changed_labels=changed_labels,
        compact_label=_compact_label(meta.label, detail_label),
        detail_label=detail_label,
        status_label=_status_label(
            section_enabled=section_enabled,
            overridden=overridden,
            changed_labels=changed_labels,
        ),
        template_status="模板基线",
        current_status=current_status,
        difference_status=difference_status,
        detail=detail,
        variant=str(getattr(override, "variant", "") or "info"),
    )


def build_scene_style_difference_projections(
    scene: SceneWorkspace,
    template: TemplateConfig | None,
    *,
    variants: Sequence[StyleVariantMeta] = STYLE_VARIANTS,
    overridden_only: bool = False,
) -> tuple[StyleDifferenceProjection, ...]:
    projections: list[StyleDifferenceProjection] = []
    for variant in variants:
        projection = build_style_difference_projection(scene, template, variant.key)
        if overridden_only and not projection.overridden:
            continue
        projections.append(projection)
    return tuple(projections)


def build_style_difference_summary_projection(
    projections: Sequence[StyleDifferenceProjection],
    *,
    max_sections: int = 3,
) -> StyleDifferenceSummaryProjection | None:
    """Aggregate section differences into one readonly comparison summary."""

    items = tuple(item for item in projections if bool(getattr(item, "overridden", False)))
    if not items:
        return None

    if len(items) == 1:
        item = items[0]
        return StyleDifferenceSummaryProjection(
            template_status=item.template_status or "模板基线",
            current_status=_single_current_status(item),
            difference_status=item.difference_status or "-",
            detail=item.detail,
            variant=item.variant,
            section_count=1,
            changed_section_count=1 if item.has_changed_fields else 0,
            pending_section_count=1 if _is_pending_difference(item) else 0,
        )

    changed_items = tuple(item for item in items if item.has_changed_fields)
    pending_items = tuple(item for item in items if _is_pending_difference(item))
    section_count = len(items)

    if changed_items:
        return StyleDifferenceSummaryProjection(
            template_status="模板基线",
            current_status=f"{section_count} 个格式例外",
            difference_status=f"{len(changed_items)} 个格式例外已调整",
            detail="不同：" + _join_section_details(
                changed_items,
                max_sections=max_sections,
                formatter=_changed_section_detail,
            ),
            variant="warning",
            section_count=section_count,
            changed_section_count=len(changed_items),
            pending_section_count=len(pending_items),
        )

    if pending_items:
        return StyleDifferenceSummaryProjection(
            template_status="模板基线",
            current_status=f"{section_count} 个格式例外",
            difference_status="待比较",
            detail="需要模板基线后比较：" + _join_section_details(
                pending_items,
                max_sections=max_sections,
                formatter=lambda item: item.scope_label,
            ),
            variant="warning",
            section_count=section_count,
            changed_section_count=0,
            pending_section_count=len(pending_items),
        )

    return StyleDifferenceSummaryProjection(
        template_status="模板基线",
        current_status=f"{section_count} 个格式例外",
        difference_status="未改字段",
        detail=f"{section_count} 个格式例外字段仍与模板一致。",
        variant="info",
        section_count=section_count,
        changed_section_count=0,
        pending_section_count=0,
    )


def compact_changed_labels(labels: Sequence[str], *, max_items: int = 2) -> str:
    cleaned = _clean_labels(labels)
    if not cleaned:
        return ""
    visible = "、".join(cleaned[:max_items])
    suffix = "等" if len(cleaned) > max_items else ""
    return f"{visible}{suffix}"


def _projection_without_template(
    meta: StyleVariantMeta,
    *,
    section_enabled: bool,
    overridden: bool,
) -> StyleDifferenceProjection:
    if not section_enabled:
        current_status = "未处理"
        difference_status = "待比较"
        detail = f"「{meta.label}」暂不可比较。"
        detail_label = "未处理"
        status_label = "未处理"
        variant = "warning"
    elif overridden:
        current_status = "独立样式"
        difference_status = "待比较"
        detail = "需要模板基线后比较字段差异。"
        detail_label = "独立设置"
        status_label = "有独立样式"
        variant = "warning"
    else:
        current_status = "跟随模板"
        difference_status = "待比较"
        detail = "需要模板基线后确认字段差异。"
        detail_label = ""
        status_label = "跟随模板"
        variant = "info"

    return StyleDifferenceProjection(
        variant_key=meta.key,
        scope_label=meta.label,
        section_enabled=section_enabled,
        overridden=overridden,
        follows_template=bool(section_enabled and not overridden),
        template_available=False,
        changed_labels=(),
        compact_label=_compact_label(meta.label, detail_label),
        detail_label=detail_label,
        status_label=status_label,
        template_status="模板基线",
        current_status=current_status,
        difference_status=difference_status,
        detail=detail,
        variant=variant,
    )


def _comparison_text(
    meta: StyleVariantMeta,
    *,
    section_enabled: bool,
    overridden: bool,
    changed_labels: tuple[str, ...],
) -> tuple[str, str, str]:
    if not section_enabled:
        return "未处理", "未比较", f"「{meta.label}」暂不可比较。"
    if not overridden:
        return "跟随模板", "无差异", "当前分区直接使用模板基线。"
    if not changed_labels:
        return "独立样式", "未改字段", "已独立，但字段仍与模板一致。"
    return (
        "独立样式",
        f"已调整 {len(changed_labels)} 项",
        "不同：" + "、".join(changed_labels),
    )


def _detail_label(
    *,
    section_enabled: bool,
    overridden: bool,
    changed_labels: tuple[str, ...],
    template_available: bool,
) -> str:
    if not section_enabled:
        return "未处理"
    if not overridden:
        return ""
    if not template_available:
        return "独立设置"
    if not changed_labels:
        return "与模板一致"
    return compact_changed_labels(changed_labels)


def _status_label(
    *,
    section_enabled: bool,
    overridden: bool,
    changed_labels: tuple[str, ...],
) -> str:
    if not section_enabled:
        return "未处理"
    if changed_labels:
        return "有格式例外"
    if overridden:
        return "有独立样式"
    return "跟随模板"


def _compact_label(scope_label: str, detail_label: str) -> str:
    label = str(scope_label or "").strip() or "分区"
    detail = str(detail_label or "").strip()
    if detail and detail != "独立设置":
        return f"{label}（{detail}）"
    return label


def _clean_labels(labels: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(label or "").strip() for label in labels if str(label or "").strip())


def _single_current_status(item: StyleDifferenceProjection) -> str:
    scope = str(item.scope_label or "").strip()
    status = str(item.current_status or "").strip()
    if scope and status:
        return f"{scope} {status}"
    return status or scope


def _is_pending_difference(item: StyleDifferenceProjection) -> bool:
    return not item.template_available or item.difference_status == "待比较"


def _changed_section_detail(item: StyleDifferenceProjection) -> str:
    changed = compact_changed_labels(item.changed_labels)
    if changed:
        return f"{item.scope_label}改了{changed}"
    return item.diff_tag


def _join_section_details(
    items: Sequence[StyleDifferenceProjection],
    *,
    max_sections: int,
    formatter,
) -> str:
    limit = max(1, int(max_sections or 1))
    visible = [str(formatter(item) or "").strip() for item in tuple(items)[:limit]]
    visible = [text for text in visible if text]
    suffix = "" if len(items) <= limit else f"等 {len(items)} 个格式例外"
    return "；".join(visible + ([suffix] if suffix else []))


def _section_enabled(scene: SceneWorkspace, meta: StyleVariantMeta) -> bool:
    return scene is not None and meta is not None


def _variant_meta(variant_key: str) -> StyleVariantMeta:
    return VARIANT_KEY_TO_META.get(
        variant_key,
        StyleVariantMeta(
            key=variant_key,
            section_type=variant_key,
            label=variant_key or "分区",
            description="",
        ),
    )


__all__ = [
    "StyleDifferenceProjection",
    "StyleDifferenceSummaryProjection",
    "build_scene_style_difference_projections",
    "build_style_difference_projection",
    "build_style_difference_summary_projection",
    "compact_changed_labels",
]
