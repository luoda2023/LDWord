"""
Pure helper logic shared by heading numbering UI pieces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


TEMPLATE_MODE_STRUCTURED = "structured"
TEMPLATE_MODE_CUSTOM = "custom"
TEMPLATE_MODE_VALUES = {TEMPLATE_MODE_STRUCTURED, TEMPLATE_MODE_CUSTOM}

STYLE_OPTIONS = [
    ("arabic", "1, 2, 3... (阿拉伯数字)"),
    ("chinese_lower", "一, 二, 三... (中文小写)"),
    ("chinese_upper", "壹, 贰, 叁... (中文大写)"),
    ("roman_lower", "ⅰ, ⅱ, ⅲ... (罗马小写)"),
    ("roman_upper", "Ⅰ, Ⅱ, Ⅲ... (罗马大写)"),
    ("circled", "①, ②, ③... (圆圈数字)"),
    ("alpha_lower", "a, b, c... (字母小写)"),
    ("alpha_upper", "A, B, C... (字母大写)"),
]

_CORE_TO_PLACEHOLDER = {
    "arabic": "{nn}",
    "chinese_lower": "{cn}",
    "chinese_upper": "{CN}",
    "roman_lower": "{rn}",
    "roman_upper": "{RN}",
    "circled": "{cc}",
    "alpha_lower": "{al}",
    "alpha_upper": "{AL}",
}
_PLACEHOLDER_TO_CORE = {placeholder: core for core, placeholder in _CORE_TO_PLACEHOLDER.items()}
_SUPPORTED_TEMPLATE_TOKENS = frozenset([*_CORE_TO_PLACEHOLDER.values(), "{chain}"])
_TOKEN_RE = re.compile(r"\{[^{}]*\}")


@dataclass(frozen=True)
class TemplateValidationState:
    is_valid: bool
    message: str = ""


@dataclass(frozen=True)
class HeadingDetailState:
    title: str
    template_mode: str
    raw_template: str
    raw_template_valid: bool
    raw_template_error: str
    prefix: str
    core_style: str
    suffix: str
    include_in_toc: bool
    chain_options: list[tuple[str, str]]
    chain_value: str
    chain_separator: str
    reference_core_style: str
    title_separator: str
    start_at: int
    restart_on: str
    restart_options: list[tuple[str, str]]
    restart_mode: str
    restart_trigger_level: int | None
    restart_mode_options: list[tuple[str, str]]
    restart_trigger_options: list[tuple[str, str]]


@dataclass(frozen=True)
class HeadingEditorEnableState:
    prefix: bool
    core_style: bool
    suffix: bool
    chain: bool
    chain_separator: bool
    reference_core_style: bool
    title_separator: bool
    start_at: bool
    restart_on: bool
    use_raw_toggle: bool
    raw_template: bool


def compose_display_template(prefix: str, core_style: str, suffix: str) -> str:
    return f"{prefix}{_CORE_TO_PLACEHOLDER.get(core_style, '{nn}')}{suffix}"


def split_display_template(template: str, fallback_core_style: str = "arabic") -> tuple[str, str, str]:
    if not template:
        return "", fallback_core_style or "arabic", ""

    for placeholder, core_style in _PLACEHOLDER_TO_CORE.items():
        if placeholder in template:
            prefix, suffix = template.split(placeholder, 1)
            return prefix, core_style, suffix

    return "", fallback_core_style or "arabic", ""


def normalize_display_template_mode(value: str | None) -> str:
    normalized = str(value or TEMPLATE_MODE_STRUCTURED).strip().lower()
    if normalized in TEMPLATE_MODE_VALUES:
        return normalized
    return TEMPLATE_MODE_STRUCTURED


def validate_display_template(template: str) -> TemplateValidationState:
    text = str(template or "").strip()
    if not text:
        return TemplateValidationState(False, "模板不能为空")
    if "{" not in text and "}" not in text:
        return TemplateValidationState(False, "模板至少需要一个编号占位符")

    consumed = [False] * len(text)
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token not in _SUPPORTED_TEMPLATE_TOKENS:
            return TemplateValidationState(False, f"不支持的占位符：{token}")
        for idx in range(match.start(), match.end()):
            consumed[idx] = True

    for idx, char in enumerate(text):
        if char in "{}" and not consumed[idx]:
            return TemplateValidationState(False, "占位符括号不完整")

    if not any(token in text for token in _SUPPORTED_TEMPLATE_TOKENS):
        return TemplateValidationState(False, "模板至少需要一个编号占位符")
    return TemplateValidationState(True)


def default_chain_value(level: int) -> str:
    if level <= 1:
        return "current_only"
    return ".".join(["parent"] * (level - 1)) + ".current"


def build_chain_options(level: int) -> list[tuple[str, str]]:
    options = [("不包含 (仅显示当前级别)", "current_only")]
    if level >= 2:
        options.append(("包含上一级 (如 1.1)", "parent.current"))
    if level >= 3:
        options.append(("包含所有上级 (如 1.1.1)", default_chain_value(level)))
    return options


def normalize_restart_on(value: str | None) -> str:
    normalized = str(value or "parent").strip().lower().replace("_", "-")
    if normalized in {"", "none"}:
        return "parent"
    if normalized in {"never", "continuous"}:
        return "document"
    return normalized


def build_restart_options(level: int) -> list[tuple[str, str]]:
    options = [("上级变化时重新开始", "parent"), ("全文连续编号", "document")]
    for parent_level in range(1, max(1, int(level))):
        options.append((f"级别 {parent_level} 变化时重新开始", f"heading{parent_level}"))
    return options


def build_restart_mode_options(level: int) -> list[tuple[str, str]]:
    options = [("上级变化时重新开始", "parent"), ("全文连续编号", "document")]
    if int(level) > 1:
        options.append(("指定级别变化时重新开始", "specific"))
    return options


def build_restart_trigger_options(level: int) -> list[tuple[str, str]]:
    return [(f"级别 {parent_level}", f"heading{parent_level}") for parent_level in range(1, max(1, int(level)))]


def restart_mode_from_value(value: str | None) -> str:
    normalized = normalize_restart_on(value)
    if normalized.startswith("heading"):
        return "specific"
    return normalized


def restart_trigger_level_from_value(value: str | None) -> int | None:
    normalized = normalize_restart_on(value)
    if not normalized.startswith("heading"):
        return None
    try:
        return int(normalized.removeprefix("heading"))
    except ValueError:
        return None


def build_detail_state(level: int, binding) -> HeadingDetailState:
    fallback_core_style = getattr(binding, "display_core_style", None) or "arabic"
    template = getattr(binding, "display_template", "") or compose_display_template("", fallback_core_style, "")
    prefix, core_style, suffix = split_display_template(template, fallback_core_style)
    template_mode = normalize_display_template_mode(getattr(binding, "display_template_mode", None))
    validation = validate_display_template(template)
    restart_on = normalize_restart_on(getattr(binding, "restart_on", None))
    chain_separator = getattr(binding, "chain_separator", None)
    return HeadingDetailState(
        title=f"级别 {level} 编号设置",
        template_mode=template_mode,
        raw_template=template,
        raw_template_valid=validation.is_valid,
        raw_template_error=validation.message,
        prefix=prefix,
        core_style=core_style,
        suffix=suffix,
        include_in_toc=getattr(binding, "include_in_toc", True),
        chain_options=build_chain_options(level),
        chain_value=getattr(binding, "chain", None) or "current_only",
        chain_separator="." if chain_separator is None else chain_separator,
        reference_core_style=getattr(binding, "reference_core_style", None) or "arabic",
        title_separator=getattr(binding, "title_separator", None) or "",
        start_at=1 if getattr(binding, "start_at", None) is None else getattr(binding, "start_at", 1),
        restart_on=restart_on,
        restart_options=build_restart_options(level),
        restart_mode=restart_mode_from_value(restart_on),
        restart_trigger_level=restart_trigger_level_from_value(restart_on),
        restart_mode_options=build_restart_mode_options(level),
        restart_trigger_options=build_restart_trigger_options(level),
    )


def should_show_chain_separator(chain_value: str | None) -> bool:
    return (chain_value or "current_only") != "current_only"


def build_editor_enable_state(
    *,
    is_binding_overridden: bool,
    use_raw_template: bool,
) -> HeadingEditorEnableState:
    if not is_binding_overridden:
        return HeadingEditorEnableState(
            prefix=False,
            core_style=False,
            suffix=False,
            chain=False,
            chain_separator=False,
            reference_core_style=False,
            title_separator=False,
            start_at=False,
            restart_on=False,
            use_raw_toggle=False,
            raw_template=False,
        )

    return HeadingEditorEnableState(
        prefix=not use_raw_template,
        core_style=not use_raw_template,
        suffix=not use_raw_template,
        chain=True,
        chain_separator=True,
        reference_core_style=True,
        title_separator=True,
        start_at=True,
        restart_on=True,
        use_raw_toggle=True,
        raw_template=use_raw_template,
    )


def build_expert_toggle_text(is_expanded: bool) -> str:
    return "▴ 收起模板编辑" if is_expanded else "▾ 展开模板编辑"


def parse_csv_items(text: str) -> list[str]:
    return [
        segment.strip()
        for segment in re.split(r"[,，]", text or "")
        if segment.strip()
    ]


def format_csv_items(items: list[str]) -> str:
    return ", ".join(item.strip() for item in items if item and item.strip())
