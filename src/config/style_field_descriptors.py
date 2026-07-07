"""Shared paragraph style field descriptors used by template and scene UIs."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.style_variant_semantics import STYLE_VARIANTS


@dataclass(frozen=True, slots=True)
class StyleFieldDescriptor:
    """Pure identity contract for one reusable paragraph-style control."""

    field_id: str
    label: str
    control_label: str
    widget_attr: str
    group: str
    group_label: str
    group_icon: str
    layout_slot: str
    visible_in_standard_mode: bool
    visible_in_diagnostic_mode: bool
    template_path: str
    scene_editor_path: str
    control_contract_key: str = ""


@dataclass(frozen=True, slots=True)
class StyleFieldGroupDescriptor:
    """Shared layout group for paragraph-style controls."""

    group_id: str
    label: str
    icon_name: str
    mode: str = "standard"


@dataclass(frozen=True, slots=True)
class StyleFieldLayoutItem:
    """One editor layout cell, including composite controls such as emphasis."""

    item_id: str
    label: str
    field_ids: tuple[str, ...]
    group: str
    group_label: str
    group_icon: str
    layout_slot: str
    visible_in_standard_mode: bool = True
    visible_in_diagnostic_mode: bool = True


STYLE_FIELD_ALIASES: dict[str, str] = {
    "font_name": "font_cn",
    "font_cn": "font_cn",
    "font_en": "font_en",
    "size": "size_pt",
    "size_pt": "size_pt",
    "font_size": "size_pt",
    "bold": "bold",
    "italic": "italic",
    "alignment": "alignment",
    "special_indent": "special_indent",
    "special_indent_mode": "special_indent",
    "special_indent_value": "special_indent",
    "special_indent_unit": "special_indent",
    "left_indent": "left_indent",
    "left_indent_chars": "left_indent",
    "left_indent_unit": "left_indent",
    "right_indent": "right_indent",
    "right_indent_chars": "right_indent",
    "right_indent_unit": "right_indent",
    "line_spacing": "line_spacing_type",
    "line_spacing_type": "line_spacing_type",
    "line_spacing_value": "line_spacing_pt",
    "line_spacing_pt": "line_spacing_pt",
    "space_before": "space_before",
    "space_before_pt": "space_before",
    "space_before_unit": "space_before",
    "space_after": "space_after",
    "space_after_pt": "space_after",
    "space_after_unit": "space_after",
}

STYLE_FIELD_WIDGET_ATTRS: dict[str, str] = {
    "font_cn": "_font_cn",
    "font_en": "_font_en",
    "size_pt": "_size_combo",
    "bold": "_bold_switch",
    "italic": "_italic_switch",
    "alignment": "_alignment_combo",
    "special_indent": "_special_indent",
    "left_indent": "_left_indent",
    "right_indent": "_right_indent",
    "line_spacing_type": "_line_type_combo",
    "line_spacing_pt": "_line_value",
    "space_before": "_space_before",
    "space_after": "_space_after",
}

STYLE_FIELD_LABELS: dict[str, str] = {
    "font_cn": "中文字体",
    "font_en": "英文字体",
    "size_pt": "字号",
    "bold": "加粗",
    "italic": "斜体",
    "alignment": "对齐",
    "special_indent": "特殊缩进",
    "left_indent": "左缩进",
    "right_indent": "右缩进",
    "line_spacing_type": "行距类型",
    "line_spacing_pt": "行距",
    "space_before": "段前",
    "space_after": "段后",
}

STYLE_FIELD_CONTROL_LABELS: dict[str, str] = {
    **STYLE_FIELD_LABELS,
    "line_spacing_pt": "行距值",
}

STYLE_FIELD_GROUPS: dict[str, str] = {
    "font_cn": "text",
    "font_en": "text",
    "size_pt": "text",
    "bold": "text",
    "italic": "text",
    "alignment": "alignment_indent",
    "special_indent": "alignment_indent",
    "left_indent": "alignment_indent",
    "right_indent": "alignment_indent",
    "line_spacing_type": "spacing",
    "line_spacing_pt": "spacing",
    "space_before": "spacing",
    "space_after": "spacing",
}

STYLE_FIELD_GROUP_DESCRIPTORS: dict[str, StyleFieldGroupDescriptor] = {
    "text": StyleFieldGroupDescriptor("text", "文字样式", "whole-word"),
    "alignment_indent": StyleFieldGroupDescriptor(
        "alignment_indent",
        "对齐与缩进",
        "layers",
    ),
    "spacing": StyleFieldGroupDescriptor("spacing", "行距与段距", "sliders-horizontal"),
}

STYLE_FIELD_LAYOUT_SLOTS: dict[str, str] = {
    "font_cn": "text.primary.1",
    "size_pt": "text.primary.2",
    "font_en": "text.secondary.1",
    "bold": "text.secondary.2",
    "italic": "text.secondary.2",
    "alignment": "alignment_indent.primary.1",
    "special_indent": "alignment_indent.primary.2",
    "left_indent": "alignment_indent.secondary.1",
    "right_indent": "alignment_indent.secondary.2",
    "line_spacing_type": "spacing.primary.1",
    "line_spacing_pt": "spacing.primary.2",
    "space_before": "spacing.secondary.1",
    "space_after": "spacing.secondary.2",
}

STYLE_FIELD_LAYOUT_COMPOSITES: dict[str, tuple[str, tuple[str, ...], str]] = {
    "emphasis": ("字形", ("bold", "italic"), "text.secondary.2"),
}

STYLE_FIELD_LAYOUT_ITEM_IDS: tuple[str, ...] = (
    "font_cn",
    "size_pt",
    "font_en",
    "emphasis",
    "alignment",
    "special_indent",
    "left_indent",
    "right_indent",
    "line_spacing_type",
    "line_spacing_pt",
    "space_before",
    "space_after",
)

STYLE_FIELD_CONTROL_CONTRACT_IDS: dict[str, str] = {
    "font_cn": "body.font_cn",
    "font_en": "body.font_en",
    "size_pt": "body.size_pt",
    "special_indent": "body.special_indent",
    "left_indent": "body.left_indent",
    "right_indent": "body.right_indent",
    "line_spacing_type": "body.line_spacing",
    "line_spacing_pt": "body.line_spacing",
    "space_before": "body.space_before",
    "space_after": "body.space_after",
}


def canonical_paragraph_style_field_id(field_id: str) -> str:
    """Normalize owner-specific style paths to the shared editor field key."""

    target = str(field_id or "").strip()
    if not target:
        return ""

    for prefix in (
        "template.styles.body.",
        "styles.body.",
        "body.",
    ):
        if target.startswith(prefix):
            target = target[len(prefix):]
            break

    for prefix in (
        "scene.section_styles.",
        "section_styles.",
    ):
        if target.startswith(prefix):
            parts = target.split(".")
            if len(parts) >= 3:
                target = parts[-1]
            break

    if target.startswith("section_style."):
        target = target[len("section_style."):]

    if target in STYLE_FIELD_ALIASES:
        return STYLE_FIELD_ALIASES[target]

    tail = target.rsplit(".", 1)[-1]
    return STYLE_FIELD_ALIASES.get(tail, "")


def style_field_descriptor(field_id: str) -> StyleFieldDescriptor | None:
    """Return the shared descriptor for a style field or owner-specific path."""

    canonical = canonical_paragraph_style_field_id(field_id)
    if not canonical:
        return None
    widget_attr = STYLE_FIELD_WIDGET_ATTRS.get(canonical, "")
    label = STYLE_FIELD_LABELS.get(canonical, "")
    group = STYLE_FIELD_GROUPS.get(canonical, "")
    group_descriptor = STYLE_FIELD_GROUP_DESCRIPTORS.get(group)
    if not widget_attr or not label:
        return None
    return StyleFieldDescriptor(
        field_id=canonical,
        label=label,
        control_label=STYLE_FIELD_CONTROL_LABELS.get(canonical, label),
        widget_attr=widget_attr,
        group=group,
        group_label=group_descriptor.label if group_descriptor is not None else "",
        group_icon=group_descriptor.icon_name if group_descriptor is not None else "",
        layout_slot=STYLE_FIELD_LAYOUT_SLOTS.get(canonical, ""),
        visible_in_standard_mode=True,
        visible_in_diagnostic_mode=True,
        template_path=f"template.styles.body.{canonical}",
        scene_editor_path=f"section_style.{canonical}",
        control_contract_key=STYLE_FIELD_CONTROL_CONTRACT_IDS.get(canonical, ""),
    )


def style_field_label(field_id: str) -> str:
    """Return the reusable control label for a style field."""

    descriptor = style_field_descriptor(field_id)
    return descriptor.label if descriptor is not None else ""


def style_field_control_label(field_id: str) -> str:
    """Return the editor-row label for a style field control."""

    descriptor = style_field_descriptor(field_id)
    return descriptor.control_label if descriptor is not None else ""


def style_field_group_descriptor(group_id: str) -> StyleFieldGroupDescriptor | None:
    """Return the shared layout group descriptor for style controls."""

    return STYLE_FIELD_GROUP_DESCRIPTORS.get(str(group_id or "").strip())


def style_field_layout_item(item_id: str) -> StyleFieldLayoutItem | None:
    """Return a layout item for a field-backed or composite style control."""

    item = str(item_id or "").strip()
    if not item:
        return None
    if item in STYLE_FIELD_LAYOUT_COMPOSITES:
        label, field_ids, slot = STYLE_FIELD_LAYOUT_COMPOSITES[item]
        canonical_fields = tuple(
            field
            for field in (
                canonical_paragraph_style_field_id(field_id) for field_id in field_ids
            )
            if field
        )
        group = _group_from_layout_slot(slot)
        group_descriptor = STYLE_FIELD_GROUP_DESCRIPTORS.get(group)
        return StyleFieldLayoutItem(
            item_id=item,
            label=label,
            field_ids=canonical_fields,
            group=group,
            group_label=group_descriptor.label if group_descriptor is not None else "",
            group_icon=group_descriptor.icon_name if group_descriptor is not None else "",
            layout_slot=slot,
        )

    descriptor = style_field_descriptor(item)
    if descriptor is None:
        return None
    return StyleFieldLayoutItem(
        item_id=descriptor.field_id,
        label=descriptor.control_label,
        field_ids=(descriptor.field_id,),
        group=descriptor.group,
        group_label=descriptor.group_label,
        group_icon=descriptor.group_icon,
        layout_slot=descriptor.layout_slot,
        visible_in_standard_mode=descriptor.visible_in_standard_mode,
        visible_in_diagnostic_mode=descriptor.visible_in_diagnostic_mode,
    )


def style_field_layout_item_for_field(field_id: str) -> StyleFieldLayoutItem | None:
    """Return the UI layout item that owns a concrete style field."""

    canonical = canonical_paragraph_style_field_id(field_id)
    if not canonical:
        return None
    for item_id, _definition in STYLE_FIELD_LAYOUT_COMPOSITES.items():
        item = style_field_layout_item(item_id)
        if item is not None and canonical in item.field_ids:
            return item
    return style_field_layout_item(canonical)


def style_field_layout_rows(group_id: str) -> tuple[tuple[StyleFieldLayoutItem, ...], ...]:
    """Return layout rows for a style group, ordered by layout slot."""

    target_group = str(group_id or "").strip()
    if not target_group:
        return ()
    items = [
        item
        for item_id in STYLE_FIELD_LAYOUT_ITEM_IDS
        if (item := style_field_layout_item(item_id)) is not None
        and item.group == target_group
    ]
    grouped: dict[str, list[StyleFieldLayoutItem]] = {}
    for item in items:
        _group, row_key, _column = _split_layout_slot(item.layout_slot)
        grouped.setdefault(row_key, []).append(item)
    rows: list[tuple[StyleFieldLayoutItem, ...]] = []
    for row_key in sorted(grouped, key=_layout_row_rank):
        rows.append(
            tuple(sorted(grouped[row_key], key=lambda item: _layout_column_rank(item.layout_slot)))
        )
    return tuple(rows)


def style_field_widget_attr(field_id: str) -> str:
    """Return the ParagraphStyleEditor widget attribute for a field."""

    descriptor = style_field_descriptor(field_id)
    return descriptor.widget_attr if descriptor is not None else ""


def template_style_field_path(field_id: str, *, style_id: str = "body") -> str:
    """Return the normalized template style path for a field."""

    canonical = canonical_paragraph_style_field_id(field_id)
    return f"template.styles.{style_id}.{canonical}" if canonical else ""


def scene_style_field_path(variant_key: str, field_id: str) -> str:
    """Return the normalized scene section-style path for a field."""

    canonical = canonical_paragraph_style_field_id(field_id)
    variant = str(variant_key or "").strip()
    return f"scene.section_styles.{variant}.{canonical}" if variant and canonical else ""


def scene_style_navigation_target_from_field_id(field_id: str) -> tuple[str, str]:
    """Return ``(variant_key, editor_field)`` for a scene section-style path."""

    target = str(field_id or "").strip()
    if not target:
        return "", ""

    for prefix in ("scene.section_styles.", "section_styles."):
        if target.startswith(prefix):
            tail = target[len(prefix):].strip()
            variant, _separator, editor_field = tail.partition(".")
            variant_key = _scene_style_variant_key(variant)
            return (variant_key, editor_field) if variant_key else ("", "")

    for variant in STYLE_VARIANTS:
        if target == variant.key:
            return variant.key, ""
        prefix = f"{variant.key}."
        if target.startswith(prefix):
            return variant.key, target[len(prefix):]

    return "", ""


def scene_style_policy_key_from_field_id(field_id: str) -> str:
    """Return the scene section-style policy key for a navigation field path."""

    variant_key, _editor_field = scene_style_navigation_target_from_field_id(field_id)
    return variant_key


def _scene_style_variant_key(value: str) -> str:
    target = str(value or "").strip()
    if not target:
        return ""
    for variant in STYLE_VARIANTS:
        if variant.key == target:
            return target
    return ""


def _group_from_layout_slot(slot: str) -> str:
    group, _row, _column = _split_layout_slot(slot)
    return group


def _split_layout_slot(slot: str) -> tuple[str, str, str]:
    parts = [part for part in str(slot or "").split(".") if part]
    group = parts[0] if len(parts) >= 1 else ""
    row = parts[1] if len(parts) >= 2 else ""
    column = parts[2] if len(parts) >= 3 else ""
    return group, row, column


def _layout_row_rank(row_key: str) -> tuple[int, str]:
    ranks = {"primary": 0, "secondary": 1, "tertiary": 2}
    return ranks.get(str(row_key or "").strip(), 99), str(row_key or "")


def _layout_column_rank(slot: str) -> tuple[int, str]:
    _group, _row, column = _split_layout_slot(slot)
    if column.isdigit():
        return int(column), column
    return 99, column


__all__ = [
    "STYLE_FIELD_ALIASES",
    "STYLE_FIELD_CONTROL_CONTRACT_IDS",
    "STYLE_FIELD_CONTROL_LABELS",
    "STYLE_FIELD_GROUP_DESCRIPTORS",
    "STYLE_FIELD_LABELS",
    "STYLE_FIELD_LAYOUT_SLOTS",
    "STYLE_FIELD_WIDGET_ATTRS",
    "StyleFieldDescriptor",
    "StyleFieldGroupDescriptor",
    "StyleFieldLayoutItem",
    "canonical_paragraph_style_field_id",
    "scene_style_field_path",
    "scene_style_navigation_target_from_field_id",
    "scene_style_policy_key_from_field_id",
    "style_field_control_label",
    "style_field_descriptor",
    "style_field_group_descriptor",
    "style_field_label",
    "style_field_layout_item",
    "style_field_layout_item_for_field",
    "style_field_layout_rows",
    "style_field_widget_attr",
    "template_style_field_path",
]
