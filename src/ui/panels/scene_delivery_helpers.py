"""Delivery preset helpers for the scene panel."""

from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from string import Formatter

from src.config.delivery_preset_display import delivery_preset_display_name
from src.config.feature_configs import OutputConfig
from src.config.library import get_template_entry
from src.config.work_mode import work_mode_for_scene_id
from src.config.scene import ContentVisibilityRule, SceneWorkspace
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    has_planned_scene_family_application,
)
from src.qt_api import Qt
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.adapters.content_visibility_display import (
    COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS,
    content_visibility_selector_display,
    content_visibility_selector_label,
    content_visibility_selector_tooltip,
)
from src.ui.panels.scene_product_summary_projection import FAMILY_DISPLAY_LABELS


def _format_visibility_rules(rules) -> str:
    lines: list[str] = []
    for rule in list(rules or []):
        selector = str(getattr(rule, "selector", "") or "").strip()
        if not selector:
            continue
        action = str(getattr(rule, "action", "") or "remove").strip() or "remove"
        lines.append(f"{selector}={action}")
    return "\n".join(lines)


def _parse_visibility_rules(text: str) -> list[ContentVisibilityRule]:
    rules: list[ContentVisibilityRule] = []
    seen: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        selector, action = _split_visibility_rule_line(line)
        selector = selector.strip()
        action = _normalize_visibility_action(action)
        if not selector:
            continue
        key = selector.lower()
        if key in seen:
            continue
        seen.add(key)
        rules.append(
            ContentVisibilityRule(
                rule_id=f"hide_{key}",
                label=content_visibility_selector_label(selector),
                selector_type="marker_block",
                selector=selector,
                action=action,
            )
        )
    return rules


def _split_visibility_rule_line(line: str) -> tuple[str, str]:
    for separator in ("=", ":"):
        if separator in line:
            left, right = line.split(separator, 1)
            return left, right
    return line, "remove"


def _normalize_visibility_action(value: str) -> str:
    normalized = str(value or "remove").strip().lower()
    return normalized


_DELIVERY_TEMPLATE_VARIABLES = (
    "document_dir",
    "output_dir",
    "stem",
    "suffix",
    "preset_id",
    "preset_label",
)
_DELIVERY_TEMPLATE_VARIABLE_LABELS: dict[str, tuple[str, str]] = {
    "document_dir": ("原文所在文件夹", "原始文档所在目录，适合用作输出根目录"),
    "output_dir": ("本次输出文件夹", "程序实际生成结果的目录"),
    "stem": ("原文件名", "不带扩展名的原始文件名"),
    "suffix": ("原扩展名", "原始文件的扩展名，例如 .docx"),
    "preset_id": ("交付编号", "当前交付版本的内部编号"),
    "preset_label": ("交付名称", "当前交付版本显示给用户的名称"),
}
_DELIVERY_RESERVED_PATH_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_DELIVERY_FORMATTER = Formatter()
_VISIBILITY_SELECTOR_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_VISIBILITY_MARKER_INPUT_RE = re.compile(
    r"\{\{\s*#?\s*(?:visibility|content)\s*:\s*([A-Za-z0-9_.-]+)\s*\}\}"
)
_VISIBILITY_ACTION_OPTIONS = {
    "remove": "删除块",
}
_DELIVERY_PRESET_TEMPLATE_SPECS = (
    {
        "preset_id": "review_copy",
        "label": "审阅稿",
        "compare_docx": True,
    },
    {
        "preset_id": "student_version",
        "label": "学生版",
        "visibility_rules": (
            ("answer", "remove"),
            ("analysis", "remove"),
            ("solution", "remove"),
        ),
    },
    {
        "preset_id": "teacher_version",
        "label": "教师版",
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "answer_version",
        "label": "答案版",
        "visibility_rules": (
            ("question_only", "remove"),
        ),
        "include_structured_intermediate": True,
    },
    {
        "preset_id": "formal_copy",
        "label": "正式稿",
    },
    {
        "preset_id": "customer_copy",
        "label": "客户版",
        "visibility_rules": (
            ("internal", "remove"),
            ("internal_note", "remove"),
            ("review_note", "remove"),
        ),
    },
    {
        "preset_id": "internal_review",
        "label": "内部审阅稿",
        "compare_docx": True,
    },
    {
        "preset_id": "material_archive",
        "label": "资料归档包",
        "material_manifest": True,
        "material_package": True,
        "report_level": "detailed",
    },
)
_DELIVERY_PRESET_TEMPLATE_MAP = {
    str(spec["preset_id"]): spec for spec in _DELIVERY_PRESET_TEMPLATE_SPECS
}
_DELIVERY_PRESET_TEMPLATE_ARTIFACTS = (
    ("final_docx", "最终 Word", True),
    ("review_pdf", "审阅 PDF", False),
    ("compare_docx", "对比 Word", False),
    ("report_json", "报告 JSON", True),
    ("report_markdown", "报告 Markdown", True),
    ("material_manifest", "资料清单", False),
    ("material_package", "资料包", False),
)


def _delivery_preset_template_artifact_labels(spec: dict[str, object]) -> list[str]:
    labels = [
        label
        for key, label, default in _DELIVERY_PRESET_TEMPLATE_ARTIFACTS
        if bool(spec.get(key, default))
    ]
    if bool(spec.get("include_structured_intermediate", False)):
        labels.append("结构化中间结果")
    if str(spec.get("report_level", "")).strip().lower() == "detailed":
        labels.append("详细报告")
    return labels


def _delivery_preset_template_rule_summary(spec: dict[str, object]) -> str:
    rules = []
    for selector, action in tuple(spec.get("visibility_rules", ()) or ()):
        normalized_selector = str(selector or "").strip()
        if not normalized_selector:
            continue
        rules.append(
            f"{content_visibility_selector_label(normalized_selector)}："
            f"{_visibility_action_label(action)}"
        )
    return "；".join(rules) if rules else "不额外隐藏内容块"


def _delivery_preset_template_tooltip(spec: dict[str, object]) -> str:
    preset_id = str(spec.get("preset_id", "") or "").strip()
    label = str(spec.get("label", "") or preset_id or "交付版本")
    artifacts = "、".join(_delivery_preset_template_artifact_labels(spec)) or "按当前生成结果"
    return "\n".join(
        (
            f"新增交付版本：{label}",
            f"输出内容：{artifacts}",
            f"内容块规则：{_delivery_preset_template_rule_summary(spec)}",
            f"模板编号：{preset_id}",
        )
    )


def _populate_delivery_preset_template_combo(combo: StyledComboBox) -> None:
    combo.clear()
    combo.setToolTip("选择一个版本模板，点击“套用模板”会新增对应交付版本。")
    for spec in _DELIVERY_PRESET_TEMPLATE_SPECS:
        preset_id = str(spec["preset_id"])
        combo.addItem(str(spec["label"]), preset_id)
        combo.setItemData(
            combo.count() - 1,
            _delivery_preset_template_tooltip(spec),
            Qt.ToolTipRole,
        )


def _delivery_preset_preview_label(scene: SceneWorkspace, preset_id: object) -> str:
    normalized = str(preset_id or "").strip()
    for preset in list(getattr(scene, "delivery_presets", []) or []):
        if str(getattr(preset, "preset_id", "") or "").strip() != normalized:
            continue
        return delivery_preset_display_name(preset)
    return delivery_preset_display_name(normalized) or "交付版本"


def _compact_delivery_preview_labels(
    labels: Sequence[str],
    *,
    limit: int = 3,
) -> str:
    visible = [str(label or "").strip() for label in labels if str(label or "").strip()]
    if not visible:
        return ""
    if len(visible) <= limit:
        return "、".join(visible)
    return "、".join(visible[:limit]) + f"等 {len(visible)} 个"


def _scene_family_delivery_preview_tooltip(scene: SceneWorkspace | None) -> str:
    if scene is None:
        return "暂无方案，无法应用推荐交付版本。"
    if not has_planned_scene_family_application(scene):
        return "当前方案类型暂无自动推荐交付版本。"
    preview = copy.deepcopy(scene)
    result = apply_planned_scene_family_defaults(preview)
    if not result.applied:
        return "当前方案类型暂无自动推荐交付版本。"
    family_label = FAMILY_DISPLAY_LABELS.get(
        result.family_id,
        str(result.family_id or "").replace("_", " "),
    )
    added_labels = [
        _delivery_preset_preview_label(preview, preset_id)
        for preset_id in result.added_presets
    ]
    updated_labels = [
        _delivery_preset_preview_label(preview, preset_id)
        for preset_id in result.updated_presets
    ]
    lines = [
        "按当前方案类型补齐推荐交付版本。",
        f"方案类型：{family_label}",
    ]
    added_text = _compact_delivery_preview_labels(added_labels)
    if added_text:
        lines.append(f"将新增：{added_text}")
    updated_text = _compact_delivery_preview_labels(updated_labels)
    if updated_text:
        lines.append(f"将更新：{updated_text}")
    if result.default_delivery_preset_id:
        lines.append(
            "默认版本："
            + _delivery_preset_preview_label(preview, result.default_delivery_preset_id)
        )
    preset_ids = [*result.added_presets, *result.updated_presets]
    if preset_ids:
        lines.append("版本 ID：" + ", ".join(preset_ids))
    return "\n".join(lines)


def _apply_delivery_preset_template_artifacts(
    artifacts: OutputConfig,
    spec: dict[str, object],
) -> OutputConfig:
    artifacts.final_docx = bool(spec.get("final_docx", True))
    artifacts.review_pdf = bool(spec.get("review_pdf", False))
    artifacts.compare_docx = bool(spec.get("compare_docx", False))
    artifacts.compare_text = artifacts.compare_docx
    artifacts.compare_formatting = artifacts.compare_docx
    artifacts.report_json = bool(spec.get("report_json", True))
    artifacts.report_markdown = bool(spec.get("report_markdown", True))
    artifacts.material_manifest = bool(spec.get("material_manifest", False))
    artifacts.material_package = bool(spec.get("material_package", False))
    return artifacts


def _build_delivery_preset_template_rules(
    spec: dict[str, object],
) -> list[ContentVisibilityRule]:
    rules: list[ContentVisibilityRule] = []
    for selector, action in tuple(spec.get("visibility_rules", ()) or ()):
        normalized_selector = str(selector or "").strip()
        normalized_action = _normalize_visibility_action(str(action or "remove"))
        if not normalized_selector:
            continue
        key = normalized_selector.lower()
        rules.append(
            ContentVisibilityRule(
                rule_id=f"hide_{key}",
                label=content_visibility_selector_label(normalized_selector),
                selector_type="marker_block",
                selector=normalized_selector,
                action=normalized_action,
            )
        )
    return rules


def _delivery_preset_template_label(spec: dict[str, object], preset_id: str) -> str:
    label = str(spec.get("label", "") or spec.get("preset_id", "") or "交付版本")
    base_id = _safe_delivery_preset_id(str(spec.get("preset_id", "") or "delivery"))
    if str(preset_id).startswith(f"{base_id}_"):
        suffix = str(preset_id)[len(base_id) + 1 :]
        if suffix.isdigit():
            return f"{label} {suffix}"
    return label


class _SafePreviewDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _safe_delivery_preset_id(value: str) -> str:
    normalized: list[str] = []
    for char in str(value or "").strip().lower():
        if char.isascii() and (char.isalnum() or char in {"_", "-"}):
            normalized.append(char)
        elif char.isspace() or char in {"/", "\\", ".", ":", "|"}:
            normalized.append("_")
    result = "".join(normalized).strip("_-")
    return result or "delivery"


def _build_delivery_validation_items(
    preset,
    *,
    scene: SceneWorkspace | None = None,
    output_template: str | None = None,
    filename_template: str | None = None,
    visibility_text: str | None = None,
) -> tuple[SummaryGridItem, ...]:
    if preset is None:
        return (
            SummaryGridItem(
                key="delivery_variables",
                label="可用变量",
                value="6 个变量",
                detail=_delivery_variable_hint(),
                tooltip=_delivery_variable_tooltip(),
                variant="info",
            ),
            SummaryGridItem(
                key="delivery_template_status",
                label="路径命名",
                value="未选择",
                detail="",
                variant="warning",
            ),
            SummaryGridItem(
                key="delivery_rule_status",
                label="内容块规则",
                value="未选择",
                detail="",
                variant="warning",
            ),
            SummaryGridItem(
                key="delivery_target_template",
                label="目标模板",
                value="未选择",
                detail="",
                variant="warning",
            ),
        )
    output_template = str(
        output_template
        if output_template is not None
        else getattr(preset, "output_dir_template", "") or "{document_dir}/output"
    )
    filename_template = str(
        filename_template
        if filename_template is not None
        else getattr(preset, "filename_template", "") or "{stem}_{preset_id}"
    )
    output_issues = _validate_delivery_template(output_template, filename=False)
    filename_issues = _validate_delivery_template(filename_template, filename=True)
    template_issues = output_issues + filename_issues
    preview_dir = _render_delivery_preview(output_template, preset)
    preview_name = _render_delivery_preview(filename_template, preset) or "document.docx"
    if not preview_name.lower().endswith(".docx"):
        preview_name = f"{preview_name}.docx"

    rule_source = (
        visibility_text
        if visibility_text is not None
        else _format_visibility_rules(getattr(preset, "content_visibility_rules", []))
    )
    rule_issues = _validate_visibility_rule_text(rule_source)
    parsed_rules = _parse_visibility_rules(rule_source)
    rule_count = len(parsed_rules)
    return (
        SummaryGridItem(
            key="delivery_variables",
            label="可用变量",
            value="6 个变量",
            detail=_delivery_variable_hint(),
            tooltip=_delivery_variable_tooltip(),
            variant="info",
        ),
        SummaryGridItem(
            key="delivery_template_status",
            label="路径命名",
            value="需处理" if template_issues else "通过",
            detail="；".join(template_issues) if template_issues else f"{preview_dir} / {preview_name}",
            variant="warning" if template_issues else "success",
        ),
        SummaryGridItem(
            key="delivery_rule_status",
            label="内容块规则",
            value="需处理" if rule_issues else f"{rule_count} 条",
            detail="；".join(rule_issues) if rule_issues else _visibility_rule_summary_text(rule_source),
            tooltip=_visibility_rule_tooltip(rule_source),
            variant="warning" if rule_issues else "success",
        ),
        _build_target_template_summary_item(preset, scene),
    )


def _delivery_variable_hint() -> str:
    return "、".join(_delivery_variable_label(name) for name in _DELIVERY_TEMPLATE_VARIABLES)


def _delivery_variable_tooltip() -> str:
    return "\n".join(
        f"{_delivery_variable_label(name)}：{{{name}}}"
        for name in _DELIVERY_TEMPLATE_VARIABLES
    )


def _delivery_variable_label(variable: str) -> str:
    return _DELIVERY_TEMPLATE_VARIABLE_LABELS.get(
        str(variable or "").strip(),
        (str(variable or "").replace("_", " "), ""),
    )[0]


def _delivery_variable_option_tooltip(variable: str) -> str:
    normalized = str(variable or "").strip()
    label, description = _DELIVERY_TEMPLATE_VARIABLE_LABELS.get(
        normalized,
        (_delivery_variable_label(normalized), ""),
    )
    lines = [f"插入占位符：{{{normalized}}}"]
    if description:
        lines.insert(0, f"{label}：{description}")
    return "\n".join(lines)


def _populate_delivery_variable_combo(combo: StyledComboBox) -> None:
    combo.clear()
    for variable in _DELIVERY_TEMPLATE_VARIABLES:
        combo.addItem(_delivery_variable_label(variable), variable)
        combo.setItemData(
            combo.count() - 1,
            _delivery_variable_option_tooltip(variable),
            Qt.ToolTipRole,
        )


def _populate_visibility_selector_combo(combo: StyledComboBox) -> None:
    combo.clear()
    combo.addItem("选择常用内容块", "")
    combo.setItemData(0, "选择后会填入右侧输入框，也可以直接输入自定义内容块名。", Qt.ToolTipRole)
    for option in COMMON_CONTENT_VISIBILITY_SELECTOR_OPTIONS:
        combo.addItem(option.label, option.selector)
        combo.setItemData(
            combo.count() - 1,
            content_visibility_selector_tooltip(option.selector, option.description),
            Qt.ToolTipRole,
        )


def _visibility_action_label(action: object) -> str:
    normalized = str(action or "remove").strip().lower()
    return _VISIBILITY_ACTION_OPTIONS.get(normalized, normalized or "删除块")


def _visibility_rule_summary_text(text: str, *, limit: int = 4) -> str:
    rules = _parse_visibility_rules(text)
    if not rules:
        return "未配置内容块规则"
    parts = [
        f"{content_visibility_selector_label(rule.selector)}：{_visibility_action_label(rule.action)}"
        for rule in rules[:limit]
    ]
    if len(rules) > limit:
        parts.append(f"还有 {len(rules) - limit} 条")
    return "；".join(parts)


def _visibility_rule_tooltip(text: str) -> str:
    rules = _parse_visibility_rules(text)
    if not rules:
        return "未配置内容块规则。"
    return "\n".join(
        (
            f"{rule.selector}={rule.action} · "
            f"{content_visibility_selector_label(rule.selector)}：{_visibility_action_label(rule.action)}"
        )
        for rule in rules
    )


def _validate_delivery_template(template: str, *, filename: bool) -> list[str]:
    text = str(template or "").strip()
    if not text:
        return []
    issues: list[str] = []
    variables, parse_issue = _extract_delivery_variables(text)
    if parse_issue:
        issues.append(parse_issue)
    unknown = sorted(variable for variable in variables if variable not in _DELIVERY_TEMPLATE_VARIABLES)
    if unknown:
        issues.append("未知变量: " + ", ".join(unknown))
    invalid_chars = '<>:"|?*' if filename else '<>"|?*'
    invalid = sorted({char for char in _strip_delivery_template_fields(text) if char in invalid_chars})
    if invalid:
        issues.append("包含非法字符: " + "".join(invalid))
    rendered = _render_delivery_preview(text, _PreviewDeliveryPreset())
    issues.extend(_validate_rendered_delivery_path(rendered, filename=filename))
    return issues


def _extract_delivery_variables(template: str) -> tuple[set[str], str]:
    variables: set[str] = set()
    try:
        parts = list(_DELIVERY_FORMATTER.parse(template))
    except ValueError:
        return variables, "模板大括号不完整"
    for _literal, field_name, _format_spec, _conversion in parts:
        if not field_name:
            continue
        root = field_name.split(".", 1)[0].split("[", 1)[0]
        if root:
            variables.add(root)
    return variables, ""


def _strip_delivery_template_fields(template: str) -> str:
    return re.sub(r"\{[^{}]*\}", "", str(template or ""))


def _render_delivery_preview(template: str, preset) -> str:
    values = _SafePreviewDict(
        {
            "document_dir": "D:/docs",
            "output_dir": "D:/docs/output",
            "stem": "document",
            "suffix": ".docx",
            "preset_id": str(getattr(preset, "preset_id", "") or "final"),
            "preset_label": delivery_preset_display_name(preset),
        }
    )
    try:
        return str(template or "").format_map(values)
    except (KeyError, ValueError, AttributeError):
        return str(template or "")


class _PreviewDeliveryPreset:
    preset_id = "preview"
    label = "Preview"


def _validate_rendered_delivery_path(path_text: str, *, filename: bool) -> list[str]:
    text = str(path_text or "").strip()
    if not text:
        return []
    issues: list[str] = []
    if filename and ("/" in text or "\\" in text):
        issues.append("文件命名不应包含路径分隔符")
    normalized = text.replace("\\", "/")
    segments = [segment for segment in normalized.split("/") if segment]
    for index, segment in enumerate(segments):
        if index == 0 and re.match(r"^[A-Za-z]:$", segment):
            continue
        if segment in {".", ".."}:
            issues.append(f"包含相对路径段: {segment}")
            continue
        trimmed = segment.rstrip(" .")
        if trimmed != segment:
            issues.append(f"路径段不能以空格或点结尾: {segment}")
        base = (trimmed or segment).split(".", 1)[0].upper()
        if base in _DELIVERY_RESERVED_PATH_NAMES:
            issues.append(f"包含 Windows 保留名: {segment}")
    return _dedupe_issue_list(issues)


def _dedupe_issue_list(issues: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for issue in issues:
        if issue in seen:
            continue
        seen.add(issue)
        deduped.append(issue)
    return deduped


def _build_target_template_summary_item(preset, scene: SceneWorkspace | None) -> SummaryGridItem:
    target_id = str(getattr(preset, "target_template_id", "") or "").strip()
    current_id = _scene_current_template_id(scene)
    compatible_ids = set(_scene_compatible_template_ids(scene))
    mode_id = _mode_id_for_scene(scene)
    if not target_id:
        return SummaryGridItem(
            key="delivery_target_template",
            label="目标模板",
            value="当前模板",
            detail=_template_label_with_id(current_id, mode_id=mode_id) if current_id else "跟随当前方案模板",
            variant="info",
        )
    if target_id in compatible_ids:
        return SummaryGridItem(
            key="delivery_target_template",
            label="目标模板",
            value="兼容模板",
            detail=_template_label_with_id(target_id, mode_id=mode_id),
            variant="success",
        )
    entry = get_template_entry(target_id, mode_id=mode_id)
    if entry is not None:
        return SummaryGridItem(
            key="delivery_target_template",
            label="目标模板",
            value="非兼容",
            detail=f"{entry.name} ({target_id}) 不在当前方案兼容列表",
            variant="warning",
        )
    return SummaryGridItem(
        key="delivery_target_template",
        label="目标模板",
        value="需处理",
        detail=f"模板不存在: {target_id}",
        variant="warning",
    )


def _scene_current_template_id(scene: SceneWorkspace | None) -> str:
    if scene is None:
        return ""
    return str(getattr(scene, "template_id", "") or "").strip()


def _scene_compatible_template_ids(scene: SceneWorkspace | None) -> list[str]:
    ids: list[str] = []
    if scene is None:
        return ids
    for value in list(getattr(scene, "compatible_template_ids", []) or []):
        normalized = str(value or "").strip()
        if normalized and normalized not in ids:
            ids.append(normalized)
    return ids


def _template_label_with_id(template_id: str, *, mode_id: str | None = None) -> str:
    normalized = str(template_id or "").strip()
    if not normalized:
        return ""
    entry = get_template_entry(normalized, mode_id=mode_id)
    if entry is None:
        return normalized
    return f"{entry.name} ({normalized})"


def _template_display_label(template_id: str, *, mode_id: str | None = None) -> str:
    normalized = str(template_id or "").strip()
    if not normalized:
        return ""
    entry = get_template_entry(normalized, mode_id=mode_id)
    return entry.name if entry is not None else normalized


def _template_option_tooltip(template_id: str, *, mode_id: str | None = None) -> str:
    normalized = str(template_id or "").strip()
    if not normalized:
        return "留空时使用当前方案模板"
    entry = get_template_entry(normalized, mode_id=mode_id)
    lines = [f"模板 ID：{normalized}"]
    if entry is not None:
        lines.insert(0, f"模板名称：{entry.name}")
    return "\n".join(lines)


def _mode_id_for_scene(scene: SceneWorkspace | None) -> str:
    if scene is None:
        return "custom"
    return work_mode_for_scene_id(str(getattr(scene, "scene_id", "") or "")).mode_id


def _validate_visibility_rule_text(text: str) -> list[str]:
    issues: list[str] = []
    seen: set[str] = set()
    for line_no, raw_line in enumerate(str(text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        selector, action = _split_visibility_rule_line(line)
        selector = selector.strip()
        action = str(action or "remove").strip().lower()
        if not selector:
            issues.append(f"第 {line_no} 行缺少内容块名")
            continue
        if not _VISIBILITY_SELECTOR_RE.match(selector):
            issues.append(f"第 {line_no} 行内容块名只能包含字母数字、_、-、.")
        if action != "remove":
            issues.append(f"第 {line_no} 行未知处理动作: {action or '空'}")
        key = selector.lower()
        if key in seen:
            issues.append(
                f"第 {line_no} 行重复内容块: {content_visibility_selector_display(selector)}"
            )
        seen.add(key)
    return issues


def _extract_visibility_selector_input(value: str) -> str:
    text = str(value or "").strip()
    marker_match = _VISIBILITY_MARKER_INPUT_RE.search(text)
    if marker_match:
        text = marker_match.group(1)
    return text.strip().lower()


def _visibility_rule_text_has_selector(text: str, selector: str) -> bool:
    target = str(selector or "").strip().lower()
    if not target:
        return False
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        existing, _action = _split_visibility_rule_line(line)
        if existing.strip().lower() == target:
            return True
    return False


def _append_visibility_rule_text(text: str, selector: str, action: str) -> str:
    selector = _extract_visibility_selector_input(selector)
    action = _normalize_visibility_action(action)
    if not selector or not _VISIBILITY_SELECTOR_RE.match(selector):
        return str(text or "")
    if _visibility_rule_text_has_selector(text, selector):
        return str(text or "")
    lines = str(text or "").splitlines()
    lines.append(f"{selector}={action}")
    return "\n".join(line for line in lines if line.strip())
