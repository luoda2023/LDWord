"""Pure heading-number text formatting shared by runtime and UI projections."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.config.heading_normalize import (
    CHAIN_NUMBER_STYLE_BY_CORE,
    CURRENT_CORE_STYLE_ALIASES,
)
from src.shared.engine.numbering import format_number

if TYPE_CHECKING:
    from src.config.template import HeadingLevelBindingConfig


_PLACEHOLDER_FORMAT: dict[str, str] = {
    "nn": "arabic",
    "cn": "cn_lower",
    "CN": "cn_upper",
    "rn": "roman_lower",
    "RN": "roman_upper",
    "cc": "circled",
    "al": "alpha_lower",
    "AL": "alpha_upper",
}
_PLACEHOLDER_RE = re.compile(
    r"\{(" + "|".join(_PLACEHOLDER_FORMAT.keys()) + r"|chain)\}"
)
_CORE_STYLE_AUTO_EXPAND: dict[str, str] = {
    "chinese_chapter": "第{cn}章",
    "chinese_section": "第{cn}节",
    "chinese_lower": "{cn}、",
    "chinese_upper": "{CN}、",
    "chinese_paren": "({cn})",
    "arabic": "{nn}",
    "arabic_paren": "{nn})",
    "roman_upper": "{RN}",
    "roman_lower": "{rn}",
    "circled": "{cc}",
    "circled_paren": "{cc}",
    "alpha_upper": "{AL}",
    "alpha_lower": "{al}",
}
_CHAIN_PATTERN = re.compile(r"^((?:parent\.)*)?current(?:_only)?$")


def parse_heading_number_chain(chain: str) -> tuple[str, ...]:
    """Return normalized parent/current segments for a heading chain."""

    value = str(chain or "current_only")
    match = _CHAIN_PATTERN.match(value)
    if not match:
        return tuple(value.split("."))
    prefix = match.group(1) or ""
    return (*("parent" for _ in range(prefix.count("parent"))), "current")


def format_heading_level_number(
    level: int,
    counters: list[int],
    binding: HeadingLevelBindingConfig,
    level_bindings: dict[str, HeadingLevelBindingConfig] | None = None,
) -> str:
    """Render one heading number from a binding without mutating inputs."""

    template = binding.display_template or _CORE_STYLE_AUTO_EXPAND.get(
        binding.display_core_style,
        "{nn}",
    )
    pairs = _resolve_chain_counters(
        int(level),
        counters,
        parse_heading_number_chain(binding.chain),
    )

    if len(pairs) == 1:
        return _replace_placeholders(template, pairs[0][0]) + binding.title_separator

    fallback_format = _PLACEHOLDER_FORMAT.get(
        binding.chain_number_style,
        "arabic",
    )
    chain_parts: list[str] = []
    for value, source_level, is_current in pairs:
        number_format = fallback_format
        if level_bindings:
            source_binding = level_bindings.get(f"heading{source_level}")
            if source_binding:
                style_key = (
                    source_binding.display_core_style
                    if is_current
                    else source_binding.reference_core_style
                )
                number_format = _resolve_core_style_format(
                    style_key,
                    fallback_format,
                )
        chain_parts.append(format_number(value, number_format))
    chain_text = binding.chain_separator.join(chain_parts)

    if "{chain}" in template:
        result = template.replace("{chain}", chain_text)
    elif _PLACEHOLDER_RE.search(template):
        result = _PLACEHOLDER_RE.sub(chain_text, template, count=1)
    else:
        result = chain_text
    return result + binding.title_separator


def _resolve_chain_counters(
    level: int,
    counters: list[int],
    chain_segments: tuple[str, ...],
) -> tuple[tuple[int, int, bool], ...]:
    result: list[tuple[int, int, bool]] = []
    current_level = level
    for segment in reversed(chain_segments):
        if segment == "current":
            result.append((counters[current_level], current_level, True))
        elif segment == "parent":
            current_level -= 1
            value = counters[current_level] if current_level >= 1 else 0
            result.append((value, max(current_level, 1), False))
        else:
            result.append((0, current_level, False))
    result.reverse()
    return tuple(result)


def _replace_placeholders(template: str, value: int) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key == "chain":
            return str(value)
        return format_number(value, _PLACEHOLDER_FORMAT.get(key, "arabic"))

    return _PLACEHOLDER_RE.sub(replace, template)


def _resolve_core_style_format(
    style_key: str | None,
    fallback: str = "arabic",
) -> str:
    raw = str(style_key or "").strip()
    if not raw:
        return fallback
    normalized = CURRENT_CORE_STYLE_ALIASES.get(raw, raw)
    return CHAIN_NUMBER_STYLE_BY_CORE.get(normalized, fallback)


__all__ = [
    "format_heading_level_number",
    "parse_heading_number_chain",
]
