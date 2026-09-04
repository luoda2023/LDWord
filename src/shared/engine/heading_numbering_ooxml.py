"""Word-native multilevel numbering helpers for recognized headings."""

from __future__ import annotations

import re
from dataclasses import dataclass

from docx.oxml import OxmlElement

from src.config.heading_normalize import CURRENT_CORE_STYLE_ALIASES
from src.shared.engine.heading_numbering_format import parse_heading_number_chain
from src.shared.engine.ooxml_ops import find_or_create_before, qn

MANAGED_ABSTRACT_NAME = "LDWordHeadingNumbering"

_AUTO_TEMPLATE_BY_CORE = {
    "chinese_chapter": "第{cn}章",
    "chinese_section": "第{cn}节",
    "chinese_lower": "{cn}、",
    "chinese_upper": "{CN}、",
    "chinese_paren": "（{cn}）",
    "arabic": "{nn}",
    "arabic_paren": "{nn})",
    "roman_upper": "{RN}",
    "roman_lower": "{rn}",
    "circled": "{cc}",
    "circled_paren": "（{cc}）",
    "alpha_upper": "{AL}",
    "alpha_lower": "{al}",
}
_NUM_FMT_BY_CORE = {
    "chinese_chapter": "chineseCounting",
    "chinese_section": "chineseCounting",
    "chinese_lower": "chineseCounting",
    "chinese_upper": "chineseLegalSimplified",
    "chinese_paren": "chineseCounting",
    "cn_lower": "chineseCounting",
    "cn_upper": "chineseLegalSimplified",
    "arabic": "decimal",
    "arabic_pad2": "decimalZero",
    "arabic_paren": "decimal",
    "roman_upper": "upperRoman",
    "roman_lower": "lowerRoman",
    "circled": "decimalEnclosedCircle",
    "circled_paren": "decimalEnclosedCircle",
    "alpha_upper": "upperLetter",
    "alpha_lower": "lowerLetter",
}
_NUMBER_PLACEHOLDER_RE = re.compile(r"\{(?:nn|cn|CN|rn|RN|cc|al|AL)\}")


@dataclass(frozen=True)
class EffectiveNumbering:
    source: str
    num_id: int
    level: int


def ensure_heading_numbering_definition(
    doc,
    level_bindings: dict,
    *,
    max_levels: int = 8,
) -> int:
    """Create or refresh one managed multilevel definition and return its numId."""

    numbering = doc.part.numbering_part.element
    abstract = _find_managed_abstract(numbering)
    if abstract is None:
        abstract_id = _next_id(numbering, "w:abstractNum", "w:abstractNumId", default=-1)
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(abstract_id))
        _insert_abstract_before_nums(numbering, abstract)
    else:
        abstract_id = int(abstract.get(qn("w:abstractNumId"), "0"))
        for child in list(abstract):
            abstract.remove(child)

    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "multilevel")
    abstract.append(multi)
    name = OxmlElement("w:name")
    name.set(qn("w:val"), MANAGED_ABSTRACT_NAME)
    abstract.append(name)

    for level in range(1, min(max(int(max_levels or 1), 1), 8) + 1):
        binding = level_bindings.get(f"heading{level}")
        if binding is None or not bool(getattr(binding, "enabled", False)):
            continue
        abstract.append(_build_level(level, binding, level_bindings))

    num = _find_num_for_abstract(numbering, abstract_id)
    if num is None:
        num_id = _next_id(numbering, "w:num", "w:numId", default=0)
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        abstract_ref = OxmlElement("w:abstractNumId")
        abstract_ref.set(qn("w:val"), str(abstract_id))
        num.append(abstract_ref)
        _insert_num_before_num_id_mac(numbering, num)
    else:
        num_id = int(num.get(qn("w:numId"), "0"))
    return num_id


def link_style_to_numbering(style, num_id: int, level: int) -> None:
    p_pr = style.element.get_or_add_pPr()
    num_pr = find_or_create_before(
        p_pr,
        "w:numPr",
        (
            "w:suppressLineNumbers",
            "w:pBdr",
            "w:shd",
            "w:tabs",
            "w:spacing",
            "w:ind",
            "w:contextualSpacing",
            "w:jc",
            "w:outlineLvl",
            "w:rPr",
            "w:pPrChange",
        ),
    )
    _write_num_pr(num_pr, num_id, level)


def unlink_style_numbering(style) -> None:
    p_pr = style.element.find(qn("w:pPr"))
    if p_pr is None:
        return
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is not None:
        p_pr.remove(num_pr)


def disable_style_numbering(style) -> None:
    p_pr = style.element.get_or_add_pPr()
    num_pr = find_or_create_before(
        p_pr,
        "w:numPr",
        (
            "w:suppressLineNumbers",
            "w:pBdr",
            "w:shd",
            "w:tabs",
            "w:spacing",
            "w:ind",
            "w:contextualSpacing",
            "w:jc",
            "w:outlineLvl",
            "w:rPr",
            "w:pPrChange",
        ),
    )
    for child in list(num_pr):
        num_pr.remove(child)
    num_id = OxmlElement("w:numId")
    num_id.set(qn("w:val"), "0")
    num_pr.append(num_id)


def set_paragraph_numbering(paragraph, num_id: int, level: int) -> None:
    p_pr = paragraph._element.get_or_add_pPr()
    num_pr = find_or_create_before(
        p_pr,
        "w:numPr",
        (
            "w:suppressLineNumbers",
            "w:pBdr",
            "w:shd",
            "w:tabs",
            "w:spacing",
            "w:ind",
            "w:contextualSpacing",
            "w:jc",
            "w:outlineLvl",
            "w:rPr",
            "w:sectPr",
            "w:pPrChange",
        ),
    )
    _write_num_pr(num_pr, num_id, level)


def disable_paragraph_numbering(paragraph) -> None:
    p_pr = paragraph._element.get_or_add_pPr()
    num_pr = find_or_create_before(
        p_pr,
        "w:numPr",
        (
            "w:suppressLineNumbers",
            "w:pBdr",
            "w:shd",
            "w:tabs",
            "w:spacing",
            "w:ind",
            "w:contextualSpacing",
            "w:jc",
            "w:outlineLvl",
            "w:rPr",
            "w:sectPr",
            "w:pPrChange",
        ),
    )
    for child in list(num_pr):
        num_pr.remove(child)
    num_id = OxmlElement("w:numId")
    num_id.set(qn("w:val"), "0")
    num_pr.append(num_id)


def clear_paragraph_numbering(paragraph) -> None:
    p_pr = paragraph._element.find(qn("w:pPr"))
    if p_pr is None:
        return
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is not None:
        p_pr.remove(num_pr)


def effective_numbering(paragraph) -> EffectiveNumbering | None:
    p_pr = paragraph._element.find(qn("w:pPr"))
    direct = _read_num_pr(p_pr.find(qn("w:numPr")) if p_pr is not None else None)
    if direct is not None:
        return EffectiveNumbering("paragraph", *direct) if direct[0] > 0 else None

    style = paragraph.style
    seen: set[int] = set()
    while style is not None and id(style) not in seen:
        seen.add(id(style))
        style_p_pr = style.element.find(qn("w:pPr"))
        inherited = _read_num_pr(
            style_p_pr.find(qn("w:numPr")) if style_p_pr is not None else None
        )
        if inherited is not None:
            if inherited[0] <= 0:
                return None
            return EffectiveNumbering(f"style:{style.name}", *inherited)
        style = style.base_style
    return None


def managed_abstract_count(doc) -> int:
    numbering = doc.part.numbering_part.element
    return sum(
        1
        for abstract in numbering.findall(qn("w:abstractNum"))
        if _abstract_name(abstract) == MANAGED_ABSTRACT_NAME
    )


def managed_level_text(doc, level: int) -> str:
    level_node = _managed_level_node(doc, level)
    if level_node is None:
        return ""
    level_text = level_node.find(qn("w:lvlText"))
    return level_text.get(qn("w:val"), "") if level_text is not None else ""


def managed_level_start(doc, level: int) -> int | None:
    level_node = _managed_level_node(doc, level)
    if level_node is None:
        return None
    start = level_node.find(qn("w:start"))
    if start is None:
        return None
    try:
        return int(start.get(qn("w:val"), "1"))
    except (TypeError, ValueError):
        return None


def managed_level_restart(doc, level: int) -> int | None:
    level_node = _managed_level_node(doc, level)
    if level_node is None:
        return None
    restart = level_node.find(qn("w:lvlRestart"))
    if restart is None:
        return None
    try:
        return int(restart.get(qn("w:val"), "0"))
    except (TypeError, ValueError):
        return None


def _managed_level_node(doc, level: int):
    abstract = _find_managed_abstract(doc.part.numbering_part.element)
    if abstract is None:
        return None
    return next(
        (
            node
            for node in abstract.findall(qn("w:lvl"))
            if node.get(qn("w:ilvl")) == str(level - 1)
        ),
        None,
    )


def _build_level(level: int, binding, level_bindings: dict):
    level_node = OxmlElement("w:lvl")
    level_node.set(qn("w:ilvl"), str(level - 1))

    start = OxmlElement("w:start")
    start.set(qn("w:val"), str(max(int(getattr(binding, "start_at", 1) or 0), 0)))
    level_node.append(start)

    num_fmt = OxmlElement("w:numFmt")
    num_fmt.set(qn("w:val"), _number_format(binding))
    level_node.append(num_fmt)

    restart = _restart_value(level, getattr(binding, "restart_on", None))
    if restart is not None:
        restart_node = OxmlElement("w:lvlRestart")
        restart_node.set(qn("w:val"), str(restart))
        level_node.append(restart_node)

    if _requires_legal_numbering(level, binding, level_bindings):
        level_node.append(OxmlElement("w:isLgl"))

    level_text = OxmlElement("w:lvlText")
    rendered = _level_text(level, binding)
    separator_mode = str(getattr(binding, "ooxml_separator_mode", "inline") or "inline")
    if separator_mode == "inline":
        rendered += str(getattr(binding, "title_separator", "") or "")
    level_text.set(qn("w:val"), rendered)
    level_node.append(level_text)

    level_jc = OxmlElement("w:lvlJc")
    level_jc.set(qn("w:val"), "left")
    level_node.append(level_jc)

    if separator_mode == "suff":
        suffix = OxmlElement("w:suff")
        suffix.set(qn("w:val"), _suffix_value(binding))
        level_node.append(suffix)
    elif separator_mode == "inline":
        configured_suffix = getattr(binding, "ooxml_suff", None)
        if configured_suffix in {"tab", "space", "nothing"}:
            suffix = OxmlElement("w:suff")
            suffix.set(qn("w:val"), str(configured_suffix))
            level_node.append(suffix)

    indent_attrs = getattr(binding, "ooxml_lvl_ind", None)
    if isinstance(indent_attrs, dict) and indent_attrs:
        p_pr = OxmlElement("w:pPr")
        indent = OxmlElement("w:ind")
        for name, value in indent_attrs.items():
            text = str(value or "").strip()
            if text:
                indent.set(qn(f"w:{name}"), text)
        if indent.attrib:
            p_pr.append(indent)
            level_node.append(p_pr)
    return level_node


def _level_text(level: int, binding) -> str:
    template = str(getattr(binding, "display_template", "") or "")
    if not template:
        core = _normalized_core(getattr(binding, "display_core_style", "arabic"))
        template = _AUTO_TEMPLATE_BY_CORE.get(core, "{nn}")

    chain = parse_heading_number_chain(str(getattr(binding, "chain", "current_only") or ""))
    sources: list[int] = []
    current_level = level
    for segment in reversed(chain):
        if segment == "current":
            sources.append(current_level)
        elif segment == "parent":
            current_level = max(current_level - 1, 1)
            sources.append(current_level)
    sources.reverse()
    if not sources:
        sources = [level]
    chain_text = str(getattr(binding, "chain_separator", ".") or ".").join(
        f"%{source_level}" for source_level in sources
    )
    if "{chain}" in template:
        return template.replace("{chain}", chain_text)
    if len(sources) > 1:
        if _NUMBER_PLACEHOLDER_RE.search(template):
            return _NUMBER_PLACEHOLDER_RE.sub(chain_text, template, count=1)
        return chain_text
    return _NUMBER_PLACEHOLDER_RE.sub(f"%{level}", template)


def _number_format(binding) -> str:
    core = _normalized_core(getattr(binding, "display_core_style", "arabic"))
    return _NUM_FMT_BY_CORE.get(core, "decimal")


def _normalized_core(value) -> str:
    raw = str(value or "arabic").strip()
    return CURRENT_CORE_STYLE_ALIASES.get(raw, raw)


def _requires_legal_numbering(level: int, binding, level_bindings: dict) -> bool:
    chain = parse_heading_number_chain(str(getattr(binding, "chain", "current_only") or ""))
    if "parent" not in chain:
        return False
    current_is_decimal = _number_format(binding) in {"decimal", "decimalZero"}
    if not current_is_decimal:
        return False
    for parent_level in range(1, level):
        parent_binding = level_bindings.get(f"heading{parent_level}")
        if parent_binding is None:
            continue
        display_is_decimal = _number_format(parent_binding) in {"decimal", "decimalZero"}
        reference_core = _normalized_core(
            getattr(parent_binding, "reference_core_style", "arabic")
        )
        reference_is_decimal = _NUM_FMT_BY_CORE.get(reference_core, "decimal") in {
            "decimal",
            "decimalZero",
        }
        if reference_is_decimal and not display_is_decimal:
            return True
    return False


def _restart_value(level: int, restart_on) -> int | None:
    if level <= 1:
        return None
    mode = str(restart_on or "parent").strip().lower().replace("_", "-")
    if mode in {"document", "never", "continuous", "none"}:
        return 0
    match = re.fullmatch(r"(?:heading|level)?\s*(\d+)", mode.replace("-", ""))
    if not match:
        return None
    target = int(match.group(1))
    if target <= 0 or target >= level or target == level - 1:
        return None
    return target


def _suffix_value(binding) -> str:
    configured = getattr(binding, "ooxml_suff", None)
    if configured in {"tab", "space", "nothing"}:
        return str(configured)
    separator = str(getattr(binding, "title_separator", "") or "")
    if separator == "\t":
        return "tab"
    if separator == " ":
        return "space"
    return "nothing"


def _write_num_pr(num_pr, num_id_value: int, level: int) -> None:
    for child in list(num_pr):
        num_pr.remove(child)
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), str(level - 1))
    num_id = OxmlElement("w:numId")
    num_id.set(qn("w:val"), str(num_id_value))
    num_pr.append(ilvl)
    num_pr.append(num_id)


def _read_num_pr(num_pr) -> tuple[int, int] | None:
    if num_pr is None:
        return None
    num_id_node = num_pr.find(qn("w:numId"))
    if num_id_node is None:
        return None
    try:
        num_id = int(num_id_node.get(qn("w:val"), "0"))
    except (TypeError, ValueError):
        return None
    level_node = num_pr.find(qn("w:ilvl"))
    try:
        level = int(level_node.get(qn("w:val"), "0")) if level_node is not None else 0
    except (TypeError, ValueError):
        level = 0
    return num_id, level


def _abstract_name(abstract) -> str:
    name = abstract.find(qn("w:name"))
    return name.get(qn("w:val"), "") if name is not None else ""


def _find_managed_abstract(numbering):
    return next(
        (
            abstract
            for abstract in numbering.findall(qn("w:abstractNum"))
            if _abstract_name(abstract) == MANAGED_ABSTRACT_NAME
        ),
        None,
    )


def _find_num_for_abstract(numbering, abstract_id: int):
    for num in numbering.findall(qn("w:num")):
        abstract_ref = num.find(qn("w:abstractNumId"))
        if abstract_ref is not None and abstract_ref.get(qn("w:val")) == str(abstract_id):
            return num
    return None


def _next_id(numbering, tag: str, attr: str, *, default: int) -> int:
    values: list[int] = []
    for node in numbering.findall(qn(tag)):
        try:
            values.append(int(node.get(qn(attr), str(default))))
        except (TypeError, ValueError):
            continue
    return max(values, default=default) + 1


def _insert_abstract_before_nums(numbering, abstract) -> None:
    first_num = numbering.find(qn("w:num"))
    if first_num is None:
        numbering.append(abstract)
    else:
        numbering.insert(numbering.index(first_num), abstract)


def _insert_num_before_num_id_mac(numbering, num) -> None:
    num_id_mac = numbering.find(qn("w:numIdMac"))
    if num_id_mac is None:
        numbering.append(num)
    else:
        numbering.insert(numbering.index(num_id_mac), num)


__all__ = [
    "MANAGED_ABSTRACT_NAME",
    "EffectiveNumbering",
    "clear_paragraph_numbering",
    "disable_paragraph_numbering",
    "disable_style_numbering",
    "effective_numbering",
    "ensure_heading_numbering_definition",
    "link_style_to_numbering",
    "managed_abstract_count",
    "managed_level_restart",
    "managed_level_start",
    "managed_level_text",
    "set_paragraph_numbering",
    "unlink_style_numbering",
]
