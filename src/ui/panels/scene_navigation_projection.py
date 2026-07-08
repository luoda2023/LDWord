"""Pure navigation projections for the scene configuration panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


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
