"""Delivery and style-source report sections."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from src.reporting.common import _clean_text


def _normalize_delivery_preset_context(
    value: Mapping[str, object] | None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    preset_id = _clean_text(value.get("preset_id", ""))
    raw_label = _clean_text(value.get("label", ""))
    display_label = (
        _clean_text(value.get("display_label", ""))
        or raw_label
        or preset_id
    )
    if not any((preset_id, raw_label, display_label)):
        return {}
    return {
        "preset_id": preset_id,
        "label": raw_label,
        "display_label": display_label,
        "target_template_id": _clean_text(value.get("target_template_id", "")),
        "report_level": _clean_text(value.get("report_level", "")),
    }


def _format_delivery_preset_markdown(
    delivery_preset: Mapping[str, object],
    *,
    output_path: Path | None,
) -> list[str]:
    display_label = _clean_text(delivery_preset.get("display_label", ""))
    preset_id = _clean_text(delivery_preset.get("preset_id", ""))
    raw_label = _clean_text(delivery_preset.get("label", ""))
    target_template_id = _clean_text(delivery_preset.get("target_template_id", ""))
    report_level = _clean_text(delivery_preset.get("report_level", ""))
    lines = ["## 交付", ""]
    if display_label:
        lines.append(f"- 版本: **{display_label}**")
    if output_path is not None:
        lines.append(f"- 输出文件: {output_path}")
    if preset_id:
        lines.append(f"- 版本 ID: `{preset_id}`")
    if raw_label and raw_label != display_label:
        lines.append(f"- 原始标签: {raw_label}")
    if target_template_id:
        lines.append(f"- 目标模板: {target_template_id}")
    if report_level:
        lines.append(f"- 报告级别: {report_level}")
    lines.append("")
    return lines

def _normalize_style_source_summary(
    value: Mapping[str, object] | None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    template_label = _clean_text(value.get("template_label", ""))
    summary = _clean_text(value.get("summary", ""))
    if not template_label and not summary:
        return {}
    return {
        "template_label": template_label,
        "summary": summary,
    }


def _format_style_source_markdown(style_source: Mapping[str, object]) -> list[str]:
    summary = _clean_text(style_source.get("summary", ""))
    template_label = _clean_text(style_source.get("template_label", ""))
    lines = ["## 样式来源", ""]
    if summary:
        lines.append(f"- 摘要: {summary}")
    if template_label:
        lines.append(f"- 模板: {template_label}")
    lines.append("")
    return lines
