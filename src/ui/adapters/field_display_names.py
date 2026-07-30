from __future__ import annotations

from dataclasses import dataclass
import re

from src.config.style_field_descriptors import (
    style_field_descriptor,
    style_field_label,
    style_field_layout_item_for_field,
)

SECTION_LABELS: dict[str, str] = {
    "abstracts": "摘要",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
    "toc": "目录",
    "body": "正文",
    "references": "参考文献",
    "acknowledgment": "致谢",
    "appendix": "附录",
    "resume": "个人简历",
    "tables": "表格",
    "figures": "图片",
}

PAGE_FIELD_LABELS: dict[str, str] = {
    "paper_size": "纸张",
    "orientation": "方向",
    "section_break_type": "分节方式",
    "top_cm": "上页边距",
    "bottom_cm": "下页边距",
    "left_cm": "左页边距",
    "right_cm": "右页边距",
    "gutter_cm": "装订线",
    "header_distance_cm": "页眉距离",
    "footer_distance_cm": "页脚距离",
}

INPUT_SOURCE_FIELD_LABELS: dict[str, str] = {
    "schema": "主资料规则",
    "schema_id": "主资料规则",
    "material_schema": "主资料规则",
    "accepted_formats": "输入格式",
    "structured_formats": "结构化格式",
    "markdown_policy": "Markdown 处理",
    "latex_policy": "公式处理",
    "require_material_package": "资料包要求",
    "material_schema_id": "主资料规则",
    "material_schema_ids": "资料规则列表",
    "required_material_fields": "必填资料字段",
    "required_image_roles": "必填图片角色",
    "failure_policy": "缺资料处理",
}

MATERIAL_FIELD_LABELS: dict[str, str] = {
    "company_name": "公司名称",
    "project_name": "项目名称",
    "legal_person": "法定代表人",
    "credit_code": "统一社会信用代码",
    "phone": "联系电话",
    "bid_date": "投标日期",
    "compile_date": "编制日期",
    "logo": "企业标志",
    "seal": "公章图片",
}

OUTPUT_FIELD_LABELS: dict[str, str] = {
    "default_delivery": "默认交付方案",
    "preset_id": "交付编号",
    "preset_label": "交付名称",
    "label": "交付名称",
    "target_template": "目标模板",
    "target_template_id": "目标模板",
    "template_options": "可选模板",
    "output_dir": "输出目录",
    "output_dir_template": "输出目录规则",
    "filename": "文件名",
    "filename_template": "文件名规则",
    "visibility_selector": "内容可见规则",
    "visibility_rules": "内容可见规则",
    "final_docx": "终稿 Word",
    "compare_docx": "对照 Word",
    "report_json": "JSON 报告",
    "report_markdown": "Markdown 报告",
    "report_md": "Markdown 报告",
    "material_manifest": "资料清单",
    "material_package": "资料包",
}

_FIELD_KEY_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_/\\#])"
    r"([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_*]+)+)"
    r"(?![A-Za-z0-9_/\\#])"
)


@dataclass(frozen=True, slots=True)
class FieldDisplayContext:
    """User-facing field name plus optional style control identity."""

    label: str = ""
    group_label: str = ""
    raw_key: str = ""
    layout_item_id: str = ""
    field_ids: tuple[str, ...] = ()
    control_contract_key: str = ""

    def label_with_group(self) -> str:
        if self.group_label and self.label:
            return f"{self.group_label}：{self.label}"
        return self.label or self.group_label

    def diagnostic_summary(self) -> str:
        parts = []
        if self.raw_key:
            parts.append(self.raw_key)
        if self.layout_item_id:
            parts.append(f"布局项：{self.layout_item_id}")
        if self.control_contract_key:
            parts.append(f"控件契约：{self.control_contract_key}")
        return " / ".join(parts)


def field_display_name(value: str, *, target_type: str = "") -> str:
    """Return a concise user-facing name for a routable field or parameter key."""

    key = str(value or "").strip()
    if not key:
        return ""
    normalized_type = str(target_type or "").strip()
    if normalized_type in {"schema", "material_schema"}:
        known = _input_source_label(key)
        return known or f"资料规则：{key}"
    known = _input_source_label(key)
    if known:
        return known
    known = _scene_document_scope_label(key)
    if known:
        return known
    known = _template_style_label(key)
    if known:
        return known
    known = _template_page_label(key)
    if known:
        return known
    if key in MATERIAL_FIELD_LABELS:
        return MATERIAL_FIELD_LABELS[key]
    if key in OUTPUT_FIELD_LABELS:
        return OUTPUT_FIELD_LABELS[key]
    known = style_field_label(key)
    if known:
        return _style_field_display_label(key, known)
    return key


def field_display_context(value: str, *, target_type: str = "") -> FieldDisplayContext:
    """Return readable text plus diagnostic style-control identity for a field path."""

    key = str(value or "").strip()
    label = field_display_name(key, target_type=target_type)
    layout_item = style_field_layout_item_for_field(key)
    group_label = layout_item.group_label if layout_item is not None else ""
    field_ids = layout_item.field_ids if layout_item is not None else ()
    descriptor = style_field_descriptor(key)
    control_contract_key = (
        descriptor.control_contract_key if descriptor is not None else ""
    )
    if not control_contract_key:
        for field_id in field_ids:
            descriptor = style_field_descriptor(field_id)
            if descriptor is not None and descriptor.control_contract_key:
                control_contract_key = descriptor.control_contract_key
                break
    return FieldDisplayContext(
        label=label,
        group_label=group_label,
        raw_key=key,
        layout_item_id=layout_item.item_id if layout_item is not None else "",
        field_ids=field_ids,
        control_contract_key=control_contract_key,
    )


def replace_field_keys_with_display_names(
    text: str,
    *,
    include_raw_key: bool = True,
) -> str:
    """Replace routable field keys embedded in display copy with readable names."""

    value = str(text or "")
    if not value:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        display = field_display_name(key)
        if not display or display == key:
            return key
        if include_raw_key:
            return f"{display}（{key}）"
        return display

    return _FIELD_KEY_TOKEN_RE.sub(_replace, value)


def navigation_issue_hint(
    issue_title: str,
    issue_key: str,
    *,
    issue_type: str = "",
) -> str:
    """Return the label shown when entering another panel from an issue."""

    title = str(issue_title or "").strip()
    if title:
        return title
    return field_display_name(issue_key, target_type=issue_type)


def _template_style_label(key: str) -> str:
    target = _strip_prefix(key, "template.styles.")
    target = _strip_prefix(target, "styles.")
    if target == key and "." not in key:
        return ""
    parts = [part for part in target.split(".") if part]
    if len(parts) < 2:
        return ""
    style_key, field_key = parts[0], parts[-1]
    field_label = _style_field_display_label(field_key, style_field_label(field_key))
    if not field_label:
        return ""
    return f"{_style_label(style_key)}{field_label}"


def _scene_document_scope_label(key: str) -> str:
    if key == "scene.document_scope.mode":
        return "处理范围"
    if key == "scene.document_scope.selected_roles":
        return "指定区域"
    return ""


def _template_page_label(key: str) -> str:
    target = _strip_prefix(key, "template.page_setup.")
    target = _strip_prefix(target, "page_setup.")
    target = _strip_prefix(target, "template.section.")
    if target == key:
        return ""
    parts = [part for part in target.split(".") if part]
    if not parts:
        return ""
    field_key = parts[-1]
    return PAGE_FIELD_LABELS.get(field_key, "")


def _input_source_label(key: str) -> str:
    target = _strip_prefix(key, "scene.input_source_profile.")
    target = _strip_prefix(target, "input_source_profile.")
    if target == key:
        target = key
    return INPUT_SOURCE_FIELD_LABELS.get(target, "")


def _style_field_display_label(key: str, label: str) -> str:
    if not label:
        return ""
    if key in {"line_spacing_type", "line_spacing_value", "line_spacing_pt"}:
        return "行距"
    layout_item = style_field_layout_item_for_field(key)
    if layout_item is not None and len(layout_item.field_ids) > 1:
        return layout_item.label
    return label


def _style_label(style_key: str) -> str:
    if style_key == "body":
        return "正文"
    if style_key.startswith("heading"):
        suffix = style_key.removeprefix("heading")
        return f"{suffix}级标题" if suffix.isdigit() else "标题"
    if style_key.startswith("toc_level"):
        suffix = style_key.removeprefix("toc_level")
        return f"{suffix}级目录" if suffix.isdigit() else "目录"
    labels = {
        "toc": "目录",
        "toc_title": "目录标题",
        "caption": "题注",
        "table": "表格",
        "references": "参考文献",
        "references_body": "参考文献正文",
        "abstract_body": "摘要正文",
        "appendix_body": "附录正文",
        "acknowledgment_body": "致谢正文",
        "resume_body": "个人简历正文",
    }
    return labels.get(style_key, style_key)


def _strip_prefix(value: str, prefix: str) -> str:
    return value[len(prefix) :] if value.startswith(prefix) else value


__all__ = [
    "FieldDisplayContext",
    "field_display_context",
    "field_display_name",
    "navigation_issue_hint",
    "replace_field_keys_with_display_names",
]
