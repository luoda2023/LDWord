"""Whitespace normalization and conservative full/half-width conversion."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from docx.oxml import OxmlElement

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.ooxml_ops import qn

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


XML_NS = "http://www.w3.org/XML/1998/namespace"
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

SPACE_VARIANTS_RE = re.compile(r"[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]")
ZERO_WIDTH_RE = re.compile(r"[\u200B\u200C\u200D\u2060\uFEFF]")
MULTI_SPACE_RE = re.compile(r" {2,}")
URL_EMAIL_PATH_RE = re.compile(
    r"(https?://\S+|www\.\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|[A-Za-z]:\\[^\s]+|\\\\[^\s]+)"
)
REF_NUM_RE = re.compile(r"(\[\s*\d+(?:\s*[-,]\s*\d+)*\s*\]|\(\s*\d+(?:\s*[-,]\s*\d+)*\s*\)|（\s*\d+(?:\s*[-,]\s*\d+)*\s*）)")

HALF_TO_FULL_PUNC = {
    ",": "\uff0c",
    ".": "\u3002",
    ":": "\uff1a",
    ";": "\uff1b",
    "!": "\uff01",
    "?": "\uff1f",
}
FULL_TO_HALF_PUNC = {value: key for key, value in HALF_TO_FULL_PUNC.items()}


class WhitespaceNormalizeModule(BaseModule):
    meta = ModuleMeta(
        name="whitespace_normalize",
        description="\u7a7a\u767d\u4e0e\u5168\u534a\u89d2\u89c4\u8303",
        category="validate",
        requires_config=("whitespace",),
        soft_after=("heading_recognition",),
        soft_consumes=("doc_tree",),
        enabled_by_default=False,
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        ws_cfg = config.whitespace
        if not any(
            (
                ws_cfg.normalize_space_variants,
                ws_cfg.convert_tabs,
                ws_cfg.remove_zero_width,
                ws_cfg.collapse_multiple_spaces,
                ws_cfg.trim_paragraph_edges,
                ws_cfg.smart_full_half_convert,
            )
        ):
            return

        changed_para_count = 0
        changed_text_nodes = 0

        # Compute reference section range to protect GB/T 7714 punctuation.
        doc_tree = getattr(context, "doc_tree", None)
        _ref_section = doc_tree.get_section("references") if doc_tree else None

        for para_index, para in enumerate(doc.paragraphs):
            if _is_skipped_style(para):
                continue
            if _has_complex_content(para._element):
                continue

            para_changed = False
            if ws_cfg.convert_tabs:
                converted_tabs = _replace_tab_elements_with_spaces(para._element)
                if converted_tabs:
                    para_changed = True
                    changed_text_nodes += converted_tabs

            t_nodes = list(para._element.findall(f".//{qn('w:t')}"))
            if not t_nodes:
                continue

            for t_el in t_nodes:
                old = t_el.text or ""
                new = _normalize_inline_text(
                    old,
                    normalize_space_variants=ws_cfg.normalize_space_variants,
                    convert_tabs=ws_cfg.convert_tabs,
                    remove_zero_width=ws_cfg.remove_zero_width,
                    collapse_multiple_spaces=ws_cfg.collapse_multiple_spaces,
                )
                if new != old:
                    t_el.text = new
                    _sync_xml_space_attr(t_el)
                    para_changed = True
                    changed_text_nodes += 1

            if ws_cfg.smart_full_half_convert and (
                ws_cfg.punctuation_by_context
                or ws_cfg.bracket_by_inner_language
                or ws_cfg.fullwidth_alnum_to_halfwidth
                or ws_cfg.quote_by_context
            ):
                _in_ref = (_ref_section is not None
                           and _ref_section.start_index <= para_index <= _ref_section.end_index)
                para_text = "".join((t.text or "") for t in t_nodes)
                para_counts = _count_lang_chars(para_text)
                para_new = _smart_full_half_convert(
                    para_text,
                    para_counts=para_counts,
                    min_confidence=max(1, min(int(ws_cfg.context_min_confidence), 4)),
                    punctuation_by_context=ws_cfg.punctuation_by_context and not _in_ref,
                    bracket_by_inner_language=ws_cfg.bracket_by_inner_language and not _in_ref,
                    fullwidth_alnum_to_halfwidth=ws_cfg.fullwidth_alnum_to_halfwidth,
                    quote_by_context=ws_cfg.quote_by_context,
                    protect_reference_numbering=ws_cfg.protect_reference_numbering,
                )
                if para_new != para_text:
                    node_lengths = [len(t_el.text or "") for t_el in t_nodes]
                    if sum(node_lengths) == len(para_new):
                        pos = 0
                        for t_el, seg_len in zip(t_nodes, node_lengths):
                            old = t_el.text or ""
                            new = para_new[pos:pos + seg_len]
                            pos += seg_len
                            if new != old:
                                t_el.text = new
                                _sync_xml_space_attr(t_el)
                                para_changed = True
                                changed_text_nodes += 1

            if ws_cfg.trim_paragraph_edges and _trim_paragraph_edges(t_nodes):
                para_changed = True

            if not para_changed:
                continue

            changed_para_count += 1
            tracker.record(
                rule_name=self.meta.name,
                target=f"paragraph #{para_index}",
                section="body",
                change_type="text",
                before="whitespace not normalized",
                after="normalized whitespace/full-half-width",
                paragraph_index=para_index,
            )

        if changed_para_count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{changed_para_count} paragraphs",
                section="global",
                change_type="normalize",
                before="mixed whitespace variants",
                after=f"normalized ({changed_text_nodes} text nodes changed)",
                paragraph_index=-1,
            )


def _sync_xml_space_attr(t_el) -> None:
    text = t_el.text or ""
    key = f"{{{XML_NS}}}space"
    if text.startswith(" ") or text.endswith(" "):
        t_el.set(key, "preserve")
    else:
        t_el.attrib.pop(key, None)


def _replace_tab_elements_with_spaces(p_el) -> int:
    changed = 0
    for tab_el in list(p_el.findall(f".//{qn('w:tab')}")):
        parent = tab_el.getparent()
        if parent is None:
            continue
        t_el = OxmlElement("w:t")
        t_el.text = " "
        _sync_xml_space_attr(t_el)
        parent.replace(tab_el, t_el)
        changed += 1
    return changed


def _normalize_inline_text(
    text: str,
    *,
    normalize_space_variants: bool,
    convert_tabs: bool,
    remove_zero_width: bool,
    collapse_multiple_spaces: bool,
) -> str:
    value = text or ""
    if remove_zero_width:
        value = ZERO_WIDTH_RE.sub("", value)
    if normalize_space_variants:
        value = SPACE_VARIANTS_RE.sub(" ", value)
    if convert_tabs:
        value = value.replace("\t", " ")
    if collapse_multiple_spaces:
        value = MULTI_SPACE_RE.sub(" ", value)
    return value


def _is_skipped_style(para) -> bool:
    style = getattr(para, "style", None)
    style_name = (getattr(style, "name", "") or "")
    low = style_name.lower()
    if any(key in low for key in ("heading", "toc", "caption", "code")):
        return True
    if any(key in style_name for key in ("\u6807\u9898", "\u76ee\u5f55", "\u9898\u6ce8", "\u4ee3\u7801")):
        return True
    return False


def _has_complex_content(p_el) -> bool:
    if p_el.findall(f".//{{{MATH_NS}}}oMath") or p_el.findall(f".//{{{MATH_NS}}}oMathPara"):
        return True
    if p_el.findall(f".//{qn('w:object')}") or p_el.findall(f".//{qn('w:drawing')}"):
        return True
    if p_el.findall(f".//{qn('w:pict')}"):
        return True
    if p_el.find(f".//{qn('w:instrText')}") is not None:
        return True
    return False


def _trim_paragraph_edges(t_nodes: list) -> bool:
    changed = False
    first_idx = None
    last_idx = None

    for index, t_el in enumerate(t_nodes):
        if t_el.text:
            first_idx = index
            break
    for index in range(len(t_nodes) - 1, -1, -1):
        if t_nodes[index].text:
            last_idx = index
            break

    if first_idx is not None:
        old = t_nodes[first_idx].text or ""
        new = old.lstrip(" ")
        if new != old:
            t_nodes[first_idx].text = new
            _sync_xml_space_attr(t_nodes[first_idx])
            changed = True

    if last_idx is not None:
        old = t_nodes[last_idx].text or ""
        new = old.rstrip(" ")
        if new != old:
            t_nodes[last_idx].text = new
            _sync_xml_space_attr(t_nodes[last_idx])
            changed = True

    return changed


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x3400 <= cp <= 0x4DBF
        or 0x4E00 <= cp <= 0x9FFF
        or 0x3040 <= cp <= 0x30FF
        or 0xAC00 <= cp <= 0xD7AF
    )


def _is_latin_or_digit(ch: str) -> bool:
    if not ch:
        return False
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch.isdigit()


def _script_kind(ch: str) -> str | None:
    if _is_cjk(ch):
        return "zh"
    if _is_latin_or_digit(ch):
        return "en"
    return None


def _count_lang_chars(text: str) -> tuple[int, int]:
    zh = 0
    en = 0
    for ch in text:
        if _is_cjk(ch):
            zh += 1
        elif _is_latin_or_digit(ch):
            en += 1
    return zh, en


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans.sort()
    merged = [spans[0]]
    for start, end in spans[1:]:
        merged_start, merged_end = merged[-1]
        if start <= merged_end:
            merged[-1] = (merged_start, max(merged_end, end))
        else:
            merged.append((start, end))
    return merged


def _build_protected_spans(text: str, *, protect_reference_numbering: bool) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in URL_EMAIL_PATH_RE.finditer(text):
        spans.append((match.start(), match.end()))
    if protect_reference_numbering:
        for match in REF_NUM_RE.finditer(text):
            spans.append((match.start(), match.end()))
    return _merge_spans(spans)


def _in_spans(idx: int, spans: list[tuple[int, int]]) -> bool:
    for start, end in spans:
        if start <= idx < end:
            return True
        if idx < start:
            return False
    return False


def _fullwidth_alnum_to_half(ch: str) -> str:
    cp = ord(ch)
    if 0xFF10 <= cp <= 0xFF19 or 0xFF21 <= cp <= 0xFF3A or 0xFF41 <= cp <= 0xFF5A:
        return chr(cp - 0xFEE0)
    return ch


def _nearest_script(chars: list[str], idx: int, step: int, max_hops: int = 12) -> str | None:
    hops = 0
    cursor = idx + step
    while 0 <= cursor < len(chars) and hops < max_hops:
        ch = chars[cursor]
        if ch.isspace():
            cursor += step
            hops += 1
            continue
        kind = _script_kind(ch)
        if kind:
            return kind
        cursor += step
        hops += 1
    return None


def _resolve_context_language(chars: list[str], idx: int, para_counts: tuple[int, int], min_confidence: int) -> str | None:
    zh_score = 0
    en_score = 0
    para_zh, para_en = para_counts
    if para_zh >= para_en + 3:
        zh_score += 1
    elif para_en >= para_zh + 3:
        en_score += 1

    left = _nearest_script(chars, idx, -1)
    right = _nearest_script(chars, idx, 1)
    if left == "zh":
        zh_score += 1
    elif left == "en":
        en_score += 1
    if right == "zh":
        zh_score += 1
    elif right == "en":
        en_score += 1

    if zh_score == en_score:
        return None
    if abs(zh_score - en_score) < min_confidence:
        return None
    return "zh" if zh_score > en_score else "en"


def _language_for_inner_text(text: str) -> str | None:
    zh, en = _count_lang_chars(text)
    if zh >= en + 1:
        return "zh"
    if en >= zh + 1:
        return "en"
    return None


def _is_numeric_pair(chars: list[str], idx: int) -> bool:
    return 0 < idx < len(chars) - 1 and chars[idx - 1].isdigit() and chars[idx + 1].isdigit()


def _convert_brackets_by_inner_language(chars: list[str], spans: list[tuple[int, int]]) -> None:
    stack: list[int] = []
    for index, ch in enumerate(chars):
        if ch in {"(", "（"}:
            if not _in_spans(index, spans):
                stack.append(index)
            continue
        if ch not in {")", "）"} or _in_spans(index, spans) or not stack:
            continue
        open_idx = stack.pop()
        inner = "".join(chars[open_idx + 1:index])
        lang = _language_for_inner_text(inner)
        if lang == "zh":
            chars[open_idx] = "（"
            chars[index] = "）"
        elif lang == "en":
            chars[open_idx] = "("
            chars[index] = ")"


def _convert_punctuation_by_context(chars: list[str], spans: list[tuple[int, int]], para_counts: tuple[int, int], min_confidence: int) -> None:
    for index, ch in enumerate(chars):
        if _in_spans(index, spans):
            continue
        if ch in {".", ",", ":"} and _is_numeric_pair(chars, index):
            continue
        if ch in HALF_TO_FULL_PUNC:
            lang = _resolve_context_language(chars, index, para_counts, min_confidence)
            if lang == "zh":
                chars[index] = HALF_TO_FULL_PUNC[ch]
            continue
        if ch in FULL_TO_HALF_PUNC:
            lang = _resolve_context_language(chars, index, para_counts, min_confidence)
            if lang == "en":
                chars[index] = FULL_TO_HALF_PUNC[ch]


def _convert_quotes_by_context(chars: list[str], spans: list[tuple[int, int]], para_counts: tuple[int, int], min_confidence: int) -> None:
    double_open = True
    single_open = True
    for index, ch in enumerate(chars):
        if _in_spans(index, spans):
            continue
        if ch not in {'"', "'", "\u201c", "\u201d", "\u2018", "\u2019"}:
            continue
        if ch == "'" and 0 < index < len(chars) - 1 and chars[index - 1].isalnum() and chars[index + 1].isalnum():
            continue
        lang = _resolve_context_language(chars, index, para_counts, min_confidence)
        if lang == "en":
            if ch in {"\u201c", "\u201d", '"'}:
                chars[index] = '"'
            else:
                chars[index] = "'"
            continue
        if lang != "zh":
            continue
        if ch in {"\u201c", "\u201d", '"'}:
            chars[index] = "\u201c" if double_open else "\u201d"
            double_open = not double_open
        else:
            chars[index] = "\u2018" if single_open else "\u2019"
            single_open = not single_open


def _smart_full_half_convert(
    text: str,
    *,
    para_counts: tuple[int, int],
    min_confidence: int,
    punctuation_by_context: bool,
    bracket_by_inner_language: bool,
    fullwidth_alnum_to_halfwidth: bool,
    quote_by_context: bool,
    protect_reference_numbering: bool,
) -> str:
    if not text:
        return text

    chars = list(text)
    spans = _build_protected_spans(text, protect_reference_numbering=protect_reference_numbering)

    if fullwidth_alnum_to_halfwidth:
        for index, ch in enumerate(chars):
            if _in_spans(index, spans):
                continue
            chars[index] = _fullwidth_alnum_to_half(ch)

    if bracket_by_inner_language:
        _convert_brackets_by_inner_language(chars, spans)

    if punctuation_by_context:
        _convert_punctuation_by_context(chars, spans, para_counts, min_confidence)

    if quote_by_context:
        _convert_quotes_by_context(chars, spans, para_counts, min_confidence)

    return "".join(chars)
