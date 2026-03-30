"""Heading-numbering normalization helpers kept separate from migration.py."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


CURRENT_HEADING_CORE_STYLES = {
    "chinese_chapter",
    "chinese_section",
    "chinese_lower",
    "chinese_upper",
    "chinese_paren",
    "arabic",
    "arabic_paren",
    "roman_upper",
    "roman_lower",
    "circled",
    "circled_paren",
    "alpha_upper",
    "alpha_lower",
}

CURRENT_CORE_STYLE_ALIASES = {
    "cn_lower": "chinese_lower",
    "cn_upper": "chinese_upper",
    "arabic_pad2": "arabic",
}

CHAIN_NUMBER_STYLE_BY_CORE = {
    "chinese_chapter": "cn_lower",
    "chinese_section": "cn_lower",
    "chinese_lower": "cn_lower",
    "chinese_upper": "cn_upper",
    "chinese_paren": "cn_lower",
    "cn_lower": "cn_lower",
    "cn_upper": "cn_upper",
    "arabic": "arabic",
    "arabic_pad2": "arabic_pad2",
    "arabic_paren": "arabic",
    "roman_upper": "roman_upper",
    "roman_lower": "roman_lower",
    "circled": "circled",
    "circled_paren": "circled_paren",
    "alpha_upper": "alpha_upper",
    "alpha_lower": "alpha_lower",
}

DISPLAY_TOKEN_BY_CORE = {
    "chinese_chapter": "{cn}",
    "chinese_section": "{cn}",
    "chinese_lower": "{cn}",
    "chinese_upper": "{CN}",
    "chinese_paren": "{cn}",
    "cn_lower": "{cn}",
    "cn_upper": "{CN}",
    "arabic": "{nn}",
    "arabic_pad2": "{nn}",
    "arabic_paren": "{nn}",
    "roman_upper": "{RN}",
    "roman_lower": "{rn}",
    "circled": "{cc}",
    "circled_paren": "{cc}",
    "alpha_upper": "{AL}",
    "alpha_lower": "{al}",
}

DISPLAY_SHELL_TEMPLATES = {
    "plain": "{}",
    "dot_suffix": "{}.",
    "dot_suffix_fullwidth": "{}\uff0e",
    "chapter_cn": "\u7b2c{}\u7ae0",
    "section_cn": "\u7b2c{}\u8282",
    "dunhao_cn": "{}\u3001",
    "paren_cn": "\uff08{}\uff09",
    "paren_en": "({})",
    "appendix_cn": "\u9644\u5f55{}",
}

LEGACY_HEADING_STYLE_PRESETS = {
    "chinese_chapter": ("chapter_cn", "cn_lower", "current_only"),
    "chinese_section": ("section_cn", "cn_lower", "current_only"),
    "chinese_ordinal": ("dunhao_cn", "cn_lower", "current_only"),
    "chinese_lower": ("dunhao_cn", "cn_lower", "current_only"),
    "chinese_upper": ("dunhao_cn", "cn_upper", "current_only"),
    "chinese_ordinal_paren": ("paren_cn", "cn_lower", "current_only"),
    "chinese_paren": ("paren_cn", "cn_lower", "current_only"),
    "arabic": ("plain", "arabic", "current_only"),
    "arabic_dotted": ("plain", "arabic", ""),
    "arabic_paren": ("paren_en", "arabic", "current_only"),
    "roman_upper": ("plain", "roman_upper", "current_only"),
    "roman_lower": ("plain", "roman_lower", "current_only"),
    "alpha_upper": ("plain", "alpha_upper", "current_only"),
    "alpha_lower": ("plain", "alpha_lower", "current_only"),
    "circled": ("plain", "circled", "current_only"),
    "circled_paren": ("paren_en", "circled", "current_only"),
}

LEGACY_CHAIN_ID_RE = re.compile(r"^l1(?:_dot_l\d+)*_dot_current$")
LEGACY_TEMPLATE_TOKEN_RE = re.compile(r"(\{level\d+\}|\{current\})")


def normalize_heading_numbering_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize all heading-numbering inputs into canonical level_bindings."""
    heading_numbering = raw.get("heading_numbering")
    if isinstance(heading_numbering, Mapping):
        payload = copy.deepcopy(dict(heading_numbering))
        bindings = payload.get("level_bindings")
        if isinstance(bindings, Mapping):
            payload["level_bindings"] = _normalize_level_bindings(bindings)
            return payload

        levels = payload.pop("levels", None)
        if isinstance(levels, Mapping):
            payload["level_bindings"] = _normalize_legacy_levels(levels)
            return payload

    heading_numbering_v2 = raw.get("heading_numbering_v2")
    if isinstance(heading_numbering_v2, Mapping):
        payload = copy.deepcopy(dict(heading_numbering_v2))
        bindings = payload.get("level_bindings")
        if isinstance(bindings, Mapping):
            payload["level_bindings"] = _normalize_level_bindings(bindings)
        return payload

    legacy_heading = raw.get("heading")
    if isinstance(legacy_heading, Mapping):
        bindings = _normalize_legacy_heading_alias(legacy_heading)
        if bindings:
            return {"level_bindings": bindings}

    return {}


def _normalize_level_bindings(bindings: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for level_name, payload in bindings.items():
        if not isinstance(payload, Mapping):
            continue
        normalized[str(level_name)] = _normalize_level_binding_payload(dict(payload))
    return normalized


def _normalize_level_binding_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _copy_mapping(payload)
    shell_id = str(normalized.get("display_shell", "plain") or "plain")
    chain = _normalize_chain_value(str(normalized.get("chain", "current_only") or "current_only"))
    raw_core_style = str(normalized.get("display_core_style", "arabic") or "arabic")
    core_style = _normalize_core_style(raw_core_style)

    normalized["display_core_style"] = core_style
    normalized["chain"] = chain
    normalized.setdefault("chain_number_style", _normalize_chain_number_style(core_style))

    if not normalized.get("display_template"):
        should_derive = (
            shell_id != "plain"
            or chain != "current_only"
            or raw_core_style != core_style
            or core_style not in CURRENT_HEADING_CORE_STYLES
        )
        if should_derive:
            display_template = _derive_display_template(
                shell_id=shell_id,
                core_style=core_style,
                chain=chain,
            )
            if display_template:
                normalized["display_template"] = display_template

    return normalized


def _normalize_legacy_levels(levels: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    for level_name, payload in levels.items():
        if not isinstance(payload, Mapping):
            continue

        format_name = str(payload.get("format", "") or "").strip()
        shell_id, core_style, default_chain = LEGACY_HEADING_STYLE_PRESETS.get(
            format_name,
            ("plain", "arabic", "current_only"),
        )

        template_conversion = _convert_legacy_display_template(
            str(payload.get("template", "") or ""),
            core_style=core_style,
        )
        chain = template_conversion.get("chain") or default_chain or _default_chain_for_level(level_name)

        binding: dict[str, Any] = {
            "enabled": bool(payload.get("enabled", True)),
            "display_shell": shell_id,
            "display_core_style": core_style,
            "chain": chain,
            "title_separator": payload.get("separator")
            or payload.get("title_separator")
            or payload.get("custom_separator")
            or "\u3000",
            "start_at": _coerce_positive_int(payload.get("start_at"), default=1),
            "include_in_toc": bool(payload.get("include_in_toc", True)),
        }

        if template_conversion.get("display_template"):
            binding["display_template"] = template_conversion["display_template"]
        if template_conversion.get("chain_separator"):
            binding["chain_separator"] = template_conversion["chain_separator"]

        normalized[str(level_name)] = _normalize_level_binding_payload(binding)

    return normalized


def _normalize_legacy_heading_alias(payload: Mapping[str, Any]) -> dict[str, Any]:
    numbering_style = str(payload.get("numbering_style", "") or "arabic_dot").strip()
    separator = str(payload.get("separator", " ") or " ")
    level2_suffix = str(payload.get("level2_suffix", "\u8282") or "\u8282")

    if numbering_style == "cn_chapter":
        level2_is_chinese = level2_suffix == "\u8282"
        bindings = {
            "heading1": {
                "enabled": True,
                "display_core_style": "chinese_chapter",
                "chain": "current_only",
                "title_separator": separator,
            },
            "heading2": {
                "enabled": True,
                "display_core_style": "chinese_section" if level2_is_chinese else "arabic",
                "chain": "current_only" if level2_is_chinese else "parent.current",
                "title_separator": separator,
            },
            "heading3": {
                "enabled": True,
                "display_core_style": "arabic",
                "chain": "parent.parent.current",
                "title_separator": separator,
            },
        }
        return {
            key: _normalize_level_binding_payload(value)
            for key, value in bindings.items()
        }

    if numbering_style == "arabic_dot":
        bindings = {
            "heading1": {
                "enabled": True,
                "display_core_style": "arabic",
                "chain": "current_only",
                "title_separator": separator,
            },
            "heading2": {
                "enabled": True,
                "display_core_style": "arabic",
                "chain": "parent.current",
                "title_separator": separator,
            },
            "heading3": {
                "enabled": True,
                "display_core_style": "arabic",
                "chain": "parent.parent.current",
                "title_separator": separator,
            },
        }
        return {
            key: _normalize_level_binding_payload(value)
            for key, value in bindings.items()
        }

    return {}


def _convert_legacy_display_template(
    template: str,
    *,
    core_style: str,
) -> dict[str, str]:
    stripped = str(template or "").strip()
    if not stripped:
        return {}

    token = DISPLAY_TOKEN_BY_CORE.get(core_style, "{nn}")
    parts = LEGACY_TEMPLATE_TOKEN_RE.split(stripped)
    placeholders = [
        part for part in parts
        if LEGACY_TEMPLATE_TOKEN_RE.fullmatch(part or "")
    ]
    if not placeholders:
        return {}

    if all(part == "{current}" for part in placeholders):
        return {"display_template": stripped.replace("{current}", token)}

    expected_tokens = [f"{{level{i}}}" for i in range(1, len(placeholders))]
    if placeholders[:-1] != expected_tokens or placeholders[-1] != "{current}":
        return {}

    literals = parts[1:-1:2]
    prefix = parts[0]
    suffix = parts[-1]
    separator = literals[0] if literals else "."

    if any(literal != separator for literal in literals):
        return {}

    parent_count = len(placeholders) - 1
    return {
        "display_template": f"{prefix}{{chain}}{suffix}",
        "chain": _build_parent_chain(parent_count),
        "chain_separator": separator or ".",
    }


def _derive_display_template(
    *,
    shell_id: str,
    core_style: str,
    chain: str,
) -> str:
    shell_template = DISPLAY_SHELL_TEMPLATES.get(shell_id, "{}")
    placeholder = "{chain}" if chain != "current_only" else DISPLAY_TOKEN_BY_CORE.get(core_style, "{nn}")
    return shell_template.replace("{}", placeholder)


def _normalize_core_style(core_style: str) -> str:
    return CURRENT_CORE_STYLE_ALIASES.get(core_style, core_style)


def _normalize_chain_number_style(core_style: str) -> str:
    return CHAIN_NUMBER_STYLE_BY_CORE.get(core_style, "arabic")


def _normalize_chain_value(chain: str) -> str:
    chain = str(chain or "current_only")
    if chain in {"current", "current_only"} or chain.startswith("parent."):
        return "current_only" if chain == "current" else chain

    if LEGACY_CHAIN_ID_RE.fullmatch(chain):
        parent_count = len(re.findall(r"l\d+", chain))
        return _build_parent_chain(parent_count)

    return "current_only"


def _default_chain_for_level(level_name: str) -> str:
    match = re.search(r"(\d+)$", str(level_name))
    if not match:
        return "current_only"
    level = max(int(match.group(1)), 1)
    return _build_parent_chain(level - 1)


def _build_parent_chain(parent_count: int) -> str:
    if parent_count <= 0:
        return "current_only"
    return ".".join(["parent"] * parent_count + ["current"])


def _coerce_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _copy_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    return copy.deepcopy(dict(payload))
