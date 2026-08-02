"""
page_setup — 页面设置模块

设置纸张大小、页边距、装订线、页眉页脚距离。
不处理页眉页脚内容格式（那属于 header_footer 模块）。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from docx.enum.section import WD_ORIENT
from docx.shared import Cm

from src.config.template import SectionMarginConfig
from src.modules.base import BaseModule, Issue, ModuleMeta
from src.shared.engine.ooxml_ops import find, qn
from src.shared.engine.section_layout_planner import (
    collect_section_inventory,
    iter_active_sections,
)

if TYPE_CHECKING:
    from docx import Document

    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── 纸张尺寸 (cm) ────────────────────────────────

PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "LETTER": (21.59, 27.94),
    "LEGAL": (21.59, 35.56),
    "16K": (18.4, 26.0),
}


def _section_has_explicit_orientation(section) -> bool:
    """Check whether a section's XML has an explicit w:orient attribute."""
    sect_pr = section._sectPr
    pg_sz = find(sect_pr, "w:pgSz")
    if pg_sz is None:
        return False
    return pg_sz.get(qn("w:orient")) is not None


class PageSetupModule(BaseModule):
    """页面设置模块。

    职责：纸张大小 + 页边距 + 装订线 + 页眉页脚距离
    不职责：页眉页脚内容格式（→ header_footer 模块）
    """

    meta = ModuleMeta(
        name="page_setup",
        description="页面设置",
        category="basic",
        requires_config=("page_setup",),
        soft_after=("section_format",),
    )

    def validate(self, doc, config, context) -> list[Issue]:
        ps = config.page_setup
        issues: list[Issue] = []
        modes: dict[str, str] = {}
        for field_name, default_value, allowed in (
            (
                "paper_size_mode",
                "force_template",
                {"preserve_source", "force_template", "per_section"},
            ),
            (
                "orientation_mode",
                "preserve_source",
                {"preserve_source", "force_template", "per_section"},
            ),
            (
                "margin_mode",
                "force_template",
                {"preserve_source", "force_template", "per_section"},
            ),
        ):
            value = str(getattr(ps, field_name, default_value) or default_value)
            modes[field_name] = value
            if value not in allowed:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=f"unsupported {field_name}: {value}",
                        location=f"page_setup.{field_name}",
                    )
                )
        paper_overrides = dict(getattr(ps, "paper_size_by_section", {}) or {})
        orientation_overrides = dict(getattr(ps, "orientation_by_section", {}) or {})
        margin_overrides = dict(getattr(ps, "margin_by_section", {}) or {})
        for key, value in paper_overrides.items():
            if str(value or "").strip().upper() not in PAPER_SIZES:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=f"unsupported per-section paper size: {value}",
                        location=f"page_setup.paper_size_by_section.{key}",
                    )
                )
        for key, value in orientation_overrides.items():
            if str(value) not in {"portrait", "landscape"}:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=f"unsupported per-section orientation: {value}",
                        location=f"page_setup.orientation_by_section.{key}",
                    )
                )
        for key, value in margin_overrides.items():
            invalid_field = _invalid_margin_override_field(value)
            if invalid_field:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=(
                            "per-section margin values must be finite and non-negative: "
                            f"{invalid_field}"
                        ),
                        location=f"page_setup.margin_by_section.{key}.{invalid_field}",
                    )
                )

        sections = iter_active_sections(doc)
        starts = _section_start_indices(doc, len(sections))
        valid_keys = _valid_section_override_keys(context, starts, len(sections))
        override_specs = (
            ("paper_size_mode", "paper_size_by_section", paper_overrides, "paper size"),
            (
                "orientation_mode",
                "orientation_by_section",
                orientation_overrides,
                "orientation",
            ),
            ("margin_mode", "margin_by_section", margin_overrides, "margin"),
        )
        for mode_name, mapping_name, mapping, label in override_specs:
            if modes.get(mode_name) != "per_section":
                continue
            if not mapping:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=(
                            f"per_section {label} requires at least one section or role override"
                        ),
                        location=f"page_setup.{mapping_name}",
                    )
                )
            for key in mapping:
                if str(key) not in valid_keys:
                    issues.append(
                        Issue(
                            level="error",
                            module_name=self.meta.name,
                            message=(
                                f"per-section {label} key does not match any section or role: {key}"
                            ),
                            location=f"page_setup.{mapping_name}.{key}",
                        )
                    )

        paper_mode = modes.get("paper_size_mode", "force_template")
        orientation_mode = modes.get("orientation_mode", "preserve_source")
        active_sections = iter_active_sections(doc)
        inventory = collect_section_inventory(doc)
        section_starts = _section_start_indices(doc, len(active_sections))
        for index, section in enumerate(active_sections):
            boundary = inventory.boundaries[index]
            protected_reason = _page_layout_mutation_block_reason(boundary)
            paper_key, paper_owned = _desired_paper_key(
                ps,
                context,
                section_index=index,
                start_index=section_starts[index],
                paper_mode=paper_mode,
            )
            source_landscape = _section_is_landscape(
                section,
                getattr(ps, "orientation", "portrait") == "landscape",
            )
            desired_landscape, orientation_owned = _desired_landscape(
                ps,
                context,
                section_index=index,
                start_index=section_starts[index],
                source_landscape=source_landscape,
                template_landscape=getattr(ps, "orientation", "portrait") == "landscape",
                orientation_mode=orientation_mode,
            )
            margin_config, margin_owned = _desired_margin_config(
                ps,
                context,
                section_index=index,
                start_index=section_starts[index],
                margin_mode=modes.get("margin_mode", "force_template"),
            )
            policy_would_write = (
                paper_owned or margin_owned or orientation_owned
            )
            if protected_reason and policy_would_write:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=(
                            "受保护分节不能安全改写页面属性："
                            f"{protected_reason}"
                        ),
                        location=f"Section {index + 1}",
                    )
                )
            geometry_error = _target_content_geometry_error(
                section,
                paper_key=paper_key if paper_owned else "",
                landscape=desired_landscape,
                margin_config=margin_config if margin_owned else None,
            )
            if geometry_error:
                issues.append(
                    Issue(
                        level="error",
                        module_name=self.meta.name,
                        message=geometry_error,
                        location=f"Section {index + 1}",
                    )
                )
            contradiction = _section_orientation_contradiction(section)
            if not contradiction:
                continue
            can_repair = (
                paper_owned or orientation_owned
            )
            issues.append(
                Issue(
                    level="warning" if can_repair else "error",
                    module_name=self.meta.name,
                    message=(
                        "section page geometry conflicts with explicit w:orient; "
                        + ("the selected policy will normalize it" if can_repair else "preserve policies cannot emit a coherent result")
                    ),
                    location=f"Section {index + 1}",
                )
            )
        return issues

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        ps = config.page_setup

        paper_mode = str(getattr(ps, "paper_size_mode", "force_template") or "force_template")
        orientation_mode = str(
            getattr(ps, "orientation_mode", "preserve_source") or "preserve_source"
        )
        margin_mode = str(getattr(ps, "margin_mode", "force_template") or "force_template")
        template_landscape = getattr(ps, "orientation", "portrait") == "landscape"
        context.page_setup_source_inventory = collect_section_inventory(doc)
        sections = iter_active_sections(doc)
        boundaries = context.page_setup_source_inventory.boundaries
        section_starts = _section_start_indices(doc, len(sections))

        for idx, section in enumerate(sections):
            if _page_layout_mutation_block_reason(boundaries[idx]):
                continue
            before = _section_geometry_tuple(section)
            source_landscape = _section_is_landscape(section, template_landscape)
            desired_landscape, orientation_owned = _desired_landscape(
                ps,
                context,
                section_index=idx,
                start_index=section_starts[idx],
                source_landscape=source_landscape,
                template_landscape=template_landscape,
                orientation_mode=orientation_mode,
            )
            paper_key, paper_owned = _desired_paper_key(
                ps,
                context,
                section_index=idx,
                start_index=section_starts[idx],
                paper_mode=paper_mode,
            )
            margin_config, margin_owned = _desired_margin_config(
                ps,
                context,
                section_index=idx,
                start_index=section_starts[idx],
                margin_mode=margin_mode,
            )

            if paper_owned:
                paper_w, paper_h = PAPER_SIZES[paper_key]
                if desired_landscape:
                    section.page_width = Cm(paper_h)
                    section.page_height = Cm(paper_w)
                else:
                    section.page_width = Cm(paper_w)
                    section.page_height = Cm(paper_h)
            elif orientation_owned and desired_landscape != source_landscape:
                width, height = section.page_width, section.page_height
                section.page_width, section.page_height = height, width

            if orientation_owned or paper_owned:
                section.orientation = (
                    WD_ORIENT.LANDSCAPE if desired_landscape else WD_ORIENT.PORTRAIT
                )

            if margin_owned:
                section.top_margin = Cm(margin_config.top_cm)
                section.bottom_margin = Cm(margin_config.bottom_cm)
                section.left_margin = Cm(margin_config.left_cm)
                section.right_margin = Cm(margin_config.right_cm)
                section.gutter = Cm(margin_config.gutter_cm)
                section.header_distance = Cm(margin_config.header_distance_cm)
                section.footer_distance = Cm(margin_config.footer_distance_cm)

            after = _section_geometry_tuple(section)
            if before != after:
                tracker.record(
                    rule_name=self.meta.name,
                    target=f"Section {idx + 1}",
                    section="global",
                    change_type="format",
                    before=_format_geometry(before),
                    after=(
                        f"paper_mode={paper_mode}, orientation_mode={orientation_mode}, "
                        f"margin_mode={margin_mode}, paper={paper_key if paper_owned else 'preserved'}; "
                        f"{_format_geometry(after)}"
                    ),
                )
        context.page_setup_final_inventory = collect_section_inventory(doc)
        context.final_section_inventory = context.page_setup_final_inventory


def _section_is_landscape(section, fallback: bool) -> bool:
    if _section_has_explicit_orientation(section):
        return section.orientation == WD_ORIENT.LANDSCAPE
    if section.page_width is not None and section.page_height is not None:
        return section.page_width > section.page_height
    return fallback


def _desired_landscape(
    page_setup,
    context,
    *,
    section_index: int,
    start_index: int,
    source_landscape: bool,
    template_landscape: bool,
    orientation_mode: str,
) -> tuple[bool, bool]:
    if orientation_mode == "force_template":
        return template_landscape, True
    if orientation_mode != "per_section":
        return source_landscape, False

    overrides = dict(getattr(page_setup, "orientation_by_section", {}) or {})
    role = _section_role(context, start_index)
    value = overrides.get(str(section_index + 1))
    if value is None and role:
        value = overrides.get(role)
    if value in {"portrait", "landscape"}:
        return value == "landscape", True
    return source_landscape, False


def _desired_paper_key(
    page_setup,
    context,
    *,
    section_index: int,
    start_index: int,
    paper_mode: str,
) -> tuple[str, bool]:
    if paper_mode == "force_template":
        key = str(getattr(page_setup, "paper_size", "A4") or "A4").strip().upper()
        return (key if key in PAPER_SIZES else "A4"), True
    if paper_mode != "per_section":
        return "", False
    value = _section_override_value(
        getattr(page_setup, "paper_size_by_section", {}) or {},
        context,
        section_index=section_index,
        start_index=start_index,
    )
    key = str(value or "").strip().upper()
    return (key, True) if key in PAPER_SIZES else ("", False)


def _desired_margin_config(
    page_setup,
    context,
    *,
    section_index: int,
    start_index: int,
    margin_mode: str,
) -> tuple[SectionMarginConfig | None, bool]:
    if margin_mode == "force_template":
        return (
            SectionMarginConfig(
                top_cm=page_setup.margin.top_cm,
                bottom_cm=page_setup.margin.bottom_cm,
                left_cm=page_setup.margin.left_cm,
                right_cm=page_setup.margin.right_cm,
                gutter_cm=page_setup.gutter_cm,
                header_distance_cm=page_setup.header_distance_cm,
                footer_distance_cm=page_setup.footer_distance_cm,
            ),
            True,
        )
    if margin_mode != "per_section":
        return None, False
    value = _section_override_value(
        getattr(page_setup, "margin_by_section", {}) or {},
        context,
        section_index=section_index,
        start_index=start_index,
    )
    if isinstance(value, SectionMarginConfig):
        return value, True
    if isinstance(value, dict):
        try:
            return SectionMarginConfig(**value), True
        except (TypeError, ValueError):
            return None, False
    return None, False


def _section_override_value(
    mapping,
    context,
    *,
    section_index: int,
    start_index: int,
):
    values = dict(mapping or {})
    ordinal_key = str(section_index + 1)
    if ordinal_key in values:
        return values[ordinal_key]
    role = _section_role(context, start_index)
    return values.get(role) if role else None


def _valid_section_override_keys(
    context,
    starts: list[int],
    section_count: int,
) -> set[str]:
    keys = {str(index + 1) for index in range(section_count)}
    keys.update(
        role
        for role in (
            _section_role(context, start_index)
            for start_index in starts
            if start_index >= 0
        )
        if role
    )
    return keys


def _invalid_margin_override_field(value) -> str:
    fields = (
        "top_cm",
        "bottom_cm",
        "left_cm",
        "right_cm",
        "gutter_cm",
        "header_distance_cm",
        "footer_distance_cm",
    )
    for field_name in fields:
        raw = value.get(field_name) if isinstance(value, dict) else getattr(value, field_name, None)
        if isinstance(raw, bool):
            return field_name
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            return field_name
        if not math.isfinite(numeric) or numeric < 0:
            return field_name
    return ""


def _target_content_geometry_error(
    section,
    *,
    paper_key: str,
    landscape: bool,
    margin_config: SectionMarginConfig | None,
) -> str:
    if paper_key:
        paper_width, paper_height = PAPER_SIZES[paper_key]
        width_cm, height_cm = (
            (paper_height, paper_width)
            if landscape
            else (paper_width, paper_height)
        )
    elif section.page_width is not None and section.page_height is not None:
        width_cm = float(section.page_width.cm)
        height_cm = float(section.page_height.cm)
        if (width_cm > height_cm) != landscape:
            width_cm, height_cm = height_cm, width_cm
    else:
        return ""

    if margin_config is None:
        lengths = (
            section.top_margin,
            section.bottom_margin,
            section.left_margin,
            section.right_margin,
            section.gutter,
        )
        if any(value is None for value in lengths):
            return ""
        top, bottom, left, right, gutter = (
            float(value.cm) for value in lengths
        )
    else:
        top = float(margin_config.top_cm)
        bottom = float(margin_config.bottom_cm)
        left = float(margin_config.left_cm)
        right = float(margin_config.right_cm)
        gutter = float(margin_config.gutter_cm)
    if width_cm - left - right - gutter <= 0 or height_cm - top - bottom <= 0:
        return "per-section paper and margin policy would produce a non-positive text area"
    return ""


def _section_start_indices(doc, section_count: int) -> list[int]:
    starts = [0]
    inventory = collect_section_inventory(doc)
    for boundary in inventory.boundaries[:-1]:
        starts.append(
            boundary.paragraph_index + 1
            if boundary.paragraph_index is not None
            else -1
        )
    starts = starts[:section_count]
    if len(starts) < section_count:
        starts.extend([starts[-1] if starts else 0] * (section_count - len(starts)))
    return starts


def _section_role(context, paragraph_index: int) -> str:
    if paragraph_index < 0:
        return ""
    tree = getattr(context, "doc_tree", None)
    getter = getattr(tree, "get_section_for_paragraph", None)
    if callable(getter):
        value = getter(paragraph_index)
        if isinstance(value, str):
            return value
        return str(getattr(value, "section_type", "") or "")
    for section in list(getattr(tree, "sections", []) or []):
        if int(getattr(section, "start_index", -1)) <= paragraph_index < int(
            getattr(section, "end_index", -1)
        ):
            return str(getattr(section, "section_type", "") or "")
    return ""


def _section_orientation_contradiction(section) -> bool:
    if not _section_has_explicit_orientation(section):
        return False
    if section.page_width is None or section.page_height is None:
        return False
    geometry_landscape = section.page_width > section.page_height
    explicit_landscape = section.orientation == WD_ORIENT.LANDSCAPE
    return geometry_landscape != explicit_landscape


def _page_layout_mutation_block_reason(boundary) -> str:
    protected_markup = set(getattr(boundary, "protected_markup", ()) or ())
    if "sectPrChange" in protected_markup:
        return "section properties contain tracked sectPrChange markup"
    if str(getattr(boundary, "anchor_kind", "")) == "nested_paragraph":
        containers = ", ".join(sorted(protected_markup)) or "nested container"
        return f"section boundary is nested inside protected content: {containers}"
    return ""


def _section_geometry_tuple(section) -> tuple:
    return (
        section.page_width,
        section.page_height,
        section.top_margin,
        section.bottom_margin,
        section.left_margin,
        section.right_margin,
        section.gutter,
        section.header_distance,
        section.footer_distance,
        section.orientation,
    )


def _format_geometry(values: tuple) -> str:
    return (
        f"width={values[0]}, height={values[1]}, "
        f"margins={values[2:6]}, orient={values[9]}"
    )

