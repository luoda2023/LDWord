"""
Pure helper logic shared by heading numbering UI pieces.
"""

from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class HeadingDetailState:
    title: str
    raw_template: str
    prefix: str
    core_style: str
    suffix: str
    include_in_toc: bool
    chain_options: list[tuple[str, str]]
    chain_value: str
    chain_separator: str
    reference_core_style: str
    title_separator: str


@dataclass(frozen=True)
class HeadingEditorEnableState:
    prefix: bool
    core_style: bool
    suffix: bool
    chain: bool
    chain_separator: bool
    reference_core_style: bool
    title_separator: bool
    use_raw_toggle: bool
    raw_template: bool


def compose_display_template(prefix: str, core_style: str, suffix: str) -> str:
    return f"{prefix}{_CORE_TO_PLACEHOLDER.get(core_style, '{nn}')}{suffix}"


def split_display_template(template: str) -> tuple[str, str, str]:
    if not template:
        return "", "arabic", ""

    for placeholder, core_style in _PLACEHOLDER_TO_CORE.items():
        if placeholder in template:
            prefix, suffix = template.split(placeholder, 1)
            return prefix, core_style, suffix

    return "", "arabic", ""


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


def build_detail_state(level: int, binding) -> HeadingDetailState:
    template = getattr(binding, "display_template", "") or "{nn}"
    prefix, core_style, suffix = split_display_template(template)
    return HeadingDetailState(
        title=f"级别 {level} 编号设置",
        raw_template=template,
        prefix=prefix,
        core_style=core_style,
        suffix=suffix,
        include_in_toc=getattr(binding, "include_in_toc", True),
        chain_options=build_chain_options(level),
        chain_value=getattr(binding, "chain", None) or "current_only",
        chain_separator=getattr(binding, "chain_separator", None) or ".",
        reference_core_style=getattr(binding, "reference_core_style", None) or "arabic",
        title_separator=getattr(binding, "title_separator", None) or "",
    )


def should_show_chain_separator(chain_value: str | None) -> bool:
    return (chain_value or "current_only") != "current_only"


def build_editor_enable_state(
    *,
    is_custom_mode: bool,
    use_raw_template: bool,
) -> HeadingEditorEnableState:
    if not is_custom_mode:
        return HeadingEditorEnableState(
            prefix=False,
            core_style=False,
            suffix=False,
            chain=False,
            chain_separator=False,
            reference_core_style=False,
            title_separator=False,
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
        use_raw_toggle=True,
        raw_template=use_raw_template,
    )


def build_expert_toggle_text(is_expanded: bool) -> str:
    return "▴ 隐藏高级选项" if is_expanded else "▾ 显示更多高级选项"


def build_non_numbered_toggle_text(is_expanded: bool) -> str:
    prefix = "▾" if is_expanded else "▸"
    return f"{prefix} 非编号标题 (忽略以下列表中的内容)"


def parse_csv_items(text: str) -> list[str]:
    return [segment.strip() for segment in (text or "").split(",") if segment.strip()]


def format_csv_items(items: list[str]) -> str:
    return ", ".join(item.strip() for item in items if item and item.strip())
